"""Rebuild audit-log rows for trades this machine never saw.

The audit log is local to whichever computer placed the orders. Move the bot
between machines - a Mac to a Windows desktop, say - and the broker keeps the
whole history while the new machine starts from an empty log. `record` then
reports NO_TRADES_YET over an account that plainly has closed round-trips in
it, and every statistic the experiment exists to produce is computed from a
fraction of the evidence.

The broker's own fill activities are the authoritative record, so the missing
rows are reconstructed from those rather than from anything local:

* Round trips are cut where the position actually opens and flattens, not per
  order. A bot exit arrives as three partial fills on one order, and a scale-in
  as several buys; counting orders would report those as separate trades.
* Realized P&L comes from the fill prices Alpaca reports, never from an
  assumed one.
* The regulatory fees Alpaca charges on sales (REG, TAF, CAT) are subtracted.
  They are small - $1.46 across the first three trades - but leaving them out
  puts the record permanently out of step with account equity, and a total
  that does not reconcile is the kind of discrepancy that costs an afternoon
  later.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Alpaca reports a flat position as an exact zero, but quantities arrive as
# strings and are summed as floats, so compare against a tolerance rather than
# against 0.0. A residue of 1e-9 share would otherwise hold a trip open forever.
FLAT_TOLERANCE = 1e-6


def round_trips_from_fills(fills: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    """Cut a stream of fills into completed round trips, one per symbol cycle.

    A trip opens when a symbol's position leaves zero and closes when it
    returns to zero. A position still open at the end of the stream is not a
    trip and is deliberately dropped: an unrealized number is not a result.
    """
    by_symbol: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for fill in fills:
        by_symbol[str(fill.get("symbol", ""))].append(fill)

    trips: List[Dict[str, object]] = []
    for symbol, rows in by_symbol.items():
        if not symbol:
            continue
        rows = sorted(rows, key=lambda r: str(r.get("transaction_time", "")))
        position = 0.0
        open_trip: Optional[Dict[str, object]] = None
        for row in rows:
            side = str(row.get("side", "")).lower()
            quantity = abs(float(row.get("qty", 0.0) or 0.0))
            price = float(row.get("price", 0.0) or 0.0)
            stamp = str(row.get("transaction_time", ""))
            if quantity <= 0 or side not in ("buy", "sell"):
                continue

            if open_trip is None:
                open_trip = {
                    "symbol": symbol, "opened": stamp, "closed": None,
                    "quantity": 0.0, "cost": 0.0, "proceeds": 0.0,
                }

            if side == "buy":
                position += quantity
                open_trip["quantity"] = float(open_trip["quantity"]) + quantity
                open_trip["cost"] = float(open_trip["cost"]) + quantity * price
            else:
                position -= quantity
                open_trip["proceeds"] = float(open_trip["proceeds"]) + quantity * price

            if abs(position) <= FLAT_TOLERANCE:
                open_trip["closed"] = stamp
                position = 0.0
                trips.append(open_trip)
                open_trip = None

    return sorted(trips, key=lambda t: str(t["closed"]))


def allocate_fees(
    trips: Sequence[Dict[str, object]], fees: Iterable[Dict[str, object]]
) -> Tuple[List[float], float]:
    """Spread each day's fees across the trips that closed that day.

    Alpaca bills REG/TAF/CAT once per day against that day's sale proceeds,
    not per order, so there is no per-trade figure to read. Proceeds are the
    basis Alpaca itself names in the fee description, so trips closing on the
    same day are charged in proportion to what they sold.

    Returns one fee per trip and the total that matched no trip, which is
    reported rather than quietly absorbed - an unallocated fee means the fill
    history and the fee history disagree, and that is worth seeing.
    """
    per_trip = [0.0] * len(trips)
    by_day: Dict[str, float] = defaultdict(float)
    for fee in fees:
        day = str(fee.get("date", ""))[:10]
        by_day[day] += abs(float(fee.get("net_amount", 0.0) or 0.0))

    unallocated = 0.0
    for day, amount in by_day.items():
        indexes = [i for i, t in enumerate(trips) if str(t["closed"])[:10] == day]
        basis = sum(float(trips[i]["proceeds"]) for i in indexes)
        if not indexes or basis <= 0:
            unallocated += amount
            continue
        for i in indexes:
            per_trip[i] += amount * float(trips[i]["proceeds"]) / basis
    return per_trip, round(unallocated, 4)


def audit_rows_for(
    trips: Sequence[Dict[str, object]], fees_per_trip: Sequence[float]
) -> List[Dict[str, object]]:
    """Render trips as the `entry`/`exit` pairs `record.from_audit_log` reads."""
    rows: List[Dict[str, object]] = []
    for trip, fee in zip(trips, fees_per_trip):
        cost = float(trip["cost"])
        proceeds = float(trip["proceeds"])
        quantity = float(trip["quantity"])
        net = proceeds - cost - fee
        entry_price = (cost / quantity) if quantity else 0.0
        shared = {
            "symbol": trip["symbol"],
            "quantity": round(quantity, 6),
            "entry_price": round(entry_price, 6),
            "cost_basis": round(cost, 2),
        }
        rows.append({
            "at": str(trip["opened"]),
            "event": "entry",
            "dry_run": False,
            "backfilled": True,
            "source": "broker_fill_activities",
            "detail": dict(shared),
        })
        exit_detail = dict(shared)
        exit_detail.update({
            "proceeds": round(proceeds, 2),
            "fees": round(fee, 4),
            "realized_pnl": round(net, 2),
            "return_fraction": round((net / cost) if cost else 0.0, 6),
        })
        rows.append({
            "at": str(trip["closed"]),
            "event": "exit",
            "dry_run": False,
            "backfilled": True,
            "source": "broker_fill_activities",
            "detail": exit_detail,
        })
    return rows


def _existing_rows(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    rows = []
    # utf-8-sig, not utf-8: a log touched by a PowerShell redirect carries a
    # BOM, and json.loads treats that as a syntax error on line one.
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _already_recorded(existing: Sequence[Dict[str, object]], trip: Dict[str, object]) -> bool:
    """True when the local log already covers this trip.

    Matched on symbol and window rather than on an id, because the local rows
    were written by a different process that knew nothing about the broker's
    activity ids. Any entry or exit for the same symbol inside the trip's own
    span is the same trade.
    """
    opened, closed = str(trip["opened"]), str(trip["closed"])
    for row in existing:
        if row.get("event") not in ("entry", "exit"):
            continue
        detail = row.get("detail") or {}
        if str(detail.get("symbol", "")) != str(trip["symbol"]):
            continue
        if opened <= str(row.get("at", "")) <= closed:
            return True
    return False


def merge_into_log(path: Path, trips: Sequence[Dict[str, object]],
                   fees_per_trip: Sequence[float]) -> Dict[str, object]:
    """Add the trips the log is missing, in timestamp order. Safe to re-run.

    The file is rewritten whole and sorted by `at`, so a backfilled trade sits
    where it happened rather than after everything that came later. Rows the
    log already has are left exactly as they were.
    """
    existing = _existing_rows(path)
    wanted, skipped = [], []
    for trip, fee in zip(trips, fees_per_trip):
        (skipped if _already_recorded(existing, trip) else wanted).append((trip, fee))

    added = audit_rows_for([t for t, _ in wanted], [f for _, f in wanted])
    if added:
        merged = existing + added
        merged.sort(key=lambda r: str(r.get("at", "")))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(json.dumps(r, sort_keys=True, default=str) for r in merged) + "\n",
            encoding="utf-8",
        )
    return {
        "trips_found": len(trips),
        "trips_added": len(wanted),
        "trips_already_present": len(skipped),
        "rows_added": len(added),
        "symbols_added": sorted({str(t["symbol"]) for t, _ in wanted}),
        "realized_pnl_added": round(
            sum(float(t["proceeds"]) - float(t["cost"]) - f for t, f in wanted), 2
        ),
    }

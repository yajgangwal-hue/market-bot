"""H-0022 Part I - does the emulator recognise capital it has earned?

READ-ONLY. No strategy change, no counterfactual, no promotion.

THE THREE QUESTIONS, kept apart on purpose (an accounting difference
is not an alpha source):

  A ACCOUNTING     does it record realised gains correctly?
  B AVAILABILITY   does realised capital become spendable in time?
  C OPPORTUNITY    would faster recognition buy anything?

THE ORDER OF OPERATIONS INSIDE ONE SESSION, traced from portfolio.py:

  section 1  pending fills          cash -= outlay      (line ~389)
             ONLY for entry_fill="next_open". Production is
             "signal_close", so this path is not the production path.
  section 2  exits                  cash += proceeds    (line ~704)
  section 2  equity = cash + invested                   (line ~736)
  section 3  entries at the signal close
                                    if outlay > cash -> rejected_for_capacity
                                                        (line ~1007)

So under the production candidate an exit's proceeds are credited in
section 2 and the entry cash test happens in section 3 of the SAME
session. That is the fact this script verifies rather than assumes.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.forward import frozen_fingerprint          # noqa: E402
from event_aware_trader.mean_reversion import (                    # noqa: E402
    MeanReversionConfig, conviction as shipped_conviction)
from event_aware_trader.phase5.metrics import measure              # noqa: E402
from event_aware_trader.research import (                          # noqa: E402
    PRODUCTION_CANDIDATE, production_report)
from forensics_regime import load                                   # noqa: E402

FP = "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b"
ATTRIB = REPO / "docs" / "phase5" / "h0015-attribution.json"
OUT = REPO / "docs" / "phase5" / "h0022-gain-recognition.json"
_conv = {}


def conviction(symbol, history):
    k = (symbol, len(history), history[0].timestamp if history else None)
    v = _conv.get(k)
    if v is None:
        v = _conv[k] = shipped_conviction(history[-40:])
    return v


def main():
    if frozen_fingerprint() != FP:
        print("REFUSED: fingerprint moved.")
        return 2
    print("fingerprint {0} | entry_fill={1}".format(
        FP[:16], PRODUCTION_CANDIDATE.get("entry_fill")))

    series = load()
    rep = production_report(series, conviction=conviction, dataset="decade",
                            purpose="rejection_test",
                            mr_config=MeanReversionConfig())
    m = measure(rep, "BASELINE").as_dict()
    print("baseline {0:+.10%} / {1} trades".format(m["total_return"],
                                                   m["trades"]))
    if abs(m["total_return"] - 0.585889) > 5e-7 or m["trades"] != 698:
        print("STOPPED: baseline not reproduced.")
        return 2

    # ---- A. ACCOUNTING IDENTITIES --------------------------------------
    realized = sum(t.net_pnl for t in rep.trades)
    identity_equity = abs(rep.equity - (rep.cash + rep.invested))
    identity_realized = abs(rep.realized_pnl - realized)
    # starting cash + realised + unrealised == equity
    unrealized = rep.invested - sum(
        p.entry_price * p.quantity for p in rep.open_positions)
    identity_full = abs((rep.starting_cash + realized + unrealized)
                        - rep.equity)
    print("\nA. ACCOUNTING IDENTITIES")
    print("  equity == cash + invested          : gap {0:.10f}".format(
        identity_equity))
    print("  report.realized_pnl == sum(net_pnl): gap {0:.10f}".format(
        identity_realized))
    print("  start + realised + unrealised == equity: gap {0:.10f}".format(
        identity_full))
    print("  starting_cash {0:,.2f} | cash {1:,.2f} | invested {2:,.2f} "
          "| equity {3:,.2f}".format(rep.starting_cash, rep.cash,
                                     rep.invested, rep.equity))
    print("  realised P&L {0:,.2f} | unrealised {1:,.2f} | open {2}".format(
        realized, unrealized, len(rep.open_positions)))

    # ---- B. CAPITAL AVAILABILITY ---------------------------------------
    # Which sessions saw a cash rejection, and did that session ALSO close
    # a profitable position whose proceeds were credited first?
    rows = json.loads(ATTRIB.read_text())["rows"]
    rejected_days = defaultdict(int)
    for symbol, day, outcome in rows:
        if outcome == "cash":
            rejected_days[day] += 1
    exits_by_day = defaultdict(list)
    for t in rep.trades:
        exits_by_day[t.exit_time.date().isoformat()].append(t)
    entries_by_day = defaultdict(list)
    for t in rep.trades:
        entries_by_day[t.entry_time.date().isoformat()].append(t)

    same_day = [d for d in rejected_days if d in exits_by_day]
    proceeds_on_those = sum(
        t.exit_price * t.quantity for d in same_day for t in exits_by_day[d])
    gains_on_those = sum(
        t.net_pnl for d in same_day for t in exits_by_day[d])
    print("\nB. CAPITAL AVAILABILITY")
    print("  cash-rejected candidates      : {0}".format(sum(rejected_days.values())))
    print("  distinct sessions with a rejection: {0}".format(len(rejected_days)))
    print("  of those, sessions that ALSO closed a position: {0}".format(
        len(same_day)))
    print("  proceeds credited on those sessions: ${0:,.0f}".format(
        proceeds_on_those))
    print("  realised P&L on those sessions     : ${0:,.0f}".format(
        gains_on_those))
    print("  rejected_for_capacity counter      : {0}".format(
        rep.rejected_for_capacity))

    # Were entries actually taken on the SAME session as exits? If the
    # emulator could not spend same-session proceeds, this would be 0.
    both = sorted(set(entries_by_day) & set(exits_by_day))
    entries_on_exit_days = sum(len(entries_by_day[d]) for d in both)
    print("\n  sessions with BOTH an exit and an entry: {0}".format(len(both)))
    print("  entries taken on those sessions        : {0}".format(
        entries_on_exit_days))
    print("  -> a non-zero count proves section-2 proceeds are spendable")
    print("     by section 3 of the same session.")

    out = {
        "fingerprint": FP,
        "entry_fill": PRODUCTION_CANDIDATE.get("entry_fill"),
        "baseline": {"total_return": m["total_return"], "trades": m["trades"]},
        "accounting": {
            "equity_minus_cash_plus_invested": identity_equity,
            "realized_pnl_gap": identity_realized,
            "full_identity_gap": identity_full,
            "starting_cash": rep.starting_cash, "cash": rep.cash,
            "invested": rep.invested, "equity": rep.equity,
            "realized": realized, "unrealized": unrealized,
            "open_positions": len(rep.open_positions)},
        "availability": {
            "cash_rejected": sum(rejected_days.values()),
            "rejection_sessions": len(rejected_days),
            "rejection_sessions_with_an_exit": len(same_day),
            "proceeds_on_those_sessions": proceeds_on_those,
            "realised_pnl_on_those_sessions": gains_on_those,
            "rejected_for_capacity_counter": rep.rejected_for_capacity,
            "sessions_with_exit_and_entry": len(both),
            "entries_on_exit_sessions": entries_on_exit_days},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=str))
    print("\nwrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

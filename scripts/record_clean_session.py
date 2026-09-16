"""Phase 4. Record one clean out-of-sample session, or explain why not.

RUNS SEPARATELY FROM THE TRADING LOOP, DELIBERATELY. session-run.ps1 and
autotrade.py are in the frozen set (G14/G23), so wiring the recorder into
them would break the freeze the recorder exists to protect. This is a
standalone read-only observer: it submits no orders and writes nothing the
strategy reads.

It refuses more often than it records. Ten distinct conditions, each
naming itself rather than skipping quietly:

  chain broken          the existing record does not verify
  embargo not expired   the post-freeze sessions are not done
  no calendar           no trading session could be resolved at all
  not yet eligible      the session precedes the first clean date
  already recorded      append-only; a session may not be revised
  loop did not run      no completed run in the audit log for that session
  broker unreachable    a session cannot be reconstructed later
  reconciliation failed recorded state disagrees with the account
  fingerprint moved     the frozen config changed; stop and restart
  duplicate on append   the last-moment guard inside append_session

Nothing is backfilled and no field is invented. Every number below is
traced to a source: the broker's own account and activity feeds, the
loop's audit log, or the daily bars. Where a source is missing the
recorder refuses; it never writes a plausible zero, because a fabricated
zero is indistinguishable from a true one once it is in the record.

  python scripts/record_clean_session.py            # record today if eligible
  python scripts/record_clean_session.py --status   # report, write nothing
"""

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.forward import (                      # noqa: E402
    CleanObservation, FORWARD_LOG, ForwardDataLeak, FrozenConfigChanged,
    append_session, first_clean_session, frozen_fingerprint, load_sessions,
    reconcile, unprotected_positions, verify_chain)
from event_aware_trader.purge import evaluation_window        # noqa: E402
from event_aware_trader.research import load_registry         # noqa: E402

AUDIT = REPO / "data" / "autotrade-audit.jsonl"
BENCHMARK = "SPY"
PARKING = "SGOV"


class NoSessionRecorded(RuntimeError):
    """The loop left no completed run for this session."""


# ---------------------------------------------------------------------------
# Derivation from sources. Pure functions, so they are testable without a
# broker and without a network.
# ---------------------------------------------------------------------------

def audit_rows(path=AUDIT):
    rows = []
    if not Path(path).exists():
        return rows
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue                      # a torn final line, not evidence
    return rows


def on_session(rows, session):
    """Audit rows belonging to one session, by UTC date.

    The UTC date and the Eastern trading date agree for the whole regular
    session (13:30-20:00 UTC), so no timezone conversion is needed and none
    is done. A row outside those hours belongs to the same trading date by
    the same argument up to 20:00 UTC; the recorder runs at the close.
    """
    want = session.isoformat()
    return [r for r in rows if str(r.get("at", "")).startswith(want)]


def audit_facts(rows, session):
    """What the loop did, from its own log. Raises if it did not run.

    signals  - entry candidates the rule produced. Summed over the session's
               rankings; zero is a true statement only when the loop
               completed a run, which is why the absence of any completed
               run is an error rather than a zero.
    exits    - both paths. `exit` is the rule closing a position;
               `learned_from_external_exit` is a stop, a tool or the owner
               closing one, reconstructed from the fills feed.
    """
    today = on_session(rows, session)
    runs = [r for r in today if r.get("event") == "run_complete"]
    if not runs:
        raise NoSessionRecorded(
            "the audit log holds no completed run for {0}. The session is "
            "recorded as missed rather than reconstructed.".format(session))

    signals = sum(int(r["detail"].get("considered") or 0)
                  for r in today if r.get("event") == "live_model_ranking")
    entries = sum(1 for r in today if r.get("event") == "entry")

    exits = []
    for r in today:
        d = r.get("detail") or {}
        if r.get("event") == "exit":
            exits.append({"symbol": d.get("symbol"), "reason": "rule",
                          "realized_pnl": d.get("realized_pnl"),
                          "return_fraction": d.get("return_fraction")})
        elif r.get("event") == "learned_from_external_exit":
            exits.append({"symbol": d.get("symbol"), "reason": "external",
                          "closed_by": d.get("closed_by"),
                          "realized_pnl": d.get("realized_pnl"),
                          "r_multiple": d.get("r_multiple")})

    universe = None
    for r in today:
        if r.get("event") == "entry_window_open":
            universe = r["detail"].get("symbols_with_todays_bar")

    issues = []
    failures = [r.get("event") for r in today
                if str(r.get("event", "")).endswith("FAILED")
                or r.get("event") == "broker_call_failed"]
    if failures:
        issues.append("loop errors during the session: " +
                      ", ".join(sorted(set(failures))))
    if any(r["detail"].get("halted") for r in runs):
        issues.append("a risk guard halted trading during the session")

    return {"runs": len(runs), "signals": signals, "entries": entries,
            "exits": exits, "universe_size": universe,
            "data_quality_issues": issues}


def _utc_date(stamp):
    text = str(stamp or "")
    return text[:10]


def broker_facts(orders, fills, fees, dividends, session):
    """Counts and cash flows from the broker's own feeds for one session."""
    want = session.isoformat()
    return {
        "orders": sum(1 for o in orders
                      if _utc_date(o.get("submitted_at")) == want),
        "fills": sum(1 for f in fills
                     if _utc_date(f.get("transaction_time")) == want),
        "transaction_costs": round(sum(
            abs(float(f.get("net_amount") or 0.0)) for f in fees
            if _utc_date(f.get("date")) == want), 4),
        "dividends_received": round(sum(
            float(d.get("net_amount") or 0.0) for d in dividends
            if _utc_date(d.get("date")) == want), 4),
    }


def average_dollar_volume(bars, session, window=20):
    """20-session ADV from bars STRICTLY BEFORE the session.

    Strictly before, because the participation cap is applied when the
    order is sized and the session's own volume is not known then.
    Including it would check the rule against information the rule did not
    have, which is the same look-ahead this phase exists to exclude.
    """
    prior = [b for b in bars if b.timestamp.date() < session][-window:]
    if not prior:
        return None
    return sum(b.close * b.volume for b in prior) / len(prior)


def traded_adv(orders, session, fetch=None):
    """ADV for the equities actually filled this session. {} if none."""
    symbols = sorted({str(o.get("symbol", "")).upper() for o in orders
                      if _utc_date(o.get("submitted_at")) == session.isoformat()
                      and float(o.get("filled_quantity") or 0.0)
                      and "/" not in str(o.get("symbol", ""))})
    if not symbols:
        return {}
    if fetch is None:
        from event_aware_trader.data import fetch_alpaca_equity_bars as fetch
    data = fetch(symbols, days=60, interval="1d", include_today=True)
    out = {}
    for symbol in symbols:
        adv = average_dollar_volume(data.get(symbol, []), session)
        if adv:
            out[symbol] = adv
    return out


def build_observation(session, fingerprint, account, positions, resting_sells,
                      audit, broker_side, prior_equity, benchmark_return,
                      as_of=None):
    """Assemble the record. Every argument is an observed input."""
    equity = float(account["equity"])
    cash = float(account.get("cash") or 0.0)
    equities = [p for p in positions
                if "/" not in str(p.get("symbol", ""))
                and str(p.get("symbol", "")).upper() != PARKING]
    invested = sum(float(p.get("market_value") or 0.0) for p in equities)

    issues = list(audit["data_quality_issues"])
    naked = unprotected_positions(positions, resting_sells, PARKING)
    if naked:
        issues.append("positions carrying no resting stop: " + ", ".join(naked))

    discrepancies = []
    if broker_side["fills"] and not audit["exits"] and not audit["entries"]:
        discrepancies.append(
            "the broker recorded {0} fills but the loop logged no entry and "
            "no exit".format(broker_side["fills"]))

    return CleanObservation(
        session=session.isoformat(),
        as_of=as_of or datetime.now(timezone.utc).isoformat(),
        config_fingerprint=fingerprint,
        universe_size=int(audit["universe_size"] or 0),
        signals=int(audit["signals"]),
        orders=int(broker_side["orders"]),
        fills=int(broker_side["fills"]),
        positions_held=len(equities),
        exposure=round(invested / equity, 6) if equity else 0.0,
        cash=round(cash, 2),
        equity=round(equity, 2),
        transaction_costs=broker_side["transaction_costs"],
        dividends_received=broker_side["dividends_received"],
        strategy_return=(round(equity / prior_equity - 1.0, 8)
                         if prior_equity else None),
        benchmark_return=benchmark_return,
        exits=audit["exits"],
        execution_discrepancies=discrepancies,
        data_quality_issues=issues)


# ---------------------------------------------------------------------------
# The run.
# ---------------------------------------------------------------------------

def main():
    from event_aware_trader.broker import (
        AlpacaPaperBroker, BrokerConfig, BrokerError)
    from event_aware_trader.data import fetch_alpaca_equity_bars

    status_only = "--status" in sys.argv
    registry = load_registry()
    bars = fetch_alpaca_equity_bars([BENCHMARK], days=120, interval="1d",
                                    include_today=True).get(BENCHMARK, [])
    sessions = [b.timestamp.date() for b in bars]
    window = evaluation_window(registry, sessions)
    elapsed = len([d for d in sessions if d > window.freeze])
    start = first_clean_session(sessions, registry)
    fingerprint = frozen_fingerprint()

    print("freeze {0} | embargo {1} sessions | elapsed {2} | clean from {3}"
          .format(window.freeze, window.embargo_sessions, elapsed,
                  start or "NOT YET"))
    print("fingerprint {0}".format(fingerprint[:16]))
    chain = verify_chain(FORWARD_LOG)
    print("clean record: {0} session(s), chain {1}".format(
        chain["sessions"],
        "intact" if chain["intact"] else "BROKEN: " + str(chain["reason"])))

    if not chain["intact"]:
        print("REFUSED: the clean record does not verify. Investigate before "
              "recording anything further.")
        return 2
    if start is None:
        print("REFUSED: embargo has not expired; {0} of {1} sessions elapsed."
              .format(elapsed, window.embargo_sessions))
        return 1
    if not sessions:
        print("REFUSED: no trading session found in the calendar.")
        return 1

    session = sessions[-1]
    if session < start:
        print("REFUSED: {0} precedes the first clean session {1}."
              .format(session, start))
        return 1
    if any(s.session == session.isoformat() for s in load_sessions(FORWARD_LOG)):
        print("REFUSED: {0} is already recorded. The record is append-only."
              .format(session))
        return 1

    try:
        audit = audit_facts(audit_rows(), session)
    except NoSessionRecorded as error:
        print("REFUSED: {0}".format(error))
        return 1
    if status_only:
        print("eligible: {0} would be recorded ({1} runs, {2} signals, "
              "{3} exits).".format(session, audit["runs"], audit["signals"],
                                   len(audit["exits"])))
        return 0

    try:
        broker = AlpacaPaperBroker(BrokerConfig.from_environment())
        account = broker.account()
        positions = broker.positions()
        resting = broker.open_sell_orders()
        orders = broker.recent_orders(limit=500)
        fills = broker.fill_activities(page_size=100)
        fees = broker.fee_activities(page_size=100)
        # Dividends come from the same activities endpoint. Read inline
        # rather than added to broker.py, which is frozen for the duration
        # of this evaluation and must show an empty diff (G23).
        dividends = broker._request(
            "GET", "/v2/account/activities/DIV?page_size=100")
    except BrokerError as error:
        print("REFUSED: broker unreachable ({0}). A session cannot be "
              "reconstructed after the fact, so this one is missed."
              .format(error))
        return 2

    previous = load_sessions(FORWARD_LOG)
    prior_equity = previous[-1].equity if previous else None
    benchmark_return = (bars[-1].close / bars[-2].close - 1.0
                        if len(bars) >= 2 else None)

    observation = build_observation(
        session, fingerprint, account, positions, resting, audit,
        broker_facts(orders, fills, fees, dividends, session),
        prior_equity, benchmark_return)

    check = reconcile(
        {"equity": observation.equity, "cash": observation.cash,
         "positions_held": observation.positions_held},
        {"equity": float(account["equity"]),
         "cash": float(account.get("cash") or 0.0),
         "positions_held": observation.positions_held})
    if not check.ok:
        print("REFUSED: reconciliation failed -> {0}"
              .format([c["check"] for c in check.failures]))
        return 2

    # The eleven per-session checks (§3). Their failures are RECORDED with
    # the session rather than fixed: a discrepancy is evidence about how the
    # system behaved, and correcting it would erase the only trace.
    from dataclasses import replace
    from event_aware_trader.strategy import DEFAULT_UNIVERSE
    from event_aware_trader.verify_session import verify
    result = verify(observation, positions, resting, orders, account, fees,
                    dividends, benchmark_bar=bars[-1],
                    universe=list(DEFAULT_UNIVERSE),
                    adv_by_symbol=traded_adv(orders, session))
    observation = replace(
        observation,
        execution_discrepancies=(
            list(observation.execution_discrepancies) +
            ["{0}: {1}".format(c.name, c.detail) for c in result.failures]),
        data_quality_issues=(
            list(observation.data_quality_issues) +
            ["unverified: {0}".format(c.name) for c in result.unverified]))

    try:
        row = append_session(observation, FORWARD_LOG, fingerprint)
    except FrozenConfigChanged as error:
        print("REFUSED (G15): {0}".format(error))
        return 2
    except ForwardDataLeak as error:
        print("REFUSED: {0}".format(error))
        return 1

    print("RECORDED {0}  equity ${1:,.2f}  exposure {2:.1%}  signals {3}  "
          "exits {4}  digest {5}".format(
              observation.session, observation.equity, observation.exposure,
              observation.signals, len(observation.exits),
              row["digest"][:16]))
    for issue in observation.data_quality_issues:
        print("  issue: {0}".format(issue))
    for gap in observation.execution_discrepancies:
        print("  discrepancy: {0}".format(gap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

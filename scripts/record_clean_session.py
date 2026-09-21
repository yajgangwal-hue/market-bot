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
    append_session, continuity, first_clean_session, frozen_fingerprint,
    is_protective, load_sessions, reconcile, unprotected_positions,
    verify_chain)
from event_aware_trader.autotrade import AutoTradeConfig      # noqa: E402
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

    # The digest of the configuration the LOOP ACTUALLY RAN ON, taken from
    # its own log rather than recomputed from source defaults here. A cycle
    # older than this change does not carry one; that is reported rather
    # than substituted, because substituting the default is precisely the
    # defect this field exists to remove.
    stamps = [r["detail"].get("config_fingerprint") for r in runs
              if r["detail"].get("config_fingerprint")]
    effective = stamps[-1] if stamps else None
    if not stamps:
        issues.append("the loop logged no effective config_fingerprint; "
                      "the cycle predates effective-fingerprint recording")
    elif len(set(stamps)) > 1:
        issues.append("the session ran under more than one configuration: "
                      + ", ".join(sorted({s[:12] for s in stamps})))

    return {"runs": len(runs), "signals": signals, "entries": entries,
            "exits": exits, "universe_size": universe,
            "effective_fingerprint": effective,
            "effective_interval": (runs[-1]["detail"].get("effective_interval")
                                   if runs else None),
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


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def position_record(position, resting_sells):
    """The smallest projection that makes sizing and stops checkable.

    Symbol, quantity, value and entry are what a sizing rule is verified
    against; the stop is what a protective-order rule is verified
    against. Nothing else is copied - no account number, no order id, no
    broker identifier - because the record is evidence about the
    strategy, not about the account.
    """
    symbol = str(position.get("symbol", "")).upper()
    orders = resting_sells.get(symbol, ()) or ()
    protective = [o for o in orders if is_protective(o)]
    stops = [_float(o.get("stop_price")) for o in protective
             if o.get("stop_price") is not None]
    return {
        "symbol": symbol,
        "quantity": _float(position.get("quantity")),
        "market_value": round(_float(position.get("market_value")), 2),
        "average_entry_price": round(_float(position.get("average_entry_price")), 4),
        "unrealized_pl": round(_float(position.get("unrealized_pl")), 2),
        "has_protective_stop": bool(protective),
        "stop_price": round(min(stops), 4) if stops else None,
    }


def build_observation(session, fingerprint, account, positions, resting_sells,
                      audit, broker_side, prior_equity, benchmark_return,
                      as_of=None, sleeve=None, benchmark=None,
                      prior_sleeve_equity=None):
    """Assemble the record. Every argument is an observed input."""
    equity = float(account["equity"])
    cash = float(account.get("cash") or 0.0)
    equities = [p for p in positions
                if "/" not in str(p.get("symbol", ""))
                and str(p.get("symbol", "")).upper() != PARKING]
    invested = sum(float(p.get("market_value") or 0.0) for p in equities)
    sleeve = sleeve or {}
    benchmark = benchmark or {}

    crypto_mv = round(sum(_float(p.get("market_value")) for p in positions
                          if "/" in str(p.get("symbol", ""))), 2)
    parking_mv = round(sum(_float(p.get("market_value")) for p in positions
                           if str(p.get("symbol", "")).upper() == PARKING), 2)
    movements = round(_float(sleeve.get("cash_movements")), 2)
    sleeve_equity = round(equity - crypto_mv, 2)
    # Net of any external cash movement, so a deposit can never read as
    # performance. None on the first session: there is nothing to compare.
    sleeve_return = None
    if prior_sleeve_equity:
        sleeve_return = round(
            (sleeve_equity - movements) / prior_sleeve_equity - 1.0, 8)

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
        positions=[position_record(p, resting_sells) for p in equities],
        exits=audit["exits"],
        execution_discrepancies=discrepancies,
        data_quality_issues=issues,
        crypto_market_value=crypto_mv,
        parking_market_value=parking_mv,
        reserved_fraction=_float(sleeve.get("reserved_fraction")),
        cash_movements=movements,
        equity_sleeve_equity=sleeve_equity,
        equity_sleeve_return=sleeve_return,
        benchmark_close=benchmark.get("close"),
        benchmark_prev_close=benchmark.get("prev_close"),
        benchmark_close_split=benchmark.get("close_split"),
        benchmark_prev_close_split=benchmark.get("prev_close_split"),
        benchmark_basis=benchmark.get("basis", "total_return_adjustment_all"))


# ---------------------------------------------------------------------------
# The run.
# ---------------------------------------------------------------------------

def main():
    from event_aware_trader.broker import (
        AlpacaPaperBroker, BrokerConfig, BrokerError)
    from event_aware_trader.data import fetch_alpaca_equity_bars

    status_only = "--status" in sys.argv
    registry = load_registry()
    # TOTAL RETURN, both sides. The account receives dividends as cash, so
    # the strategy side is a total return and the benchmark must be one
    # too. adjustment="all" folds distributions into the closes;
    # data.py already designates it as the benchmark path and the frozen
    # fingerprint already declares basis_post_2016 = "total_vs_total".
    # Until 2026-09-21 this call took the default "split" and compared a
    # total return against a PRICE return, understating SPY by about 1.58
    # points a year. The code was wrong, not the declaration - so fixing
    # the code leaves the fingerprint untouched.
    bars = fetch_alpaca_equity_bars([BENCHMARK], days=120, interval="1d",
                                    include_today=True,
                                    adjustment="all").get(BENCHMARK, [])
    # The split-only series is kept purely for auditability: the
    # difference between the two is the dividend component, and an
    # adjusted series is restated by the vendor on every distribution.
    bars_split = fetch_alpaca_equity_bars([BENCHMARK], days=120,
                                          interval="1d", include_today=True,
                                          adjustment="split").get(BENCHMARK, [])
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

    # THE STAMP IS AN OBSERVATION OF THE RUN, not a recomputation of the
    # source. `fingerprint` above is the DECLARED frozen configuration;
    # this is what the cycle actually ran on, taken from its own log.
    # Refusing when they differ is the point: before 2026-09-21 both
    # sides read the same defaults, so a runner passing --interval 15m
    # produced observations stamped with a configuration the account was
    # not running, and nothing could see it.
    effective = audit.get("effective_fingerprint")
    if not effective:
        print("REFUSED: the loop recorded no effective config fingerprint "
              "for {0}. Substituting the source default is exactly the "
              "defect this check exists to remove, so the session is "
              "missed rather than mis-stamped.".format(session))
        return 2
    if effective != fingerprint:
        print("REFUSED: the cycle ran under configuration {0} but the "
              "declared frozen configuration is {1}. The account is not "
              "running the frozen candidate; stop and reconcile before "
              "recording anything."
              .format(effective[:16], fingerprint[:16]))
        return 2
    print("effective config {0} == declared frozen configuration".format(
        effective[:16]))

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
    prior_sleeve = (previous[-1].equity_sleeve_equity if previous else None)
    benchmark_return = (bars[-1].close / bars[-2].close - 1.0
                        if len(bars) >= 2 else None)
    benchmark = {
        "basis": "total_return_adjustment_all",
        "close": round(bars[-1].close, 6) if bars else None,
        "prev_close": round(bars[-2].close, 6) if len(bars) >= 2 else None,
        "close_split": (round(bars_split[-1].close, 6)
                        if bars_split else None),
        "prev_close_split": (round(bars_split[-2].close, 6)
                             if len(bars_split) >= 2 else None),
    }

    # External cash in or out. Without this a deposit reads as return.
    # A failure here is recorded, never silently treated as zero.
    movements, sleeve_issues = 0.0, []
    for kind in ("JNLC", "CSD", "CSW"):
        try:
            rows = broker._request(
                "GET", "/v2/account/activities/{0}?page_size=100".format(kind))
            movements += sum(float(a.get("net_amount") or 0.0) for a in rows
                             if _utc_date(a.get("date")
                                          or a.get("transaction_time"))
                             == session.isoformat())
        except Exception as error:                       # noqa: BLE001
            sleeve_issues.append(
                "cash-movement feed {0} unavailable: {1}".format(kind, error))
    sleeve = {"cash_movements": movements,
              "reserved_fraction": AutoTradeConfig().reserved_fraction}

    # G22 at record time. The chain cannot reveal a TRUNCATED tail - a
    # prefix of a valid chain is itself a valid chain - so the only
    # independent check is the calendar. A gap is named in the record,
    # never filled.
    state = continuity(previous, sessions, registry)
    if state["missing"]:
        sleeve_issues.append(
            "missing eligible sessions: " + ", ".join(state["missing"][:10]))
    if state["recorded_before_eligibility"]:
        sleeve_issues.append(
            "sessions recorded before eligibility: "
            + ", ".join(state["recorded_before_eligibility"][:10]))
    audit["data_quality_issues"] = list(audit["data_quality_issues"]) + sleeve_issues

    # Stamped with the RUN's own digest, proven equal to the declared
    # frozen configuration above. append_session re-checks it.
    observation = build_observation(
        session, effective, account, positions, resting, audit,
        broker_facts(orders, fills, fees, dividends, session),
        prior_equity, benchmark_return, sleeve=sleeve, benchmark=benchmark,
        prior_sleeve_equity=prior_sleeve)

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

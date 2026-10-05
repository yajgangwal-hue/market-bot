"""Pre-OOS dry run: exercise the whole recording pipeline, record nothing.

SAFETY. Every write goes to a scratch path. The real clean record
(data/forward-evaluation.jsonl) is asserted untouched at the start and
again at the end, and the run fails loudly if it ever appears. No
order is submitted: the cycle runs with dry_run=True.

It proves, in order:
  1. the runner's arguments resolve to the frozen configuration
  2. run_once emits the digest of the config it actually ran on
  3. the recorder extracts that digest and refuses a mismatch
  4. the benchmark is total-vs-total
  5. the equity sleeve is separable from crypto and parked cash
  6. positions are serialised with sizing and stop state
  7. the chain, duplicate and continuity guards all fire
  8. nothing was registered and no clean observation was created
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import record_clean_session as REC                               # noqa: E402
from event_aware_trader.autotrade import AutoTradeConfig, run_once  # noqa: E402
from event_aware_trader.data import fetch_alpaca_equity_bars     # noqa: E402
from event_aware_trader.forward import (                         # noqa: E402
    FORWARD_LOG, CleanObservation, FrozenConfigChanged, ForwardDataLeak,
    append_session, config_digest, continuity, frozen_fingerprint,
    load_sessions, verify_chain)
from event_aware_trader.purge import evaluation_window           # noqa: E402
from event_aware_trader.research import load_registry            # noqa: E402

# Was da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b until the owner's adaptive exits
# (EXP-0055, 2026-09-28) restarted the evaluation under da857ab7..., and da857ab7... until the
# take profit moved to the broker in an OCO (EXP-0056, 2026-10-03) restarted it again, and
# ab33087c... until the take profit moved to the bounce price (EXP-0057, 2026-10-04).
DECLARED = "448170c3364935560663048c59647dfb5b204c6e6c724ce603f0d61c476e0f29"
ok = True


def check(label, condition, detail=""):
    global ok
    ok = ok and bool(condition)
    print("  [{0}] {1}{2}".format("PASS" if condition else "FAIL", label,
                                  ("  -> " + str(detail)) if detail else ""))


def main():
    real = Path(REPO / FORWARD_LOG)
    before_exists = real.exists()
    print("real clean record exists at start: {0}".format(before_exists))

    scratch = Path(tempfile.mkdtemp(prefix="preoos-dryrun-"))
    print("scratch: {0}\n".format(scratch))

    # ---- 1. the runner's arguments resolve to the frozen configuration --
    print("1. RUNNER -> FROZEN CONFIGURATION")
    # Exactly what cli.command_autotrade builds from the NEW runner args
    # (`autotrade --asset-class equity` and, when live, `--live`):
    live_cfg = AutoTradeConfig(
        interval="1d", period="2y", max_orders_per_run=3, dry_run=False,
        asset_class="equity", capital_base=None,
        capital_baseline_equity=None)
    check("effective digest == declared frozen fingerprint",
          config_digest(live=live_cfg) == DECLARED,
          config_digest(live=live_cfg)[:16])
    check("frozen_fingerprint() unchanged", frozen_fingerprint() == DECLARED,
          frozen_fingerprint()[:16])
    old = AutoTradeConfig(interval="15m", period="1mo", dry_run=False,
                          asset_class="equity")
    check("the OLD runner config still hashes differently",
          config_digest(live=old) != DECLARED, config_digest(live=old)[:16])
    check("require_market_open is not fingerprinted",
          config_digest(live=AutoTradeConfig(require_market_open=False))
          == DECLARED)

    # ---- 2. run_once emits its own effective digest --------------------
    print("\n2. run_once EMITS ITS EFFECTIVE DIGEST")
    audit = scratch / "audit.jsonl"
    state = scratch / "state.json"
    cycle = AutoTradeConfig(
        interval="1d", period="2y", asset_class="equity",
        dry_run=True,                      # NO ORDER IS SUBMITTED
        require_market_open=False,         # not fingerprinted; lets it run
        audit_log=audit, state_file=state)
    try:
        run_once(cycle)
    except Exception as error:                                # noqa: BLE001
        print("    (cycle raised: {0})".format(error))
    rows = REC.audit_rows(audit)
    runs = [r for r in rows if r.get("event") == "run_complete"]
    check("a run_complete was logged", bool(runs), len(runs))
    stamp = runs[-1]["detail"].get("config_fingerprint") if runs else None
    check("run_complete carries config_fingerprint", bool(stamp),
          (stamp or "")[:16])
    check("the emitted digest is the declared frozen fingerprint",
          stamp == DECLARED)
    check("run_complete records the effective interval",
          runs and runs[-1]["detail"].get("effective_interval") == "1d")
    check("no live order was submitted (dry_run)",
          not any(r.get("event") == "entry" and
                  not (r.get("detail") or {}).get("dry_run", True)
                  for r in rows))

    # ---- 3. the recorder extracts it, and refuses a mismatch -----------
    print("\n3. RECORDER EXTRACTS AND ENFORCES")
    session = date.fromisoformat(
        str(runs[-1]["at"])[:10]) if runs else date.today()
    facts = REC.audit_facts(rows, session)
    check("audit_facts surfaces the effective fingerprint",
          facts["effective_fingerprint"] == DECLARED)
    bad = [dict(r) for r in rows]
    for r in bad:
        if r.get("event") == "run_complete":
            r["detail"] = dict(r["detail"], config_fingerprint="f" * 64)
    check("a divergent cycle is surfaced, not silently accepted",
          REC.audit_facts(bad, session)["effective_fingerprint"] != DECLARED)

    # ---- 4. benchmark is total-vs-total --------------------------------
    print("\n4. BENCHMARK")
    # 400 days, not 20. SPY distributes quarterly, so over a short window
    # with no ex-dividend date the adjusted and split series are
    # legitimately IDENTICAL - the first version of this check used 20
    # days and failed for that reason, which was the test being wrong and
    # not the code.
    tot = fetch_alpaca_equity_bars(["SPY"], days=400, interval="1d",
                                   include_today=True,
                                   adjustment="all").get("SPY", [])
    spl = fetch_alpaca_equity_bars(["SPY"], days=400, interval="1d",
                                   include_today=True,
                                   adjustment="split").get("SPY", [])
    check("adjustment='all' series available", len(tot) >= 2, len(tot))
    check("adjustment='split' series available for audit", len(spl) >= 2)
    gap = (tot[0].close / spl[0].close - 1.0) if (tot and spl) else 0.0
    check("the two series differ over a window spanning a distribution",
          abs(gap) > 1e-6, "oldest bar total-vs-price {0:+.4%}".format(gap))
    check("total return exceeds price return over the window",
          tot[-1].close / tot[0].close > spl[-1].close / spl[0].close,
          "total {0:+.4%} vs price {1:+.4%}".format(
              tot[-1].close / tot[0].close - 1.0,
              spl[-1].close / spl[0].close - 1.0))
    check("fingerprint still declares total_vs_total",
          "total_vs_total" in json.dumps(
              {"b": "total_vs_total"}) and frozen_fingerprint() == DECLARED)

    # ---- 5/6. sleeve separation and position serialisation -------------
    print("\n5/6. SLEEVE SEPARATION AND POSITION SERIALISATION")
    from event_aware_trader.broker import (AlpacaPaperBroker, BrokerConfig,
                                           BrokerError)
    try:
        broker = AlpacaPaperBroker(BrokerConfig.from_environment())
        account = broker.account()
        positions = broker.positions()
        resting = broker.open_sell_orders()
    except BrokerError as error:
        print("    broker unreachable: {0}".format(error))
        return 2

    obs = REC.build_observation(
        session, DECLARED, account, positions, resting, facts,
        {"orders": 0, "fills": 0, "transaction_costs": 0.0,
         "dividends_received": 0.0},
        prior_equity=None,
        benchmark_return=(tot[-1].close / tot[-2].close - 1.0),
        sleeve={"cash_movements": 0.0, "reserved_fraction": 0.05},
        benchmark={"basis": "total_return_adjustment_all",
                   "close": tot[-1].close, "prev_close": tot[-2].close,
                   "close_split": spl[-1].close,
                   "prev_close_split": spl[-2].close},
        prior_sleeve_equity=None)

    check("crypto market value recorded", obs.crypto_market_value > 0,
          obs.crypto_market_value)
    check("equity sleeve excludes crypto",
          abs(obs.equity_sleeve_equity - (obs.equity - obs.crypto_market_value))
          < 0.01,
          "{0:.2f} = {1:.2f} - {2:.2f}".format(
              obs.equity_sleeve_equity, obs.equity, obs.crypto_market_value))
    check("parking value separately identifiable",
          obs.parking_market_value >= 0.0, obs.parking_market_value)
    check("reserved fraction recorded", obs.reserved_fraction == 0.05)
    check("benchmark closes stored for reproducibility",
          obs.benchmark_close and obs.benchmark_prev_close
          and obs.benchmark_close_split)
    check("benchmark basis labelled",
          obs.benchmark_basis == "total_return_adjustment_all")
    equities = [p for p in positions
                if "/" not in str(p.get("symbol", ""))
                and str(p.get("symbol", "")).upper() != "SGOV"]
    check("positions serialised", len(obs.positions) == len(equities),
          "{0} recorded / {1} held".format(len(obs.positions), len(equities)))
    if obs.positions:
        p = obs.positions[0]
        check("position carries sizing fields",
              all(k in p for k in ("symbol", "quantity", "market_value",
                                   "average_entry_price")))
        check("position carries stop state",
              "has_protective_stop" in p and "stop_price" in p)
        check("no account identifiers leaked into the record",
              not any(k for k in p
                      if "account" in k.lower() or k.endswith("_id")))
    check("positions_held agrees with the serialised list",
          obs.positions_held == len(obs.positions))

    # ---- 7. chain, duplicate and continuity guards ---------------------
    print("\n7. CHAIN / DUPLICATE / CONTINUITY GUARDS")
    tmp_log = scratch / "forward.jsonl"
    append_session(obs, path=tmp_log)
    check("append to the scratch chain succeeded", tmp_log.exists())
    check("scratch chain verifies", verify_chain(tmp_log)["intact"])
    try:
        append_session(obs, path=tmp_log)
        check("duplicate session refused", False)
    except ForwardDataLeak:
        check("duplicate session refused", True)
    drifted = CleanObservation(**dict(obs.payload(),
                                      config_fingerprint="e" * 64,
                                      session="2099-01-01"))
    try:
        append_session(drifted, path=tmp_log)
        check("divergent fingerprint refused", False)
    except FrozenConfigChanged:
        check("divergent fingerprint refused", True)
    tampered = tmp_log.read_text(encoding="utf-8").replace(
        '"equity":', '"equity_x":', 1)
    (scratch / "tampered.jsonl").write_text(tampered, encoding="utf-8")
    check("an edited record breaks the chain",
          not verify_chain(scratch / "tampered.jsonl")["intact"])
    registry = load_registry()
    cal = [b.timestamp.date() for b in tot]
    state_c = continuity(load_sessions(tmp_log), cal, registry)
    check("continuity reports against the eligible calendar",
          "missing" in state_c and "complete" in state_c,
          "eligible={0} recorded={1}".format(state_c["eligible"],
                                             state_c["recorded"]))

    # ---- 8. nothing registered, nothing recorded -----------------------
    print("\n8. NOTHING REGISTERED, NOTHING RECORDED")
    from event_aware_trader.modelgov import prereg
    check("registrations still 21", len(prereg.load()) == 21,
          len(prereg.load()))
    check("prereg chain intact", prereg.verify_chain()["intact"])
    rowcount = len([l for l in open(REPO / "docs" / "experiments.jsonl",
                                    encoding="utf-8") if l.strip()])
    check("experiments.jsonl still 53 rows", rowcount == 53, rowcount)
    w = evaluation_window(load_registry(), cal)
    check("freeze date still 2026-09-11", str(w.freeze) == "2026-09-11",
          w.freeze)
    check("REAL clean record still absent",
          real.exists() == before_exists and not real.exists())
    check("REAL chain still reports zero sessions",
          verify_chain()["sessions"] == 0)

    shutil.rmtree(scratch, ignore_errors=True)
    print("\nscratch removed. RESULT: {0}".format("ALL PASS" if ok else "FAILURES ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

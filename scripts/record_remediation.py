"""Append governance/measurement corrections to their OWN ledger.

WHY THIS IS NOT experiments.jsonl. `purge.freeze_date()` takes the
latest `when` among experiment rows whose decision is in
CONFIG_CHANGING = ('accepted', 'reverted'), and `evaluation_window`
adds a 20-session embargo to it. Writing a remediation there as
`accepted` would move the freeze date to today and slide the clean-OOS
start roughly twenty sessions - for a change that alters no economic
rule. These are corrections to the MEASUREMENT machinery, so they get
their own additive log and the experiment record is left exactly as it
was.

Append-only and hash-chained, for the same reason the clean record is:
a correction that can be edited afterwards is not a correction.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LEDGER = REPO / "docs" / "remediations.jsonl"
GENESIS = "0" * 64


def _rows():
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in
            LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]


def _digest(payload, previous):
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((previous + body).encode("utf-8")).hexdigest()


def append(payload):
    rows = _rows()
    if any(r["payload"]["id"] == payload["id"] for r in rows):
        raise SystemExit("refused: {0} already recorded".format(payload["id"]))
    previous = rows[-1]["digest"] if rows else GENESIS
    row = {"payload": payload, "previous": previous,
           "digest": _digest(payload, previous),
           "recorded_at": datetime.now(timezone.utc).isoformat()}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def verify():
    previous = GENESIS
    for i, row in enumerate(_rows()):
        if row.get("previous") != previous:
            return {"intact": False, "broken_at": i}
        if row.get("digest") != _digest(row["payload"], previous):
            return {"intact": False, "broken_at": i}
        previous = row["digest"]
    return {"intact": True, "rows": len(_rows()), "broken_at": None}


REMEDIATIONS = [
    {
        "id": "REM-0001",
        "when": "2026-09-21",
        "title": "Runner passed --interval 15m; fingerprint hashed defaults",
        "what_was_wrong": (
            "frozen_fingerprint() digested AutoTradeConfig() defaults, where "
            "interval='1d', while session-run.ps1 passed --interval 15m "
            "--period 1mo. The live configuration hashed to 569a8da7..., not "
            "the published da22011e.... Both sides of every check read the "
            "same defaults, so the divergence was undetectable."),
        "affects": "governance and measurement; NOT economic behaviour",
        "economic_rules_changed": False,
        "correction": (
            "session-run.ps1 no longer passes --interval or --period to "
            "autotrade, so the CLI defaults (1d, 2y) apply and the effective "
            "configuration hashes to da22011e.... Changing only --interval "
            "would have left ~24 daily bars against a minimum_history of 50 "
            "and silently stopped all trading."),
        "evidence": (
            "scripts/preoos_interval_equivalence.py, 2026-09-21: 230/230 "
            "symbols passed the gate under both configurations, no symbol "
            "had fewer than the rule's 215 daily bars, and the candidate set "
            "was identical (BAC, CVS, KRE, RTX, UNP)."),
        "fingerprint_before": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "fingerprint_after": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "historical_results_usable": True,
        "reports_affected": "none invalidated; the published digest is restored, not changed",
    },
    {
        "id": "REM-0002",
        "when": "2026-09-21",
        "title": "Fingerprint is now an observation of the run (Option C)",
        "what_was_wrong": (
            "The stamp on a clean observation was recomputed from source "
            "defaults by the recorder, so it could never disagree with the "
            "source and could never detect what the trading process did."),
        "affects": "governance",
        "economic_rules_changed": False,
        "correction": (
            "forward.config_digest() is now one definition with parameters; "
            "frozen_fingerprint() is config_digest() with no arguments. "
            "run_once logs config_digest(...) of the objects it actually ran "
            "on into its run_complete event. The recorder stamps the "
            "observation with THAT value and refuses to record when it "
            "differs from the declared frozen fingerprint."),
        "fingerprint_before": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "fingerprint_after": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "historical_results_usable": True,
        "reports_affected": "none; digest byte-identical for defaults",
    },
    {
        "id": "REM-0003",
        "when": "2026-09-21",
        "title": "Benchmark compared total return against SPY price return",
        "what_was_wrong": (
            "record_clean_session fetched SPY with the default "
            "adjustment='split' and compared a PRICE return against the "
            "account's TOTAL return, while the fingerprint declared "
            "basis_post_2016='total_vs_total'. SPY price return understates "
            "its total return by about 1.58 points a year."),
        "affects": "measurement",
        "economic_rules_changed": False,
        "correction": (
            "The benchmark now uses adjustment='all', matching the "
            "declaration already inside the digest, so the fingerprint is "
            "untouched. The split-adjusted pair is stored beside it and both "
            "closes used are recorded, because an adjusted series is "
            "restated by the vendor on every distribution."),
        "fingerprint_before": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "fingerprint_after": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "historical_results_usable": True,
        "reports_affected": "none; the recorder has produced zero observations",
    },
    {
        "id": "REM-0004",
        "when": "2026-09-21",
        "title": "CleanObservation.positions was never populated",
        "what_was_wrong": (
            "The field exists because 'a count cannot be checked against a "
            "sizing rule', but build_observation never passed it, so every "
            "observation would have recorded a position count and no "
            "per-name sizes."),
        "affects": "measurement",
        "economic_rules_changed": False,
        "correction": (
            "A whitelisted projection is now recorded per position: symbol, "
            "quantity, market value, average entry price, unrealised P&L, "
            "whether a protective stop rests, and its stop price. No account "
            "identifier, no order id."),
        "fingerprint_before": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "fingerprint_after": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "historical_results_usable": True,
        "reports_affected": "none; zero observations recorded",
    },
    {
        "id": "REM-0005",
        "when": "2026-09-21",
        "title": "Account-level return conflated the equity book with a live BTC sleeve",
        "what_was_wrong": (
            "strategy_return was account equity over prior account equity, "
            "and the account holds a live BTC sleeve (about 5.6% of equity, "
            "traded every 30 seconds) plus parked cash. The recorded return "
            "was therefore not the frozen candidate's return, and no crypto "
            "position was recorded, so the two could not be separated."),
        "affects": "measurement",
        "economic_rules_changed": False,
        "correction": (
            "crypto_market_value, parking_market_value, reserved_fraction, "
            "cash_movements, equity_sleeve_equity and equity_sleeve_return "
            "are now recorded. equity_sleeve_return is the HEADLINE "
            "candidate metric and is net of external cash movement; "
            "strategy_return keeps its original name and meaning - the "
            "combined account - rather than being silently repurposed."),
        "fingerprint_before": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "fingerprint_after": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "historical_results_usable": True,
        "reports_affected": "none; zero observations recorded",
    },
    {
        "id": "REM-0006",
        "when": "2026-09-21",
        "title": "Continuity was never checked at record time",
        "what_was_wrong": (
            "A truncated prefix of a hash chain is itself a valid chain, so "
            "deleting trailing observations was undetectable. continuity() "
            "existed but was invoked only by phase4_checkpoint.py."),
        "affects": "governance",
        "economic_rules_changed": False,
        "correction": (
            "The recorder now calls continuity() before appending and writes "
            "any missing eligible session, or any session recorded before "
            "eligibility, into data_quality_issues - which is itself "
            "chained."),
        "fingerprint_before": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "fingerprint_after": "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b",
        "historical_results_usable": True,
        "reports_affected": "none",
    },
]


def main():
    if "--verify" in sys.argv:
        print(json.dumps(verify(), indent=1))
        return 0
    for payload in REMEDIATIONS:
        try:
            row = append(payload)
        except SystemExit as error:
            print(error)
            continue
        print("{0}  {1}".format(row["payload"]["id"], row["digest"][:16]))
    print("\nchain: {0}".format(json.dumps(verify())))
    print("NOTE: docs/experiments.jsonl is deliberately untouched. Writing "
          "these as 'accepted' experiments would move freeze_date and slide "
          "the clean-OOS start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

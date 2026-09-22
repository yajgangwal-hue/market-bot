"""Annotate the synthetic rows my tests wrote into the operational log.

On 2026-09-22 while implementing the protective-stop coverage fix I ran
tests whose AutoTradeConfig still pointed at the DEFAULT audit_log, so
34 fake safety events were appended to data/autotrade-audit.jsonl. They
describe a fixture broker, not the account - which is why they mention
BAC as unprotected.

Nothing is deleted. Removing operational evidence to make a log read
cleanly is the exact failure this project audits against, so the rows
stay and this record says what they are. Run once.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "data" / "autotrade-audit.jsonl"

RECORD = {
    "event": "audit_log_contamination_notice",
    "dry_run": False,
    "detail": {
        "note": ("34 rows in this log are SYNTHETIC and must not be read as "
                 "operational history. Unit tests were left pointing at the "
                 "default audit_log path while the protective-stop coverage "
                 "fix was being developed."),
        "synthetic_timestamps": ["2026-09-22T15:34:31",
                                 "2026-09-22T15:35:28"],
        "synthetic_events": ["stop_coverage", "stop_coverage_SHORTFALL",
                             "stop_coverage_UNVERIFIED",
                             "entry_fill_unreadable", "broker_call_failed"],
        "synthetic_row_count": 34,
        "why_BAC_appears": ("the test fixture broker uses the symbol BAC, so "
                            "those rows describe a fake broker and not the "
                            "account"),
        "genuine_rows": ("2026-09-22T15:35:55 stop_coverage x2 (CVS, UNP) "
                         "came from a READ-ONLY check against the real paper "
                         "broker and is accurate"),
        "no_orders_placed": ("the tests used fake brokers; the live check "
                             "called only positions() and open_sell_orders()"),
        "nothing_deleted": "annotated rather than removed",
        "fix": ("tests/test_stop_coverage_race.py now writes to an isolated "
                "temporary audit_log and state_file"),
    },
}


def main():
    rows = [json.loads(line) for line in
            LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(r.get("event") == "audit_log_contamination_notice" for r in rows):
        print("already annotated; nothing appended")
        return 0
    record = dict(RECORD, at=datetime.now(timezone.utc).isoformat())
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    print("annotation appended to {0}".format(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

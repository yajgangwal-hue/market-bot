"""The owner's +0.5% target / -0.2% stop beside the bot, as a table.

Read-only. It reads data/autotrade-audit.jsonl - the same figures the daily
report carries under `tight_exit_comparison` - places no order and calls no
API. Realized is what the owner calls "recognized" gain (closed, banked);
unrealized is "unrecognized" (still open).

    python scripts/tight_exit_compare.py                     # held since 2026-09-28
    python scripts/tight_exit_compare.py --since 2026-09-08
    python scripts/tight_exit_compare.py --as-of 2026-10-02
    python scripts/tight_exit_compare.py --brief             # totals only
"""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.tight_exit_shadow import TRACKING_FROM, compare  # noqa: E402

try:
    from zoneinfo import ZoneInfo
    NEW_YORK = ZoneInfo("America/New_York")
except Exception:   # no timezone database: show UTC and say so
    NEW_YORK = None


def _when(stamp):
    if not stamp:
        return ""
    moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    if NEW_YORK is None:
        return moment.strftime("%m-%d %H:%M UTC")
    return moment.astimezone(NEW_YORK).strftime("%m-%d %H:%M")


def _dollars(value):
    return "{0:+,.2f}".format(value or 0.0)


def _block(title, totals):
    bot, rule = totals["bot"], totals["tight_rule"]
    lines = [
        "{0}: {1} position(s)".format(title, totals["positions"]),
        "  {0:<26}{1:>13}{2:>13}{3:>13}".format(
            "", "realized", "unrealized", "total"),
        "  {0:<26}{1:>13}{2:>13}{3:>13}".format(
            "the bot as it runs", _dollars(bot["realized"]),
            _dollars(bot["unrealized"]), _dollars(bot["total"])),
        "  {0:<26}{1:>13}{2:>13}{3:>13}".format(
            "+0.5% / -0.2% rule", _dollars(rule["realized"]),
            _dollars(rule["unrealized"]), _dollars(rule["total"])),
        "  {0:<52}{1:>13}".format(
            "rule minus bot", _dollars(totals["tight_rule_minus_bot"])),
        "  the rule: {0} sold at the target, {1} stopped out, {2} at neither "
        "level".format(rule["sold_at_target"], rule["stopped_out"],
                       rule["neither_level"]),
    ]
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--audit-log", default=str(REPO / "data" / "autotrade-audit.jsonl"))
    parser.add_argument("--since", default=TRACKING_FROM.isoformat(),
                        help="positions held on or after this date (YYYY-MM-DD)")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD; defaults to today")
    parser.add_argument("--brief", action="store_true", help="totals only")
    args = parser.parse_args(argv)

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    since = date.fromisoformat(args.since)
    payload = compare(Path(args.audit_log), as_of=as_of, since=since)

    out = ["+0.5% target / -0.2% stop vs the bot - tracked on paper, no orders",
           "as of {0}. Realized = recognized (closed, banked). Unrealized = "
           "unrecognized (still open).".format(as_of.isoformat()), ""]
    if "held_since" in payload:
        out += _block("Held since {0}".format(since.isoformat()), payload["held_since"])
        out.append("")
    else:
        out += ["Held since {0}: that date has not arrived yet.".format(
            since.isoformat()), ""]
    out += _block("Every position since the first logged check",
                  payload["every_position"])

    if not args.brief:
        zone = "UTC" if NEW_YORK is None else "ET"
        out += ["", "Position by position (times {0}):".format(zone)]
        start = since.isoformat()
        for row in payload["positions"]:
            bot, rule = row["bot"], row["tight_rule"]
            if bot["status"] != "open" and (bot["closed"] or "")[:10] < start:
                continue
            bot_text = "{0} {1:+.2f}% {2}".format(
                bot["status"] if bot["status"] == "open"
                else "{0} {1}".format(bot["status"], _when(bot["closed"])),
                bot["gain_pct"], _dollars(bot["gain"]))
            rule_text = "{0}{1} {2:+.2f}% {3}".format(
                rule["status"],
                " " + _when(rule["sold"]) if rule["sold"] else "",
                rule["gain_pct"], _dollars(rule["gain"]))
            out.append("  {0:<5} opened {1}".format(row["symbol"], _when(row["opened"])))
            out.append("        bot : " + bot_text)
            out.append("        rule: " + rule_text)
        skipped = payload["not_compared"]
        if skipped:
            out += ["", "Not compared ({0}) - nothing to judge them on:".format(len(skipped))]
            for item in skipped:
                out.append("  {0:<5} {1}: {2}".format(
                    item["symbol"], _when(item["opened"] or item["closed"]),
                    item["reason"]))
        out += ["", "How it is measured:"] + ["  - " + line for line in payload["how_it_is_measured"]]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

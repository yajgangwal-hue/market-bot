"""REM-0010: re-date open positions stamped with the session BEFORE their entry.

From about 2026-09-22 until the fix of 2026-10-04, autotrade stamped each new
position's `opened_at_ts` with the cycle's last bar - which, on daily bars,
is the previous session's - so the 20-session holding cap would fire one
session early (D+19, against SPEC-0001 C-16's D+20). The code is fixed
(`autotrade._entry_stamp`); this repairs the positions already open.

For each remembered position, the most recent `entry` event in the bot's own
audit log for that symbol is the moment it was opened. When the stamp's date
is EARLIER than that event's date, the stamp is replaced by the event's time.
Nothing else in the state changes. A stamp that already matches is left
alone, so running this twice changes nothing the second time.

Dry run by default: prints what it would change. --apply backs up the state
file, writes it atomically, and appends a `state_repair` event to the audit
log. No broker call; local files only.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.autotrade import _parse_stamp  # noqa: E402


def latest_entries(audit_log: Path):
    out = {}
    for line in audit_log.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("event") != "entry" or row.get("dry_run"):
            continue
        symbol = (row.get("detail") or {}).get("symbol")
        if symbol and str(row.get("at", "")) > out.get(symbol, ""):
            out[symbol] = str(row["at"])
    return out


def repairs(state: dict, entries: dict):
    out = []
    for symbol, remembered in sorted((state.get("stops") or {}).items()):
        stamp, entered = remembered.get("opened_at_ts"), entries.get(symbol)
        if not stamp or not entered:
            continue
        if _parse_stamp(stamp).date() < _parse_stamp(entered).date():
            fixed = _parse_stamp(entered).replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
            out.append({"symbol": symbol, "from": stamp, "to": fixed, "entry_event_at": entered})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=str(REPO / "data" / "autotrade-state.json"))
    parser.add_argument("--audit", default=str(REPO / "data" / "autotrade-audit.jsonl"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    state_path, audit_path = Path(args.state), Path(args.audit)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    todo = repairs(state, latest_entries(audit_path))
    for r in todo:
        print("{symbol:6} {from} -> {to}   (entry event {entry_event_at})".format(**r))
    if not todo:
        print("nothing to repair")
        return 0
    if not args.apply:
        print("dry run: pass --apply to write")
        return 0
    backup = state_path.with_name(state_path.stem + ".backup-before-REM-0010.json")
    shutil.copy2(state_path, backup)
    for r in todo:
        state["stops"][r["symbol"]]["opened_at_ts"] = r["to"]
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, state_path)
    event = {"at": datetime.now(timezone.utc).isoformat(), "event": "state_repair",
             "dry_run": False, "detail": {"remediation": "REM-0010", "field": "opened_at_ts",
                                          "repairs": todo, "backup": backup.name}}
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    print("repaired {0} position(s); backup {1}".format(len(todo), backup))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

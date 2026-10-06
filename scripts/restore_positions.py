"""REM-0011: restore the bot's records of positions it dropped when it was
pointed at a different account.

WHAT HAPPENED. On 2026-10-05 the equity bot started with a new Alpaca key that
belongs to a different, empty paper account ($100,000.00, no positions, no
fills). At 06:30 PT it saw none of its seven open positions (CVS, IWM, MDY,
SCHD, SCHW, UNP, VZ), logged `external_exit_unrecoverable` for each ("the
last 0 fills"), and deleted their records. The positions themselves are
still open in the original account, under their resting GTC stops.

WHY THE RECORDS MATTER. A position the bot has no record of is rebuilt on
the next cycle: a stop from TODAY's ATR and an entry date of TODAY. That
restarts the 20-session limit and moves the stop. Restored records keep:
- the original stop;
- the entry date (with REM-0010's correction);
- the entry ATR;
- the features the learner needs.

WHAT IT DOES.
1. Records opened while the bot ran on the other account (from
   OTHER_ACCOUNT_FROM: JNJ, SCHD and XLF on 2026-10-05) are moved to
   data/autotrade-state.other-account-2026-10-05.json. Those positions live
   in the other account, and SCHD's would otherwise govern the original
   account's SCHD.
2. For each symbol in the backup that the state no longer holds (or holds
   only as a rebuilt record), the backup's `stops` and `open_features`
   entries are copied back, with the `opened_at_ts` corrections REM-0010's
   `state_repair` event recorded.
3. The weekly loss guard's anchor, set at 06:30 from the other account's
   $100,000, is set to the original account's last recorded equity before
   the week: $97,310.39 (run_complete, 2026-10-02 19:45 UTC).
Nothing else changes; session-scoped fields reset at the next session. The
take profit is refreshed to the session's bounce price by the next cycle.

RUN IT ONLY AFTER THE BOT IS BACK ON THE ORIGINAL ACCOUNT. On the other
account the next cycle would see the positions missing again and drop them
again. Harmless, but pointless. The last cycle's account equity is printed
to help check: about $97,000 is the original account, $100,000 the new one.

Dry run by default. --apply backs up the state, writes it atomically and
appends a `state_repair` event. Local files only; no broker call.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
BACKUP = DATA / "autotrade-state.backup-before-REM-0010.json"
OTHER_ACCOUNT_FROM = "2026-10-05T13:30:00+00:00"
ASIDE = DATA / "autotrade-state.other-account-2026-10-05.json"
WEEK = "2026-W41"
WEEK_OPENING_EQUITY = 97310.39


def rem0010_stamps(audit_path):
    """symbol -> corrected opened_at_ts, from REM-0010's own state_repair event."""
    out = {}
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        detail = row.get("detail") or {}
        if row.get("event") == "state_repair" and detail.get("remediation") == "REM-0010":
            for repair in detail.get("repairs") or []:
                out[repair["symbol"]] = repair["to"]
    return out


def last_cycle(audit_path):
    """The most recent equity run's account equity and positions seen, if logged."""
    found = None
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("event") == "run_complete":
            detail = row.get("detail") or {}
            snapshot = detail.get("portfolio_snapshot_at_cycle_start") or {}
            found = (row.get("at"), detail.get("account_equity_at_cycle_start"),
                     snapshot.get("positions_seen"))
    return found


def other_account_records(state):
    """Records opened on the other account: opened_at_ts at or after the switch."""
    from_ = datetime.fromisoformat(OTHER_ACCOUNT_FROM)
    out = []
    for symbol, record in sorted((state.get("stops") or {}).items()):
        stamp = record.get("opened_at_ts")
        if stamp and datetime.fromisoformat(stamp).astimezone(timezone.utc) >= from_:
            out.append(symbol)
    return out


def plan(state, backup, stamps):
    """Records to put back: the backup's, for symbols the state lost or rebuilt."""
    todo = []
    for symbol, record in sorted((backup.get("stops") or {}).items()):
        current = (state.get("stops") or {}).get(symbol)
        rebuilt = current is not None and "atr_at_entry" not in current
        if current is not None and not rebuilt:
            continue
        restored = dict(record)
        if symbol in stamps:
            restored["opened_at_ts"] = stamps[symbol]
        todo.append({"symbol": symbol, "stops": restored,
                     "open_features": (backup.get("open_features") or {}).get(symbol),
                     "replaces": "rebuilt record" if rebuilt else "nothing (record was deleted)"})
    return todo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=str(DATA / "autotrade-state.json"))
    parser.add_argument("--audit", default=str(DATA / "autotrade-audit.jsonl"))
    parser.add_argument("--backup", default=str(BACKUP))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    state_path, audit_path = Path(args.state), Path(args.audit)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    backup = json.loads(Path(args.backup).read_text(encoding="utf-8"))
    aside = other_account_records(state)
    working = json.loads(json.dumps(state))
    for symbol in aside:
        working["stops"].pop(symbol, None)
        (working.get("open_features") or {}).pop(symbol, None)
    todo = plan(working, backup, rem0010_stamps(audit_path))
    cycle = last_cycle(audit_path)
    if cycle:
        print("last equity cycle {0}: account equity ${1:,.2f}, positions seen {2}".format(
            cycle[0][:19], float(cycle[1] or 0), cycle[2]))
    for symbol in aside:
        record = state["stops"][symbol]
        print("{0:5} set aside: opened {1} on the other account".format(symbol, record["opened_at_ts"]))
    for item in todo:
        s = item["stops"]
        print("{0:5} stop {1:10.4f}  entry dated {2}  take profit {3}  replaces {4}".format(
            item["symbol"], float(s["initial"]), s["opened_at_ts"], s.get("take_profit"),
            item["replaces"]))
    print("weekly guard anchor: {0} {1} -> {2} {3}".format(
        state.get("week"), state.get("week_opening_equity"), WEEK, WEEK_OPENING_EQUITY))
    if not todo and not aside:
        print("nothing to restore")
        return 0
    if not args.apply:
        print("dry run: pass --apply to write")
        return 0
    copy = state_path.with_name(state_path.stem + ".backup-before-REM-0011.json")
    shutil.copy2(state_path, copy)
    if aside:
        ASIDE.write_text(json.dumps({
            "note": "records of positions opened on the other paper account on 2026-10-05",
            "stops": {s: state["stops"][s] for s in aside},
            "open_features": {s: (state.get("open_features") or {}).get(s) for s in aside}},
            indent=2, sort_keys=True), encoding="utf-8")
    state = working
    state["week"], state["week_opening_equity"] = WEEK, WEEK_OPENING_EQUITY
    for item in todo:
        state.setdefault("stops", {})[item["symbol"]] = item["stops"]
        if item["open_features"] is not None:
            state.setdefault("open_features", {})[item["symbol"]] = item["open_features"]
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, state_path)
    event = {"at": datetime.now(timezone.utc).isoformat(), "event": "state_repair",
             "dry_run": False, "detail": {
                 "remediation": "REM-0011", "fields": ["stops", "open_features"],
                 "restored": [i["symbol"] for i in todo], "source": Path(args.backup).name,
                 "set_aside": aside, "set_aside_to": ASIDE.name if aside else None,
                 "week_opening_equity": WEEK_OPENING_EQUITY, "backup": copy.name,
                 "why": "records dropped on 2026-10-05 while the bot ran on a different account"}}
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    print("restored {0} position record(s); state backed up to {1}".format(len(todo), copy.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())

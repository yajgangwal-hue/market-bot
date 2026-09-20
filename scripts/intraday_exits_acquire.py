"""PHASE 4 acquisition - 5-minute bars for the 459 historical rule exits.

Targeted, not bulk: only the sessions the measurement needs. Each
symbol-session is written to the raw store the moment it arrives, so a
killed process loses one request rather than the whole run.

Read-only market data. No order, no account call, no trading.
Credentials are read by NAME and never printed or persisted.
"""

import glob
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def _scratch_with_deep():
    cands = sorted(glob.glob(os.path.join(
        os.environ.get("TEMP", "/tmp"), "claude", "C--market-bot", "*",
        "scratchpad")))
    hit = [c for c in cands
           if len(glob.glob(os.path.join(c, "deep", "*.csv"))) >= 200]
    if not hit:
        raise SystemExit("REFUSED: decade universe not found.")
    return Path(hit[0])


SCRATCH = _scratch_with_deep()
RAW = SCRATCH / "raw" / "intraday-exits"
CACHE = REPO / "docs" / "phase5" / "h0011-cache.json"
DATA_HOST = "https://data.alpaca.markets"
RULE_REASONS = ("reverted", "time_exit")


def headers():
    k = os.environ.get("APCA_API_KEY_ID")
    s = os.environ.get("APCA_API_SECRET_KEY")
    if not k or not s:
        raise SystemExit("REFUSED: credentials absent.")
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s,
            "User-Agent": "market-bot-research/1.0"}


def fetch(symbol, start, end):
    q = ("?symbols={0}&timeframe=5Min&start={1}&end={2}&limit=10000"
         "&adjustment=split".format(urllib.parse.quote(symbol), start, end))
    req = urllib.request.Request(DATA_HOST + "/v2/stocks/bars" + q,
                                 headers=headers())
    try:
        with urllib.request.urlopen(req, timeout=60,
                                    context=ssl.create_default_context()) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, "HTTP {0}: {1}".format(
            e.code, e.read().decode("utf-8", "replace")[:160])
    except Exception as e:                                   # noqa: BLE001
        return None, "{0}: {1}".format(type(e).__name__, e)[:160]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    store = json.loads(CACHE.read_text(encoding="utf-8"))
    exits = [t for t in store["BASELINE"]["trades"]
             if t["reason"] in RULE_REASONS]
    print("PHASE 4 ACQUISITION")
    print("  rule exits in the frozen baseline: {0}".format(len(exits)))
    by = {}
    for t in exits:
        by[t["reason"]] = by.get(t["reason"], 0) + 1
    print("  by reason: {0}".format(by))

    # The trigger session is the EXIT session. Fetch that day only; the
    # measurement compares intraday prices within it against its close.
    want = sorted({(t["symbol"], t["exit"]) for t in exits})
    print("  unique symbol-sessions to acquire: {0}".format(len(want)))
    done = {p.stem for p in RAW.glob("*.json")}
    todo = [(s, d) for s, d in want if "{0}_{1}".format(s, d) not in done]
    print("  already cached: {0} | to fetch: {1}\n".format(
        len(want) - len(todo), len(todo)), flush=True)

    ok = fail = 0
    for i, (sym, day) in enumerate(todo, 1):
        d0 = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        payload, err = fetch(sym, day, (d0 + timedelta(days=1)).date().isoformat())
        if payload is None:
            fail += 1
            print("  {0}/{1} {2} {3} FAILED {4}".format(i, len(todo), sym, day, err),
                  flush=True)
        else:
            (RAW / "{0}_{1}.json".format(sym, day)).write_text(
                json.dumps(payload), encoding="utf-8")
            ok += 1
        if i % 50 == 0:
            print("  {0}/{1} ok={2} fail={3}".format(i, len(todo), ok, fail),
                  flush=True)
        time.sleep(0.32)
    print("\n  acquired {0} | failed {1} | raw store {2}".format(ok, fail, RAW))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""H-0017 - targeted acquisition for the 221 reverted exits. Read-only.

Two pulls per exit, both bounded:

  TRADES over the next regular session - the window in which an H-0011
  limit (configuration A, patience 1) would have been working. Used for
  the fill BOUND only.

  NBBO in a narrow window around the trigger close - 15:55 to 16:00 ET
  of the exit session, the minutes in which the limit level was set.
  Used for spread state only.

Condition codes are retained verbatim. Nothing is filtered at
acquisition; exclusions happen in analysis and are counted there.

Resume-safe: one JSON per exit, skipped if present.
"""

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


# Decade price data only through the research dataset gate: verified
# before use, fail-closed, no scratchpad fallback. Intraday stores are
# UNPRESERVED and scratchpad-only; they are located by the one sanctioned
# lookup, keyed on the store itself. Both replaced a glob keyed on the
# scratchpad's decade files on 2026-09-24
# (docs/2026-09-24-governed-research-dataset-migration.md).
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))
from research_gate import unpreserved_intraday_store           # noqa: E402
RAW = unpreserved_intraday_store("raw/h0017-micro")
TARGETS = REPO / "docs" / "phase5" / "h0017-targets.json"
VENDOR = {"BRK-B": "BRK.B"}
HOST = "https://data.alpaca.markets"


def headers():
    k = os.environ.get("APCA_API_KEY_ID")
    s = os.environ.get("APCA_API_SECRET_KEY")
    if not k or not s:
        raise SystemExit("REFUSED: credentials absent.")
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s,
            "User-Agent": "market-bot-research/1.0"}


def pull(path, sym, start, end, cap_pages=14):
    v = VENDOR.get(sym, sym)
    out, tok, pages = [], None, 0
    while True:
        q = {"symbols": v, "start": start, "end": end, "limit": 10000}
        if tok:
            q["page_token"] = tok
        url = HOST + path + "?" + urllib.parse.urlencode(q)
        for attempt in range(4):
            try:
                r = urllib.request.Request(url, headers=headers())
                with urllib.request.urlopen(
                        r, timeout=120,
                        context=ssl.create_default_context()) as z:
                    p = json.loads(z.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                if e.code in (400, 403):
                    return out, "HTTP {0}".format(e.code), pages
                if attempt == 3:
                    return out, "HTTP {0}".format(e.code), pages
                time.sleep(2 * (attempt + 1))
            except Exception:                                    # noqa: BLE001
                if attempt == 3:
                    return out, "network", pages
                time.sleep(2 * (attempt + 1))
        body = p.get("trades") or p.get("quotes") or {}
        out += body.get(v) or []
        pages += 1
        tok = p.get("next_page_token")
        if not tok or pages >= cap_pages:
            return out, ("capped" if tok else None), pages
        time.sleep(0.12)


def et_to_utc(day, hh, mm):
    """Explicit post-2007 US Eastern rule; tzdata is absent here."""
    d = datetime.fromisoformat(day)

    def nth_sun(y, m, n):
        x = datetime(y, m, 1)
        x += timedelta(days=(6 - x.weekday()) % 7)
        return x + timedelta(weeks=n - 1)
    s = nth_sun(d.year, 3, 2) + timedelta(hours=2)
    e = nth_sun(d.year, 11, 1) + timedelta(hours=2)
    off = 4 if s <= d < e else 5
    return (d + timedelta(hours=hh + off, minutes=mm)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    tgt = json.loads(TARGETS.read_text(encoding="utf-8"))
    print("targets {0} | raw store {1}".format(len(tgt), RAW), flush=True)
    done = {p.stem for p in RAW.glob("*.json")}
    todo = [t for t in tgt
            if "{0}_{1}".format(t["symbol"], t["exit"]) not in done]
    print("cached {0} | to fetch {1}\n".format(len(tgt) - len(todo), len(todo)),
          flush=True)
    okc = fail = 0
    for i, t in enumerate(todo, 1):
        sym, ex, nx = t["symbol"], t["exit"], t["next_session"]
        # trades across the next regular session (the working window)
        tr, terr, tp = pull("/v2/stocks/trades", sym,
                            et_to_utc(nx, 9, 30), et_to_utc(nx, 16, 0))
        # NBBO in the final five minutes of the trigger session
        qt, qerr, qp = pull("/v2/stocks/quotes", sym,
                            et_to_utc(ex, 15, 55), et_to_utc(ex, 16, 0),
                            cap_pages=6)
        rec = {"target": t, "trades": tr, "quotes": qt,
               "trade_pages": tp, "quote_pages": qp,
               "trade_err": terr, "quote_err": qerr,
               "trade_window": [et_to_utc(nx, 9, 30), et_to_utc(nx, 16, 0)],
               "quote_window": [et_to_utc(ex, 15, 55), et_to_utc(ex, 16, 0)]}
        (RAW / "{0}_{1}.json".format(sym, ex)).write_text(
            json.dumps(rec), encoding="utf-8")
        if terr or qerr:
            fail += 1
        else:
            okc += 1
        if i % 25 == 0:
            print("  {0}/{1} clean={2} flagged={3}".format(
                i, len(todo), okc, fail), flush=True)
        time.sleep(0.12)
    print("\nacquired {0} clean, {1} flagged | files {2}".format(
        okc, fail, len(list(RAW.glob('*.json')))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

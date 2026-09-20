"""PHASE 1 - intraday data feasibility probe. Read-only, no trading.

Measures what historical intraday coverage ACTUALLY exists for the
fixed research universe, rather than trusting a vendor claim. Nothing
here is a strategy, nothing is registered, and no order is placed.

Raw vendor payloads land in the scratchpad under raw/intraday-probe/
so raw data stays separate from derived research data. Only the
derived summary is written to docs/phase5/.

Credential hygiene: keys are read from the environment by NAME only,
used for the Authorization header, and never printed, logged or
written to any artifact.
"""

import csv
import glob
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
def _scratch_with_deep():
    """Several sessions have scratchpads; only one holds the decade set.

    glob order is not guaranteed, and taking [0] silently picked an empty
    sibling on the first run - 0 universe files, 0 probes, a clean-looking
    report about nothing. Select on the data actually being there.
    """
    cands = sorted(glob.glob(os.path.join(
        os.environ.get("TEMP", "/tmp"), "claude", "C--market-bot", "*",
        "scratchpad")))
    withdeep = [c for c in cands
                if len(glob.glob(os.path.join(c, "deep", "*.csv"))) >= 200]
    if not withdeep:
        raise SystemExit(
            "REFUSED: no scratchpad holds the decade universe "
            "(looked in {0} candidate(s)).".format(len(cands)))
    return Path(withdeep[0])


SCRATCH = _scratch_with_deep()
DEEP = SCRATCH / "deep"
RAW = SCRATCH / "raw" / "intraday-probe"
OUT = REPO / "docs" / "phase5" / "intraday-probe.json"

DATA_HOST = "https://data.alpaca.markets"
INTERVAL = "5Min"
# Early / middle / recent, one week each, deliberately small.
WINDOWS = [("early", "2016-01-04", "2016-01-09"),
           ("middle", "2021-06-07", "2021-06-12"),
           ("recent", "2026-09-01", "2026-09-05")]


def headers():
    k = os.environ.get("APCA_API_KEY_ID")
    s = os.environ.get("APCA_API_SECRET_KEY")
    if not k or not s:
        raise SystemExit("REFUSED: credentials absent from the environment.")
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s,
            "User-Agent": "market-bot-research/1.0"}


def fetch(symbol, start, end, adjustment="split", feed=None):
    """One page. Returns (payload, http_status, error_text)."""
    q = ("?symbols={0}&timeframe={1}&start={2}&end={3}&limit=10000"
         "&adjustment={4}".format(urllib.parse.quote(symbol), INTERVAL,
                                  start, end, adjustment))
    if feed:
        q += "&feed=" + feed
    url = DATA_HOST + "/v2/stocks/bars" + q
    req = urllib.request.Request(url, headers=headers())
    try:
        with urllib.request.urlopen(req, timeout=60,
                                    context=ssl.create_default_context()) as r:
            return json.loads(r.read().decode("utf-8")), r.status, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        return None, e.code, body
    except Exception as e:                                   # noqa: BLE001
        return None, None, "{0}: {1}".format(type(e).__name__, e)[:300]


def daily_for(symbol):
    p = DEEP / (symbol + ".csv")
    if not p.exists():
        return {}
    out = {}
    for r in csv.DictReader(open(p)):
        out[r["timestamp"][:10]] = {k: float(r[k]) for k in
                                    ("open", "high", "low", "close", "volume")}
    return out


def pick_symbols():
    """High- and low-ADV names FROM THE EXISTING UNIVERSE. No new symbols."""
    adv = {}
    for p in sorted(DEEP.glob("*.csv")):
        rows = list(csv.DictReader(open(p)))[-250:]
        if len(rows) < 100:
            continue
        try:
            adv[p.stem] = sum(float(r["close"]) * float(r["volume"])
                              for r in rows) / len(rows)
        except Exception:                                    # noqa: BLE001
            continue
    ranked = sorted(adv.items(), key=lambda x: -x[1])
    return ([s for s, _v in ranked[:3]], [s for s, _v in ranked[-3:]], adv)


def analyse(payload, symbol, daily):
    bars = (payload or {}).get("bars", {}).get(symbol) or []
    if not bars:
        return {"bars": 0}
    ts = [b["t"] for b in bars]
    parsed = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in ts]
    deltas = Counter((parsed[i] - parsed[i - 1]).total_seconds()
                     for i in range(1, len(parsed)))
    sessions = Counter(p.astimezone(timezone.utc).date().isoformat()
                       for p in parsed)
    # reconcile each covered session against the daily bar already on disk
    recon = []
    for d, n in sorted(sessions.items()):
        day = [b for b, p in zip(bars, parsed)
               if p.astimezone(timezone.utc).date().isoformat() == d]
        dd = daily.get(d)
        if not dd:
            recon.append({"session": d, "intraday_bars": n, "daily": "ABSENT"})
            continue
        ih = max(b["h"] for b in day)
        il = min(b["l"] for b in day)
        io = day[0]["o"]
        ic = day[-1]["c"]
        iv = sum(b["v"] for b in day)
        recon.append({
            "session": d, "intraday_bars": n,
            "high_diff_pct": (ih - dd["high"]) / dd["high"],
            "low_diff_pct": (il - dd["low"]) / dd["low"],
            "open_diff_pct": (io - dd["open"]) / dd["open"],
            "close_diff_pct": (ic - dd["close"]) / dd["close"],
            "volume_ratio": iv / dd["volume"] if dd["volume"] else None})
    return {
        "bars": len(bars),
        "first_ts": ts[0], "last_ts": ts[-1],
        "tz_suffix": ts[0][-1] if ts[0][-1] in "Zz" else ts[0][-6:],
        "modal_gap_seconds": deltas.most_common(1)[0][0] if deltas else None,
        "gap_histogram": dict(deltas.most_common(5)),
        "duplicate_timestamps": len(ts) - len(set(ts)),
        "sessions_covered": len(sessions),
        "bars_per_session": dict(sessions),
        "reconciliation": recon,
        "next_page_token": (payload or {}).get("next_page_token"),
    }


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    hi, lo, adv = pick_symbols()
    probe_syms = hi + lo
    print("PHASE 1 PROBE - fixed universe only, no new symbols")
    print("  deep universe files: {0}".format(len(list(DEEP.glob('*.csv')))))
    print("  high-ADV probes: {0}".format(", ".join(
        "{0} (${1:,.0f}M)".format(s, adv[s] / 1e6) for s in hi)))
    print("  low-ADV probes:  {0}".format(", ".join(
        "{0} (${1:,.0f}M)".format(s, adv[s] / 1e6) for s in lo)))
    print("  interval {0} | adjustment=split (matches the daily set)\n".format(
        INTERVAL), flush=True)

    results = {"interval": INTERVAL, "host": DATA_HOST,
               "probed_at": datetime.now(timezone.utc).isoformat(),
               "universe_files": len(list(DEEP.glob("*.csv"))),
               "high_adv": hi, "low_adv": lo, "windows": {}}

    for label, start, end in WINDOWS:
        results["windows"][label] = {}
        print("=== {0} window {1} -> {2} ===".format(label, start, end),
              flush=True)
        for sym in probe_syms:
            payload, status, err = fetch(sym, start, end)
            time.sleep(0.35)
            if payload is None:
                print("  {0:<6} HTTP {1}  {2}".format(sym, status, err))
                results["windows"][label][sym] = {"http_status": status,
                                                  "error": err}
                continue
            (RAW / "{0}-{1}.json".format(label, sym)).write_text(
                json.dumps(payload), encoding="utf-8")
            a = analyse(payload, sym, daily_for(sym))
            a["http_status"] = status
            results["windows"][label][sym] = a
            if not a["bars"]:
                print("  {0:<6} 0 bars returned".format(sym))
                continue
            r = a["reconciliation"]
            worst = max((abs(x.get("high_diff_pct") or 0) for x in r),
                        default=0)
            print("  {0:<6} {1:>5} bars | {2} sessions | gap {3}s | dup {4} | "
                  "worst H diff {5:.4%}".format(
                      sym, a["bars"], a["sessions_covered"],
                      a["modal_gap_seconds"], a["duplicate_timestamps"],
                      worst))
        print(flush=True)

    OUT.write_text(json.dumps(results, indent=1, sort_keys=True, default=str),
                   encoding="utf-8")
    print("raw payloads -> {0}".format(RAW))
    print("derived summary -> {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

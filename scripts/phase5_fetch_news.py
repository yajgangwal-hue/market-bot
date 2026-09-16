"""Phase 5. Build a point-in-time news archive for the anatomised trades.

Fetches only what a decision could have used: for every trade in the
anatomy file, the window from N days before the entry up to the DECISION
TIMESTAMP - 15:45 Eastern on the entry session, converted to UTC with the
daylight-saving rule that applied in that year. Anything published after
that instant is not requested at all, so it cannot leak in later by
accident.

Every row keeps its provenance: vendor, item id, publication time,
retrieval time, tagged symbols, tier, and whether the vendor revised it
after publishing. Rows without a parseable publication time are stored
marked unusable rather than dropped, because the count of what had to be
discarded is itself evidence about the data source.

  python scripts/phase5_fetch_news.py deep --lookback 3
  python scripts/phase5_fetch_news.py deep --candidates   # every candidate
"""

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.phase5.asof import (                   # noqa: E402
    ARCHIVE, decision_timestamp, from_alpaca)

ENDPOINT = "https://data.alpaca.markets/v1beta1/news"
PAGE = 50

#: Concurrent windows in flight. Four is chosen against the data API's rate
#: limit, not against the machine: the work is pure latency, and a 429
#: storm costs more time than extra threads save.
WORKERS = 4


def request(params, key, secret, attempts=4):
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as handle:
                return json.load(handle)
        except urllib.error.HTTPError as error:
            if error.code == 429 and attempt < attempts - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt < attempts - 1:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise
    return {}


def fetch_window(symbol, start, end, key, secret, cap=200):
    """Every item for one symbol between two UTC instants."""
    out, token, fetched = [], None, 0
    while True:
        params = {"symbols": symbol, "limit": PAGE,
                  "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "sort": "asc"}
        if token:
            params["page_token"] = token
        data = request(params, key, secret)
        rows = data.get("news") or []
        out.extend(rows)
        fetched += len(rows)
        token = data.get("next_page_token")
        if not token or fetched >= cap:
            break
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "deep"
    lookback = 3
    if "--lookback" in sys.argv:
        lookback = int(sys.argv[sys.argv.index("--lookback") + 1])

    key = os.environ.get("APCA_API_KEY_ID", "").strip()
    secret = os.environ.get("APCA_API_SECRET_KEY", "").strip()
    if not key or not secret:
        print("APCA_API_KEY_ID / APCA_API_SECRET_KEY are not set.")
        return 1

    # Two sources of windows. The anatomy file covers the trades actually
    # taken, which is enough to ask whether news SEPARATES good from bad.
    # The candidate file covers every entry the rule could have acted on,
    # which is what a portfolio re-run needs: rejecting one entry frees
    # capital for a candidate the baseline never bought, and that
    # candidate's news has to be in the archive too.
    source = "candidates" if "--candidates" in sys.argv else "anatomy"
    path = REPO / "data" / "phase5" / "{0}-{1}.jsonl".format(source, which)
    if not path.exists():
        print("{0} not found; run the {1} script first".format(path, source))
        return 1
    rows = [json.loads(l) for l in
            path.read_text(encoding="utf-8").splitlines() if l.strip()]
    trades = [{"symbol": r["symbol"],
               "entry_date": r.get("entry_date") or r["date"]} for r in rows]

    out_path = REPO / "data" / "phase5" / "news-archive-{0}.jsonl".format(which)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(json.loads(line)["item_id"])

    # Window-level resume. Without it a re-run re-requests thousands of
    # windows to discover it already has their items, and an interrupted
    # fetch is effectively unresumable.
    done_path = REPO / "data" / "phase5" / "news-windows-{0}.txt".format(which)
    done = set()
    if done_path.exists():
        done = {l for l in done_path.read_text(encoding="utf-8").splitlines() if l}

    windows = sorted({(t["symbol"], t["entry_date"]) for t in trades})
    windows = [w for w in windows if "{0} {1}".format(*w) not in done]
    print("{0} rows, {1} windows to fetch, {2} already done, {3} items archived"
          .format(len(trades), len(windows), len(done), len(seen)))
    # A small thread pool, not a large one. Each window is one HTTP request
    # and the work is entirely latency; four in flight turns a seven-hour
    # sequential crawl into about half an hour. It is kept small on purpose:
    # the data API rate-limits, and a 429 storm would cost more time than
    # the extra threads save. Writes go through one lock so the archive and
    # the resume marker cannot interleave mid-line.
    written = skipped = finished = 0
    lock = threading.Lock()
    counter = {"done": 0}

    def work(entry_pair, handle, marker):
        nonlocal written, skipped
        symbol, day = entry_pair
        entry = datetime.fromisoformat(day).date()
        end = decision_timestamp(entry)
        start = end - timedelta(days=lookback)
        try:
            rows = fetch_window(symbol, start, end, key, secret)
        except Exception as error:
            with lock:
                skipped += 1
                print("  {0} {1}: FAILED {2}".format(symbol, day, error))
            return
        retrieved = datetime.now(timezone.utc).isoformat()
        fresh = []
        for raw in rows:
            item = from_alpaca(raw, retrieved_at=retrieved)
            # The API bound is inclusive at the second; enforce the strict
            # inequality the engine promises.
            published = item.published()
            if published is not None and published >= end:
                continue
            fresh.append(item)
        with lock:
            for item in fresh:
                if item.item_id in seen:
                    continue
                seen.add(item.item_id)
                handle.write(json.dumps(item.__dict__, sort_keys=True) + "\n")
                written += 1
            # Marked only after the window's items are written, so an
            # interrupted run re-fetches the window it was mid-way through
            # rather than recording it as complete.
            marker.write("{0} {1}\n".format(symbol, day))
            counter["done"] += 1
            if counter["done"] % 100 == 0:
                handle.flush()
                marker.flush()
                print("  {0}/{1} windows, {2} items".format(
                    counter["done"], len(windows), written), flush=True)

    with out_path.open("a", encoding="utf-8") as handle, \
            done_path.open("a", encoding="utf-8") as marker:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(work, w, handle, marker) for w in windows]
            for future in as_completed(futures):
                future.result()
                finished += 1
    print("done: {0} windows, {1} new items, {2} failed windows".format(
        finished, written, skipped))
    print("archive: {0}".format(out_path.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

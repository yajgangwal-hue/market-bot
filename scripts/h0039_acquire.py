"""H-0039 data: daily history of futures-tracking funds, preserved as a governed dataset.

Owner, 2026-10-04: "i want you to build a smart futuers trading strategy".

WHAT IT FETCHES. One raw Yahoo Finance chart payload per symbol (daily bars,
dividend- and split-adjusted close included), 2006-01-01 to 2026-10-02:

  - 19 exchange-traded funds, each standing in for one futures market (the
    table in scripts/h0039_trend.py says which contract each one stands for);
  - ^IRX, the 13-week Treasury bill yield, for the cash return.

SPY is both a market and the benchmark. No account, no key, no credential:
the endpoint is public. Nothing here computes a return.

WHAT IT WRITES. The payload bytes exactly as received, one file per symbol,
under data/research/<DATASET_ID>/ (made read-only); a `sha256sum` list and a
manifest in docs/datasets/; and a registry entry with the dataset-level hash
(research_gate.dataset_hash), so the H-0039 runner can load it only through
research_gate.verify_dataset. It refuses to touch a dataset that exists.

Usage:  python scripts/h0039_acquire.py
"""

import hashlib
import json
import os
import stat
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import research_gate  # noqa: E402

DATASET_ID = "futures-proxies-yahoo-2006-2026-20"
SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "SHY", "IEF", "TLT", "GLD", "SLV", "DBB",
           "USO", "UNG", "DBA", "FXE", "FXY", "FXB", "FXA", "FXC", "FXF", "^IRX"]
START = datetime(2006, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 10, 3, tzinfo=timezone.utc)      # through Friday 2026-10-02
URL = ("https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}"
       "&interval=1d&events=div%2Csplit&includeAdjustedClose=true")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def file_name(symbol):
    return symbol.replace("^", "") + ".json"


def fetch(symbol):
    url = URL.format(symbol=urllib.parse.quote(symbol), p1=int(START.timestamp()),
                     p2=int(END.timestamp()))
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        return url, response.status, response.read()


def describe(raw):
    """Structure checks and metadata. Raises on a payload the engine cannot read."""
    body = json.loads(raw.decode("utf-8"))
    if body["chart"].get("error"):
        raise ValueError("chart error: {0}".format(body["chart"]["error"]))
    result = body["chart"]["result"][0]
    stamps = result["timestamp"]
    adj = result["indicators"]["adjclose"][0]["adjclose"]
    close = result["indicators"]["quote"][0]["close"]
    if not (len(stamps) == len(adj) == len(close)):
        raise ValueError("timestamp, close and adjclose lengths differ")
    present = [i for i, v in enumerate(adj) if v is not None]
    day = lambda i: utc_day(stamps[i])
    meta = result["meta"]
    first_trade = meta.get("firstTradeDate")
    return {"points": len(stamps), "points_with_adjclose": len(present),
            "first": day(present[0]), "last": day(present[-1]),
            "currency": meta.get("currency"), "instrument_type": meta.get("instrumentType"),
            "exchange": meta.get("exchangeName"),
            "first_trade_date_utc": utc_day(first_trade) if first_trade is not None else None}


def utc_day(stamp):
    # Not datetime.fromtimestamp: on Windows it rejects negative stamps, and
    # ^IRX's first trade date is before 1970.
    return (EPOCH + timedelta(seconds=int(stamp))).date().isoformat()


def main():
    target = research_gate.RESEARCH_ROOT / DATASET_ID
    registry = research_gate.registry()
    if target.exists() or DATASET_ID in registry["datasets"]:
        print("REFUSED: {0} already exists; a preserved dataset is never rewritten.".format(DATASET_ID))
        return 2
    staging = target.with_name(target.name + ".partial")
    staging.mkdir(parents=True, exist_ok=False)
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    files = []
    for symbol in SYMBOLS:
        url, status, raw = fetch(symbol)
        info = describe(raw)
        name = file_name(symbol)
        (staging / name).write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        files.append({"file": name, "symbol": symbol, "bytes": len(raw), "sha256": digest,
                      "http_status": status, "url": url, "meta": info})
        print("{0:5} {1:>6} points  {2} .. {3}  {4:>9} bytes".format(
            symbol, info["points_with_adjclose"], info["first"], info["last"], len(raw)), flush=True)
        time.sleep(1.0)
    os.replace(staging, target)
    for path in target.iterdir():
        os.chmod(path, stat.S_IREAD)

    entries = {f["file"]: (f["bytes"], f["sha256"]) for f in files}
    dataset_sha256 = research_gate.dataset_hash(entries)
    checksums = REPO / "docs" / "datasets" / (DATASET_ID + ".sha256")
    checksums.write_text("".join("{0}  {1}\n".format(f["sha256"], f["file"])
                                 for f in sorted(files, key=lambda f: f["file"])), encoding="utf-8")
    manifest_path = REPO / "docs" / "datasets" / (DATASET_ID + ".manifest.json")
    manifest = {
        "dataset_id": DATASET_ID, "dataset_sha256": dataset_sha256, "file_count": len(files),
        "bytes": sum(f["bytes"] for f in files), "fetched_at_utc": fetched_at,
        "acquired_by": "scripts/h0039_acquire.py",
        "request": {"endpoint": "query1.finance.yahoo.com/v8/finance/chart", "interval": "1d",
                    "period1": START.isoformat(), "period2": END.isoformat(),
                    "events": "div,split", "includeAdjustedClose": True,
                    "credential": "none - public endpoint"},
        "checksum_list": str(checksums.relative_to(REPO)).replace("\\", "/"),
        "checksum_list_sha256": hashlib.sha256(checksums.read_bytes()).hexdigest(),
        "dataset_hash_rule": ("SHA-256 of '<file>\\t<size>\\t<sha256>\\n' per file, sorted by "
                              "file name (research_gate.dataset_hash)"),
        "preserved_path": "data/research/" + DATASET_ID,
        "copy": "payload bytes exactly as received; files made read-only",
        "files": files,
    }
    manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    registry["datasets"][DATASET_ID] = {
        "status": "preserved",
        "evidence_class": "historical_in_sample",
        "kind": "raw vendor payload - daily bars with adjusted close, one file per symbol",
        "raw_or_derived": "raw",
        "sha256": dataset_sha256,
        "file_count": len(files),
        "bytes": manifest["bytes"],
        "path": "data/research/" + DATASET_ID,
        "checksums": manifest["checksum_list"],
        "manifest": str(manifest_path.relative_to(REPO)).replace("\\", "/"),
        "datasheet": "docs/datasets/" + DATASET_ID + ".md",
        "source_location": "Yahoo Finance public chart endpoint (no credential); request in the manifest",
        "population": ("19 futures-tracking ETFs (US equity index, Treasury, metals, energy, "
                       "agriculture, currency) and ^IRX"),
        "experiments": ["H-0039 (scripts/run_h0039.py)"],
        "acquisition": "scripts/h0039_acquire.py at {0}, before H-0039 was registered".format(fetched_at),
        "window": "{0} .. {1}".format(min(f["meta"]["first"] for f in files),
                                      max(f["meta"]["last"] for f in files)),
        "adjustment": "Yahoo adjusted close: split- and dividend-adjusted, as of the fetch date",
        "information_boundary": ("daily bars through 2026-10-02. A new strategy family: no "
                                 "Clean OOS record exists for it, and nothing here touches the "
                                 "stock strategy's forward record."),
        "execution_relevance": "research only; not read by production code",
        "preserved_on": fetched_at[:10],
        "provenance_class": "A - acquisition script, request and raw bytes preserved",
        "reproducibility": "input data preserved and hash-verifiable",
    }
    research_gate.REGISTRY.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    path = research_gate.verify_dataset(DATASET_ID, dataset_sha256)
    print("registered {0}  sha256 {1}  ({2} files) - verified at {3}".format(
        DATASET_ID, dataset_sha256, len(files), path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

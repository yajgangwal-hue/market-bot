"""FORENSIC_NON_PROMOTIONAL. Acquire SEC Form 4 for the research universe.

FEASIBILITY ONLY. No economic hypothesis, no backtest, no trading rule.
Production is untouched.

ACQUISITION POLICY, recorded because the audit requires it:
  endpoints   https://www.sec.gov/files/company_tickers.json
              https://data.sec.gov/submissions/CIK##########.json
              https://www.sec.gov/Archives/... (filing documents)
  method      HTTPS GET, read-only, public, no authentication
  User-Agent  the owner-approved contact string, passed in via
              --contact so it is never hard-coded into the repository
  rate        MIN_INTERVAL below, held under SEC's stated 10 req/s
  retries     RETRIES attempts with linear backoff; every failure is
              recorded rather than dropped
  provenance  every raw file keeps its URL and retrieval timestamp;
              RAW and DERIVED are written to separate trees and the
              raw tree is never edited by the parser

"no record found" is NEVER written as "no Form 4 existed" - the two are
separate categories all the way through.

  python scripts/form4_acquire.py map     --contact "..."
  python scripts/form4_acquire.py submit  --contact "..."
  python scripts/form4_acquire.py index   --contact "..."
"""

import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

RAW = REPO / "data" / "form4" / "raw"
DERIVED = REPO / "data" / "form4" / "derived"
#: SEC states a 10 req/s maximum. Held deliberately under it.
MIN_INTERVAL = 0.125
RETRIES = 3
WINDOW = (date(2016, 1, 1), date(2026, 9, 30))
_last = [0.0]


def now():
    return datetime.now(timezone.utc).isoformat()


def get(url, contact, binary=False):
    """One rate-limited, identified GET. Returns (bytes, meta)."""
    wait = MIN_INTERVAL - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={
        "User-Agent": contact,
        "Accept-Encoding": "gzip, deflate",
        "Host": urllib.request.urlparse(url).netloc
        if hasattr(urllib.request, "urlparse") else None,
    })
    req.remove_header("Host")
    last_error = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as handle:
                body = handle.read()
                _last[0] = time.monotonic()
                enc = handle.headers.get("Content-Encoding", "")
                if "gzip" in enc:
                    import gzip
                    body = gzip.decompress(body)
                return body, {"url": url, "retrieved_at": now(),
                              "status": handle.status, "attempt": attempt + 1}
        except urllib.error.HTTPError as error:
            last_error = "HTTP {0}".format(error.code)
            _last[0] = time.monotonic()
            if error.code in (403, 404):
                break
            time.sleep(1.0 * (attempt + 1))
        except Exception as error:                       # noqa: BLE001
            last_error = type(error).__name__
            _last[0] = time.monotonic()
            time.sleep(1.0 * (attempt + 1))
    return None, {"url": url, "retrieved_at": now(), "status": None,
                  "error": last_error}


def universe():
    return sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s))


def cmd_map(contact):
    """Stage A. Today's ticker->CIK snapshot. Explicitly a SNAPSHOT."""
    RAW.mkdir(parents=True, exist_ok=True)
    body, meta = get("https://www.sec.gov/files/company_tickers.json", contact)
    if body is None:
        print("FAILED: {0}".format(meta))
        return 2
    (RAW / "company_tickers.json").write_bytes(body)
    (RAW / "company_tickers.meta.json").write_text(
        json.dumps(meta, indent=1), encoding="utf-8")
    rows = json.loads(body)
    by_ticker = {}
    for v in rows.values():
        by_ticker.setdefault(v["ticker"].upper(), []).append(
            {"cik": int(v["cik_str"]), "title": v["title"]})
    uni = universe()
    hit = {t: by_ticker[t] for t in uni if t in by_ticker}
    miss = [t for t in uni if t not in by_ticker]
    dupes = {t: v for t, v in hit.items() if len(v) > 1}
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "ticker_cik.json").write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "source": meta, "snapshot_caveat":
            "company_tickers.json is TODAY'S mapping. It cannot resolve a "
            "ticker that changed hands, and it omits delisted issuers "
            "entirely. Survivorship is NOT established by this file.",
        "universe": len(uni), "mapped": len(hit), "unmapped": miss,
        "duplicate_tickers": dupes,
        "map": {t: v[0]["cik"] for t, v in hit.items()},
        "titles": {t: v[0]["title"] for t, v in hit.items()},
    }, indent=1, sort_keys=True), encoding="utf-8")
    print("universe {0} | mapped {1} | unmapped {2}".format(
        len(uni), len(hit), len(miss)))
    if miss:
        print("  unmapped: {0}".format(", ".join(miss)))
    if dupes:
        print("  duplicate ticker rows: {0}".format(sorted(dupes)))
    print("total tickers in SEC file: {0}".format(len(by_ticker)))
    return 0


def cmd_submit(contact):
    """Stage B. Submissions index per CIK, including older shards."""
    m = json.loads((DERIVED / "ticker_cik.json").read_text(encoding="utf-8"))
    sub = RAW / "submissions"
    sub.mkdir(parents=True, exist_ok=True)
    failures, extra_files = [], 0
    items = sorted(m["map"].items())
    for n, (ticker, cik) in enumerate(items, 1):
        name = "CIK{0:010d}.json".format(cik)
        target = sub / name
        if not target.exists():
            body, meta = get("https://data.sec.gov/submissions/" + name,
                             contact)
            if body is None:
                failures.append({"ticker": ticker, "cik": cik, **meta})
                continue
            target.write_bytes(body)
            (sub / (name + ".meta")).write_text(json.dumps(meta, indent=1),
                                                encoding="utf-8")
        data = json.loads(target.read_bytes())
        for shard in data.get("filings", {}).get("files", []):
            sname = shard.get("name")
            if not sname or (sub / sname).exists():
                continue
            body, meta = get("https://data.sec.gov/submissions/" + sname,
                             contact)
            if body is None:
                failures.append({"ticker": ticker, "cik": cik,
                                 "shard": sname, **meta})
                continue
            (sub / sname).write_bytes(body)
            (sub / (sname + ".meta")).write_text(json.dumps(meta, indent=1),
                                                 encoding="utf-8")
            extra_files += 1
        if n % 25 == 0:
            print("  {0}/{1} issuers".format(n, len(items)), flush=True)
    (DERIVED / "submission_failures.json").write_text(
        json.dumps({"failures": failures, "at": now()}, indent=1),
        encoding="utf-8")
    print("submissions done. extra shards {0}, failures {1}".format(
        extra_files, len(failures)))
    return 0


def cmd_index(contact):
    """Stage C. Derive the Form 4 index. Raw is only READ here."""
    m = json.loads((DERIVED / "ticker_cik.json").read_text(encoding="utf-8"))
    sub = RAW / "submissions"
    rows, per_issuer, no_form4, unreadable = [], {}, [], []
    for ticker, cik in sorted(m["map"].items()):
        paths = [sub / "CIK{0:010d}.json".format(cik)]
        if not paths[0].exists():
            unreadable.append(ticker)
            continue
        head = json.loads(paths[0].read_bytes())
        blocks = [head.get("filings", {}).get("recent", {})]
        for shard in head.get("filings", {}).get("files", []):
            p = sub / shard.get("name", "")
            if p.exists():
                blocks.append(json.loads(p.read_bytes()))
        count = 0
        for blk in blocks:
            forms = blk.get("form", [])
            for i, form in enumerate(forms):
                if form not in ("4", "4/A"):
                    continue
                fdate = blk["filingDate"][i]
                if not (WINDOW[0].isoformat() <= fdate
                        <= WINDOW[1].isoformat()):
                    continue
                rows.append({
                    "ticker": ticker, "cik": cik,
                    "issuer": m["titles"].get(ticker),
                    "form": form,
                    "accession": blk["accessionNumber"][i],
                    "filingDate": fdate,
                    "acceptanceDateTime": blk.get(
                        "acceptanceDateTime", [None] * len(forms))[i],
                    "reportDate": blk.get(
                        "reportDate", [None] * len(forms))[i],
                    "primaryDocument": blk.get(
                        "primaryDocument", [None] * len(forms))[i],
                })
                count += 1
        per_issuer[ticker] = count
        if count == 0:
            no_form4.append(ticker)
    out = {
        "FORENSIC_NON_PROMOTIONAL": True,
        "built_at": now(), "window": [w.isoformat() for w in WINDOW],
        "filings": len(rows),
        "issuers_with_filings": sum(1 for v in per_issuer.values() if v),
        "issuers_zero_filings_in_window": no_form4,
        "issuers_submissions_unreadable": unreadable,
        "per_issuer": per_issuer,
        "note": "zero filings IN WINDOW is not proof no Form 4 exists; it "
                "is a retrieval-and-window statement only",
    }
    (DERIVED / "form4_index.json").write_text(
        json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    (DERIVED / "form4_rows.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows),
        encoding="utf-8")
    print("Form 4/4A filings in window: {0:,}".format(len(rows)))
    print("issuers with >=1: {0} | with zero: {1} | unreadable: {2}".format(
        out["issuers_with_filings"], len(no_form4), len(unreadable)))
    amend = sum(1 for r in rows if r["form"] == "4/A")
    print("amendments (4/A): {0:,} ({1:.2%})".format(
        amend, amend / len(rows) if rows else 0))
    missing_acc = sum(1 for r in rows if not r["acceptanceDateTime"])
    missing_rep = sum(1 for r in rows if not r["reportDate"])
    print("missing acceptanceDateTime: {0:,} ({1:.2%})".format(
        missing_acc, missing_acc / len(rows) if rows else 0))
    print("missing reportDate:         {0:,} ({1:.2%})".format(
        missing_rep, missing_rep / len(rows) if rows else 0))
    by_year = defaultdict(int)
    for r in rows:
        by_year[r["filingDate"][:4]] += 1
    print("by year: {0}".format(dict(sorted(by_year.items()))))
    return 0


def main():
    if len(sys.argv) < 2 or "--contact" not in sys.argv:
        print(__doc__)
        return 2
    contact = sys.argv[sys.argv.index("--contact") + 1]
    if "@" not in contact:
        print("REFUSED: SEC requires a contact address in the User-Agent.")
        return 2
    stage = sys.argv[1]
    return {"map": cmd_map, "submit": cmd_submit,
            "index": cmd_index}[stage](contact)


if __name__ == "__main__":
    raise SystemExit(main())

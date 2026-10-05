"""Preserve the scratchpad-only intraday research stores: byte-identical,
hash-verified, registered.

PRESERVATION TOOLING ONLY. Source files are read as bytes and never written,
renamed, re-encoded or touched. Those bytes are parsed IN MEMORY only for
structural metadata - record counts, first and last timestamps, the symbol a
file carries. No feature, statistic, forward value or result is computed, no
experiment runs, no vendor is contacted. Snapshot CSVs are tokenised only to
count rows and read the session column; no other value is converted or used,
including the forward-outcome columns.

    python scripts/preserve_intraday_stores.py inventory   # read-only
    python scripts/preserve_intraday_stores.py preserve    # copy, verify, register
    python scripts/preserve_intraday_stores.py verify      # re-verify everything

Record: docs/2026-09-24-intraday-data-preservation-audit.md
"""

import csv
import hashlib
import io
import json
import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import research_gate as RG                                       # noqa: E402

#: The one scratchpad that holds every store (the only one with them, verified
#: by research_gate.unpreserved_intraday_store on 2026-09-24).
SOURCE_ROOT = Path(os.environ.get("TEMP", "/tmp")) / "claude" / "C--market-bot" / \
    "ba9a513c-7a3b-43dd-bc7f-dfe8be46d8d9" / "scratchpad"
WORK = REPO / "data" / "_preservation-work"                      # gitignored
DATASETS = REPO / "docs" / "datasets"
PRESERVED_ON = "2026-09-24"

#: store -> preserved dataset ID, one identity per logically distinct store.
#: The boundary of each was established by `inventory` from tracked records.
STORES = {
    "raw/intraday-exits": "intraday-exit-sessions-5min-698",
    "raw/intraday-spy": "spy-5min-2016-2026-quarterly-43",
    "snapshots": "h0014-intraday-snapshots-230",
    "raw/h0017-micro": "h0017-trades-quotes-221",
}
INVENTORY_ONLY = ("raw/intraday-probe",)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def iso(ns):
    return datetime.fromtimestamp(ns / 1e9, timezone.utc).isoformat()


def meta(store, name, raw):
    """Structural metadata from bytes already in memory. Never writes."""
    if store == "snapshots":
        text = raw.decode("utf-8")
        reader = csv.reader(io.StringIO(text))
        header = next(reader)
        first = last = None
        n = 0
        for row in reader:
            if not row:
                continue
            n += 1
            if first is None:
                first = row[0]
            last = row[0]
        return {"symbol": name[:-4], "rows": n, "columns": len(header),
                "header_sha256": sha(",".join(header).encode()),
                "first_session": first, "last_session": last}
    o = json.loads(raw)
    if store == "raw/h0017-micro":
        tr, qu = o.get("trades") or [], o.get("quotes") or []
        tgt = o.get("target") or {}
        return {"symbol": tgt.get("symbol"), "exit": tgt.get("exit"),
                "trades": len(tr), "quotes": len(qu),
                "trade_pages": o.get("trade_pages"), "quote_pages": o.get("quote_pages"),
                "trade_err": o.get("trade_err"), "quote_err": o.get("quote_err"),
                "keys": sorted(o),
                "first_t": min((x["t"] for x in tr + qu), default=None),
                "last_t": max((x["t"] for x in tr + qu), default=None)}
    bars = o.get("bars") or {}
    syms = sorted(bars)
    allb = [b for s in syms for b in bars[s]]
    return {"symbols": syms, "bars": len(allb),
            "next_page_token": o.get("next_page_token"),
            "first_t": min((b["t"] for b in allb), default=None),
            "last_t": max((b["t"] for b in allb), default=None)}


def scan(root, store, with_meta=True):
    """Per-file identity (and metadata) of one directory, sorted by name."""
    d = root / store
    files = sorted(p.name for p in d.iterdir())
    for n in files:
        if not (d / n).is_file():
            raise SystemExit("REFUSED: {0}/{1} is not a regular file".format(store, n))
    out = []
    for n in files:
        p = d / n
        raw = p.read_bytes()
        st = p.stat()
        e = {"file": n, "bytes": len(raw), "sha256": sha(raw),
             "mtime_ns": st.st_mtime_ns, "mtime_utc": iso(st.st_mtime_ns)}
        if st.st_size != len(raw):
            raise SystemExit("REFUSED: size changed while reading " + n)
        if with_meta:
            e["meta"] = meta(store, n, raw)
        out.append(e)
    return out


def dataset_hash(entries):
    return RG.dataset_hash({e["file"]: (e["bytes"], e["sha256"]) for e in entries})


def tree_state(root):
    """(relpath, size, mtime_ns) of every file under the scratchpad - proves
    the source area as a whole was not changed."""
    rows = []
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for f in sorted(fn):
            p = Path(dp) / f
            st = p.stat()
            rows.append("{0}\t{1}\t{2}".format(p.relative_to(root).as_posix(),
                                               st.st_size, st.st_mtime_ns))
    return {"files": len(rows), "sha256": sha("\n".join(rows).encode())}


# ---------------------------------------------------------------- boundaries
def boundaries(inv):
    """Which files each experiment's committed code reads, from tracked records."""
    res = {}
    trades = json.loads((REPO / "docs/phase5/h0011-cache.json").read_text(
        encoding="utf-8"))["BASELINE"]["trades"]
    want = {"{0}_{1}.json".format(t["symbol"], t["exit"]) for t in trades}
    have = {e["file"] for e in inv["raw/intraday-exits"]["files"]}
    res["H-0013 raw/intraday-exits = one file per baseline trade (h0011-cache BASELINE)"] = {
        "expected": len(want), "present": len(have),
        "missing": sorted(want - have)[:10], "unexpected": sorted(have - want)[:10],
        "symbol_matches_name": all(e["meta"]["symbols"] == [e["file"].split("_")[0]]
                                   for e in inv["raw/intraday-exits"]["files"]),
        "date_matches_name": all(e["meta"]["first_t"] and e["meta"]["first_t"][:10] <=
                                 e["file"][:-5].split("_")[1] <= e["meta"]["last_t"][:10]
                                 for e in inv["raw/intraday-exits"]["files"])}
    tg = json.loads((REPO / "docs/phase5/h0017-targets.json").read_text(encoding="utf-8"))
    want = {"{0}_{1}.json".format(t["symbol"], t["exit"]) for t in tg}
    files = inv["raw/h0017-micro"]["files"]
    have = {e["file"] for e in files}
    res["H-0017 raw/h0017-micro = one file per target (h0017-targets.json)"] = {
        "expected": len(want), "present": len(have),
        "missing": sorted(want - have)[:10], "unexpected": sorted(have - want)[:10],
        "target_matches_name": all("{0}_{1}.json".format(e["meta"]["symbol"], e["meta"]["exit"])
                                   == e["file"] for e in files),
        "files_with_trade_err": sum(1 for e in files if e["meta"]["trade_err"]),
        "files_with_quote_err": sum(1 for e in files if e["meta"]["quote_err"]),
        "files_with_zero_trades": sum(1 for e in files if e["meta"]["trades"] == 0),
        "files_with_zero_quotes": sum(1 for e in files if e["meta"]["quotes"] == 0)}
    decade = {p.stem for p in RG.decade_dir().glob("*.csv")}
    have = {e["file"][:-4] for e in inv["snapshots"]["files"]}
    res["H-0014 snapshots = one CSV per decade-dataset symbol (230/230 required)"] = {
        "expected": len(decade), "present": len(have),
        "missing": sorted(decade - have)[:10], "unexpected": sorted(have - decade)[:10],
        "one_header_for_all": len({e["meta"]["header_sha256"] for e in inv["snapshots"]["files"]}) == 1}
    q = sorted(e["file"] for e in inv["raw/intraday-spy"]["files"])
    months = [n[4:11] for n in q]
    expect, y, m = [], 2016, 1
    while (y, m) <= (int(months[-1][:4]), int(months[-1][5:7])):
        expect.append("{0:04d}-{1:02d}".format(y, m))
        m += 3
        if m > 12:
            y, m = y + 1, m - 12
    res["H-0013/H-0014 raw/intraday-spy = every quarterly SPY file (both builders glob *.json)"] = {
        "files": len(q), "contiguous_quarters": months == expect,
        "all_spy_only": all(e["meta"]["symbols"] == ["SPY"] for e in inv["raw/intraday-spy"]["files"])}
    return res


# ------------------------------------------------------------------ commands
def inventory():
    WORK.mkdir(exist_ok=True)
    inv = {"source_root": str(SOURCE_ROOT), "taken_utc": datetime.now(timezone.utc).isoformat(),
           "tree_before": tree_state(SOURCE_ROOT)}
    for store in list(STORES) + list(INVENTORY_ONLY):
        files = scan(SOURCE_ROOT, store)
        inv[store] = {"files": files, "file_count": len(files),
                      "bytes": sum(e["bytes"] for e in files),
                      "dataset_sha256": dataset_hash(files)}
        print("{0:<22} {1:>5} files {2:>14,} bytes  dataset {3}".format(
            store, len(files), inv[store]["bytes"], inv[store]["dataset_sha256"][:16]), flush=True)
    inv["boundaries"] = boundaries(inv)
    inv["tree_after_inventory"] = tree_state(SOURCE_ROOT)
    (WORK / "inventory.json").write_text(json.dumps(inv, indent=1), encoding="utf-8")
    print(json.dumps(inv["boundaries"], indent=1))
    print("source tree unchanged by inventory:", inv["tree_before"] == inv["tree_after_inventory"])


#: What the registry says about each store beyond its identity. Every value
#: here was established by the inventory or by the repository; "UNKNOWN" is
#: written where the repository does not say.
DESCRIBE = {
    "raw/intraday-exits": {
        "kind": "raw vendor payload - 5-minute bars, one file per exit session",
        "raw_or_derived": "raw",
        "experiments": ["H-0013 (scripts/h0013_build_features.py builds the tracked docs/phase5/h0013-features.json that scripts/run_h0013.py reads)",
                        "also read by scripts/intraday_exit_measure.py (Phase 4/5 exit measurement, unregistered)"],
        "population": "the 698 trades of the frozen baseline (docs/phase5/h0011-cache.json BASELINE): 221 reverted, 238 time_exit, 239 stop; 176 symbols",
        "acquisition": "Alpaca /v2/stocks/bars, timeframe=5Min, adjustment=split, limit=10000. The 459 rule-exit sessions were written 2026-09-20T05:50-05:56Z, consistent with scripts/intraday_exits_acquire.py (RULE_REASONS = reverted, time_exit; committed 3c169b5 at 05:57Z) - inferred. The 239 stop sessions were written 06:15-06:18Z by code that is NOT in the repository - UNKNOWN.",
        "information_boundary": "each file holds one historical exit session; exit dates 2016-11-09 .. 2026-09-03, all before the 2026-09-11 freeze",
        "execution_relevance": "measures the rule-exit trigger and trigger-to-close drift (execution calibration). Not read by production code.",
    },
    "raw/intraday-spy": {
        "kind": "raw vendor payload - SPY 5-minute bars, one file per calendar quarter",
        "raw_or_derived": "raw",
        "experiments": ["H-0013 (scripts/h0013_build_features.py reads every file)",
                        "H-0014 (scripts/h0014_acquire_snapshots.py reads every file to build the snapshots' spy_ret / spy_rvol)"],
        "population": "SPY only",
        "acquisition": "Written 2026-09-20T06:18-06:23Z, just before H-0013's registration commit (5367245, 06:24Z). No committed script writes this store; both commits that mention it only read it - acquisition code and request parameters UNKNOWN.",
        "information_boundary": "bars run to 2026-09-18T23:55Z, i.e. PAST the 2026-09-11 research freeze, into the embargo window (paper-operational period, not Clean OOS). The consumers bound their own use - H-0013 reads only exit sessions up to 2026-09-03; the H-0014 snapshots end at session 2026-08-07. Any future use must apply the freeze boundary itself.",
        "execution_relevance": "market-context features only. Not read by production code.",
    },
    "snapshots": {
        "kind": "DERIVED - per-symbol intraday snapshot tables (10 sealed snapshot times per session)",
        "raw_or_derived": "derived",
        "experiments": ["H-0014 (scripts/h0014_analyse.py - the sealed analysis body; scripts/run_h0014.py; scripts/h0014_validate.py; scripts/h0014_ic_yearly.py)"],
        "population": "the fixed 230-symbol decade universe, one CSV per symbol (230/230, the count h0014_analyse requires)",
        "acquisition": "Built by scripts/h0014_acquire_snapshots.py (first committed 6036727) from Alpaca /v2/stocks/bars 5Min adjustment=split, fetched IN MEMORY and never written to disk, plus raw/intraday-spy and the decade daily CSVs. Written 2026-09-20T16:45Z .. 2026-09-21T06:17Z. The raw 5-minute bars for the 230 symbols were NOT retained anywhere, so these tables cannot be rebuilt from preserved data.",
        "information_boundary": "per the H-0014 registration: at snapshot T only bars closing at or before T enter a feature; daily features use closes through D-1. The columns fwd5/fwd10/fwd20, spy_fwd5/10/20, mfe20 and mae20 are forward OUTCOMES (targets), never inputs. Sessions 2016-11-15 .. 2026-08-07.",
        "execution_relevance": "research only. Not read by production code.",
    },
    "raw/h0017-micro": {
        "kind": "raw vendor payload - trades (next session) and quotes (the exit's closing five minutes), one file per target",
        "raw_or_derived": "raw",
        "experiments": ["H-0017 (scripts/h0017_analyse.py reads every file and writes the tracked docs/phase5/h0017-results.json)"],
        "population": "the 221 reverted exits of the frozen baseline (docs/phase5/h0017-targets.json), 120 symbols; each file carries its own target record",
        "acquisition": "Alpaca /v2/stocks/trades and /v2/stocks/quotes (the registration's data_source), limit=10000 per page, fetched by scripts/h0017_acquire.py 2026-09-21T15:07-15:47Z. Page caps were hit on four pulls: trade_err 'capped' in AAPL_2026-02-02, AAPL_2026-07-02 and NVDA_2026-02-25 (600,000 trades each), quote_err 'capped' in NVDA_2026-02-25 (60,000 quotes). The sealed docs/phase5/h0017-results.json already records these as acquisition_errors (trade_capped 3, quote_capped 1). Preserved exactly as acquired.",
        "information_boundary": "exit dates 2016-12-09 .. 2026-08-13; trades end 2026-08-14 - all before the 2026-09-11 freeze",
        "execution_relevance": "limit-order fill bound (execution-model evidence). Not read by production code.",
    },
}


def write_text_lf(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def preserve():
    inv = json.loads((WORK / "inventory.json").read_text(encoding="utf-8"))
    if tree_state(SOURCE_ROOT) != inv["tree_before"]:
        raise SystemExit("STOP: the source tree changed since the inventory")
    for store, did in STORES.items():
        if (RG.RESEARCH_ROOT / did).exists():
            raise SystemExit("STOP: {0} exists already; nothing is overwritten".format(did))
    registry_path = DATASETS / "registry.json"
    raw_reg = registry_path.read_text(encoding="utf-8")
    reg = json.loads(raw_reg)
    if json.dumps(reg, indent=2, ensure_ascii=False) + "\n" != raw_reg.replace("\r\n", "\n"):
        raise SystemExit("STOP: registry.json does not round-trip")
    report = {}
    for store, did in STORES.items():
        src = inv[store]
        dest = RG.RESEARCH_ROOT / did
        dest.mkdir()
        for e in src["files"]:
            shutil.copy2(SOURCE_ROOT / store / e["file"], dest / e["file"])
        copied = scan(RG.RESEARCH_ROOT, did, with_meta=False)
        a = [(e["file"], e["bytes"], e["sha256"]) for e in src["files"]]
        b = [(e["file"], e["bytes"], e["sha256"]) for e in copied]
        if a != b:
            bad = [x for x, y in zip(a, b) if x != y][:5]
            raise SystemExit("STOP: {0} copy differs from its source: {1} (nothing "
                             "deleted or overwritten)".format(did, bad or "file sets differ"))
        for e in copied:
            os.chmod(dest / e["file"], stat.S_IREAD)
        sums = "".join("{0}  {1}\n".format(e["sha256"], e["file"]) for e in src["files"])
        sums_path = DATASETS / (did + ".sha256")
        write_text_lf(sums_path, sums)
        dhash = src["dataset_sha256"]
        manifest = {
            "dataset_id": did, "dataset_sha256": dhash,
            "dataset_hash_rule": "SHA-256 of '<file>\\t<size>\\t<sha256>\\n' per file, sorted by file name (research_gate.dataset_hash)",
            "file_count": src["file_count"], "bytes": src["bytes"],
            "source": {"root": str(SOURCE_ROOT), "store": store},
            "preserved_path": "data/research/" + did, "preserved_on": PRESERVED_ON,
            "checksum_list": "docs/datasets/" + did + ".sha256",
            "checksum_list_sha256": sha(sums.encode("utf-8")),
            "copy": "shutil.copy2 - bytes and modification time; destination made read-only",
            "files": [{"file": e["file"], "bytes": e["bytes"], "sha256": e["sha256"],
                       "source_mtime_utc": e["mtime_utc"], "meta": e["meta"]}
                      for e in src["files"]],
        }
        write_text_lf(DATASETS / (did + ".manifest.json"),
                      json.dumps(manifest, indent=1, sort_keys=True) + "\n")
        d = DESCRIBE[store]
        reg["datasets"][did] = {
            "status": "preserved", "evidence_class": "historical_in_sample",
            "kind": d["kind"], "raw_or_derived": d["raw_or_derived"],
            "sha256": dhash, "file_count": src["file_count"], "bytes": src["bytes"],
            "path": "data/research/" + did,
            "checksums": "docs/datasets/" + did + ".sha256",
            "manifest": "docs/datasets/" + did + ".manifest.json",
            "datasheet": "docs/datasets/intraday-preservation-2026-09-24.md",
            "source_location": "Claude session scratchpad {0}/scratchpad/{1} - kept, untouched".format(
                SOURCE_ROOT.parent.name, store),
            "population": d["population"], "experiments": d["experiments"],
            "acquisition": d["acquisition"],
            "information_boundary": d["information_boundary"],
            "execution_relevance": d["execution_relevance"],
            "preserved_on": PRESERVED_ON,
            "reproducibility": "input data preserved and hash-verifiable; NO experiment was re-run from it",
        }
        report[did] = {"files": src["file_count"], "bytes": src["bytes"], "dataset_sha256": dhash,
                       "checksum_list_sha256": sha(sums.encode("utf-8"))}
        print("preserved", did, report[did], flush=True)
    write_text_lf(registry_path, json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    verify()


def verify():
    """Re-verify every preserved store: through the gate, against its manifest,
    read-only, and against the untouched source."""
    ok = True
    for store, did in STORES.items():
        man = json.loads((DATASETS / (did + ".manifest.json")).read_text(encoding="utf-8"))
        path = RG.verify_dataset(did, man["dataset_sha256"])          # the gate
        dest = scan(RG.RESEARCH_ROOT, did, with_meta=False)
        src = scan(SOURCE_ROOT, store, with_meta=False)
        want = [(e["file"], e["bytes"], e["sha256"]) for e in man["files"]]
        d_ok = [(e["file"], e["bytes"], e["sha256"]) for e in dest] == want
        s_ok = [(e["file"], e["bytes"], e["sha256"]) for e in src] == want
        m_ok = [e["mtime_utc"] for e in src] == [e["source_mtime_utc"] for e in man["files"]]
        ro = all(not os.access(path / e["file"], os.W_OK) for e in dest)
        sums_ok = sha((DATASETS / (did + ".sha256")).read_bytes()) == man["checksum_list_sha256"]
        ok &= d_ok and s_ok and m_ok and ro and sums_ok
        print("{0:<34} gate VERIFIED | copy==manifest {1} | source==manifest {2} | source "
              "mtimes unchanged {3} | read-only {4} | checksum list {5}".format(
                  did, d_ok, s_ok, m_ok, ro, sums_ok), flush=True)
    print("ALL VERIFIED" if ok else "VERIFICATION FAILED")
    return 0 if ok else 1


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "inventory":
        return inventory()
    if cmd == "preserve":
        return preserve()
    if cmd == "verify":
        return verify()
    raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)

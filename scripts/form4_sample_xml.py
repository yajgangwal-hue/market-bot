"""FORENSIC_NON_PROMOTIONAL. Step 3 - reconstruct transactions from XML.

A SEEDED RANDOM SAMPLE, not a selection. 130,069 filings would be a
~4.5 hour acquisition at SEC's rate ceiling; a random sample of SAMPLE
gives the transaction-code census to about +/-1% and is drawn with a
fixed seed BEFORE anything is fetched, so no filing is chosen for
looking interesting. A full parse is required before any economic
experiment and that is stated rather than skipped.

Raw XML lands in the raw tree with its URL and retrieval timestamp.
The parser only ever READS that tree.

No forward return is read. No trading rule is derived.
"""

import json
import random
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from form4_acquire import DERIVED, RAW, get, now                 # noqa: E402

SAMPLE = 2500
SEED = 20260919
XMLDIR = RAW / "ownership"


def url_for(row):
    acc = row["accession"].replace("-", "")
    doc = (row["primaryDocument"] or "").split("/")[-1]
    return "https://www.sec.gov/Archives/edgar/data/{0}/{1}/{2}".format(
        row["cik"], acc, doc)


def text(node, path):
    el = node.find(path)
    if el is None:
        return None
    v = el.find("value")
    el = v if v is not None else el
    return (el.text or "").strip() if el.text else None


def parse(raw_bytes):
    """Return (transactions, problem). Never guesses at a code's meaning."""
    try:
        root = ET.fromstring(raw_bytes)
    except ET.ParseError as error:
        return [], "xml_parse_error: {0}".format(type(error).__name__)
    out = []
    for kind, tag in (("non_derivative", "nonDerivativeTransaction"),
                      ("derivative", "derivativeTransaction")):
        for tr in root.iter(tag):
            out.append({
                "kind": kind,
                "security": text(tr, "securityTitle"),
                "transaction_date": text(tr, "transactionDate"),
                "code": text(tr, "transactionCoding/transactionCode"),
                "shares": text(tr, "transactionAmounts/transactionShares"),
                "price": text(tr,
                              "transactionAmounts/transactionPricePerShare"),
                "acq_disp": text(
                    tr, "transactionAmounts/transactionAcquiredDisposedCode"),
                "direct_indirect": text(
                    tr, "ownershipNature/directOrIndirectOwnership"),
                "shares_after": text(
                    tr,
                    "postTransactionAmounts/sharesOwnedFollowingTransaction"),
            })
    holdings = sum(1 for _ in root.iter("nonDerivativeHolding")) + \
        sum(1 for _ in root.iter("derivativeHolding"))
    return out, ("holdings_only" if not out and holdings else
                 (None if out else "no_transaction_and_no_holding"))


def main():
    if "--contact" not in sys.argv:
        print(__doc__)
        return 2
    contact = sys.argv[sys.argv.index("--contact") + 1]
    if "@" not in contact:
        print("REFUSED: SEC requires a contact address in the User-Agent.")
        return 2
    rows = [json.loads(l) for l in
            (DERIVED / "form4_rows.jsonl").read_text(encoding="utf-8")
            .splitlines() if l.strip()]
    rng = random.Random(SEED)
    picked = rng.sample(rows, min(SAMPLE, len(rows)))
    print("population {0:,} | seeded random sample {1:,} (seed {2})".format(
        len(rows), len(picked), SEED), flush=True)

    XMLDIR.mkdir(parents=True, exist_ok=True)
    fetched, failures, meta_rows = 0, [], []
    for i, row in enumerate(picked, 1):
        name = row["accession"].replace("-", "") + ".xml"
        target = XMLDIR / name
        if not target.exists():
            body, meta = get(url_for(row), contact)
            if body is None:
                failures.append({"accession": row["accession"],
                                 "ticker": row["ticker"], **meta})
                continue
            target.write_bytes(body)
            meta_rows.append({"accession": row["accession"], **meta})
        fetched += 1
        if i % 250 == 0:
            print("  {0}/{1}".format(i, len(picked)), flush=True)
    (DERIVED / "xml_sample_meta.json").write_text(json.dumps({
        "seed": SEED, "sample": len(picked), "fetched": fetched,
        "failures": failures, "provenance": meta_rows[:50],
        "provenance_note": "first 50 shown; every raw file has a .meta twin",
        "at": now()}, indent=1, default=str), encoding="utf-8")

    codes, kinds, ad, di = Counter(), Counter(), Counter(), Counter()
    status = Counter()
    per_filing, priced, shares_ok = [], 0, 0
    for row in picked:
        p = XMLDIR / (row["accession"].replace("-", "") + ".xml")
        if not p.exists():
            status["not_retrieved"] += 1
            continue
        trs, problem = parse(p.read_bytes())
        if problem:
            status[problem] += 1
            continue
        if row["form"] == "4/A":
            status["amended"] += 1
        per_filing.append(len(trs))
        usable = 0
        for t in trs:
            kinds[t["kind"]] += 1
            codes[t["code"] or "MISSING"] += 1
            ad[t["acq_disp"] or "MISSING"] += 1
            di[t["direct_indirect"] or "MISSING"] += 1
            if t["price"] not in (None, ""):
                priced += 1
            if t["shares"] not in (None, ""):
                shares_ok += 1
            if t["code"] and t["acq_disp"] and t["shares"]:
                usable += 1
        status["parsed"] += 1
        status["fully_reconstructable" if usable == len(trs) and trs
               else "partially_reconstructable"] += 1

    total_tr = sum(kinds.values())
    print("\n" + "=" * 78)
    print("STEP 3 - FILING RECONSTRUCTION (seeded random sample)")
    print("=" * 78)
    print("  filings sampled              {0:,}".format(len(picked)))
    print("  retrieval failures           {0:,}".format(len(failures)))
    for k in sorted(status):
        print("  {0:<28} {1:,}".format(k, status[k]))
    print("\n  transactions parsed          {0:,}".format(total_tr))
    if per_filing:
        print("  transactions per filing      mean {0:.2f}, max {1}".format(
            sum(per_filing) / len(per_filing), max(per_filing)))
    print("  with a price                 {0:,} ({1:.1%})".format(
        priced, priced / total_tr if total_tr else 0))
    print("  with a share count           {0:,} ({1:.1%})".format(
        shares_ok, shares_ok / total_tr if total_tr else 0))
    print("\n  non-derivative vs derivative: {0}".format(dict(kinds)))
    print("  acquired / disposed:          {0}".format(dict(ad)))
    print("  direct / indirect:            {0}".format(dict(di)))
    print("\n  TRANSACTION CODE CENSUS (SEC Form 345 codes, NOT interpreted)")
    print("  {0:<8} {1:>9} {2:>9}".format("code", "count", "share"))
    for c, k in codes.most_common(16):
        print("  {0:<8} {1:>9,} {2:>9.2%}".format(c, k, k / total_tr))

    (DERIVED / "xml_sample_census.json").write_text(json.dumps({
        "FORENSIC_NON_PROMOTIONAL": True,
        "seed": SEED, "sample": len(picked), "population": len(rows),
        "status": dict(status), "transactions": total_tr,
        "codes": dict(codes), "kinds": dict(kinds),
        "acquired_disposed": dict(ad), "direct_indirect": dict(di),
        "with_price": priced, "with_shares": shares_ok,
        "retrieval_failures": len(failures),
        "note": "codes are counted, NOT assigned economic meaning",
    }, indent=1, sort_keys=True), encoding="utf-8")
    print("\nwrote {0}".format(
        (DERIVED / "xml_sample_census.json").relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

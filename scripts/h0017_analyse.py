"""H-0017 - fill bound and spread state on the 221 reverted exits.

THE FILL BOUND IS A BOUND. It counts the share volume that actually
transacted at or above the H-0011 limit level during the session the
order would have been working. It does NOT estimate a fill probability,
does NOT assume queue position, and does NOT treat displayed size as
available. Categories are plausibility bands, not outcomes.

Condition codes are applied, not ignored. Trades carrying conditions
that are not regular-way continuous prints are EXCLUDED and counted:
odd-lot, derivatively priced, average price, and the opening/closing
auction prints are not liquidity a resting continuous limit could have
interacted with in the ordinary way.
"""

import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean, median

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
OUT = REPO / "docs" / "phase5" / "h0017-results.json"
SEAL = "b2654c5abeff5ac6f00047e4f8290c0490e4bf5c5a0dcc07b481848ba7d12081"

# Trade condition codes excluded from the fill bound, with reasons.
# A resting continuous limit could not interact with these in the
# ordinary way, so counting them would overstate the bound.
EXCLUDE_TRADE = {
    "I": "odd lot", "4": "derivatively priced", "W": "average price",
    "O": "opening auction print", "6": "closing auction print",
    "M": "market centre close", "Q": "market centre open",
    "5": "reopening print", "9": "corrected consolidated close",
    "B": "average price trade", "7": "qualified contingent trade",
}
# Quote conditions that are not a normal two-sided market.
ABNORMAL_QUOTE = {"B", "C", "H", "L", "N", "O", "T", "U", "V", "Z"}


def et(ts):
    """UTC RFC3339 -> US/Eastern naive. Explicit DST rule; tzdata absent."""
    s = ts.replace("Z", "")
    if "." in s:
        head, frac = s.split(".", 1)
        s = head + "." + frac[:6]
    d = datetime.fromisoformat(s)

    def nth_sun(y, m, n):
        x = datetime(y, m, 1)
        x += timedelta(days=(6 - x.weekday()) % 7)
        return x + timedelta(weeks=n - 1)
    a = nth_sun(d.year, 3, 2) + timedelta(hours=7)
    b = nth_sun(d.year, 11, 1) + timedelta(hours=6)
    return d - timedelta(hours=4 if a <= d < b else 5)


def main():
    files = sorted(RAW.glob("*.json"))
    print("H-0017 analysis | seal {0} | files {1}".format(SEAL[:16],
                                                          len(files)))
    rows = []
    excl = Counter()
    qexcl = Counter()
    errs = Counter()
    for p in files:
        r = json.loads(p.read_text(encoding="utf-8"))
        t = r["target"]
        if r.get("trade_err"):
            errs["trade_" + str(r["trade_err"])] += 1
        if r.get("quote_err"):
            errs["quote_" + str(r["quote_err"])] += 1
        lvl, qty = t["limit_level"], t["qty"]

        # ---- fill bound from TRADES -----------------------------------
        vol_at_or_above = 0
        n_at_or_above = 0
        first_touch = None
        kept = dropped = 0
        for x in r["trades"]:
            cds = x.get("c") or []
            bad = [c for c in cds if c in EXCLUDE_TRADE]
            if bad:
                dropped += 1
                for c in bad:
                    excl[EXCLUDE_TRADE[c]] += 1
                continue
            kept += 1
            if x["p"] >= lvl:
                vol_at_or_above += x["s"]
                n_at_or_above += 1
                if first_touch is None:
                    first_touch = et(x["t"])
        ratio = (vol_at_or_above / qty) if qty else None
        if vol_at_or_above == 0:
            band = "NO-OBSERVED-TRADE"
        elif ratio is not None and ratio > 10:
            band = "HIGH-BOUND"
        else:
            band = "MARGINAL"

        # ---- spread state from NBBO ------------------------------------
        sp = []
        last = None
        for q in r["quotes"]:
            cds = q.get("c") or []
            if any(c in ABNORMAL_QUOTE for c in cds):
                for c in cds:
                    if c in ABNORMAL_QUOTE:
                        qexcl[c] += 1
                continue
            b, a = q.get("bp"), q.get("ap")
            if not b or not a or a <= b:          # crossed/locked/empty
                qexcl["crossed_locked_or_empty"] += 1
                continue
            mid = (a + b) / 2.0
            sp.append({"bid": b, "ask": a, "mid": mid, "spread": a - b,
                       "bps": 1e4 * (a - b) / mid,
                       "bs": q.get("bs"), "as": q.get("as")})
            last = sp[-1]
        rows.append({
            "symbol": t["symbol"], "exit": t["exit"], "third": t["third"],
            "qty": qty, "limit": lvl,
            "trades_kept": kept, "trades_dropped": dropped,
            "n_at_or_above": n_at_or_above, "vol_at_or_above": vol_at_or_above,
            "ratio": ratio, "band": band,
            "first_touch_et": first_touch.strftime("%H:%M:%S")
            if first_touch else None,
            "quotes_used": len(sp),
            "spread_bps_med": median([x["bps"] for x in sp]) if sp else None,
            "last_bid": last["bid"] if last else None,
            "last_ask": last["ask"] if last else None,
            "last_mid": last["mid"] if last else None,
            "last_bs": last["bs"] if last else None,
            "last_as": last["as"] if last else None,
            "limit_vs_nbbo": (
                None if not last else
                "inside" if last["bid"] < lvl < last["ask"] else
                "at_or_below_bid" if lvl <= last["bid"] else
                "at_or_above_ask"),
            "trade_pages": r["trade_pages"], "capped": r["trade_err"] == "capped",
        })

    def band_counts(g):
        c = Counter(x["band"] for x in g)
        return {k: c.get(k, 0) for k in
                ("HIGH-BOUND", "MARGINAL", "NO-OBSERVED-TRADE")}

    def summarise(g):
        r = [x["ratio"] for x in g if x["ratio"] is not None]
        s = [x["spread_bps_med"] for x in g if x["spread_bps_med"] is not None]
        pos = Counter(x["limit_vs_nbbo"] for x in g if x["limit_vs_nbbo"])
        return {"n": len(g), "bands": band_counts(g),
                "median_ratio": median(r) if r else None,
                "mean_ratio": fmean(r) if r else None,
                "median_spread_bps": median(s) if s else None,
                "mean_spread_bps": fmean(s) if s else None,
                "limit_vs_nbbo": dict(pos),
                "quotes_missing": sum(1 for x in g if not x["quotes_used"]),
                "capped_pages": sum(1 for x in g if x["capped"])}

    res = {"FORENSIC_NON_PROMOTIONAL": True, "seal": SEAL,
           "pooled": summarise(rows),
           "thirds": {t: summarise([x for x in rows if x["third"] == t])
                      for t in (1, 2, 3)},
           "trade_conditions_excluded": dict(excl),
           "quote_conditions_excluded": dict(qexcl),
           "acquisition_errors": dict(errs),
           "rows": rows}
    OUT.write_text(json.dumps(res, indent=1, sort_keys=True, default=str),
                   encoding="utf-8")

    p = res["pooled"]
    print("\n=== POOLED {0} EXITS ===".format(p["n"]))
    for k, v in p["bands"].items():
        print("  {0:<20} {1:>4}  {2:>6.1%}".format(k, v, v / p["n"]))
    print("  median volume ratio   {0}".format(
        "{0:,.1f}x".format(p["median_ratio"]) if p["median_ratio"] else "n/a"))
    print("  median spread (bps)   {0}".format(
        "{0:.2f}".format(p["median_spread_bps"])
        if p["median_spread_bps"] else "n/a"))
    print("  limit vs NBBO         {0}".format(p["limit_vs_nbbo"]))
    print("  exits with no usable quotes {0}".format(p["quotes_missing"]))
    print("  exits with capped trade pages {0}".format(p["capped_pages"]))
    print("\n  trade conditions excluded: {0}".format(dict(excl)))
    print("  quote conditions excluded: {0}".format(dict(qexcl)))
    print("  acquisition errors: {0}".format(dict(errs) or "none"))
    print("\nwrote {0}".format(OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

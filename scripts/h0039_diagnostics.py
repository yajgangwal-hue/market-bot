"""H-0039 diagnostics, after the sealed run: where the return came from, and
whether the book can be held in whole contracts. Descriptive only - nothing
here can change H-0039's verdict, and nothing feeds back into its rule.

1. P&L by asset class and calendar year: the daily contributions w * (r - rf)
   summed per class, in % of equity (arithmetic, before costs).
2. Whole contracts. The registration lists "a whole-contract sizing check" as
   a promotion requirement. For each market: the median and latest
   target notional (|w| at the monthly decisions), the notional of the
   smallest contract that trades it, and the account size at which the
   median position is one contract.

   Contract notionals are APPROXIMATE, as of the panel's last session:
   - index, gold, silver and currency levels come from the funds' closes
     through fixed fund-to-underlying ratios;
   - Treasury, copper, crude, natural gas and corn levels are round figures.
   They are good to roughly +-15%: enough to say whether a position is a
   fraction of a contract or several, not to place an order.

Records one dataset use (purpose diagnostic).

Usage:  python scripts/h0039_diagnostics.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import h0039_spec as spec                                      # noqa: E402
import h0039_trend as engine                                   # noqa: E402
import research_gate                                           # noqa: E402

OUT = REPO / "docs" / "phase5" / "h0039-diagnostics.json"

# market: (smallest contract, how its notional is approximated from the last close)
CONTRACTS = {
    "SPY": ("Micro E-mini S&P 500 ($5 x index)", lambda c: c["SPY"] * 10.0 * 5),
    "QQQ": ("Micro E-mini Nasdaq-100 ($2 x index)", lambda c: c["QQQ"] * 41.0 * 2),
    "IWM": ("Micro E-mini Russell 2000 ($5 x index)", lambda c: c["IWM"] * 10.0 * 5),
    "DIA": ("Micro E-mini Dow ($0.50 x index)", lambda c: c["DIA"] * 100.0 * 0.5),
    "SHY": ("2-year Treasury note ($200,000 face)", lambda c: 200_000.0),
    "IEF": ("10-year Treasury note ($100,000 face, ~110)", lambda c: 110_000.0),
    "TLT": ("Treasury bond ($100,000 face, ~115)", lambda c: 115_000.0),
    "GLD": ("Micro gold (10 oz)", lambda c: c["GLD"] * 10.9 * 10),
    "SLV": ("Micro silver (1,000 oz)", lambda c: c["SLV"] / 0.92 * 1000),
    "DBB": ("Micro copper (2,500 lb, ~$5/lb)", lambda c: 12_500.0),
    "USO": ("Micro WTI crude (100 bbl, ~$65)", lambda c: 6_500.0),
    "UNG": ("E-mini natural gas (2,500 MMBtu, ~$3.50)", lambda c: 8_750.0),
    "DBA": ("Mini corn (1,000 bu, ~$4.20)", lambda c: 4_200.0),
    "FXE": ("Micro EUR/USD (EUR 12,500)", lambda c: 12_500 * 1.15),
    "FXY": ("Micro JPY/USD (JPY 1,250,000)", lambda c: 1_250_000 * 0.0068),
    "FXB": ("Micro GBP/USD (GBP 6,250)", lambda c: 6_250 * 1.33),
    "FXA": ("Micro AUD/USD (AUD 10,000)", lambda c: 10_000 * 0.66),
    "FXC": ("Micro CAD/USD (CAD 10,000)", lambda c: 10_000 * 0.72),
    "FXF": ("Micro CHF/USD (CHF 12,500)", lambda c: 12_500 * 1.24),
}
ACCOUNTS = (100_000, 250_000, 1_000_000)


def decision_weights(dates, symbols, returns, rf):
    """Target weights at every monthly decision, exactly as run() computes them."""
    excess = returns - rf[:, None]
    vols = engine.ewma_vols(excess)
    start = engine.first_decision_row(dates)
    rows = [start] + [k for k in engine.decision_rows(dates, "monthly") if k > start]
    return rows, np.array([engine.target_weights(engine.trailing_signals(returns, rf, k),
                                                 vols[k], engine.trailing_correlation(excess, k))
                           for k in rows])


def main():
    directory = research_gate.verify_dataset(spec.DATASET["id"], spec.DATASET["sha256"])
    closes, irx = engine.load(directory)
    dates, symbols, returns, rf = engine.build_panel(closes, irx, spec.END)
    primary = engine.run(dates, symbols, returns, rf)

    classes = sorted({engine.MARKETS[s][0] for s in symbols})
    by_year = {}
    for day, row in zip(primary["dates"], primary["contribution"]):
        year = by_year.setdefault(str(day.year), {c: 0.0 for c in classes})
        for j, s in enumerate(symbols):
            year[engine.MARKETS[s][0]] += float(row[j])
    costs_by_year = {}
    for day, cost in zip(primary["dates"], primary["costs"]):
        costs_by_year[str(day.year)] = costs_by_year.get(str(day.year), 0.0) + float(cost)

    rows, weights = decision_weights(dates, symbols, returns, rf)
    last_close = {s: closes[s][dates[-1]] for s in symbols}
    sizing = {}
    for j, s in enumerate(symbols):
        contract, notional_of = CONTRACTS[s]
        notional = float(notional_of(last_close))
        held = np.abs(weights[:, j])
        median = float(np.median(held[held > 0])) if np.any(held > 0) else 0.0
        latest = float(weights[-1, j])
        sizing[s] = {
            "contract": contract, "approx_contract_notional": round(notional),
            "median_weight": median, "latest_weight": latest,
            "account_for_one_contract_at_median": round(notional / median) if median else None,
            "contracts_at_latest": {str(a): latest * a / notional for a in ACCOUNTS},
        }
    whole = {}
    for a in ACCOUNTS:
        at_median = [s for s in symbols if sizing[s]["median_weight"] * a / sizing[s]["approx_contract_notional"] >= 0.5]
        whole[str(a)] = {"markets_whose_median_position_rounds_to_at_least_one_contract": len(at_median),
                         "of": len(symbols)}

    out = {"note": "descriptive, after the sealed run; cannot change H-0039's verdict",
           "pnl_by_class_by_year_pct": {y: {c: round(100 * v, 3) for c, v in d.items()}
                                        for y, d in by_year.items()},
           "costs_by_year_pct": {y: round(100 * v, 3) for y, v in costs_by_year.items()},
           "latest_decision": dates[rows[-1]].isoformat(), "sizing": sizing,
           "whole_contract_summary": whole}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    with (REPO / "docs" / "dataset-uses.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "at": datetime.now(timezone.utc).isoformat(), "dataset": spec.DATASET["id"],
            "kind": "dataset_use", "note": "H-0039 diagnostics, no accept/reject attached",
            "purpose": "diagnostic", "symbols": len(symbols) + 1}) + "\n")

    print("P&L by class and year (% of equity, before costs):")
    print("year  " + "  ".join("%11s" % c for c in classes) + "      costs")
    for y, d in by_year.items():
        print(y + "  " + "  ".join("%+10.2f%%" % (100 * d[c]) for c in classes)
              + "   %6.2f%%" % (100 * costs_by_year[y]))
    print()
    print("%-4s %-45s %10s %8s %8s %12s   contracts at latest weights: $100k / $250k / $1M" % (
        "", "smallest contract", "notional", "median w", "latest w", "acct for 1"))
    for s in symbols:
        z = sizing[s]
        c = z["contracts_at_latest"]
        print("%-4s %-45s %10s %8.3f %+8.3f %12s   %+6.2f / %+6.2f / %+6.2f" % (
            s, z["contract"], "{:,}".format(z["approx_contract_notional"]), z["median_weight"],
            z["latest_weight"], "{:,}".format(z["account_for_one_contract_at_median"] or 0),
            c["100000"], c["250000"], c["1000000"]))
    print()
    for a, w in whole.items():
        print("${:,}: {} of {} markets' median position is at least half a contract".format(
            int(a), w["markets_whose_median_position_rounds_to_at_least_one_contract"], w["of"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

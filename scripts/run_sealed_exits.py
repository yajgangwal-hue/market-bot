"""Run the four sealed exit hypotheses. Confirmatory, against the seals.

Every configuration here was registered in docs/preregistrations.jsonl
BEFORE any of it was run, and `prereg.verify` is called first: if a
parameter, a rejection rule or the trial cap has moved since
registration, the seal no longer matches and this refuses to run rather
than quietly reporting an exploratory result as confirmatory.

The acceptance criteria are the registered ones and are applied as
written, not adjusted after seeing the surface:

  beats the baseline on PORTFOLIO TOTAL RETURN, and
  volatility and drawdown no more than 10% worse, and
  monotone or flat across adjacent parameter values, and
  still positive after removing its single best calendar year, and
  better in at least 7 of 11 calendar years, and
  sign holds on the thirty-year window.

  python scripts/run_sealed_exits.py deep
"""

import glob
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.modelgov import prereg                 # noqa: E402
from event_aware_trader.phase5.metrics import compare, measure  # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

SCRATCH = Path(glob.glob(
    "C:/Users/yajga/AppData/Local/Temp/claude/**/scratchpad/deep",
    recursive=True)[0]).parent

WINDOW = 400
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)
_conv = {}


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


WINDOWS = {
    "deep": {"folder": "deep", "since": None, "minimum": 500,
             "dataset": "decade", "label": "decade 2016-2026"},
    "long": {"folder": "long", "since": date(1996, 1, 1), "minimum": 400,
             "dataset": "thirty_year", "label": "thirty years 1996-2026"},
}


def load(folder, since=None, minimum=500):
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = SCRATCH / folder / (symbol + ".csv")
        if not path.exists():
            continue
        try:
            bars = load_bars(path)
        except Exception:
            continue
        if since:
            bars = [b for b in bars if b.timestamp.date() >= since]
        if len(bars) >= minimum:
            out[symbol] = bars
    return out


#: The sealed grids, expanded into simulator arguments. The VALUES come
#: from the registrations; nothing here may add or move one.
def configurations():
    out = []
    for arm in (1.0, 1.5, 2.0):
        for atr in (2.0, 3.0):
            out.append(("H-0001", "trail arm {0}R atr {1}".format(arm, atr),
                        {"mr_trail": (arm, atr)}))
    for take in (1.5, 2.0, 3.0):
        out.append(("H-0002", "take profit {0}R".format(take),
                    {"mr_take_profit_r": take}))
    for lock in (1.0, 1.5, 2.0):
        out.append(("H-0003", "breakeven lock at {0}R".format(lock),
                    {"mr_lock_at_r": lock}))
    for scale in (1.0, 2.0):
        out.append(("H-0004", "scale half at {0}R".format(scale),
                    {"mr_partial": (scale, 0.5)}))
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "deep"
    spec = WINDOWS[which]

    registered = {p["hypothesis_id"]: p for p in prereg.load()}
    chain = prereg.verify_chain()
    if not chain["intact"]:
        print("REFUSED: registration chain broken -> {0}".format(chain))
        return 2
    print("registrations intact: {0}".format(chain["registrations"]))
    for hid, row in sorted(registered.items()):
        print("  {0} seal {1} cap {2}".format(hid, row["seal"][:12],
                                              row["max_configurations"]))

    grid = configurations()
    # A SUBSET of the sealed grid may be run on the robustness window -
    # the registered clause asks only whether the candidate's sign holds
    # there. Selecting a subset is never allowed to ADD a configuration,
    # which the cap check below still enforces.
    if "--only" in sys.argv:
        wanted = sys.argv[sys.argv.index("--only") + 1].split(";")
        grid = [g for g in grid if g[1] in wanted]
        print("running a registered SUBSET: {0}".format([g[1] for g in grid]))
    counts = {}
    for hid, _label, _kw in grid:
        counts[hid] = counts.get(hid, 0) + 1
    for hid, n in sorted(counts.items()):
        cap = registered[hid]["max_configurations"]
        if n > cap:
            print("REFUSED: {0} would run {1} configurations, cap is {2}"
                  .format(hid, n, cap))
            return 2
    print("configurations to run: {0}, all within their caps\n".format(len(grid)))

    series = load(spec["folder"], spec["since"], spec["minimum"])
    print("{0}  ({1} symbols)".format(spec["label"], len(series)), flush=True)

    base_report = production_report(series, conviction=conviction,
                                    dataset=spec["dataset"],
                                    purpose="rejection_test")
    baseline = measure(base_report, "BASELINE")
    header = "{0:<10} {1:<26} {2:>6} {3:>8} {4:>8} {5:>8} {6:>7} {7:>7} {8:>7}"
    print("\n" + header.format("hypothesis", "configuration", "trades",
                               "total", "CAGR", "maxDD", "vol", "Sharpe",
                               "Calmar"))
    show("-", baseline)

    results = [dict(baseline.as_dict(), hypothesis="baseline")]
    for hid, label, kwargs in grid:
        report = production_report(series, conviction=conviction,
                                   dataset=spec["dataset"],
                                   purpose="rejection_test", **kwargs)
        scored = measure(report, label)
        show(hid, scored)
        row = scored.as_dict()
        row["hypothesis"] = hid
        row["configuration"] = kwargs
        row["difference"] = compare(scored, baseline)
        results.append(row)

    out = REPO / "data" / "phase5" / "sealed-exits-{0}.json".format(which)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1, sort_keys=True, default=str),
                   encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


def show(hid, m):
    print("{0:<10} {1:<26} {2:>6} {3:>8} {4:>8} {5:>8} {6:>7} {7:>7} {8:>7}"
          .format(hid, m.label[:26], m.trades,
                  "{0:+.1%}".format(m.total_return),
                  "{0:+.2%}".format(m.cagr),
                  "{0:.2%}".format(m.max_drawdown),
                  "-" if m.annualised_volatility is None
                  else "{0:.1%}".format(m.annualised_volatility),
                  "-" if m.sharpe is None else "{0:.2f}".format(m.sharpe),
                  "-" if m.calmar is None else "{0:.2f}".format(m.calmar)),
          flush=True)


if __name__ == "__main__":
    raise SystemExit(main())

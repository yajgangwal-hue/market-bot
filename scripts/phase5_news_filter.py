"""Phase 5 §8, experiments A and B. News as a portfolio filter.

The screening test found that trades opened into an earnings headline did
much worse than the rest. This asks the only question that decides
anything: does REMOVING them make the ACCOUNT more money once the freed
capital is reallocated?

Every price-based filter in this phase separated well on taken trades and
then failed here, so the prior is unkind and the test is worth running for
exactly that reason.

COVERAGE IS REPORTED, NOT ASSUMED. The veto can only answer honestly for a
symbol-day whose news window was actually fetched. Windows outside the
archive are counted and reported, and the run states what fraction of
candidate decisions it could actually see. A filter evaluated at 60%
coverage is a filter evaluated at 60% coverage, and the number goes in the
report.

  python scripts/phase5_news_filter.py deep
"""

import json
import sys
from bisect import bisect_left
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.events import classify_headline        # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.asof import (                   # noqa: E402
    Archive, decision_timestamp)
from event_aware_trader.phase5.headline import label           # noqa: E402
from event_aware_trader.phase5.metrics import compare, measure  # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

# Decade price data comes only through the research dataset gate: verified
# before a bar is read, fail-closed, no scratchpad fallback. It replaced a
# first-match glob over session scratchpads on 2026-09-24
# (docs/2026-09-24-governed-research-dataset-migration.md).
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))
from research_gate import dataset_file, price_dir              # noqa: E402

WINDOW = 400
LOOKBACK_HOURS = 72.0
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)
_conv = {}


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def load(folder, since=None, minimum=500):
    base = price_dir(folder)        # verified before any bar is read
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        bars = load_bars(dataset_file(base, symbol + ".csv"))
        if since:
            bars = [b for b in bars if b.timestamp.date() >= since]
        if len(bars) >= minimum:
            out[symbol] = bars
    return out


class NewsOracle:
    """Answers 'what was public about this name before the decision'.

    Indexed once and queried by bisect, because the veto runs on every
    candidate bar and a linear scan per call turns a five-minute backtest
    into an hour.
    """

    def __init__(self, archive: Archive, covered):
        self.times = {}
        self.items = {}
        for symbol, rows in archive._by_symbol.items():
            # Sort by the KEY only. Two items published in the same
            # second made Python fall through to comparing NewsItem
            # objects, which have no ordering, and the whole run died
            # with a TypeError after the baseline had been computed.
            dated = sorted(((i.published(), i) for i in rows
                            if i.published()), key=lambda pair: pair[0])
            self.times[symbol] = [d for d, _ in dated]
            self.items[symbol] = [i for _, i in dated]
        self.covered = covered
        self.seen = 0
        self.uncovered = 0

    def before(self, symbol, moment):
        floor = moment.timestamp() - LOOKBACK_HOURS * 3600
        times = self.times.get(symbol) or []
        if not times:
            return []
        high = bisect_left(times, moment)
        out = []
        for i in range(high - 1, -1, -1):
            if times[i].timestamp() < floor:
                break
            out.append(self.items[symbol][i])
        return out

    def window(self, symbol, day):
        self.seen += 1
        if "{0} {1}".format(symbol, day.isoformat()) not in self.covered:
            self.uncovered += 1
            return None
        return self.before(symbol, decision_timestamp(day))

    def coverage(self):
        return 1.0 - (self.uncovered / self.seen if self.seen else 0.0)


def veto_earnings(oracle):
    """Skip an entry when an earnings-category headline preceded it."""
    def veto(symbol, history):
        items = oracle.window(symbol, history[-1].timestamp.date())
        if not items:
            return False
        return any(classify_headline(i.headline).category == "earnings"
                   for i in items)
    return veto


def veto_adverse(oracle):
    """Skip an entry when any adverse company headline preceded it."""
    def veto(symbol, history):
        items = oracle.window(symbol, history[-1].timestamp.date())
        if not items:
            return False
        return any(label(i.headline).adverse for i in items)
    return veto


def veto_any_news(oracle):
    """Control: skip on ANY prior item. Expected to be bad; run anyway.

    Without it, a positive result from the earnings filter cannot be
    distinguished from "trading less is simply better here".
    """
    def veto(symbol, history):
        items = oracle.window(symbol, history[-1].timestamp.date())
        return bool(items)
    return veto


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "deep"
    series = load("deep" if which == "deep" else "long",
                  None if which == "deep" else date(1996, 1, 1))
    archive = Archive.load(REPO / "data" / "phase5" /
                           "news-archive-{0}.jsonl".format(which))
    covered_path = REPO / "data" / "phase5" / "news-windows-{0}.txt".format(which)
    covered = {l.strip() for l in
               covered_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    print("{0} symbols, {1} news items, {2} covered windows".format(
        len(series), len(archive.items), len(covered)), flush=True)

    base_report = production_report(series, conviction=conviction,
                                    dataset="decade", purpose="rejection_test")
    baseline = measure(base_report, "BASELINE")
    print("\n{0:<28} {1:>6} {2:>8} {3:>8} {4:>8} {5:>7} {6:>8} {7:>9}".format(
        "variant", "trades", "total", "CAGR", "maxDD", "stop%", "Sharpe",
        "coverage"))
    show(baseline, None)

    results = [baseline.as_dict()]
    for name, factory in (("news: earnings in 72h", veto_earnings),
                          ("news: adverse headline", veto_adverse),
                          ("control: any news at all", veto_any_news)):
        oracle = NewsOracle(archive, covered)
        report = production_report(series, conviction=conviction,
                                   dataset="decade", purpose="rejection_test",
                                   model_veto=factory(oracle))
        scored = measure(report, name)
        show(scored, oracle)
        row = scored.as_dict()
        row["coverage"] = oracle.coverage()
        row["decisions_seen"] = oracle.seen
        row["decisions_uncovered"] = oracle.uncovered
        row["difference"] = compare(scored, baseline)
        results.append(row)

    out = REPO / "data" / "phase5" / "news-filters-{0}.json".format(which)
    out.write_text(json.dumps(results, indent=1, sort_keys=True, default=str),
                   encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


def show(m, oracle):
    print("{0:<28} {1:>6} {2:>8} {3:>8} {4:>8} {5:>7} {6:>8} {7:>9}".format(
        m.label[:28], m.trades, "{0:+.1%}".format(m.total_return),
        "{0:+.2%}".format(m.cagr), "{0:.2%}".format(m.max_drawdown),
        "-" if m.stop_rate is None else "{0:.1%}".format(m.stop_rate),
        "-" if m.sharpe is None else "{0:.2f}".format(m.sharpe),
        "-" if oracle is None else "{0:.1%}".format(oracle.coverage())),
        flush=True)


if __name__ == "__main__":
    raise SystemExit(main())

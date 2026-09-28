"""Read-only regime forensics. NOTHING REGISTERED, NOTHING CHANGED.

THE QUESTION, asked before any risk configuration is tested: does the
distribution of long opportunities actually change enough across market
regimes to justify different portfolio behaviour?

EVERY REGIME LABEL FOR SESSION t IS BUILT FROM CLOSES THROUGH t-1.
The label is then used to bucket what happened ON t. A label built from
t's own close - still less from t's forward return - would answer a
question nobody can trade.

THE PRIMARY REGIME HAS NO FITTED PARAMETER. SPY against its own 200-day
and 50-day simple moving averages, both as of t-1:
    above both          FAVOURABLE
    above exactly one   NEUTRAL
    below both          UNFAVOURABLE
Two textbook lookbacks, no threshold chosen by anyone, three states that
fall out of the construction. Four cross-checks are reported beside it
so that a conclusion resting on one definition is visible as such.

WHAT THIS DELIBERATELY DOES NOT DO. No sweep. No threshold search. No
configuration is simulated, so nothing here can be a result about
returns under a different risk budget - only about whether the
opportunity and risk distribution differs enough to justify asking.
"""

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import fmean, median, pstdev

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import portfolio as portfolio_module   # noqa: E402
from event_aware_trader.data import load_bars                  # noqa: E402
from event_aware_trader.mean_reversion import conviction as shipped_conviction  # noqa: E402
from event_aware_trader.phase5.metrics import measure          # noqa: E402
from event_aware_trader.portfolio import CORRELATION_BUCKETS    # noqa: E402
from event_aware_trader.research import production_report      # noqa: E402
from event_aware_trader.strategy import DEFAULT_UNIVERSE, is_crypto  # noqa: E402

# THE DECADE PRICE DATA, through the research dataset gate. Until 2026-09-24
# this module took the first match of a glob over Claude session scratchpads
# in the OS temp directory, and skipped any file it could not read. It now
# loads only the preserved copy, and only after every file has been verified
# against its manifest and the dataset hash pinned here. There is no fallback
# to a scratchpad: if verification fails, loading fails.
# docs/2026-09-24-research-loader-and-clean-oos-integrity-audit.md
DECADE_DATASET = "decade-2016-2026-split-adjusted-230"
DECADE_SHA256 = "935fed79de9803f1da2a380c6f3f76ab525b27c5d14830bbea4744a7bf73d4a7"
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))
from research_gate import verify_dataset                        # noqa: E402

WINDOW = 400
_full = portfolio_module.mean_reversion_signal
portfolio_module.mean_reversion_signal = lambda s, h, c: _full(s, h[-WINDOW:], c)
_conv = {}

STATES = ("favourable", "neutral", "unfavourable")
MAX_POSITIONS, MAX_PER_BUCKET = 12, 1
MIN_READINGS = 252
TRADING_YEAR = 252.0


def conviction(symbol, history):
    key = (symbol, len(history), history[0].timestamp if history else None)
    hit = _conv.get(key)
    if hit is None:
        hit = _conv[key] = shipped_conviction(history[-40:])
    return hit


def load():
    """The decade dataset, verified before a single bar is read. Fail-closed.

    `verify_dataset` raises unless every file matches its recorded SHA-256 and
    the dataset hash equals DECADE_SHA256. A universe symbol with no file, or a
    file that does not parse, raises here too - nothing is skipped. The
    500-bar population filter is unchanged.
    """
    deep = verify_dataset(DECADE_DATASET, DECADE_SHA256)
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = deep / (symbol + ".csv")
        if not path.exists():
            raise FileNotFoundError(
                "{0} is in the research universe but not in the verified "
                "dataset {1}".format(symbol, DECADE_DATASET))
        bars = load_bars(path)
        if len(bars) >= 500:
            out[symbol] = bars
    return out


def sma(values, n):
    return sum(values[-n:]) / n if len(values) >= n else None


def expanding_rank(seen, value):
    return sum(1 for v in seen if v <= value) / len(seen)


def shift(by_day, days):
    """Move a t-indexed map to t+1, so session t reads t-1's reading."""
    out = {}
    for i, d in enumerate(days):
        out[d] = by_day.get(days[i - 1]) if i else None
    return out


def drawdown(curve):
    peak, worst = curve[0], 0.0
    for v in curve:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1.0)
    return worst


def sharpe(rets):
    if len(rets) < 20:
        return None
    sd = pstdev(rets)
    return (fmean(rets) / sd * (TRADING_YEAR ** 0.5)) if sd else None


def sortino(rets):
    if len(rets) < 20:
        return None
    down = [r for r in rets if r < 0]
    if not down:
        return None
    sd = pstdev(down)
    return (fmean(rets) / sd * (TRADING_YEAR ** 0.5)) if sd else None


def build_signals(series):
    """All regime labels. Every one reads closes through t-1 only."""
    spy = series["SPY"]
    days = [b.timestamp.date() for b in spy]
    closes = [b.close for b in spy]
    labels, diag = {}, {}

    # --- 1. PRIMARY: dual moving average, no fitted parameter -----------
    raw = {}
    for i, d in enumerate(days):
        s200, s50 = sma(closes[:i + 1], 200), sma(closes[:i + 1], 50)
        if s200 is None or s50 is None:
            raw[d] = None
            continue
        above = (closes[i] > s200) + (closes[i] > s50)
        raw[d] = ("favourable" if above == 2 else
                  "neutral" if above == 1 else "unfavourable")
    labels["trend_dual_ma"] = shift(raw, days)

    # --- 2. SPY drawdown from its own expanding peak --------------------
    raw, peak = {}, closes[0]
    for i, d in enumerate(days):
        peak = max(peak, closes[i])
        dd = closes[i] / peak - 1.0
        raw[d] = ("favourable" if dd > -0.02 else
                  "neutral" if dd > -0.10 else "unfavourable")
    labels["spy_drawdown"] = shift(raw, days)

    # --- 3. realised volatility, expanding percentile terciles ----------
    raw, seen = {}, []
    for i, d in enumerate(days):
        if i < 20:
            raw[d] = None
            continue
        rets = [closes[j] / closes[j - 1] - 1.0 for j in range(i - 19, i + 1)]
        vol = pstdev(rets)
        seen.append(vol)
        if len(seen) < MIN_READINGS:
            raw[d] = None
        else:
            r = expanding_rank(seen, vol)
            raw[d] = ("favourable" if r < 1 / 3 else       # calm = favourable
                      "neutral" if r < 2 / 3 else "unfavourable")
    labels["spy_volatility"] = shift(raw, days)

    # --- 4. breadth: share of the universe above its own 200-day SMA ----
    #     SURVIVORSHIP-BIASED: today's constituents, back-projected.
    idx = {d: i for i, d in enumerate(days)}
    counts = defaultdict(lambda: [0, 0])
    for sym, bars in series.items():
        if sym == "SPY":
            continue
        cl = [b.close for b in bars]
        for i, b in enumerate(bars):
            if i < 200:
                continue
            d = b.timestamp.date()
            if d not in idx:
                continue
            counts[d][1] += 1
            if cl[i] > sma(cl[:i + 1], 200):
                counts[d][0] += 1
    raw, seen = {}, []
    for d in days:
        up, tot = counts.get(d, [0, 0])
        if tot < 50:
            raw[d] = None
            continue
        frac = up / tot
        seen.append(frac)
        if len(seen) < MIN_READINGS:
            raw[d] = None
        else:
            r = expanding_rank(seen, frac)
            raw[d] = ("favourable" if r >= 2 / 3 else
                      "neutral" if r >= 1 / 3 else "unfavourable")
    labels["breadth"] = shift(raw, days)
    diag["breadth_coverage"] = {
        "days_with_50plus_names": sum(1 for d in days
                                      if counts.get(d, [0, 0])[1] >= 50),
        "median_names": median([counts[d][1] for d in days
                                if d in counts] or [0]),
    }

    # --- 5. credit tone: HYG/LQD against its own 50-day average ---------
    for name, (a, b) in (("credit_hyg_lqd", ("HYG", "LQD")),
                         ("risk_spy_tlt", ("SPY", "TLT"))):
        if a not in series or b not in series:
            labels[name] = {d: None for d in days}
            continue
        ac = {x.timestamp.date(): x.close for x in series[a]}
        bc = {x.timestamp.date(): x.close for x in series[b]}
        ratio, rdays = [], []
        for d in days:
            if d in ac and d in bc and bc[d]:
                ratio.append(ac[d] / bc[d])
                rdays.append(d)
        raw = {}
        for i, d in enumerate(rdays):
            s50 = sma(ratio[:i + 1], 50)
            s20 = sma(ratio[:i + 1], 20)
            if s50 is None or s20 is None:
                raw[d] = None
                continue
            above = (ratio[i] > s50) + (ratio[i] > s20)
            raw[d] = ("favourable" if above == 2 else
                      "neutral" if above == 1 else "unfavourable")
        labels[name] = shift(raw, days)
    return labels, days, diag


def main():
    series = load()
    spy = series["SPY"]
    print("decade: {0} symbols, SPY {1} -> {2}".format(
        len(series), spy[0].timestamp.date(), spy[-1].timestamp.date()),
        flush=True)
    report = production_report(series, conviction=conviction,
                               dataset="decade", purpose="diagnostic")
    scored = measure(report, "baseline").as_dict()
    print("baseline: {0} trades, total {1:+.4%}, Sharpe {2:.4f}, maxDD "
          "{3:.4%}, exposure {4:.2%}\n".format(
              scored["trades"], scored["total_return"], scored["sharpe"],
              scored["max_drawdown"], scored["exposure"]), flush=True)

    labels, days, diag = build_signals(series)
    spy_close = {b.timestamp.date(): b.close for b in spy}
    closes = {s: {b.timestamp.date(): b.close for b in bs}
              for s, bs in series.items()}

    # ---- 1. signal screening -------------------------------------------
    print("=" * 76)
    print("1. REGIME SIGNAL SCREENING - coverage, stability, leakage")
    print("=" * 76)
    print("  {0:<18} {1:>7} {2:>7} {3:>8} {4:>8} {5:>8} {6:>9}".format(
        "signal", "labelled", "unlab", "fav", "neu", "unfav", "switches"))
    screen = {}
    for name, lab in labels.items():
        vals = [lab.get(d) for d in days]
        good = [v for v in vals if v]
        if not good:
            print("  {0:<18} {1:>7}".format(name, 0))
            continue
        switches = sum(1 for i in range(1, len(vals))
                       if vals[i] and vals[i - 1] and vals[i] != vals[i - 1])
        counts = {s: good.count(s) / len(good) for s in STATES}
        screen[name] = {"labelled": len(good), "unlabelled": len(vals) - len(good),
                        "shares": counts, "switches": switches,
                        "mean_run": len(good) / max(switches, 1)}
        print("  {0:<18} {1:>7} {2:>7} {3:>8.1%} {4:>8.1%} {5:>8.1%} "
              "{6:>9}".format(name, len(good), len(vals) - len(good),
                              counts["favourable"], counts["neutral"],
                              counts["unfavourable"], switches))
    print("\n  mean run length in sessions (higher = more stable):")
    for name, s in screen.items():
        print("    {0:<18} {1:>7.1f}".format(name, s["mean_run"]))
    print("\n  breadth coverage: {0}".format(diag["breadth_coverage"]))

    # ---- 2. what the market itself did, by regime ----------------------
    print("\n" + "=" * 76)
    print("2. SPY's OWN BEHAVIOUR BY REGIME (label from t-1, return on t)")
    print("=" * 76)
    spy_rets = {}
    for i, d in enumerate(days):
        if i:
            spy_rets[d] = spy_close[d] / spy_close[days[i - 1]] - 1.0
    for name in ("trend_dual_ma", "spy_drawdown", "spy_volatility"):
        lab = labels[name]
        print("\n  {0}".format(name))
        print("    {0:<14} {1:>6} {2:>10} {3:>10} {4:>10} {5:>10}".format(
            "state", "days", "ann ret", "ann vol", "Sharpe", "worst day"))
        for st in STATES:
            r = [spy_rets[d] for d in days if lab.get(d) == st and d in spy_rets]
            if len(r) < 20:
                continue
            print("    {0:<14} {1:>6} {2:>10.2%} {3:>10.2%} {4:>10.3f} "
                  "{5:>10.2%}".format(
                      st, len(r), fmean(r) * TRADING_YEAR,
                      pstdev(r) * (TRADING_YEAR ** 0.5), sharpe(r) or 0.0,
                      min(r)))

    # ---- 3. the strategy by regime -------------------------------------
    equity = {t.date(): v for t, v in report.equity_curve}
    cash = {t.date(): v for t, v in report.cash_curve}
    eq_days = sorted(equity)
    port_ret = {}
    for i, d in enumerate(eq_days):
        if i:
            prev = equity[eq_days[i - 1]]
            port_ret[d] = equity[d] / prev - 1.0 if prev else 0.0

    # positions open on each session, reconstructed from the trades
    open_on = defaultdict(list)
    for t in report.trades:
        d0, d1 = t.entry_time.date(), t.exit_time.date()
        for d in eq_days:
            if d0 <= d < d1:
                open_on[d].append(t.symbol)

    print("\n" + "=" * 76)
    print("3. THE FROZEN STRATEGY BY REGIME - primary signal (trend_dual_ma)")
    print("=" * 76)
    lab = labels["trend_dual_ma"]
    per_state = {}
    print("\n  DAILY PORTFOLIO BEHAVIOUR")
    print("  {0:<14} {1:>6} {2:>9} {3:>9} {4:>8} {5:>8} {6:>9} {7:>9}".format(
        "state", "days", "ann ret", "ann vol", "Sharpe", "Sortino",
        "cash", "positions"))
    for st in STATES:
        ds = [d for d in eq_days if lab.get(d) == st]
        r = [port_ret[d] for d in ds if d in port_ret]
        if len(r) < 20:
            continue
        cashpct = fmean([cash[d] / equity[d] for d in ds if equity.get(d)])
        pos = fmean([len(open_on.get(d, [])) for d in ds])
        chained = [1.0]
        for x in r:
            chained.append(chained[-1] * (1.0 + x))
        per_state[st] = {
            "days": len(ds), "ann_ret": fmean(r) * TRADING_YEAR,
            "ann_vol": pstdev(r) * (TRADING_YEAR ** 0.5),
            "sharpe": sharpe(r), "sortino": sortino(r),
            "cash_share": cashpct, "positions": pos,
            "chained_dd": drawdown(chained),
            "worst_day": min(r),
        }
        print("  {0:<14} {1:>6} {2:>9.2%} {3:>9.2%} {4:>8.3f} {5:>8.3f} "
              "{6:>9.1%} {7:>9.2f}".format(
                  st, len(ds), per_state[st]["ann_ret"],
                  per_state[st]["ann_vol"], per_state[st]["sharpe"] or 0.0,
                  per_state[st]["sortino"] or 0.0, cashpct, pos))
    print("\n  regime-conditional drawdown (the chain of that regime's days")
    print("  only - NOT a drawdown anyone could have experienced):")
    for st, v in per_state.items():
        print("    {0:<14} {1:>9.2%}   worst single day {2:>8.2%}".format(
            st, v["chained_dd"], v["worst_day"]))

    # ---- 4. trades and attribution by entry regime ---------------------
    print("\n  TRADES, BY THE REGIME IN FORCE AT ENTRY")
    rows = defaultdict(list)
    for t in report.trades:
        d0, d1 = t.entry_time.date(), t.exit_time.date()
        st = lab.get(d0)
        c = closes.get(t.symbol, {})
        if not st or d0 not in c or d1 not in c or d0 not in spy_close \
                or d1 not in spy_close:
            continue
        notional = abs(t.quantity) * t.entry_price
        r_sym = c[d1] / c[d0] - 1.0
        r_spy = spy_close[d1] / spy_close[d0] - 1.0
        rows[st].append({
            "pnl": t.net_pnl, "notional": notional, "held": t.bars_held,
            "reason": t.exit_reason, "r": t.r_multiple,
            "market": notional * r_spy,
            "selection": notional * (r_sym - r_spy),
            "timing": t.net_pnl - notional * r_sym,
        })
    print("  {0:<14} {1:>6} {2:>8} {3:>8} {4:>10} {5:>9} {6:>8} {7:>7}".format(
        "state", "trades", "win", "pf", "avg $", "med R", "held", "stops"))
    trade_stats = {}
    for st in STATES:
        g = rows.get(st, [])
        if not g:
            continue
        wins = [x["pnl"] for x in g if x["pnl"] > 0]
        losses = [-x["pnl"] for x in g if x["pnl"] <= 0]
        pf = sum(wins) / sum(losses) if losses else float("inf")
        trade_stats[st] = {
            "n": len(g), "win": len(wins) / len(g), "pf": pf,
            "avg": fmean([x["pnl"] for x in g]),
            "median_r": median([x["r"] for x in g]),
            "held": fmean([x["held"] for x in g]),
            "stop_rate": sum(1 for x in g if x["reason"] == "stop") / len(g),
        }
        print("  {0:<14} {1:>6} {2:>8.1%} {3:>8.3f} {4:>10,.0f} {5:>9.3f} "
              "{6:>8.1f} {7:>7.1%}".format(
                  st, len(g), trade_stats[st]["win"], pf,
                  trade_stats[st]["avg"], trade_stats[st]["median_r"],
                  trade_stats[st]["held"], trade_stats[st]["stop_rate"]))

    print("\n  ATTRIBUTION PER DOLLAR OF NOTIONAL - is the EDGE regime-")
    print("  dependent, and is the TIMING DRAG regime-dependent?")
    print("  {0:<14} {1:>6} {2:>13} {3:>11} {4:>11} {5:>11}".format(
        "state", "trades", "notional", "market", "selection", "timing"))
    attr = {}
    for st in STATES:
        g = rows.get(st, [])
        if not g:
            continue
        n = sum(x["notional"] for x in g)
        attr[st] = {k: sum(x[k] for x in g) / n
                    for k in ("market", "selection", "timing")}
        attr[st]["notional"] = n
        print("  {0:<14} {1:>6} {2:>13,.0f} {3:>11.4%} {4:>11.4%} "
              "{5:>11.4%}".format(st, len(g), n, attr[st]["market"],
                                  attr[st]["selection"], attr[st]["timing"]))

    # ---- 5. capacity ----------------------------------------------------
    print("\n" + "=" * 76)
    print("4. PORTFOLIO CAPACITY - does it bind differently by regime?")
    print("=" * 76)
    cands = defaultdict(list)
    for line in (REPO / "data" / "phase5" / "candidates-deep.jsonl"
                 ).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            cands[date.fromisoformat(r["date"])].append(r["symbol"])
    taken = defaultdict(set)
    for t in report.trades:
        taken[t.entry_time.date()].add(t.symbol)

    cap = defaultdict(lambda: {"days": 0, "cands": 0, "entries": 0,
                               "pos_cap": 0, "bucket": 0, "cash": 0,
                               "other": 0, "cand_days": 0})
    for d in eq_days:
        st = lab.get(d)
        if not st:
            continue
        c = cap[st]
        c["days"] += 1
        todays = cands.get(d, [])
        if not todays:
            continue
        c["cand_days"] += 1
        c["cands"] += len(todays)
        got = taken.get(d, set())
        c["entries"] += len(got)
        held = open_on.get(d, [])
        buckets = [CORRELATION_BUCKETS.get(s, "other") for s in held]
        free_cash = cash.get(d, 0.0)
        eq = equity.get(d, 1.0)
        for sym in todays:
            if sym in got:
                continue
            if len(held) >= MAX_POSITIONS:
                c["pos_cap"] += 1
            elif buckets.count(CORRELATION_BUCKETS.get(sym, "other")) \
                    >= MAX_PER_BUCKET:
                c["bucket"] += 1
            elif free_cash < 0.05 * eq:
                c["cash"] += 1
            else:
                c["other"] += 1
    print("  Refusal reasons are attributed in the simulator's own order:")
    print("  position cap, then correlation bucket, then cash. 'other' is a")
    print("  candidate the portfolio had room for and still did not take -")
    print("  the 3-per-day cap, sizing, or ADV.")
    print("\n  {0:<14} {1:>6} {2:>7} {3:>7} {4:>7} {5:>8} {6:>8} {7:>7} {8:>7}"
          .format("state", "days", "cands", "taken", "conv", "pos cap",
                  "bucket", "cash", "other"))
    for st in STATES:
        c = cap.get(st)
        if not c or not c["cands"]:
            continue
        print("  {0:<14} {1:>6} {2:>7} {3:>7} {4:>7.1%} {5:>8} {6:>8} {7:>7} "
              "{8:>7}".format(st, c["days"], c["cands"], c["entries"],
                              c["entries"] / c["cands"], c["pos_cap"],
                              c["bucket"], c["cash"], c["other"]))
    print("\n  candidates per candidate-day, and cash available:")
    print("  {0:<14} {1:>14} {2:>14} {3:>14}".format(
        "state", "cands/day", "mean cash %", "mean positions"))
    for st in STATES:
        ds = [d for d in eq_days if lab.get(d) == st]
        cd = [len(cands.get(d, [])) for d in ds if cands.get(d)]
        if not cd:
            continue
        print("  {0:<14} {1:>14.2f} {2:>14.1%} {3:>14.2f}".format(
            st, fmean(cd),
            fmean([cash[d] / equity[d] for d in ds if equity.get(d)]),
            fmean([len(open_on.get(d, [])) for d in ds])))

    # ---- 6. transitions --------------------------------------------------
    print("\n" + "=" * 76)
    print("5. REGIME TRANSITIONS - could the bot act on them in time?")
    print("=" * 76)
    seq = [(d, lab.get(d)) for d in days if lab.get(d)]
    runs = []
    cur, start = seq[0][1], seq[0][0]
    for d, st in seq[1:]:
        if st != cur:
            runs.append((cur, start, d))
            cur, start = st, d
    runs.append((cur, start, seq[-1][0]))
    lengths = defaultdict(list)
    for st, a, b in runs:
        n = sum(1 for d, s in seq if a <= d < b)
        lengths[st].append(n)
    print("  {0:<14} {1:>8} {2:>10} {3:>10} {4:>12} {5:>12}".format(
        "state", "runs", "median", "mean", "<5 sessions", "<10 sessions"))
    for st in STATES:
        L = lengths.get(st, [])
        if not L:
            continue
        print("  {0:<14} {1:>8} {2:>10.0f} {3:>10.1f} {4:>12} {5:>12}".format(
            st, len(L), median(L), fmean(L),
            "{0} ({1:.0%})".format(sum(1 for x in L if x < 5),
                                   sum(1 for x in L if x < 5) / len(L)),
            "{0} ({1:.0%})".format(sum(1 for x in L if x < 10),
                                   sum(1 for x in L if x < 10) / len(L))))
    print("\n  total regime changes: {0} over {1} labelled sessions "
          "({2:.1f} per year)".format(
              len(runs) - 1, len(seq), (len(runs) - 1) / (len(seq) / 252.0)))

    print("\n  WHIPSAW COST. A run shorter than 10 sessions is a round trip")
    print("  the bot would have made and unmade before it mattered.")
    short = [(st, a, b) for st, a, b in runs
             if sum(1 for d, s in seq if a <= d < b) < 10]
    print("    runs under 10 sessions: {0} of {1} ({2:.0%})".format(
        len(short), len(runs), len(short) / len(runs)))
    print("    sessions inside them:   {0} of {1} ({2:.1%})".format(
        sum(sum(1 for d, s in seq if a <= d < b) for _st, a, b in short),
        len(seq),
        sum(sum(1 for d, s in seq if a <= d < b)
            for _st, a, b in short) / len(seq)))

    print("\n  WHAT SPY DID AROUND A FAVOURABLE -> UNFAVOURABLE FLIP")
    print("  (the defensive signal: is it early, late, or noise?)")
    print("  {0:>10} {1:>10} {2:>10}".format("sessions", "SPY before",
                                             "SPY after"))
    flips = [(runs[i + 1][1], runs[i][0], runs[i + 1][0])
             for i in range(len(runs) - 1)]
    di = {d: i for i, d in enumerate(days)}
    for horizon in (5, 10, 20, 40):
        before, after = [], []
        for d, frm, to in flips:
            if not (frm == "favourable" and to == "unfavourable"):
                continue
            i = di.get(d)
            if i is None or i - horizon < 0 or i + horizon >= len(days):
                continue
            before.append(spy_close[days[i]] / spy_close[days[i - horizon]] - 1.0)
            after.append(spy_close[days[i + horizon]] / spy_close[days[i]] - 1.0)
        if before:
            print("  {0:>10} {1:>10.2%} {2:>10.2%}   n={3}".format(
                horizon, fmean(before), fmean(after), len(before)))
    print("\n  WHAT SPY DID AROUND AN UNFAVOURABLE -> FAVOURABLE FLIP")
    print("  {0:>10} {1:>10} {2:>10}".format("sessions", "SPY before",
                                             "SPY after"))
    for horizon in (5, 10, 20, 40):
        before, after = [], []
        for d, frm, to in flips:
            if not (frm == "unfavourable" and to == "favourable"):
                continue
            i = di.get(d)
            if i is None or i - horizon < 0 or i + horizon >= len(days):
                continue
            before.append(spy_close[days[i]] / spy_close[days[i - horizon]] - 1.0)
            after.append(spy_close[days[i + horizon]] / spy_close[days[i]] - 1.0)
        if before:
            print("  {0:>10} {1:>10.2%} {2:>10.2%}   n={3}".format(
                horizon, fmean(before), fmean(after), len(before)))

    # ---- 7. cross-check across the other signals -----------------------
    print("\n" + "=" * 76)
    print("6. CROSS-CHECK - does the story hold under other definitions?")
    print("=" * 76)
    print("  Strategy annualised return and selection-per-dollar by state,")
    print("  under each signal. Agreement across definitions is the test.")
    cross = {}
    for name, lb in labels.items():
        if not any(lb.values()):
            continue
        print("\n  {0}".format(name))
        print("    {0:<14} {1:>6} {2:>10} {3:>10} {4:>8} {5:>11} {6:>11}".format(
            "state", "days", "ann ret", "ann vol", "trades", "selection",
            "timing"))
        cross[name] = {}
        for st in STATES:
            ds = [d for d in eq_days if lb.get(d) == st]
            r = [port_ret[d] for d in ds if d in port_ret]
            g = []
            for t in report.trades:
                d0, d1 = t.entry_time.date(), t.exit_time.date()
                if lb.get(d0) != st:
                    continue
                c = closes.get(t.symbol, {})
                if d0 not in c or d1 not in c or d0 not in spy_close \
                        or d1 not in spy_close:
                    continue
                notional = abs(t.quantity) * t.entry_price
                g.append((notional,
                          notional * (c[d1] / c[d0] - spy_close[d1]
                                      / spy_close[d0]),
                          t.net_pnl - notional * (c[d1] / c[d0] - 1.0)))
            if len(r) < 20 or not g:
                continue
            tot = sum(x[0] for x in g)
            cross[name][st] = {
                "days": len(ds), "ann_ret": fmean(r) * TRADING_YEAR,
                "ann_vol": pstdev(r) * (TRADING_YEAR ** 0.5),
                "trades": len(g),
                "selection": sum(x[1] for x in g) / tot,
                "timing": sum(x[2] for x in g) / tot}
            v = cross[name][st]
            print("    {0:<14} {1:>6} {2:>10.2%} {3:>10.2%} {4:>8} "
                  "{5:>11.4%} {6:>11.4%}".format(
                      st, v["days"], v["ann_ret"], v["ann_vol"], v["trades"],
                      v["selection"], v["timing"]))

    out = REPO / "docs" / "phase5" / "regime-forensics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "baseline": scored, "screen": screen, "by_state": per_state,
        "trade_stats": trade_stats, "attribution": attr,
        "capacity": {k: dict(v) for k, v in cap.items()},
        "run_lengths": {k: {"n": len(v), "median": median(v),
                            "mean": fmean(v)} for k, v in lengths.items()},
        "transitions": len(runs) - 1,
        "cross_check": cross, "breadth_coverage": diag["breadth_coverage"],
        "note": "read-only regime forensics; nothing registered or changed",
    }, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print("\nwrote {0}".format(out.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

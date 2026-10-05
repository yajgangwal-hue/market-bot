"""Run H-0027..H-0030 exactly as registered. Research only; nothing here trades.

Order, and every refusal:
1. Each hypothesis must be registered, its seal must match the spec as it stands
   now, and every code file must hash to what the registration sealed.
2. The frozen baseline must reproduce +58.5889% / 698 trades, or nothing runs.
3. Each sleeve hypothesis: the overlay on the frozen long book, the sealed
   criteria R1-R6, every robustness run fixed in advance, and the secondary
   measurements. H-0030: one trade per signal, both sides.
4. Classification computed from the sealed criteria - nothing chosen.
"""

import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from event_aware_trader.mean_reversion import MeanReversionConfig        # noqa: E402
from event_aware_trader.modelgov import prereg                          # noqa: E402
from event_aware_trader.portfolio import CORRELATION_BUCKETS            # noqa: E402
from event_aware_trader.research import (check_dataset_gate,           # noqa: E402
                                         load_tbill_rates, production_report,
                                         with_parked_cash)
from event_aware_trader.strategy import INSTRUMENT_NAMES                # noqa: E402

import run_h0026 as r                                                   # verified loader + speed patch
import short_hypotheses_spec as spec                                    # noqa: E402
import short_sleeve_research as sr                                      # noqa: E402

RESULTS = REPO / "docs" / "phase5" / "h0027-h0030-results.json"
TRADES = REPO / "docs" / "phase5" / "h0027-h0030-trades.json"
HALF_SPLIT = date(2021, 1, 1)
RF = 0.023
SPY_DIVIDENDS = 0.0158             # REM-0003: SPY total return exceeds price return by ~1.58 pts/yr
_KW = ("ETF", "Fund", "Trust", "Index", "Shares ")
ETFS = frozenset(({s for s, n in INSTRUMENT_NAMES.items() if any(k in n for k in _KW)} - {"STX"}) | {"GLD"})


def refuse(message):
    print("REFUSED: " + message)
    return 2


# ---------------------------------------------------------------------------
# The long book, as functions of the session date
# ---------------------------------------------------------------------------

class LongBook:
    def __init__(self, report, parked, calendar):
        eq = {t.date(): v for t, v in report.equity_curve}
        cash = {t.date(): v for t, v in report.cash_curve}
        pk = {t.date(): v for t, v in parked.equity_curve}
        self.eq_unparked, self.eq_parked, self.long_value = {}, {}, {}
        last = (report.starting_cash, report.starting_cash, report.starting_cash)
        for d in calendar:
            if d in eq:
                last = (eq[d], pk.get(d, last[1]), cash.get(d, last[2]))
            self.eq_unparked[d], self.eq_parked[d] = last[0], last[1]
            self.long_value[d] = max(0.0, last[0] - last[2])
        self.spans = defaultdict(list)
        for t in report.trades:
            self.spans[t.symbol].append((t.entry_time.date(), t.exit_time.date()))
        for p in report.open_positions:
            self.spans[p.symbol].append((p.entry_time.date(), date(9999, 1, 1)))

    def holds(self, symbol, day):
        return any(a <= day <= b for a, b in self.spans.get(symbol, ()))

    def curve(self, parked=True):
        source = self.eq_parked if parked else self.eq_unparked
        return sorted(source.items())


# ---------------------------------------------------------------------------
# Curves and metrics
# ---------------------------------------------------------------------------

def overlay(series, ctx, rules, book, parked=True):
    """The sleeve on the long book's account. Returns (result, combined curve)."""
    base = book.eq_parked if parked else book.eq_unparked
    result = sr.run_sleeve(series, ctx, rules, base_equity=lambda d: base[d],
                           long_value=lambda d: book.long_value[d],
                           long_holds=book.holds, buckets=CORRELATION_BUCKETS)
    curve, forgone, prev = [], 0.0, None
    for (d, pnl), (_, notional) in zip(result.pnl_curve, result.notional_curve):
        if parked and prev is not None:
            forgone += prev[1] * ctx.rate(d) * (d - prev[0]).days / 365.0
        curve.append((d, base[d] + pnl - forgone))
        prev = (d, notional)
    result.forgone_interest = forgone
    return result, curve


def standalone(series, ctx, rules, capital=100_000.0):
    """The sleeve alone on its own capital: (result, unparked curve, parked curve)."""
    result = sr.run_sleeve(series, ctx, rules, base_equity=lambda d: capital,
                           long_value=lambda d: 0.0, long_holds=lambda s, d: False,
                           buckets=CORRELATION_BUCKETS)
    unparked, parked, interest, prev = [], [], 0.0, None
    for (d, pnl), (_, notional) in zip(result.pnl_curve, result.notional_curve):
        equity = capital + pnl
        if prev is not None:
            idle = max(0.0, prev[1] - prev[2] - 2_000.0 - 0.05 * prev[1])
            interest += idle * ctx.rate(d) * (d - prev[0]).days / 365.0
        unparked.append((d, equity))
        parked.append((d, equity + interest))
        prev = (d, equity + interest, notional)
    return result, unparked, parked


def slice_curve(curve, start, end):
    out, base = [], None
    for d, v in curve:
        if d < start:
            base = (d, v)
        elif d < end:
            out.append((d, v))
    return ([base] if base else []) + out


def metrics(curve):
    m = sr.account_metrics(curve, RF)
    m["by_year"] = {str(k): v for k, v in m.get("by_year", {}).items()}
    return m


def sharpe(curve):
    return sr.account_metrics(curve, RF).get("sharpe")


def daily(curve):
    return {d: x for d, x in sr.daily_returns(curve)}


def spy_curves(ctx, calendar, capital=100_000.0):
    spy = ctx.spy
    price, tr = [], []
    first = spy.closes[spy.index[calendar[0]]]
    growth = 1.0
    prev = None
    for d in calendar:
        i = spy.index.get(d)
        close = spy.closes[i] if i is not None else price[-1][1] / capital * first
        if prev is not None:
            growth *= (close / prev) * (1.0 + SPY_DIVIDENDS) ** (1 / 252)
        price.append((d, capital * close / first))
        tr.append((d, capital * growth))
        prev = close
    return price, tr


def blend(tr_curve, ctx, weight, capital=100_000.0):
    """weight in SPY total return, the rest at the bill rate, rebalanced daily."""
    out, value, prev = [], capital, None
    for d, v in tr_curve:
        if prev is not None:
            spy_r = v / prev[1] - 1.0
            bill = ctx.rate(d) * (d - prev[0]).days / 365.0
            value *= 1.0 + weight * spy_r + (1.0 - weight) * bill
        out.append((d, value))
        prev = (d, v)
    return out


def scaled(curve, ctx, k):
    """The same account with its excess over bills multiplied by k."""
    out, value, prev = [], curve[0][1], None
    for d, v in curve:
        if prev is not None:
            r = v / prev[1] - 1.0
            bill = ctx.rate(d) * (d - prev[0]).days / 365.0
            value *= 1.0 + bill + k * (r - bill)
        out.append((d, value))
        prev = (d, v)
    return out


# ---------------------------------------------------------------------------
# Trade-level reporting
# ---------------------------------------------------------------------------

def trade_rows(trades):
    return [{"symbol": t.symbol, "entry": t.entry_date.isoformat(),
             "exit": t.exit_date.isoformat() if t.exit_date else None, "reason": t.reason,
             "entry_ref": t.entry_ref, "entry_fill": t.entry_fill, "exit_fill": t.exit_fill,
             "stop": t.stop, "qty": t.quantity, "net": t.net, "net_pct": t.net_pct,
             "bars": t.bars_held, "gap": t.gap_through, "mae": t.mae, "mfe": t.mfe,
             "pct_of_equity": (t.net / t.equity_at_entry) if t.equity_at_entry else None,
             "bull": t.regime_bull, "vol": t.regime_vol} for t in trades]


def trade_report(trades):
    rets = [t.net_pct for t in trades]
    out = {"distribution": sr.distribution(rets)}
    by_reason = defaultdict(list)
    for t in trades:
        by_reason[t.reason].append(t.net_pct)
    out["by_reason"] = {k: {"n": len(v), "share": len(v) / len(trades), "mean": statistics.fmean(v)}
                        for k, v in sorted(by_reason.items())} if trades else {}
    if trades:
        maes = [t.mae for t in trades]
        mfes = [t.mfe for t in trades]
        out["mae"] = {"mean": statistics.fmean(maes), "median": statistics.median(maes),
                      "p90": sr.percentile(maes, 0.9), "max": max(maes)}
        out["mfe"] = {"mean": statistics.fmean(mfes), "median": statistics.median(mfes),
                      "p90": sr.percentile(mfes, 0.9), "max": max(mfes)}
        bars = [t.bars_held for t in trades]
        out["holding_sessions"] = {"mean": statistics.fmean(bars), "median": statistics.median(bars)}
        stops = [t for t in trades if t.reason == "stop"]
        gapped = [t for t in stops if t.gap_through]
        out["stops"] = {"n": len(stops), "gapped": len(gapped),
                        "gapped_share": (len(gapped) / len(stops)) if stops else None,
                        "mean_excess_beyond_stop": (statistics.fmean(t.exit_fill / t.stop - 1.0 for t in gapped)
                                                    if gapped else None),
                        "max_excess_beyond_stop": (max(t.exit_fill / t.stop - 1.0 for t in gapped)
                                                   if gapped else None)}
        regime = defaultdict(list)
        for t in trades:
            regime["SPY above 200-day" if t.regime_bull else "SPY below 200-day"].append(t.net_pct)
            regime["vol " + (t.regime_vol or "unknown")].append(t.net_pct)
        out["by_regime_at_entry"] = {k: {"n": len(v), "mean": statistics.fmean(v),
                                         "win_rate": sum(1 for x in v if x > 0) / len(v)}
                                     for k, v in sorted(regime.items())}
        halves = defaultdict(list)
        for t in trades:
            halves["first half" if t.entry_date < HALF_SPLIT else "second half"].append(t.net_pct)
        out["halves"] = {k: sr.distribution(v) for k, v in sorted(halves.items())}
        worst = sorted(trades, key=lambda t: t.net)[:10]
        out["worst_10"] = trade_rows(worst)
        out["worst_pct_of_equity"] = min((t.net / t.equity_at_entry) for t in trades if t.equity_at_entry)
    return out


def expectancy_t(trades):
    d = sr.distribution([t.net_pct for t in trades])
    return d.get("mean"), d.get("t_stat")


def accuracy(series, ctx, signal):
    """Share of (non-overlapping) signals followed by a lower close after k
    sessions, against all eligible stock-days below their 200-day."""
    out = {}
    pops = {"signals": [], "base": []}
    for sym, s in series.items():
        busy = -1
        for i in range(len(s.closes)):
            if not sr.tradable(s, i) or s.sma200[i] is None or s.closes[i] >= s.sma200[i]:
                continue
            pops["base"].append((s, i))
            if i > busy and signal(s, i, ctx) is not None:
                pops["signals"].append((s, i))
                busy = i + 20
    for k in (5, 10, 20):
        for name, pop in pops.items():
            fwd = [s.closes[i + k] / s.closes[i] - 1.0 for s, i in pop if i + k < len(s.closes)]
            out["{0}_{1}d".format(name, k)] = {
                "n": len(fwd), "share_lower": sum(1 for x in fwd if x < 0) / len(fwd) if fwd else None,
                "mean_forward_return": statistics.fmean(fwd) if fwd else None}
    return out


# ---------------------------------------------------------------------------
# One sleeve hypothesis, judged by its sealed criteria
# ---------------------------------------------------------------------------

def judge_sleeve(name, rules, series, ctx, book, book_live, calendar, spy_price, spy_tr):
    out = {"hypothesis": name}
    a_curve = book.curve(parked=True)
    res, c_curve = overlay(series, ctx, rules, book, parked=True)
    a, c = metrics(a_curve), metrics(c_curve)
    trades = res.trades
    mean, t_stat = expectancy_t(trades)

    def halves_delta(curve_c, curve_a):
        return {label: (sharpe(slice_curve(curve_c, lo, hi)) or 0.0) - (sharpe(slice_curve(curve_a, lo, hi)) or 0.0)
                for label, lo, hi in (("first", calendar[0], HALF_SPLIT),
                                      ("second", HALF_SPLIT, date(9999, 1, 1)))}

    delta = (c["sharpe"] or 0.0) - (a["sharpe"] or 0.0)
    delta_halves = halves_delta(c_curve, a_curve)

    # robustness, each fixed in advance
    rob = {}
    for label, variant in (("R5a_cost_12bp", replace(rules, costs=replace(rules.costs, one_way_bps=12.0))),
                           ("R5b_borrow3_div4", replace(rules, costs=replace(rules.costs, borrow_annual=0.03,
                                                                             dividend_annual=0.04)))):
        _, cv = overlay(series, ctx, variant, book, parked=True)
        mv = metrics(cv)
        rob[label] = {"delta_sharpe": (mv["sharpe"] or 0) - (a["sharpe"] or 0),
                      "cagr": mv["cagr"], "control_cagr": a["cagr"],
                      "pass": ((mv["sharpe"] or 0) - (a["sharpe"] or 0)) > 0 and mv["cagr"] >= a["cagr"]}
    a_live = metrics(book_live.curve(parked=True))
    _, c_live_curve = overlay(series, ctx, rules, book_live, parked=True)
    c_live = metrics(c_live_curve)
    rob["R5c_live_long_book"] = {"delta_sharpe": (c_live["sharpe"] or 0) - (a_live["sharpe"] or 0),
                                 "cagr": c_live["cagr"], "control_cagr": a_live["cagr"],
                                 "pass": ((c_live["sharpe"] or 0) - (a_live["sharpe"] or 0)) > 0
                                 and c_live["cagr"] >= a_live["cagr"]}
    etf_res, _ = overlay(series, ctx, replace(rules, symbols=ETFS), book, parked=True)
    etf_mean, etf_t = expectancy_t(etf_res.trades)
    rob["R5d_etf_universe"] = {"trades": len(etf_res.trades), "mean_net_pct": etf_mean, "t": etf_t,
                               "pass": (etf_mean or 0) > 0}

    worst_trade = min(((t.net / t.equity_at_entry) for t in trades if t.equity_at_entry), default=0.0)
    criteria = {
        "R1_full": delta > 0,
        "R1_halves": all(v > 0 for v in delta_halves.values()),
        "R2_expectancy": (mean or 0) > 0 and (t_stat or 0) >= 2.0,
        "R3_cagr": c["cagr"] >= a["cagr"],
        "R4_drawdown": abs(c["max_drawdown"]) <= 1.10 * abs(a["max_drawdown"]),
        "R5_robustness": all(v["pass"] for v in rob.values()),
        "R6_tail": worst_trade >= -0.01 and c["worst_day"] >= a["worst_day"] - 0.005,
    }
    if not (criteria["R1_full"] and criteria["R2_expectancy"] and criteria["R3_cagr"] and criteria["R4_drawdown"]):
        verdict = "REJECTED"
    elif not (criteria["R1_halves"] and criteria["R5_robustness"] and criteria["R6_tail"]):
        verdict = "INCONCLUSIVE"
    else:
        verdict = "PROMISING BUT NOT READY FOR OOS"

    # reported-only variants
    reported = {}
    for bps in (0.0, 12.0, 24.0):
        res_b, cb = overlay(series, ctx, replace(rules, costs=replace(rules.costs, one_way_bps=bps)), book)
        m_b, t_b = expectancy_t(res_b.trades)
        reported["one_way_{0:g}bp".format(bps)] = {"mean_net_pct": m_b, "t": t_b,
                                                   "combined_cagr": metrics(cb)["cagr"]}
    res_h, ch = overlay(series, ctx, replace(rules, costs=replace(rules.costs, rule_exit_haircut=0.0)), book)
    reported["haircut_0"] = {"mean_net_pct": expectancy_t(res_h.trades)[0],
                             "delta_sharpe": (metrics(ch)["sharpe"] or 0) - (a["sharpe"] or 0),
                             "combined_cagr": metrics(ch)["cagr"]}

    # accounts B, C unparked, D, E
    b_res, b_unparked, b_parked = standalone(series, ctx, rules)
    _, c_unparked = overlay(series, ctx, rules, book, parked=False)
    k = (c["volatility"] / a["volatility"]) if a["volatility"] else 1.0
    d_curve = scaled(a_curve, ctx, k)
    spy_m = metrics(spy_tr)
    e2 = blend(spy_tr, ctx, c["volatility"] / spy_m["volatility"])

    # diversification
    a_d, c_d, spy_d = daily(a_curve), daily(c_curve), daily(spy_price)
    sleeve_d, prev = {}, None
    for (d, pnl), (_, cv) in zip(res.pnl_curve, c_curve):
        if prev is not None and prev[1] > 0:
            sleeve_d[d] = (pnl - prev[0]) / prev[1]
        prev = (pnl, cv)
    days = sorted(set(a_d) & set(sleeve_d) & set(spy_d))
    corr_a, _ = sr.correlation_beta([sleeve_d[x] for x in days], [a_d[x] for x in days])
    corr_spy, beta_sleeve = sr.correlation_beta([sleeve_d[x] for x in days], [spy_d[x] for x in days])
    _, beta_a = sr.correlation_beta([a_d[x] for x in days], [spy_d[x] for x in days])
    _, beta_c = sr.correlation_beta([c_d[x] for x in days if x in c_d], [spy_d[x] for x in days if x in c_d])

    # the long book's weak periods
    peak, weak_days = 0.0, set()
    for d, v in a_curve:
        peak = max(peak, v)
        if v < 0.95 * peak:
            weak_days.add(d)
    monthly_a, monthly_s = defaultdict(float), defaultdict(float)
    for x in days:
        key = (x.year, x.month)
        monthly_a[key] += a_d[x]
        monthly_s[key] += sleeve_d[x]
    worst_months = sorted(monthly_a, key=lambda m: monthly_a[m])[:max(1, len(monthly_a) // 10)]
    regime_days = defaultdict(list)
    for x in days:
        bull = ctx.bull(x)
        regime_days["SPY above 200-day" if bull else "SPY below 200-day"].append(x)
        regime_days["vol " + (ctx.vol_regime(x) or "unknown")].append(x)

    def ann(values):
        return statistics.fmean(values) * 252 if values else None

    weak = {
        "A_more_than_5pct_below_peak": {"sessions": len(weak_days),
                                        "A_annualised": ann([a_d[x] for x in days if x in weak_days]),
                                        "sleeve_annualised": ann([sleeve_d[x] for x in days if x in weak_days])},
        "A_worst_decile_months": {"months": len(worst_months),
                                  "A_mean_month": statistics.fmean(monthly_a[m] for m in worst_months),
                                  "sleeve_mean_month": statistics.fmean(monthly_s[m] for m in worst_months)},
        "year_2022": {"A": a["by_year"].get("2022"), "C": c["by_year"].get("2022")},
        "by_regime_daily": {k2: {"sessions": len(v), "A_annualised": ann([a_d[x] for x in v]),
                                 "sleeve_annualised": ann([sleeve_d[x] for x in v]),
                                 "C_annualised": ann([c_d[x] for x in v if x in c_d])}
                            for k2, v in sorted(regime_days.items())},
    }
    exposure = statistics.fmean(n / cv for (_, n), (_, cv) in zip(res.notional_curve, c_curve) if cv > 0)
    years = (calendar[-1] - calendar[0]).days / 365.25
    turnover = sum(t.notional for t in trades) / statistics.fmean(v for _, v in c_curve) / years

    out.update({
        "verdict": verdict, "criteria": criteria,
        "primary": {"delta_sharpe": delta, "delta_sharpe_halves": delta_halves,
                    "sharpe_A": a["sharpe"], "sharpe_C": c["sharpe"]},
        "R2": {"trades": len(trades), "mean_net_pct": mean, "t": t_stat},
        "R6": {"worst_trade_pct_of_equity": worst_trade, "worst_day_C": c["worst_day"], "worst_day_A": a["worst_day"]},
        "robustness": rob, "reported_only": reported,
        "accounts": {"A_frozen_long_parked": a, "A_frozen_long_unparked": metrics(book.curve(parked=False)),
                     "A_live_long_parked": a_live, "C_live_long_plus_sleeve": c_live,
                     "B_sleeve_alone_unparked": metrics(b_unparked), "B_sleeve_alone_parked": metrics(b_parked),
                     "C_combined_parked": c, "C_combined_unparked": metrics(c_unparked),
                     "D_A_scaled_to_C_volatility": dict(metrics(d_curve), scale=k),
                     "E_SPY_price": metrics(spy_price), "E_SPY_total_return_approx": spy_m,
                     "E2_SPY_bill_blend_matched_to_C_volatility": dict(metrics(e2),
                                                                       weight=c["volatility"] / spy_m["volatility"])},
        "diversification": {"corr_sleeve_vs_A": corr_a, "corr_sleeve_vs_SPY": corr_spy,
                            "beta_sleeve_to_SPY": beta_sleeve, "beta_A_to_SPY": beta_a, "beta_C_to_SPY": beta_c},
        "weak_periods": weak,
        "sleeve": {"trades": trade_report(trades), "open_at_end": len(res.open_at_end),
                   "forced_covers": res.forced, "rule_201_skips": res.skipped_rule_201,
                   "long_held_skips": res.skipped_long_held, "capacity_skips": res.skipped_capacity,
                   "exposure_mean_short_notional_over_equity": exposure,
                   "turnover_per_year": turnover,
                   "forgone_interest_dollars": res.forgone_interest,
                   "B_trades": len(b_res.trades)},
        "accuracy": accuracy(series, ctx, rules.signal),
    })
    return out, trades


# ---------------------------------------------------------------------------
# H-0030: one trade per signal
# ---------------------------------------------------------------------------

def h0030(series, ctx, costs):
    out = {}
    sides = {
        "long": (sr.long_rule_signal,
                 lambda s, i, c, **kw: sr.long_outcome(s, i, c),
                 lambda s, i, c, first: sr.long_outcome(s, i, c, target_pct=0.005, stop_pct=0.002,
                                                        ambiguous_target_first=first)),
        "short": (sr.mirror_signal,
                  lambda s, i, c, **kw: sr.short_outcome(s, i, c, sr.ShortExits()),
                  lambda s, i, c, first: sr.short_outcome(
                      s, i, c, sr.ShortExits(target_pct=0.005, stop_pct=0.002, rsi_cover=None),
                      ambiguous_target_first=first)),
    }
    for side, (signal, frozen_fn, tight_fn) in sides.items():
        def frozen_bars(s, i):
            o = frozen_fn(s, i, costs)
            return o.bars if o else None
        signals = sr.non_overlapping(series, signal, ctx, frozen_bars)
        rows = []
        for sym, i in signals:
            s = series[sym]
            f = frozen_fn(s, i, costs)
            tc = tight_fn(s, i, costs, False)
            to = tight_fn(s, i, costs, True)
            if f and tc and to:
                rows.append((s, i, f, tc, to))
        diff = [tc.net_pct - f.net_pct for _, _, f, tc, _ in rows]
        halves = defaultdict(list)
        for (s, i, f, tc, _), d in zip(rows, diff):
            halves["first" if s.dates[i] < HALF_SPLIT else "second"].append(d)
        tight = [tc for _, _, _, tc, _ in rows]
        stops = [x.net_pct for x in tight if x.reason == "stop"]
        gapped = [x for x in tight if x.reason == "stop" and x.gap]
        wins = [x.net_pct for x in tight if x.net_pct > 0]
        losses = [-x.net_pct for x in tight if x.net_pct <= 0]
        breakeven = (statistics.fmean(losses) / (statistics.fmean(wins) + statistics.fmean(losses))
                     if wins and losses else None)
        dist_diff = sr.distribution(diff)
        tight_mean = statistics.fmean(x.net_pct for x in tight) if tight else 0.0
        pass_ = ((dist_diff.get("mean") or 0) > 0 and (dist_diff.get("t_stat") or 0) >= 2.0
                 and all(statistics.fmean(v) > 0 for v in halves.values()) and tight_mean > 0)
        reject = (dist_diff.get("mean") or 0) <= 0 or tight_mean <= 0
        cost_rows = {}
        for bps in (0.0, 12.0):
            c2 = replace(costs, one_way_bps=bps)
            fz = [frozen_fn(s, i, c2) for s, i, *_ in rows]
            tg = [tight_fn(s, i, c2, False) for s, i, *_ in rows]
            cost_rows["one_way_{0:g}bp".format(bps)] = {
                "frozen_mean": statistics.fmean(x.net_pct for x in fz if x),
                "tight_mean": statistics.fmean(x.net_pct for x in tg if x)}
        out[side] = {
            "verdict": "PROMISING BUT NOT READY FOR OOS" if pass_ else ("REJECTED" if reject else "INCONCLUSIVE"),
            "signals": len(rows),
            "paired_difference": dist_diff,
            "paired_difference_halves": {k: statistics.fmean(v) for k, v in sorted(halves.items())},
            "frozen": sr.distribution([f.net_pct for _, _, f, _, _ in rows]),
            "tight_stop_first": sr.distribution([x.net_pct for x in tight]),
            "tight_target_first_bound": sr.distribution([to.net_pct for _, _, _, _, to in rows]),
            "tight_exit_mix": {k: sum(1 for x in tight if x.reason == k) / len(tight)
                               for k in sorted({x.reason for x in tight})} if tight else {},
            "tight_target_share": (sum(1 for x in tight if x.reason == "take_profit") / len(tight)) if tight else None,
            "tight_stop_realised": {
                "n": len(stops), "mean": statistics.fmean(stops) if stops else None,
                "median": statistics.median(stops) if stops else None,
                "p05": sr.percentile(stops, 0.05), "worst": min(stops) if stops else None,
                "share_worse_than_-0.25%": sum(1 for x in stops if x < -0.0025) / len(stops) if stops else None,
                "share_worse_than_-0.5%": sum(1 for x in stops if x < -0.005) / len(stops) if stops else None,
                "share_worse_than_-1.0%": sum(1 for x in stops if x < -0.01) / len(stops) if stops else None,
                "share_gapped": len(gapped) / len(stops) if stops else None},
            "tight_sessions_held": {"mean": statistics.fmean(x.bars for x in tight),
                                    "median": statistics.median(x.bars for x in tight)} if tight else {},
            "breakeven_win_rate": breakeven,
            "cost_sensitivity": cost_rows,
        }
    return out


# ---------------------------------------------------------------------------

def main():
    registered = {}
    for h in spec.hypotheses():
        try:
            registered[h.hypothesis_id] = prereg.verify(h.hypothesis_id, h)
        except prereg.RegistrationError as error:
            return refuse(str(error))
    if not prereg.verify_chain()["intact"]:
        return refuse("registration chain broken")

    bars = r.load()
    check_dataset_gate(bars, "decade", "rejection_test")      # this engine's own read, recorded
    rates = load_tbill_rates(REPO / "data" / "tbill.csv")
    base = production_report(bars, conviction=r.conviction, dataset="decade",
                             purpose="rejection_test", mr_config=MeanReversionConfig())
    if round(base.equity / base.starting_cash - 1.0, 6) != 0.585889 or len(base.trades) != 698:
        return refuse("the frozen baseline did not reproduce: {0:.6%} / {1}".format(
            base.equity / base.starting_cash - 1.0, len(base.trades)))
    live = production_report(bars, conviction=r.conviction, dataset="decade",
                             purpose="rejection_test", mr_config=MeanReversionConfig(),
                             mr_take_profit_r=1.0, mr_take_profit_trade_through=0.0005)
    print("baseline reproduced: +58.5889% / 698", flush=True)

    series = {sym: sr.Series.from_bars(sym, b) for sym, b in bars.items()}
    ctx = sr.Context(series["SPY"], rates)
    calendar = list(series["SPY"].dates)
    book = LongBook(base, with_parked_cash(base, rates), calendar)
    book_live = LongBook(live, with_parked_cash(live, rates), calendar)
    spy_price, spy_tr = spy_curves(ctx, calendar)

    costs = sr.Costs(**spec.COSTS)
    common = dict(costs=costs, notional_fraction=0.05, max_positions=6, max_short_fraction=0.30)
    sleeves = {
        "H-0027": sr.SleeveRules(signal=sr.mirror_signal, exits=sr.ShortExits(), **common),
        "H-0028": sr.SleeveRules(signal=sr.mirror_signal, exits=sr.ShortExits(), bear_gate=True, **common),
        "H-0029": sr.SleeveRules(signal=sr.relative_weakness_signal,
                                 exits=sr.ShortExits(rsi_cover=None), **common),
    }
    results = {"registrations": {k: {"seal": v["seal"], "registered_at": v["registered_at"]}
                                 for k, v in registered.items()},
               "window": [calendar[0].isoformat(), calendar[-1].isoformat()],
               "symbols": len(series), "etf_control_symbols": len(ETFS & set(series))}
    all_trades = {}
    for hid, rules in sleeves.items():
        print("running " + hid, flush=True)
        results[hid], trades = judge_sleeve(hid, rules, series, ctx, book, book_live,
                                            calendar, spy_price, spy_tr)
        all_trades[hid] = trade_rows(trades)
        print("  {0}: {1}".format(hid, results[hid]["verdict"]), flush=True)
    print("running H-0030", flush=True)
    results["H-0030"] = h0030(series, ctx, costs)
    for side in ("long", "short"):
        print("  H-0030 {0}: {1}".format(side, results["H-0030"][side]["verdict"]), flush=True)

    RESULTS.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    TRADES.write_text(json.dumps(all_trades, default=str), encoding="utf-8")
    print("wrote " + str(RESULTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

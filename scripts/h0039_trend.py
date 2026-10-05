"""H-0039 engine: diversified trend following (time-series momentum) on futures-tracking funds.

Owner, 2026-10-04: "i want you to build a smart futuers trading strategy".

THE STRATEGY is taken from the literature, not fitted here:
Moskowitz, Ooi & Pedersen (2012), "Time series momentum", Journal of
Financial Economics 104; Hurst, Ooi & Pedersen (2017), "A Century of
Evidence on Trend-Following Investing", Journal of Portfolio Management 44.

  - Signal, per market, at a rebalance close: the average of the signs of its
    1-, 3- and 12-month (21, 63, 252 sessions) returns in excess of Treasury
    bills. +1 when all three are up, -1 when all are down, +-1/3 when mixed.
  - Risk, per market: annualised exponentially weighted volatility of daily
    excess returns, centre of mass 60 sessions (the estimator in Moskowitz,
    Ooi & Pedersen).
  - Sizing: raw weight = signal / volatility (equal risk per market). The book
    is then scaled so its ex-ante volatility is 10% a year, from those
    volatilities and the trailing 252-session correlation matrix. Gross
    notional is capped at 10x equity: a guard against a near-zero volatility
    estimate, not a working limit. Equal risk gives the 2-year note a large
    notional because it barely moves, while its futures margin is under 1% of
    notional, so a tighter notional cap would be a constraint that real
    margin does not impose.
  - Rebalance at the last session of each month and trade at the NEXT
    session's close. Hold until the next rebalance; weights drift with prices.

ACCOUNTING. A futures account keeps its equity in Treasury bills and holds
its positions as notional exposure. Each session:

    R_t = rf_t + sum_i w_i (r_i,t - rf_t) - costs_t

- r_i,t: fund i's total return.
- rf_t: the bill return.
- w_i: position notional as a fraction of equity coming into the session.

Weights then drift: w_i <- w_i (1 + r_i,t - rf_t) / (1 + R_t).

COSTS. Each market has a cost per side, as a fraction of the notional traded:
commission plus at least a tick of slippage on the micro contract, set
conservatively. It is charged on rebalance turnover, and on every roll (two
sides on |w|, ROLLS times a year, accrued daily).

OVERLAY. The futures P&L, F_t = sum_i w_i (r_i,t - rf_t) - costs_t, is added
to an account holding 80% SPY and 20% bills (the bills post the futures
margin): A_t = 0.8 r_SPY,t + 0.2 rf_t + F_t. The weights come from the
stand-alone run. With monthly rebalancing the drift difference that ignores
is second order. This is the governing objective's question: does the
strategy help an account beat SPY?

Pure functions over numpy arrays; no file is written here.
"""

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# proxy fund: (asset class, futures market it stands for, cost per side, rolls a year)
MARKETS = {
    "SPY": ("equity", "S&P 500 index (Micro E-mini)", 0.00010, 4),
    "QQQ": ("equity", "Nasdaq-100 index (Micro E-mini)", 0.00010, 4),
    "IWM": ("equity", "Russell 2000 index (Micro E-mini)", 0.00015, 4),
    "DIA": ("equity", "Dow index (Micro E-mini)", 0.00010, 4),
    "SHY": ("rates", "2-year Treasury note", 0.00005, 4),
    "IEF": ("rates", "10-year Treasury note", 0.00005, 4),
    "TLT": ("rates", "Treasury bond", 0.00010, 4),
    "GLD": ("metals", "gold (micro)", 0.00015, 6),
    "SLV": ("metals", "silver (micro)", 0.00030, 5),
    "DBB": ("metals", "copper (micro)", 0.00030, 5),
    "USO": ("energy", "WTI crude oil (micro)", 0.00030, 12),
    "UNG": ("energy", "Henry Hub natural gas", 0.00060, 12),
    "DBA": ("agriculture", "grains", 0.00050, 5),
    "FXE": ("currency", "euro (micro)", 0.00020, 4),
    "FXY": ("currency", "Japanese yen (micro)", 0.00020, 4),
    "FXB": ("currency", "British pound (micro)", 0.00020, 4),
    "FXA": ("currency", "Australian dollar (micro)", 0.00020, 4),
    "FXC": ("currency", "Canadian dollar (micro)", 0.00020, 4),
    "FXF": ("currency", "Swiss franc (micro)", 0.00020, 4),
}
TBILL = "IRX"
BENCHMARK = "SPY"
LOOKBACKS = (21, 63, 252)
VOL_COM = 60
CORR_WINDOW = 252
TARGET_VOL = 0.10
GROSS_CAP = 10.0
TRADING_DAYS = 252
OVERLAY_SPY = 0.80


# ------------------------------------------------------------------ data

def parse_payload(raw):
    """date -> adjusted close from one raw Yahoo chart payload. Empty bars are skipped."""
    body = json.loads(raw.decode("utf-8"))
    result = body["chart"]["result"][0]
    stamps = result["timestamp"]
    values = result["indicators"]["adjclose"][0]["adjclose"]
    out = {}
    for stamp, value in zip(stamps, values):
        if value is None:
            continue
        value = float(value)
        if not math.isfinite(value) or value <= 0:
            continue
        out[(EPOCH + timedelta(seconds=int(stamp))).date()] = value
    return out


def load(directory):
    """Adjusted closes per market and the bill yield, from a VERIFIED dataset directory."""
    directory = Path(directory)
    closes = {s: parse_payload((directory / (s + ".json")).read_bytes()) for s in MARKETS}
    irx = parse_payload((directory / (TBILL + ".json")).read_bytes())
    return closes, irx


def build_panel(closes, irx, end):
    """Common sessions and aligned daily returns.

    The calendar is the set of sessions EVERY market has, up to `end`; it
    therefore starts on the youngest fund's first day. Row k of `returns` is
    the session dates[k], measured from the previous common session's close.

    The bill yield is carried forward over days the yield series lacks (the
    bond market closes on some stock-market holidays). rf for a session is
    the PREVIOUS session's yield, /100/252: known when the session starts.
    """
    symbols = list(closes)
    common = sorted(set.intersection(*(set(c) for c in closes.values())))
    common = [d for d in common if d <= end]
    prices = np.array([[closes[s][d] for s in symbols] for d in common], dtype=float)
    returns = prices[1:] / prices[:-1] - 1.0
    irx_days = sorted(irx)
    yields, j, last = [], 0, None
    for d in common:
        while j < len(irx_days) and irx_days[j] <= d:
            last = irx[irx_days[j]]
            j += 1
        if last is None:
            raise ValueError("no bill yield on or before {0}".format(d))
        yields.append(last)
    rf = np.array(yields[:-1], dtype=float) / 100.0 / TRADING_DAYS
    return common[1:], symbols, returns, rf


# --------------------------------------------------------------- signals

def trailing_signals(returns, rf, t, lookbacks=LOOKBACKS):
    """Average sign of each market's trailing excess return, rows t-L+1..t inclusive.

    Excess over the window = prod(1 + r) / prod(1 + rf) - 1.
    """
    total = np.zeros(returns.shape[1])
    for length in lookbacks:
        window = returns[t - length + 1: t + 1]
        growth = np.prod(1.0 + window, axis=0) / np.prod(1.0 + rf[t - length + 1: t + 1])
        total += np.sign(growth - 1.0)
    return total / len(lookbacks)


def ewma_vols(excess, com=VOL_COM):
    """Annualised exponentially weighted volatility, row t using rows up to t.

    delta / (1 - delta) = com. Demeaned by the exponentially weighted mean;
    started from the first `com` rows' sample moments. Rows before that are NaN.
    """
    delta = com / (com + 1.0)
    n, m = excess.shape
    out = np.full((n, m), np.nan)
    if n < com:
        return out
    mean = excess[:com].mean(axis=0)
    var = excess[:com].var(axis=0, ddof=1)
    out[com - 1] = np.sqrt(TRADING_DAYS * var)
    for t in range(com, n):
        mean = delta * mean + (1.0 - delta) * excess[t]
        var = delta * var + (1.0 - delta) * (excess[t] - mean) ** 2
        out[t] = np.sqrt(TRADING_DAYS * var)
    return out


def trailing_correlation(excess, t, window=CORR_WINDOW):
    """Sample correlation of the last `window` rows through t; undefined entries -> 0 (diagonal 1)."""
    block = excess[t - window + 1: t + 1]
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.corrcoef(block, rowvar=False)
    corr = np.where(np.isfinite(corr), corr, 0.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def target_weights(signal, vol, corr, target=TARGET_VOL, cap=GROSS_CAP):
    """Equal risk per market, scaled to the target ex-ante volatility, gross capped."""
    raw = np.where(vol > 0, signal / np.where(vol > 0, vol, 1.0), 0.0)
    if not np.any(raw):
        return np.zeros_like(raw)
    cov = np.outer(vol, vol) * corr
    ex_ante = math.sqrt(max(float(raw @ cov @ raw), 0.0))
    if ex_ante <= 0:
        return np.zeros_like(raw)
    weights = raw * (target / ex_ante)
    gross = float(np.abs(weights).sum())
    if gross > cap:
        weights *= cap / gross
    return weights


def decision_rows(dates, frequency):
    """Rows whose session is the last of its month (or ISO week) and has a next session."""
    rows = []
    for k in range(len(dates) - 1):
        here, after = dates[k], dates[k + 1]
        if frequency == "monthly":
            last = (after.year, after.month) != (here.year, here.month)
        elif frequency == "weekly":
            last = after.isocalendar()[:2] != here.isocalendar()[:2]
        else:
            raise ValueError("frequency must be monthly or weekly")
        if last:
            rows.append(k)
    return rows


def first_decision_row(dates, lookbacks=LOOKBACKS):
    """The first month-end with enough history for every lookback, the volatility
    start-up and the correlation window. All variants start deciding here, so they
    are measured over identical sessions."""
    need = max(max(lookbacks), CORR_WINDOW, VOL_COM) - 1
    return next(k for k in decision_rows(dates, "monthly") if k >= need)


# -------------------------------------------------------------- simulate

def run(dates, symbols, returns, rf, lookbacks=LOOKBACKS, frequency="monthly",
        cost_multiplier=1.0, target=TARGET_VOL, cap=GROSS_CAP, start_row=None):
    """Simulate the futures account. Returns per-session arrays from the first
    execution row (inclusive) to the last row.

    A decision at row k (its close) is executed at row k+1's close: row k+1's
    P&L uses the weights held before, and the new weights earn from row k+2.
    """
    n, m = returns.shape
    excess = returns - rf[:, None]
    vols = ewma_vols(excess)
    side = np.array([MARKETS[s][2] for s in symbols]) * cost_multiplier
    roll_rate = 2.0 * side * np.array([MARKETS[s][3] for s in symbols]) / TRADING_DAYS
    start = first_decision_row(dates) if start_row is None else start_row
    # Every variant decides at `start` (a month-end), so a weekly variant does
    # not sit in cash until its first week-end and all are measured alike.
    decisions = [start] + [k for k in decision_rows(dates, frequency) if k > start]
    targets, capped = {}, 0
    for k in decisions:
        signal, corr = trailing_signals(returns, rf, k, lookbacks), trailing_correlation(excess, k)
        targets[k + 1] = target_weights(signal, vols[k], corr, target, cap)
        free = target_weights(signal, vols[k], corr, target, float("inf"))
        capped += int(float(np.abs(free).sum()) > cap)
    first_exec = start + 1
    w = np.zeros(m)
    keys = ("account", "futures_pnl", "costs", "gross", "turnover")
    out = {k: np.zeros(n - first_exec) for k in keys}
    contribution = np.zeros((n - first_exec, m))
    for t in range(first_exec, n):
        i = t - first_exec
        move = returns[t] - rf[t]
        pnl_by_market = w * move
        roll_cost = float(np.abs(w) @ roll_rate)
        before = rf[t] + float(pnl_by_market.sum()) - roll_cost
        w = w * (1.0 + move) / (1.0 + before)
        trade_cost, turnover = 0.0, 0.0
        if t in targets:
            new = targets[t]
            turnover = float(np.abs(new - w).sum())
            trade_cost = float(np.abs(new - w) @ side)
            w = new.copy()
        out["account"][i] = before - trade_cost
        out["futures_pnl"][i] = float(pnl_by_market.sum()) - roll_cost - trade_cost
        out["costs"][i] = roll_cost + trade_cost
        out["gross"][i] = float(np.abs(w).sum())
        out["turnover"][i] = turnover
        contribution[i] = pnl_by_market
    out["dates"] = list(dates[first_exec:])
    out["rf"] = rf[first_exec:].copy()
    out["contribution"] = contribution
    out["first_execution"] = dates[first_exec]
    out["decisions"] = len(decisions)
    out["decisions_capped"] = capped
    return out


def overlay(spy_returns, rf, futures_pnl, spy_weight=OVERLAY_SPY):
    """80% SPY and 20% bills, plus the futures P&L stream."""
    return spy_weight * spy_returns + (1.0 - spy_weight) * rf + futures_pnl


# --------------------------------------------------------------- measure

def metrics(r, rf, dates):
    """Account-level total-return statistics over the given sessions."""
    r, rf = np.asarray(r, dtype=float), np.asarray(rf, dtype=float)
    equity = np.cumprod(1.0 + r)
    years = len(r) / TRADING_DAYS
    total = float(equity[-1] - 1.0)
    peak = np.maximum.accumulate(np.concatenate([[1.0], equity]))[1:]
    excess = r - rf
    sd = float(excess.std(ddof=1))
    by_year = {}
    for day, value in zip(dates, r):
        by_year[day.year] = by_year.get(day.year, 1.0) * (1.0 + value)
    return {
        "first": dates[0].isoformat(), "last": dates[-1].isoformat(), "sessions": len(r),
        "total_return": total,
        "cagr": float((1.0 + total) ** (1.0 / years) - 1.0) if years > 0 else 0.0,
        "volatility": float(r.std(ddof=1) * math.sqrt(TRADING_DAYS)),
        "mean_excess": float(excess.mean() * TRADING_DAYS),
        "sharpe": float(excess.mean() / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else 0.0,
        "max_drawdown": float((equity / peak - 1.0).min()),
        "by_year": {str(y): v - 1.0 for y, v in sorted(by_year.items())},
    }


def split_rows(dates, split):
    first = [i for i, d in enumerate(dates) if d < split]
    second = [i for i, d in enumerate(dates) if d >= split]
    return first, second


def stationary_bootstrap_p(x, q=0.05, resamples=10_000, seed=20261004):
    """One-sided p-value for mean(x) > 0: Politis & Romano (1994) stationary
    bootstrap, mean block 1/q, re-centred at the sample mean."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    rng = np.random.default_rng(seed)
    mean = float(x.mean())
    positions = np.arange(n)
    exceed = 0
    for _ in range(resamples):
        new = rng.random(n) < q
        new[0] = True
        starts = rng.integers(0, n, size=int(new.sum()))
        block = np.cumsum(new) - 1
        began = np.maximum.accumulate(np.where(new, positions, 0))
        index = (starts[block] + positions - began) % n
        if float(x[index].mean()) - mean >= mean:
            exceed += 1
    return (1 + exceed) / (resamples + 1)


def decide(results):
    """The sealed verdict, from computed numbers only. Gates (registered):

    G1 edge: stand-alone net Sharpe >= 0.30 and bootstrap p <= 0.05.
    G2 survives publication: stand-alone mean excess > 0 in both halves.
    G3 SPY-relative: the overlay's CAGR beats SPY's over the full window and in
       both halves, and its worst drawdown is shallower than SPY's.
    G4 costs: at double costs, Sharpe >= 0.30 and mean excess > 0.

    REJECTED if G1 or G2 fails; NOT REJECTED if all four hold; WEAK otherwise.
    """
    p, d, o, s = (results["primary"], results["double_cost"], results["overlay"],
                  results["spy"])
    gates = {
        "G1_edge": p["full"]["sharpe"] >= 0.30 and p["bootstrap_p"] <= 0.05,
        "G2_both_halves": p["half1"]["mean_excess"] > 0 and p["half2"]["mean_excess"] > 0,
        "G3_beats_spy": (o["full"]["cagr"] > s["full"]["cagr"]
                         and o["half1"]["cagr"] > s["half1"]["cagr"]
                         and o["half2"]["cagr"] > s["half2"]["cagr"]
                         and o["full"]["max_drawdown"] > s["full"]["max_drawdown"]),
        "G4_double_costs": d["full"]["sharpe"] >= 0.30 and d["full"]["mean_excess"] > 0,
    }
    if not (gates["G1_edge"] and gates["G2_both_halves"]):
        verdict = "REJECTED"
    elif gates["G3_beats_spy"] and gates["G4_double_costs"]:
        verdict = "NOT REJECTED"
    else:
        verdict = "WEAK"
    return {"verdict": verdict, "gates": gates}

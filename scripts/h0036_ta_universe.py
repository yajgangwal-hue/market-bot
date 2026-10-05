"""H-0036 engine: the full universe of 7,846 technical trading rules from
Sullivan, Timmermann & White (1999, "Data-Snooping, Technical Trading Rule
Performance, and the Bootstrap", Appendix A), run on SPY 5-minute bars as day
trades, with White's (2000) Reality Check and Hansen's (2005) test for
Superior Predictive Ability correcting for the search across all of them.

Marshall, Cahan & Cahan (2008) ran this universe on SPY 5-minute bars for
2002-2003, replacing "days" with 5-minute bars, and found no rule profitable
after the correction. This runs it on 2016-2026.

The universe (Appendix A of the paper, "days" read as 5-minute bars):
  filter rules        x, y, e, c                                         497
  moving averages     n, fast/slow pairs, band b, delay d, hold c, +9 BLL 2,049
  support/resistance  n or e extrema, band b, delay d, hold c          1,220
  channel break-outs  n, width x, band b, hold c                       2,040
  on-balance volume   the moving-average rules on OBV                  2,040

Day trading. Indicators run on the continuous series of 5-minute closes
(complete sessions only, in order). A rule's state at a bar's close sets its
position over the next bar's return inside the same session; every position is
closed at 16:00 and, if the rule still says so, reopened at the next session's
first close. P&L is per unit of notional: no overnight return is ever earned.
Each position change, the 16:00 exit and the next morning's re-entry pay the
per-share cost, as a fraction of price.

Interpretations where the paper leaves a choice (fixed here, before any result):
  - a band b leaves the position neutral while the signal sits inside the band;
  - a delay d switches the position only after the raw signal has held d bars;
  - a hold c takes a signal, holds it c bars ignoring other signals, then goes
    neutral until the next signal; crossings (moving averages, OBV) and
    breakout bars (support/resistance, channels) are the signals;
  - filter rules start neutral; a filter with hold c takes the standard x
    filter's switches as its signals;
  - local extrema with e: the most recent close, before the current bar, that
    is above (below) each of the e closes before it;
  - OBV bands are additive in |slow|, since OBV can be negative.
"""

import math
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

BARS = 78

FILTER_X = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05, 0.06, 0.07,
            0.08, 0.09, 0.1, 0.12, 0.14, 0.16, 0.18, 0.2, 0.25, 0.3, 0.4, 0.5]
FILTER_Y = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.075, 0.1, 0.15, 0.2]
FILTER_E = [1, 2, 3, 4, 5, 10, 15, 20]
HOLD_C = [5, 10, 25, 50]
MA_N = [2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 200, 250]
BAND_B = [0.001, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.05]
DELAY_D = [2, 3, 4, 5]
SR_N = [5, 10, 15, 20, 25, 50, 100, 150, 200, 250]
SR_E = [2, 3, 4, 5, 10, 20, 25, 50, 100, 200]
CH_N = [5, 10, 15, 20, 25, 50, 100, 150, 200, 250]
CH_X = [0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15]
FAMILY_COUNTS = {"filter": 497, "ma": 2049, "sr": 1220, "channel": 2040, "obv": 2040}


def universe() -> List[Tuple]:
    """Every rule as a tuple: (family, kind, *parameters). 7,846 in all."""
    rules: List[Tuple] = []
    rules += [("filter", "x", x) for x in FILTER_X]
    rules += [("filter", "xe", x, e) for x in FILTER_X for e in FILTER_E]
    rules += [("filter", "xc", x, c) for x in FILTER_X for c in HOLD_C]
    rules += [("filter", "xy", x, y) for x in FILTER_X for y in FILTER_Y if y < x]
    for family in ("ma", "obv"):
        bases = [("single", n) for n in MA_N] + [("pair", f, s) for i, f in enumerate(MA_N)
                                                for s in MA_N[i + 1:]]
        rules += [(family, "plain", base) for base in bases]
        rules += [(family, "band", base, b) for base in bases for b in BAND_B]
        rules += [(family, "delay", base, d) for base in bases for d in DELAY_D]
        rules += [(family, "hold", base, c) for base in bases for c in HOLD_C]
        if family == "ma":                       # the nine Brock-Lakonishok-LeBaron rules
            rules += [("ma", "bll", (("single", s) if f == 1 else ("pair", f, s)), 0.01, 10)
                      for f in (1, 2, 5) for s in (50, 150, 200)]
    levels = [("n", n) for n in SR_N] + [("e", e) for e in SR_E]
    for level in levels:
        for c in [None] + HOLD_C:
            rules.append(("sr", "plain", level, 0.0, c))
            rules += [("sr", "band", level, b, c) for b in BAND_B]
        rules += [("sr", "delay", level, d, c) for d in DELAY_D for c in HOLD_C]
    for n in CH_N:
        for x in CH_X:
            rules += [("channel", "plain", n, x, 0.0, c) for c in HOLD_C]
            rules += [("channel", "band", n, x, b, c) for b in BAND_B if b < x for c in HOLD_C]
    counts: Dict[str, int] = {}
    for r in rules:
        counts[r[0]] = counts.get(r[0], 0) + 1
    assert counts == FAMILY_COUNTS, counts
    return rules


def label(rule: Tuple) -> str:
    return " ".join(str(p) for p in rule)


# ---------------------------------------------------------------- building blocks

def _ffill_state(signal: np.ndarray) -> np.ndarray:
    """Carry the last non-zero signal forward; zero before the first."""
    idx = np.where(signal != 0, np.arange(signal.size), -1)
    np.maximum.accumulate(idx, out=idx)
    out = np.where(idx >= 0, signal[np.maximum(idx, 0)], 0)
    return out.astype(np.int8)


def _hold(events: np.ndarray, c: int) -> np.ndarray:
    """Take each signal not inside a running hold; hold it c bars; then neutral."""
    pos = np.zeros(events.size, dtype=np.int8)
    idx = np.flatnonzero(events)
    j = 0
    while j < idx.size:
        i = idx[j]
        pos[i:i + c] = events[i]
        j = int(np.searchsorted(idx, i + c, side="left"))
    return pos


def _run_length(state: np.ndarray) -> np.ndarray:
    """Length of the current run of equal values, ending at each bar."""
    change = np.ones(state.size, dtype=bool)
    change[1:] = state[1:] != state[:-1]
    starts = np.maximum.accumulate(np.where(change, np.arange(state.size), 0))
    return np.arange(state.size) - starts + 1


def _delay(state: np.ndarray, d: int) -> np.ndarray:
    """Switch to the raw state only once it has held d bars."""
    acted = np.where((_run_length(state) >= d) & (state != 0), state, 0).astype(np.int8)
    return _ffill_state(acted)


def _crossings(state: np.ndarray) -> np.ndarray:
    """+1/-1 on the bar the raw state turns positive/negative."""
    ev = np.zeros(state.size, dtype=np.int8)
    turned = np.zeros(state.size, dtype=bool)
    turned[1:] = state[1:] != state[:-1]
    ev[turned & (state != 0)] = state[turned & (state != 0)]
    return ev


class Series:
    """The continuous 5-minute close and volume series of complete sessions."""

    def __init__(self, sessions: Dict, cost_per_share: float):
        days = [d for d in sorted(sessions) if len(sessions[d]) == BARS]
        self.days = days
        self.close = np.array([b["c"] for d in days for b in sessions[d]], dtype=np.float64)
        self.volume = np.array([b["v"] for d in days for b in sessions[d]], dtype=np.float64)
        self.n_sessions = len(days)
        c2 = self.close.reshape(self.n_sessions, BARS)
        self.ret2 = np.zeros_like(c2)
        self.ret2[:, 1:] = c2[:, 1:] / c2[:, :-1] - 1.0
        self.cost2 = cost_per_share / c2
        s = pd.Series(self.close)
        self._ma: Dict[int, np.ndarray] = {n: s.rolling(n).mean().to_numpy() for n in MA_N}
        step = np.sign(np.diff(self.close, prepend=self.close[0]))
        self.obv = np.cumsum(step * self.volume)
        o = pd.Series(self.obv)
        self._obv_ma: Dict[int, np.ndarray] = {n: o.rolling(n).mean().to_numpy() for n in MA_N}
        self._s = s
        self._extremes: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        self._local: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}

    def extremes(self, n: int) -> Tuple[np.ndarray, np.ndarray]:
        """Highest and lowest close of the previous n bars, the current bar excluded."""
        if n not in self._extremes:
            self._extremes[n] = (self._s.rolling(n).max().shift(1).to_numpy(),
                                 self._s.rolling(n).min().shift(1).to_numpy())
        return self._extremes[n]

    def local(self, e: int) -> Tuple[np.ndarray, np.ndarray]:
        """The most recent close before the bar that was above (below) each of
        the e closes before it."""
        if e not in self._local:
            s = self._s
            prev_max = s.rolling(e).max().shift(1)
            prev_min = s.rolling(e).min().shift(1)
            self._local[e] = (s.where(s > prev_max).ffill().shift(1).to_numpy(),
                              s.where(s < prev_min).ffill().shift(1).to_numpy())
        return self._local[e]

    # ------------------------------------------------------------ indicator states
    def _pair(self, family: str, base: Tuple):
        ma = self._ma if family == "ma" else self._obv_ma
        level = self.close if family == "ma" else self.obv
        if base[0] == "single":
            return level, ma[base[1]]
        return ma[base[1]], ma[base[2]]

    @staticmethod
    def _sign(fast, slow, band: float, additive: bool) -> np.ndarray:
        with np.errstate(invalid="ignore"):
            if band == 0.0:
                st = np.where(fast > slow, 1, np.where(fast < slow, -1, 0))
            elif additive:
                st = np.where(fast > slow + band * np.abs(slow), 1,
                              np.where(fast < slow - band * np.abs(slow), -1, 0))
            else:
                st = np.where(fast > slow * (1 + band), 1, np.where(fast < slow * (1 - band), -1, 0))
        st[np.isnan(fast) | np.isnan(slow)] = 0
        return st.astype(np.int8)

    def _ma_position(self, rule: Tuple) -> np.ndarray:
        family, kind, base = rule[0], rule[1], rule[2]
        fast, slow = self._pair(family, base)
        additive = family == "obv"
        if kind == "plain":
            return _ffill_state(self._sign(fast, slow, 0.0, additive))
        if kind == "band":
            return self._sign(fast, slow, rule[3], additive)
        if kind == "delay":
            return _delay(self._sign(fast, slow, 0.0, additive), rule[3])
        if kind == "hold":
            return _hold(_crossings(self._sign(fast, slow, 0.0, additive)), rule[3])
        if kind == "bll":                                    # band 1% and a 10-bar hold
            return _hold(_crossings(self._sign(fast, slow, rule[3], additive)), rule[4])
        raise ValueError(rule)

    def _sr_position(self, rule: Tuple) -> np.ndarray:
        _, kind, level, param, c = rule
        hi, lo = self.extremes(level[1]) if level[0] == "n" else self.local(level[1])
        band = param if kind == "band" else 0.0
        with np.errstate(invalid="ignore"):
            up = self.close > hi * (1 + band)
            down = self.close < lo * (1 - band)
        events = np.where(up & ~down, 1, np.where(down & ~up, -1, 0)).astype(np.int8)
        if kind == "delay":                                  # the break must hold d bars
            d = param
            run_up = _run_length(up.astype(np.int8)) * up
            run_down = _run_length(down.astype(np.int8)) * down
            events = np.where(run_up == d, 1, np.where(run_down == d, -1, 0)).astype(np.int8)
        if c is None:
            return _ffill_state(events)
        return _hold(events, c)

    def _channel_position(self, rule: Tuple) -> np.ndarray:
        _, _, n, x, band, c = rule
        hi, lo = self.extremes(n)
        with np.errstate(invalid="ignore"):
            channel = hi <= lo * (1 + x)
            up = channel & (self.close > hi * (1 + band))
            down = channel & (self.close < lo * (1 - band))
        events = np.where(up, 1, np.where(down, -1, 0)).astype(np.int8)
        return _hold(events, c)

    def _filter_states(self, x: float, y: float = None) -> np.ndarray:
        """The classic x% filter (and the x/y filter with a neutral state),
        tracking the extreme close since the last switch."""
        close = self.close.tolist()
        out = np.zeros(len(close), dtype=np.int8)
        pos, hi, lo = 0, close[0], close[0]
        up, down = 1.0 + x, 1.0 - x
        yu, yd = (1.0 + y, 1.0 - y) if y is not None else (None, None)
        for i, p in enumerate(close):
            if pos == 1:
                if p > hi:
                    hi = p
                if p <= hi * down:
                    pos, lo = -1, p
                elif yd is not None and p <= hi * yd:
                    pos, lo, hi = 0, p, p
            elif pos == -1:
                if p < lo:
                    lo = p
                if p >= lo * up:
                    pos, hi = 1, p
                elif yu is not None and p >= lo * yu:
                    pos, lo, hi = 0, p, p
            else:
                if p > hi:
                    hi = p
                if p < lo:
                    lo = p
                if p >= lo * up:
                    pos, hi = 1, p
                elif p <= hi * down:
                    pos, lo = -1, p
            out[i] = pos
        return out

    def position(self, rule: Tuple, cache: Dict) -> np.ndarray:
        family, kind = rule[0], rule[1]
        if family == "filter":
            x = rule[2]
            if kind in ("x", "xc"):
                key = ("filter_x", x)
                if key not in cache:
                    cache[key] = self._filter_states(x)
                base = cache[key]
                return base if kind == "x" else _hold(_crossings(base), rule[3])
            if kind == "xy":
                return self._filter_states(x, rule[3])
            hi, lo = self.local(rule[3])                      # kind "xe"
            with np.errstate(invalid="ignore"):
                long_ = self.close >= lo * (1 + x)
                short = self.close <= hi * (1 - x)
            return _ffill_state(np.where(long_ & ~short, 1, np.where(short & ~long_, -1, 0)).astype(np.int8))
        if family in ("ma", "obv"):
            return self._ma_position(rule)
        if family == "sr":
            return self._sr_position(rule)
        return self._channel_position(rule)

    def daily(self, pos: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """(gross, net) return per session for a unit position series, flat at
        every close: no overnight return, a cost on every change, on the 16:00
        exit and on the next morning's re-entry."""
        p = pos.reshape(self.n_sessions, BARS).astype(np.float64)
        gross = (p[:, :BARS - 1] * self.ret2[:, 1:]).sum(axis=1)
        cost = (np.abs(p[:, 0]) * self.cost2[:, 0]
                + (np.abs(np.diff(p[:, :BARS - 1], axis=1)) * self.cost2[:, 1:BARS - 1]).sum(axis=1)
                + np.abs(p[:, BARS - 2]) * self.cost2[:, BARS - 1])
        return gross, gross - cost


def run_universe(series: Series, rules: List[Tuple]) -> Tuple[np.ndarray, np.ndarray]:
    """Gross and net daily returns, rules x sessions (float64)."""
    gross = np.zeros((len(rules), series.n_sessions))
    net = np.zeros((len(rules), series.n_sessions))
    cache: Dict = {}
    for k, rule in enumerate(rules):
        g, n = series.daily(series.position(rule, cache))
        gross[k], net[k] = g, n
    return gross, net


# ---------------------------------------------------------------- data-snooping tests

def stationary_indices(n: int, q: float, rng: np.random.Generator) -> np.ndarray:
    """Politis & Romano (1994): blocks of geometric length, mean 1/q, wrapping."""
    new = rng.random(n) < q
    new[0] = True
    starts = np.flatnonzero(new)
    block = np.cumsum(new) - 1
    first = rng.integers(0, n, starts.size)
    return (first[block] + np.arange(n) - starts[block]) % n


def reality_check_and_spa(d: np.ndarray, n_boot: int = 1000, q: float = 0.1,
                          seed: int = 20261004) -> Dict[str, object]:
    """White's Reality Check and Hansen's SPA (consistent) for the best of the
    rules in d (rules x sessions, performance relative to a zero benchmark).
    Rules that never trade are excluded."""
    keep = d.std(axis=1) > 0
    d = d[keep]
    k, n = d.shape
    mean = d.mean(axis=1)
    rng = np.random.default_rng(seed)
    boot = np.empty((n_boot, k))
    for b in range(n_boot):
        counts = np.bincount(stationary_indices(n, q, rng), minlength=n).astype(np.float64)
        boot[b] = d @ counts / n
    root_n = math.sqrt(n)
    omega = np.sqrt(((root_n * (boot - mean)) ** 2).mean(axis=0))
    v = root_n * mean.max()
    v_star = (root_n * (boot - mean)).max(axis=1)
    p_rc = float((v_star >= v).mean())
    t = max(0.0, float((root_n * mean / omega).max()))
    threshold = -np.sqrt(omega ** 2 / n * 2 * math.log(math.log(n)))
    g = np.where(mean >= threshold, mean, 0.0)
    t_star = np.maximum(0.0, (root_n * (boot - g) / omega).max(axis=1))
    p_spa = float((t_star >= t).mean())
    best = int(np.argmax(mean))
    return {"rules_tested": int(k), "rules_never_trading": int((~keep).sum()),
            "best_index_among_tested": best, "best_mean": float(mean[best]),
            "best_t_naive": float(mean[best] / (d[best].std(ddof=1) / math.sqrt(n))),
            "reality_check_p": p_rc, "spa_p": p_spa, "spa_statistic": t,
            "positive_rules": int((mean > 0).sum()), "n_boot": n_boot, "q": q,
            "kept_mask": keep}

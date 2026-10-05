"""H-0039 engine and verdict, on hand-built and synthetic data.

Every arithmetic step the sealed run relies on is checked against a value
worked out by hand, and the whole evaluation - including the verdict step
that stopped H-0037 - runs end to end on a synthetic panel before the
registered run is allowed to.
"""

import json
import math
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import h0039_trend as engine                                          # noqa: E402
import run_h0039 as runner                                            # noqa: E402

SYMBOLS = list(engine.MARKETS)


def stamp(day):
    return int(datetime(day.year, day.month, day.day, 13, 30, tzinfo=timezone.utc).timestamp())


def payload(days, values):
    return json.dumps({"chart": {"result": [{
        "timestamp": [stamp(d) for d in days],
        "indicators": {"adjclose": [{"adjclose": values}], "quote": [{"close": values}]}}],
        "error": None}}).encode("utf-8")


def sessions(start, count):
    out, day = [], start
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


class ParsePayload(unittest.TestCase):
    def test_reads_dates_and_skips_empty_bars(self):
        days = [date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 6)]
        got = engine.parse_payload(payload(days, [10.0, None, 11.0]))
        self.assertEqual(got, {date(2020, 1, 2): 10.0, date(2020, 1, 6): 11.0})

    def test_skips_non_positive_values(self):
        days = [date(2020, 1, 2), date(2020, 1, 3)]
        self.assertEqual(engine.parse_payload(payload(days, [0.0, 5.0])), {date(2020, 1, 3): 5.0})


class BuildPanel(unittest.TestCase):
    def test_calendar_starts_with_the_youngest_market_and_rf_lags_one_session(self):
        d = [date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 6), date(2020, 1, 7)]
        closes = {"A": {d[0]: 100.0, d[1]: 101.0, d[2]: 102.01, d[3]: 100.0},
                  "B": {d[1]: 50.0, d[2]: 55.0, d[3]: 55.0}}
        irx = {d[1]: 2.52, d[3]: 5.04}             # missing on d[2]: carried forward
        dates, symbols, returns, rf = engine.build_panel(closes, irx, end=date(2020, 1, 31))
        self.assertEqual(dates, [d[2], d[3]])
        self.assertEqual(symbols, ["A", "B"])
        np.testing.assert_allclose(returns, [[0.01, 0.10], [100.0 / 102.01 - 1.0, 0.0]])
        # rf for d[2] is d[1]'s yield; for d[3] it is d[2]'s, i.e. d[1]'s carried forward.
        np.testing.assert_allclose(rf, [2.52 / 100 / 252, 2.52 / 100 / 252])

    def test_end_date_is_inclusive(self):
        d = [date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 6)]
        closes = {"A": {x: 1.0 + i for i, x in enumerate(d)}}
        dates, _, _, _ = engine.build_panel(closes, {d[0]: 1.0}, end=d[1])
        self.assertEqual(dates, [d[1]])


class Signals(unittest.TestCase):
    def test_signs_of_the_three_lookbacks(self):
        n = 300
        returns = np.zeros((n, 4))
        returns[:, 0] = 0.001                        # up throughout
        returns[:, 1] = -0.001                       # down throughout
        returns[:, 2] = 0.002                        # up for a year...
        returns[-21:, 2] = -0.003                    # ...down the last month, still up over 3
        returns[:, 3] = 0.0001                       # exactly the bill rate
        rf = np.full(n, 0.0001)
        s = engine.trailing_signals(returns, rf, n - 1)
        np.testing.assert_allclose(s, [1.0, -1.0, 1.0 / 3.0, 0.0], atol=1e-12)

    def test_uses_rows_through_t_only(self):
        returns = np.full((300, 1), 0.001)
        returns[260:] = -0.05                        # a crash AFTER t = 259
        s = engine.trailing_signals(returns, np.zeros(300), 259)
        self.assertEqual(float(s[0]), 1.0)


class Volatility(unittest.TestCase):
    def test_recovers_a_known_volatility(self):
        rng = np.random.default_rng(1)
        x = rng.normal(0.0, 0.01, size=(4000, 1))
        vols = engine.ewma_vols(x)
        self.assertTrue(np.isnan(vols[58, 0]))
        self.assertAlmostEqual(float(np.nanmean(vols[1000:, 0])), 0.01 * math.sqrt(252), delta=0.01)

    def test_row_t_ignores_later_rows(self):
        rng = np.random.default_rng(2)
        x = rng.normal(0.0, 0.01, size=(300, 2))
        y = x.copy()
        y[200:] *= 10
        np.testing.assert_allclose(engine.ewma_vols(x)[199], engine.ewma_vols(y)[199])


class Weights(unittest.TestCase):
    def test_equal_risk_then_scaled_to_the_target(self):
        vol = np.array([0.10, 0.20])
        w = engine.target_weights(np.array([1.0, -1.0]), vol, np.eye(2), target=0.10, cap=10.0)
        # raw (10, -5); ex-ante sqrt(100*0.01 + 25*0.04) = sqrt(2)
        np.testing.assert_allclose(w, [10 * 0.10 / math.sqrt(2), -5 * 0.10 / math.sqrt(2)])
        cov = np.outer(vol, vol)
        np.fill_diagonal(cov, vol ** 2)
        cov[0, 1] = cov[1, 0] = 0.0
        self.assertAlmostEqual(math.sqrt(float(w @ cov @ w)), 0.10)

    def test_correlation_enters_the_scaling(self):
        vol = np.array([0.10, 0.10])
        corr = np.array([[1.0, 0.5], [0.5, 1.0]])
        w = engine.target_weights(np.array([1.0, 1.0]), vol, corr, target=0.10, cap=10.0)
        self.assertAlmostEqual(math.sqrt(float(w @ (np.outer(vol, vol) * corr) @ w)), 0.10)

    def test_gross_cap(self):
        w = engine.target_weights(np.array([1.0, 1.0]), np.array([0.01, 0.01]), np.eye(2),
                                  target=0.10, cap=4.0)
        self.assertAlmostEqual(float(np.abs(w).sum()), 4.0)

    def test_no_signal_no_position(self):
        w = engine.target_weights(np.zeros(3), np.array([0.1, 0.2, 0.3]), np.eye(3))
        self.assertEqual(float(np.abs(w).sum()), 0.0)


class DecisionRows(unittest.TestCase):
    def test_last_session_of_each_month_with_a_next_session(self):
        d = [date(2020, 1, 30), date(2020, 1, 31), date(2020, 2, 3), date(2020, 2, 28),
             date(2020, 3, 2), date(2020, 3, 31)]
        self.assertEqual(engine.decision_rows(d, "monthly"), [1, 3])

    def test_weekly(self):
        d = [date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 6), date(2020, 1, 10),
             date(2020, 1, 13)]
        self.assertEqual(engine.decision_rows(d, "weekly"), [1, 3])


def flat_panel(n=400, start=date(2010, 1, 4)):
    dates = sessions(start, n)
    returns = np.zeros((n, len(SYMBOLS)))
    rf = np.full(n, 0.0001)
    return dates, returns, rf


class Run(unittest.TestCase):
    def test_execution_lags_the_decision_by_one_session_and_costs_are_charged(self):
        dates, returns, rf = flat_panel()
        rng = np.random.default_rng(3)
        returns[:] = rf[:, None] + rng.normal(0.0, 0.01, size=returns.shape)
        spy = SYMBOLS.index("SPY")
        returns[:, spy] += 0.002                     # a clear up-trend in one market
        out = engine.run(dates, SYMBOLS, returns, rf)
        start = engine.first_decision_row(dates)
        self.assertEqual(out["first_execution"], dates[start + 1])
        # Execution row: nothing was held coming in, so the account earns the bill
        # return less the cost of building the book.
        self.assertAlmostEqual(out["account"][0], rf[start + 1] - out["costs"][0])
        side = np.array([engine.MARKETS[s][2] for s in SYMBOLS])
        self.assertGreater(out["costs"][0], 0.0)
        self.assertAlmostEqual(out["turnover"][0], out["gross"][0])
        # The next row earns the book: P&L = w . (r - rf) - roll cost.
        excess = returns - rf[:, None]
        w = engine.target_weights(engine.trailing_signals(returns, rf, start),
                                  engine.ewma_vols(excess)[start],
                                  engine.trailing_correlation(excess, start))
        self.assertAlmostEqual(out["costs"][0], float(np.abs(w) @ side))
        roll = float(np.abs(w) @ (2 * side * np.array([engine.MARKETS[s][3] for s in SYMBOLS]))) / 252
        expected = rf[start + 2] + float(w @ excess[start + 2]) - roll
        self.assertAlmostEqual(out["account"][1], expected)
        self.assertGreater(w[spy], 0.0)

    def test_double_costs_cost_more(self):
        dates, returns, rf = flat_panel()
        rng = np.random.default_rng(4)
        returns[:] = rng.normal(0.0002, 0.01, size=returns.shape)
        one = engine.run(dates, SYMBOLS, returns, rf)
        two = engine.run(dates, SYMBOLS, returns, rf, cost_multiplier=2.0)
        self.assertGreater(two["costs"].sum(), one["costs"].sum())
        self.assertLess(np.prod(1 + two["account"]), np.prod(1 + one["account"]))

    def test_weekly_variant_starts_at_the_same_decision(self):
        dates, returns, rf = flat_panel()
        rng = np.random.default_rng(5)
        returns[:] = rng.normal(0.0002, 0.01, size=returns.shape)
        monthly = engine.run(dates, SYMBOLS, returns, rf)
        weekly = engine.run(dates, SYMBOLS, returns, rf, frequency="weekly")
        self.assertEqual(monthly["dates"], weekly["dates"])
        self.assertAlmostEqual(monthly["gross"][0], weekly["gross"][0])


class Overlay(unittest.TestCase):
    def test_arithmetic(self):
        got = engine.overlay(np.array([0.01, -0.02]), np.array([0.0001, 0.0001]),
                             np.array([0.002, 0.003]))
        np.testing.assert_allclose(got, [0.8 * 0.01 + 0.2 * 0.0001 + 0.002,
                                         0.8 * -0.02 + 0.2 * 0.0001 + 0.003])


class Metrics(unittest.TestCase):
    def test_known_series(self):
        days = sessions(date(2020, 1, 2), 252)
        r = np.full(252, 0.001)
        m = engine.metrics(r, np.zeros(252), days)
        self.assertAlmostEqual(m["total_return"], 1.001 ** 252 - 1)
        self.assertAlmostEqual(m["cagr"], 1.001 ** 252 - 1)
        self.assertEqual(m["max_drawdown"], 0.0)

    def test_drawdown_and_years(self):
        days = [date(2020, 12, 30), date(2020, 12, 31), date(2021, 1, 4)]
        m = engine.metrics(np.array([0.10, -0.50, 0.20]), np.zeros(3), days)
        self.assertAlmostEqual(m["max_drawdown"], -0.5)
        self.assertAlmostEqual(m["by_year"]["2020"], 1.1 * 0.5 - 1)
        self.assertAlmostEqual(m["by_year"]["2021"], 0.2)

    def test_first_session_loss_counts_as_drawdown(self):
        days = sessions(date(2020, 1, 2), 2)
        m = engine.metrics(np.array([-0.1, 0.05]), np.zeros(2), days)
        self.assertAlmostEqual(m["max_drawdown"], -0.1)


class Bootstrap(unittest.TestCase):
    def test_clear_positive_mean(self):
        x = np.random.default_rng(6).normal(0.002, 0.01, 2000)
        self.assertLess(engine.stationary_bootstrap_p(x, resamples=2000), 0.01)

    def test_zero_mean_is_not_significant(self):
        x = np.random.default_rng(7).normal(0.0, 0.01, 1000)
        x = np.concatenate([x, -x])                  # mean exactly zero
        p = engine.stationary_bootstrap_p(x, resamples=2000)
        self.assertGreater(p, 0.3)

    def test_deterministic(self):
        x = np.random.default_rng(8).normal(0.0005, 0.01, 500)
        self.assertEqual(engine.stationary_bootstrap_p(x, resamples=500),
                         engine.stationary_bootstrap_p(x, resamples=500))


def block(cagr=0.10, sharpe=0.5, mean_excess=0.05, max_drawdown=-0.2):
    return {"cagr": cagr, "sharpe": sharpe, "mean_excess": mean_excess,
            "max_drawdown": max_drawdown}


def results(p_sharpe=0.5, p_value=0.01, half1=0.05, half2=0.05, o_cagr=(0.12, 0.12, 0.12),
            s_cagr=(0.10, 0.10, 0.10), o_dd=-0.20, s_dd=-0.30, d_sharpe=0.4, d_mean=0.03):
    return {
        "primary": {"full": block(sharpe=p_sharpe), "half1": block(mean_excess=half1),
                    "half2": block(mean_excess=half2), "bootstrap_p": p_value},
        "double_cost": {"full": block(sharpe=d_sharpe, mean_excess=d_mean)},
        "overlay": {"full": block(cagr=o_cagr[0], max_drawdown=o_dd), "half1": block(cagr=o_cagr[1]),
                    "half2": block(cagr=o_cagr[2])},
        "spy": {"full": block(cagr=s_cagr[0], max_drawdown=s_dd), "half1": block(cagr=s_cagr[1]),
                "half2": block(cagr=s_cagr[2])},
    }


class Decide(unittest.TestCase):
    def test_not_rejected_when_every_gate_holds(self):
        got = engine.decide(results())
        self.assertEqual(got["verdict"], "NOT REJECTED")
        self.assertTrue(all(got["gates"].values()))

    def test_rejected_without_an_edge(self):
        self.assertEqual(engine.decide(results(p_sharpe=0.29))["verdict"], "REJECTED")
        self.assertEqual(engine.decide(results(p_value=0.051))["verdict"], "REJECTED")

    def test_rejected_when_a_half_loses(self):
        self.assertEqual(engine.decide(results(half2=-0.001))["verdict"], "REJECTED")
        self.assertEqual(engine.decide(results(half1=0.0))["verdict"], "REJECTED")

    def test_weak_without_a_spy_relative_case(self):
        self.assertEqual(engine.decide(results(o_cagr=(0.12, 0.12, 0.09)))["verdict"], "WEAK")
        self.assertEqual(engine.decide(results(o_cagr=(0.09, 0.12, 0.12)))["verdict"], "WEAK")
        self.assertEqual(engine.decide(results(o_dd=-0.35))["verdict"], "WEAK")
        self.assertEqual(engine.decide(results(o_dd=-0.30))["verdict"], "WEAK")  # equal: not shallower

    def test_weak_when_double_costs_break_it(self):
        self.assertEqual(engine.decide(results(d_sharpe=0.29))["verdict"], "WEAK")
        self.assertEqual(engine.decide(results(d_mean=-0.01))["verdict"], "WEAK")

    def test_boundaries_pass(self):
        self.assertEqual(engine.decide(results(p_sharpe=0.30, p_value=0.05, d_sharpe=0.30))["verdict"],
                         "NOT REJECTED")


class EvaluateEndToEnd(unittest.TestCase):
    """The runner's whole evaluation on a synthetic panel: every block the
    verdict reads exists, so the sealed run cannot stop in its verdict step."""

    def test_runs_and_decides(self):
        n = 700
        dates = sessions(date(2009, 1, 5), n)
        rng = np.random.default_rng(9)
        rf = np.full(n, 0.0001)
        returns = rng.normal(0.0003, 0.01, size=(n, len(SYMBOLS)))
        got = runner.evaluate(dates, SYMBOLS, returns, rf, split=date(2010, 6, 1), resamples=200,
                              seed=1)
        self.assertIn(got["decision"]["verdict"], ("REJECTED", "WEAK", "NOT REJECTED"))
        for key in ("primary", "double_cost", "overlay", "spy"):
            for part in ("full", "half1", "half2"):
                self.assertIn("cagr", got[key][part])
        self.assertEqual(got["window"]["sessions"], got["primary"]["full"]["sessions"])
        self.assertEqual(got["spy"]["full"]["first"], got["primary"]["full"]["first"])
        self.assertEqual(set(got["descriptive"]["pnl_by_class_per_year"]),
                         {"equity", "rates", "metals", "energy", "agriculture", "currency"})
        self.assertEqual(set(got["data_quality"]["by_symbol"]), set(SYMBOLS))
        # SPY's block is SPY's own total return over the evaluated sessions.
        first = n - got["window"]["sessions"]
        spy = returns[first:, SYMBOLS.index("SPY")]
        self.assertAlmostEqual(got["spy"]["full"]["total_return"], float(np.prod(1 + spy) - 1))


if __name__ == "__main__":
    unittest.main()

"""Adaptive volatility exits (EXP-0055): the levels, the replay, and the learner.

The learner's tests use a rule whose bounce exit can never fire (rsi_exit
1000), so the replay is decided by the target, the stop and the holding cap
alone. That isolates the thing being learned.
"""

import json
import math
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from event_aware_trader.adaptive_exits import (
    AdaptiveExitConfig, current_levels, learn, logged_entries, params_path,
    r_multiple, replay)
from event_aware_trader.data import save_bars
from event_aware_trader.mean_reversion import MeanReversionConfig
from event_aware_trader.types import Bar

CONFIG = AdaptiveExitConfig()
NO_BOUNCE = SimpleNamespace(max_holding_bars=20, rsi_period=14, rsi_exit=1000.0,
                            stop_atr_multiple=2.5)
START = datetime(2026, 9, 14, 4, tzinfo=timezone.utc)


def bar(day, o, h, l, c):
    return Bar(timestamp=START + timedelta(days=day), open=o, high=h, low=l, close=c,
               volume=1_000_000)


def flat(days, price=100.0, first_day=0):
    return [bar(first_day + i, price, price + 0.1, price - 0.1, price) for i in range(days)]


class Levels(unittest.TestCase):
    def test_no_file_means_the_initial_levels(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(current_levels(CONFIG, Path(tmp) / "missing.json"), (2.5, 2.5))

    def test_a_learned_file_is_read_and_kept_inside_the_bounds(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "adaptive-exits.json"
            path.write_text(json.dumps({"take_profit_atr": 3.5, "stop_atr": 2.75}), encoding="utf-8")
            self.assertEqual(current_levels(CONFIG, path), (3.5, 2.75))
            path.write_text(json.dumps({"take_profit_atr": 40.0, "stop_atr": 0.1}), encoding="utf-8")
            self.assertEqual(current_levels(CONFIG, path), (6.0, 2.0))

    def test_a_damaged_file_falls_back_to_the_initial_levels(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "adaptive-exits.json"
            for body in ("not json", "[1, 2]", json.dumps({"take_profit_atr": "x", "stop_atr": 2}),
                         '{"take_profit_atr": NaN, "stop_atr": 2.5}'):
                path.write_text(body, encoding="utf-8")
                self.assertEqual(current_levels(CONFIG, path), (2.5, 2.5), body)

    def test_the_file_lives_beside_the_state_file(self):
        self.assertEqual(params_path(Path("x") / "state.json"), Path("x") / "adaptive-exits.json")


class Replay(unittest.TestCase):
    """Entry 100, ATR 2: stop 95 at 2.5 ATR, target 105 at 2.5 ATR."""

    def run_it(self, after, take=2.5, stop=2.5, rule=NO_BOUNCE):
        return replay(after, [100.0] * 30, 100.0, 2.0, take, stop, rule)

    def test_the_target_fills_at_its_level(self):
        after = [bar(1, 101, 106, 100.5, 103)] + flat(19)
        self.assertEqual(self.run_it(after), (105.0, "take_profit"))

    def test_the_stop_fills_at_its_level(self):
        after = [bar(1, 99, 99.5, 94, 96)] + flat(19)
        self.assertEqual(self.run_it(after), (95.0, "stop"))

    def test_a_bar_reaching_both_goes_to_the_stop(self):
        after = [bar(1, 100, 106, 94, 100)] + flat(19)
        self.assertEqual(self.run_it(after), (95.0, "stop"))

    def test_gaps_fill_at_the_open(self):
        self.assertEqual(self.run_it([bar(1, 93, 94, 92, 93)] + flat(19)), (93.0, "stop"))
        self.assertEqual(self.run_it([bar(1, 107, 108, 106, 107)] + flat(19)), (107.0, "take_profit"))

    def test_the_holding_cap_closes_at_the_last_close(self):
        after = flat(19) + [bar(20, 101, 101.5, 100.5, 101.2)]
        self.assertEqual(self.run_it(after), (101.2, "time"))

    def test_the_bounce_exit_uses_the_real_rsi(self):
        # A long fall then a sharp recovery: RSI(14) crosses 60 before either level.
        history = [100.0 + 0.5 * (40 - i) for i in range(40)]
        after = [bar(i, history[-1] + i, history[-1] + i + 0.2, history[-1] + i - 0.2,
                     history[-1] + i) for i in range(1, 21)]
        price, reason = replay(after, history, history[-1], 10.0, 2.5, 2.5, MeanReversionConfig())
        self.assertEqual(reason, "reverted")

    def test_an_unfinished_trade_is_not_replayed(self):
        self.assertIsNone(self.run_it(flat(19)))

    def test_r_multiple_charges_the_cost_once(self):
        self.assertAlmostEqual(r_multiple(105.0, 100.0, 2.0, 2.5, 0.0), 1.0)
        self.assertAlmostEqual(r_multiple(105.0, 100.0, 2.0, 2.5, 0.0012), (5.0 - 0.12) / 5.0)


def write_entries(path, entries):
    rows = [{"at": "{0}T19:45:00+00:00".format(day), "event": "entry",
             "detail": dict({"symbol": symbol, "entry_reference": price, "stop": stop}, **extra)}
            for symbol, day, price, stop, extra in entries]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class Entries(unittest.TestCase):
    def test_the_atr_is_recovered_from_the_logged_stop(self):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            write_entries(log, [
                ("AAA", "2026-09-10", 100.0, 95.0, {}),                 # before learning_start
                ("BBB", "2026-09-15", 100.0, 95.0, {}),                 # frozen 2.5 multiple
                ("CCC", "2026-09-16", 100.0, 94.0, {"stop_atr": 3.0}),  # learned multiple
                ("CCC", "2026-09-16", 100.0, 94.0, {"stop_atr": 3.0}),  # same trade twice
                ("DDD", "2026-09-17", 100.0, 101.0, {}),                # stop above entry
            ])
            entries = logged_entries(log, CONFIG, 2.5)
            self.assertEqual([(e.symbol, e.atr) for e in entries], [("BBB", 2.0), ("CCC", 2.0)])


class Learner(unittest.TestCase):
    """Trades each in their own symbol, entered at 100 with ATR 2.

    The mechanics tests lower `min_trades` to 20 so a fixture stays small;
    everything else is the shipped rule. The shipped thresholds themselves
    are pinned below, and pure noise is tested against them unchanged.
    """

    # EXP-0055's fixed-target learner, which take_profit_mode='atr' keeps. The
    # bounce-mode learner (EXP-0057, the default) is pinned in
    # test_bounce_take_profit.py.
    MECHANICS = replace(CONFIG, min_trades=20, take_profit_mode="atr")

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / "audit.jsonl"
        self.params = self.dir / "adaptive-exits.json"

    def tearDown(self):
        self.tmp.cleanup()

    def trades(self, paths, directory=None):
        directory = directory or self.dir
        entries = []
        for i, after in enumerate(paths):
            symbol = "S{0:03d}".format(i)
            save_bars(directory / "{0}.csv".format(symbol), flat(1) + after)
            entries.append((symbol, "2026-09-14", 100.0, 95.0, {}))
        write_entries(directory / "audit.jsonl", entries)

    def run_learn(self, today=date(2026, 10, 30), config=None, directory=None):
        directory = directory or self.dir
        return learn(directory / "audit.jsonl", directory, directory / "adaptive-exits.json",
                     config or self.MECHANICS, NO_BOUNCE, today=today)

    def runner(self, i):
        """Jumps past +3 ATR on day 1 and keeps going: wider targets earn more."""
        return [bar(1, 100.5, 106.4, 100.2, 106.0)] + [
            bar(1 + d, 106 + d * 0.2, 106.5 + d * 0.2, 105.8 + d * 0.2, 106.2 + d * 0.2)
            for d in range(1, 20)]

    def fader(self, i):
        """Touches +2.5 ATR on day 1, then falls to the stop: a wider target loses."""
        return [bar(1, 100.5, 105.4, 100.2, 104.0), bar(2, 103.0, 103.5, 94.0, 94.5)] + flat(18, 94.5, first_day=3)

    def test_the_shipped_rule_is_the_one_measured(self):
        self.assertEqual((CONFIG.min_trades, CONFIG.improvement_standard_errors,
                          CONFIG.min_improvement_r, CONFIG.min_sessions_between_evaluations,
                          CONFIG.require_both_halves), (100, 3.0, 0.05, 20, True))

    def test_too_few_finished_trades_never_moves(self):
        self.trades([self.runner(i) for i in range(19)])
        decision = self.run_learn()
        self.assertEqual(decision["action"], "stayed")
        self.assertEqual(decision["finished_trades"], 19)
        record = json.loads(self.params.read_text(encoding="utf-8"))
        self.assertEqual(record["take_profit_atr"], 2.5)
        self.assertEqual(record["history"][-1]["finished_trades"], 19)

    def test_clear_evidence_moves_one_step_and_no_further(self):
        self.trades([self.runner(i) for i in range(20)])
        decision = self.run_learn()
        self.assertEqual(decision["action"], "moved")
        self.assertEqual((decision["take_profit_atr"], decision["stop_atr"]), (3.0, 2.5))
        self.assertEqual(current_levels(CONFIG, self.params), (3.0, 2.5))
        self.assertEqual(json.loads(self.params.read_text(encoding="utf-8"))["updated_at"],
                         "2026-10-30")

    def test_it_waits_twenty_sessions_between_evaluations(self):
        self.trades([self.runner(i) for i in range(20)])
        self.run_learn(today=date(2026, 10, 30))
        waited = self.run_learn(today=date(2026, 11, 13))            # ten sessions later
        self.assertEqual(waited["action"], "wait")
        self.assertEqual(current_levels(CONFIG, self.params), (3.0, 2.5))
        again = self.run_learn(today=date(2026, 11, 27))             # twenty sessions later
        self.assertEqual(again["take_profit_atr"], 3.5)

    def test_both_halves_of_the_record_must_agree(self):
        # 19 runners then 1 fader: over the whole record a wider target wins
        # (+0.09 R a trade), but the newer half, which holds the fader, says
        # otherwise. The standard-error bar is switched off and the stop held
        # fixed, so the halves rule is the only thing that can block the move.
        self.trades([self.runner(i) for i in range(19)] + [self.fader(0)])
        target_only = replace(self.MECHANICS, stop_bounds=(2.5, 2.5),
                              improvement_standard_errors=0.0)
        loose = replace(target_only, require_both_halves=False)
        self.assertEqual(self.run_learn(config=loose)["take_profit_atr"], 3.0)
        self.params.unlink()
        strict = self.run_learn(config=target_only)
        wider = strict["neighbours"]["take 3.0 / stop 2.5"]
        self.assertGreater(wider["mean_r_gain"], 0)
        self.assertGreater(wider["older_half"], 0)
        self.assertLess(wider["newer_half"], 0)
        self.assertFalse(wider["clears_the_bar"])
        self.assertEqual(strict["action"], "stayed")

    def test_pure_noise_rarely_moves_the_shipped_rule(self):
        # Twenty worlds of 100 driftless random walks (one ATR of noise a
        # day). Simulation put the shipped rule's false-move rate at 7.2%; a
        # broken rule moves in most worlds.
        import random
        moved = 0
        for world in range(20):
            with TemporaryDirectory() as tmp:
                directory, paths = Path(tmp), []
                for i in range(100):
                    rng, price, after = random.Random(world * 1000 + i), 100.0, []
                    for d in range(1, 21):
                        close = price + rng.gauss(0.0, 2.0)
                        after.append(bar(d, price, max(price, close) + 0.5,
                                         min(price, close) - 0.5, close))
                        price = close
                    paths.append(after)
                self.trades(paths, directory)
                moved += self.run_learn(config=replace(CONFIG, take_profit_mode="atr"),
                                        directory=directory)["action"] == "moved"
        self.assertLessEqual(moved, 5)

    def test_it_never_leaves_the_bounds(self):
        self.params.write_text(json.dumps({"take_profit_atr": 6.0, "stop_atr": 2.5,
                                           "last_evaluated": "2026-09-01"}), encoding="utf-8")
        self.trades([self.runner(i) for i in range(20)])
        decision = self.run_learn()
        self.assertLessEqual(decision["take_profit_atr"], 6.0)
        self.assertNotIn("take 6.5 / stop 2.5", decision["neighbours"])


if __name__ == "__main__":
    unittest.main()

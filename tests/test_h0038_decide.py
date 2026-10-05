"""H-0038's verdict step, on synthetic result blocks: the defect that stopped
H-0037 (a lookup of a comparison it never computed) cannot recur."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import run_h0038 as runner                                            # noqa: E402


def block(mean, t, first, second):
    return {"C_minus_B": {"all": {"mean": mean, "t": t},
                          "halves": {"first": {"mean": first}, "second": {"mean": second}}}}


def results(primary, backtest_mean, none_mean):
    return {"primary": primary,
            "backtest": block(backtest_mean, 1.0, backtest_mean, backtest_mean),
            "none": block(none_mean, 1.0, none_mean, none_mean)}


class Decide(unittest.TestCase):
    def test_move_when_c_beats_b_everywhere(self):
        criteria, verdict = runner.decide(results(block(0.05, 2.5, 0.04, 0.06), 0.07, 0.03))
        self.assertEqual(verdict, "MOVE")
        self.assertEqual(criteria, {"MOVE": True, "KEEP": False})

    def test_keep_when_b_beats_c_everywhere(self):
        criteria, verdict = runner.decide(results(block(-0.05, -2.5, -0.04, -0.06), -0.02, -0.08))
        self.assertEqual(verdict, "KEEP")
        self.assertEqual(criteria, {"MOVE": False, "KEEP": True})

    def test_no_difference_when_t_is_short(self):
        _, verdict = runner.decide(results(block(0.05, 1.9, 0.04, 0.06), 0.07, 0.03))
        self.assertEqual(verdict, "NO DIFFERENCE SHOWN")

    def test_no_difference_when_a_half_disagrees(self):
        _, verdict = runner.decide(results(block(0.05, 3.0, -0.01, 0.10), 0.07, 0.03))
        self.assertEqual(verdict, "NO DIFFERENCE SHOWN")

    def test_no_difference_when_another_haircut_disagrees(self):
        _, verdict = runner.decide(results(block(0.05, 3.0, 0.04, 0.06), 0.07, -0.01))
        self.assertEqual(verdict, "NO DIFFERENCE SHOWN")

    def test_missing_t_does_not_crash(self):
        _, verdict = runner.decide(results(block(0.05, None, 0.04, 0.06), 0.07, 0.03))
        self.assertEqual(verdict, "NO DIFFERENCE SHOWN")


if __name__ == "__main__":
    unittest.main()

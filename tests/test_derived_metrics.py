#!/usr/bin/env python3
"""The three parameters the reweight was built for, measured from source data.

Each returns None when its input is absent, so the caller decides what an
unmeasured parameter is worth rather than a default silently deciding for it.
"""
import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "app", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from screener.derived_metrics import (
    calculate_daily_green_rate,
    calculate_drawdown_depth,
    calculate_edge_to_friction,
)


class TestDrawdownDepth(unittest.TestCase):
    def test_measures_the_deepest_fall_as_a_share_of_the_peak(self):
        # Peak 100, trough 60 after it: a 40 point fall against a 100 point peak.
        curve = [0, 50, 100, 80, 60, 90]
        self.assertAlmostEqual(calculate_drawdown_depth(json.dumps(curve)), 0.40)

    def test_a_curve_that_only_rises_has_no_drawdown(self):
        self.assertAlmostEqual(calculate_drawdown_depth(json.dumps([0, 10, 20, 30, 40, 50])), 0.0)

    def test_measures_against_the_running_peak_not_the_final_value(self):
        # The deepest fall is 200 -> 50, not the smaller dip that follows.
        curve = [0, 100, 200, 50, 120, 110]
        self.assertAlmostEqual(calculate_drawdown_depth(json.dumps(curve)), 0.75)

    def test_a_fall_is_measured_against_the_peak_it_fell_from(self):
        # Halving from 1000 is a 50% fall even though the curve later doubles.
        # Dividing by the final, larger peak would report 25% and score it well.
        curve = [0, 1000, 500, 600, 1500, 2000]
        self.assertAlmostEqual(calculate_drawdown_depth(json.dumps(curve)), 0.50)

    def test_losing_more_than_the_peak_is_reported_as_total(self):
        # A curve that runs below zero can fall further than it ever rose.
        curve = [0, 100, 50, -100, -200, -50]
        self.assertAlmostEqual(calculate_drawdown_depth(json.dumps(curve)), 1.0)

    def test_ignores_the_stretch_before_the_curve_turns_positive(self):
        curve = [0, -50, -20, 100, 40, 120]
        self.assertAlmostEqual(calculate_drawdown_depth(json.dumps(curve)), 0.60)

    def test_returns_none_when_the_curve_is_absent_or_too_short(self):
        self.assertIsNone(calculate_drawdown_depth(None))
        self.assertIsNone(calculate_drawdown_depth(""))
        self.assertIsNone(calculate_drawdown_depth(json.dumps([1, 2, 3])))

    def test_returns_none_when_the_curve_never_reaches_a_positive_peak(self):
        # A share of a non-positive peak is not a meaningful number.
        self.assertIsNone(calculate_drawdown_depth(json.dumps([0, -10, -20, -5, -30, -40])))

    def test_returns_none_on_malformed_input_rather_than_raising(self):
        self.assertIsNone(calculate_drawdown_depth("not json"))


class TestDailyGreenRate(unittest.TestCase):
    @staticmethod
    def _series(copy_pnls):
        return json.dumps(
            [
                {"date": f"2026-08-{i + 1:02d}", "volume": 10.0, "trades": 1,
                 "actual_pnl": 999.0, "bt_copy_pnl": v}
                for i, v in enumerate(copy_pnls)
            ]
        )

    def test_counts_days_green_on_copy_adjusted_profit(self):
        rate, days = calculate_daily_green_rate(self._series([1, 1, 1, -1, -1, 1, 1, -1, 1, 1]))
        self.assertAlmostEqual(rate, 70.0)
        self.assertEqual(days, 10)

    def test_ignores_the_targets_own_profit(self):
        # Every day is green for the target and red for a copier. The copier wins.
        rate, _ = calculate_daily_green_rate(self._series([-1] * 12))
        self.assertAlmostEqual(rate, 0.0)

    def test_a_flat_day_is_not_a_green_day(self):
        rate, days = calculate_daily_green_rate(self._series([0, 0, 0, 0, 0, 1, 1, 1, 1, 1]))
        self.assertAlmostEqual(rate, 50.0)
        self.assertEqual(days, 10)

    def test_a_day_the_series_does_not_report_is_not_an_observed_day(self):
        # Ten measured green days beside ten unreported ones is a 100% rate over
        # ten days, not a 50% rate over twenty.
        days = [
            {"date": f"2026-08-{i + 1:02d}", "volume": 10.0, "trades": 1,
             "actual_pnl": 5.0, "bt_copy_pnl": 1.0}
            for i in range(10)
        ] + [
            {"date": f"2026-08-{i + 11:02d}", "volume": 10.0, "trades": 1, "actual_pnl": 5.0}
            for i in range(10)
        ]
        rate, observed = calculate_daily_green_rate(json.dumps(days))
        self.assertAlmostEqual(rate, 100.0)
        self.assertEqual(observed, 10)

    def test_an_explicit_null_is_unreported_rather_than_flat(self):
        days = [
            {"date": "2026-08-01", "bt_copy_pnl": 5.0},
            {"date": "2026-08-02", "bt_copy_pnl": None},
        ]
        rate, observed = calculate_daily_green_rate(json.dumps(days))
        self.assertAlmostEqual(rate, 100.0)
        self.assertEqual(observed, 1)

    def test_reports_the_real_observed_day_count(self):
        _, days = calculate_daily_green_rate(self._series([1] * 7))
        self.assertEqual(days, 7)

    def test_returns_none_when_the_series_is_absent(self):
        rate, days = calculate_daily_green_rate(None)
        self.assertIsNone(rate)
        self.assertEqual(days, 0)

    def test_returns_none_on_malformed_input_rather_than_raising(self):
        rate, days = calculate_daily_green_rate("not json")
        self.assertIsNone(rate)
        self.assertEqual(days, 0)


class TestEdgeToFriction(unittest.TestCase):
    def test_compares_edge_and_friction_on_the_same_denominator(self):
        # Both sides are shares of traded volume: friction costs the assumed
        # slippage on every dollar that changes hands.
        self.assertAlmostEqual(calculate_edge_to_friction(20.0, 10.0), 2.0)

    def test_a_ratio_of_one_is_break_even(self):
        self.assertAlmostEqual(calculate_edge_to_friction(10.0, 10.0), 1.0)

    def test_an_edge_thinner_than_friction_falls_below_one(self):
        self.assertLess(calculate_edge_to_friction(4.0, 10.0), 1.0)

    def test_a_target_that_loses_money_has_no_edge_to_measure(self):
        self.assertAlmostEqual(calculate_edge_to_friction(-5.0, 10.0), 0.0)

    def test_returns_none_when_friction_is_undefined(self):
        self.assertIsNone(calculate_edge_to_friction(20.0, 0.0))
        self.assertIsNone(calculate_edge_to_friction(20.0, -1.0))

    def test_returns_none_when_the_edge_is_unknown(self):
        self.assertIsNone(calculate_edge_to_friction(None, 10.0))


if __name__ == "__main__":
    unittest.main()

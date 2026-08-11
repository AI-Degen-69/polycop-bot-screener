#!/usr/bin/env python3
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from screener.score_wallets import (
    TIER_A_MIN,
    TIER_B_MIN,
    TIER_C_MIN,
    TIER_S_MIN,
    TRACK_RECORD_LENGTH_MIN_MARKETS,
    calculate_bankroll_optimized_score,
    calculate_edge_retention,
    grade_for_score,
)

class TestScoreWalletsEngine(unittest.TestCase):
    def test_edge_retention_positive_pnl(self):
        """Test edge retention on positive PnLs."""
        self.assertAlmostEqual(calculate_edge_retention(80.0, 100.0), 0.8)

    def test_edge_retention_negative_pnl_returns_none(self):
        """Test edge retention gate ordering: negative PnL must return None."""
        self.assertIsNone(calculate_edge_retention(-5.95, -5.05))
        self.assertIsNone(calculate_edge_retention(-5.0, 10.0))
        self.assertIsNone(calculate_edge_retention(10.0, 0.0))

    
    def test_pass_target_high_score(self):
        """Test a clean S-Tier target passing all gates.

        Every parameter is measured. A wallet missing measurements cannot reach
        this score, which is the point of the fail-closed rule.
        """
        metrics = {
            "actual_pnl": 5000.0,
            "copy_pnl": 4900.0,
            "hedged_pct": 0.0,
            "pl_ratio": 5.0,
            "days_win_rate": 80.0,
            "observed_days": 14,
            "r20_win_rate": 80.0,
            "r20_pnl": 800.0,
            "r20_slip": 2.0,
            "pnl_vol_ratio": 25.0,
            "avg_invest": 100.0,
            "markets": 150,
            "polycop_site_score": 85.0,
            "edge_to_friction": 3.0,
            "drawdown_depth": 0.05,
        }
        res = calculate_bankroll_optimized_score(metrics, user_capital=100.0)
        self.assertEqual(len(res["rejection_reasons"]), 0)
        # Recalibrated tier bands (ADR 0005, re-measured in ADR 0010): a fully
        # measured wallet must clear the S-Tier floor, which is 80 rather than
        # the inherited 90.
        self.assertGreaterEqual(res["final_score"], TIER_S_MIN)

    def test_whale_gate_at_200(self):
        """Test Hard Gate: Avg Invest > $200.00 USD."""
        metrics = {"polycop_site_score": 75.0, "actual_pnl": 1000.0, "copy_pnl": 950.0, "avg_invest": 250.0}
        res = calculate_bankroll_optimized_score(metrics)
        self.assertTrue(any("Whale Avg Invest" in r for r in res["rejection_reasons"]))

    def test_site_score_prefilter_removed_sanity_floor_at_40(self):
        """Test site score <= 60 no longer rejects, but < 40 sanity floor rejects."""
        # 55 passes (pre-filter removed)
        metrics_pass = {"polycop_site_score": 55.0, "actual_pnl": 1000.0, "copy_pnl": 950.0, "markets": 30, "r20_win_rate": 60.0}
        res_pass = calculate_bankroll_optimized_score(metrics_pass)
        self.assertFalse(any("PolyCop Site Score" in r for r in res_pass["rejection_reasons"]))

        # 35 fails (sanity floor at 40)
        metrics_fail = {"polycop_site_score": 35.0, "actual_pnl": 1000.0, "copy_pnl": 950.0}
        res_fail = calculate_bankroll_optimized_score(metrics_fail)
        self.assertTrue(any("PolyCop Site Score" in r for r in res_fail["rejection_reasons"]))

    def test_divergence_gate_negative_recent_vs_positive_lifetime(self):
        """Test Divergence Gate: r20_pnl < 0 while actual_pnl > 1000."""
        metrics = {"polycop_site_score": 75.0, "actual_pnl": 5000.0, "copy_pnl": 4500.0, "r20_pnl": -200.0}
        res = calculate_bankroll_optimized_score(metrics)
        self.assertTrue(any("Divergence Gate" in r for r in res["rejection_reasons"]))

    def test_track_record_length_rejects_below_the_lifetime_market_floor(self):
        """Issue #30: a wallet under the lifetime-markets floor is rejected.

        The gate is measured on the lifetime markets field, not the rolling
        daily activity series: that series is hard-capped at 14 rows, so a
        slow steady trader with a real record would be wrongly rejected and a
        one-week frenzy would pass. Lifetime markets is the only lifetime
        record-depth field the leaderboard provides.
        """
        res = calculate_bankroll_optimized_score(_clean_metrics(markets=24))
        self.assertTrue(any("Track Record Length" in r for r in res["rejection_reasons"]))

    def test_track_record_length_passes_at_and_above_the_floor(self):
        res = calculate_bankroll_optimized_score(_clean_metrics(markets=25))
        self.assertFalse(any("Track Record Length" in r for r in res["rejection_reasons"]))

    def test_track_record_length_absence_rejects(self):
        """A wallet whose trade record cannot be measured is rejected.

        The engine defaults an absent markets figure to zero, which sits below
        the floor — an unmeasurable record is not a record (the Markets Sample
        gate's absence semantics, carried into the re-scoped gate).
        """
        absent = _clean_metrics()
        absent.pop("markets")
        res = calculate_bankroll_optimized_score(absent)
        self.assertTrue(any("Track Record Length" in r for r in res["rejection_reasons"]))

    def test_the_track_record_length_floor_is_the_recalibrated_constant(self):
        """The research's ~50-position bar maps to ~23 lifetime markets at the
        observed ~2.2 trades-per-market density, rounded conservatively to 25;
        the floor must not drift."""
        self.assertEqual(TRACK_RECORD_LENGTH_MIN_MARKETS, 25.0)


def _clean_metrics(**overrides):
    """A wallet that clears every gate, so parameter scoring can be read in isolation."""
    base = {
        "actual_pnl": 5000.0,
        "copy_pnl": 4900.0,
        "hedged_pct": 0.0,
        "pl_ratio": 5.0,
        "r20_pnl": 800.0,
        "r20_slip": 2.0,
        "pnl_vol_ratio": 25.0,
        "avg_invest": 100.0,
        "markets": 150,
        "polycop_site_score": 85.0,
    }
    base.update(overrides)
    return base


def _points(res, needle):
    # Try stable id first, then match against the display labels (which are
    # the engine's canonical source, so a needle like "Edge-to-Friction"
    # finds the right row).
    b = res["breakdown"]
    labels = res.get("breakdown_labels", {})
    if needle in b:
        return b[needle]
    for bid, lbl in labels.items():
        if needle in lbl:
            return b[bid]
    matched = [v for k, v in b.items() if needle in k]
    raise AssertionError(f"expected one breakdown row matching {needle!r}, got {matched}")


class TestUnmeasuredParametersFailClosed(unittest.TestCase):
    """A parameter nobody measured must score nothing, not everything.

    These three defaulted to their best possible value, so every wallet
    collected 44 points it had not earned and the tier bands measured an
    offset rather than performance.
    """

    def test_edge_to_friction_scores_nothing_when_absent(self):
        res = calculate_bankroll_optimized_score(_clean_metrics())
        self.assertEqual(_points(res, "Edge-to-Friction"), 0.0)

    def test_copyable_window_share_is_simulation_only(self):
        """ADR 0006: the triage engine no longer reads a window share at all.

        A leaderboard profile cannot measure the share of entry signals a window
        admits, so the parameter was moved off the triage table entirely. Its ten
        points were redistributed proportionally; passing a value in the metrics
        dict must not earn anything, because a stale simulation payload on a
        leaderboard profile must never feed triage scoring (PR #22 footgun).
        """
        res = calculate_bankroll_optimized_score(
            _clean_metrics(copyable_window_share=1.0)
        )
        self.assertNotIn("window_share", res["breakdown"])
        self.assertNotIn("Copyable Window Share", res.get("breakdown_labels", {}).values())
        # The redistributed weights still sum to one hundred.
        self.assertEqual(sum(res["breakdown_points"].values()), 100)

    def test_drawdown_depth_scores_nothing_when_absent(self):
        res = calculate_bankroll_optimized_score(_clean_metrics())
        self.assertEqual(_points(res, "Drawdown Depth"), 0.0)

    def test_daily_green_rate_scores_nothing_when_absent(self):
        res = calculate_bankroll_optimized_score(_clean_metrics())
        self.assertEqual(_points(res, "Daily Green Rate"), 0.0)

    def test_a_wallet_with_nothing_measured_cannot_reach_a_passing_score(self):
        res = calculate_bankroll_optimized_score(_clean_metrics())
        self.assertLess(res["final_score"], 50.0)


class TestEdgeToFrictionCurve(unittest.TestCase):
    def test_break_even_scores_nothing(self):
        """A ratio of one means friction eats the edge exactly. That is not worth points."""
        res = calculate_bankroll_optimized_score(_clean_metrics(edge_to_friction=1.0))
        self.assertAlmostEqual(_points(res, "Edge-to-Friction"), 0.0, places=2)

    def test_an_edge_below_friction_scores_nothing(self):
        res = calculate_bankroll_optimized_score(_clean_metrics(edge_to_friction=0.4))
        self.assertAlmostEqual(_points(res, "Edge-to-Friction"), 0.0, places=2)

    def test_full_marks_need_an_edge_several_times_the_friction(self):
        res = calculate_bankroll_optimized_score(_clean_metrics(edge_to_friction=3.0))
        self.assertAlmostEqual(_points(res, "Edge-to-Friction"), 24.0, places=2)

    def test_the_curve_rises_between_break_even_and_full_marks(self):
        thin = calculate_bankroll_optimized_score(_clean_metrics(edge_to_friction=1.5))
        thick = calculate_bankroll_optimized_score(_clean_metrics(edge_to_friction=2.5))
        self.assertLess(_points(thin, "Edge-to-Friction"), _points(thick, "Edge-to-Friction"))


class TestDrawdownDepthScoring(unittest.TestCase):
    def test_an_untouched_equity_curve_scores_full_marks(self):
        res = calculate_bankroll_optimized_score(_clean_metrics(drawdown_depth=0.0))
        self.assertAlmostEqual(_points(res, "Drawdown Depth"), 13.0, places=2)

    def test_a_deep_fall_scores_nothing(self):
        res = calculate_bankroll_optimized_score(_clean_metrics(drawdown_depth=0.90))
        self.assertAlmostEqual(_points(res, "Drawdown Depth"), 0.0, places=2)

    def test_a_deeper_fall_scores_less(self):
        shallow = calculate_bankroll_optimized_score(_clean_metrics(drawdown_depth=0.10))
        deep = calculate_bankroll_optimized_score(_clean_metrics(drawdown_depth=0.35))
        self.assertLess(_points(deep, "Drawdown Depth"), _points(shallow, "Drawdown Depth"))


class TestDailyGreenRateNeedsEnoughDays(unittest.TestCase):
    def test_a_strong_rate_over_too_few_days_scores_nothing(self):
        res = calculate_bankroll_optimized_score(
            _clean_metrics(days_win_rate=100.0, observed_days=4)
        )
        self.assertEqual(_points(res, "Daily Green Rate"), 0.0)

    def test_a_strong_rate_over_enough_days_scores(self):
        res = calculate_bankroll_optimized_score(
            _clean_metrics(days_win_rate=90.0, observed_days=14)
        )
        self.assertGreater(_points(res, "Daily Green Rate"), 0.0)


class TestRecentFormWeighsSlip(unittest.TestCase):
    def test_the_same_profit_earned_through_more_friction_scores_less(self):
        clean = calculate_bankroll_optimized_score(_clean_metrics(r20_pnl=1000.0, r20_slip=0.0))
        gritty = calculate_bankroll_optimized_score(_clean_metrics(r20_pnl=1000.0, r20_slip=12.0))
        self.assertLess(_points(gritty, "Recent Form"), _points(clean, "Recent Form"))

    def test_profit_earned_through_total_friction_scores_nothing(self):
        res = calculate_bankroll_optimized_score(_clean_metrics(r20_pnl=1000.0, r20_slip=15.0))
        self.assertAlmostEqual(_points(res, "Recent Form"), 0.0, places=2)

    def test_a_losing_recent_run_scores_nothing(self):
        res = calculate_bankroll_optimized_score(_clean_metrics(r20_pnl=0.0, r20_slip=0.0))
        self.assertAlmostEqual(_points(res, "Recent Form"), 0.0, places=2)


class TestRecentFormMeasuresReturnNotAbsoluteDollars(unittest.TestCase):
    """ADR 0004: recent profit is scored against the capital that produced it.

    An absolute-dollar scale rewards the target's size rather than its edge: a
    big trader clears the threshold on ordinary performance while a small trader
    needs a far better result for the same points. Return makes the parameter
    measure edge per dollar deployed.
    """

    def test_the_same_absolute_pnl_scores_more_on_a_smaller_target(self):
        big = calculate_bankroll_optimized_score(_clean_metrics(r20_pnl=800.0, avg_invest=160.0))
        small = calculate_bankroll_optimized_score(_clean_metrics(r20_pnl=800.0, avg_invest=40.0))
        # Same $800 of recent profit, but the $40 target earned a 100% return on
        # its deployed capital while the $160 target earned 25%.
        self.assertGreater(_points(small, "Recent Form"), _points(big, "Recent Form"))

    def test_full_marks_need_a_100_percent_return_over_the_window(self):
        # $1,000 recent profit on $50 average investment is a 100% return over
        # the 20-trade window at zero slip.
        res = calculate_bankroll_optimized_score(_clean_metrics(r20_pnl=1000.0, avg_invest=50.0, r20_slip=0.0))
        self.assertAlmostEqual(_points(res, "Recent Form"), 11.0, places=2)

    def test_an_unknown_target_size_scores_nothing(self):
        res = calculate_bankroll_optimized_score(_clean_metrics(r20_pnl=1000.0, avg_invest=0.0))
        self.assertAlmostEqual(_points(res, "Recent Form"), 0.0, places=2)


class TestSizingFitFollowsTheCopyableWindow(unittest.TestCase):
    """The peak belongs where the realised copy ratio equals the nominal one."""

    def test_the_peak_sits_inside_the_window(self):
        from execution.copy_execution_profile import CURRENT_PROFILE

        peak = CURRENT_PROFILE.sizing_fit_peak_usd
        self.assertGreater(peak, CURRENT_PROFILE.window_min_usd)
        self.assertLess(peak, CURRENT_PROFILE.window_max_usd)

    def test_a_target_sized_at_the_peak_scores_full_marks(self):
        from execution.copy_execution_profile import CURRENT_PROFILE

        res = calculate_bankroll_optimized_score(
            _clean_metrics(avg_invest=CURRENT_PROFILE.sizing_fit_peak_usd)
        )
        self.assertAlmostEqual(_points(res, "Sizing Fit"), 6.0, places=2)

    def test_a_target_below_the_window_scores_nothing(self):
        """Below the window every copy order is bumped to the venue minimum."""
        res = calculate_bankroll_optimized_score(_clean_metrics(avg_invest=10.0))
        self.assertAlmostEqual(_points(res, "Sizing Fit"), 0.0, places=2)

    def test_a_target_above_the_window_scores_nothing(self):
        """Above the window the position cap clips the copy below the nominal ratio."""
        res = calculate_bankroll_optimized_score(_clean_metrics(avg_invest=190.0))
        self.assertAlmostEqual(_points(res, "Sizing Fit"), 0.0, places=2)


class TestRecalibratedTierBands(unittest.TestCase):
    """Bands were inherited from the old engine and never checked against the
    score distribution the current engine produces (ADR 0005). These assert the
    recalibrated floors directly, so a future move of a boundary is visible.
    """

    def test_the_bands_are_the_recalibrated_absolutes(self):
        self.assertEqual(TIER_S_MIN, 80.0)
        self.assertEqual(TIER_A_MIN, 71.0)
        self.assertEqual(TIER_B_MIN, 65.0)
        self.assertEqual(TIER_C_MIN, 56.0)

    def test_each_band_claims_its_score_range(self):
        self.assertIn("S-Tier", grade_for_score(TIER_S_MIN))
        self.assertIn("A-Tier", grade_for_score(TIER_A_MIN))
        self.assertIn("B-Tier", grade_for_score(TIER_B_MIN))
        self.assertIn("C-Tier", grade_for_score(TIER_C_MIN))
        self.assertIn("F-Tier", grade_for_score(TIER_C_MIN - 0.01))

    def test_the_engine_assigns_the_band_the_score_earns(self):
        res = calculate_bankroll_optimized_score(
            _clean_metrics(edge_to_friction=3.0,
                           drawdown_depth=0.0, days_win_rate=95.0,
                           observed_days=14, r20_pnl=2000.0, r20_slip=0.0,
                           pl_ratio=4.0, pnl_vol_ratio=30.0, markets=250)
        )
        self.assertEqual(res["grade"], grade_for_score(res["final_score"]))


class TestTheDocstringGatesAreGeneratedFromTheSpec(unittest.TestCase):
    """Issue #27: the engine docstring's gate list is generated from
    SCORING_SPEC at import, so a threshold changed in the code updates help()
    automatically and can never drift from the constants the drift check
    trusts.
    """

    def test_every_spec_gate_appears_in_the_docstring(self):
        from screener.score_wallets import SCORING_SPEC

        doc = calculate_bankroll_optimized_score.__doc__
        for gate in SCORING_SPEC["gates"]:
            self.assertIn(gate["condition"], doc)

    def test_the_hand_written_gate_copies_are_gone(self):
        doc = calculate_bankroll_optimized_score.__doc__
        # The old docstring duplicated thresholds the drift check does not
        # gate; the generated list carries the spec's own wording instead.
        self.assertNotIn("Low quality sanity floor", doc)
        self.assertNotIn("5% modelled (0.05)", doc)


class TestTheModelledCopyPnlDomainTerm(unittest.TestCase):
    """CONTEXT.md's glossary approves "Modelled Copy PnL" and avoids "backtest
    copy PnL" / "copy PnL"; the gate's constant, label and rejection wording
    must use it (issue #27).
    """

    def test_the_constant_uses_the_approved_term(self):
        from screener.score_wallets import MODELLED_COPY_PNL_MIN_USD

        self.assertEqual(MODELLED_COPY_PNL_MIN_USD, 0.0)
        with self.assertRaises(ImportError):
            from screener.score_wallets import BACKTEST_COPY_PNL_MIN_USD  # noqa: F401

    def test_the_rejection_wording_uses_the_approved_term(self):
        metrics = {"polycop_site_score": 75.0, "actual_pnl": 1000.0, "copy_pnl": -50.0}
        res = calculate_bankroll_optimized_score(metrics)
        self.assertTrue(any("Modelled Copy PnL" in r for r in res["rejection_reasons"]))
        self.assertFalse(any("Backtest" in r for r in res["rejection_reasons"]))


class TestScaleIsIntact(unittest.TestCase):
    def test_a_fully_measured_ideal_wallet_scores_one_hundred(self):
        from execution.copy_execution_profile import CURRENT_PROFILE

        res = calculate_bankroll_optimized_score(
            _clean_metrics(
                copy_pnl=5000.0,
                edge_to_friction=3.0,
                drawdown_depth=0.0,
                days_win_rate=95.0,
                observed_days=14,
                r20_pnl=2000.0,
                r20_slip=0.0,
                pl_ratio=4.0,
                pnl_vol_ratio=30.0,
                markets=250,
                avg_invest=CURRENT_PROFILE.sizing_fit_peak_usd,
            )
        )
        self.assertEqual(len(res["rejection_reasons"]), 0)
        self.assertAlmostEqual(res["final_score"], 100.0, places=1)


class TestTheSpecIsTheEngine(unittest.TestCase):
    """SCORING_SPEC's parameters are executable: the engine awards each row
    exactly its declared points at that row's full-marks anchors, so a reweight
    is a one-row edit and the docs regenerate from the same table."""

    def test_every_parameter_awards_exactly_its_spec_points_at_full_marks(self):
        from screener.score_wallets import SCORING_SPEC
        from execution.copy_execution_profile import CURRENT_PROFILE

        # The same fully measured ideal wallet as TestScaleIsIntact: every
        # parameter sits at its full-marks anchor, so each breakdown row must
        # equal the spec's declared points exactly.
        res = calculate_bankroll_optimized_score(
            _clean_metrics(
                copy_pnl=5000.0,
                edge_to_friction=3.0,
                drawdown_depth=0.0,
                days_win_rate=95.0,
                observed_days=14,
                r20_pnl=2000.0,
                r20_slip=0.0,
                pl_ratio=4.0,
                pnl_vol_ratio=30.0,
                markets=250,
                avg_invest=CURRENT_PROFILE.sizing_fit_peak_usd,
            )
        )
        for row in SCORING_SPEC["parameters"]:
            with self.subTest(key=row["key"]):
                self.assertEqual(res["breakdown"][row["key"]], row["points"])

    def test_every_row_names_a_shape_the_engine_knows(self):
        from screener.score_wallets import SCORING_SPEC, _SHAPE_FNS

        for row in SCORING_SPEC["parameters"]:
            with self.subTest(key=row["key"]):
                self.assertIn(row["shape"], _SHAPE_FNS)

    def test_every_row_scores_a_metric_the_engine_extracts(self):
        """A row referencing a metric the engine never extracts would score a
        silent zero forever; the full-marks parity test catches a wiring bug at
        the max end, this pins the contract at the source."""
        from screener.score_wallets import SCORING_SPEC

        extracted = {
            "edge_to_friction", "slip_cost_rate", "drawdown_depth",
            "r20_pnl", "r20_slip", "avg_invest", "days_win_rate",
            "observed_days", "pl_ratio", "hedged_pct", "markets",
            "pnl_vol_ratio",
        }
        for row in SCORING_SPEC["parameters"]:
            with self.subTest(key=row["key"]):
                # Composite shapes (recent_form) read their inputs directly;
                # generic shapes declare the one metric they score.
                if "metric" in row:
                    self.assertIn(row["metric"], extracted)

    def test_spec_keys_are_unique_and_are_the_breakdown_keys(self):
        from screener.score_wallets import SCORING_SPEC

        keys = [row["key"] for row in SCORING_SPEC["parameters"]]
        self.assertEqual(len(keys), len(set(keys)))
        res = calculate_bankroll_optimized_score(_clean_metrics())
        self.assertEqual(set(res["breakdown"]), set(keys))


if __name__ == "__main__":
    unittest.main()

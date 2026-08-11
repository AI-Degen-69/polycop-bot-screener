#!/usr/bin/env python3
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))
from paths import SRC_DIR

from execution.copy_execution_profile import CURRENT_PROFILE, CopyExecutionProfile


class TestProfileFingerprint(unittest.TestCase):
    """A screening result is valid only for a stated profile, so the profile must
    be able to state itself in a form that changes when it does."""

    def test_identical_profiles_share_a_fingerprint(self):
        self.assertEqual(
            CopyExecutionProfile().fingerprint,
            CopyExecutionProfile().fingerprint,
        )

    def test_a_changed_copy_ratio_changes_the_fingerprint(self):
        self.assertNotEqual(
            CopyExecutionProfile(copy_ratio=0.03).fingerprint,
            CopyExecutionProfile(copy_ratio=0.06).fingerprint,
        )

    def test_every_field_participates_in_the_fingerprint(self):
        base = CopyExecutionProfile()
        for field_name, value in base.as_dict().items():
            bumped = CopyExecutionProfile(**{**base.as_dict(), field_name: value + 1.0})
            self.assertNotEqual(
                base.fingerprint,
                bumped.fingerprint,
                f"changing {field_name} left the fingerprint untouched",
            )

    def test_the_fingerprint_survives_a_process_restart(self):
        # Cached simulation results are keyed on this string. If it depended on
        # PYTHONHASHSEED every run would miss cache instead of only a profile change
        # missing it, so compute it in two fresh processes seeded differently.
        script = (
            "import sys; sys.path.insert(0, %r);"
            "from execution.copy_execution_profile import CURRENT_PROFILE;"
            "print(CURRENT_PROFILE.fingerprint)" % SRC_DIR
        )

        def fingerprint_under(seed):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            out = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, check=True, env=env,
            )
            return out.stdout.strip()

        self.assertEqual(fingerprint_under("0"), fingerprint_under("12345"))
        self.assertEqual(fingerprint_under("0"), CURRENT_PROFILE.fingerprint)


class TestCopyableTradeWindow(unittest.TestCase):
    """The window is the range of target trade sizes the profile actually mirrors."""

    def test_lower_bound_is_the_venue_minimum_divided_by_the_copy_ratio(self):
        # Below $33.33 a 3% copy order falls under the $1.00 venue minimum.
        self.assertAlmostEqual(CURRENT_PROFILE.window_min_usd, 33.33, places=2)

    def test_upper_bound_is_the_per_token_cap_divided_by_the_copy_ratio(self):
        # Above $166.67 a 3% copy order is clipped by the $5.00 per-token cap.
        self.assertAlmostEqual(CURRENT_PROFILE.window_max_usd, 166.67, places=2)

    def test_a_doubled_copy_ratio_halves_both_bounds(self):
        doubled = CopyExecutionProfile(copy_ratio=0.06)
        self.assertAlmostEqual(doubled.window_min_usd, 16.67, places=2)
        self.assertAlmostEqual(doubled.window_max_usd, 83.33, places=2)

    def test_raising_a_cap_that_is_not_binding_widens_nothing(self):
        # The 5% bankroll rule already caps a position at $5.00, so doubling the
        # per-token cap admits no larger a copy order and no wider a window.
        wider_cap = CopyExecutionProfile(per_token_cap_usd=10.0)
        self.assertAlmostEqual(wider_cap.window_min_usd, CURRENT_PROFILE.window_min_usd, places=2)
        self.assertAlmostEqual(wider_cap.window_max_usd, CURRENT_PROFILE.window_max_usd, places=2)

    def test_the_upper_bound_follows_whichever_cap_binds(self):
        # Lift both the per-token cap and the bankroll share, and the window moves.
        lifted = CopyExecutionProfile(per_token_cap_usd=10.0, max_position_bankroll_fraction=0.10)
        self.assertAlmostEqual(lifted.max_single_position_usd, 10.00, places=2)
        self.assertAlmostEqual(lifted.window_max_usd, 333.33, places=2)

    def test_a_small_bankroll_narrows_the_window_it_can_actually_mirror(self):
        # A $50 bankroll caps a position at $2.50, so it cannot mirror a $166 trade
        # at the nominal ratio however high the per-token cap is set.
        small = CopyExecutionProfile(bankroll_usd=50.0)
        self.assertAlmostEqual(small.window_max_usd, 83.33, places=2)


class TestProfileDerivedSizing(unittest.TestCase):
    """Everything downstream asks the profile rather than carrying its own copy."""

    def test_the_copy_order_is_the_bankroll_share_held_under_the_position_cap(self):
        self.assertAlmostEqual(CURRENT_PROFILE.copy_trade_usd, 3.00, places=2)

    def test_max_single_position_respects_both_the_cap_and_the_bankroll(self):
        self.assertAlmostEqual(CURRENT_PROFILE.max_single_position_usd, 5.00, places=2)
        small = CopyExecutionProfile(bankroll_usd=50.0)
        self.assertAlmostEqual(small.max_single_position_usd, 2.50, places=2)

    def test_min_target_order_floor_is_where_the_follower_share_reaches_the_venue_minimum(self):
        # A target averaging $50 draws a $3.00 copy order, a 6% participation rate,
        # so the smallest target order the follower can still mirror is $1.00 / 6%.
        self.assertAlmostEqual(
            CURRENT_PROFILE.min_target_order_floor_usd(50.0), 16.67, places=2
        )

    def test_min_target_order_floor_is_zero_when_the_target_size_is_unknown(self):
        self.assertEqual(CURRENT_PROFILE.min_target_order_floor_usd(0.0), 0.0)

    def test_the_current_profile_is_the_one_the_spec_states(self):
        self.assertEqual(CURRENT_PROFILE.bankroll_usd, 100.0)
        self.assertEqual(CURRENT_PROFILE.copy_ratio, 0.03)
        self.assertEqual(CURRENT_PROFILE.per_token_cap_usd, 5.0)
        self.assertEqual(CURRENT_PROFILE.global_cap_usd, 100.0)
        self.assertEqual(CURRENT_PROFILE.min_price, 0.05)
        self.assertEqual(CURRENT_PROFILE.max_price, 0.95)

    def test_a_profile_with_no_copy_ratio_is_refused_at_construction(self):
        # Rather than raising ZeroDivisionError deep inside the window derivation.
        with self.assertRaises(ValueError):
            CopyExecutionProfile(copy_ratio=0.0)

    def test_the_sizing_peak_is_the_midpoint_of_the_copyable_window(self):
        # Derived rather than stated, so it cannot be set to a figure the bot's
        # own caps contradict.
        self.assertAlmostEqual(CURRENT_PROFILE.sizing_fit_peak_usd, 100.0, places=2)

    def test_the_sizing_peak_follows_a_change_to_the_caps(self):
        # A hand-picked constant would have stayed put and quietly become wrong.
        lifted = CopyExecutionProfile(per_token_cap_usd=10.0, max_position_bankroll_fraction=0.10)
        self.assertGreater(lifted.sizing_fit_peak_usd, CURRENT_PROFILE.sizing_fit_peak_usd)
        self.assertAlmostEqual(
            lifted.sizing_fit_peak_usd,
            (lifted.window_min_usd + lifted.window_max_usd) / 2.0,
            places=2,
        )

    def test_the_sizing_peak_cannot_be_set_by_hand(self):
        with self.assertRaises(TypeError):
            CopyExecutionProfile(sizing_fit_peak_usd=25.0)

    def test_a_profile_cannot_be_mutated_after_construction(self):
        # Results are labelled with a fingerprint; a mutable profile would let the
        # label and the numbers drift apart mid-run.
        with self.assertRaises(Exception):
            CURRENT_PROFILE.bankroll_usd = 250.0


class TestPositionCapSweepProfile(unittest.TestCase):
    """A per-position cap sweep needs a profile whose stated cap is the one
    that binds — otherwise every level simulates the same $5 position."""

    def test_the_current_settings_are_reproduced_at_five_dollars(self):
        at_five = CURRENT_PROFILE.with_position_cap(5.0)
        self.assertAlmostEqual(at_five.max_single_position_usd, 5.00, places=2)
        self.assertAlmostEqual(at_five.window_min_usd, 33.33, places=2)
        self.assertAlmostEqual(at_five.window_max_usd, 166.67, places=2)

    def test_a_ten_dollar_cap_raises_the_binding_share_and_widens_the_window(self):
        # Raising only the per-token cap widens nothing (the 5% bankroll rule
        # binds at $5), so the sweep raises the bankroll share with the cap.
        at_ten = CURRENT_PROFILE.with_position_cap(10.0)
        self.assertAlmostEqual(at_ten.max_position_bankroll_fraction, 0.10, places=4)
        self.assertAlmostEqual(at_ten.max_single_position_usd, 10.00, places=2)
        self.assertAlmostEqual(at_ten.window_max_usd, 333.33, places=2)
        self.assertAlmostEqual(at_ten.copy_trade_usd, 3.00, places=2)

    def test_the_copy_order_is_unchanged_across_the_sweep(self):
        # The cap constrains the maximum position, not the routine copy size.
        for cap in (5.0, 10.0, 15.0, 20.0):
            self.assertAlmostEqual(
                CURRENT_PROFILE.with_position_cap(cap).copy_trade_usd, 3.00, places=2
            )

    def test_a_wider_cap_gets_its_own_fingerprint(self):
        # Each cap level must miss cache on its own, or a rescan would serve
        # the $5 result for every level.
        self.assertNotEqual(
            CURRENT_PROFILE.with_position_cap(5.0).fingerprint,
            CURRENT_PROFILE.with_position_cap(20.0).fingerprint,
        )

    def test_a_non_positive_cap_is_refused(self):
        with self.assertRaises(ValueError):
            CURRENT_PROFILE.with_position_cap(0.0)

    def test_a_non_positive_bankroll_cannot_derive_a_cap_profile(self):
        # With no bankroll no share makes the requested cap bind:
        # `max_single_position_usd` stays at the non-positive bankroll share,
        # so the derived profile would be labelled with a cap it never
        # applied. (CodeRabbit, PR #34.)
        from execution.copy_execution_profile import CopyExecutionProfile

        for bankroll in (0.0, -50.0):
            with self.assertRaises(ValueError):
                CopyExecutionProfile(bankroll_usd=bankroll).with_position_cap(10.0)

    def test_a_non_finite_cap_is_refused(self):
        # NaN passes a `<= 0` guard (comparisons with NaN are False) and would
        # silently produce NaN windows — the repo's non-finite discipline
        # (PR #28) applies here too.
        with self.assertRaises(ValueError):
            CURRENT_PROFILE.with_position_cap(float("nan"))
        with self.assertRaises(ValueError):
            CURRENT_PROFILE.with_position_cap(float("inf"))


if __name__ == "__main__":
    unittest.main()

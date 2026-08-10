#!/usr/bin/env python3
"""Phase 2 driven end to end over a fixture.

The scoring engine had three parameters that defaulted to full marks, and the
pipeline never supplied them. Every unit test passed, because every unit test
handed the engine a metrics dict with the fields already filled in. Only running
the phase against raw source data catches that, which is what these do.
"""
import json
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "app", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from pipeline.phase2_filter_targets import run_phase2_filter

# Parameters that must never be scored from a default. Each maps to the substring
# identifying its row in the engine's breakdown.
MEASURED_PARAMETERS = {
    "edge_to_friction": "Edge-to-Friction",
    "drawdown_depth": "Drawdown Depth",
    "copyable_window_share": "Copyable Window Share",
    "daily_green_rate": "Daily Green Rate",
}


def _rising_curve():
    """An equity curve with one modest, recoverable dip."""
    return json.dumps([0, 200, 400, 600, 560, 800, 1000, 1400, 1800, 2400])


def _daily_series(green_days, red_days):
    days = []
    for i in range(green_days + red_days):
        copy_pnl = 40.0 if i < green_days else -15.0
        days.append({
            "date": f"2026-08-{i + 1:02d}",
            "volume": 500.0,
            "trades": 3,
            "actual_pnl": 60.0,
            "bt_copy_pnl": copy_pnl,
        })
    return json.dumps(days)


def _profile(address, **overrides):
    """A wallet that clears every gate, so scoring can be read without rejection."""
    base = {
        "address": address,
        "name": "Fixture Trader",
        "actual_pnl": 4000.0,
        "copy_backtest_pnl": 3900.0,
        "hedged_pct": 0.0,
        "avg_profit_loss_ratio": 4.0,
        "r20_wr": 70.0,
        "r20_pnl": 900.0,
        "r20_slip": 2.0,
        "roi": 25.0,
        "avg_invest": 100.0,
        "markets_traded": 120,
        "polycop_site_score": 80.0,
        "buy_price": 0.45,
        "last_active": "2026-08-09 12:00",
        "all_pnl_json": _rising_curve(),
        "daily_stats_json": _daily_series(green_days=10, red_days=2),
    }
    base.update(overrides)
    return base


def _run(profiles):
    with tempfile.TemporaryDirectory() as tmp:
        in_file = os.path.join(tmp, "phase1.json")
        out_file = os.path.join(tmp, "phase2.json")
        with open(in_file, "w", encoding="utf-8") as f:
            json.dump({"timestamp": "2026-08-10T00:00:00Z", "profiles": profiles}, f)
        run_phase2_filter(in_file=in_file, out_file=out_file)
        with open(out_file, "r", encoding="utf-8") as f:
            return json.load(f)


def _points(target, needle):
    # Try stable id first, then the display labels.
    b = target["breakdown"]
    labels = target.get("breakdown_labels", {})
    if needle in b:
        return b[needle]
    for bid, lbl in labels.items():
        if needle in lbl:
            return b[bid]
    matched = [v for k, v in b.items() if needle in k]
    assert len(matched) == 1, f"expected one breakdown row matching {needle!r}, got {matched}"
    return matched[0]


class TestMeasuredParametersReachTheEngine(unittest.TestCase):
    def setUp(self):
        out = _run([_profile("0xmeasured")])
        self.assertEqual(len(out["verified_targets"]), 1, "fixture wallet was rejected")
        self.target = out["verified_targets"][0]

    def test_the_source_series_produce_a_measured_drawdown(self):
        self.assertIsNotNone(self.target["metrics"]["drawdown_depth"])
        self.assertGreater(_points(self.target, "Drawdown Depth"), 0.0)

    def test_the_source_series_produce_a_measured_green_rate(self):
        self.assertIsNotNone(self.target["metrics"]["days_win_rate"])
        self.assertEqual(self.target["metrics"]["observed_days"], 12)
        self.assertGreater(_points(self.target, "Daily Green Rate"), 0.0)

    def test_edge_to_friction_is_measured_against_the_profile_slippage(self):
        self.assertIsNotNone(self.target["metrics"]["edge_to_friction"])
        self.assertGreater(_points(self.target, "Edge-to-Friction"), 0.0)

    def test_the_green_rate_is_copy_adjusted_not_the_lifetime_win_rate(self):
        # The fixture's target-side profit is green every day; the copy-adjusted
        # figure is green on ten of twelve. Reading the wrong one gives 100.
        self.assertAlmostEqual(self.target["metrics"]["days_win_rate"], 83.33, places=1)


class TestWindowShareReachesTheEngineWhenSimulated(unittest.TestCase):
    """The other three parameters have source data on every wallet; this one
    only exists once a Simulated Copy Run has produced decision logs. Without a
    positive case, a wiring error that never yields a value looks identical to a
    wallet that legitimately has none."""

    def setUp(self):
        simulated = _profile(
            "0xsimulated",
            run_mock_response={
                "sim_total_pnl": 240.0,
                # Ten target entries, six of which the window admitted, plus
                # two exits that belong in neither term — see spike 0002.
                "logs": (
                    [{"type": "BUY", "action": "BUY",
                      "msg": "[m] Target BUY 10.00 shares @ $0.500."}] * 5
                    + [{"type": "WARNING", "action": "SKIP_CAP",
                        "msg": "[m] Target BUY 10.00 shares. Skipped: Hit Risk Cap Limits."}]
                    + [{"type": "INTERCEPT", "action": "SKIP_FILTER",
                        "msg": "[m] Target BUY 10.00 shares @ $0.500. Sim skipped: Target size out of bounds"}] * 4
                    + [{"type": "INTERCEPT", "action": "INTERCEPT",
                        "msg": "[m] Target SELL 10.00 shares. Sim inventory is 0. [INTERCEPTED] Ghost Position."}] * 2
                ),
            },
        )
        out = _run([simulated])
        self.assertEqual(len(out["verified_targets"]), 1, "fixture wallet was rejected")
        self.target = out["verified_targets"][0]

    def test_the_decision_logs_produce_a_measured_window_share(self):
        self.assertAlmostEqual(self.target["copyable_window_share"], 0.6, places=4)

    def test_the_measured_share_is_scored(self):
        # Six of ten entry signals were copyable, so six of ten points.
        self.assertAlmostEqual(_points(self.target, "Copyable Window Share"), 6.0, places=2)


class TestRecentFormWillNotAssumeFrictionlessExecution(unittest.TestCase):
    def test_a_wallet_with_no_slip_figure_scores_nothing_for_recent_form(self):
        # An absent cost used to arrive as zero, which is the best possible
        # reading, so profit earned through unknown friction scored full marks.
        blind = _profile("0xnoslip", r20_slip=None)
        target = _run([blind])["verified_targets"][0]
        self.assertIsNone(target["metrics"]["r20_slip"])
        self.assertEqual(_points(target, "Recent Form"), 0.0)


class TestAbsentRatioFieldsDoNotBecomeMeasuredZeroes(unittest.TestCase):
    def test_a_null_ratio_does_not_abort_the_run(self):
        target = _run([_profile("0xnullroi", roi=None)])["verified_targets"][0]
        self.assertIsNone(target["metrics"]["edge_to_friction"])
        self.assertEqual(_points(target, "Edge-to-Friction"), 0.0)

    def test_a_null_ratio_falls_through_to_the_next_field(self):
        target = _run([_profile("0xfallback", roi=None, pnl_to_volume_ratio=25.0)])["verified_targets"][0]
        self.assertIsNotNone(target["metrics"]["edge_to_friction"])
        self.assertGreater(_points(target, "Edge-to-Friction"), 0.0)


class TestUnmeasurableWalletsScoreNothing(unittest.TestCase):
    """The regression guard: a wallet with no source series must not score well."""

    def setUp(self):
        bare = _profile("0xbare", all_pnl_json=None, daily_stats_json=None, roi=0.0)
        out = _run([bare])
        self.assertEqual(len(out["verified_targets"]), 1, "fixture wallet was rejected")
        self.target = out["verified_targets"][0]

    def test_every_unmeasured_parameter_scores_zero(self):
        for label in MEASURED_PARAMETERS.values():
            with self.subTest(parameter=label):
                self.assertEqual(
                    _points(self.target, label),
                    0.0,
                    f"{label} scored on a default instead of a measurement",
                )

    def test_the_unmeasured_wallet_cannot_outrank_the_measured_one(self):
        measured = _run([_profile("0xmeasured")])["verified_targets"][0]
        self.assertLess(self.target["final_score"], measured["final_score"])

    def test_the_unmeasured_wallet_falls_below_a_passing_score(self):
        self.assertLess(self.target["final_score"], 50.0)


class TestTheScaleIsNotInflated(unittest.TestCase):
    def test_no_wallet_carries_a_constant_floor_of_free_points(self):
        # The defect gave every candidate 44 points before it had earned any.
        bare = _profile(
            "0xnothing",
            all_pnl_json=None,
            daily_stats_json=None,
            roi=0.0,
            r20_pnl=0.0,
            avg_invest=10.0,
            markets_traded=20,
            avg_profit_loss_ratio=0.3,
            hedged_pct=3.0,
        )
        target = _run([bare])["verified_targets"][0]
        self.assertLess(target["final_score"], 10.0)


if __name__ == "__main__":
    unittest.main()

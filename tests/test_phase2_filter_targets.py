#!/usr/bin/env python3
"""Phase 2 driven end to end over a fixture.

The scoring engine had three parameters that defaulted to full marks, and the
pipeline never supplied them. Every unit test passed, because every unit test
handed the engine a metrics dict with the fields already filled in. Only running
the phase against raw source data catches that, which is what these do.

The source is now the scanner's first-party record rather than the aggregator's
profile (ADR 0012), so the fixtures build records. The properties being
protected did not change: a parameter must be measured to score, an unmeasured
gate input must reject rather than pass, and a wallet nobody could measure must
never outrank one that was.
"""
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from execution.copy_execution_profile import CURRENT_PROFILE
from pipeline.phase2_filter_targets import run_phase2_filter

# Parameters that must never be scored from a default. Each maps to the substring
# identifying its row in the engine's breakdown.
MEASURED_PARAMETERS = {
    "edge_to_friction": "Edge-to-Friction",
    "drawdown_depth": "Drawdown Depth",
    "daily_green_rate": "Daily Green Rate",
}

DAY = 86400
FIRST_CLOSE = 1786000000


def _settled(results, first_close=FIRST_CLOSE):
    """Per-market results, one market per day, oldest first."""
    return [
        {
            "condition_id": f"0xc{i}",
            "result_usdc": float(value),
            "closed_at": first_close + i * DAY,
            "notional_usdc": 500.0,
        }
        for i, value in enumerate(results)
    ]


def _per_day(green_days, red_days, first_close=FIRST_CLOSE):
    """A copy-adjusted per-day result map, as the replay produces it."""
    days = {}
    for i in range(green_days + red_days):
        stamp = first_close + i * DAY
        key = datetime.datetime.fromtimestamp(
            stamp, datetime.timezone.utc
        ).strftime("%Y-%m-%d")
        days[key] = 40.0 if i < green_days else -15.0
    return days


# Ten wins of $400 and two losses of $100: a profit/loss ratio of 4.0, a
# recoverable dip in the equity curve, and twelve settled markets.
_WINNING_RESULTS = [400.0] * 4 + [-100.0] + [400.0] * 3 + [-100.0] + [400.0] * 3


def _record(address, **overrides):
    """A wallet that clears every gate, so scoring can be read without rejection."""
    settled_pnl = sum(_WINNING_RESULTS)
    base = {
        "address": address,
        "pseudonym": "Fixture Trader",
        "classification": "human",
        "bot_score": 1,
        "schema_version": 4,
        "profile_fingerprint": CURRENT_PROFILE.fingerprint,
        "scanned_at": FIRST_CLOSE + 20 * DAY,
        "last_trade_at": FIRST_CLOSE + 12 * DAY,
        "trades_7d": 9,
        "volume_7d": 4500.0,
        "active_days_7d": 5,
        "coverage_days": 60.0,
        "history_truncated": False,
        "settled_results": _settled(_WINNING_RESULTS),
        "settled_pnl_usdc": settled_pnl,
        # A 25% profit-to-volume ratio, which at the profile's 10% modelled
        # slippage is an Edge-to-Friction of 2.5.
        "traded_volume_usdc": settled_pnl * 4.0,
        "avg_position_usdc": 100.0,
        "distinct_markets": 120,
        "hedged_pct": 0.0,
        "copy_replay": {
            # A 2.5% Slippage Cost Rate against the target's own profit.
            "modelled_copy_pnl": round(settled_pnl * 0.975, 4),
            "per_day_copy_pnl": _per_day(green_days=10, red_days=2),
            "recent_window_target_pnl": 900.0,
            "recent_window_friction_pct": 2.0,
            "replayed_markets": 12,
        },
    }
    replay_overrides = overrides.pop("copy_replay", None)
    base.update(overrides)
    if replay_overrides is not None:
        base["copy_replay"] = dict(base["copy_replay"], **replay_overrides)
    return base


def _run(records, profiles=None):
    """Run the phase over a record set, discovering every record's address."""
    if profiles is None:
        profiles = [
            {"address": r["address"], "name": r.get("pseudonym", ""),
             "aggregator_opinion": 80.0}
            for r in records
        ]
    with tempfile.TemporaryDirectory() as tmp:
        in_file = os.path.join(tmp, "phase1.json")
        record_file = os.path.join(tmp, "scanned_wallets.json")
        out_file = os.path.join(tmp, "phase2.json")
        with open(in_file, "w", encoding="utf-8") as f:
            json.dump({"timestamp": "2026-08-10T00:00:00Z", "profiles": profiles}, f)
        with open(record_file, "w", encoding="utf-8") as f:
            json.dump({r["address"]: r for r in records}, f)
        run_phase2_filter(in_file=in_file, out_file=out_file, record_file=record_file)
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
        out = _run([_record("0xmeasured")])
        self.assertEqual(len(out["verified_targets"]), 1, "fixture wallet was rejected")
        self.target = out["verified_targets"][0]

    def test_the_settled_results_produce_a_measured_drawdown(self):
        self.assertIsNotNone(self.target["metrics"]["drawdown_depth"])
        self.assertGreater(_points(self.target, "Drawdown Depth"), 0.0)

    def test_the_replay_produces_a_measured_green_rate(self):
        self.assertIsNotNone(self.target["metrics"]["days_win_rate"])
        self.assertEqual(self.target["metrics"]["observed_days"], 12)
        self.assertGreater(_points(self.target, "Daily Green Rate"), 0.0)

    def test_edge_to_friction_is_measured_against_the_profile_slippage(self):
        self.assertIsNotNone(self.target["metrics"]["edge_to_friction"])
        self.assertGreater(_points(self.target, "Edge-to-Friction"), 0.0)

    def test_the_green_rate_is_copy_adjusted_not_the_lifetime_win_rate(self):
        # The wallet won ten of its twelve markets outright, and the copy is
        # green on ten of twelve days. Reading the target's own result instead
        # of the replay's is what this figure must not do.
        self.assertAlmostEqual(self.target["metrics"]["days_win_rate"], 83.33, places=1)

    def test_the_record_states_how_much_history_it_measured(self):
        # A figure measured over six hours must not be silently compared with
        # one measured over four months (ADR 0012).
        self.assertEqual(self.target["metrics"]["coverage_days"], 60.0)
        self.assertIs(self.target["metrics"]["history_truncated"], False)


class TestTheAggregatorReachesNothingButTheGemComparison(unittest.TestCase):
    """ADR 0012: the aggregator supplies addresses, and every judgment is
    derived from first-party fills."""

    def test_the_aggregator_opinion_does_not_gate_or_score(self):
        # A wallet the aggregator rates at zero still scores on its own fills.
        profiles = [{"address": "0xmeasured", "name": "x", "aggregator_opinion": 0.0}]
        out = _run([_record("0xmeasured")], profiles=profiles)
        self.assertEqual(len(out["verified_targets"]), 1)
        target = out["verified_targets"][0]
        self.assertEqual(target["metrics"]["aggregator_opinion"], 0.0)
        self.assertGreater(target["final_score"], 0.0)

    def test_a_low_aggregator_opinion_on_a_strong_wallet_is_a_hidden_gem(self):
        profiles = [{"address": "0xmeasured", "name": "x", "aggregator_opinion": 10.0}]
        out = _run([_record("0xmeasured")], profiles=profiles)
        target = out["verified_targets"][0]
        self.assertIs(target["is_hidden_gem"], True)

    def test_an_unscanned_address_is_pending_not_rejected(self):
        # Absence of a measurement is not evidence about the wallet.
        profiles = [{"address": "0xunscanned", "name": "x", "aggregator_opinion": 90.0}]
        out = _run([], profiles=profiles)
        self.assertEqual(out["verified_targets"], [])
        self.assertEqual(out["rejected_disqualified_count"], 0)
        self.assertEqual(out["pending_measurement_count"], 1)

    def test_a_record_measured_under_another_profile_is_held_not_scored(self):
        stale = _record("0xstale", profile_fingerprint="0" * 64)
        out = _run([stale])
        self.assertEqual(out["verified_targets"], [])
        self.assertEqual(out["rejected_disqualified_count"], 0)
        self.assertEqual(out["stale_profile_count"], 1)


class TestWindowShareIsSimulationOnly(unittest.TestCase):
    """ADR 0006: a stale run_mock payload on a record must not feed triage.

    Copyable Window Share moved off the triage table because no pre-simulation
    source can measure it; the value only exists after Phase 3 simulates the
    wallet. If a record ever carries a leftover `run_mock_response` (the PR #22
    footgun), the triage phase must ignore it - a stale simulation result
    silently scoring ten points is exactly the wrong answer this prevents.
    """

    def setUp(self):
        simulated = _record(
            "0xstalemock",
            run_mock_response={
                "sim_total_pnl": 240.0,
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

    def test_a_stale_run_mock_payload_does_not_score_at_triage(self):
        self.assertNotIn("window_share", self.target["breakdown"])
        self.assertNotIn("Copyable Window Share",
                         self.target.get("breakdown_labels", {}).values())

    def test_the_phase_two_record_carries_no_window_share_field(self):
        self.assertNotIn("copyable_window_share", self.target)


class TestRecentFormWillNotAssumeFrictionlessExecution(unittest.TestCase):
    def test_a_wallet_with_no_slip_figure_scores_nothing_for_recent_form(self):
        # An absent cost used to arrive as zero, which is the best possible
        # reading, so profit earned through unknown friction scored full marks.
        blind = _record("0xnoslip", copy_replay={"recent_window_friction_pct": None})
        target = _run([blind])["verified_targets"][0]
        self.assertIsNone(target["metrics"]["r20_slip"])
        self.assertEqual(_points(target, "Recent Form"), 0.0)


class TestAbsentRatioFieldsDoNotBecomeMeasuredZeroes(unittest.TestCase):
    def test_an_unmeasured_volume_does_not_abort_the_run(self):
        target = _run([_record("0xnovol", traded_volume_usdc=None)])["verified_targets"][0]
        self.assertIsNone(target["metrics"]["edge_to_friction"])
        self.assertEqual(_points(target, "Edge-to-Friction"), 0.0)

    def test_a_zero_volume_is_unmeasurable_not_infinite_edge(self):
        target = _run([_record("0xzerovol", traded_volume_usdc=0.0)])["verified_targets"][0]
        self.assertIsNone(target["metrics"]["edge_to_friction"])
        self.assertEqual(_points(target, "Edge-to-Friction"), 0.0)


class TestUnmeasurableWalletsScoreNothing(unittest.TestCase):
    """The regression guard: a wallet with no source series must not score well."""

    def setUp(self):
        # Four settled markets: enough to measure a profit/loss ratio, too few
        # for an equity curve to describe a track record. No per-day replay, and
        # a volume so large the edge rounds away.
        bare = _record(
            "0xbare",
            settled_results=_settled([400.0, 400.0, -100.0, 400.0]),
            settled_pnl_usdc=1100.0,
            traded_volume_usdc=1.0e9,
            copy_replay={"per_day_copy_pnl": None, "modelled_copy_pnl": 1072.5},
        )
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
        measured = _run([_record("0xmeasured")])["verified_targets"][0]
        self.assertLess(self.target["final_score"], measured["final_score"])

    def test_the_unmeasured_wallet_falls_below_a_passing_score(self):
        self.assertLess(self.target["final_score"], 50.0)


class TestTheScaleIsNotInflated(unittest.TestCase):
    def test_no_wallet_carries_a_constant_floor_of_free_points(self):
        # The defect gave every candidate 44 points before it had earned any.
        # The only nonzero component left for this wallet is Slippage Cost Rate,
        # which its actual and modelled copy PnL genuinely measure, so the
        # honest total is a small fraction of the scale.
        #
        # A first loss deeper than every later gain leaves the equity curve
        # having given back everything it ever had, which is what a zero-scoring
        # drawdown means; the same shape puts the profit/loss ratio at the gate.
        results = [30.0, -100.0, 30.0, 30.0, 30.0, 30.0]
        bare = _record(
            "0xnothing",
            settled_results=_settled(results),
            settled_pnl_usdc=sum(results),
            traded_volume_usdc=1.0e9,
            avg_position_usdc=10.0,
            distinct_markets=25,
            hedged_pct=3.0,
            copy_replay={
                "per_day_copy_pnl": None,
                "modelled_copy_pnl": round(sum(results) * 0.975, 4),
                "recent_window_target_pnl": 0.0,
            },
        )
        target = _run([bare])["verified_targets"][0]
        for label in MEASURED_PARAMETERS.values():
            self.assertEqual(_points(target, label), 0.0)
        # The only earned points are Slippage Cost Rate: 2.5% of the way through
        # a ramp that pays 17 points at 1% and nothing at the 5% gate.
        self.assertAlmostEqual(target["final_score"], 10.63, places=1)


class TestAnUnmeasuredFigureDoesNotAbortThePhase(unittest.TestCase):
    """A present-but-null figure must score as unmeasured, not crash the run.

    ADR 0007 requires a figure the source could not supply to stay absent
    rather than arrive as a measured zero. Nothing exercised this while the
    leaderboard was the source, because it filled every field in. A first-party
    source measures each figure independently and leaves absent whatever its
    window could not cover, so it emits exactly the shape these assert on: one
    null figure among valid ones.
    """

    # Every record field that reaches a figure the engine reads.
    NULLABLE_RECORD_FIELDS = (
        "settled_pnl_usdc",
        "hedged_pct",
        "settled_results",
        "avg_position_usdc",
        "distinct_markets",
        "traded_volume_usdc",
    )

    NULLABLE_REPLAY_FIELDS = (
        "modelled_copy_pnl",
        "recent_window_target_pnl",
        "recent_window_friction_pct",
        "per_day_copy_pnl",
    )

    def _assert_reaches_a_verdict(self, record, field):
        try:
            scan = _run([record])
        except TypeError as exc:
            self.fail(
                f"a null {field} aborted the phase instead of scoring "
                f"as unmeasured: {exc}"
            )
        accounted = (len(scan["verified_targets"])
                     + scan["rejected_disqualified_count"])
        self.assertEqual(accounted, 1)

    def test_a_null_figure_in_any_field_does_not_raise(self):
        """Every wallet reaches a verdict - passed or rejected, never a crash."""
        for field in self.NULLABLE_RECORD_FIELDS:
            with self.subTest(field=field):
                self._assert_reaches_a_verdict(
                    _record("0x" + field[:8], **{field: None}), field
                )
        for field in self.NULLABLE_REPLAY_FIELDS:
            with self.subTest(field=field):
                self._assert_reaches_a_verdict(
                    _record("0x" + field[:8], copy_replay={field: None}), field
                )

    def test_an_unmeasured_gate_input_rejects_rather_than_passing(self):
        """A gate cannot be cleared by a figure nobody measured.

        Failing closed is the conservative reading: the alternative admits a
        wallet precisely because the evidence that would disqualify it is the
        evidence that is missing.
        """
        scan = _run([_record("0xnullpl", settled_results=None)])
        self.assertEqual(scan["verified_targets"], [])
        self.assertEqual(scan["rejected_disqualified_count"], 1)

    def test_an_unmeasured_copy_pnl_rejects_as_unmeasured_not_as_toxic(self):
        scan = _run([_record("0xnullcopy", copy_replay={"modelled_copy_pnl": None})])
        self.assertEqual(scan["verified_targets"], [])
        self.assertEqual(scan["rejected_disqualified_count"], 1)

    def test_an_unmeasured_scored_input_costs_its_points_not_the_wallet(self):
        """A figure that only scores, and never gates, must not disqualify."""
        record = _record("0xnullr20", copy_replay={"recent_window_target_pnl": None})
        target = _run([record])["verified_targets"][0]
        self.assertEqual(_points(target, "Recent Form"), 0.0)

    def test_a_wallet_scored_on_nulls_cannot_outrank_a_fully_measured_one(self):
        measured = _record("0xmeasured")
        partial = _record("0xpartial", copy_replay={"recent_window_target_pnl": None})
        scan = _run([measured, partial])
        by_address = {t["address"]: t for t in scan["verified_targets"]}
        self.assertLess(
            by_address["0xpartial"]["final_score"],
            by_address["0xmeasured"]["final_score"],
        )


if __name__ == "__main__":
    unittest.main()

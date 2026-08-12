#!/usr/bin/env python3
"""The scanner record, read as engine metrics.

The adapter is the one place that knows the record's shape, so this is where a
renamed field must fail. The contract test below asserts against the engine's
own input list: a scored parameter added without a first-party source should
break here rather than score silently on a default.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from execution.copy_execution_profile import CURRENT_PROFILE
from pipeline.first_party_adapter import (
    RECORD_ANNOTATIONS,
    first_party_activity,
    to_engine_metrics,
)

DAY = 86400
FIRST_CLOSE = 1786000000

# Every figure `calculate_bankroll_optimized_score` reads out of its metrics
# dict. Kept here as the contract the adapter owes the engine.
ENGINE_INPUTS = (
    "actual_pnl",
    "copy_pnl",
    "hedged_pct",
    "pl_ratio",
    "days_win_rate",
    "observed_days",
    "r20_pnl",
    "r20_slip",
    "pnl_vol_ratio",
    "avg_invest",
    "markets",
    "drawdown_depth",
    "edge_to_friction",
)

# The aggregator field names that must never reappear on a scoring path.
AGGREGATOR_FIELDS = (
    "polycop_site_score",
    "copy_backtest_pnl",
    "avg_profit_loss_ratio",
    "r20_wr",
    "daily_stats_json",
    "all_pnl_json",
    "markets_traded",
)


def _record(**overrides):
    base = {
        "address": "0xtest",
        "pseudonym": "Fixture",
        "classification": "human",
        "bot_score": 2,
        "profile_fingerprint": CURRENT_PROFILE.fingerprint,
        "scanned_at": FIRST_CLOSE + 10 * DAY,
        "last_trade_at": FIRST_CLOSE + 9 * DAY,
        "trades_7d": 12,
        "volume_7d": 900.0,
        "active_days_7d": 4,
        "coverage_days": 45.0,
        "history_truncated": False,
        "settled_results": [
            {"condition_id": f"0xc{i}", "result_usdc": 100.0 if i % 4 else -50.0,
             "closed_at": FIRST_CLOSE + i * DAY, "notional_usdc": 200.0}
            for i in range(8)
        ],
        "settled_pnl_usdc": 500.0,
        "traded_volume_usdc": 2000.0,
        "avg_position_usdc": 90.0,
        "distinct_markets": 40,
        "hedged_pct": 1.0,
        "copy_replay": {
            "modelled_copy_pnl": 480.0,
            "per_day_copy_pnl": {"2026-08-01": 30.0, "2026-08-02": -5.0},
            "recent_window_target_pnl": 250.0,
            "recent_window_friction_pct": 6.0,
            "replayed_markets": 8,
        },
    }
    replay = overrides.pop("copy_replay", None)
    base.update(overrides)
    if replay is not None:
        base["copy_replay"] = dict(base["copy_replay"], **replay)
    return base


def _metrics(**overrides):
    return to_engine_metrics(_record(**overrides), CURRENT_PROFILE.slippage_pct)["raw_metrics"]


def test_every_engine_input_is_supplied():
    metrics = _metrics()
    for key in ENGINE_INPUTS:
        assert key in metrics, f"the engine reads {key} and the adapter does not supply it"


def test_no_aggregator_field_reaches_the_engine():
    metrics = _metrics()
    for field in AGGREGATOR_FIELDS:
        assert field not in metrics


def test_the_measured_record_produces_measured_figures():
    metrics = _metrics()
    for key in ("actual_pnl", "copy_pnl", "pl_ratio", "edge_to_friction",
                "drawdown_depth", "days_win_rate"):
        assert metrics[key] is not None, f"{key} was not measured from a complete record"


def test_an_absent_measurement_stays_absent_rather_than_becoming_zero():
    """The leaderboard adapter defaults `copy_pnl` to -1.0 because the
    leaderboard fills every field. A source that measures each figure
    independently must not inherit that default."""
    metrics = _metrics(copy_replay={"modelled_copy_pnl": None})
    assert metrics["copy_pnl"] is None


def test_a_record_with_no_settled_markets_measures_no_ratio_or_curve():
    metrics = _metrics(settled_results=[])
    assert metrics["pl_ratio"] is None
    assert metrics["drawdown_depth"] is None


def test_an_unmeasured_volume_leaves_the_edge_unmeasured():
    metrics = _metrics(traded_volume_usdc=None)
    assert metrics["pnl_vol_ratio"] is None
    assert metrics["edge_to_friction"] is None


def test_the_annotations_are_carried_beside_the_metrics_not_inside_them():
    """`bot_score` is an uncalibrated proxy and is not permitted to gate or to
    score, so it must not be reachable as an engine input."""
    out = to_engine_metrics(_record(), CURRENT_PROFILE.slippage_pct)
    for key in RECORD_ANNOTATIONS:
        assert key in out["annotations"]
        assert key not in out["raw_metrics"]


def test_the_adapter_returns_the_contract_phase_two_reads():
    """The keys the phase destructures, so a dropped one fails here rather than
    with a KeyError halfway through a scan."""
    out = to_engine_metrics(_record(), CURRENT_PROFILE.slippage_pct)
    for key in ("raw_metrics", "sim_summary", "green_rate", "observed_days",
                "drawdown_depth", "edge_to_friction", "annotations"):
        assert key in out


# ----------------------------------------------------------------- activity

def test_activity_is_aged_against_the_scan_not_the_read():
    activity = first_party_activity(_record())
    # The last fill landed a day before the scan instant.
    assert activity["hours_since_active"] == 24.0
    assert activity["activity_bucket"] == "d3"


def test_activity_counts_green_days_from_the_copy_not_the_target():
    activity = first_party_activity(_record())
    assert activity["green_days_7d"] == 1
    assert activity["trading_days"] == 2


def test_a_wallet_that_never_traded_has_an_unknown_recency():
    activity = first_party_activity(_record(last_trade_at=None))
    assert activity["hours_since_active"] is None
    assert activity["activity_bucket"] == "unknown"

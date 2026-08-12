#!/usr/bin/env python3
"""The scanner's record, read as engine metrics.

The one place that knows the shape of a scanner record. Everything else asks
for engine metrics, so a renamed field fails here instead of silently
defaulting across the pipeline.

It replaces the aggregator adapter, and is deliberately not a copy of it. That
module carried defaults - a copy PnL of -1.0, a site score of 0.0 - because the
aggregator filled every field on every profile, so an absent key there meant the
endpoint had changed. A source that measures each figure independently sends
absent for the ordinary reason that the measurement could not be made, and
substituting a default would state a number nobody took. Every figure here is
either measured or None (ADR 0007, ADR 0012).
"""
from typing import Any, Dict, Optional

from screener.derived_metrics import (
    calculate_drawdown_depth,
    calculate_edge_to_friction,
)
from screener.first_party_copy_replay import daily_green_rate
from screener.first_party_metrics import (
    equity_curve,
    pnl_to_volume_ratio,
    profit_loss_ratio,
)
from screener.activity import bucket_for_hours
from screener.simulated_copy_run import parse_simulated_run_response

# The record annotations a reader needs to judge how much a record is worth,
# carried beside the metrics rather than inside them so they cannot be mistaken
# for scored inputs. `bot_score` in particular is an uncalibrated proxy and is
# not permitted to gate or to score (ADR 0012).
RECORD_ANNOTATIONS = (
    "classification",
    "bot_score",
    "history_truncated",
    "coverage_days",
    "profile_fingerprint",
)


def _measured(value) -> Optional[float]:
    """A figure the scanner measured, or None when it could not.

    Zero passes through as zero: a measured break-even is a result, and only
    an absent measurement is absent.
    """
    if value is None:
        return None
    try:
        parsed = float(value)
    except (ValueError, TypeError):
        return None
    return parsed if parsed == parsed else None


def _replay(record: Dict[str, Any]) -> Dict[str, Any]:
    replay = record.get("copy_replay")
    return replay if isinstance(replay, dict) else {}


def first_party_activity(record: Dict[str, Any]) -> Dict[str, Any]:
    """Is this wallet still trading, measured from its own fills?

    The same block shape `screener.activity.compute_activity` builds from the
    aggregator's `last_active` string and rolling day series, from first-party
    evidence instead. Ages are measured against the scan instant, not read
    time, so a cached dataset never claims a trader went quiet while it sat on
    disk (CONTEXT.md, Activity Recency).

    Green days come from the copy replay's per-day results, so the figure means
    what the Daily Green Rate parameter means by it: a day a follower finished
    up, not a day the target did.
    """
    last_trade_at = record.get("last_trade_at")
    scanned_at = record.get("scanned_at")
    hours_since = None
    if last_trade_at and scanned_at:
        hours_since = max(0.0, (float(scanned_at) - float(last_trade_at)) / 3600.0)

    per_day = _replay(record).get("per_day_copy_pnl") or {}
    green_days = sum(
        1 for value in per_day.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
    )

    return {
        "last_active": last_trade_at,
        "hours_since_active": round(hours_since, 2) if hours_since is not None else None,
        "activity_bucket": bucket_for_hours(hours_since),
        "trades_7d": record.get("trades_7d"),
        "volume_7d": record.get("volume_7d"),
        "active_days_7d": record.get("active_days_7d"),
        "green_days_7d": green_days,
        # The days the record could measure a result on, which is what the
        # score's minimum-observed-days floor counts.
        "trading_days": len(per_day),
    }


def to_engine_metrics(record: Dict[str, Any], slippage_pct: float) -> Dict[str, Any]:
    """Measure one scanner record into the engine's metric shape.

    Returns the `raw_metrics` dict the engine consumes plus the intermediate
    measurements the scan record also needs, so the phase that calls it does
    not have to know where any single figure came from.
    """
    settled_results = record.get("settled_results") or []
    replay = _replay(record)

    green_rate, observed_days = daily_green_rate(replay.get("per_day_copy_pnl"))
    drawdown_depth = calculate_drawdown_depth(equity_curve(settled_results))
    pnl_vol_ratio = pnl_to_volume_ratio(
        record.get("settled_pnl_usdc"), record.get("traded_volume_usdc")
    )
    edge_to_friction = calculate_edge_to_friction(pnl_vol_ratio, slippage_pct)

    mock_payload = record.get("run_mock_response") or record.get("mock_data")
    sim_summary = parse_simulated_run_response(mock_payload) if mock_payload else None

    raw_metrics = {
        "actual_pnl": _measured(record.get("settled_pnl_usdc")),
        # The Modelled Copy PnL, replayed from this wallet's own fills rather
        # than taken on trust from an aggregator.
        "copy_pnl": _measured(replay.get("modelled_copy_pnl")),
        "hedged_pct": _measured(record.get("hedged_pct")),
        "pl_ratio": profit_loss_ratio(settled_results),
        "days_win_rate": green_rate,
        "observed_days": observed_days,
        # The target's own profit over the recent window, which is what Recent
        # Form scores as a return on the target's deployed capital, and what
        # the Divergence gate reads.
        "r20_pnl": _measured(replay.get("recent_window_target_pnl")),
        # The friction that window's profit came through, as a share of the
        # capital the copy turned over.
        "r20_slip": _measured(replay.get("recent_window_friction_pct")),
        "pnl_vol_ratio": pnl_vol_ratio,
        "avg_invest": _measured(record.get("avg_position_usdc")),
        # Track Record Length and Markets Sample both ask how many markets this
        # wallet has traded, not how many produced a scoreable result: a record
        # is deep because the wallet traded widely, and holding an unresolved
        # market against it would measure the calendar rather than the trader.
        "markets": _measured(record.get("distinct_markets")),
        "drawdown_depth": drawdown_depth,
        "edge_to_friction": edge_to_friction,
    }

    return {
        "raw_metrics": raw_metrics,
        "sim_summary": sim_summary,
        "green_rate": green_rate,
        "observed_days": observed_days,
        "drawdown_depth": drawdown_depth,
        "edge_to_friction": edge_to_friction,
        "annotations": {
            key: record.get(key) for key in RECORD_ANNOTATIONS if key in record
        },
    }

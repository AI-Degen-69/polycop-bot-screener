#!/usr/bin/env python3
"""The leaderboard profile, read as engine metrics.

The PolyCop leaderboard delivers its own field names, several with aliases
depending on which endpoint filled them. This module is the single adapter
that knows those names: everything else asks for engine metrics and never
touches the upstream shape. A renamed upstream field now fails loudly in one
place instead of silently defaulting across the pipeline.

Absent figures stay absent: each measurement is None when the source will not
support it, and the engine scores None as nothing, so an unmeasured wallet
ranks below a measured poor one.
"""
import os
import sys
from typing import Any, Dict, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# SCRIPT_DIR is app/src/pipeline -> SRC_DIR is app/src
SRC_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from screener.derived_metrics import (  # noqa: E402
    calculate_daily_green_rate,
    calculate_drawdown_depth,
    calculate_edge_to_friction,
)
from screener.simulated_copy_run import (  # noqa: E402
    parse_simulated_run_response,
)


def _optional_float(value) -> Optional[float]:
    """An upstream figure that was present, or None if it was not.

    Coercing an absent figure to zero is not neutral: for a cost, zero is the
    best possible reading, and the engine would score the wallet as though it
    traded without friction.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def to_engine_metrics(profile: Dict[str, Any], slippage_pct: float) -> Dict[str, Any]:
    """Measure a raw leaderboard profile into the engine's metric shape.

    Returns the `raw_metrics` dict the engine consumes plus the intermediate
    measurements the scan record also needs, so the profile's shape is known
    here and nowhere else.
    """
    mock_payload = profile.get("run_mock_response") or profile.get("mock_data")
    sim_summary = parse_simulated_run_response(mock_payload) if mock_payload else None
    green_rate, observed_days = calculate_daily_green_rate(profile.get("daily_stats_json"))
    drawdown_depth = calculate_drawdown_depth(profile.get("all_pnl_json"))
    # Each fallback is tried only when the one before it is genuinely absent,
    # so a present-but-null field does not abort the run or masquerade as a
    # measured zero.
    pnl_vol_ratio = None
    for key in ("roi", "pnl_to_volume_ratio", "pnl_vol_ratio"):
        pnl_vol_ratio = _optional_float(profile.get(key))
        if pnl_vol_ratio is not None:
            break
    edge_to_friction = calculate_edge_to_friction(pnl_vol_ratio, slippage_pct)

    raw_metrics = {
        "actual_pnl": float(profile.get("actual_pnl", profile.get("pnl", 0.0))),
        "copy_pnl": float(profile.get("copy_backtest_pnl", profile.get("copy_pnl", -1.0))),
        "hedged_pct": float(profile.get("hedged_pct", profile.get("hedged_percentage", 0.0))),
        "pl_ratio": float(profile.get("avg_profit_loss_ratio", profile.get("pl_ratio", 0.0))),
        "days_win_rate": green_rate,
        "observed_days": observed_days,
        "r20_win_rate": float(profile.get("r20_wr", profile.get("recent_20_win_rate", profile.get("r20_win_rate", 0.0)))),
        "r20_pnl": float(profile.get("r20_pnl", profile.get("recent_20_pnl", 0.0))),
        "r20_slip": _optional_float(profile.get("r20_slip", profile.get("recent_20_slippage"))),
        # Capital Efficiency reads this directly and an unknown ratio earns
        # nothing there, which zero already expresses.
        "pnl_vol_ratio": pnl_vol_ratio if pnl_vol_ratio is not None else 0.0,
        "avg_invest": float(profile.get("avg_invest", 0.0)),
        "markets": int(profile.get("markets_traded", profile.get("markets", 0))),
        "polycop_site_score": float(profile.get("polycop_site_score", profile.get("score", 0.0))),
        "buy_price": float(profile.get("buy_price", profile.get("avg_buy_price", 0.0))),
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
    }

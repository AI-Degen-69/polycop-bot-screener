#!/usr/bin/env python3
"""Parameters measured from the leaderboard's raw series rather than read off it.

Every function here returns None when its input is missing or unusable. None is
not the same as zero: zero is a measured verdict, None means nothing was
measured. Scoring turns None into no points, so a wallet we could not measure
ranks below one we measured badly, rather than above it.
"""
import json
from typing import Any, Optional, Tuple

# Fewer points than this and a curve describes an incident, not a track record.
MIN_EQUITY_CURVE_POINTS = 6


def _load(raw: Any) -> Optional[Any]:
    """Parse a field the leaderboard delivers as a JSON string, or give up quietly.

    The upstream shape is not under our control, so a malformed series is an
    unmeasured wallet rather than a crashed scan.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def calculate_drawdown_depth(all_pnl_json: Any) -> Optional[float]:
    """Deepest peak-to-trough fall in cumulative profit, as a share of the peak.

    Expressed as a share so it carries across account sizes: the shape of the
    fall is what transfers to a follower, not its dollar size. Measured against
    the running peak, so a later shallow dip cannot mask an earlier collapse.
    """
    curve = _load(all_pnl_json)
    if not isinstance(curve, list) or len(curve) < MIN_EQUITY_CURVE_POINTS:
        return None

    try:
        values = [float(v) for v in curve]
    except (ValueError, TypeError):
        return None

    peak = values[0]
    deepest = 0.0
    for value in values:
        peak = max(peak, value)
        deepest = max(deepest, peak - value)

    highest = max(values)
    if highest <= 0:
        # A share of a non-positive peak says nothing about how far the wallet fell.
        return None
    return deepest / highest


def calculate_daily_green_rate(daily_stats_json: Any) -> Tuple[Optional[float], int]:
    """Share of observed days that ended green for a copier, and how many days that was.

    Judged on the copy-adjusted figure, not the target's own profit: a day the
    target finished up but a follower finished down is not a green day for the
    follower. Flat days count as observed but not green, since a day that
    returned nothing is not evidence of edge.

    Returns the rate as a percentage alongside the observed-day count, so the
    caller can refuse to score a rate drawn from too few days.
    """
    series = _load(daily_stats_json)
    if not isinstance(series, list) or not series:
        return None, 0

    observed = 0
    green = 0
    for day in series:
        if not isinstance(day, dict):
            continue
        try:
            copy_pnl = float(day.get("bt_copy_pnl", 0.0))
        except (ValueError, TypeError):
            continue
        observed += 1
        if copy_pnl > 0:
            green += 1

    if observed == 0:
        return None, 0
    return (green / observed) * 100.0, observed


def calculate_edge_to_friction(
    pnl_volume_ratio_pct: Optional[float],
    slippage_pct: float,
) -> Optional[float]:
    """The target's edge divided by the friction of copying it.

    Both sides are shares of traded volume, which is what makes them comparable.
    The leaderboard's profit-to-volume ratio is the edge per dollar that changed
    hands; assumed slippage is charged on every dollar that changes hands, so it
    is the friction per dollar on the same denominator.

    A ratio of one is break-even: the edge is exactly consumed by the cost of
    following it. Below one the wallet cannot be copied profitably however good
    it looks, which is why scoring treats one as the floor rather than the
    middle.
    """
    if pnl_volume_ratio_pct is None:
        return None
    if slippage_pct is None or slippage_pct <= 0:
        # Without an assumed friction there is nothing to compare the edge against.
        return None
    try:
        edge = float(pnl_volume_ratio_pct)
    except (ValueError, TypeError):
        return None
    if edge <= 0:
        # A wallet that did not make money has no edge to weigh against friction.
        return 0.0
    return edge / float(slippage_pct)

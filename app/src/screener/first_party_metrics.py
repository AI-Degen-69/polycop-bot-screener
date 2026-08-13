#!/usr/bin/env python3
"""Engine parameters derived from a wallet's own fills and positions.

`derived_metrics.py` measures the parameters the aggregator delivered as raw
series - a lifetime equity curve, a rolling per-day record. This module produces
those same series from first-party evidence instead, so the arithmetic
downstream of them does not change: the equity curve built here is handed to
`derived_metrics.calculate_drawdown_depth` exactly as the aggregator's was.

Every function returns None when its input cannot support a measurement. None
is not zero. For a cost, zero is the best possible reading, and for a ratio it
is a claim; either would hand a wallet points nothing measured (ADR 0007).
"""
from typing import Any, Dict, List, Optional, Sequence

# Below this, an opposite holding is settlement dust rather than a hedge.
# Polymarket positions carry fractional share counts from partial fills and
# rounding, and a wallet left holding 0.4 shares of the losing side of a
# resolved market is not making a market. Chosen an order of magnitude under
# the venue's own $1 minimum order, so nothing a wallet could deliberately
# trade falls below it.
HEDGE_DUST_SHARES = 0.5


def _results(settled_results: Optional[Sequence[Dict[str, Any]]]) -> List[float]:
    """The per-market USDC results, in the order the record stored them.

    The record is written close-time ordered by the scanner; this does not
    re-sort, because a caller handing over an unordered list has a bug the
    curve should expose rather than quietly repair.
    """
    if not settled_results:
        return []
    values = []
    for entry in settled_results:
        if not isinstance(entry, dict):
            continue
        value = entry.get("result_usdc")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def equity_curve(settled_results: Optional[Sequence[Dict[str, Any]]]) -> Optional[List[float]]:
    """Cumulative profit after each settled market, oldest first.

    The series `calculate_drawdown_depth` expects. Returns None on no input
    rather than an empty curve; that function applies its own minimum-points
    floor, so a curve too short to describe a track record is refused there,
    in the one place that owns what "too short" means.
    """
    values = _results(settled_results)
    if not values:
        return None
    curve = []
    running = 0.0
    for value in values:
        running += value
        curve.append(round(running, 4))
    return curve


def profit_loss_ratio(settled_results: Optional[Sequence[Dict[str, Any]]]) -> Optional[float]:
    """Average win divided by average loss, in absolute dollars.

    None when either side has no observations. A wallet that has never lost has
    an undefined ratio, not an infinite one, and the difference matters: this
    figure is a hard gate, and an infinity would pass it on no evidence.
    """
    values = _results(settled_results)
    wins = [v for v in values if v > 0]
    losses = [-v for v in values if v < 0]
    if not wins or not losses:
        return None
    avg_win = sum(wins) / len(wins)
    avg_loss = sum(losses) / len(losses)
    if avg_loss <= 0:
        return None
    return round(avg_win / avg_loss, 4)


def pnl_to_volume_ratio(settled_pnl_usdc, traded_volume_usdc) -> Optional[float]:
    """Profit as a percentage of every dollar that changed hands.

    The edge term of Edge-to-Friction, on the denominator that makes it
    comparable to a slippage rate: friction is charged per dollar traded, so
    the edge has to be expressed per dollar traded too.

    A percentage rather than a fraction, because `calculate_edge_to_friction`
    divides it by a slippage figure already expressed in percent.
    """
    if settled_pnl_usdc is None or traded_volume_usdc is None:
        return None
    try:
        pnl = float(settled_pnl_usdc)
        volume = float(traded_volume_usdc)
    except (ValueError, TypeError):
        return None
    if volume <= 0:
        return None
    return round(pnl / volume * 100.0, 6)


def hedged_rate(positions: Optional[Sequence[Dict[str, Any]]]) -> Optional[float]:
    """Share of markets where the wallet held more than one outcome at once.

    The Hedged Rate, measured directly instead of read off an aggregator field
    nobody could check. Holding both sides of a market at the same time is the
    market-making signature the gate exists to catch, and it is also a doubling
    of the legs on which a follower pays friction.

    None on an empty positions feed: a feed that returned nothing is not a
    wallet that hedged nothing. This figure gates and carries points, so the
    distinction decides outcomes.

    Measured against the markets the wallet currently holds, which is what the
    feed reports. A wallet that hedged heavily and has since closed everything
    reads as unhedged here - a limitation of the source, not of the definition,
    and the reason the classifier's cadence traits remain a separate signal.
    """
    if not positions:
        return None
    outcomes_by_market: Dict[str, set] = {}
    for position in positions:
        if not isinstance(position, dict):
            continue
        condition = position.get("conditionId")
        if not condition:
            continue
        try:
            size = float(position.get("size") or 0.0)
        except (ValueError, TypeError):
            continue
        if size <= HEDGE_DUST_SHARES:
            continue
        # `asset` identifies the outcome token; `outcomeIndex` is the fallback
        # for a feed row that omits it. Either one distinguishes the two sides.
        outcome = position.get("asset")
        if outcome is None:
            outcome = position.get("outcomeIndex")
        if outcome is None:
            continue
        outcomes_by_market.setdefault(str(condition), set()).add(str(outcome))

    if not outcomes_by_market:
        return None
    hedged = sum(1 for outcomes in outcomes_by_market.values() if len(outcomes) > 1)
    return round(hedged / len(outcomes_by_market) * 100.0, 4)


def recent_window_results(settled_results: Optional[Sequence[Dict[str, Any]]],
                          window: int) -> List[Dict[str, Any]]:
    """The last `window` settled markets, oldest first.

    The recent-form window. A wallet with fewer settled markets than the window
    returns all of them - a short record is measured over what exists rather
    than padded, and the caller reports the count alongside so a reader can see
    the window was not full.
    """
    if not settled_results or window <= 0:
        return []
    entries = [entry for entry in settled_results if isinstance(entry, dict)]
    return entries[-int(window):]

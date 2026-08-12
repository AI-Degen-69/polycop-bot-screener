#!/usr/bin/env python3
"""Modelled Copy PnL, replayed from a wallet's own fills.

The Modelled Copy PnL used to arrive precomputed from the aggregator, and it is
the single most load-bearing figure in the engine: the Toxic Copy Poison gate
reads it directly, and the Slippage Cost Rate gate plus 17 points are derived
from the gap between it and the target's own profit. Two more parameters -
Recent Form and Daily Green Rate - read windowed slices of the same replay.
Nothing else in the cutover unlocks as much.

This module produces it locally. Each of the target's fills is put through the
Copy Execution Profile - the Copyable Trade Window, the copy ratio, the position
and global caps - and charged the profile's assumed `slippage_pct` on each side.

**Modelled, not observed.** The friction here is an assumption, exactly as
CONTEXT.md defines the term, which is what makes this a substitute for the
figure it replaces rather than a different measurement wearing its name. The
Paper Trade Log (ADR 0013) measures *observed* friction against a live book, and
can only do so forward in time; it cannot answer a question about a wallet's
past, which is the question the screen asks.

Only markets the scanner could settle completely are replayed. A market whose
cost basis the fetched window only partly covers is unscoreable for the target
(see `_settled_market_pnl`), and scoring it for the follower would book a payout
against a fraction of its cost - the error that once turned a 2% edge into an
apparent 50% one.
"""
import datetime
from dataclasses import replace
from typing import Any, Dict, Optional, Sequence

from execution.copy_execution_profile import CopyExecutionProfile

TRADE_TYPE = "TRADE"
REDEEM_TYPE = "REDEEM"

# A cap large enough that no real trade reaches it, used to lift the bankroll's
# caps for the full-size mirror below. Not infinity: the profile's derived
# quantities are arithmetic on these fields, and an infinity would propagate
# into a window bound as a NaN rather than as "no limit".
NO_LIMIT_USD = 1e12

# The friction the modelled counterfactual assumes, per side, in percent.
# ADR 0001 records it as the leaderboard's assumption - 2% of adverse price
# movement on each side - and the Slippage Cost Rate gate's 5% threshold is
# calibrated against a figure computed under it. The Copy Execution Profile's
# own `slippage_pct` is a sweep level, not this: the Slippage Sensitivity Sweep
# raises it deliberately to see what an edge survives, and computing the
# *modelled* figure at a swept level would move the gate every time the sweep
# was retuned.
#
# `execution.paper_trade_log` states the same figure for the same reason. The
# two are kept apart on purpose: that module measures observed friction against
# a live book and this one assumes it, and the whole point of running both is
# to find out how far apart they are (ADR 0013).
MODELLED_SLIPPAGE_PCT_PER_SIDE = 2.0


def mirror_profile(profile: CopyExecutionProfile) -> CopyExecutionProfile:
    """The modelled counterfactual: a full-size mirror at the modelled friction.

    Modelled Copy PnL is defined as a counterfactual computed under a fixed
    friction assumption **and a full-size mirror** (CONTEXT.md). The full-size
    part is not incidental: it is what makes the figure measure friction and
    only friction.

    Measured against a bankroll-scaled copy instead, the gap between a target's
    profit and the copy's is dominated by the fact that the copy trades a
    fraction of the size - on a wallet earning $900k against a $100 bankroll it
    is essentially 100%, whatever the friction. Every wallet then fails the
    Slippage Cost Rate gate, which is a statement about the bankroll rather than
    about the wallet. Mirroring at full size removes the scale term, and what is
    left in the gap is what the gate was calibrated to reject.

    The price bounds survive, because a market the bot will not trade is not one
    a mirror of it trades either.
    """
    return replace(
        profile,
        copy_ratio=1.0,
        slippage_pct=MODELLED_SLIPPAGE_PCT_PER_SIDE,
        per_token_cap_usd=NO_LIMIT_USD,
        global_cap_usd=NO_LIMIT_USD,
        max_position_bankroll_fraction=NO_LIMIT_USD,
    )


def _number(value, default=0.0) -> float:
    """An upstream figure as a finite float, or the default.

    A scan runs unattended over thousands of wallets; one malformed row must
    read as nothing rather than end the pass.
    """
    try:
        parsed = float(value)
    except (ValueError, TypeError):
        return default
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return default
    return parsed


class _FollowerBook:
    """The follower's paper position across one wallet's replayed history.

    Tracks per-market cash flow and share inventory, plus the deployed capital
    the global cap limits. Cost basis is retired at average cost on the way out,
    so a partial exit releases the share of capital it actually returned.
    """

    def __init__(self, profile: CopyExecutionProfile):
        self.profile = profile
        self.shares: Dict[str, float] = {}
        self.cost: Dict[str, float] = {}
        self.flow: Dict[str, float] = {}
        self.notional: Dict[str, float] = {}
        self.friction: Dict[str, float] = {}
        self.target_shares: Dict[str, float] = {}
        self.deployed = 0.0

    def headroom(self, market: str) -> float:
        """What the caps leave free for another entry in this market."""
        position_room = self.profile.max_single_position_usd - self.cost.get(market, 0.0)
        global_room = self.profile.global_cap_usd - self.deployed
        return min(position_room, global_room)

    def buy(self, market: str, spend: float, fill_price: float, friction: float) -> None:
        if fill_price <= 0 or spend <= 0:
            return
        self.shares[market] = self.shares.get(market, 0.0) + spend / fill_price
        self.cost[market] = self.cost.get(market, 0.0) + spend
        self.flow[market] = self.flow.get(market, 0.0) - spend
        self.notional[market] = self.notional.get(market, 0.0) + spend
        self.friction[market] = self.friction.get(market, 0.0) + friction
        self.deployed += spend

    def sell(self, market: str, shares: float, fill_price: float, friction: float) -> None:
        held = self.shares.get(market, 0.0)
        shares = min(shares, held)
        if shares <= 0 or fill_price <= 0:
            return
        average_cost = self.cost.get(market, 0.0) / held if held > 0 else 0.0
        proceeds = shares * fill_price
        self.shares[market] = held - shares
        self.cost[market] = max(0.0, self.cost.get(market, 0.0) - average_cost * shares)
        self.flow[market] = self.flow.get(market, 0.0) + proceeds
        self.notional[market] = self.notional.get(market, 0.0) + proceeds
        self.friction[market] = self.friction.get(market, 0.0) + friction
        self.deployed = max(0.0, self.deployed - average_cost * shares)


def _replay_events(events: Sequence[Dict[str, Any]],
                   profile: CopyExecutionProfile) -> _FollowerBook:
    """Put every target fill through the profile, in the order it happened."""
    book = _FollowerBook(profile)
    slip = profile.slippage_pct / 100.0

    ordered = sorted(
        (event for event in events if isinstance(event, dict)),
        key=lambda event: _number(event.get("timestamp")),
    )

    for event in ordered:
        market = event.get("conditionId")
        if not market:
            continue
        event_type = event.get("type") or TRADE_TYPE
        price = _number(event.get("price"))
        size = _number(event.get("size"))
        usdc = _number(event.get("usdcSize"))

        if event_type == REDEEM_TYPE:
            # Settlement, not execution: the outcome pays a fixed rate per
            # share and there is no book to cross, so no friction is charged.
            held = book.shares.get(market, 0.0)
            if held <= 0 or size <= 0:
                continue
            book.sell(market, held, usdc / size, 0.0)
            continue

        if event_type != TRADE_TYPE:
            continue
        if not (profile.min_price <= price <= profile.max_price):
            continue

        side = str(event.get("side") or "").upper()
        if side == "BUY":
            book.target_shares[market] = book.target_shares.get(market, 0.0) + size
            # The Copyable Trade Window: outside it the bot does not mirror the
            # trade at all, so it contributes nothing to the copy's profit while
            # still counting in the target's. That gap is the whole of what
            # Slippage Cost Rate measures.
            if not (profile.window_min_usd <= usdc <= profile.window_max_usd):
                continue
            headroom = book.headroom(market)
            if headroom < profile.venue_min_order_usd:
                continue
            spend = min(usdc * profile.copy_ratio, profile.max_single_position_usd, headroom)
            fill_price = price * (1.0 + slip)
            # Friction is what the copy paid over what the target paid for the
            # same exposure: of every dollar spent, this share bought nothing.
            book.buy(market, spend, fill_price, spend * slip / (1.0 + slip))
        elif side == "SELL":
            held = book.shares.get(market, 0.0)
            target_held = book.target_shares.get(market, 0.0)
            book.target_shares[market] = max(0.0, target_held - size)
            if held <= 0:
                continue
            # Mirror the fraction of its position the target sold, measured
            # against the position this replay watched it build. Without that
            # denominator every partial trim would read as a full exit.
            fraction = min(1.0, size / target_held) if target_held > 0 else 1.0
            shares = held * fraction
            fill_price = price * (1.0 - slip)
            book.sell(market, shares, fill_price, shares * price * slip)

    return book


def _day(timestamp) -> Optional[str]:
    """The UTC date a market closed on, or None when it is unstamped."""
    stamp = _number(timestamp)
    if stamp <= 0:
        return None
    return datetime.datetime.fromtimestamp(
        stamp, datetime.timezone.utc
    ).strftime("%Y-%m-%d")


def replay_copy(events: Sequence[Dict[str, Any]],
                settled_results: Optional[Sequence[Dict[str, Any]]],
                profile: CopyExecutionProfile,
                recent_window: int) -> Dict[str, Any]:
    """What copying this wallet would have returned, under one stated profile.

    Returns the figures the engine reads, or None for each of them when the
    record holds no completely-settled market. A wallet nothing could be
    measured on scores nothing and is rejected on the absence, rather than
    being handed a break-even zero it never earned (ADR 0007).

    `recent_window` is the count of most-recent settled markets the Recent Form
    parameter judges. It is passed in rather than imported so the engine's
    window constant keeps exactly one home.
    """
    scoreable = [entry for entry in (settled_results or []) if isinstance(entry, dict)]
    if not scoreable:
        return {
            "modelled_copy_pnl": None,
            "bankroll_copy_pnl": None,
            "per_day_copy_pnl": None,
            "recent_window_target_pnl": None,
            "recent_window_friction_pct": None,
            "replayed_markets": 0,
        }

    # Two passes over the same fills under the same friction assumption. The
    # mirror answers "what did friction cost this edge", which is what the
    # Slippage Cost Rate gate asks; the bankroll pass answers "what would this
    # follower have experienced", which is what the per-day and recent-window
    # figures are about. Conflating them makes every large wallet look like it
    # was destroyed by friction when it was only traded smaller.
    book = _replay_events(events, profile)
    mirror = _replay_events(events, mirror_profile(profile))

    total = 0.0
    mirror_total = 0.0
    per_day: Dict[str, float] = {}
    replayed = 0
    mirror_replayed = 0
    for entry in scoreable:
        market = entry.get("condition_id")
        if market is None:
            continue
        mirror_result = mirror.flow.get(market)
        if mirror_result is not None:
            mirror_replayed += 1
            mirror_total += mirror_result
        # Any share still held in a market the target has settled is worthless:
        # a resolved position that was going to pay would have produced the
        # REDEEM the replay already processed. So the follower's cash flow is
        # its result, and a market the follower never entered contributes
        # nothing rather than a zero that would dilute the per-day rate.
        result = book.flow.get(market)
        if result is None:
            continue
        replayed += 1
        total += result
        day = _day(entry.get("closed_at"))
        if day is not None:
            per_day[day] = round(per_day.get(day, 0.0) + result, 6)

    window = scoreable[-int(recent_window):] if recent_window > 0 else []
    window_target_pnl = sum(_number(entry.get("result_usdc")) for entry in window)
    window_notional = sum(book.notional.get(entry.get("condition_id"), 0.0) for entry in window)
    window_friction = sum(book.friction.get(entry.get("condition_id"), 0.0) for entry in window)
    # The friction the recent run came through, as a share of the capital the
    # copy actually turned over. Expressed in percent because the Recent Form
    # shape scores it against a percentage ceiling.
    friction_pct = (
        round(window_friction / window_notional * 100.0, 4) if window_notional > 0 else None
    )

    return {
        # The full-size mirror: the counterfactual the Toxic Copy Poison and
        # Slippage Cost Rate gates are written against.
        "modelled_copy_pnl": round(mirror_total, 4) if mirror_replayed else None,
        # What this bankroll would actually have returned. Not a friction
        # measure - the caps and the window are in it - so it never reaches a
        # gate calibrated on friction.
        "bankroll_copy_pnl": round(total, 4) if replayed else None,
        "per_day_copy_pnl": per_day if per_day else None,
        "recent_window_target_pnl": round(window_target_pnl, 4) if window else None,
        "recent_window_friction_pct": friction_pct,
        "replayed_markets": replayed,
    }


def daily_green_rate(per_day_copy_pnl: Optional[Dict[str, float]]):
    """Share of observed days that ended green for a copier, and how many days.

    The same contract `derived_metrics.calculate_daily_green_rate` returns for
    the aggregator's series, so the engine's minimum-observed-days floor applies
    unchanged. A day on which nothing settled is not an observed day: counting
    it flat would dilute the rate and inflate the day count the floor relies on.
    """
    if not per_day_copy_pnl:
        return None, 0
    values = [
        value for value in per_day_copy_pnl.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if not values:
        return None, 0
    green = sum(1 for value in values if value > 0)
    return (green / len(values)) * 100.0, len(values)

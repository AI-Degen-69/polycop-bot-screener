#!/usr/bin/env python3
"""The Paper Trade Log: what copying a target would actually have cost.

Nothing in this project has yet checked whether a screened wallet was profitable
to copy. Scores and Simulated Copy Runs both argue from the target's own history;
neither commits to a claim that a later reader can mark right or wrong. This
module makes that commitment: for every trade a target makes from now on, it
records the order the follower's bot would have sent, the price the live book
would have given it, and the profit or loss that position went on to realise.

No money moves. The log is an append-only record of counterfactual orders, so a
reader coming back weeks later can total it up and say whether the picks earned.

Two things make the record worth keeping rather than re-derivable:

* The book is read at the moment the follower would have traded. A backtest can
  reconstruct a target's fill from history, but it cannot reconstruct the depth
  that was standing when the follower arrived a poll interval later. That gap is
  the whole of copy friction and it is only observable live.
* Every record carries its own Friction Realism Multiplier sample - observed
  slippage over the leaderboard's modelled assumption. ADR 0001 set that
  multiplier to 4.2 from three hand-logged fills and said the figure was a
  tracked estimate expected to move. `execution.friction_calibration` re-derives
  it from this log; this module's job is to make sure every term of that
  division is written down.

The module is pure: it is handed activity, a book and a portfolio, and it
returns records. Fetching lives in `pipeline.poll_paper_trades`.
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from execution.copy_execution_profile import CopyExecutionProfile

# Bumped whenever a change makes older records incomparable to fresh ones. The
# log is append-only and expected to be read months after it was written, so a
# reader must be able to tell which arithmetic produced a given line.
PAPER_TRADE_SCHEMA_VERSION = 1

# The friction the leaderboard's copy-PnL model assumes, per side, in percent.
# ADR 0001 names it as the denominator the 4.2 multiplier was measured against;
# it is stated here because this log's whole purpose is to re-measure that ratio,
# and a ratio needs both of its terms written down beside each other.
MODELLED_SLIPPAGE_PCT_PER_SIDE = 2.0

# Activity types. Only a TRADE is an order the follower could have mirrored;
# a REDEEM settles shares already held, at the outcome rather than at a price.
TRADE_TYPE = "TRADE"
REDEEM_TYPE = "REDEEM"

# Why a target trade did not become a copy. Recorded rather than dropped: a
# target whose trades the profile mostly refuses is a finding about the profile,
# and it is invisible if the log only keeps the trades that went through.
SKIP_NOT_A_TRADE = "NOT_A_TRADE"
SKIP_PRICE_OUT_OF_BOUNDS = "PRICE_OUT_OF_BOUNDS"
SKIP_BELOW_WINDOW = "BELOW_COPYABLE_WINDOW"
SKIP_ABOVE_WINDOW = "ABOVE_COPYABLE_WINDOW"
SKIP_POSITION_CAP_FULL = "POSITION_CAP_FULL"
SKIP_GLOBAL_CAP_FULL = "GLOBAL_CAP_FULL"
SKIP_NO_INVENTORY = "NO_INVENTORY"
SKIP_NO_BOOK = "NO_BOOK"
SKIP_BOOK_TOO_THIN = "BOOK_TOO_THIN"

COPIED = "COPIED"
SKIPPED = "SKIPPED"


def _finite_float(value, default: float = 0.0) -> float:
    """A live-API figure as a float, or the default when it is missing or junk.

    The same tolerance the rest of the screen applies to upstream numbers: a
    malformed field reads as unmeasured rather than crashing a poll that is
    meant to run unattended for weeks.
    """
    if value is None:
        return default
    try:
        parsed = float(value)
    except (ValueError, TypeError):
        return default
    return parsed if math.isfinite(parsed) else default


def _levels(book: Optional[Dict[str, Any]], side: str) -> List[Tuple[float, float]]:
    """The book side the follower would cross, best price first.

    A buyer lifts asks cheapest-first and a seller hits bids dearest-first, so
    each side is sorted here rather than trusted to arrive ordered - the CLOB
    returns bids ascending, which is the wrong end to start from.
    """
    if not isinstance(book, dict):
        return []
    raw = book.get("asks" if side == "BUY" else "bids") or []
    parsed = []
    for level in raw:
        if not isinstance(level, dict):
            continue
        price = _finite_float(level.get("price"))
        size = _finite_float(level.get("size"))
        if price > 0 and size > 0:
            parsed.append((price, size))
    parsed.sort(key=lambda level: level[0], reverse=(side == "SELL"))
    return parsed


def walk_book_for_notional(levels, notional_usd: float):
    """Spend a dollar amount into a book side, returning what it actually buys.

    Returns `(shares, spent_usd, vwap)`. The vwap is the realistic fill price:
    quoting the touch would price a $5 order and a $500 order identically, and
    the difference between them is exactly the friction this log exists to
    measure. A book too thin to absorb the order fills what it can and reports
    the shortfall through `spent_usd` being under the amount asked for.
    """
    remaining = max(0.0, notional_usd)
    shares = 0.0
    spent = 0.0
    for price, size in levels:
        if remaining <= 0:
            break
        level_notional = price * size
        take = min(level_notional, remaining)
        shares += take / price
        spent += take
        remaining -= take
    vwap = (spent / shares) if shares > 0 else 0.0
    return shares, round(spent, 6), vwap


def walk_book_for_shares(levels, shares_wanted: float):
    """Sell a share quantity into a book side, returning what it actually raises.

    The mirror of `walk_book_for_notional` for the exit leg, where the follower
    holds a quantity rather than a dollar amount.
    """
    remaining = max(0.0, shares_wanted)
    shares = 0.0
    proceeds = 0.0
    for price, size in levels:
        if remaining <= 0:
            break
        take = min(size, remaining)
        shares += take
        proceeds += take * price
        remaining -= take
    vwap = (proceeds / shares) if shares > 0 else 0.0
    return shares, round(proceeds, 6), vwap


def adverse_slippage_pct(reference_price: float, fill_price: float, side: str) -> Optional[float]:
    """How much worse than a reference price a fill was, in percent.

    Signed so that positive always means worse for the follower, on both legs:
    a buyer is hurt by paying more, a seller by receiving less. Without that
    convention the two legs would cancel when averaged, and the average is what
    the Friction Realism Multiplier is calibrated from.

    None when the reference price is unusable, because an unmeasurable friction
    must stay absent rather than read as a measured zero (ADR 0007).
    """
    if reference_price <= 0 or fill_price <= 0:
        return None
    delta = (fill_price - reference_price) if side == "BUY" else (reference_price - fill_price)
    return round(delta / reference_price * 100.0, 4)


@dataclass
class Position:
    """The follower's paper holding in one outcome token."""

    follower_shares: float = 0.0
    follower_cost_usd: float = 0.0
    # The target's own holding, accumulated from the activity this log has seen.
    # It is what turns a target's partial exit into a proportional one for the
    # follower: without it, any sell would have to be read as a full exit.
    target_shares: float = 0.0

    @property
    def average_cost(self) -> float:
        return (self.follower_cost_usd / self.follower_shares) if self.follower_shares > 0 else 0.0


@dataclass
class PaperPortfolio:
    """The follower's paper book for one arm, as the caps see it.

    Held separately per arm so the two arms never compete for the same
    bankroll: the point of running them side by side is to compare the wallets,
    which a shared global cap would confound with whichever arm traded first.
    """

    profile: CopyExecutionProfile
    positions: Dict[str, Position] = field(default_factory=dict)
    realised_pnl_usd: float = 0.0

    @property
    def deployed_usd(self) -> float:
        """Cost basis currently at risk, which is what the global cap limits."""
        return round(sum(p.follower_cost_usd for p in self.positions.values()), 6)

    def position(self, asset: str) -> Position:
        return self.positions.setdefault(asset, Position())

    def open(self, asset: str, shares: float, cost_usd: float) -> None:
        pos = self.position(asset)
        pos.follower_shares += shares
        pos.follower_cost_usd += cost_usd

    def close(self, asset: str, shares: float, proceeds_usd: float) -> float:
        """Retire shares at average cost, returning the profit or loss booked."""
        pos = self.position(asset)
        shares = min(shares, pos.follower_shares)
        if shares <= 0:
            return 0.0
        cost = pos.average_cost * shares
        pos.follower_shares -= shares
        pos.follower_cost_usd -= cost
        # Floating-point residue on a fully closed position would otherwise sit
        # in `deployed_usd` forever and slowly eat the global cap.
        if pos.follower_shares <= 1e-9:
            pos.follower_shares = 0.0
            pos.follower_cost_usd = 0.0
        realised = round(proceeds_usd - cost, 6)
        self.realised_pnl_usd = round(self.realised_pnl_usd + realised, 6)
        return realised

    def as_dict(self) -> Dict[str, Any]:
        return {
            "deployed_usd": self.deployed_usd,
            "realised_pnl_usd": self.realised_pnl_usd,
            "open_positions": {
                asset: {
                    "follower_shares": round(pos.follower_shares, 6),
                    "follower_cost_usd": round(pos.follower_cost_usd, 6),
                    "target_shares": round(pos.target_shares, 6),
                }
                for asset, pos in self.positions.items()
                if pos.follower_shares > 0 or pos.target_shares > 0
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], profile: CopyExecutionProfile) -> "PaperPortfolio":
        portfolio = cls(profile=profile)
        portfolio.realised_pnl_usd = _finite_float((data or {}).get("realised_pnl_usd"))
        for asset, raw in ((data or {}).get("open_positions") or {}).items():
            portfolio.positions[asset] = Position(
                follower_shares=_finite_float(raw.get("follower_shares")),
                follower_cost_usd=_finite_float(raw.get("follower_cost_usd")),
                target_shares=_finite_float(raw.get("target_shares")),
            )
        return portfolio


def _target_block(activity: Dict[str, Any]) -> Dict[str, Any]:
    """The upstream trade, kept verbatim enough to audit a record against the API."""
    return {
        "timestamp": int(_finite_float(activity.get("timestamp"))),
        "transaction_hash": str(activity.get("transactionHash") or ""),
        "condition_id": str(activity.get("conditionId") or ""),
        "asset": str(activity.get("asset") or ""),
        "title": str(activity.get("title") or ""),
        "slug": str(activity.get("slug") or ""),
        "outcome": str(activity.get("outcome") or ""),
        "type": str(activity.get("type") or ""),
        "side": str(activity.get("side") or "").upper(),
        "price": _finite_float(activity.get("price")),
        "shares": _finite_float(activity.get("size")),
        "usdc_size": _finite_float(activity.get("usdcSize")),
    }


def _record(arm, wallet, activity, observed_at, profile, decision, **extra):
    record = {
        "schema_version": PAPER_TRADE_SCHEMA_VERSION,
        "arm": arm,
        "address": str(wallet.get("address") or "").lower(),
        "pseudonym": str(wallet.get("pseudonym") or ""),
        "observed_at": int(observed_at),
        "profile_fingerprint": profile.fingerprint,
        "decision": decision,
        "skip_reason": None,
        "target": _target_block(activity),
    }
    record.update(extra)
    return record


def _sized_order(profile: CopyExecutionProfile, target_notional: float,
                 headroom_usd: float) -> Dict[str, Any]:
    """The order the bot would send for a target trade of this size.

    Follows the profile in the order the bot itself applies it: nominal copy
    ratio, then the position cap, then whatever the global cap leaves free.

    There is no Minimum Order Bump here, and that is a property of the profile
    rather than an omission. The window's lower bound *is* `venue_min / ratio`,
    so a trade whose proportional copy would fall under the venue minimum is
    refused by the window before sizing is reached, and both cap checks refuse
    headroom under the minimum before they can shrink an order beneath it. The
    over-exposure the bump would cause is therefore never taken; it shows up as
    a BELOW_COPYABLE_WINDOW record instead, which is where a reader should count
    it. A profile that widened the window below `venue_min / ratio` would have
    to reintroduce the bump here, and would owe this comment an update.
    """
    nominal = target_notional * profile.copy_ratio
    order = min(nominal, profile.max_single_position_usd, headroom_usd)
    return {
        "nominal_usd": round(nominal, 6),
        "order_usd": round(order, 6),
        "capped_by_position": order < nominal,
        "realised_copy_ratio": round(order / target_notional, 6) if target_notional > 0 else 0.0,
    }


def _pricing(target_price, quote_price, fill_price, side, filled_usd, requested_usd):
    """The three prices of a copied trade and the friction between them.

    Latency and depth are separated because they answer different questions and
    have different fixes: latency friction is the price that moved between the
    target's fill and the follower's arrival, depth friction is what the
    follower's own order cost itself by crossing the book. Only their sum feeds
    the Friction Realism Multiplier, which is the leaderboard model's subject.
    """
    total = adverse_slippage_pct(target_price, fill_price, side)
    return {
        "target_price": round(target_price, 6),
        "quote_price": round(quote_price, 6),
        "fill_price": round(fill_price, 6),
        "filled_usd": round(filled_usd, 6),
        "unfilled_usd": round(max(0.0, requested_usd - filled_usd), 6),
        "latency_slippage_pct": adverse_slippage_pct(target_price, quote_price, side),
        "depth_slippage_pct": adverse_slippage_pct(quote_price, fill_price, side),
        "total_slippage_pct": total,
        "modelled_slippage_pct": MODELLED_SLIPPAGE_PCT_PER_SIDE,
        # The per-fill Friction Realism Multiplier sample. ADR 0001 fixed 4.2
        # from three of these; the log accumulates them so the figure can be
        # re-derived rather than re-asserted.
        "friction_realism_sample": (
            round(total / MODELLED_SLIPPAGE_PCT_PER_SIDE, 4) if total is not None else None
        ),
    }


def record_target_trade(arm: str, wallet: Dict[str, Any], activity: Dict[str, Any],
                        book: Optional[Dict[str, Any]], portfolio: PaperPortfolio,
                        observed_at: int) -> Dict[str, Any]:
    """One target trade, priced as the follower's bot would have met it.

    Mutates `portfolio` when the trade is copied, and returns the record to
    append. Every target trade produces a record, copied or not: a log that kept
    only the fills would hide the profile refusing most of a target's behaviour,
    which is a verdict about that target rather than an absence of data.
    """
    profile = portfolio.profile
    target = _target_block(activity)
    side = target["side"]
    asset = target["asset"]
    position = portfolio.position(asset)

    def skip(reason, **extra):
        record = _record(arm, wallet, activity, observed_at, profile, SKIPPED, **extra)
        record["skip_reason"] = reason
        record["portfolio_after"] = portfolio.as_dict()
        return record

    if target["type"] == REDEEM_TYPE:
        return _redemption(arm, wallet, activity, portfolio, observed_at)

    if target["type"] != TRADE_TYPE or side not in ("BUY", "SELL"):
        return skip(SKIP_NOT_A_TRADE)

    if not (profile.min_price <= target["price"] <= profile.max_price):
        return skip(SKIP_PRICE_OUT_OF_BOUNDS)

    levels = _levels(book, side)
    if not levels:
        return skip(SKIP_NO_BOOK)
    quote_price = levels[0][0]

    if side == "BUY":
        return _copy_entry(arm, wallet, activity, levels, quote_price, portfolio,
                           observed_at, position, skip)
    return _copy_exit(arm, wallet, activity, levels, quote_price, portfolio,
                      observed_at, position, skip)


def _copy_entry(arm, wallet, activity, levels, quote_price, portfolio, observed_at,
                position, skip):
    """The follower's entry leg: a share of the target's buy, under every cap."""
    profile = portfolio.profile
    target = _target_block(activity)
    position.target_shares += target["shares"]

    target_notional = target["usdc_size"]
    window = {
        "min_usd": round(profile.window_min_usd, 2),
        "max_usd": round(profile.window_max_usd, 2),
    }
    if target_notional < profile.window_min_usd:
        return skip(SKIP_BELOW_WINDOW, window=window)
    if target_notional > profile.window_max_usd:
        return skip(SKIP_ABOVE_WINDOW, window=window)

    position_headroom = profile.max_single_position_usd - position.follower_cost_usd
    global_headroom = profile.global_cap_usd - portfolio.deployed_usd
    if position_headroom < profile.venue_min_order_usd:
        return skip(SKIP_POSITION_CAP_FULL)
    if global_headroom < profile.venue_min_order_usd:
        return skip(SKIP_GLOBAL_CAP_FULL)

    sizing = _sized_order(profile, target_notional, min(position_headroom, global_headroom))
    shares, spent, fill_price = walk_book_for_notional(levels, sizing["order_usd"])
    if shares <= 0:
        return skip(SKIP_BOOK_TOO_THIN, sizing=sizing)

    portfolio.open(target["asset"], shares, spent)
    record = _record(arm, wallet, activity, observed_at, profile, COPIED,
                     sizing=sizing,
                     pricing=_pricing(target["price"], quote_price, fill_price, "BUY",
                                      spent, sizing["order_usd"]),
                     fill={"shares": round(shares, 6), "notional_usd": round(spent, 6)},
                     realised_pnl_usd=None)
    record["portfolio_after"] = portfolio.as_dict()
    return record


def _copy_exit(arm, wallet, activity, levels, quote_price, portfolio, observed_at,
               position, skip):
    """The follower's exit leg: the same fraction of the position the target sold.

    The fraction is taken against the target's holding as this log has watched it
    accumulate, so a target trimming a third of a position trims a third of the
    follower's. A sell in a token the follower never entered is a ghost exit -
    recorded as such, since it is the target's behaviour the profile could not
    replicate, not an error.
    """
    profile = portfolio.profile
    target = _target_block(activity)

    if position.follower_shares <= 0:
        position.target_shares = max(0.0, position.target_shares - target["shares"])
        return skip(SKIP_NO_INVENTORY)

    if position.target_shares > 0:
        exit_fraction = min(1.0, target["shares"] / position.target_shares)
    else:
        # The target sold more than this log ever saw them buy, so the position
        # predates the log. A full exit is the only reading that does not invent
        # a denominator.
        exit_fraction = 1.0
    position.target_shares = max(0.0, position.target_shares - target["shares"])

    shares_wanted = position.follower_shares * exit_fraction
    shares, proceeds, fill_price = walk_book_for_shares(levels, shares_wanted)
    if shares <= 0:
        return skip(SKIP_BOOK_TOO_THIN)

    realised = portfolio.close(target["asset"], shares, proceeds)
    record = _record(arm, wallet, activity, observed_at, profile, COPIED,
                     sizing={
                         "exit_fraction": round(exit_fraction, 6),
                         "shares_wanted": round(shares_wanted, 6),
                     },
                     pricing=_pricing(target["price"], quote_price, fill_price, "SELL",
                                      proceeds, shares_wanted * quote_price),
                     fill={"shares": round(shares, 6), "notional_usd": round(proceeds, 6)},
                     realised_pnl_usd=realised)
    record["portfolio_after"] = portfolio.as_dict()
    return record


def _redemption(arm, wallet, activity, portfolio, observed_at):
    """A settled market paying out shares the follower still holds.

    Redemption has no book and no slippage: the outcome pays a fixed amount per
    share, so the follower's payout is that same rate on its own quantity. This
    is where a copied position finally becomes a profit or a loss a reader can
    check, which is the point of keeping the log at all.
    """
    profile = portfolio.profile
    target = _target_block(activity)
    position = portfolio.position(target["asset"])

    if position.follower_shares <= 0:
        record = _record(arm, wallet, activity, observed_at, profile, SKIPPED)
        record["skip_reason"] = SKIP_NO_INVENTORY
        record["portfolio_after"] = portfolio.as_dict()
        return record

    payout_per_share = (
        target["usdc_size"] / target["shares"] if target["shares"] > 0 else 0.0
    )
    shares = position.follower_shares
    proceeds = payout_per_share * shares
    realised = portfolio.close(target["asset"], shares, proceeds)
    position.target_shares = max(0.0, position.target_shares - target["shares"])

    record = _record(arm, wallet, activity, observed_at, profile, COPIED,
                     sizing={"exit_fraction": 1.0, "shares_wanted": round(shares, 6)},
                     pricing={
                         "target_price": round(payout_per_share, 6),
                         "quote_price": round(payout_per_share, 6),
                         "fill_price": round(payout_per_share, 6),
                         "filled_usd": round(proceeds, 6),
                         "unfilled_usd": 0.0,
                         # A redemption is settlement, not execution. Its
                         # friction is not zero, it is undefined - and an
                         # undefined figure must not be averaged in as a zero
                         # that would drag the multiplier down.
                         "latency_slippage_pct": None,
                         "depth_slippage_pct": None,
                         "total_slippage_pct": None,
                         "modelled_slippage_pct": MODELLED_SLIPPAGE_PCT_PER_SIDE,
                         "friction_realism_sample": None,
                     },
                     fill={"shares": round(shares, 6), "notional_usd": round(proceeds, 6)},
                     realised_pnl_usd=realised)
    record["portfolio_after"] = portfolio.as_dict()
    return record

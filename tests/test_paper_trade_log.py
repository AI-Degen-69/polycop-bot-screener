#!/usr/bin/env python3
"""What the Paper Trade Log claims about a copy it never placed.

The log's value rests entirely on its arithmetic being the bot's arithmetic: no
reader weeks from now can check a fill that never happened against anything but
these rules. So the rules are pinned here - the caps in the order the bot
applies them, the sign of friction on both legs, and the profit a round trip
books.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from execution.copy_execution_profile import CopyExecutionProfile  # noqa: E402
from execution.paper_trade_log import (  # noqa: E402
    COPIED,
    MODELLED_SLIPPAGE_PCT_PER_SIDE,
    SKIP_ABOVE_WINDOW,
    SKIP_BELOW_WINDOW,
    SKIP_GLOBAL_CAP_FULL,
    SKIP_NO_BOOK,
    SKIP_NO_INVENTORY,
    SKIP_NOT_A_TRADE,
    SKIP_POSITION_CAP_FULL,
    SKIP_PRICE_OUT_OF_BOUNDS,
    SKIPPED,
    PaperPortfolio,
    adverse_slippage_pct,
    record_target_trade,
    walk_book_for_notional,
    walk_book_for_shares,
)

WALLET = {"address": "0xTEST", "pseudonym": "Test-Wallet"}
ASSET = "token-a"


def _profile(**overrides):
    return CopyExecutionProfile(**overrides)


def _portfolio(**overrides):
    return PaperPortfolio(profile=_profile(**overrides))


def _trade(side="BUY", price=0.5, shares=100.0, usdc_size=50.0, timestamp=1000,
           activity_type="TRADE", asset=ASSET):
    return {
        "timestamp": timestamp,
        "transactionHash": "0xhash",
        "conditionId": "0xcondition",
        "asset": asset,
        "title": "Test market",
        "slug": "test-market",
        "outcome": "Yes",
        "type": activity_type,
        "side": side,
        "price": price,
        "size": shares,
        "usdcSize": usdc_size,
    }


def _book(asks=(("0.51", "1000"),), bids=(("0.49", "1000"),)):
    return {
        "asks": [{"price": p, "size": s} for p, s in asks],
        "bids": [{"price": p, "size": s} for p, s in bids],
    }


_DEFAULT_BOOK = object()


def _record(activity, portfolio, book=_DEFAULT_BOOK, observed_at=1200):
    """A recorded trade. `book=None` means the book could not be read, which is
    a distinct outcome from the default book this helper otherwise supplies."""
    return record_target_trade("test_arm", WALLET, activity,
                               _book() if book is _DEFAULT_BOOK else book,
                               portfolio, observed_at=observed_at)


# ------------------------------------------------------------ book walking

def test_a_small_order_fills_at_the_touch():
    shares, spent, vwap = walk_book_for_notional([(0.50, 1000.0)], 3.0)
    assert spent == 3.0
    assert shares == 6.0
    assert vwap == 0.50


def test_an_order_larger_than_the_touch_pays_the_next_level():
    """Quoting the touch would price every order identically. The difference
    between a $1 copy and a $100 one is the friction the log exists to measure."""
    levels = [(0.50, 10.0), (0.60, 1000.0)]
    _shares, spent, vwap = walk_book_for_notional(levels, 10.0)
    assert spent == 10.0
    assert 0.50 < vwap < 0.60


def test_a_book_too_thin_fills_only_what_is_there():
    shares, spent, _vwap = walk_book_for_notional([(0.50, 10.0)], 100.0)
    assert spent == 5.0
    assert shares == 10.0


def test_selling_walks_the_bids_down():
    shares, proceeds, vwap = walk_book_for_shares([(0.60, 5.0), (0.40, 100.0)], 10.0)
    assert shares == 10.0
    assert proceeds == 5.0 * 0.60 + 5.0 * 0.40
    assert 0.40 < vwap < 0.60


def test_the_seller_starts_at_the_best_bid_not_the_worst():
    """The CLOB returns bids ascending, which is the wrong end for a seller."""
    book = _book(bids=(("0.10", "1000"), ("0.90", "1000")))
    portfolio = _portfolio()
    _record(_trade(usdc_size=50.0), portfolio)
    record = _record(_trade(side="SELL", price=0.90, shares=100.0), portfolio, book=book)
    assert record["pricing"]["quote_price"] == 0.90


# ---------------------------------------------------------------- friction

def test_a_buyer_is_hurt_by_paying_more():
    assert adverse_slippage_pct(0.50, 0.55, "BUY") == 10.0


def test_a_seller_is_hurt_by_receiving_less():
    assert adverse_slippage_pct(0.50, 0.45, "SELL") == 10.0


def test_a_favourable_fill_reads_as_negative_friction():
    """Both legs must be signed the same way or they cancel when averaged, and
    the average is what the Friction Realism Multiplier is calibrated from."""
    assert adverse_slippage_pct(0.50, 0.45, "BUY") == -10.0
    assert adverse_slippage_pct(0.50, 0.55, "SELL") == -10.0


def test_an_unusable_reference_price_leaves_friction_unmeasured():
    assert adverse_slippage_pct(0.0, 0.50, "BUY") is None
    assert adverse_slippage_pct(0.50, 0.0, "BUY") is None


def test_every_fill_carries_its_own_multiplier_sample():
    """ADR 0001 fixed 4.2 from three of these. The log accumulates them so the
    figure can be re-derived rather than re-asserted."""
    record = _record(_trade(price=0.50), _portfolio(), book=_book(asks=(("0.51", "1000"),)))
    pricing = record["pricing"]
    assert pricing["total_slippage_pct"] == 2.0
    assert pricing["modelled_slippage_pct"] == MODELLED_SLIPPAGE_PCT_PER_SIDE
    assert pricing["friction_realism_sample"] == 1.0


def test_latency_and_depth_friction_are_reported_apart():
    """They have different fixes and different comparison measurements: depth
    against latency_slippage_profile.json, latency against ADR 0001's chase."""
    book = _book(asks=(("0.51", "2.0"), ("0.60", "1000")))
    record = _record(_trade(price=0.50, usdc_size=50.0), _portfolio(), book=book)
    pricing = record["pricing"]
    assert pricing["latency_slippage_pct"] == 2.0
    assert pricing["depth_slippage_pct"] > 0.0
    assert pricing["total_slippage_pct"] > pricing["latency_slippage_pct"]


# ------------------------------------------------------------------ sizing

def test_a_copy_takes_the_nominal_ratio_of_the_target_trade():
    record = _record(_trade(usdc_size=50.0), _portfolio())
    assert record["decision"] == COPIED
    assert record["sizing"]["nominal_usd"] == 1.5
    assert record["sizing"]["order_usd"] == 1.5
    assert record["sizing"]["capped_by_position"] is False


def test_the_position_cap_clips_a_large_copy():
    """At the window's top the ratio is already clipped; past it the trade is
    refused, so the cap binds only inside the window."""
    record = _record(_trade(usdc_size=_profile().window_max_usd), _portfolio())
    assert record["sizing"]["order_usd"] == _profile().max_single_position_usd


def test_a_trade_under_the_window_is_refused_rather_than_bumped():
    """Bumping a sub-minimum copy to the venue floor is over-exposure, not a
    mirror, so the window refuses the trade before the floor can apply."""
    record = _record(_trade(usdc_size=10.0), _portfolio())
    assert record["decision"] == SKIPPED
    assert record["skip_reason"] == SKIP_BELOW_WINDOW
    assert record["window"]["min_usd"] == round(_profile().window_min_usd, 2)


def test_a_trade_over_the_window_is_refused():
    record = _record(_trade(usdc_size=10000.0), _portfolio())
    assert record["skip_reason"] == SKIP_ABOVE_WINDOW


def test_the_window_makes_a_minimum_order_bump_unreachable():
    """The window's floor is `venue_min / ratio`, so no admitted trade can size
    a copy under the venue minimum. Every trade that would have needed the bump
    is a BELOW_COPYABLE_WINDOW record instead - which is where the over-exposure
    the bump would have caused should be counted."""
    profile = _profile()
    smallest_admitted = profile.window_min_usd
    record = _record(_trade(usdc_size=smallest_admitted), _portfolio())
    assert record["decision"] == COPIED
    assert record["sizing"]["order_usd"] >= profile.venue_min_order_usd

    just_below = _record(_trade(usdc_size=smallest_admitted - 0.01), _portfolio())
    assert just_below["skip_reason"] == SKIP_BELOW_WINDOW


# -------------------------------------------------------------------- caps

def test_a_full_position_refuses_further_entries():
    portfolio = _portfolio()
    for index in range(4):
        _record(_trade(usdc_size=_profile().window_max_usd, timestamp=1000 + index),
                portfolio)
    record = _record(_trade(usdc_size=_profile().window_max_usd, timestamp=2000),
                     portfolio)
    assert record["skip_reason"] == SKIP_POSITION_CAP_FULL


def test_a_full_bankroll_refuses_entries_in_a_fresh_market():
    # A $2 global cap also caps a single position at $2, which narrows the
    # window to $66.67 - so the target trade has to fit the narrowed window.
    portfolio = _portfolio(global_cap_usd=2.0)
    first = _record(_trade(usdc_size=50.0), portfolio)
    assert first["decision"] == COPIED
    # A different token, so the position cap is not what refuses this one.
    record = _record(_trade(usdc_size=50.0, timestamp=1001, asset="token-b"), portfolio)
    assert record["skip_reason"] == SKIP_GLOBAL_CAP_FULL


def test_a_price_outside_the_profile_bounds_is_not_copied():
    record = _record(_trade(price=0.99), _portfolio())
    assert record["skip_reason"] == SKIP_PRICE_OUT_OF_BOUNDS


def test_a_missing_book_leaves_the_trade_unpriced_rather_than_guessed():
    record = _record(_trade(), _portfolio(), book=None)
    assert record["skip_reason"] == SKIP_NO_BOOK


def test_a_non_trade_activity_is_recorded_but_not_copied():
    record = _record(_trade(activity_type="SPLIT"), _portfolio())
    assert record["skip_reason"] == SKIP_NOT_A_TRADE


def test_a_refused_trade_is_still_recorded():
    """A log that kept only the fills would hide the profile refusing most of a
    target's behaviour, which is a verdict about that target."""
    record = _record(_trade(usdc_size=10.0), _portfolio())
    assert record["decision"] == SKIPPED
    assert record["target"]["usdc_size"] == 10.0
    assert record["profile_fingerprint"] == _profile().fingerprint


# ------------------------------------------------------------------- exits

def test_a_partial_exit_sells_the_same_fraction_the_target_sold():
    portfolio = _portfolio()
    entry = _record(_trade(usdc_size=50.0, shares=100.0), portfolio)
    held = entry["fill"]["shares"]

    record = _record(_trade(side="SELL", price=0.49, shares=50.0), portfolio)
    assert record["decision"] == COPIED
    assert record["sizing"]["exit_fraction"] == 0.5
    assert abs(record["fill"]["shares"] - held / 2) < 1e-6


def test_a_round_trip_books_the_profit_a_reader_can_check():
    portfolio = _portfolio()
    _record(_trade(usdc_size=50.0, shares=100.0), portfolio,
            book=_book(asks=(("0.50", "1000"),)))
    record = _record(_trade(side="SELL", price=0.60, shares=100.0), portfolio,
                     book=_book(bids=(("0.60", "1000"),)))
    # 3 shares bought at $0.50 and sold at $0.60.
    assert abs(record["realised_pnl_usd"] - 0.30) < 1e-6
    assert portfolio.realised_pnl_usd == record["realised_pnl_usd"]


def test_a_closed_position_frees_its_capital():
    portfolio = _portfolio()
    _record(_trade(usdc_size=50.0, shares=100.0), portfolio)
    assert portfolio.deployed_usd > 0
    _record(_trade(side="SELL", price=0.49, shares=100.0), portfolio)
    assert portfolio.deployed_usd == 0.0


def test_a_sell_the_follower_never_entered_is_a_ghost_exit():
    record = _record(_trade(side="SELL", price=0.49, shares=100.0), _portfolio())
    assert record["skip_reason"] == SKIP_NO_INVENTORY


# --------------------------------------------------------------- redemption

def test_a_redemption_settles_the_position_at_the_payout_rate():
    portfolio = _portfolio()
    _record(_trade(usdc_size=50.0, shares=100.0), portfolio,
            book=_book(asks=(("0.50", "1000"),)))
    record = _record(_trade(activity_type="REDEEM", side="", shares=100.0,
                            usdc_size=100.0), portfolio)
    assert record["decision"] == COPIED
    # 3 shares bought at $0.50 redeem at $1.00.
    assert abs(record["realised_pnl_usd"] - 1.50) < 1e-6


def test_a_redemption_reports_no_friction_rather_than_zero_friction():
    """Settlement is not execution. An undefined friction must not be averaged
    in as a zero that would drag the multiplier down."""
    portfolio = _portfolio()
    _record(_trade(usdc_size=50.0, shares=100.0), portfolio)
    record = _record(_trade(activity_type="REDEEM", side="", shares=100.0,
                            usdc_size=100.0), portfolio)
    assert record["pricing"]["total_slippage_pct"] is None
    assert record["pricing"]["friction_realism_sample"] is None


def test_a_redemption_of_shares_the_follower_never_held_is_recorded_as_a_miss():
    record = _record(_trade(activity_type="REDEEM", side="", shares=100.0,
                            usdc_size=100.0), _portfolio())
    assert record["decision"] == SKIPPED
    assert record["skip_reason"] == SKIP_NO_INVENTORY


# ---------------------------------------------------------------- portfolio

def test_a_portfolio_survives_a_round_trip_through_its_state_file():
    """The poller is stopped and restarted by hand; an open position that did
    not survive the restart would silently free capital it never returned."""
    portfolio = _portfolio()
    _record(_trade(usdc_size=50.0, shares=100.0), portfolio)

    restored = PaperPortfolio.from_dict(portfolio.as_dict(), _profile())
    original = portfolio.position(ASSET)
    assert restored.deployed_usd == portfolio.deployed_usd
    # The state file rounds to six places, which is finer than any figure the
    # log reports; the holding must survive within that, not exactly.
    assert abs(restored.position(ASSET).follower_shares - original.follower_shares) < 1e-6
    assert restored.position(ASSET).target_shares == original.target_shares

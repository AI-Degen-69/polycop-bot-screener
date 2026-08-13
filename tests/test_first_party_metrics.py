#!/usr/bin/env python3
"""The parameters derived from a wallet's own fills.

These four figures replace aggregator fields that nobody could check, so the
arithmetic is pinned here: what each one measures, and - more often the point -
when it refuses to measure at all. Every None below is a case where returning a
number would have handed a wallet points it never earned.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from screener.derived_metrics import MIN_EQUITY_CURVE_POINTS, calculate_drawdown_depth
from screener.first_party_metrics import (
    HEDGE_DUST_SHARES,
    equity_curve,
    hedged_rate,
    pnl_to_volume_ratio,
    profit_loss_ratio,
    recent_window_results,
)


def _settled(results):
    return [
        {"condition_id": f"0xc{i}", "result_usdc": float(v),
         "closed_at": 1000 + i, "notional_usdc": 10.0}
        for i, v in enumerate(results)
    ]


def _position(condition, asset, size):
    return {"conditionId": condition, "asset": asset, "size": size}


# ------------------------------------------------------------- equity curve

def test_the_curve_accumulates_the_per_market_results():
    assert equity_curve(_settled([10, -4, 6])) == [10.0, 6.0, 12.0]


def test_no_settled_market_produces_no_curve():
    assert equity_curve([]) is None
    assert equity_curve(None) is None


def test_a_short_curve_is_refused_by_the_drawdown_measure_not_by_this_one():
    """The minimum-points floor lives in one place, with the function that owns
    what 'too short to describe a track record' means."""
    curve = equity_curve(_settled([10, -4, 6]))
    assert curve is not None
    assert len(curve) < MIN_EQUITY_CURVE_POINTS
    assert calculate_drawdown_depth(curve) is None


def test_a_wallet_that_halved_and_recovered_still_reports_the_deep_fall():
    # +100 then -60 is a 60% fall from the peak it fell from, even though the
    # curve goes on to a new high.
    results = [100, -60, 20, 20, 20, 20]
    assert calculate_drawdown_depth(equity_curve(_settled(results))) == 0.6


# --------------------------------------------------------- profit/loss ratio

def test_the_ratio_is_the_average_win_over_the_average_loss():
    assert profit_loss_ratio(_settled([10, 20, -5])) == 3.0


def test_a_wallet_that_has_never_lost_has_an_undefined_ratio_not_an_infinite_one():
    """This figure is a hard gate. An infinity would clear it on no evidence."""
    assert profit_loss_ratio(_settled([10, 20])) is None


def test_a_wallet_that_has_never_won_has_an_undefined_ratio():
    assert profit_loss_ratio(_settled([-10, -20])) is None


def test_no_settled_market_produces_no_ratio():
    assert profit_loss_ratio([]) is None


# -------------------------------------------------------- pnl / volume ratio

def test_the_ratio_is_a_percentage_of_traded_volume():
    assert pnl_to_volume_ratio(250.0, 1000.0) == 25.0


def test_zero_volume_is_unmeasurable_rather_than_infinite():
    assert pnl_to_volume_ratio(250.0, 0.0) is None


def test_an_absent_figure_on_either_side_leaves_the_ratio_unmeasured():
    assert pnl_to_volume_ratio(None, 1000.0) is None
    assert pnl_to_volume_ratio(250.0, None) is None


def test_a_losing_wallet_reports_a_negative_ratio_rather_than_nothing():
    # A measured loss is a result; only an unmeasurable one is absent.
    assert pnl_to_volume_ratio(-250.0, 1000.0) == -25.0


# ---------------------------------------------------------------- hedged rate

def test_holding_both_outcomes_of_one_market_counts_once():
    positions = [
        _position("0xa", "yes", 100.0),
        _position("0xa", "no", 100.0),
        _position("0xb", "yes", 100.0),
    ]
    assert hedged_rate(positions) == 50.0


def test_holding_one_side_of_every_market_is_not_hedging():
    positions = [_position("0xa", "yes", 100.0), _position("0xb", "yes", 100.0)]
    assert hedged_rate(positions) == 0.0


def test_dust_on_the_losing_side_is_not_a_hedge():
    """A resolved market leaves fractional shares of the worthless side behind.
    Counting those as market-making would flag every wallet that ever won."""
    positions = [
        _position("0xa", "yes", 100.0),
        _position("0xa", "no", HEDGE_DUST_SHARES / 2),
    ]
    assert hedged_rate(positions) == 0.0


def test_an_empty_positions_feed_is_unmeasured_not_unhedged():
    """This figure gates and carries points, so a feed that returned nothing
    must not read as a wallet that hedged nothing."""
    assert hedged_rate([]) is None
    assert hedged_rate(None) is None


def test_a_feed_of_only_dust_measures_nothing():
    assert hedged_rate([_position("0xa", "yes", 0.0)]) is None


def test_a_row_without_an_outcome_identifier_is_skipped_not_guessed():
    positions = [{"conditionId": "0xa", "size": 100.0}]
    assert hedged_rate(positions) is None


# ------------------------------------------------------------ recent window

def test_the_window_takes_the_most_recent_markets_oldest_first():
    window = recent_window_results(_settled([1, 2, 3, 4, 5]), 3)
    assert [entry["result_usdc"] for entry in window] == [3.0, 4.0, 5.0]


def test_a_record_shorter_than_the_window_returns_what_exists():
    window = recent_window_results(_settled([1, 2]), 20)
    assert len(window) == 2


def test_an_empty_record_has_an_empty_window():
    assert recent_window_results([], 20) == []
    assert recent_window_results(None, 20) == []

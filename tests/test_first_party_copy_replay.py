#!/usr/bin/env python3
"""The replayed Modelled Copy PnL.

This module produces the figure the Toxic Copy Poison gate reads directly, and
the figure the Slippage Cost Rate gate plus 17 points are derived from, so a
silent arithmetic error here propagates into two gates and 37 scored points with
nothing downstream able to detect it. The rules are pinned accordingly: what the
profile mirrors, what it refuses, what friction costs, and what an unmeasurable
wallet returns.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from execution.copy_execution_profile import CopyExecutionProfile
from screener.first_party_copy_replay import (
    MODELLED_SLIPPAGE_PCT_PER_SIDE,
    daily_green_rate,
    mirror_profile,
    replay_copy,
)

DAY = 86400
MARKET = "0xc1"


def _profile(**overrides):
    return CopyExecutionProfile(**overrides)


def _buy(timestamp=1000, price=0.5, shares=100.0, usdc=50.0, market=MARKET):
    return {"timestamp": timestamp, "conditionId": market, "type": "TRADE",
            "side": "BUY", "price": price, "size": shares, "usdcSize": usdc}


def _sell(timestamp=2000, price=0.8, shares=100.0, usdc=80.0, market=MARKET):
    return {"timestamp": timestamp, "conditionId": market, "type": "TRADE",
            "side": "SELL", "price": price, "size": shares, "usdcSize": usdc}


def _redeem(timestamp=3000, shares=100.0, usdc=100.0, market=MARKET):
    return {"timestamp": timestamp, "conditionId": market, "type": "REDEEM",
            "size": shares, "usdcSize": usdc}


def _settled(*markets):
    return [
        {"condition_id": m, "result_usdc": 1.0, "closed_at": 1000 + i * DAY,
         "notional_usdc": 50.0}
        for i, m in enumerate(markets)
    ]


def _replay(events, settled=None, profile=None, window=20):
    return replay_copy(events, settled if settled is not None else _settled(MARKET),
                       profile or _profile(), window)


# ----------------------------------------------------------------- the copy

def test_a_winning_round_trip_returns_less_than_the_target_made():
    """Friction is charged on both legs, so the copy keeps less of the move."""
    out = _replay([_buy(price=0.5, usdc=50.0), _sell(price=0.8)])
    assert out["bankroll_copy_pnl"] > 0
    target_return = (0.8 - 0.5) / 0.5
    copy_return = out["bankroll_copy_pnl"] / 1.5
    assert copy_return < target_return


def test_more_assumed_friction_returns_less():
    events = [_buy(price=0.5, usdc=50.0), _sell(price=0.8)]
    cheap = _replay(events, profile=_profile(slippage_pct=2.0))
    dear = _replay(events, profile=_profile(slippage_pct=15.0))
    assert dear["bankroll_copy_pnl"] < cheap["bankroll_copy_pnl"]


def test_the_modelled_figure_does_not_move_with_the_sweep_level():
    """The Slippage Sensitivity Sweep raises `slippage_pct` deliberately. If the
    modelled counterfactual moved with it, the gate calibrated against that
    figure would shift every time the sweep was retuned."""
    events = [_buy(price=0.5, usdc=50.0), _sell(price=0.8)]
    cheap = _replay(events, profile=_profile(slippage_pct=2.0))
    dear = _replay(events, profile=_profile(slippage_pct=15.0))
    assert dear["modelled_copy_pnl"] == cheap["modelled_copy_pnl"]


def test_the_mirror_is_full_size_so_the_gap_is_friction_not_scale():
    """Measured against a bankroll-scaled copy, the gap between a target's
    profit and the copy's is dominated by the copy trading a fraction of the
    size - which would fail every large wallet on a gate about friction."""
    # Inside the bankroll's window, so the bankroll copy does trade it and the
    # comparison is about scale rather than about the window refusing it.
    events = [_buy(price=0.5, usdc=150.0, shares=300.0),
              _sell(price=0.9, usdc=270.0, shares=300.0)]
    out = _replay(events)
    target_pnl = 120.0
    # The mirror keeps most of a strong edge; the bankroll copy keeps a
    # fraction of it, because it only ever committed a few dollars.
    assert out["modelled_copy_pnl"] > target_pnl * 0.5
    assert out["bankroll_copy_pnl"] < target_pnl * 0.05


def test_the_mirror_lifts_the_caps_but_keeps_the_price_bounds():
    mirror = mirror_profile(_profile())
    assert mirror.copy_ratio == 1.0
    assert mirror.slippage_pct == MODELLED_SLIPPAGE_PCT_PER_SIDE
    assert mirror.window_max_usd > 1e9
    # A market the bot will not trade is not one a mirror of it trades either.
    assert mirror.min_price == _profile().min_price
    assert mirror.max_price == _profile().max_price


def test_a_trade_below_the_window_is_not_mirrored_at_all():
    """The gap between what the target earned and what the copy earned on the
    trades it could not follow is the whole of what Slippage Cost Rate means."""
    out = _replay([_buy(usdc=5.0), _sell()])
    assert out["replayed_markets"] == 0
    assert out["bankroll_copy_pnl"] is None
    # The full-size mirror has no bankroll to constrain, so it still measures
    # the trade. Asserting only the bankroll side would pass even if the mirror
    # wrongly refused it too, which would silently break the friction gates.
    assert out["modelled_copy_pnl"] is not None


def test_a_trade_above_the_window_is_not_mirrored_either():
    profile = _profile()
    out = _replay([_buy(usdc=profile.window_max_usd * 10), _sell()], profile=profile)
    assert out["replayed_markets"] == 0
    assert out["bankroll_copy_pnl"] is None
    assert out["modelled_copy_pnl"] is not None


def test_a_price_outside_the_profile_bounds_is_not_copied():
    out = _replay([_buy(price=0.99, usdc=50.0), _sell(price=0.995)])
    assert out["replayed_markets"] == 0


def test_an_exit_above_the_price_ceiling_still_closes_the_position():
    """The price bounds decide which markets the bot enters. Applied to exits
    too, a target selling above the ceiling would leave a position the follower
    did open to expire worthless - booking a loss it never took."""
    entered = _replay([_buy(price=0.5, usdc=50.0), _sell(price=0.97)])
    assert entered["bankroll_copy_pnl"] > 0


def test_the_position_cap_clips_a_large_copy():
    profile = _profile()
    out = _replay([_buy(usdc=profile.window_max_usd, price=0.5)], profile=profile)
    # The copy spent the cap, not the full nominal ratio of a large trade.
    assert out["bankroll_copy_pnl"] == -profile.max_single_position_usd


def test_the_global_cap_stops_a_copy_in_a_fresh_market():
    profile = _profile(global_cap_usd=2.0)
    events = [
        _buy(timestamp=1000, usdc=50.0, market="0xa"),
        _buy(timestamp=2000, usdc=50.0, market="0xb"),
    ]
    out = _replay(events, settled=_settled("0xa", "0xb"), profile=profile)
    # Only the first market drew capital; the second found the bankroll deployed.
    assert out["replayed_markets"] == 1


def test_a_partial_exit_mirrors_the_fraction_the_target_sold():
    half = _replay([_buy(shares=100.0, usdc=50.0), _sell(shares=50.0, price=0.8)])
    full = _replay([_buy(shares=100.0, usdc=50.0), _sell(shares=100.0, price=0.8)])
    assert half["bankroll_copy_pnl"] < full["bankroll_copy_pnl"]


def test_a_redemption_settles_the_position_without_charging_friction():
    """Settlement pays a fixed rate per share. There is no book to cross."""
    out = _replay([_buy(price=0.5, usdc=50.0), _redeem(shares=100.0, usdc=100.0)])
    assert out["bankroll_copy_pnl"] > 0


def test_a_worthless_redemption_leaves_the_position_a_total_loss():
    out = _replay([_buy(price=0.5, usdc=50.0), _redeem(shares=100.0, usdc=0.0)])
    # The bankroll committed $1.50 and lost it; the mirror committed the
    # target's full $50 and lost that.
    assert out["bankroll_copy_pnl"] == -1.5
    assert out["modelled_copy_pnl"] == -50.0


# ------------------------------------------------------------ absent figures

def test_a_wallet_with_no_settled_market_measures_nothing():
    """Zero is a measured break-even; None is an unmeasured wallet, and the
    gates must reject on the second (ADR 0007)."""
    out = replay_copy([_buy()], [], _profile(), 20)
    assert out["modelled_copy_pnl"] is None
    assert out["bankroll_copy_pnl"] is None
    assert out["per_day_copy_pnl"] is None
    assert out["recent_window_target_pnl"] is None
    assert out["recent_window_friction_pct"] is None


def test_a_market_the_scanner_could_not_settle_is_not_replayed():
    """A market whose cost basis the window only partly covers is unscoreable
    for the target, and scoring it for the follower would book a payout against
    a fraction of its cost."""
    events = [_buy(market="0xa"), _buy(timestamp=1500, market="0xunsettled")]
    out = _replay(events, settled=_settled("0xa"))
    assert out["replayed_markets"] == 1


def test_a_market_the_bankroll_never_entered_contributes_nothing_to_it():
    """The window refused the trade for this bankroll. The full-size mirror
    still takes it, because the window is a bankroll constraint and the mirror
    exists to measure friction without one."""
    out = _replay([_buy(usdc=5.0)], settled=_settled(MARKET))
    assert out["replayed_markets"] == 0
    assert out["bankroll_copy_pnl"] is None
    assert out["modelled_copy_pnl"] is not None


# --------------------------------------------------------------- the windows

def test_the_per_day_map_buckets_by_the_close_date():
    events = [_buy(market="0xa"), _sell(market="0xa", price=0.8)]
    out = _replay(events, settled=_settled("0xa"))
    assert out["per_day_copy_pnl"] is not None
    assert len(out["per_day_copy_pnl"]) == 1


def test_a_day_nothing_settled_on_is_absent_rather_than_flat():
    """Counting an idle day as flat would dilute the green rate and inflate the
    observed-day count the score's floor relies on."""
    events = [_buy(market="0xa"), _sell(market="0xa", price=0.8)]
    out = _replay(events, settled=_settled("0xa"))
    rate, observed = daily_green_rate(out["per_day_copy_pnl"])
    assert observed == 1
    assert rate == 100.0


def test_the_recent_window_covers_the_last_n_settled_markets():
    settled = _settled(*[f"0x{i}" for i in range(30)])
    out = replay_copy([], settled, _profile(), 20)
    # The target's own profit over the window: 20 markets at $1 each.
    assert out["recent_window_target_pnl"] == 20.0


def test_a_record_shorter_than_the_window_is_measured_over_what_exists():
    out = replay_copy([], _settled("0xa", "0xb"), _profile(), 20)
    assert out["recent_window_target_pnl"] == 2.0


def test_the_window_friction_is_a_share_of_the_capital_the_copy_turned_over():
    out = _replay([_buy(price=0.5, usdc=50.0), _sell(price=0.8)],
                  profile=_profile(slippage_pct=10.0))
    # Both legs slipped 10%, so the friction lands on the same scale the Recent
    # Form ceiling is expressed in, not at zero and not above 100.
    assert 0.0 < out["recent_window_friction_pct"] < 15.0


def test_the_window_refusing_a_trade_does_not_make_friction_unmeasured():
    """Recent Form weighs the target's own return against the friction it came
    through, so the friction term is measured on the mirror. Read off the
    bankroll pass it would go absent whenever the Copyable Trade Window refused
    the recent stretch - a statement about the window, not about friction, and
    window share is simulation-only (ADR 0006)."""
    out = _replay([_buy(usdc=5.0)], settled=_settled(MARKET))
    assert out["bankroll_copy_pnl"] is None
    assert out["recent_window_friction_pct"] is not None


def test_friction_is_unmeasured_when_the_mirror_turned_over_nothing():
    # Priced outside the profile's bounds, so no pass enters the market at all.
    out = _replay([_buy(price=0.99, usdc=50.0)], settled=_settled(MARKET))
    assert out["recent_window_friction_pct"] is None


# ------------------------------------------------------------ the green rate

def test_the_green_rate_counts_days_the_copy_finished_up():
    rate, observed = daily_green_rate({"2026-08-01": 5.0, "2026-08-02": -1.0})
    assert rate == 50.0
    assert observed == 2


def test_a_flat_day_is_observed_but_not_green():
    rate, observed = daily_green_rate({"2026-08-01": 0.0})
    assert rate == 0.0
    assert observed == 1


def test_no_per_day_record_measures_no_rate():
    assert daily_green_rate(None) == (None, 0)
    assert daily_green_rate({}) == (None, 0)

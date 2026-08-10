#!/usr/bin/env python3
import json
import os
import sys

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from execution.copy_execution_profile import CURRENT_PROFILE

# ---------------------------------------------------------------------------
# Hard Rejection Gate constants.
#
# These are the single machine-readable source of truth for the gate values.
# The scoring engine reads them, and `tools/scoring_docs.py` renders the
# documentation tables from them, so a gate can never change in the code
# without the docs being regenerated (the CI drift check fails until they
# match). Never write a gate threshold as an inline literal here.
# ---------------------------------------------------------------------------

# Whale gate: a target whose typical trade dwarfs the bankroll cannot be mirrored at
# any sane participation rate. A screening gate rather than a bot setting, so it is
# not part of the Copy Execution Profile.
WHALE_AVG_INVEST_LIMIT_USD = 200.0

# Sanity floor for manually pasted addresses. The leaderboard site-score pre-filter
# is gone, so this is what stops arbitrary garbage from being scored.
SITE_SCORE_SANITY_FLOOR = 40.0

# Toxic Copy Poison: a modelled copy that loses money is not a target.
BACKTEST_COPY_PNL_MIN_USD = 0.0

# Slippage Cost Rate gate, in modelled terms. 5% modelled is roughly 20% real under
# the Friction Realism Multiplier of 4.2 (ADR 0001).
SLIPPAGE_COST_RATE_GATE = 0.05

# How much worse real execution friction is than the leaderboard model assumes.
# A tracked estimate (ADR 0001), not a constant: it is expected to move as more
# live fills are logged, and the docs are generated from it so they move too.
FRICTION_REALISM_MULTIPLIER = 4.2

# Hedged Rate gate: a market-making signature and a doubling of the legs on which
# friction is paid.
HEDGED_RATE_GATE_PCT = 3.0

# Profit/Loss Ratio gate: winning pennies, losing dollars.
PL_RATIO_GATE = 0.3

# Markets Sample gate: fewer markets and the record is a streak, not a track record.
MARKETS_GATE = 20

# Divergence gate: a dead edge must not be carried by history. Rejects a wallet
# whose recent form is negative while lifetime performance is strongly positive.
DIVERGENCE_LIFETIME_PNL_USD = 1000.0

# ---------------------------------------------------------------------------
# Continuous parameter constants.
# ---------------------------------------------------------------------------

# Edge-to-Friction of 1.0 is break-even: the edge is exactly consumed by the cost
# of following it. Points start there rather than peaking there. Full marks need
# an edge three times the friction, which leaves room for the friction estimate
# itself to be wrong without the wallet turning unprofitable.
EDGE_TO_FRICTION_BREAK_EVEN = 1.0
EDGE_TO_FRICTION_FULL_MARKS = 3.0

# A wallet that has given back half its peak scores nothing for drawdown. At a
# $100 bankroll a fall that deep is not a dip to ride out.
DRAWDOWN_DEPTH_ZERO_AT = 0.50

# Below this many observed days a green rate is a streak, not a record.
MIN_OBSERVED_DAYS = 10

# Recent Form reads profit as a return on the capital that produced it, judged
# against the friction it was earned through. Profit taken entirely through this
# much slippage is worth nothing to a follower.
#
# The recent-20 window covers the target's most recent 20 trades, so the capital
# deployed over it is 20 trades at the target's average investment. An
# absolute-dollar scale would reward the target's size rather than its edge, and
# size is the thing the Copyable Trade Window already constrains elsewhere — see
# ADR 0004. Full marks at a 100% return over the window, before the friction
# discount.
RECENT_FORM_SLIP_CEILING_PCT = 15.0
RECENT_FORM_WINDOW_TRADES = 20.0
RECENT_FORM_FULL_MARKS_RETURN = 1.0

# Copyability Score tier bands, calibrated against the distribution of a real
# scored run over the cached leaderboard data (ADR 0005). Absolute, not
# percentile: a scan full of weak wallets must not manufacture an S-Tier.
# These bands grade the triage score only; verdicts come from simulation.
TIER_S_MIN = 72.0
TIER_A_MIN = 65.0
TIER_B_MIN = 60.0
TIER_C_MIN = 50.0

# A Hidden Gem is a wallet the screen grades highly while the leaderboard's own
# score rates it poorly. Tied to the recalibrated A-Tier floor (ADR 0005).
GEM_SITE_SCORE_MAX = 75.0

# Simulated Verdict tier bands, on Edge Retention (the share of simulated
# profit that survives rising friction). ADR 0002: verdicts come from
# simulation, so these bands grade simulated performance — distinct from the
# triage bands above, which only order wallets for simulation. Inherited from
# the outgoing engine; recalibration would follow ADR 0005's method.
SIM_TIER_S_MIN = 0.85
SIM_TIER_A_MIN = 0.70
SIM_TIER_B_MIN = 0.50
SIM_TIER_C_MIN = 0.30

# ---------------------------------------------------------------------------
# Machine-readable scoring spec. Rendered into the docs by tools/scoring_docs.py;
# the CI drift check fails when the docs drift from it.
# ---------------------------------------------------------------------------

SCORING_SPEC = {
    "gates": [
        {
            "name": "PolyCop Site Score sanity floor",
            "condition": f"< {SITE_SCORE_SANITY_FLOOR:.0f} / 100",
            "reason": "stops manually pasted garbage from being scored once the leaderboard pre-filter is gone",
        },
        {
            "name": "Toxic Copy Poison",
            "condition": f"Copy PnL < ${BACKTEST_COPY_PNL_MIN_USD:.0f}",
            "reason": "a modelled copy that loses money is not a target",
        },
        {
            "name": "Slippage Cost Rate",
            "condition": f"> {SLIPPAGE_COST_RATE_GATE * 100:.1f}% modelled",
            "reason": f"roughly {SLIPPAGE_COST_RATE_GATE * 100 * FRICTION_REALISM_MULTIPLIER:.0f}% real under the Friction Realism Multiplier (ADR 0001)",
        },
        {
            "name": "Hedged Rate",
            "condition": f"> {HEDGED_RATE_GATE_PCT:.1f}%",
            "reason": "market-making signature and doubled friction legs",
        },
        {
            "name": "Profit/Loss Ratio",
            "condition": f"< {PL_RATIO_GATE:.1f}",
            "reason": "winning pennies, losing dollars",
        },
        {
            "name": "Markets Sample",
            "condition": f"< {MARKETS_GATE:.0f}",
            "reason": "a streak, not a track record",
        },
        {
            "name": "Whale Avg Invest",
            "condition": f"> ${WHALE_AVG_INVEST_LIMIT_USD:.0f}",
            "reason": "a typical trade that dwarfs the bankroll cannot be mirrored",
        },
        {
            "name": "Divergence",
            "condition": f"r20_pnl < $0 while actual_pnl > ${DIVERGENCE_LIFETIME_PNL_USD:,.0f}",
            "reason": "a dead edge must not be carried by history",
        },
    ],
    "parameters": [
        {
            "name": "Edge-to-Friction Ratio",
            "points": 22,
            "zero": f"<= {EDGE_TO_FRICTION_BREAK_EVEN:.1f} (break-even)",
            "full": f">= {EDGE_TO_FRICTION_FULL_MARKS:.1f}",
            "note": "edge per dollar of friction; the cheapest disqualifying arithmetic runs first",
            "radar": "Edge/Friction",
        },
        {
            "name": "Slippage Cost Rate",
            "points": 15,
            "zero": f">= {SLIPPAGE_COST_RATE_GATE * 100:.1f}%",
            "full": "<= 1.0%",
            "note": "modelled, before the Friction Realism Multiplier",
            "radar": "Slippage Cost",
        },
        {
            "name": "Drawdown Depth",
            "points": 12,
            "zero": f">= {DRAWDOWN_DEPTH_ZERO_AT:.2f} of peak",
            "full": "0.0",
            "note": "from the lifetime equity curve",
            "radar": "Drawdown",
        },
        {
            "name": "Copyable Window Share",
            "points": 10,
            "zero": "0%",
            "full": "100%",
            "note": "share of trades the Copyable Trade Window admits",
            "radar": "Window Share",
        },
        {
            "name": "Recent Form",
            "points": 10,
            "zero": "PnL <= $0 or slip unmeasured",
            "full": f">= {RECENT_FORM_FULL_MARKS_RETURN * 100:.0f}% return over the recent-{RECENT_FORM_WINDOW_TRADES:.0f} window at 0% slip",
            "note": "return on deployed capital, judged against the friction it came through (ADR 0004)",
            "radar": "Recent Form",
        },
        {
            "name": "Daily Green Rate",
            "points": 8,
            "zero": f"< 40% or fewer than {MIN_OBSERVED_DAYS:.0f} observed days",
            "full": ">= 85%",
            "note": "copy-adjusted, measured from real per-day simulated results",
            "radar": "Green Rate",
        },
        {
            "name": "Profit/Loss Ratio",
            "points": 8,
            "zero": f"<= {PL_RATIO_GATE:.1f}",
            "full": ">= 3.0",
            "note": "",
            "radar": "P/L Ratio",
        },
        {
            "name": "Sizing Fit",
            "points": 5,
            "zero": "outside the Copyable Trade Window",
            "full": "at the window midpoint",
            "note": "peak derived from the Copy Execution Profile, never hand-picked",
            "radar": "Sizing Fit",
        },
        {
            "name": "Hedged Control",
            "points": 5,
            "zero": f">= {HEDGED_RATE_GATE_PCT:.1f}%",
            "full": "0%",
            "note": "",
            "radar": "Hedged",
        },
        {
            "name": "Markets Sample",
            "points": 3,
            "zero": f"< {MARKETS_GATE:.0f}",
            "full": ">= 200",
            "note": "",
            "radar": "Markets",
        },
        {
            "name": "Capital Efficiency",
            "points": 2,
            "zero": "0",
            "full": ">= 30 PnL/volume ratio",
            "note": "",
            "radar": "Efficiency",
        },
    ],
    "tiers": [
        {"label": "S-Tier (God-Tier Target)", "min": TIER_S_MIN},
        {"label": "A-Tier (Strong Copy Target)", "min": TIER_A_MIN},
        {"label": "B-Tier (Moderate Copy Target)", "min": TIER_B_MIN},
        {"label": "C-Tier (High Risk / Volatile)", "min": TIER_C_MIN},
        {"label": "F-Tier (Toxic / Rejection)", "min": None},
    ],
    "sim_tiers": [
        {"label": "S-Tier (God-Tier Target)", "min": SIM_TIER_S_MIN},
        {"label": "A-Tier (Strong Copy Target)", "min": SIM_TIER_A_MIN},
        {"label": "B-Tier (Moderate Copy Target)", "min": SIM_TIER_B_MIN},
        {"label": "C-Tier (High Risk / Volatile)", "min": SIM_TIER_C_MIN},
        {"label": "F-Tier / REJECT", "min": None},
    ],
}


def _measured(value):
    """A metric that was actually measured, or None if it was not.

    Distinguishes an absent measurement from a measured zero, so scoring can
    refuse to reward the first while still recording the second.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def grade_for_score(final_score: float) -> str:
    """The triage grade a Copyability Score earns under the recalibrated bands.

    Triage only: verdicts come from simulation. Extracted from the engine so the
    band mapping is unit-testable and the web app can reuse the exact wording.
    """
    if final_score >= TIER_S_MIN:
        return "S-Tier (God-Tier Target)"
    if final_score >= TIER_A_MIN:
        return "A-Tier (Strong Copy Target)"
    if final_score >= TIER_B_MIN:
        return "B-Tier (Moderate Copy Target)"
    if final_score >= TIER_C_MIN:
        return "C-Tier (High Risk / Volatile)"
    return "F-Tier (Toxic / Rejection)"


def calculate_edge_retention(pnl_10_pct: float, pnl_2_pct: float) -> float | None:
    """
    Calculate edge retention ratio between 10% and 2% slippage simulation levels.
    Enforces gate ordering: PnL at 10% must be > $0 and PnL at 2% must be > $0.
    Returns None if either simulation level produced non-positive PnL.
    """
    if pnl_10_pct <= 0 or pnl_2_pct <= 0:
        return None
    return pnl_10_pct / pnl_2_pct


def calculate_bankroll_optimized_score(metrics, user_capital=None, profile=CURRENT_PROFILE):
    """
    PolyCop Reweighted 100-Point Triage Engine, run under one Copy Execution Profile.
    Reallocated 11 continuous parameters (Total 100 pts).

    HARD REJECTION GATES (see SCORING_SPEC):
    1. PolyCop Site Score < 40.0 -> Low quality sanity floor.
    2. Backtest Copy PnL < $0 -> Toxic Copy Poison.
    3. Slippage Cost Rate > 5% modelled (0.05) -> Friction limit.
    4. Hedged Rate > 3.0% -> $100 Bankroll ratio distortion / arb risk.
    5. P/L Ratio < 0.3 -> Liquidation Risk.
    6. Markets Sample < 20 -> Short Track Record.
    7. Avg Invest > $200.00 USD -> Whale Trade Sizing Friction.
    8. Divergence Gate: r20_pnl < 0 while actual_pnl > $1,000 -> Decay / inversion risk.
    """
    if user_capital is not None:
        profile = profile.with_bankroll(user_capital)

    score = 0.0
    breakdown = {}
    rejection_reasons = []

    actual_pnl = float(metrics.get("actual_pnl", metrics.get("copy_pnl", 0.0)))
    copy_pnl = float(metrics.get("copy_pnl", -1.0))
    hedged = float(metrics.get("hedged_pct", 100.0))
    pl_ratio = float(metrics.get("pl_ratio", 0.0))
    r20_pnl = float(metrics.get("r20_pnl", 0.0))
    # Unmeasured slip is not frictionless slip. A missing value here used to
    # arrive as zero from the pipeline, which is the best possible reading.
    r20_slip = _measured(metrics.get("r20_slip"))
    pnl_vol = float(metrics.get("pnl_vol_ratio", 0.0))
    mkts = float(metrics.get("markets", 0))
    avg_inv = float(metrics.get("avg_invest", 0.0))
    polycop_site_score = float(metrics.get("polycop_site_score", 0.0))
    # These four are measured rather than read off the leaderboard, and any of
    # them can be unavailable. None means unmeasured and scores nothing: a
    # default would hand out points the wallet never earned, which is exactly
    # how a previous version of this engine gave every candidate a free 44.
    drawdown_depth = _measured(metrics.get("drawdown_depth"))
    window_share = _measured(metrics.get("copyable_window_share"))
    edge_to_friction = _measured(metrics.get("edge_to_friction"))
    daily_green_rate = _measured(metrics.get("days_win_rate"))
    observed_days = int(metrics.get("observed_days") or 0)

    if abs(actual_pnl) > 0:
        slip_cost_rate = max(0.0, (actual_pnl - copy_pnl) / abs(actual_pnl))
    else:
        slip_cost_rate = 0.0

    # --- HARD REJECTION GATES ---
    if polycop_site_score < SITE_SCORE_SANITY_FLOOR:
        rejection_reasons.append(f"PolyCop Site Score {polycop_site_score:.0f} < {SITE_SCORE_SANITY_FLOOR:.0f}/100 sanity floor")
    if copy_pnl < BACKTEST_COPY_PNL_MIN_USD:
        rejection_reasons.append("Backtest Copy PnL < $0 (Toxic Copy Poison)")
    if slip_cost_rate > SLIPPAGE_COST_RATE_GATE:
        rejection_reasons.append(f"Slippage Cost Rate {slip_cost_rate*100:.1f}% > {SLIPPAGE_COST_RATE_GATE*100:.1f}% modelled limit")
    if hedged > HEDGED_RATE_GATE_PCT:
        rejection_reasons.append(f"Hedged Rate {hedged}% > {HEDGED_RATE_GATE_PCT}%")
    if pl_ratio < PL_RATIO_GATE:
        rejection_reasons.append(f"P/L Ratio {pl_ratio:.2f}x < {PL_RATIO_GATE:.1f}x")
    if mkts < MARKETS_GATE:
        rejection_reasons.append(f"Short Track Record ({int(mkts)} markets < {MARKETS_GATE:.0f} min threshold)")
    if avg_inv > WHALE_AVG_INVEST_LIMIT_USD:
        rejection_reasons.append(f"Whale Avg Invest (${avg_inv:.2f} > ${WHALE_AVG_INVEST_LIMIT_USD:.0f})")
    if r20_pnl < 0 and actual_pnl > DIVERGENCE_LIFETIME_PNL_USD:
        rejection_reasons.append(f"Divergence Gate: Negative Recent Form (${r20_pnl:.2f}) vs strongly positive lifetime PnL (${actual_pnl:.2f})")

    # --- 11 REWEIGHTED CONTINUOUS PARAMETERS (TOTAL 100 PTS) ---

    # 1. Edge-to-Friction Ratio (22 pts) - nothing at break-even, full marks at 3x
    if edge_to_friction is None or edge_to_friction <= EDGE_TO_FRICTION_BREAK_EVEN:
        etf_score = 0.0
    elif edge_to_friction >= EDGE_TO_FRICTION_FULL_MARKS:
        etf_score = 22.0
    else:
        span = EDGE_TO_FRICTION_FULL_MARKS - EDGE_TO_FRICTION_BREAK_EVEN
        etf_score = 22.0 * ((edge_to_friction - EDGE_TO_FRICTION_BREAK_EVEN) / span)
    score += etf_score
    breakdown["edge_to_friction"] = round(etf_score, 2)

    # 2. Slippage Cost Rate (15 pts)
    if slip_cost_rate <= 0.01:
        slip_score = 15.0
    elif slip_cost_rate >= SLIPPAGE_COST_RATE_GATE:
        slip_score = 0.0
    else:
        slip_score = 15.0 * (1.0 - ((slip_cost_rate - 0.01) / (SLIPPAGE_COST_RATE_GATE - 0.01)))
    score += slip_score
    breakdown["slippage_cost_rate"] = round(slip_score, 2)

    # 3. Drawdown Depth (12 pts)
    if drawdown_depth is None:
        dd_score = 0.0
    else:
        dd_score = max(0.0, 12.0 * (1.0 - min(1.0, drawdown_depth / DRAWDOWN_DEPTH_ZERO_AT)))
    score += dd_score
    breakdown["drawdown_depth"] = round(dd_score, 2)

    # 4. Copyable Window Share (10 pts)
    cws_score = 0.0 if window_share is None else min(10.0, max(0.0, window_share * 10.0))
    score += cws_score
    breakdown["window_share"] = round(cws_score, 2)

    # 5. Recent Form (10 pts) - recent return judged against the friction it came through
    if r20_pnl <= 0 or r20_slip is None or avg_inv <= 0:
        rf_score = 0.0
    else:
        slip_factor = 1.0 - (min(max(r20_slip, 0.0), RECENT_FORM_SLIP_CEILING_PCT)
                             / RECENT_FORM_SLIP_CEILING_PCT)
        recent_return = r20_pnl / (RECENT_FORM_WINDOW_TRADES * avg_inv)
        return_factor = min(recent_return / RECENT_FORM_FULL_MARKS_RETURN, 1.0)
        rf_score = 10.0 * slip_factor * return_factor
    score += rf_score
    breakdown["recent_form"] = round(rf_score, 2)

    # 6. Daily Green Rate (8 pts) - a rate drawn from too few days is a streak
    if daily_green_rate is None or observed_days < MIN_OBSERVED_DAYS or daily_green_rate <= 40.0:
        days_score = 0.0
    elif daily_green_rate >= 85.0:
        days_score = 8.0
    else:
        days_score = 8.0 * ((daily_green_rate - 40.0) / (85.0 - 40.0))
    score += days_score
    breakdown["daily_green_rate"] = round(days_score, 2)

    # 7. Profit/Loss Ratio (8 pts)
    if pl_ratio <= PL_RATIO_GATE:
        pl_score = 0.0
    elif pl_ratio >= 3.0:
        pl_score = 8.0
    else:
        pl_score = 8.0 * ((pl_ratio - PL_RATIO_GATE) / (3.0 - PL_RATIO_GATE))
    score += pl_score
    breakdown["pl_ratio"] = round(pl_score, 2)

    # 8. Sizing Fit (5 pts) - full marks at the window midpoint, nothing outside it
    #
    # Outside the Copyable Trade Window the realised copy ratio stops matching the
    # nominal one: below it the venue minimum bumps the order up, above it the
    # position cap clips it down. Neither is a mirror of the target, so neither
    # earns points however close to the boundary it sits.
    window_low = profile.window_min_usd
    window_high = profile.window_max_usd
    sizing_peak = profile.sizing_fit_peak_usd
    if avg_inv <= window_low or avg_inv >= window_high:
        inv_score = 0.0
    elif avg_inv <= sizing_peak:
        inv_score = 5.0 * ((avg_inv - window_low) / (sizing_peak - window_low))
    else:
        inv_score = 5.0 * ((window_high - avg_inv) / (window_high - sizing_peak))
    score += inv_score
    breakdown["sizing_fit"] = round(inv_score, 2)

    # 9. Hedged Control (5 pts)
    if hedged > HEDGED_RATE_GATE_PCT:
        hedged_score = 0.0
    else:
        hedged_score = 5.0 * (1.0 - (hedged / HEDGED_RATE_GATE_PCT))
    score += hedged_score
    breakdown["hedged_control"] = round(hedged_score, 2)

    # 10. Markets Sample (3 pts)
    if mkts < MARKETS_GATE:
        mkt_score = 0.0
    elif mkts >= 200:
        mkt_score = 3.0
    else:
        mkt_score = 3.0 * ((mkts - MARKETS_GATE) / (200.0 - MARKETS_GATE))
    score += mkt_score
    breakdown["markets_sample"] = round(mkt_score, 2)

    # 11. Capital Efficiency (2 pts)
    pv_clamped = min(max(pnl_vol, 0.0), 30.0)
    pv_score = 2.0 * (pv_clamped / 30.0)
    score += pv_score
    breakdown["capital_efficiency"] = round(pv_score, 2)

    # Build the display labels from the spec, once per call. The Sizing Fit
    # label is the only one that varies per target (it embeds the profile),
    # so it is built here rather than as a module-level constant.
    breakdown_labels = {}
    radar_labels = {}
    breakdown_points = {}
    for i, param in enumerate(SCORING_SPEC["parameters"], start=1):
        pts = param["points"]
        # Map parameter name to the stable breakdown key.
        if param["name"] == "Sizing Fit":
            bid = "sizing_fit"
            blbl = f"{i}. Sizing Fit (${sizing_peak:.0f} Peak) ({pts}%)"
        elif param["name"] == "Hedged Control":
            bid = "hedged_control"
            blbl = f"{i}. Hedged Control < {HEDGED_RATE_GATE_PCT:.0f}% ({pts}%)"
        else:
            bid = {
                "Edge-to-Friction Ratio": "edge_to_friction",
                "Slippage Cost Rate": "slippage_cost_rate",
                "Drawdown Depth": "drawdown_depth",
                "Copyable Window Share": "window_share",
                "Recent Form": "recent_form",
                "Daily Green Rate": "daily_green_rate",
                "Profit/Loss Ratio": "pl_ratio",
                "Markets Sample": "markets_sample",
                "Capital Efficiency": "capital_efficiency",
            }[param["name"]]
            blbl = f"{i}. {param['name']} ({pts}%)"
        breakdown_labels[bid] = blbl
        radar_labels[bid] = param["radar"] + f" ({pts}%)"
        breakdown_points[bid] = pts

    final_score = round(score, 2)

    if len(rejection_reasons) > 0:
        grade = f"REJECT ({rejection_reasons[0]})"
    else:
        grade = grade_for_score(final_score)

    # Bankroll Sizing Controls & Caps, all stated by the Copy Execution Profile
    max_single_position_usd = profile.max_single_position_usd
    actual_copy_trade = profile.copy_trade_usd
    participation_rate = round((actual_copy_trade / avg_inv) * 100.0, 2) if avg_inv > 0 else 0.0

    # Smallest target order whose mirrored share still clears the venue minimum
    min_target_order_for_1usd = profile.min_target_order_floor_usd(avg_inv)

    return {
        "final_score": final_score,
        "grade": grade,
        "rejection_reasons": rejection_reasons,
        "breakdown": breakdown,
        "breakdown_labels": breakdown_labels,
        "radar_labels": radar_labels,
        "breakdown_points": breakdown_points,
        "bankroll_analysis": {
            "available_capital": profile.bankroll_usd,
            "target_avg_invest_usd": avg_inv,
            "user_copy_trade_usd": actual_copy_trade,
            "max_single_position_cap_usd": max_single_position_usd,
            "capital_participation_rate": f"{participation_rate}%",
            "slippage_cost_rate": f"{slip_cost_rate*100:.2f}%",
            "min_target_order_floor_usd": min_target_order_for_1usd
        }
    }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r") as f:
            data = json.load(f)
        print(json.dumps(calculate_bankroll_optimized_score(data), indent=2))

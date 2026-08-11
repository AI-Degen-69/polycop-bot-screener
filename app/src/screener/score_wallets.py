#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# Toxic Copy Poison: a modelled copy that loses money is not a target. The
# name uses CONTEXT.md's term "Modelled Copy PnL" — never "backtest copy PnL"
# (the glossary lists it under _Avoid_).
MODELLED_COPY_PNL_MIN_USD = 0.0

# Slippage Cost Rate gate, in modelled terms. The real-friction equivalent is
# FRICTION_REALISM_MULTIPLIER times this (ADR 0001); the docs render that
# product, so the number is not repeated here and cannot drift.
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

# Track Record Length gate: fewer markets and the record is a streak, not a
# track record. Measured in lifetime markets — the only lifetime record-depth
# field the leaderboard provides. The research's ~50-position bar (issue #29)
# translates to ~23 markets at the observed ~2.2 trades-per-market density;
# the floor of 25 rounds that up conservatively. The daily activity series is
# a rolling window that cannot measure lifetime trades, so the lifetime field
# is the honest measurement (issue #30 re-scope).
TRACK_RECORD_LENGTH_MIN_MARKETS = 25

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

# Ramp anchors for the remaining continuous parameters. Each is the single
# source referenced by both the SCORING_SPEC row (scored value) and the row's
# generated display text, so a recalibration cannot split the two.

# Slippage Cost Rate full marks: at or below 1% modelled the parameter is
# clean; between here and the gate it falls linearly. A fraction, not a
# percentage-points number, matching the rate it anchors — the display text
# scales it by 100.
SLIPPAGE_FULL_MARKS = 0.01

# Daily Green Rate ramp: nothing at or below 40%, full marks at 85%.
GREEN_RATE_ZERO_PCT = 40.0
GREEN_RATE_FULL_PCT = 85.0

# Profit/Loss Ratio ramp: nothing at or below the gate, full marks at 3x.
PL_RATIO_FULL = 3.0

# Markets Sample ramp: nothing below the track-record floor, full marks at 200.
MARKETS_FULL_MARKS = 200.0

# Capital Efficiency ramp: linear to full marks at a 30 PnL/volume ratio.
CAPITAL_EFFICIENCY_FULL_RATIO = 30.0

# Copyability Score tier bands, calibrated against the distribution of a real
# scored run over the cached leaderboard data. Originally ADR 0005; re-measured
# and scaled after the #23 reweight shifted the distribution (ADR 0010) to stop
# an S-Tier's share of survivors tripling under floors that no longer matched
# the engine. Absolute, not percentile: a scan full of weak wallets must not
# manufacture an S-Tier. These bands grade the triage score only; verdicts
# come from simulation.
TIER_S_MIN = 80.0
TIER_A_MIN = 71.0
TIER_B_MIN = 65.0
TIER_C_MIN = 56.0

# A Hidden Gem is a wallet the screen grades highly while the leaderboard's own
# score rates it poorly. Tied to the recalibrated A-Tier floor (ADR 0005, re-measured in
# ADR 0010).
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
            "condition": f"Modelled Copy PnL < ${MODELLED_COPY_PNL_MIN_USD:.0f}",
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
            "name": "Track Record Length",
            "condition": f"< {TRACK_RECORD_LENGTH_MIN_MARKETS:.0f} lifetime markets",
            "reason": "a short record is a streak, not a track record; measured in lifetime markets because the daily activity series is a rolling window that cannot measure lifetime trades",
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
        # The rows are executable: `key` is the stable breakdown id, `shape`
        # names a curve function in _SHAPE_FNS, and the anchors are the numbers
        # the shape scores against. The zero/full display text is generated
        # from the same anchors where a one-line rendering exists, so a
        # recalibration moves the scored value and the docs together.
        {
            "name": "Edge-to-Friction Ratio",
            "key": "edge_to_friction",
            "points": 24,
            "shape": "ramp_linear",
            "metric": "edge_to_friction",
            "zero_at": EDGE_TO_FRICTION_BREAK_EVEN,
            "full_at": EDGE_TO_FRICTION_FULL_MARKS,
            "zero": f"<= {EDGE_TO_FRICTION_BREAK_EVEN:.1f} (break-even)",
            "full": f">= {EDGE_TO_FRICTION_FULL_MARKS:.1f}",
            "note": "edge per dollar of friction; the cheapest disqualifying arithmetic runs first",
            "radar": "Edge/Friction",
        },
        {
            "name": "Slippage Cost Rate",
            "key": "slippage_cost_rate",
            "points": 17,
            "shape": "ramp_linear_down",
            "metric": "slip_cost_rate",
            "full_below": SLIPPAGE_FULL_MARKS,
            "zero_at": SLIPPAGE_COST_RATE_GATE,
            "zero": f">= {SLIPPAGE_COST_RATE_GATE * 100:.1f}%",
            "full": f"<= {SLIPPAGE_FULL_MARKS * 100:.1f}%",
            "note": "modelled, before the Friction Realism Multiplier",
            "radar": "Slippage Cost",
        },
        {
            "name": "Drawdown Depth",
            "key": "drawdown_depth",
            "points": 13,
            "shape": "decay_from_peak",
            "metric": "drawdown_depth",
            "zero_at": DRAWDOWN_DEPTH_ZERO_AT,
            "zero": f">= {DRAWDOWN_DEPTH_ZERO_AT:.2f} of peak",
            "full": "0.0",
            "note": "from the lifetime equity curve",
            "radar": "Drawdown",
        },
        {
            "name": "Recent Form",
            "key": "recent_form",
            "points": 11,
            "shape": "recent_form",
            "slip_ceiling": RECENT_FORM_SLIP_CEILING_PCT,
            "window_trades": RECENT_FORM_WINDOW_TRADES,
            "full_marks_return": RECENT_FORM_FULL_MARKS_RETURN,
            "zero": "PnL <= $0 or slip unmeasured",
            "full": f">= {RECENT_FORM_FULL_MARKS_RETURN * 100:.0f}% return over the recent-{RECENT_FORM_WINDOW_TRADES:.0f} window at 0% slip",
            "note": "return on deployed capital, judged against the friction it came through (ADR 0004)",
            "radar": "Recent Form",
        },
        {
            "name": "Daily Green Rate",
            "key": "daily_green_rate",
            "points": 9,
            "shape": "ramp_linear",
            "metric": "days_win_rate",
            "zero_at": GREEN_RATE_ZERO_PCT,
            "full_at": GREEN_RATE_FULL_PCT,
            "min_observed_days": MIN_OBSERVED_DAYS,
            "zero": f"<= {GREEN_RATE_ZERO_PCT:.0f}% or fewer than {MIN_OBSERVED_DAYS:.0f} observed days",
            "full": f">= {GREEN_RATE_FULL_PCT:.0f}%",
            "note": "copy-adjusted, measured from real per-day simulated results",
            "radar": "Green Rate",
        },
        {
            "name": "Profit/Loss Ratio",
            "key": "pl_ratio",
            "points": 9,
            "shape": "ramp_linear",
            "metric": "pl_ratio",
            "zero_at": PL_RATIO_GATE,
            "full_at": PL_RATIO_FULL,
            "zero": f"<= {PL_RATIO_GATE:.1f}",
            "full": f">= {PL_RATIO_FULL:.1f}",
            "note": "",
            "radar": "P/L Ratio",
        },
        {
            "name": "Sizing Fit",
            "key": "sizing_fit",
            "points": 6,
            "shape": "triangle",
            "metric": "avg_invest",
            "zero": "outside the Copyable Trade Window",
            "full": "at the window midpoint",
            "note": "peak derived from the Copy Execution Profile, never hand-picked",
            "radar": "Sizing Fit",
        },
        {
            "name": "Hedged Control",
            "key": "hedged_control",
            "points": 6,
            "shape": "decay_from_peak",
            "metric": "hedged_pct",
            "zero_at": HEDGED_RATE_GATE_PCT,
            "zero": f">= {HEDGED_RATE_GATE_PCT:.1f}%",
            "full": "0%",
            "note": "",
            "radar": "Hedged",
        },
        {
            "name": "Markets Sample",
            "key": "markets_sample",
            "points": 3,
            "shape": "ramp_linear",
            "metric": "markets",
            "zero_at": TRACK_RECORD_LENGTH_MIN_MARKETS,
            "full_at": MARKETS_FULL_MARKS,
            "zero": f"<= {TRACK_RECORD_LENGTH_MIN_MARKETS:.0f}",
            "full": f">= {MARKETS_FULL_MARKS:.0f}",
            "note": "",
            "radar": "Markets",
        },
        {
            "name": "Capital Efficiency",
            "key": "capital_efficiency",
            "points": 2,
            "shape": "clamp_ramp",
            "metric": "pnl_vol_ratio",
            "full_at": CAPITAL_EFFICIENCY_FULL_RATIO,
            "zero": "0",
            "full": f">= {CAPITAL_EFFICIENCY_FULL_RATIO:.0f} PnL/volume ratio",
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


# ---------------------------------------------------------------------------
# Parameter shapes: the small registry of curve functions the engine evaluates
# SCORING_SPEC's parameters through. Each shape is a pure function
# (row, ctx) -> points: the row carries its weight and anchors, the shape only
# knows how to walk the curve. Generic shapes pull their metric from ctx by the
# row's `metric` key; composite shapes (recent_form) read what they need
# directly. A new parameter is a row; a new curve is a shape.
# ---------------------------------------------------------------------------

def _row_value(row, ctx):
    """The metric a row scores, or None when it must score nothing.

    Absent-stays-absent (ADR 0007): a metric that was never measured scores
    nothing, never zero points by default. A row with a min_observed_days
    precondition treats a streak of too few days the same way — a rate drawn
    from a streak is not a rate.
    """
    value = ctx.get(row["metric"])
    if value is None:
        return None
    if "min_observed_days" in row:
        if int(ctx.get("observed_days") or 0) < row["min_observed_days"]:
            return None
    return value


def _shape_ramp_linear(row, ctx):
    """Nothing at or below zero_at, full marks at or above full_at, linear rise."""
    value = _row_value(row, ctx)
    if value is None or value <= row["zero_at"]:
        return 0.0
    if value >= row["full_at"]:
        return row["points"]
    span = row["full_at"] - row["zero_at"]
    return row["points"] * ((value - row["zero_at"]) / span)


def _shape_ramp_linear_down(row, ctx):
    """Full marks at or below full_below, nothing at or above zero_at, linear fall."""
    value = _row_value(row, ctx)
    if value is None:
        return 0.0
    if value <= row["full_below"]:
        return row["points"]
    if value >= row["zero_at"]:
        return 0.0
    span = row["zero_at"] - row["full_below"]
    return row["points"] * (1.0 - ((value - row["full_below"]) / span))


def _shape_decay_from_peak(row, ctx):
    """Full marks at zero, nothing at or beyond zero_at, linear falloff."""
    value = _row_value(row, ctx)
    if value is None:
        return 0.0
    return row["points"] * max(0.0, 1.0 - min(1.0, value / row["zero_at"]))


def _shape_clamp_ramp(row, ctx):
    """Linear rise to full marks at full_at, clamped flat beyond it and below zero."""
    value = _row_value(row, ctx)
    if value is None:
        return 0.0
    clamped = min(max(value, 0.0), row["full_at"])
    return row["points"] * (clamped / row["full_at"])


def _shape_triangle(row, ctx):
    """Nothing outside the Copyable Trade Window, full marks at the profile's
    sizing peak, linear on both sides of the peak."""
    value = _row_value(row, ctx)
    low = ctx["profile"].window_min_usd
    high = ctx["profile"].window_max_usd
    peak = ctx["profile"].sizing_fit_peak_usd
    if value is None or value <= low or value >= high:
        return 0.0
    if value <= peak:
        return row["points"] * ((value - low) / (peak - low))
    return row["points"] * ((high - value) / (high - peak))


def _shape_recent_form(row, ctx):
    """Recent profit judged against the friction it came through (ADR 0004):
    the product of a slip factor and a return-on-deployed-capital factor.
    Nothing when the run is flat, the slip is unmeasured, or the target size
    is unknown — all three read as 'no edge to measure'."""
    r20_pnl = ctx.get("r20_pnl") or 0.0
    r20_slip = ctx.get("r20_slip")
    avg_inv = ctx.get("avg_invest") or 0.0
    if r20_pnl <= 0 or r20_slip is None or avg_inv <= 0:
        return 0.0
    slip_ceiling = row["slip_ceiling"]
    slip_factor = 1.0 - (min(max(r20_slip, 0.0), slip_ceiling) / slip_ceiling)
    recent_return = r20_pnl / (row["window_trades"] * avg_inv)
    return_factor = min(recent_return / row["full_marks_return"], 1.0)
    return row["points"] * slip_factor * return_factor


_SHAPE_FNS = {
    "ramp_linear": _shape_ramp_linear,
    "ramp_linear_down": _shape_ramp_linear_down,
    "decay_from_peak": _shape_decay_from_peak,
    "clamp_ramp": _shape_clamp_ramp,
    "triangle": _shape_triangle,
    "recent_form": _shape_recent_form,
}


def _score_parameter(row, ctx):
    """Score one SCORING_SPEC parameter row: points from its shape and anchors."""
    return _SHAPE_FNS[row["shape"]](row, ctx)


def _hard_rejection_gates_doc() -> str:
    """The numbered gate list, generated from SCORING_SPEC so the engine's
    docstring can never disagree with the constants (issue #27)."""
    return "\n".join(
        f"{i}. {gate['name']} ({gate['condition']}) -> {gate['reason']}."
        for i, gate in enumerate(SCORING_SPEC["gates"], start=1)
    )


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
    Reallocated 10 continuous parameters (Total 100 pts). Each parameter's weight,
    shape and anchors live in SCORING_SPEC; the engine only walks the declared
    curve, so a reweight is a one-row edit and the generated docs move with it.

    Copyable Window Share is deliberately absent: it is simulation-only (ADR 0006),
    because no leaderboard field can proxy a distributional share of entry signals.
    Its former ten points were redistributed proportionally across the parameters
    triage can actually measure.

    HARD REJECTION GATES: the numbered list is generated into this docstring
    from SCORING_SPEC at import (see the appended section), so a threshold can
    never drift here — `tools/scoring_docs.py` renders the same spec into the
    docs.
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
    # These three are measured rather than read off the leaderboard, and any of
    # them can be unavailable. None means unmeasured and scores nothing: a
    # default would hand out points the wallet never earned, which is exactly
    # how a previous version of this engine gave every candidate a free 44.
    drawdown_depth = _measured(metrics.get("drawdown_depth"))
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
    if copy_pnl < MODELLED_COPY_PNL_MIN_USD:
        rejection_reasons.append("Modelled Copy PnL < $0 (Toxic Copy Poison)")
    if slip_cost_rate > SLIPPAGE_COST_RATE_GATE:
        rejection_reasons.append(f"Slippage Cost Rate {slip_cost_rate*100:.1f}% > {SLIPPAGE_COST_RATE_GATE*100:.1f}% modelled limit")
    if hedged > HEDGED_RATE_GATE_PCT:
        rejection_reasons.append(f"Hedged Rate {hedged}% > {HEDGED_RATE_GATE_PCT}%")
    if pl_ratio < PL_RATIO_GATE:
        rejection_reasons.append(f"P/L Ratio {pl_ratio:.2f}x < {PL_RATIO_GATE:.1f}x")
    if mkts < TRACK_RECORD_LENGTH_MIN_MARKETS:
        rejection_reasons.append(f"Track Record Length ({int(mkts)} lifetime markets < {TRACK_RECORD_LENGTH_MIN_MARKETS:.0f})")
    if avg_inv > WHALE_AVG_INVEST_LIMIT_USD:
        rejection_reasons.append(f"Whale Avg Invest (${avg_inv:.2f} > ${WHALE_AVG_INVEST_LIMIT_USD:.0f})")
    if r20_pnl < 0 and actual_pnl > DIVERGENCE_LIFETIME_PNL_USD:
        rejection_reasons.append(f"Divergence Gate: Negative Recent Form (${r20_pnl:.2f}) vs strongly positive lifetime PnL (${actual_pnl:.2f})")

    # --- 10 REWEIGHTED CONTINUOUS PARAMETERS (TOTAL 100 PTS) ---
    # Evaluated from SCORING_SPEC: each row declares its weight, shape and
    # anchors, and a small registry of pure curve functions scores it. A
    # reweight is a one-row edit; the docs regenerate from the same table.
    param_ctx = {
        "profile": profile,
        "edge_to_friction": edge_to_friction,
        "slip_cost_rate": slip_cost_rate,
        "drawdown_depth": drawdown_depth,
        "r20_pnl": r20_pnl,
        "r20_slip": r20_slip,
        "avg_invest": avg_inv,
        "days_win_rate": daily_green_rate,
        "observed_days": observed_days,
        "pl_ratio": pl_ratio,
        "hedged_pct": hedged,
        "markets": mkts,
        "pnl_vol_ratio": pnl_vol,
    }
    for row in SCORING_SPEC["parameters"]:
        pts = _score_parameter(row, param_ctx)
        score += pts
        breakdown[row["key"]] = round(pts, 2)

    # Build the display labels from the spec, once per call. The Sizing Fit
    # label is the only one that varies per target (it embeds the profile), so
    # it is built here rather than in the spec.
    sizing_peak = profile.sizing_fit_peak_usd
    breakdown_labels = {}
    radar_labels = {}
    breakdown_points = {}
    for i, param in enumerate(SCORING_SPEC["parameters"], start=1):
        pts = param["points"]
        if param["key"] == "sizing_fit":
            blbl = f"{i}. Sizing Fit (${sizing_peak:.0f} Peak) ({pts}%)"
        elif param["key"] == "hedged_control":
            blbl = f"{i}. Hedged Control < {HEDGED_RATE_GATE_PCT:.0f}% ({pts}%)"
        else:
            blbl = f"{i}. {param['name']} ({pts}%)"
        breakdown_labels[param["key"]] = blbl
        radar_labels[param["key"]] = param["radar"] + f" ({pts}%)"
        breakdown_points[param["key"]] = pts

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


# The gate list in the docstring above is generated from SCORING_SPEC at
# import, so a gate change updates help() automatically and the docstring can
# never disagree with the constants (issue #27).
calculate_bankroll_optimized_score.__doc__ = (
    (calculate_bankroll_optimized_score.__doc__ or "")
    + "\n\nHARD REJECTION GATES (generated from SCORING_SPEC):\n"
    + _hard_rejection_gates_doc()
)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r") as f:
            data = json.load(f)
        print(json.dumps(calculate_bankroll_optimized_score(data), indent=2))

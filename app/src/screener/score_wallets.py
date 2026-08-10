#!/usr/bin/env python3
import json
import os
import sys

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from execution.copy_execution_profile import CURRENT_PROFILE

# Whale gate: a target whose typical trade dwarfs the bankroll cannot be mirrored at
# any sane participation rate. A screening gate rather than a bot setting, so it is
# not part of the Copy Execution Profile.
WHALE_AVG_INVEST_LIMIT_USD = 200.0

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

    HARD REJECTION GATES:
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
    days_wr = float(metrics.get("days_win_rate", 0.0))
    r20_wr = float(metrics.get("r20_win_rate", 0.0))
    r20_pnl = float(metrics.get("r20_pnl", 0.0))
    r20_slip = float(metrics.get("r20_slip", 100.0))
    pnl_vol = float(metrics.get("pnl_vol_ratio", 0.0))
    mkts = float(metrics.get("markets", 0))
    avg_inv = float(metrics.get("avg_invest", 0.0))
    polycop_site_score = float(metrics.get("polycop_site_score", 0.0))
    drawdown_depth = float(metrics.get("drawdown_depth", metrics.get("max_drawdown", 0.0)))
    window_share = float(metrics.get("copyable_window_share", 1.0))
    edge_to_friction = float(metrics.get("edge_to_friction", 1.0))

    if abs(actual_pnl) > 0:
        slip_cost_rate = max(0.0, (actual_pnl - copy_pnl) / abs(actual_pnl))
    else:
        slip_cost_rate = 0.0

    # --- HARD REJECTION GATES ---
    if polycop_site_score < 40.0:
        rejection_reasons.append(f"PolyCop Site Score {polycop_site_score:.0f} < 40/100 sanity floor")
    if copy_pnl < 0:
        rejection_reasons.append("Backtest Copy PnL < $0 (Toxic Copy Poison)")
    if slip_cost_rate > 0.05:
        rejection_reasons.append(f"Slippage Cost Rate {slip_cost_rate*100:.1f}% > 5.0% modelled limit")
    if hedged > 3.0:
        rejection_reasons.append(f"Hedged Rate {hedged}% > 3.0%")
    if pl_ratio < 0.3:
        rejection_reasons.append(f"P/L Ratio {pl_ratio:.2f}x < 0.3x")
    if mkts < 20:
        rejection_reasons.append(f"Short Track Record ({int(mkts)} markets < 20 min threshold)")
    if avg_inv > WHALE_AVG_INVEST_LIMIT_USD:
        rejection_reasons.append(f"Whale Avg Invest (${avg_inv:.2f} > ${WHALE_AVG_INVEST_LIMIT_USD:.0f})")
    if r20_pnl < 0 and actual_pnl > 1000.0:
        rejection_reasons.append(f"Divergence Gate: Negative Recent Form (${r20_pnl:.2f}) vs strongly positive lifetime PnL (${actual_pnl:.2f})")

    # --- 11 REWEIGHTED CONTINUOUS PARAMETERS (TOTAL 100 PTS) ---

    # 1. Edge-to-Friction Ratio (22 pts)
    etf_score = min(22.0, max(0.0, edge_to_friction * 22.0))
    score += etf_score
    breakdown["1. Edge-to-Friction Ratio (22%)"] = round(etf_score, 2)

    # 2. Slippage Cost Rate (15 pts)
    if slip_cost_rate <= 0.01:
        slip_score = 15.0
    elif slip_cost_rate >= 0.05:
        slip_score = 0.0
    else:
        slip_score = 15.0 * (1.0 - ((slip_cost_rate - 0.01) / (0.05 - 0.01)))
    score += slip_score
    breakdown["2. Slippage Cost Rate (15%)"] = round(slip_score, 2)

    # 3. Drawdown Depth (12 pts)
    dd_score = max(0.0, 12.0 * (1.0 - min(1.0, drawdown_depth / 0.50)))
    score += dd_score
    breakdown["3. Drawdown Depth (12%)"] = round(dd_score, 2)

    # 4. Copyable Window Share (10 pts)
    cws_score = min(10.0, max(0.0, window_share * 10.0))
    score += cws_score
    breakdown["4. Copyable Window Share (10%)"] = round(cws_score, 2)

    # 5. Recent Form (10 pts)
    rf_score = min(10.0, max(0.0, (r20_pnl / 1000.0) * 10.0))
    score += rf_score
    breakdown["5. Recent Form (10%)"] = round(rf_score, 2)

    # 6. Daily Green Rate (8 pts) - Requires min 10 observed days
    if days_wr <= 40.0 or metrics.get("trading_days", 10) < 10:
        days_score = 0.0
    elif days_wr >= 85.0:
        days_score = 8.0
    else:
        days_score = 8.0 * ((days_wr - 40.0) / (85.0 - 40.0))
    score += days_score
    breakdown["6. Daily Green Rate (8%)"] = round(days_score, 2)

    # 7. Profit/Loss Ratio (8 pts)
    if pl_ratio <= 0.3:
        pl_score = 0.0
    elif pl_ratio >= 3.0:
        pl_score = 8.0
    else:
        pl_score = 8.0 * ((pl_ratio - 0.3) / (3.0 - 0.3))
    score += pl_score
    breakdown["7. Profit/Loss Ratio (8%)"] = round(pl_score, 2)

    # 8. Sizing Fit (5 pts)
    sizing_peak = profile.sizing_fit_peak_usd
    if avg_inv <= sizing_peak:
        inv_score = 5.0 * max(0.0, avg_inv / sizing_peak)
    elif sizing_peak >= WHALE_AVG_INVEST_LIMIT_USD:
        inv_score = 0.0
    else:
        inv_score = max(0.0, 5.0 * (1.0 - ((avg_inv - sizing_peak) / (WHALE_AVG_INVEST_LIMIT_USD - sizing_peak))))
    score += inv_score
    breakdown[f"8. Sizing Fit (${sizing_peak:.0f} Peak) (5%)"] = round(inv_score, 2)

    # 9. Hedged Control (5 pts)
    if hedged > 3.0:
        hedged_score = 0.0
    else:
        hedged_score = 5.0 * (1.0 - (hedged / 3.0))
    score += hedged_score
    breakdown["9. Hedged Control < 3% (5%)"] = round(hedged_score, 2)

    # 10. Markets Sample (3 pts)
    if mkts < 20:
        mkt_score = 0.0
    elif mkts >= 200:
        mkt_score = 3.0
    else:
        mkt_score = 3.0 * ((mkts - 20.0) / (200.0 - 20.0))
    score += mkt_score
    breakdown["10. Markets Sample (3%)"] = round(mkt_score, 2)

    # 11. Capital Efficiency (2 pts)
    pv_clamped = min(max(pnl_vol, 0.0), 30.0)
    pv_score = 2.0 * (pv_clamped / 30.0)
    score += pv_score
    breakdown["11. Capital Efficiency (2%)"] = round(pv_score, 2)

    final_score = round(score, 2)

    
    if len(rejection_reasons) > 0:
        grade = f"REJECT ({rejection_reasons[0]})"
    elif final_score >= 90.0:
        grade = "S-Tier (God-Tier Target)"
    elif final_score >= 80.0:
        grade = "A-Tier (Strong Copy Target)"
    elif final_score >= 70.0:
        grade = "B-Tier (Moderate Copy Target)"
    elif final_score >= 50.0:
        grade = "C-Tier (High Risk / Volatile)"
    else:
        grade = "F-Tier (Toxic / Rejection)"

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

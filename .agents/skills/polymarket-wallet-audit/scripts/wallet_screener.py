#!/usr/bin/env python3
import json
import sys

def calculate_bankroll_optimized_score(metrics, user_capital=100.0):
    """
    PolyCop $100 Bankroll Continuous Linear Screener Engine.
    Incorporates PolyCop AI Analysis Rules, $100 Capital Sizing, $5.00 Max Position Cap, and Losing Streak Protection.
    
    HARD REJECTION GATES (INSTANT DISQUALIFICATION):
    1. Backtest Copy PnL < $0 -> Toxic Copy Poison.
    2. Slippage Cost Rate > 100% (> 1.0) -> Pure Arb / Market Maker Bot.
    3. Hedged Rate > 3.0% -> Ratio Distortion / Arb Risk.
    4. P/L Ratio < 0.3 -> Liquidation Risk (Winning Pennies, Losing Dollars).
    5. Markets Sample < 20 -> Short Track Record Risk.
    6. Avg Invest > $300.00 USD -> Whale Trade Sizing Friction.
    7. Recent 20 Win Rate < 45.0% -> Severe Losing Streak / Longshot Hunter Risk.
    """
    score = 0.0
    breakdown = {}
    rejection_reasons = []

    actual_pnl = float(metrics.get("actual_pnl", metrics.get("copy_pnl", 0.0)))
    copy_pnl = float(metrics.get("copy_pnl", -1.0))
    slippage = float(metrics.get("slippage", 100.0))
    hedged = float(metrics.get("hedged_pct", 100.0))
    pl_ratio = float(metrics.get("pl_ratio", 0.0))
    days_wr = float(metrics.get("days_win_rate", 0.0))
    r20_wr = float(metrics.get("r20_win_rate", 0.0))
    r20_pnl = float(metrics.get("r20_pnl", 0.0))
    r20_slip = float(metrics.get("r20_slip", 100.0))
    pnl_vol = float(metrics.get("pnl_vol_ratio", 0.0))
    mkts = float(metrics.get("markets", 0))
    avg_inv = float(metrics.get("avg_invest", 0.0))

    # Exact Slippage Cost Rate calculation: (Actual PnL - Copy PnL) / |Actual PnL|
    if abs(actual_pnl) > 0:
        slip_cost_rate = max(0.0, (actual_pnl - copy_pnl) / abs(actual_pnl))
    else:
        slip_cost_rate = 0.0

    # --- HARD REJECTION GATES ---
    polycop_site_score = float(metrics.get("polycop_site_score", 0.0))
    if polycop_site_score <= 60.0:
        rejection_reasons.append(f"PolyCop Site Score {polycop_site_score:.0f} <= 60/100 threshold")
    if copy_pnl < 0:
        rejection_reasons.append("Backtest Copy PnL < $0 (Toxic Copy Poison)")
    if slip_cost_rate > 0.20:
        rejection_reasons.append(f"Slippage Cost Rate {slip_cost_rate*100:.1f}% > 20.0% max limit (Excessive friction)")
    if hedged > 3.0:
        rejection_reasons.append(f"Hedged Rate {hedged}% > 3.0% ($100 Bankroll ratio distortion / arb risk)")
    if pl_ratio < 0.3:
        rejection_reasons.append(f"P/L Ratio {pl_ratio:.2f}x < 0.3x (Liquidation Risk - Winning Pennies, Losing Dollars)")
    if mkts < 20:
        rejection_reasons.append(f"Short Track Record ({int(mkts)} markets < 20 min threshold)")
    if avg_inv > 300.0:
        rejection_reasons.append(f"Whale Avg Invest (${avg_inv:.2f} > $300) - Severe $100 bankroll scaling friction")
    if r20_wr < 45.0:
        rejection_reasons.append(f"Recent Win Rate {r20_wr:.1f}% < 45% (High Losing Streak / Drawdown Risk)")
    if mkts > 300 and slip_cost_rate > 0.05:
        rejection_reasons.append(f"High Frequency Friction Sensitivity ({int(mkts)} markets & {slip_cost_rate*100:.1f}% slip rate > 5.0% - High-frequency bot liquidation risk)")

    # --- 9 WEIGHTED CONTINUOUS PARAMETERS ---
    
    # 1. Slippage Cost Rate Score (20.00 Pts) - Best < 10% (20 pts), degrades to 0 at 60%
    if slip_cost_rate <= 0.10:
        slip_score = 20.0
    elif slip_cost_rate >= 0.60:
        slip_score = 0.0
    else:
        slip_score = 20.0 * (1.0 - ((slip_cost_rate - 0.10) / (0.60 - 0.10)))
    score += slip_score
    breakdown["1. Slippage Cost Rate (20%)"] = round(slip_score, 2)

    # 2. Recent 20 PnL & Slip (15.00 Pts)
    if r20_pnl <= 0:
        r20_score = 0.0
    else:
        slip_factor = 1.0 - (min(max(r20_slip, 0.0), 15.0) / 15.0)
        pnl_factor = min(r20_pnl / 1000.0, 1.0)
        r20_score = 15.0 * slip_factor * pnl_factor
    score += r20_score
    breakdown["2. Recent 20 PnL & Slip (15%)"] = round(r20_score, 2)

    # 3. Hedged Control (15.00 Pts)
    if hedged > 3.0:
        hedged_score = 0.0
    else:
        hedged_score = 15.0 * (1.0 - (hedged / 3.0))
    score += hedged_score
    breakdown["3. Hedged Control < 3% (15%)"] = round(hedged_score, 2)

    # 4. Daily Green Rate (15.00 Pts) - Continuous slope 40%..85%
    if days_wr <= 40.0:
        days_score = 0.0
    elif days_wr >= 85.0:
        days_score = 15.0
    else:
        days_score = 15.0 * ((days_wr - 40.0) / (85.0 - 40.0))
    score += days_score
    breakdown["4. Daily Green Rate (15%)"] = round(days_score, 2)

    # 5. Recent 20 Win Rate (10.00 Pts) - Continuous slope 45%..75%
    if r20_wr <= 45.0:
        r20_wr_score = 0.0
    elif r20_wr >= 75.0:
        r20_wr_score = 10.0
    else:
        r20_wr_score = 10.0 * ((r20_wr - 45.0) / (75.0 - 45.0))
    score += r20_wr_score
    breakdown["5. Recent 20 Win Rate (10%)"] = round(r20_wr_score, 2)

    # 6. Avg Profit/Loss Ratio (10.00 Pts) - Continuous slope 0.3..3.0
    if pl_ratio <= 0.3:
        pl_score = 0.0
    elif pl_ratio >= 3.0:
        pl_score = 10.0
    else:
        pl_score = 10.0 * ((pl_ratio - 0.3) / (3.0 - 0.3))
    score += pl_score
    breakdown["6. Profit/Loss Ratio (10%)"] = round(pl_score, 2)

    # 7. Capital Efficiency (5.00 Pts) - Continuous slope 0%..30%
    pv_clamped = min(max(pnl_vol, 0.0), 30.0)
    pv_score = 5.0 * (pv_clamped / 30.0)
    score += pv_score
    breakdown["7. Capital Efficiency (5%)"] = round(pv_score, 2)

    # 8. Markets Sample Size (5.00 Pts) - Continuous slope 20..200
    if mkts < 20:
        mkt_score = 0.0
    elif mkts >= 200:
        mkt_score = 5.0
    else:
        mkt_score = 5.0 * ((mkts - 20.0) / (200.0 - 20.0))
    score += mkt_score
    breakdown["8. Markets Sample (5%)"] = round(mkt_score, 2)

    # 9. Target Trader Avg Invest Sizing ($25.00 Peak Fit) (5.00 Pts)
    if avg_inv <= 25.0:
        inv_score = 5.0 * max(0.0, avg_inv / 25.0)
    else:
        inv_score = max(0.0, 5.0 * (1.0 - ((avg_inv - 25.0) / (300.0 - 25.0))))
    score += inv_score
    breakdown["9. Continuous Sizing Fit ($25 Peak) (5%)"] = round(inv_score, 2)

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

    # Bankroll Sizing Controls & Caps
    uncapped_copy_trade = user_capital * 0.03  # 3% scale = $3.00 USD
    max_single_position_usd = round(min(user_capital * 0.05, 5.00), 2)  # Hard $5.00 cap (5% of bankroll)
    actual_copy_trade = min(uncapped_copy_trade, max_single_position_usd)
    participation_rate = round((actual_copy_trade / avg_inv) * 100.0, 2) if avg_inv > 0 else 0.0

    # Polymarket $1.00 Minimum Order Limit Floor Calculation
    min_target_order_for_1usd = round(1.00 / (actual_copy_trade / avg_inv), 2) if avg_inv > 0 and actual_copy_trade > 0 else 0.0

    return {
        "final_score": final_score,
        "grade": grade,
        "rejection_reasons": rejection_reasons,
        "breakdown": breakdown,
        "bankroll_analysis": {
            "available_capital": user_capital,
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

/**
 * PolyCop $100 Bankroll Continuous Linear Screener Engine (Client-Side JS Mirror)
 */
function calculateBankrollOptimizedScore(metrics, userCapital = 100.0) {
    let score = 0.0;
    const breakdown = {};
    const rejectionReasons = [];

    const actualPnl = parseFloat(metrics.actual_pnl || metrics.copy_pnl || 0.0);
    const copyPnl = parseFloat(metrics.copy_pnl ?? -1.0);
    const hedged = parseFloat(metrics.hedged_pct ?? 100.0);
    const plRatio = parseFloat(metrics.pl_ratio ?? 0.0);
    const daysWr = parseFloat(metrics.days_win_rate ?? 0.0);
    const r20Wr = parseFloat(metrics.r20_win_rate ?? 0.0);
    const r20Pnl = parseFloat(metrics.r20_pnl ?? 0.0);
    const r20Slip = parseFloat(metrics.r20_slip ?? 100.0);
    const pnlVol = parseFloat(metrics.pnl_vol_ratio ?? 0.0);
    const mkts = parseFloat(metrics.markets ?? 0);
    const avgInv = parseFloat(metrics.avg_invest ?? 0.0);
    const polycopSiteScore = parseFloat(metrics.polycop_site_score ?? 0.0);

    const slipCostRate = Math.abs(actualPnl) > 0 
        ? Math.max(0.0, (actualPnl - copyPnl) / Math.abs(actualPnl)) 
        : 0.0;

    // --- HARD REJECTION GATES ---
    if (polycopSiteScore <= 60.0) rejectionReasons.push(`PolyCop Site Score ${polycopSiteScore.toFixed(0)} <= 60/100 threshold`);
    if (copyPnl < 0) rejectionReasons.push("Backtest Copy PnL < $0 (Toxic Copy Poison)");
    if (slipCostRate > 0.20) rejectionReasons.push(`Slippage Cost Rate ${(slipCostRate * 100).toFixed(1)}% > 20.0% max limit`);
    if (hedged > 3.0) rejectionReasons.push(`Hedged Rate ${hedged}% > 3.0% ($100 Bankroll ratio distortion / arb risk)`);
    if (plRatio < 0.3) rejectionReasons.push(`P/L Ratio ${plRatio.toFixed(2)}x < 0.3x (Liquidation Risk)`);
    if (mkts < 20) rejectionReasons.push(`Short Track Record (${Math.round(mkts)} markets < 20 min threshold)`);
    if (avgInv > 300.0) rejectionReasons.push(`Whale Avg Invest ($${avgInv.toFixed(2)} > $300)`);
    if (r20Wr < 45.0) rejectionReasons.push(`Recent Win Rate ${r20Wr.toFixed(1)}% < 45% (High Losing Streak Risk)`);
    if (mkts > 300 && slipCostRate > 0.05) rejectionReasons.push(`High Frequency Friction Sensitivity (${Math.round(mkts)} markets & ${(slipCostRate * 100).toFixed(1)}% slip rate > 5.0%)`);

    // 1. Slippage Cost Rate Score (20 Pts)
    let slipScore = 0.0;
    if (slipCostRate <= 0.10) slipScore = 20.0;
    else if (slipCostRate >= 0.60) slipScore = 0.0;
    else slipScore = 20.0 * (1.0 - ((slipCostRate - 0.10) / (0.60 - 0.10)));
    score += slipScore;
    breakdown["1. Slippage Cost Rate (20%)"] = Number(slipScore.toFixed(2));

    // 2. Recent 20 PnL & Slip (15 Pts)
    let r20Score = 0.0;
    if (r20Pnl > 0) {
        const slipFactor = 1.0 - (Math.min(Math.max(r20Slip, 0.0), 15.0) / 15.0);
        const pnlFactor = Math.min(r20Pnl / 1000.0, 1.0);
        r20Score = 15.0 * slipFactor * pnlFactor;
    }
    score += r20Score;
    breakdown["2. Recent 20 PnL & Slip (15%)"] = Number(r20Score.toFixed(2));

    // 3. Hedged Control (15 Pts)
    let hedgedScore = hedged > 3.0 ? 0.0 : 15.0 * (1.0 - (hedged / 3.0));
    score += hedgedScore;
    breakdown["3. Hedged Control < 3% (15%)"] = Number(hedgedScore.toFixed(2));

    // 4. Daily Green Rate (15 Pts)
    let daysScore = 0.0;
    if (daysWr <= 40.0) daysScore = 0.0;
    else if (daysWr >= 85.0) daysScore = 15.0;
    else daysScore = 15.0 * ((daysWr - 40.0) / (85.0 - 40.0));
    score += daysScore;
    breakdown["4. Daily Green Rate (15%)"] = Number(daysScore.toFixed(2));

    // 5. Recent 20 Win Rate (10 Pts)
    let r20WrScore = 0.0;
    if (r20Wr <= 45.0) r20WrScore = 0.0;
    else if (r20Wr >= 75.0) r20WrScore = 10.0;
    else r20WrScore = 10.0 * ((r20Wr - 45.0) / (75.0 - 45.0));
    score += r20WrScore;
    breakdown["5. Recent 20 Win Rate (10%)"] = Number(r20WrScore.toFixed(2));

    // 6. Profit/Loss Ratio (10 Pts)
    let plScore = 0.0;
    if (plRatio <= 0.3) plScore = 0.0;
    else if (plRatio >= 3.0) plScore = 10.0;
    else plScore = 10.0 * ((plRatio - 0.3) / (3.0 - 0.3));
    score += plScore;
    breakdown["6. Profit/Loss Ratio (10%)"] = Number(plScore.toFixed(2));

    // 7. Capital Efficiency (5 Pts)
    const pvClamped = Math.min(Math.max(pnlVol, 0.0), 30.0);
    const pvScore = 5.0 * (pvClamped / 30.0);
    score += pvScore;
    breakdown["7. Capital Efficiency (5%)"] = Number(pvScore.toFixed(2));

    // 8. Markets Sample Size (5 Pts)
    let mktScore = 0.0;
    if (mkts < 20) mktScore = 0.0;
    else if (mkts >= 200) mktScore = 5.0;
    else mktScore = 5.0 * ((mkts - 20.0) / (200.0 - 20.0));
    score += mktScore;
    breakdown["8. Markets Sample (5%)"] = Number(mktScore.toFixed(2));

    // 9. Target Trader Avg Invest Sizing (5 Pts)
    let invScore = 0.0;
    if (avgInv <= 25.0) invScore = 5.0 * Math.max(0.0, avgInv / 25.0);
    else invScore = Math.max(0.0, 5.0 * (1.0 - ((avgInv - 25.0) / (300.0 - 25.0))));
    score += invScore;
    breakdown["9. Continuous Sizing Fit ($25 Peak) (5%)"] = Number(invScore.toFixed(2));

    // 10. High Entry Price Risk Penalty (Avg Buy Price > $0.85)
    const avgBuyPrice = parseFloat(metrics.buy_price ?? metrics.avg_buy_price ?? 0.0);
    if (avgBuyPrice > 0.85) {
        const buyPenalty = Math.min(10.0, 10.0 * ((avgBuyPrice - 0.85) / (0.99 - 0.85)));
        score = Math.max(0.0, score - buyPenalty);
        breakdown["10. High Entry Penalty (> $0.85 Avg Buy)"] = -Number(buyPenalty.toFixed(2));
    }

    const finalScore = Number(score.toFixed(2));

    let grade = "";
    if (rejectionReasons.length > 0) grade = `REJECT (${rejectionReasons[0]})`;
    else if (finalScore >= 90.0) grade = "S-Tier (God-Tier Target)";
    else if (finalScore >= 80.0) grade = "A-Tier (Strong Copy Target)";
    else if (finalScore >= 70.0) grade = "B-Tier (Moderate Copy Target)";
    else if (finalScore >= 50.0) grade = "C-Tier (High Risk / Volatile)";
    else grade = "F-Tier (Toxic / Rejection)";

    const uncappedCopyTrade = userCapital * 0.03;
    const maxSinglePositionUsd = Number(Math.min(userCapital * 0.05, 5.00).toFixed(2));
    const actualCopyTrade = Math.min(uncappedCopyTrade, maxSinglePositionUsd);
    const participationRate = avgInv > 0 ? Number(((actualCopyTrade / avgInv) * 100.0).toFixed(2)) : 0.0;
    const minTargetOrderFor1usd = (avgInv > 0 && actualCopyTrade > 0) 
        ? Number((1.00 / (actualCopyTrade / avgInv)).toFixed(2)) 
        : 0.0;

    return {
        final_score: finalScore,
        grade: grade,
        rejection_reasons: rejectionReasons,
        breakdown: breakdown,
        bankroll_analysis: {
            available_capital: userCapital,
            target_avg_invest_usd: avgInv,
            user_copy_trade_usd: actualCopyTrade,
            max_single_position_cap_usd: maxSinglePositionUsd,
            capital_participation_rate: `${participationRate}%`,
            slippage_cost_rate: `${(slipCostRate * 100).toFixed(2)}%`,
            min_target_order_floor_usd: minTargetOrderFor1usd
        }
    };
}

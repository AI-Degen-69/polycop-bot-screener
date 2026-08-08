---
name: polymarket-wallet-audit
description: Use when evaluating, scoring, ranking, or auditing Polymarket trader wallets for copy-trading viability.
---

# Polymarket Wallet Audit System

## Overview
A weighted 100-point continuous grading engine incorporating PolyCop AI Analysis rules for evaluating Polymarket copy-trading wallets. It scores 9 data parameters to assign an objective letter grade (`S-Tier`, `A-Tier`, `B-Tier`, `C-Tier`, `F-Tier`).

---

## PolyCop AI Tier 1 Hard Rejection Gates (Instant Disqualification)
- **Backtest Copy PnL < $0**: Toxic copy poison (Instant REJECT).
- **Slippage Cost Rate > 100%**: `(Actual PnL - Copy PnL) / |Actual PnL| > 1.0` -> Pure Arb / Market Maker Bot (Instant REJECT).
- **Hedged Rate > 3.0%**: Ratio distortion & hedge order execution failure risk (Instant REJECT for $100 Bankroll).
- **P/L Ratio < 0.3**: Liquidation risk - winning pennies, losing dollars (Instant REJECT).
- **Markets < 20**: Short track record / lucky streak risk (Instant REJECT).
- **Avg Invest > $300 USD**: Whale trade sizing friction for $100 bankrolls (Instant REJECT).
- **Recent 20 Win Rate < 45.0%**: Severe losing streak / high drawdown risk (Instant REJECT).

---

## $100 Bankroll Position Controls & Card Definitions

1. **Backtest Copy PnL**:
   - `Copy PnL = Actual PnL - (Total Volume * 4.0% Slippage Penalty)`
   - Simulated PnL after applying PolyCop's 4.0% round-trip execution friction (2% buy markup + 2% sell markdown).
2. **$5.00 Max Position Cap Rule**:
   - `Max Single Position USD = min(0.05 * Capital, $5.00)`
   - Hard position limit capping single trade exposure to $5.00 USD (5% of a $100 bankroll) to protect capital during high volatility.
3. **Polymarket $1.00 Order Limit Floor Formula**:
   - `Min Target Order Floor USD = $1.00 / Copy Scaling Multiplier`
   - Minimum target trader order size required so your copy trade stays above Polymarket's $1.00 USD minimum execution limit floor (e.g. $29.63 USD at 3.37% scale).

---

## 9 Continuous Weighted Parameters (100% Total)

| Parameter | Weight | Min Range (0.0 Pts) | Max Range (Full Pts) | Max Score |
| :--- | :--- | :--- | :--- | :--- |
| **1. Slippage Cost Rate** | **20%** | `60.0%` Slippage Rate | `10.0%` Slippage Rate | 20.0 Pts |
| **2. Recent 20 PnL & Slip** | **15%** | `$0 PnL & 15% Slip` | `$1,000 PnL & 0% Slip` | 15.0 Pts |
| **3. Hedged Control** | **15%** | `3.0%` Hedged | `0.0%` Hedged | 15.0 Pts |
| **4. Daily Green Rate** | **15%** | `40.0%` Win Rate | `85.0%` Win Rate | 15.0 Pts |
| **5. Recent 20 Win Rate** | **10%** | `45.0%` Win Rate | `75.0%` Win Rate | 10.0 Pts |
| **6. Avg Profit/Loss Ratio** | **10%** | `0.30x` Ratio | `3.00x` Ratio | 10.0 Pts |
| **7. Capital Efficiency** | **5%** | `0.0%` PnL/Vol | `30.0%` PnL/Vol | 5.0 Pts |
| **8. Markets Sample Size** | **5%** | `20` Markets | `200` Markets | 5.0 Pts |
| **9. Continuous Sizing Fit** | **5%** | `$300.00` Avg Invest | `$25.00` Peak Invest | 5.0 Pts |

---

## Letter Grade Scale

- **90 – 100 Pts**: **S-Tier** (God-Tier Target)
- **80 – 89 Pts**: **A-Tier** (Strong Target)
- **70 – 79 Pts**: **B-Tier** (Moderate Copy Target)
- **50 – 69 Pts**: **C-Tier** (High Risk / Volatile)
- **< 50 Pts**: **F-Tier / REJECT** (Toxic / Disqualified)

---

## Automated Script Execution

Run the wallet screener script to calculate the continuous weighted score automatically:
```bash
python .agents/skills/polymarket-wallet-audit/scripts/wallet_screener.py path/to/wallet_data.json
```

# Project AGENTS Rules

### PolyCop & Polymarket Weighted 100-Point Audit Standard
Whenever asked to evaluate, recommend, or analyze a Polymarket copy-trading wallet:

1. **PolyCop AI Tier 1 Hard Rejection Gates (Instant Disqualification)**:
   - **Backtest Copy PnL < $0**: Toxic copy poison (Instant REJECT).
   - **Slippage Cost Rate > 100%**: `(Actual PnL - Copy PnL) / |Actual PnL| > 1.0` -> Pure Arb / Market Maker Bot (Instant REJECT).
   - **Hedged Rate > 3.0%**: Ratio distortion & hedge order execution failure risk (Instant REJECT for $100 Bankroll).
   - **P/L Ratio < 0.3**: Liquidation risk - winning pennies, losing dollars (Instant REJECT).
   - **Markets < 20**: Short track record / lucky streak risk (Instant REJECT).
   - **Avg Invest > $300 USD**: Whale trade sizing friction for $100 bankrolls (Instant REJECT).

2. **Calculate Continuous Weighted 100-Point Score**:
   - **Slippage Cost Rate (20%)**: `(Actual - Copy) / |Actual| < 10%` (20 pts, degrades to 0 at 60%).
   - **Recent 20 PnL & Slip (15%)**: `> $1k & <5% slip` (15 pts), `Recent PnL <= $0` (0 pts).
   - **Hedged Control (15%)**: `< 3.0%` (15 pts), `> 3.0%` (0 pts & REJECT).
   - **Daily Green Rate (15%)**: `> 85% green` (15 pts), continuous slope `40%..85%`.
   - **Recent 20 Win Rate (10%)**: `> 75%` (10 pts), continuous slope `35%..75%`.
   - **Avg Profit/Loss Ratio (10%)**: `> 3.0` (10 pts), `< 0.3` (0 pts & REJECT).
   - **PnL / Volume Ratio (5%)**: `> 30%` (5 pts), continuous slope `0%..30%`.
   - **Markets Sample Size (5%)**: `> 200` (5 pts), `< 20` (0 pts & REJECT).
   - **Continuous Sizing Fit (5%)**: `$25 Peak Optimal` (5 pts), `> $300` (0 pts & REJECT).

3. **Letter Grade Assignment**:
   - **90 – 100 Pts**: **S-Tier** (God-Tier Target)
   - **80 – 89 Pts**: **A-Tier** (Strong Copy Target)
   - **70 – 79 Pts**: **B-Tier** (Moderate / High Volatility)
   - **50 – 69 Pts**: **C-Tier** (High Risk / Drawdown)
   - **< 50 Pts**: **F-Tier / REJECT** (Toxic / Disqualified)

4. **Data Evidence Requirement**: Present the numerical breakdown for all 9 weighted parameters alongside the final grade.

### Response Formatting Rules
1. **No Time Estimates**: Do NOT include minute counts or time duration estimates (e.g., mins count) in responses.
2. **Suggested Follow-ups Ending**: End every response with a `### Suggested Follow-ups` section containing exactly 3 options framed as actions the AI assistant will execute using "I'll..." phrasing (without "Option 1:", "Option 2:", etc.):
   1. **(Recommended) I'll [action verb]**: Primary recommended next action I will perform with a short description in plain English.
   2. **I'll [action verb]**: An alternative direction I will take with a short description in plain English.
   3. **I'll [action verb]**: Another variation I will take with a short description in plain English.
3. **Numbered Selection Execution**: When the user replies with a number (e.g., "1", "2", "3", "option 1", "I choose 1"), immediately execute that numbered follow-up action.

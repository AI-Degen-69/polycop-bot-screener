# Project AGENTS Rules

### PolyCop & Polymarket Weighted 100-Point Audit Standard
Whenever asked to evaluate, recommend, or analyze a Polymarket copy-trading wallet, score it with the
engine as canon. The authoritative gate list, parameter weights and tier bands are generated from
`app/src/screener/score_wallets.py` (the only source of truth) in the section below; the scoring
engine's `SCORING_SPEC` and `tools/scoring_docs.py` produce it, and CI fails if the two diverge.
Never quote a gate threshold or point weight from memory — read it from the generated tables.

<!-- SCORING-SPEC:BEGIN -->

### Scoring Engine — Gates, Parameters and Tiers

> This section is generated from `app/src/screener/score_wallets.py` via
> `tools/scoring_docs.py`. Do not edit it by hand — change the code and run
> `python tools/scoring_docs.py generate`, or CI will fail the drift check.

#### Hard Rejection Gates (instant disqualification, never traded off)

| Gate | Condition | Why |
| :--- | :--- | :--- |
| PolyCop Site Score sanity floor | `< 40 / 100` | stops manually pasted garbage from being scored once the leaderboard pre-filter is gone |
| Toxic Copy Poison | `Modelled Copy PnL < $0` | a modelled copy that loses money is not a target |
| Slippage Cost Rate | `> 5.0% modelled` | roughly 21% real under the Friction Realism Multiplier (ADR 0001) |
| Hedged Rate | `> 3.0%` | market-making signature and doubled friction legs |
| Profit/Loss Ratio | `< 0.3` | winning pennies, losing dollars |
| Markets Sample | `< 20` | a streak, not a track record |
| Whale Avg Invest | `> $200` | a typical trade that dwarfs the bankroll cannot be mirrored |
| Divergence | `r20_pnl < $0 while actual_pnl > $1,000` | a dead edge must not be carried by history |

#### Continuous Parameters (100 points total)

| Parameter | Points | Zero points | Full marks |
| :--- | :---: | :--- | :--- |
| Edge-to-Friction Ratio | 24 | <= 1.0 (break-even) | >= 3.0 — edge per dollar of friction; the cheapest disqualifying arithmetic runs first |
| Slippage Cost Rate | 17 | >= 5.0% | <= 1.0% — modelled, before the Friction Realism Multiplier |
| Drawdown Depth | 13 | >= 0.50 of peak | 0.0 — from the lifetime equity curve |
| Recent Form | 11 | PnL <= $0 or slip unmeasured | >= 100% return over the recent-20 window at 0% slip — return on deployed capital, judged against the friction it came through (ADR 0004) |
| Daily Green Rate | 9 | < 40% or fewer than 10 observed days | >= 85% — copy-adjusted, measured from real per-day simulated results |
| Profit/Loss Ratio | 9 | <= 0.3 | >= 3.0 |
| Sizing Fit | 6 | outside the Copyable Trade Window | at the window midpoint — peak derived from the Copy Execution Profile, never hand-picked |
| Hedged Control | 6 | >= 3.0% | 0% |
| Markets Sample | 3 | < 20 | >= 200 |
| Capital Efficiency | 2 | 0 | >= 30 PnL/volume ratio |

#### Copyability Score Tier Bands (triage only — verdicts come from simulation)

| Tier | Score |
| :--- | :--- |
| S-Tier (God-Tier Target) | &ge; 72 |
| A-Tier (Strong Copy Target) | &ge; 65 |
| B-Tier (Moderate Copy Target) | &ge; 60 |
| C-Tier (High Risk / Volatile) | &ge; 50 |
| F-Tier (Toxic / Rejection) | < 50 |

#### Simulated Verdict Tier Bands (Edge Retention — the verdict)

| Tier | Edge Retention |
| :--- | :--- |
| S-Tier (God-Tier Target) | &ge; 0.85 |
| A-Tier (Strong Copy Target) | &ge; 0.70 |
| B-Tier (Moderate Copy Target) | &ge; 0.50 |
| C-Tier (High Risk / Volatile) | &ge; 0.30 |
| F-Tier / REJECT | < 0.30 |

<!-- SCORING-SPEC:END -->

**Data Evidence Requirement**: Present the numerical breakdown for every weighted parameter alongside the final grade, as the engine reports it in `breakdown`.

### Response Formatting Rules
1. **No Time Estimates**: Do NOT include minute counts or time duration estimates (e.g., mins count) in responses.
2. **Suggested Follow-ups Ending**: End every response with a `### Suggested Follow-ups` section containing exactly 3 options framed as actions the AI assistant will execute using "I'll..." phrasing (without "Option 1:", "Option 2:", etc.):
   1. **(Recommended) I'll [action verb]**: Primary recommended next action I will perform with a short description in plain English.
   2. **I'll [action verb]**: An alternative direction I will take with a short description in plain English.
   3. **I'll [action verb]**: Another variation I will take with a short description in plain English.
3. **Numbered Selection Execution**: When the user replies with a number (e.g., "1", "2", "3", "option 1", "I choose 1"), immediately execute that numbered follow-up action.

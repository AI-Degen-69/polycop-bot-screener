# Evaluation: Do issues #29–#32 serve the screener's goal?

**Date:** 2026-08-10 · **Type:** research evaluation (repo-internal + external primary-source verification) · **Scope:** issues #29 (spec), #30 (Track Record Length gate), #31 (Wash Signature gate), #32 (Recency-weighted Recent Form)

---

## Goal under test

The screener's purpose, per `CONTEXT.md`: select Polymarket wallets a small-bankroll follower can profitably copy — surfacing wallets with a **real edge** that survives replication (**copyability**), and filtering out **Mirage** shapes (arbitrage bots, short lucky streaks, wash-trading churn, dead edges). The user's framing: surface "real edge capable addresses from a pool (leaderboard)" and "filter out bots / unreal / non copyable addresses."

The question: do #29–#32 move that needle?

## Method

- **Internal primary sources:** the four issue bodies; the scoring engine and its gates/parameters (`SCORING_SPEC`); `CONTEXT.md` domain model; the motivating deep-research doc (`docs/research/copy-trade-settings-and-wallet-screening.md`); measured distributions over the cached scan (2,120 profiles).
- **External primary-source verification** (background researcher): the Columbia wash-trading paper (SSRN 5714122), the arXiv Polymarket microstructure paper (2604.24366), binomial sample-size statistics, social/copy-trading skill-persistence literature.

---

## The four load-bearing claims, verified

| Claim the tickets rest on | Verification | What it means for the tickets |
|---|---|---|
| **Sample size:** ~1,000 trades separate a 53% win rate from a coin flip at ~95% confidence; a few hundred for 55% | **Confirmed by binomial statistics.** For a proportion, SE = √(p(1−p)/n); solving n ≈ (z·SE/Δp)² gives ~1,000–1,100 trades at p=0.53, ~380–400 at p=0.55 | #30's **50-trade bar is honest only as a luck-floor**, not a skill threshold. It rules out obvious streaks; it does not certify skill. The Markets Sample parameter already uses 200 as full marks — a stronger, but still not 95%-confidence, bar |
| **Wash detection:** Columbia's method is network-based (self-counterparty loops, homophily clusters, 43k-wallet rings); simple aggregates can't catch the rings | **Confirmed.** The Columbia algorithm is an iterative network redistribution over wallet–counterparty graphs (SSRN 5714122). Crude self-trading with sub-penny churn is detectable from aggregates; sophisticated rings route through neutral-PnL intermediate wallets and need per-trade counterparty mapping | #31's **wallet-level signature (volume, profit-per-dollar, avg entry price) can only catch the crude tail** of wash trading — not the bulk of the ~25% fake volume. The spec already says loop detection is out of scope, so #31 is honest but limited: a crude-churn tripwire, expected to fire on ~0.1–0.2% of the current pool |
| **Bots:** bots dominate top wallets and are fingerprintable from public data | **Confirmed.** Microstructure work on the Polymarket order book shows on-chain fills expose sub-second latency, constant-spread market-making loops, and near-zero hold times (arXiv 2604.24366); industry on-chain analyses report roughly **~70% of top-volume wallets show programmatic/bot signatures** (as reported by IOSG-style analyses). A bot with genuine PnL is *not* wash trading and has plenty of trades | **The single biggest gap against the stated goal.** None of #29–#32 target bots — the spec explicitly de-scopes bot-latency detection. A bot sails through #30 (lots of trades), #31 (not churn without edge), and #32 (trades constantly, so high recency). The screen's only partial bot defenses are the Hedged Rate gate and the simulated-verdict machinery, which catch market-makers and non-copyable edges but not speed-based bots whose edge is simply *uncopyable by a later follower* |
| **Edge decay:** predictive skill does not persist; recency weighting is justified | **Confirmed by copy-trading literature** (e.g., TalTech study of social-trading copy portfolios; eToro disclosures on non-reliability of track records). Edges decay via regime shifts, crowding, and being front-run once public | #32 is the **best-evidenced of the three** and targets the copyability failure most directly. But see the slow-trader false-penalty risk below |

---

## Per-issue verdict

| Issue | Verdict | Evidence / reasoning |
|---|---|---|
| **#29** (spec) | **Sound, honest, but de-scopes the biggest problem.** | Correctly frames the three weaknesses, uses measured-only inputs, records the asymmetric absence semantics, and honestly flags that #31 fires rarely. But it explicitly lists **bot-latency detection as out of scope** — the largest "unreal address" category — and self-counterparty loop detection as out of scope — the bulk of wash volume |
| **#30** (Track Record Length gate) | **Helpful — small but real.** | Kills obvious short streaks; complements the Markets gate (markets ≠ trades: 50 trades in 5 markets fails the 20-market gate; 30 one-trade markets fails #30). Low risk, cheap, single constant. Two caveats: (1) 50 trades is far below the ~400–1,000 statistical bar, so it is a luck-floor, not a skill bar; (2) if the daily-activity series is a rolling window, it **undercounts slow traders** — the same population #32 risks penalising (see below) |
| **#31** (Wash Signature gate) | **Marginally helpful — honest tripwire.** | Can catch only crude churn (sub-penny entries, volume without edge); cannot catch Columbia-style rings (needs counterparty graphs). Overlaps the existing Hedged Rate gate (market-making signature) and the Capital Efficiency parameter (pnl/volume) — fine as defense-in-depth, but it will rarely change the survivor pool. Its real value is the always-on flag surfaced in the feed and the tripwire for future scans |
| **#32** (Recency-weighted Recent Form) | **Most valuable of the three — with one calibration risk.** | Directly attacks "dead edge carried by history," is evidence-backed (edge decay), and reuses the already-measured but unused recent win rate. **Risk:** a hard recency decay penalises slow-and-steady traders — and the research's own finding is that slow political markets are the *most copyable* (lowest copy bar). A weekly political trader lands in the "stale (7d+)" bucket and would be decayed most. Mitigation options: decay relative to the wallet's own cadence, or a much longer stale horizon, or only decaying Recent Form once the recent-20 window itself is old |

---

## Gaps and risks, ranked

1. **Bots are untouched (highest-impact gap).** ~70% of top-volume wallets show bot signatures; a bot with real PnL passes #30, #31 and #32. For the stated goal ("filters out bots"), a **bot-signature measure** — hold-time distribution, trade-timing regularity, sub-second-latency response, near-zero inventory dwell — is the missing fourth measure. The arXiv microstructure paper demonstrates the raw data exists; the open question is whether the leaderboard profile (rather than the trade stream) exposes enough of it.
2. **The wash gate cannot see the wash problem.** Wallet-level aggregates catch only the crude tail; the Columbia rings are invisible without per-trade counterparty data. If wash-filtering is a goal, the Data API trade stream is the enabling dependency — currently out of scope.
3. **Sample-size bar is a floor, not a skill bar.** 50 trades < ~400–1,000. Acceptable as a luck-floor; worth stating in the docs so the gate isn't over-read.
4. **Slow-trader false penalties (compounded #30 + #32 risk).** If the daily-series window undercounts and the recency decay is absolute-time-based, the same population — slow, persistent, low-frequency traders, arguably the most copyable — is hit twice.
5. **Spec-vs-goal mismatch to watch.** The three measures improve *pool reliability* (fewer luck/wash/stale candidates); they do not change the *profit logic* (edge/friction/simulation verdicts) and barely touch the *unreal-address* problem's two biggest shapes (bots, wash rings). If the current pool already contains few crude mirages, the observable feed change will be small — that is expected and fine, but the value is defensive.

---

## Recommendations

1. **Proceed with #30, #31, #32 as scoped** — they are cheap, honest, low-risk integrity floors consistent with the engine's conventions, and #32 is genuinely evidence-backed.
2. **Add a follow-up ticket: a Bot Signature measure** (or explicitly re-scope it into #29) — this is the highest-value missing piece for "filters out bots." Design it on the same measured-only, fail-closed seam: hold-time distribution and trade-timing regularity if the data supports them; otherwise a documented lower-bound flag.
3. **Calibration guards for #32:** decay relative to the wallet's own inter-trade cadence (or a ≥30-day stale horizon) so slow-but-alive traders aren't penalised; test the weekly-political-trader shape explicitly.
4. **#30 measurement verification:** confirm the daily-activity series covers lifetime (not a rolling window) before the gate ships; if it is a window, measure Track Record Length with an explicit lifetime-floor fallback.
5. **Keep #31's absence-passes semantics** (no evidence = no conviction) and its feed flag; consider noting in the docs that it is a crude-churn tripwire, not loop detection.
6. **Re-measure tier bands after all three land (#33)** as planned — the survivor-share shift is the honest check on whether the floors still mean what ADR 0010 said.

## Bottom line

Issues #29–#32 are **directionally correct and worth doing**, but they harden the *margins* of the screener — they do not address its two largest "unreal address" populations. Sample-size verification confirms #30 as a luck-floor; wash-detection verification confirms #31 can only catch crude churn; edge-decay verification confirms #32 is the strongest of the three. The **bot population (~70% of top-volume wallets) is the gap that most directly threatens the stated goal**, and it is the one category all three measures miss. That is the natural next ticket after #30–#32.

## Sources

- SSRN 5714122 — *Network-Based Detection of Wash Trading* (Columbia; Sirolly et al.): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5714122 — network/homophily method; aggregates can't catch rings
- CoinDesk — *Polymarket's Trading Volume May Be 25% Fake, Columbia Study Finds* (Nov 2025): https://www.coindesk.com/markets/2025/11/07/polymarket-s-trading-volume-may-be-25-fake-columbia-study-finds — 25% fake volume, 43k-wallet cluster
- Rajiv Sethi — *The Detection of Wash Trading*: https://rajivsethi.substack.com/p/the-detection-of-wash-trading — author commentary on the Columbia method
- arXiv 2604.24366 — *The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book*: https://arxiv.org/html/2604.24366v1 — on-chain fills expose bot signatures (sub-second latency, constant-spread MM, near-zero hold)
- Binomial proportion statistics (standard error of a proportion, sample size for confidence intervals) — computed, no external URL; ~1,000–1,100 trades for 53% vs chance at 95% confidence, ~380–400 for 55%
- TalTech — *Empirical Investigation on the Performance of Copy Trading Portfolios on Social Trading Platforms* (as reported by the background researcher) — past performance poorly predicts future; supports recency weighting
- eToro platform disclosures on the non-reliability of historical track records (as reported by the background researcher)
- Repo primary sources: issue bodies #29–#32; `app/src/screener/score_wallets.py` (SCORING_SPEC); `CONTEXT.md`; `docs/research/copy-trade-settings-and-wallet-screening.md`; cached phase-1 scan distributions
- *Uncertainty notes:* the ~70% bot-prevalence figure is as reported by industry on-chain analyses (IOSG-style) and was not independently re-derived here; treat as an order-of-magnitude claim. The TalTech/eToro references were summarised by the researcher without URLs and are cited as reported.

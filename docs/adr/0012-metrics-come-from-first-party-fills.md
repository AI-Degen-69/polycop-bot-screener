# Wallet metrics come from first-party fills, not the aggregator's precomputed fields

Every figure the screen reads today arrives precomputed from the third-party
PolyCop leaderboard API: `actual_pnl`, `copy_backtest_pnl`, `hedged_pct`,
`avg_profit_loss_ratio`, `r20_wr`, `daily_stats_json`. The pipeline has no way
to check any of them. If that aggregator is stale, wrong, or gone, the 100-point
audit still produces confident tiers over numbers nobody verified, and ADR 0007's
discipline — an unmeasured figure must stay absent — cannot be enforced on a
field that arrives already filled in.

`overnight_scanner.py` demonstrated the alternative over a 14-hour unattended
run: Polymarket's own endpoints answer unauthenticated and expose the raw fills
(`data-api/activity`, `data-api/positions`, `data-api/holders`,
`lb-api/{profit,volume}`, `gamma-api/events`). From those events the scanner
recomputes hold periods, trade cadence, inter-fill gaps, sizing distribution,
per-market settled PnL and win rate — and it found three scoring bugs in its own
arithmetic that were only findable because the inputs were raw.

## The decision

**The aggregator supplies addresses. Every judgment is derived from first-party
fills.**

The aggregator's two jobs separate cleanly, and only one of them survives.
Measured against its own top-ranked wallet, `0xb2d2d1ad3b…` — which it scores
100/100 on a reported 99.52% win rate over 1,048 markets — the raw fills show a
median buy price of **0.999**, 78% of fills at or above 0.95, and a maximum
possible gain of **0.1% per fill**. That wallet is uncopyable by arithmetic: a
follower paying any slippage loses money, so Edge-to-Friction is below one
before it is modelled. The site score rewards win rate, and in a prediction
market win rate is bought by paying 99 cents for a certainty. `CONTEXT.md`
already asserted that the site score "optimises for something other than
copyability"; this is that claim measured.

Its address list is a different matter: it pages 100 profiles at a time over
thousands, where `lb-api` saturates at 50 rows across eight metric x window
slices. Breadth is the one thing it is genuinely good at, and candidate
discovery is the binding constraint on this project's yield.

- Phase 1 sources candidate **addresses** from three places and keeps nothing
  else from any of them: the aggregator's leaderboard (address field only, every
  precomputed field discarded at the boundary), `lb-api/{profit,volume}` (eight
  metric x window slices; `category` and `offset` are ignored by that endpoint
  and `limit` saturates at 50), and holder sampling of the busiest live markets
  per Gamma tag, which is the only path reaching category specialists no global
  board ranks.
- Per-wallet measurement reads `data-api/activity` (TRADE plus REDEEM, so a
  wallet that never sells still has a measurable holding period) and
  `data-api/positions`.
- A market's result is scored only when its cost basis is fully observed inside
  the fetched window: shares closed must not exceed shares bought. Applied to
  wins and losses alike, because applying it to one side biases every truncated
  wallet.
- No aggregator field reaches the engine. `polycop_site_score`, `copy_backtest_pnl`,
  `hedged_pct`, `r20_slip` and their siblings are dropped at the phase-1
  boundary, which means the four hard gates and the roughly 41 score points that
  read them need first-party substitutes or removal before cutover. That work is
  a blocking prerequisite of this decision, not a follow-up to it.

**What this decision does not buy.** The verdict still leaves the building:
`run_mock_client.py:100` POSTs to `https://polycop.fun/api/run_mock`, and under
ADR 0002 and ADR 0009 that response is the verdict while the score is only
triage. Independence at the triage layer is real; independence at the verdict
layer is not claimed here and remains an accepted, named risk.

## Why not the alternatives

- **Keep the aggregator as the source and bolt the scanner alongside** was
  rejected because it leaves the single point of failure in place and produces
  two rankings of the same wallet with no rule for which one the dashboard
  shows.
- **Drop the aggregator entirely** was rejected as premature. It is the only
  independent check available on the derived arithmetic, and this project has
  now shipped three PnL bugs in one night; a second opinion is worth keeping
  even when it is not authoritative.
- **Score every market the window touches** was rejected because it double
  counts: a redemption of shares bought before the window books the full payout
  against a fraction of its cost. Measured on one wallet, that inflated a 2.4%
  edge into an apparent $714k profit against a true figure near $40k.

## Consequences

- Metrics derived from a truncated window are **window-scoped, not lifetime**,
  and ADR 0007 governs them: a wallet whose window does not cover its history
  carries `history_truncated`, and figures that could not be completely measured
  stay absent rather than ranking as measured. Comparing a wallet measured over
  four months against one measured over six hours is the error this flag exists
  to prevent.
- The scan gains a scoring-version stamp. When the derivation changes, records
  written under the old one are re-scanned before new candidates are taken,
  because a dataset that mixes two derivations cannot be ranked.
- A wallet that stops qualifying under a corrected derivation is removed, not
  left in place. A stale record still looks authoritative to every reader.
- Automation classification becomes measurable rather than inferred from
  `hedged_pct` alone: fill cadence, inter-fill gap, sizing granularity and hold
  time are all first-party observations now. They do **not** feed a hard gate.
  The composite `bot_score` is hand-tuned against no labelled set, and a gate is
  a binary disqualifier that cannot be traded off; granting that authority to an
  uncalibrated proxy would discard 267 of 291 current records on a number set by
  eye. The traits enter as scored parameters, and any gate is written against a
  measured trait — median hold time, fills per market — never against the
  classifier's verdict.

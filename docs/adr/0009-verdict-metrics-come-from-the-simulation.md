# The verdict-side metrics come from the simulation, not the leaderboard

Issue #26: the spec's #13/#14/#15 requirements asked for three verdict-side
figures to come from the Simulated Copy Run, and `parse_simulated_run_response`
already extracted them — but no consumer read them. The published feed carried
`balance_miss_details` but no skip reasons, and the page's Daily Green and
Drawdown figures were the leaderboard's lifetime readings rather than the
follower's simulation.

## The decision

**The verdict side publishes the simulated figures; the triage side keeps the
lifetime figures.** The two answer different questions, and the issue's note
is explicit that the triage Drawdown Depth from `all_pnl_json` is a separate,
deliberate decision. What was missing was the verdict side:

- **Daily Green Rate** (`simulated_daily_green_rate`, percent) is
  `winning_days / trading_days` from the 10%-slippage run's per-day results,
  with the sample size published beside it (`simulated_trading_days`). Zero
  trading days means nothing measured, so the rate is `None`, not 0%.
- **Drawdown Depth** (`simulated_max_drawdown`, percent) is the simulation's
  own `max_drawdown` field. An absent field stays absent — the parser reads
  it as `Optional[float]` rather than defaulting it to a fabricated 0.0.
- **Decision log** (`skip_reasons`) is the decision log condensed to the
  refusals — `SKIP_FILTER` (the Copyable Trade Window refused) and `SKIP_CAP`
  (the bankroll's risk cap stopped it) — each carrying the upstream message
  that names the failing filter. Mirrored actions and ghost exits are not
  skips. This is what makes spec #13 readable on the page.

Both figures and the reasons come from the same 10%-slippage run that produces
the verdict PnL, so the verdict's numbers share one provenance.

## Why not the alternatives

- **Pointing the page at the leaderboard lifetime series** (the status quo)
  describes the target's history, not the follower's, and contradicts the
  spec's wording: Drawdown Depth "describes my account rather than the
  target's", Daily Green Rate "measures what its name claims".
- **Switching the triage engine to the simulated figures** was rejected: the
  triage runs before (and independently of) the simulation — it must work when
  the endpoint is down — and ADR 0002's degradation path depends on that.
  Triage stays leaderboard-fed by design.

## Consequences

- The feed's simulated rows carry `simulated_daily_green_rate`,
  `simulated_trading_days`, `simulated_max_drawdown` and `skip_reasons`;
  triage-fallback rows carry `None`/`0`/`[]`, and the page renders "Not
  simulated"/"Not measured" rather than a figure of zero.
- `parse_simulated_run_response`'s `max_drawdown` becomes `Optional[float]`,
  so an absent upstream field can no longer masquerade as a measured zero.

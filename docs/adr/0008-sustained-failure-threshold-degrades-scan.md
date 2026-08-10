# A sustained failure threshold, not any single failure, degrades a scan

Issue #25: `run_phase3_simulation_rank` broke the whole scan loop on any
unsuccessful slippage level. One transient failure on wallet 60 of 66
discarded 59 wallets' worth of completed simulation work — roughly 236
`run_mock` calls — and downgraded every verdict in the feed to triage
ranking, even though the endpoint was healthy for all the other wallets.

Issue #3 asks for degradation when the endpoint is *failed or unavailable*.
An outage and a single flaky request are not the same event, and the old code
treated them as the same event.

## The decision

**One failure is a flake; a streak is an outage.**

- A wallet whose gated levels the endpoint did not answer for is rejected
  with its endpoint-failure reason (ADR 0007) and the scan continues. Its
  completed siblings keep their verdicts.
- Only a sustained run of consecutive endpoint-failure wallets — default
  threshold of 3 — is treated as an outage. The scan stops hammering the dead
  endpoint, the verdicts already computed are kept and published, and only
  the wallets that were never reached fall back to triage ordering, each
  labelled `verdict_source: "triage"` so the page can tell them from
  simulated tiers.
- A wallet that measured a non-positive PnL is not an outage signal: the
  endpoint answered, the wallet simply failed the gate. A measured rejection
  resets the failure streak.
- The threshold is a parameter of `run_phase3_simulation_rank`
  (`endpoint_failure_threshold`, default 3), consistent with the phase's
  existing test seams (`fetcher`, `cache_dir`).

## Why not the alternatives

- **Breaking on any failure** (the status quo) conflates a flake with an
  outage, throws away completed work, and fabricates a full triage fallback
  on top of healthy verdicts.
- **Degrading only when every wallet fails** would keep hammering a dead
  endpoint for the entire scan before admitting the outage, wasting exactly
  the `run_mock` calls #25 wants to stop burning.
- **Retrying inside the sweep** remains out of scope (ADR 0007): the sweep's
  job is to be honest about what it could not measure; the scan's job is to
  decide how much failure is tolerable.

## Consequences

- The published feed may now mix `verdict_source` values in one scan. The web
  banner distinguishes a partial degrade ("simulation interrupted — some
  wallets are triage order only") from a full one.
- The worst-case waste on an outage is bounded by the threshold times the
  levels per wallet (3 × 4 = 12 calls) instead of the whole scan.
- The scan's per-wallet rejection reasons are the honest data the threshold
  keys off, which is exactly why ADR 0007 was its prerequisite.

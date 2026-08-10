# A failed run_mock fetch is an absent measurement, not a measured rejection

Issue #24: `run_slippage_sensitivity_sweep` scored an unsuccessful fetch as
`pnl = 0.0`, so the 10%-slippage gate rejected the wallet with
"Non-positive Simulated Copy PnL ($0.00) at 10% slippage threshold" — a
statement of a measurement that was never taken. A network failure and a
wallet that genuinely broke even were indistinguishable in the output. Issue
#3's ordering rules exist because "a wrong answer here is silent"; this was
that wrong answer.

## The decision

**Absent stays absent.** A level whose fetch failed records `None` in
`pnl_by_level`, never `0.0`:

- A wallet whose gated level (10% or 2%) is unmeasured is rejected with an
  **endpoint-failure reason** — "Simulation unavailable at 10% slippage
  threshold (endpoint failure)" — never a fabricated dollar figure.
- A wallet whose 10% figure was genuinely measured at `<= 0` keeps the
  existing measured rejection wording. The two cases are now distinguishable
  in the output.
- A failed non-gated level (5% or 15%) records `None` in the published feed —
  a visible gap in the decay curve — but does not disqualify the wallet, since
  the gates only read 10% and 2%.
- Edge Retention is computed only when both 2% and 10% are measured and
  positive (the existing gate ordering, plus `None` guards).

## Why not the alternatives

- **Keep collapsing to zero** was rejected because it fabricates a measured
  rejection and hides the endpoint failure from every downstream reader — the
  exact "silent wrong answer" issue #3's ordering rules exist to prevent.
- **Retrying the failed level inside the sweep** was deferred to issue #25:
  distinguishing a flaky request from an outage is a scan-level question (a
  sustained-failure threshold), not a per-level one. The sweep's job is to be
  honest about what it could not measure; the scan's job is to decide how much
  failure is tolerable.

## Consequences

- `pnl_by_level` may now contain `None` values, so every consumer must read
  levels as `Optional[float]` rather than `float`. The published
  `pnl_by_slippage_level` may carry `None` for a level the endpoint did not
  answer; the web app's existing "Not measured"/dash rendering discipline
  covers it.
- This change is the prerequisite for #25, not its substitute: it makes the
  per-wallet reasons honest so a sustained-failure threshold has honest data
  to key off. The scan-level `break` on any failure is a separate issue.
- A regression test locks the distinction: a raising fetcher must produce a
  rejection whose reason names the endpoint failure and a `None` PnL at the
  failed level, while a genuine measured `0.0` keeps the measured wording.

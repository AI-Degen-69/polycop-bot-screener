# Copyable Window Share is a simulation-only metric; its 10 triage points redistribute

Issue #23 found that Copyable Window Share — ten points in the triage table — could never be
measured at triage. Its only source is the `run_mock` response (`to_engine_metrics` in
`leaderboard_adapter.py`), which exists only after Phase 3 has simulated the wallet. Measured
against the cached scan, 0 of 66 phase-2 targets carried it, and the triage breakdown's
`copyable_window_share` was `None` for every wallet. The decision is settled: the parameter stays,
as a **verdict-side measurement**, and its ten triage points are redistributed proportionally
across the parameters triage can actually measure.

## Why not a leaderboard proxy

The alternative — ten points for a proxy computable from leaderboard fields — was rejected. Copyable
Window Share is distributional: it counts the share of entry signals the Copyable Trade Window
admits, which requires the per-trade size distribution only a Simulated Copy Run provides. The
leaderboard profile offers one size figure, `avg_invest`, which Sizing Fit already turns into five
points. A proxy would either duplicate Sizing Fit on a weaker signal or be an ungrounded guess, and
ADR 0002's premise is that the screen measures copyability rather than inferring it from proxies.
The screen's founding commitment is "stop inferring copyability and measure it"; inventing a new
inference for a quantity the simulation already measures exactly would walk that commitment back.

## The redistribution

The ten points return to the live parameters in proportion to their existing weights, so the
maintainer's relative priorities survive untouched:

| Parameter | Was | Now |
| :--- | ---: | ---: |
| Edge-to-Friction Ratio | 22 | 24 |
| Slippage Cost Rate | 15 | 17 |
| Drawdown Depth | 12 | 13 |
| Copyable Window Share | 10 | — (simulation-only) |
| Recent Form | 10 | 11 |
| Daily Green Rate | 8 | 9 |
| Profit/Loss Ratio | 8 | 9 |
| Sizing Fit | 5 | 6 |
| Hedged Control | 5 | 6 |
| Markets Sample | 3 | 3 |
| Capital Efficiency | 2 | 2 |

Proportional scaling preserves the spec's deliberate choices — Edge-to-Friction remains the largest
block (user story 17), the win-rate family keeps its reduced share — without inventing new
priorities.

## Consequences

- The triage engine's metric shape drops `copyable_window_share`; `to_engine_metrics` stops reading
  `run_mock_response` for it. This closes the stale-payload footgun flagged on PR #22 — a stale
  simulation response can no longer silently feed Phase 2 scoring.
- The measurement survives intact on the verdict side: Phase 3 already computes
  `copyable_window_share` from the 10%-slippage run's decision log and the web cards already render
  it (user story 11).
- The tier bands (ADR 0005) are unchanged and remain absolute; the next calibration run measures the
  redistributed distribution naturally. Scores are not comparable across the change, as with any
  engine revision.
- The generated scoring tables must be regenerated (`tools/scoring_docs.py`); CI fails the drift
  check until they are.

## Considered options

- **Keep the dead ten points**: rejected — the triage scale's effective ceiling becomes a permanent
  90, the parameter earns nothing while the verdict card renders the real figure, and the
  stale-`run_mock` footgun stays live.
- **Leaderboard proxy**: rejected — no proxy for a distributional quantity exists in a profile, and
  the nearest proxy (`avg_invest` vs. the window) is already Sizing Fit.
- **Targeted redistribution into Sizing Fit**: rejected — over-concentrates size weighting on one
  parameter; proportional preserves all of the spec's relative priorities.

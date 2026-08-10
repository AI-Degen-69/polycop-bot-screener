# Copyability Score tier bands re-measured after the #23 reweight

ADR 0005 calibrated the tier bands (72 / 65 / 60 / 50) against a scored run of the
pre-reweight engine and left an explicit instruction: *re-measure the distribution over a
fresh scan before moving any floor*. Issue #23 then reweighted the engine — it dropped a
simulation-only parameter's dead triage points and redistributed them across the
parameters triage can actually measure (ADR 0006) — which shifted the distribution upward
enough that S-Tier's share of survivors roughly tripled under the old floors. This ADR is
the re-measurement that instruction asked for.

## The measured distribution

A full scoring run over the cached Phase 1 data (2,120 profiles, 105 survivors) with the
post-reweight engine:

| Statistic | ADR 0005 run (pre-#23) | Re-measured (post-#23) | Shift |
|---|---:|---:|---:|
| Minimum | 16.28 | 18.39 | ×1.13 |
| p25 | 35.33 | 38.85 | ×1.10 |
| Median | 47.04 | 48.02 | ×1.02 |
| Mean | 48.05 | 51.33 | ×1.07 |
| p75 | 62.10 | 65.67 | ×1.06 |
| p90 | 67.46 | 73.12 | ×1.08 |
| Maximum | 77.05 | 85.89 | ×1.11 |

The stretch is not uniform: the top of the distribution moved more than the middle
(median ×1.02 vs. max ×1.11), because the reweight's redistributed points landed
proportionally on parameters the leading wallets already measured well on.

Two causes moved between the runs, not one: the reweight AND a fresh scrape (1,401
profiles / 66 survivors in the 0005 run, 2,120 / 105 now). The shares quoted below
are therefore the honest comparison — raw counts across different populations
would be misleading — and the direction of the shift (upper tail stretching more
than the middle) is the signature of the reweight regardless of the population
refresh.

## The distortion under the old floors

Under the ADR 0005 floors (72 / 65 / 60 / 50) the same re-measured run placed 12 wallets
in S-Tier and 15 in A-Tier — an S-Tier share of 11.4% of survivors, roughly three times
the 4.5% the 0005 calibration assigned. As in ADR 0005, this is a verdict produced by an
offset, not by performance: the floors describe a scale the reweighted engine no longer
uses.

## The chosen boundaries

| Tier | Old floor | New floor | Count in the re-measured run | Share |
|---|---:|---:|---:|---:|
| S-Tier | 72 | **80** | 4 | 3.8% |
| A-Tier | 65 | **71** | 11 | 10.5% |
| B-Tier | 60 | **65** | 12 | 11.4% |
| C-Tier | 50 | **56** | 15 | 14.3% |
| F-Tier | — | < 56 | 63 | 60.0% |

The new floors sit on visible gaps in the re-measured distribution, following the method
ADR 0005 established rather than a blind uniform scale (a ×1.111 scale would have landed
A-Tier at 7.6% and C-Tier at 18.1% — the middle of the distribution simply did not shift
as far as the top):

- **80** sits between the top cluster (82.69–85.89) and the next tier down (78.46) —
  the widest gap in the run (4.23).
- **71** sits between the 71.50–72.98 cluster and the 69.81 body, exploiting the
  larger 71.50 → 69.81 gap (1.69) rather than the smaller internal 72.98 → 71.92 one.
- **65** sits between the 65.67–67.61 band and the 64.43–64.27 cluster below it.
- **56** sits in the widest gap below the top cluster (57.41 → 54.23, a 3.18 gap), the C/F seam.

The new bands restore the calibration's intent — S-Tier is again the top few, not a
sixth of the field — while keeping the ADR 0005 commitment that boundaries remain
absolute (no percentile floors, no manufactured S-Tiers in a weak week).

## Follows automatically

- **Hidden Gem** threshold follows `TIER_A_MIN` (now 71), so the gem definition cannot
  silently diverge from the bands.
- **Web UI labels** (S-Tier pill, gem card floors) and the generated docs are rendered
  from the same constants via `tools/scoring_docs.py`, so they moved with the code.

## Consequences

Scores remain comparable across weekly scans within the new bands, but not comparable to
scores computed before this change. The next revision should re-measure the distribution
over a fresh scan before moving any floor — and note that a reweight is precisely the
kind of engine change that can invalidate a calibration without any scan looking wrong.

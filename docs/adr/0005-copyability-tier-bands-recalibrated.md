# Copyability Score tier bands recalibrated against a real scored run

The tier bands (S / A / B / C / F on the 100-point Copyability Score) were inherited from the
outgoing engine at 90 / 80 / 70 / 50 and never checked against the distribution the reweighted
engine actually produces. Ticket #19 asked for them to be set against a real scored run over the
cached leaderboard data. They now sit at **72 / 65 / 60 / 50**.

## The measured distribution

A full Phase 2 run over the cached Phase 1 leaderboard data (1,401 profiles, 66 survivors) produced
this score distribution with the current engine, after the wiring-defect fix and the Recent Form
return change (ADR 0004):

| Statistic | Value |
|---|---:|
| Minimum | 16.28 |
| p25 | 35.33 |
| Median | 47.04 |
| Mean | 48.05 |
| p75 | 62.10 |
| p90 | 67.46 |
| Maximum | 77.05 |

Under the inherited boundaries (90 / 80 / 70 / 50), the same run placed 0 wallets in S-Tier, 0 in
A-Tier and only 4 in B-Tier — a verdict produced by an offset, not by performance. The engine
scores on measured inputs and fails closed on absent ones, so its practical ceiling is well below
100 and the inherited bands described a scale the engine no longer used.

## The chosen boundaries

| Tier | Old floor | New floor | Count in the calibration run |
|---|---:|---:|---:|
| S-Tier | 90 | **72** | 3 |
| A-Tier | 80 | **65** | 7 |
| B-Tier | 70 | **60** | 11 |
| C-Tier | 50 | **50** | 10 |
| F-Tier | — | < 50 | 35 |

The new floors track visible gaps in the distribution: 72 sits between the top few wallets and the
rest, 65 between the upper tail and the body, 60 between the two mid clusters, and 50 is the
existing C/F seam, which the data still supports.

## Boundaries remain absolute

Percentile boundaries were considered and rejected, as in the original decision: absolute
boundaries keep scores comparable between weekly scans, let a target be seen degrading toward a
floor, and refuse to manufacture an S-Tier in a week when the whole field is poor. Only the numbers
have moved.

## Hidden Gem threshold follows

A Hidden Gem is a wallet the screen rates highly while the leaderboard rates it poorly. The gem
definition was `site score < 75 and score >= 80`; the 80 was the old A-Tier floor, so it moves with
the band to `score >= TIER_A_MIN` (65). The constant is shared, so the two cannot diverge again.

## Rank alongside the tier

Each wallet's rank within the scan (1-based, read off the published ordering) is now stamped by
Phase 3 and rendered beside the tier in the web app, so the reader sees both where a wallet sits
and why it sits there.

## Consequences

Scores remain comparable across weekly scans within the new bands, but are not comparable to scores
computed before this change. The next revision should re-measure the distribution over a fresh scan
before moving any floor.

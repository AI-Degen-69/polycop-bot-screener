# Modelled Copy PnL is a full-size mirror, and the tier bands stay put until a full rescan

The first-party cutover (ADR 0012) had to produce a Modelled Copy PnL locally, because the
aggregator's `copy_backtest_pnl` was the single field that gated two hard gates and 37 scored
points. The first implementation replayed each target's fills through the Copy Execution Profile as
stated: a $100 bankroll, a 3% copy ratio, a $5 position cap.

Run against 17 real wallets, that rejected **every one of them** on the Slippage Cost Rate gate.

The reason is arithmetic, not liquidity. Slippage Cost Rate is
`(actual_pnl - copy_pnl) / abs(actual_pnl)`. Against a bankroll-scaled copy, that gap is dominated
by the copy trading a fraction of the size: a wallet earning $900,000 against a $100 bankroll shows a
rate of essentially 100% whatever the friction. The gate then measures the bankroll, not the wallet.

## The decision

**Modelled Copy PnL is computed from a full-size mirror at the modelled friction assumption.**

CONTEXT.md already defined it that way - "computed under a fixed optimistic friction assumption and
a full-size mirror" - and the full-size half is what makes the figure measure friction and only
friction. `screener.first_party_copy_replay.mirror_profile` derives that counterfactual from the
stated profile: copy ratio 1.0, caps lifted, price bounds kept, and slippage pinned to the 2% per
side ADR 0001 records as the leaderboard's assumption.

The slippage pin matters separately. The profile's own `slippage_pct` is a **sweep level** - the
Slippage Sensitivity Sweep raises it deliberately to see what an edge survives. Computing the
*modelled* figure at a swept level would move the Slippage Cost Rate gate every time the sweep was
retuned, which is a threshold drifting for a reason unrelated to any wallet.

The replay therefore makes two passes over the same fills:

| Figure | Pass | Because |
| :--- | :--- | :--- |
| Modelled Copy PnL, Slippage Cost Rate | full-size mirror at 2%/side | the question is what friction cost the edge |
| Daily Green Rate, Recent Form friction | the stated bankroll profile | the question is what this follower would have experienced |

`bankroll_copy_pnl` is recorded alongside and reaches no gate. It is a real and useful number - it is
what the bankroll would have made - but it is not a friction measurement, because the window and the
caps are inside it.

## What the measurement showed

`tools/measure_tier_bands.py`, run over the scanner record on 2026-08-12 after the correction:

- 382 records on disk, **26** measured under the current Copy Execution Profile, 356 awaiting rescan.
- Of the 26: **3 scoreable**, 23 rejected.
- Slippage Cost Rate across the measured wallets: median **0.0**, p75 **0.65**, p90 **1.20**, max
  **6.06**. Before the correction it was above the 5% gate for every wallet without exception.
- Edge-to-Friction: median **0.50**, p75 **1.96**, p90 **3.78**.
- Rejections by gate: Whale Avg Invest 17, Slippage Cost Rate 10, Modelled Copy PnL 8, P/L Ratio
  unmeasured 4, Divergence 3, Hedged Rate 4 (2 of them unmeasured), Track Record Length 2.
- The three survivors scored 35.70, 54.57 and 55.15.

The gate is discriminating again rather than rejecting categorically, and the top rejector is now
Whale Avg Invest - the correct answer for a sample drawn from the volume leaderboard, where a
typical trade dwarfs a $100 bankroll.

## The tier bands were re-measured, and they hold

**The bands stay at S 80 / A 71 / B 65 / C 56 - measured, not inherited.**

An earlier revision of this ADR deferred the calibration because only 3 wallets were scoreable. The
scanner has since re-measured the whole dataset under the current profile. Run on 2026-08-13 over
**511 records, 0 stale**:

| | |
| :--- | :--- |
| Scoreable | 68 |
| Rejected by a gate | 443 |
| Score distribution | min 26.07, p25 33.98, **median 44.59**, p75 56.02, max 90.60 |

At the existing floors the 68 survivors fall out as **5 S-Tier, 7 A-Tier, 2 B-Tier, 4 C-Tier,
50 F-Tier**.

That is a working scale, so nothing moves. The S-Tier admits 7.3% of survivors - selective without
being empty, which is the failure ADR 0005's method guards against in both directions. The median
sits at 44.59, well below the C floor, so most survivors are correctly graded mediocre rather than
clustering into a flattering band. The top of the range reaches 90.60 without saturating, so the
scale still has room above its best wallet.

The bands were calibrated against the aggregator's distribution and they survive the change of
source. That is a result rather than a formality: every input is different and the shape they
produce is still one these floors describe.

**What would change them.** A candidate pool sized to the bankroll (see below). If the Whale gate
stops rejecting half the field, the surviving population is a different one and these floors are
owed a fresh measurement.

## The rejections say more than the scores do

Of 443 rejections:

| Gate | Count |
| :--- | ---: |
| Whale Avg Invest | 255 |
| Slippage Cost Rate | 242 |
| Divergence | 108 |
| Modelled Copy PnL | 87 |
| Track Record Length | 57 |
| P/L Ratio (measured) | 37 |
| Hedged Rate (measured) | 22 |

Two readings matter.

**152 rejections are for an absent measurement, not a bad one** - 51 P/L Ratio, 41 Hedged Rate, 30
Modelled Copy PnL, 30 Slippage Cost Rate. Those wallets were not judged and found wanting; the scan
could not measure them. P/L Ratio needs both a win and a loss, and Hedged Rate needs a non-empty
positions feed. Failing closed is the right call for a gate (ADR 0007), but a third of the
rejections being coverage rather than verdict is a fact about the scan, not about the wallets.

**The dominant rejector is a bankroll constraint.** Whale Avg Invest removes 255 of 511 - half the
field - because a typical trade dwarfs a $100 bankroll. The Paper Trade Log (ADR 0013) shows the
same thing from the other side: 76 of its first 91 observed trades fell outside the Copyable Trade
Window, so that bankroll could mirror roughly 4% of what these wallets do. The screen is working;
the bankroll is the binding constraint on which wallets are reachable at all, and no amount of
screening changes that.

## Consequences

Records carry `profile_fingerprint`, and a record measured under a profile that no longer exists is
re-scanned rather than scored. That is what makes the pending 356 visible instead of silently mixing
two derivations in one ranking.

Phase 2 now reports `pending_measurement_count` and `stale_profile_count` apart from
`rejected_disqualified_count`. Collapsing them would report scan coverage as a verdict about the
wallets, which is the same category error this ADR corrects at the gate level.

The Slippage Cost Rate gate's 5% threshold is **inherited, not re-derived**. It was calibrated
against the aggregator's arithmetic, and the first-party figure - while measuring the quantity the
gate's name describes - is a different computation. The distribution above is recorded so the next
revision has a baseline; changing the threshold now, on 26 records, would be the same mistake as
moving the bands.

## Considered options

Lowering the Slippage Cost Rate gate until wallets passed was rejected. The gate was rejecting
everything because the input was wrong, and a threshold moved to accommodate a broken input hides
the defect instead of fixing it.

Keeping the bankroll-scaled figure and treating the mass rejection as a real finding was rejected:
it is a real finding about the bankroll, and the screen already expresses bankroll limits through
Sizing Fit, the Copyable Trade Window, and Balance Miss. Charging it a second time through a
friction gate double-counts it.

Computing the mirror at the profile's own `slippage_pct` was rejected because it couples a gate
threshold to a sweep level, so retuning the sweep would silently re-gate every wallet.

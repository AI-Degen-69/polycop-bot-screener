# Recent Form scores return on deployed capital, not absolute dollars

Recent Form is worth ten triage points and measures whether a target's edge is recent and healthy.
The outgoing engine scored it on absolute dollars: recent profit divided by $1,000, capped at full
marks. Ticket #18 asked whether that was the right measure. It is not: Recent Form now scores the
recent profit as a **return on the capital that produced it**.

## The defect in absolute dollars

An absolute-dollar scale is meaningless to a follower with a small bankroll. A target whose typical
trade is large clears the $1,000 threshold on ordinary performance, while a target trading small
clears only a fraction of it however well it is doing — even though the second target is the one
whose trades a $100 bankroll can actually mirror. The scale rewarded the target's size rather than
its edge, and size is the thing the Copyable Trade Window already constrains elsewhere.

Measured over the cached leaderboard data, the effect was visible but not dominant: among the 66
survivors, `avg_invest` and `r20_pnl` were essentially uncorrelated (r ≈ 0.03), because the window
and whale gates already bound size. The distortion was concentrated at the window edges — a wallet
at the $167 top cleared full marks at roughly a quarter of the return a wallet at the $33 floor
needed — which is exactly the boundary where the scale should be size-blind.

## The measure

Recent Form = 10 points × (friction factor) × (return factor), where:

- return = `r20_pnl / (20 × avg_invest)` — recent profit divided by the capital deployed over the
  recent-20 trade window at the target's average investment;
- return factor = min(return / 1.0, 1.0) — full marks at a 100% return over the window;
- friction factor is unchanged: 1.0 at zero slip, 0.0 at the 15% slip ceiling.

The denominator is chosen and defended: `r20_pnl` is a measured recent figure, `avg_invest` is the
measured average trade size, and 20 is the size of the recent window. An absent or non-positive
denominator scores nothing (fail-closed), matching the rest of the engine.

## Consequences

Recent Form now measures edge per dollar deployed rather than dollars earned, so it no longer
rewards the target's size. The `$1,000` full-marks constant is gone; the full-marks return of 100%
keeps the parameter's practical sensitivity in the same band (the median survivor scores
comparably before and after). Historical scores are not comparable across the change, as with any
engine revision.

## Considered options

Keeping absolute dollars and documenting why size is legitimate was rejected because the size
signal is already handled by the Copyable Trade Window and the whale gate, so a second, unmeasured
dose of it inside Recent Form is pure distortion. Splitting the ten points between dollars and
return was rejected as a compromise between a wrong measure and a right one — it keeps half the
size bias while halving the parameter's sensitivity to the edge.

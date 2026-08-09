# Friction realism multiplier of 4.2 applied to leaderboard slippage figures

The PolyCop leaderboard's copy-PnL figures assume 2% adverse price movement on each side of a trade,
but logged live fills on this account showed 5.8% on a buy, 11.0% on a sell, and 14.9% on a buy that
subsequently failed — roughly four to seven times the modelled figure. We therefore treat every
leaderboard-derived slippage figure as understated by a factor of 4.2, and set the slippage-cost-rate
rejection gate at 5% modelled (equivalent to about 20% real) rather than the 20% the raw figures
would suggest.

## Consequences

The multiplier is calibrated from three observations and is expected to move. It is a tracked
estimate, not a constant: every logged fill should be recorded and the figure revised. Because
scores and gate thresholds are calibrated against it, changing the multiplier invalidates
previously computed scores, so historical results must be recomputed rather than compared directly
across revisions.

The multiplier applies a linear scaling to a figure that is not strictly linear in friction, and it
ignores both the minimum-order bump and trades skipped for insufficient liquidity. It is a
first-order correction that makes an optimistic number less wrong, not an accurate model of
execution.

## Considered options

Accepting the 2% figure and treating scores as purely relative was rejected because the rejection
gates are absolute, not relative — a gate calibrated to fiction rejects the wrong wallets. Deferring
until more fills accumulated was rejected because the existing 20% gate removes only 3 of 98
candidates and is therefore doing no work at all in the meantime.

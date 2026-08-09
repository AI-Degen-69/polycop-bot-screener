# Simulated copy runs decide the verdict; the 100-point score only triages

PolyCop exposes a simulation endpoint that accepts every parameter of our copy-execution profile —
bankroll, copy percentage, slippage, price bounds, trade-size bounds, per-token and global capital
caps — and replays a wallet's transaction history through it. Because that produces the actual
quantity we care about (what this account would have made) rather than a proxy for it, the
copyability score is demoted to a cheap pre-filter that decides which wallets are worth simulating,
and tiers are assigned from simulated performance instead.

## Consequences

The 100-point score remains visible and maintained, but a high score is no longer a recommendation.
Any change to the copy-execution profile invalidates every simulated result, because the simulation
is profile-specific in a way the score never was — results must therefore be cached against a hash
of the profile, not against the wallet alone.

The screen now depends on a third-party endpoint for its verdict rather than only for its inputs.
Each scan issues roughly four hundred simulation jobs, so runs must be throttled and cached, and the
provider's terms checked before scheduling. If the endpoint becomes unavailable the score still
functions as a fallback ranking, at reduced confidence.

## Considered options

Simulating every scraped wallet was rejected as both slow and inconsiderate to the provider, at
roughly fifteen hundred jobs per scan. Keeping the score as the verdict and treating simulation as
supporting evidence was rejected because it means ranking by proxies while a direct measurement of
the actual account is one request away.

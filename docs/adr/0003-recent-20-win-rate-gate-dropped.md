# The recent-20 win-rate hard rejection gate is deliberately dropped

The outgoing engine hard-rejected any wallet whose recent-20 win rate fell below 45%. The triage
rewrite in the parent spec (#3) removed it without a recorded decision. Ticket #17 asked that the
question be settled rather than left implicit. It is settled: the gate stays dropped, deliberately.

## Why it was dropped

The gate was an attempt to catch a dead edge by its win rate. Two of the current gates cover the
same failure more directly:

- The **Divergence gate** rejects a wallet whose recent form is negative while lifetime performance
  is strongly positive — the exact "dead edge carried by history" shape the win-rate gate pointed at,
  but stated in terms of profit rather than of a proxy for it.
- The **P/L Ratio gate** rejects wallets that win often and lose more than they win — the shape a
  high win rate can conceal.

A low win rate with a healthy payoff ratio is a legitimate profile (a wallet that wins a third of
its markets but wins three times as much as it loses is profitable), and the reweighted engine gives
the win-rate family only eight of its hundred points. Hard-rejecting on win rate would throw out
wallets the engine otherwise has good reason to keep.

## Consequences

No wallet is rejected for a sub-45% recent win rate alone. `r20_win_rate` remains a displayed and
sortable metric in the web app, but it carries no gate and no points in the engine. If live
simulation data ever shows low win rate to be independently disqualifying, the gate should be
reinstated with a measured threshold — not with the inherited 45.

## Considered options

Reinstating the 45% gate was rejected because it duplicates the divergence and P/L gates on a
weaker signal, and because it would reject the low-win-rate/high-payoff profile the P/L gate
explicitly admits. Keeping the gate but at a different threshold was rejected for the same reason:
any threshold is a number attached to a proxy when a measurement of the thing itself is available.

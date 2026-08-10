# Copy-Trading Screener

This context selects Polymarket wallets that a small-bankroll follower can profitably copy. It
exists because a wallet's profitability and its copyability are different properties, and the
public leaderboard measures only the first.

## Language

### Screening

**Candidate Wallet**:
A Polymarket address pulled from the leaderboard and put through the screen. A candidate is not yet
a target.
_Avoid_: lead, prospect, address

**Copy Target**:
A candidate that has survived every hard rejection gate. Only targets are scored and simulated.
_Avoid_: signal provider, guru, trader

**Mirage**:
A wallet whose surface statistics look excellent but whose edge cannot survive being copied. The
canonical shapes are the arbitrage bot and the short lucky streak.
_Avoid_: fake, scam, bad wallet

**Copyability**:
The property of an edge surviving replication by a follower who trades later, smaller, and at worse
prices. Distinct from profitability: a highly profitable wallet can have zero copyability.

**Hard Rejection Gate**:
A binary disqualifier applied before scoring. Gates are never traded off against points earned
elsewhere.
_Avoid_: filter, threshold, cutoff

**Copyability Score**:
A weighted sum used to triage candidates cheaply. It orders wallets for further work; it
is not the verdict. A parameter whose input could not be measured contributes nothing to the sum,
so an unmeasured wallet scores low rather than scoring well by default.
_Avoid_: rating, grade, rank

**Tier**:
A letter band presenting a verdict to the reader. Tiers derive from simulated performance, not from
the copyability score.
_Avoid_: grade, class

**Hidden Gem**:
A wallet the screen rates highly while the leaderboard's own score rates it poorly. The disagreement
is the point.

**Scan**:
A complete screening pass: every candidate scraped, filtered, scored and simulated together,
producing the feed the page reads. One wallet being scored is not a scan; a scan is the whole
pass. A repeated scan is a rescan.
_Avoid_: run, audit run, pipeline run

### Execution

**Bankroll**:
The follower's total capital available to the copy bot. All sizing and ruin reasoning is expressed
relative to it.
_Avoid_: capital, balance, account size

**Copy Execution Profile**:
The follower's complete copy-bot configuration. A screening result is valid only for a stated
profile.
_Avoid_: bot settings, config, parameters

**Copy Ratio**:
The nominal fraction of a target's trade size that the follower mirrors. Nominal because floors and
caps make the realised fraction differ outside a bounded range of trade sizes.
_Avoid_: copy percentage, scale factor

**Copyable Trade Window**:
The range of target trade sizes the execution profile actually mirrors. Trades outside it are
ignored entirely.
_Avoid_: ignore window, size filter

**Minimum Order Bump**:
Raising a copy order that falls below the venue minimum up to that minimum. It converts a sizing
shortfall into over-exposure on the target's smallest trades.

**Tracking Error**:
Divergence between the target's results and the follower's. It is never random — it concentrates in
whichever trades the execution profile handles worst.
_Avoid_: drift, divergence, slippage

### Measurement

**Actual PnL**:
The target's own realised and unrealised profit, as the venue reports it.
_Avoid_: real PnL, true PnL

**Modelled Copy PnL**:
The leaderboard's counterfactual profit figure, computed under a fixed optimistic friction
assumption and a full-size mirror. A thin-margin detector, not a follower's expected outcome.
_Avoid_: backtest copy PnL, copy PnL

**Slippage Cost Rate**:
The share of a target's actual profit consumed by copy friction. High values mean the edge lives
inside the friction.

**Friction Realism Multiplier**:
The factor by which observed execution friction exceeds the leadeboard model's assumption.
Calibrated from logged live fills and revised as fills accumulate.

**Edge-to-Friction Ratio**:
A target's average round-trip edge divided by expected round-trip friction. Below one, the wallet is
uncopyable by arithmetic regardless of any other metric.

**Copyable Window Share**:
The share of a target's entry signals falling inside the copyable trade window. Measures how much of
the target's behaviour the follower gets to replicate at all. Entries only: the window is a range of
sizes and has a say where a position is opened, while exits inherit whatever the entry did.

**Hedged Rate**:
The share of a target's markets held on both sides at once. Read as a market-making signature, and
as a doubling of the legs on which friction is paid.

**Sizing Fit**:
How closely a target's typical trade size sits inside the range where the realised copy ratio equals
the nominal one. Derived from the execution profile, never hand-picked.

**Drawdown Depth**:
Largest peak-to-trough fall in a target's cumulative profit, as a fraction of the peak. Expressed as
a fraction so it transfers across account sizes.
_Avoid_: max drawdown, DD

**Recent Form**:
A target's recent profit judged together with the friction it was earned under, rather than either
alone. Restricted to recent activity because a dead edge and an edge that never existed look
identical in lifetime numbers.

**Activity Recency**:
How recently a target last traded, measured against data collection time rather than read time.

**Track Record Length**:
The depth of a target's lifetime trading record, measured in the markets it has
traded. A record that cannot be measured is not a record: a wallet whose trade
series is unreadable is rejected, not guessed around. Depth is distinct from
recency — a long record can be stale, and a fresh one can be short.
_Avoid_: sample size, history length, trade count

### Simulation

**Simulated Copy Run**:
A replay of a target's transaction history through the follower's exact execution profile, returning
per-market outcomes for that specific bankroll.
_Avoid_: backtest, mock, sim

**Slippage Sensitivity Sweep**:
A set of simulated copy runs over the same target at increasing friction, holding everything else
fixed. The primary mirage test: genuine edge degrades gradually, a mirage inverts.

**Edge Retention**:
The fraction of a target's simulated profit that survives when friction is raised from the optimistic
assumption to the observed one. The headline ranking measure.

**Balance Miss**:
A target trade the simulation could not follow because the bankroll was fully deployed. Direct
evidence of capital exhaustion at a given account size.
_Avoid_: missed trade, skip

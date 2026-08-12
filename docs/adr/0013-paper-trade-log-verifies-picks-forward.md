# A forward Paper Trade Log is what verifies a pick, and what recalibrates friction

Every claim this screen makes is retrospective. Scores are computed from a wallet's own history,
Simulated Copy Runs replay that same history through the Copy Execution Profile, and Edge Retention
compares two replays of it. None of them produces a statement that can later be marked right or
wrong, so after twelve ADRs the project still has no evidence that a wallet it rated highly was
profitable to copy.

We therefore keep a Paper Trade Log: from now on, every trade a followed wallet makes is priced
against the live order book at the moment the follower's bot would have reacted, and the resulting
counterfactual order is appended to `app/data/paper_trades.jsonl`. No money moves. Weeks later the
log totals up into a realised profit or loss per wallet, which is the check nothing else in the
project performs.

Two arms are followed separately and never share a bankroll:

* **human_alpha** — wallets `overnight_scanner.py` classified from first-party Polymarket fills.
* **phase3_simulated** — the old pipeline's top picks, selected from third-party polycop.fun
  figures this project stopped trusting (ADR 0012). A comparison arm only; its selection numbers are
  not evidence, its forward results are.

A shared global cap would let whichever arm was polled first deny the other its capital, and the
difference between the arms would then measure poll ordering rather than wallet quality.

## The multiplier this log exists to re-derive

ADR 0001 set the Friction Realism Multiplier to 4.2 from three hand-logged fills and called it a
tracked estimate that every subsequent fill should revise. It was never revised. Meanwhile
`app/data/latency_slippage_profile.json` measured 0.0%–0.41% slippage, which read against the
leaderboard's 2% assumption would put the multiplier below 1. Both measurements can be right,
because they measure different things: the profile quotes a resting book against a hypothetical
order and sees **depth** friction only, while ADR 0001's fills were copies chasing a target who had
already traded and therefore carried **latency** friction on top.

Every record in the log splits the two and states its own multiplier sample, so
`execution.friction_calibration` re-derives 4.2 rather than re-asserting it, and each component can
be compared against the measurement it actually corresponds to. The first live fills recorded show
the split is real: ~5.4% latency against ~0% depth on a liquid market, a 2.7× sample rather than
either 4.2 or 0.4.

## Consequences

The log is append-only and its records are labelled with the Copy Execution Profile's fingerprint.
A changed profile makes earlier records incomparable to later ones, so the poller refuses to extend
a log started under different settings rather than producing totals that silently mix two
experiments.

Nothing is backfilled. A wallet seen for the first time has its cursor set to its newest trade and
its earlier history is not recorded, because the book that was standing then is gone and
reconstructing it would replace the measurement with exactly the kind of retrospective estimate this
log exists to replace. The cost is that the experiment only begins to produce evidence from the day
it is started, and a re-derived multiplier is not offered at all until 30 measured fills exist.

Trades the profile refuses are recorded too, with the reason. A log holding only fills would hide a
target whose behaviour the profile mostly cannot replicate, which is a verdict about that target
rather than an absence of data. In the first live pass, refusals outnumbered copies heavily — many
of them markets already resolved, but a large share genuinely outside the Copyable Trade Window,
which is itself a finding the score never surfaced.

A consequence of the window's design is that the Minimum Order Bump can never fire: the window's
lower bound is `venue_min / copy_ratio`, so any trade whose proportional copy would fall under the
venue minimum is refused before sizing. The over-exposure the bump would cause is counted as
`BELOW_COPYABLE_WINDOW` instead. A profile that widened the window below that bound would have to
reintroduce the bump.

## Considered options

Backfilling each wallet's history at first sight was rejected for the reason above: it produces far
more records far sooner, all of them priced against a book that has to be guessed, which is the
existing simulation wearing a different name.

Running a single pooled arm was rejected because the comparison between the first-party screen and
the pipeline it replaced is the question the log is best placed to answer, and pooling destroys it.

Waiting to record until real capital was committed was rejected because the point is to be wrong on
paper first. A verdict that costs nothing to be wrong about is the only kind this project can afford
to collect at the volume a calibration needs.

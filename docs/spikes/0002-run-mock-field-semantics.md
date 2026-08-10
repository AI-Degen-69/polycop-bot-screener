# Spike 0002 — what `run_mock` counts

**Date:** 2026-08-10
**Status:** resolved — the open question of spike 0001 is answered, and the wired formula was wrong.
**Probe wallet:** `0xeafc018ccbca46db203ba57c3e798ce0e84fe4c4` (the same whale spike 0001 used)

Spike 0001 left one question open: `intercepted`, `total_trades` and the decision log disagree with
each other, so the Copyable Window Share denominator could not be taken from any of them
uncritically. It asked for a reconciliation against a wallet whose trade count is known
independently. This spike does that reconciliation, and finds that the provisional formula was not
merely unverified — it was measuring the opposite of what it claimed.

## Method

`fetch_mode: "limit"` bounds how much of the target's history the simulation ingests, so sweeping
`limit` gives a controlled denominator without needing a second wallet. Runs were made at
`limit` 5, 10, 25, 50 and 4000, all other payload fields as spike 0001 recorded them. The full run
was then cross-tabulated by log `type` against log `action`, and each log message was matched
against the target-side verb it reports.

The independent trade count came out of the response itself: `market_stats[].target_trades` sums to
the number of log entries, from a different part of the payload than the log. That is the anchor.

## Findings

### One log entry is exactly one target trade

At `limit: 4000` the log holds 112 entries and `sum(market_stats[].target_trades)` is 112, across 44
markets. The two agree exactly. `len(logs)` is therefore the target's trade count for the fetched
window, and it is the only field in the response that is.

`limit` is not that count. It bounds the upstream transaction fetch, which includes rows the
simulator never issues a decision for — `limit: 50` produced 39 log entries, `limit: 25` produced 12.
Never read `limit` as a denominator.

### `type` is not the discriminator — `action` is

Spike 0001 read `type` and found 46 `INTERCEPT` entries "plus" 56 `SKIP_FILTER`. That framing was
the source of the confusion. `type` is coarse and mostly says `INTERCEPT`; `action` carries the
decision. The cross-tabulation is clean:

| `type` | `action` | count | what it is |
|---|---|---:|---|
| `INTERCEPT` | `SKIP_FILTER` | 56 | target BUY the execution profile refused |
| `INTERCEPT` | `INTERCEPT` | 47 | target SELL/REDEEM the simulation cannot follow |
| `BUY` | `BUY` | 4 | mirrored entry |
| `SELL` | `SELL` | 2 | mirrored exit |
| `REDEEM` | `REDEEM` | 2 | mirrored redemption |
| `WARNING` | `SKIP_CAP` | 1 | target BUY stopped by the risk cap, not by the window |

Every entry has both fields, and `action` partitions the log without overlap. Reading `type` double
counts, because `type: INTERCEPT` covers both the refusals and the ghost positions.

### `intercepted` means the opposite of "copied"

`intercepted` is 47 and the count of `action == "INTERCEPT"` is 47 — an exact match at every limit
tested (3, 4, 6, 18, 47 against limits 5, 10, 25, 50, 4000). So the field is well defined. What it
counts is the problem. Every one of those 47 entries reports a target SELL (26) or REDEEM (21) with
the message

> `Sim inventory is 0. [INTERCEPTED] Ghost Position.`

An intercepted decision is a target **exit the simulation could not mirror because it never held the
position** — the follower missed the entry, so the exit arrives against empty inventory. It is a
miss, not a copy. The docstring on the wired formula asserted the reverse: "an intercepted signal is
one the follower gets to mirror at all."

### `total_trades` counts markets, not trades

`total_trades` is 3. The markets with non-zero `sim_trades` number 3, and `sim_volume`,
`sim_invested` and the sim's PnL all come from those same three. Meanwhile
`sum(market_stats[].sim_trades)` is 8, which is exactly the mirrored log actions (4 BUY + 2 SELL +
2 REDEEM), and `finished_trades` holds 6 closes. Three different quantities, none of them
interchangeable:

- `total_trades` = 3 = distinct markets the simulation traded (`win_rate` of 33.3% is one winner of
  these three, confirming this is the unit the upstream win rate is computed over)
- `sum(sim_trades)` = 8 = individual orders the simulation executed
- `len(finished_trades)` = 6 = closed positions

The adapter exposed `total_trades` under the name `executed_trades`, which reads as the middle one
and is the least accurate of the three readings.

## The denominator

The glossary defines Copyable Window Share as "the share of a target's trades falling inside the
copyable trade window", and the Copyable Trade Window as a range of target trade **sizes** — a filter
that applies at entry. Exits are not admitted or refused by a size window; they follow whatever the
entry did. So the population is the target's BUY signals:

- denominator: log entries whose message reports a target BUY = 61 (56 `SKIP_FILTER` + 4 `BUY` +
  1 `SKIP_CAP`)
- numerator: those the window admitted = 5 (the 4 mirrored BUYs, plus the 1 `SKIP_CAP` — the window
  admitted that trade and the bankroll risk cap stopped it, which is Balance Miss's subject, not
  this metric's)

That is **5/61 ≈ 0.082**. The wired formula returned `47/112 ≈ 0.42` — it counted ghost positions as
copyable and divided by the exits as well as the entries. Both halves were wrong and both erred
generously, so the metric was awarding points to the wallets least able to be copied.

Two of the 56 refusals cite `Price ... out of bounds` rather than `Target size ... out of bounds`.
The price bounds are part of the same execution profile and are refusals of the same entry signal, so
they stay in the numerator's complement; splitting them out would need a separate metric and a
separate name.

## Consequences

- `calculate_copyable_window_share` is rewritten against `action` and the target-side verb.
- `parse_simulated_run_response` renames its keys to say what each one counts: `intercepted` becomes
  `ghost_exits`, `total_trades` becomes `traded_markets`, `total_decisions` becomes `target_trades`,
  and `mirrored_orders` is added for the count the old `executed_trades` name implied but never
  held.
- Any Copyable Window Share in a scan record written before this date is inflated and should be
  regenerated rather than compared against a new one.

## Notes

`total_markets` (44) equals `len(market_stats)`, and `intercepted` tracked `len(market_stats)` at the
smaller limits by coincidence of this wallet's history — it does not in the full run (47 against 44).

Raw responses are in the session scratchpad as `resp_5.json`, `resp_10.json`, `resp_25.json`,
`resp_50.json` and `resp_full_0xeafc018c.json`; the probe scripts are `probe_fields.py` and
`analyze_full.py` beside them.

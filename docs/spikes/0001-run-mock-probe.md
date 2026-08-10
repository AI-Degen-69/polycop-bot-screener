# Spike 0001 — `POST /api/run_mock` probe

**Date:** 2026-08-10
**Status:** resolved — endpoint verified, ADR 0002 is buildable as written.
**Probe wallet:** `0xeafc018ccbca46db203ba57c3e798ce0e84fe4c4`

This spike existed to unblock ADR 0002, which makes `run_mock` the source of the verdict despite the
endpoint never having been called. Three questions were asked. All three are answered.

## Answers

**Does it accept the payload without authentication?**
Yes. `HTTP 200` with no cookie, token, or API key. Only `Content-Type: application/json` was sent,
alongside `Origin` and `Referer` matching the copy-backtest page.

**What is the response shape?**
A single JSON object, 68.9 KB for this wallet. No job id, no polling — the simulation is synchronous.

**How long does a 4000-transaction job take?**
0.8 s wall clock. Roughly four hundred jobs per scan is therefore about five minutes serial, so
throttling is a courtesy constraint rather than a performance one.

## Request

The field list read from the page source is accepted verbatim. `start_time` and `end_time` accept
`null` under `fetch_mode: "limit"`; the four list fields accept empty arrays.

```json
{
  "wallet": "0x…", "fetch_mode": "limit", "limit": 4000,
  "start_time": null, "end_time": null,
  "copy_pct": 3, "slippage": 10, "capital": 100,
  "target_max_price": 0.95, "target_min_price": 0.05,
  "target_max_usd": 167, "target_min_usd": 33,
  "sim_max_per_token": 5, "sim_max_global": 100,
  "allowed_categories": [], "exclude_words": [], "blacklist": [], "whitelist": []
}
```

## Response

Twenty-nine top-level keys. The ones the screen needs:

| Key | Meaning for us |
|---|---|
| `sim_total_pnl` | Simulated Copy PnL — the quantity the sweep ranks on |
| `target_total_pnl` | Actual PnL, for the retention denominator sanity check |
| `max_drawdown` | Drawdown Depth, already simulated rather than inferred |
| `pl_ratio`, `win_rate` | copy-adjusted, replacing the leaderboard proxies |
| `winning_days` / `losing_days` / `flat_days` / `trading_days` | the real Daily Green Rate, which the leaderboard never supplied |
| `intercepted`, `total_trades` | inputs to Copyable Window Share — see the open question below |
| `final_balance`, `total_equity`, `position_value` | end-state reconciliation |

Four arrays carry the detail: `market_stats` (per-market, mirrors the page's table columns and adds
`sim_missed_amount` — the Balance Miss figure), `daily_data` (per-day equity, `cum_sim_pnl`,
`cum_target_pnl`, `daily_dd`), `finished_trades`, and `logs`.

`logs` is the reason a trade was or was not copied, one entry per decision, typed
`INTERCEPT` / `BUY` / `SELL` / `REDEEM` / `WARNING` with an `action` of `SKIP_FILTER` or `SKIP_CAP`
on the rejections. This is a direct read of where Tracking Error comes from, and it should be
retained rather than discarded on ingest.

## What the probe result itself says

The probe wallet is a whale, and the run is a clean demonstration of the thesis rather than a
disappointment. Against a $100 bankroll on the real execution profile it produced
`sim_total_pnl` of **−5.95** while `target_total_pnl` was **99,295.84**.

The log carries 102 decisions, of which 56 are `SKIP_FILTER` and one is `SKIP_CAP`, leaving 3
executed trades across 3 of 44 markets. Target invested $475,256 against $15,882 the simulation had
to skip. A wallet earning ninety-nine thousand dollars is, at this bankroll, a losing copy.

Copyable Window Share is therefore load-bearing and should be measured from the simulation rather
than estimated from trade-size distributions. And the tightened whale gate at `avg_invest > $200`
is, if anything, still loose.

## Slippage sensitivity sweep — verified, with one defect exposed

The endpoint honours `slippage`, and the curve is smooth and monotonic. Each run took 0.4 to 0.8 s.

| slippage | `sim_total_pnl` | `total_trades` | `intercepted` | `max_drawdown` |
|---:|---:|---:|---:|---:|
| 2% | −5.051 | 3 | 46 | 6.89 |
| 5% | −5.405 | 3 | 46 | 7.01 |
| 10% | −5.953 | 3 | 46 | 7.18 |
| 15% | −6.453 | 3 | 46 | 7.33 |

**Defect: edge retention is meaningless when PnL is negative.** Retention is defined as PnL at 10%
divided by PnL at 2%, read as "genuine edge decays gradually, a mirage inverts". Here it computes to
**1.179** — a number that reads as *better than perfect retention* for a wallet that loses money at
every slippage level, because dividing a larger loss by a smaller one exceeds one.

The spec must state the order explicitly: apply the reject-if-negative-at-10% gate **first**, and
compute retention only on wallets that survive it, where both terms are positive and the ratio means
what it claims. Retention must never be computed on a negative denominator.

## Open question for the spec — answered by spike 0002

**Resolved.** See `0002-run-mock-field-semantics.md`. The reconciliation found that `action`, not
`type`, partitions the log; that `intercepted` counts exits the follower *missed*; that
`total_trades` counts markets; and that `len(logs)` is the target's trade count. The question as
posed below is kept verbatim for the record.

`intercepted` is 46 while the log holds 46 `INTERCEPT` entries plus 56 `SKIP_FILTER` entries, and
`total_trades` is 3 against 4 `BUY` and 2 `SELL` log lines. Neither field is a plain count of the
target's trades, so the Copyable Window Share denominator cannot be taken from `intercepted`
uncritically. Resolve by reconciling the three against a wallet whose trade count is known
independently before wiring the metric.

## Notes

`fetch_mode: "limit"` with `limit: 4000` returned a wallet history spanning 26 trading days, so the
limit was not the binding constraint here and the 0.8 s figure is not an upper bound. Time a
high-volume wallet before fixing the throttle interval.

Raw request and response are in the session scratchpad as `probe.json` and `resp.json`.

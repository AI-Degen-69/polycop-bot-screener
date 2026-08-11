# PR Review: #34 — feat(screener): Simulated Verdict seam, paths fix, and Clear Data fix

**Reviewed**: 2026-08-11
**Author**: AI-Degen-69
**Branch**: feat/simulated-verdict-seam → main
**Decision**: CHANGES APPLIED (9 of 10 CodeRabbit findings fixed, 1 declined with reason)

## Summary

CodeRabbit raised 10 findings: 2 Major (data integrity), 4 Minor (functional
correctness / maintainability), 4 lint-level. Nine were valid against the
current code and are fixed here with regression coverage. One (CSS font-family
quoting) is declined because the fix would leave the file internally
inconsistent for no functional gain.

## Findings

### CRITICAL

None.

### HIGH

1. **`phase3_simulation_rank.py:61` — endpoint-failed cap sweeps inflated the
   backtested count.** `summarize_cap_upgrades` skipped a sweep only when
   `sweep[0]["error"]` was set, so a wallet whose cap levels all came back with
   `endpoint_failure=True` still incremented `cap_sweep_backtested`, and a
   failure at a wider level was ignored entirely. The denominator the upgrade
   rate is reported against therefore counted wallets with no valid cap
   measurement. **Fixed**: a sweep is skipped when any level carries `error` or
   `endpoint_failure`. Covered by
   `test_a_wallet_the_endpoint_failed_at_one_cap_is_not_counted`.

2. **`simulated_verdict.py:236` — every sweep exception was classified as an
   endpoint outage.** The fetch layer already converts a dead endpoint into
   `success: False`, which the sweep reports as `endpoint_failure`; nothing
   that raises past it says anything about the endpoint. A malformed
   `sim_total_pnl` therefore advanced the outage streak, and three such wallets
   stopped the scan and published triage fallbacks claiming an outage that was
   not happening. **Fixed**: a raised sweep is a data/code fault —
   `endpoint_failure=False`, no row, streak untouched. Covered by
   `test_a_sweep_that_raises_is_not_an_endpoint_failure`,
   `test_a_malformed_response_does_not_start_the_outage_fallback`, and
   `test_a_sweep_exception_does_not_degrade_the_scan` (which replaces the test
   that pinned the old contract).

### MEDIUM

3. **`copy_execution_profile.py:154` — a non-positive bankroll produced a cap
   profile that did not bind.** With `bankroll_usd <= 0` the share fell back to
   `1.0` while `max_single_position_usd` stayed zero or negative, so the derived
   profile was labelled with a cap it never applied. **Fixed**: `with_position_cap`
   raises `ValueError` for a non-positive bankroll; the `1.0` fallback is gone.
   Covered by `test_a_non_positive_bankroll_cannot_derive_a_cap_profile` (zero
   and negative).

4. **`run_mock_client.py:11` — `copy_pct` defaulted to a literal 3.0 while the
   window and cap fields came from the profile.** A caller passing a 5% profile
   got a payload that simulated a 3% copy ratio against the 5% profile's
   window. **Fixed**: `copy_pct` is `Optional[float] = None` and derives from
   `profile.copy_ratio` when not given; `fetch_simulated_copy_run` no longer
   passes it explicitly.

5. **`serve_web_app.py:203` — a corrupt scan file returned 400.**
   `json.JSONDecodeError` subclasses `ValueError`, so a truncated file on disk
   reported a client error for a valid request. **Fixed**: decode failures are
   caught before the client-error branch and return 500.

6. **`score_wallets.py:260,309` — the generated "zero" text used `<` where the
   engine scores zero at the anchor.** `_shape_ramp_linear` returns `0.0` at
   `value <= zero_at`, so the Daily Green Rate and Markets Sample rows
   disagreed with the scored value at exactly 40% and exactly 25. **Fixed**:
   both now read `<=`, matching the Edge-to-Friction and Profit/Loss Ratio
   rows. `tools/scoring_docs.py generate` re-run; README.md and .agents/AGENTS.md
   updated.

### LOW

7-9. **E741 ambiguous `l` in three test files.** **Fixed**: renamed to `level`
in `test_cap_backtest_endpoint.py`, `test_simulated_verdict.py`, and
`test_simulation_rank.py`.

10. **`styles.css:1523` — `font-family: 'Outfit'` quoted.** **Declined.** The
quoting is the file's convention: 28 other declarations quote `'Outfit'` and
`'Space Mono'`. Unquoting only the line inside this diff makes the file
internally inconsistent, and unquoting all of them is 28 lines of churn
unrelated to this PR. Worth a separate stylistic pass if the repo adopts
stylelint in CI.

## Validation Results

| Check | Result |
|---|---|
| Type check | Skipped (no typechecker configured) |
| Lint | Skipped (ruff not installed locally); E741 sites verified gone by grep |
| Tests | Pass — 297 passed, 130 subtests passed |
| Build | N/A (no build step) |
| Scoring docs sync | Pass (`tools/scoring_docs.py` check clean after regenerate) |

## Files Reviewed

| File | Change |
|---|---|
| app/src/execution/copy_execution_profile.py | Modified |
| app/src/pipeline/phase3_simulation_rank.py | Modified |
| app/src/pipeline/run_mock_client.py | Modified |
| app/src/screener/score_wallets.py | Modified |
| app/src/screener/simulated_verdict.py | Modified |
| app/src/server/serve_web_app.py | Modified |
| tests/test_cap_backtest_endpoint.py | Modified |
| tests/test_copy_execution_profile.py | Modified |
| tests/test_simulated_verdict.py | Modified |
| tests/test_simulation_rank.py | Modified |
| README.md | Regenerated |
| .agents/AGENTS.md | Regenerated |
| app/web/css/styles.css | Unchanged (finding declined) |

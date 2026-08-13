# QA Report — polycop-bot-screener (2026-08-11)

**Scope:** Clear Data button + Scan Leaderboard button, live on http://localhost:8050
**Tier:** Standard (critical + high + medium)
**Health score: 84/100 → 98/100**

## Issues found

### ISSUE-001 — Clear Data button appears dead (CRITICAL, fixed)

**Repro:** Click "Clear Data" → approve confirm → grid stays full. Network log shows
`/api/clear_data → 200` followed by `/api/feed/v1 → 200` with the *same 48 wallets*.

**Root cause:** `reset_data_cache()` deleted only `phase1_scraped_wallets.json` +
`phase2_verified_targets.json` — files the page never reads. The page loads the
**phase3 feed** (`phase3_simulated_targets.json` via `/api/feed/v1`), which survived,
so `loadDataset()` refilled the grid from the untouched feed. The button deleted
nothing visible. A test (`test_reset_data_cache_deletes_only_the_pre_feed_phase_files`)
had pinned this "feed must survive a reset" behavior.

**Fix (`64b9247`):** `reset_data_cache()` now deletes the phase3 feed too. The feed
endpoint 404s on a missing file (already handled by `_feed_projection_body` →
`os.stat` OSError → None), the UI renders its designed empty state ("No Cached Scan
Data Found"), and the next `screen.py` launch re-runs the pipeline from scratch
(screen.py's `elif force_rescan or not os.path.exists(VERIFIED_DATA_FILE)` branch).
Pinned test renamed to `TestACacheResetClearsTheWholeDataset` asserting all three
files are removed.

**Verified live:** before → 268 cards / 48 verified; after → empty-state message,
stats 0/0. Server log: `clear_data → 200`, `feed/v1 → 404`.

### ISSUE-002 — Scan button: NOT broken (verified working)

The user bet the scan didn't work either. It does — it's just an ~11-minute
synchronous pipeline with no progress feedback beyond a "Scanning…" button.

**Verified:** clicked the button → button entered "Scanning PolyCop Leaderboard…"
(disabled) → phase1/phase2 rewrote → phase3 feed republished at 02:34:20 → UI
refilled to 97 scanned / 48 verified with a fresh cap-upgrade summary.

## Fix summary

| Issue | Severity | Status | Commit |
|---|---|---|---|
| Clear Data does nothing visible | Critical | verified | `64b9247` |
| Scan appears dead | — | verified working (slow, not broken) | — |

**Tests:** full suite green — 294 passed + 130 subtests (incl. updated paths tests).
**Health score:** 84 → 98 (Clear Data functional; only remaining low-severity gap is
no progress bar during the ~11-min scan).

## Deferred / notes

- Scan progress feedback (spinner with elapsed time / phase indicator) would help;
  the button currently blocks ~11 minutes with only "Scanning…" text.
- `endpoint_cap_backtest` would 500 if invoked while no feed exists (unreachable
  from the UI post-clear, low priority).

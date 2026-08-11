# The page reads a compact versioned feed projection, not the raw scan file

The page loaded `phase3_simulated_targets.json` over HTTP on every visit: a
~5 MB scan for 48 wallets, of which **92% was `skip_reasons`** — the
simulation's full decision log, 4.4 MB of refusals the page only ever shows
12 rows of. `balance_miss_details` added another 195 KB, also rendered 12
rows at a time. The page fetched the whole audit record to draw a table.

## The decision

**The page's only read path is `/api/feed/v1`, a server-side projection of
the raw scan file; the raw file remains the audit/cache record, untouched.**

- **One compact contract.** The endpoint projects the scan onto an explicit
  whitelist of the wallet fields the page renders, and stamps
  `feed_version: 1` on the payload. The page fetches this, and nothing else;
  `/api/rescan` returns the same projection, so a finished scan fills the
  grid through the one path that knows how to normalise it.
- **Decision logs are capped at 12 rows with true totals.** `skip_reasons`
  and `balance_miss_details` ship as the first 12 entries plus
  `skip_reasons_total` / `balance_miss_total`, keeping the page's
  "…and N more" lines honest without shipping the log. The raw file keeps
  the full log for the audit record.
- **Server-side projection, cached on the source file's mtime.** The
  projection is computed from the same file screen.py and the tests read,
  and cached keyed on `(mtime, size)` so a 5 MB re-parse happens once per
  written scan, not once per request. Writing the cached body before the
  key prevents a concurrent reader from serving a stale scan under a fresh
  key.
- **The raw file stays where it was.** `screen.py`'s presence check, the
  tests' fixtures, and the audit record keep reading
  `phase3_simulated_targets.json` unchanged. The projection is a view, not a
  second source of truth.

## Why not the alternatives

- **Leave the page fetching the raw file** was the status quo: 5 MB for a
  table. The page's rendering surface is ~46 KB of grid fields; the other
  99% of the payload exists for one modal at a time.
- **Truncate `skip_reasons` at the pipeline source** would shrink the file
  itself, but the pipeline's full decision log is the audit record (and the
  source of the "…and N more" count). Truncation at the source destroys
  what the raw file exists to preserve.
- **Grid-only feed plus an on-demand per-wallet detail endpoint** (feed v2)
  was measured and rejected. The modal-only fields — `cap_sweep`,
  `breakdown`/labels/points, `radar_labels` and the two capped lists — are
  240 KB of the 311 KB feed (77%), so a grid-only projection is 71 KB: a
  further 4.4×, not the headline number it looks like. The measured
  initial-load prize is ~10 ms (the v1 feed fetches in ~14 ms; 71 KB would
  fetch in ~4 ms), and the modal is the page's primary interaction —
  making every open a second fetch with a loading state and a stale-response
  guard, for a localhost tool where the win is already 15.6×, is a bad
  trade. If scan growth ever makes the feed heavy (a 200-wallet scan
  would be ~1.3 MB), the answer is paginating the grid, not shipping modal
  data on demand.

## Consequences

- The page ships ~311 KB instead of ~4.8 MB over the wire (15.6× on the
  current 48-wallet scan); the feed's shape is a contract, versioned, so a
  future change is a new version rather than a silent break.
- A wallet field the page starts rendering must be added to the projection
  whitelist — the drift guard in `test_web_app_cutover.py` fails if the two
  disagree. A field the page stops reading is dropped from the feed with the
  version bump.
- The capped lists are a new honesty seam: absent stays absent (ADR 0007),
  and a zero total means a genuinely empty log — the page renders the
  "bankroll held"/"nothing skipped" reading only when the total is zero.
- `MODAL_LIST_CAP` (12) lives in `feed_projection.py` and is mirrored by the
  page's slice; changing it touches both sides, which the tests and the
  cross-referencing comments make visible.

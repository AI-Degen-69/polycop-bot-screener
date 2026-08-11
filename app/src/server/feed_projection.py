#!/usr/bin/env python3
"""The compact, versioned feed projection the page fetches.

The pipeline writes one file — phase3_simulated_targets.json, ~6 MB for a
typical scan — and the page used to fetch it in full even though 92% of it is
`skip_reasons`, a decision log the page only ever shows 12 rows of. This
module projects that file through the API boundary: the raw file stays the
single source of truth (screen.py, the tests and the audit record read it),
and the page gets exactly the fields it renders and nothing it does not.

Contract: `feed_version` 1. A page that speaks version 1 reads these keys; a
page that speaks version 2 must not be pointed at this endpoint. Bump
FEED_VERSION when the shape changes, and let the tests in
tests/test_feed_projection.py document what each version carried.
"""

# The page renders at most this many decision-log and balance-miss rows, then
# says "…and N more" — so the projection carries the capped rows plus the true
# total, and the raw file keeps the full log for the audit record.
MODAL_LIST_CAP = 12

FEED_VERSION = 1

# The per-wallet fields the page reads. Whitelisted explicitly so a field the
# pipeline adds later cannot silently balloon the feed: it enters the contract
# only when the page starts rendering it (and the version is bumped). The two
# heavy lists are handled separately below, capped with totals.
WALLET_FIELDS = (
    "address",
    "name",
    "triage_copyability_score",
    "triage_grade",
    "metrics",
    "verdict_source",
    "tier",
    "edge_retention",
    "simulated_copy_pnl_10",
    "simulated_daily_green_rate",
    "simulated_max_drawdown",
    "copyable_window_share",
    "scan_rank",
    "activity",
    "is_hidden_gem",
    "bankroll_analysis",
    "cap_sweep",
    "breakdown",
    "breakdown_labels",
    "breakdown_points",
    "radar_labels",
)

# The capped lists, mapped to the key that carries their true total.
CAPPED_LISTS = (
    ("skip_reasons", "skip_reasons_total"),
    ("balance_miss_details", "balance_miss_total"),
)

# The top-level summary fields the page reads. `feed_version` and
# `simulated_targets` are always present; these are carried through when the
# scan produced them.
SUMMARY_FIELDS = (
    "timestamp",
    "copy_execution_profile",
    "reduced_confidence",
    "fallback_reason",
    "total_targets_evaluated",
    "simulated_survivors_count",
    "cap_sweep_levels",
    "cap_sweep_baseline_cap",
    "cap_sweep_backtested",
    "cap_sweep_upgrades",
)


def project_wallet(wallet: dict) -> dict:
    """Project one wallet onto the v1 feed contract.

    Keeps only the fields the page reads, and caps the two decision-log lists
    at MODAL_LIST_CAP rows with their true totals alongside. A fallback wallet
    without the lists projects to an empty list and a zero total — an absent
    log is not a log of zero entries (ADR 0007).
    """
    projected = {field: wallet[field] for field in WALLET_FIELDS if field in wallet}
    for key, total_key in CAPPED_LISTS:
        entries = wallet.get(key) or []
        projected[key] = entries[:MODAL_LIST_CAP]
        projected[total_key] = len(entries)
    return projected


def project_feed(data: dict) -> dict:
    """Project the raw Phase 3 payload onto the v1 feed contract.

    The raw payload is left untouched — this returns a new dict, so the cache
    and the audit file can never alias each other's lists.
    """
    projected = {
        "feed_version": FEED_VERSION,
        "simulated_targets": [
            project_wallet(w) for w in data.get("simulated_targets", [])
        ],
    }
    for field in SUMMARY_FIELDS:
        if field in data:
            projected[field] = data[field]
    return projected

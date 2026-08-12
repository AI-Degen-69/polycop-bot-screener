#!/usr/bin/env python3
"""How recently a wallet traded, expressed as bands a reader can scan.

Activity Recency answers a different question from the audit score: not whether
this wallet is worth copying, but whether its track record is still live. The
bands are the vocabulary that answer is given in.

Building the block itself moved to `pipeline.first_party_adapter` at the
ADR 0012 cutover, because recency is now measured from the wallet's own fills
rather than parsed out of an aggregator's `last_active` string and rolling
per-day series. What remains here is what both readers share: the band
definitions, and the counting of a scan across them.
"""

# (bucket key, human label, upper bound in hours). Ordered fastest-first.
ACTIVITY_BUCKETS = (
    ("live", "Live (< 6h)", 6.0),
    ("today", "Today (< 24h)", 24.0),
    ("d3", "Last 3 days", 72.0),
    ("d7", "Last 7 days", 168.0),
    ("stale", "Stale (7d+)", float("inf")),
)


def bucket_for_hours(hours):
    """Map an age in hours to an activity bucket key.

    An age nobody could measure is "unknown", not "stale": a wallet whose last
    fill could not be read has not been shown to have gone quiet.
    """
    if hours is None:
        return "unknown"
    for key, _label, upper in ACTIVITY_BUCKETS:
        if hours < upper:
            return key
    return "stale"


def summarize_buckets(activities):
    """Count activity buckets across a list of activity blocks."""
    counts = {key: 0 for key, _label, _upper in ACTIVITY_BUCKETS}
    counts["unknown"] = 0
    for act in activities:
        key = act.get("activity_bucket", "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts

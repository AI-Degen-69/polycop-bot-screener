#!/usr/bin/env python3
"""Recent-activity enrichment for PolyCop leaderboard profiles.

The PolyCop leaderboard API returns a `last_active` wall-clock stamp
("YYYY-MM-DD HH:MM", UTC) plus a rolling `daily_stats_json` window of
per-day volume / trade counts. Neither feeds the 100-point audit score -
they answer a different question: is this trader still trading right now,
or is the track record stale?
"""
import datetime
import json

LAST_ACTIVE_FORMAT = "%Y-%m-%d %H:%M"

# (bucket key, human label, upper bound in hours). Ordered fastest-first.
ACTIVITY_BUCKETS = (
    ("live", "Live (< 6h)", 6.0),
    ("today", "Today (< 24h)", 24.0),
    ("d3", "Last 3 days", 72.0),
    ("d7", "Last 7 days", 168.0),
    ("stale", "Stale (7d+)", float("inf")),
)


def parse_timestamp(value):
    """Parse a PolyCop timestamp string into a naive UTC datetime, or None."""
    if not value:
        return None
    text = str(value).strip().replace("T", " ").replace("Z", "")
    for fmt in (LAST_ACTIVE_FORMAT, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def bucket_for_hours(hours):
    """Map an age in hours to an activity bucket key."""
    if hours is None:
        return "unknown"
    for key, _label, upper in ACTIVITY_BUCKETS:
        if hours < upper:
            return key
    return "stale"


def _load_daily_stats(profile):
    raw = profile.get("daily_stats_json")
    if isinstance(raw, list):
        return raw
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def compute_activity(profile, now=None):
    """Build the activity block for a single raw leaderboard profile.

    `now` is the reference instant (naive UTC) - normally the scrape
    timestamp, so a cached dataset reports ages relative to when it was
    captured rather than when it happens to be viewed.
    """
    last_active_raw = profile.get("last_active")
    last_active = parse_timestamp(last_active_raw)

    hours_since = None
    if last_active is not None and now is not None:
        hours_since = max(0.0, (now - last_active).total_seconds() / 3600.0)

    daily = _load_daily_stats(profile)
    cutoff_7d = (now.date() - datetime.timedelta(days=6)) if now is not None else None

    trades_7d = 0
    volume_7d = 0.0
    active_days_7d = 0
    green_days_7d = 0

    for entry in daily:
        if not isinstance(entry, dict):
            continue
        day = parse_timestamp(entry.get("date"))
        if cutoff_7d is not None and (day is None or day.date() < cutoff_7d):
            continue
        try:
            trades = int(entry.get("trades", 0) or 0)
        except (ValueError, TypeError):
            trades = 0
        try:
            volume = float(entry.get("volume", 0.0) or 0.0)
        except (ValueError, TypeError):
            volume = 0.0
        try:
            pnl = float(entry.get("actual_pnl", 0.0) or 0.0)
        except (ValueError, TypeError):
            pnl = 0.0

        trades_7d += trades
        volume_7d += volume
        if trades > 0 or volume > 0:
            active_days_7d += 1
        if pnl > 0:
            green_days_7d += 1

    return {
        "last_active": last_active_raw,
        "hours_since_active": round(hours_since, 2) if hours_since is not None else None,
        "activity_bucket": bucket_for_hours(hours_since),
        "trades_7d": trades_7d,
        "volume_7d": round(volume_7d, 2),
        "active_days_7d": active_days_7d,
        "green_days_7d": green_days_7d,
        "trading_days": int(profile.get("trading_days", 0) or 0),
    }


def summarize_buckets(activities):
    """Count activity buckets across a list of activity blocks."""
    counts = {key: 0 for key, _label, _upper in ACTIVITY_BUCKETS}
    counts["unknown"] = 0
    for act in activities:
        key = act.get("activity_bucket", "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts

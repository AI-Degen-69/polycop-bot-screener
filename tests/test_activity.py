#!/usr/bin/env python3
import datetime
import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "app", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from screener.activity import (
    bucket_for_hours,
    compute_activity,
    parse_timestamp,
    summarize_buckets,
)

NOW = datetime.datetime(2026, 8, 9, 18, 0)


def daily_stats(entries):
    return json.dumps(entries)


class TestParseTimestamp(unittest.TestCase):

    def test_leaderboard_format(self):
        self.assertEqual(parse_timestamp("2026-08-09 02:44"), datetime.datetime(2026, 8, 9, 2, 44))

    def test_iso_z_format(self):
        self.assertEqual(parse_timestamp("2026-08-09T18:19:29Z"), datetime.datetime(2026, 8, 9, 18, 19, 29))

    def test_date_only(self):
        self.assertEqual(parse_timestamp("2026-08-09"), datetime.datetime(2026, 8, 9))

    def test_garbage_returns_none(self):
        self.assertIsNone(parse_timestamp("not-a-date"))
        self.assertIsNone(parse_timestamp(""))
        self.assertIsNone(parse_timestamp(None))


class TestBuckets(unittest.TestCase):

    def test_bucket_boundaries(self):
        self.assertEqual(bucket_for_hours(0.0), "live")
        self.assertEqual(bucket_for_hours(5.99), "live")
        self.assertEqual(bucket_for_hours(6.0), "today")
        self.assertEqual(bucket_for_hours(23.9), "today")
        self.assertEqual(bucket_for_hours(24.0), "d3")
        self.assertEqual(bucket_for_hours(71.9), "d3")
        self.assertEqual(bucket_for_hours(72.0), "d7")
        self.assertEqual(bucket_for_hours(167.9), "d7")
        self.assertEqual(bucket_for_hours(168.0), "stale")

    def test_unknown_when_missing(self):
        self.assertEqual(bucket_for_hours(None), "unknown")

    def test_summarize_counts_each_bucket_once(self):
        counts = summarize_buckets([
            {"activity_bucket": "live"},
            {"activity_bucket": "live"},
            {"activity_bucket": "stale"},
            {},
        ])
        self.assertEqual(counts["live"], 2)
        self.assertEqual(counts["stale"], 1)
        self.assertEqual(counts["unknown"], 1)
        self.assertEqual(counts["today"], 0)


class TestComputeActivity(unittest.TestCase):

    def test_hours_since_active(self):
        act = compute_activity({"last_active": "2026-08-09 12:00"}, now=NOW)
        self.assertEqual(act["hours_since_active"], 6.0)
        self.assertEqual(act["activity_bucket"], "today")

    def test_future_timestamp_clamps_to_zero(self):
        """Clock skew between PolyCop and the scrape must not yield negative age."""
        act = compute_activity({"last_active": "2026-08-10 00:00"}, now=NOW)
        self.assertEqual(act["hours_since_active"], 0.0)
        self.assertEqual(act["activity_bucket"], "live")

    def test_missing_last_active_is_unknown(self):
        act = compute_activity({}, now=NOW)
        self.assertIsNone(act["hours_since_active"])
        self.assertEqual(act["activity_bucket"], "unknown")

    def test_seven_day_rollup(self):
        profile = {
            "last_active": "2026-08-09 02:44",
            "trading_days": 26,
            "daily_stats_json": daily_stats([
                {"date": "2026-08-09", "volume": 100.0, "trades": 2, "actual_pnl": 5.0},
                {"date": "2026-08-08", "volume": 50.0, "trades": 1, "actual_pnl": -3.0},
                {"date": "2026-08-05", "volume": 0.0, "trades": 0, "actual_pnl": 0.0},
                # Outside the 7d window - must be excluded.
                {"date": "2026-07-20", "volume": 9999.0, "trades": 40, "actual_pnl": 500.0},
            ]),
        }
        act = compute_activity(profile, now=NOW)
        self.assertEqual(act["trades_7d"], 3)
        self.assertEqual(act["volume_7d"], 150.0)
        self.assertEqual(act["active_days_7d"], 2)
        self.assertEqual(act["green_days_7d"], 1)
        self.assertEqual(act["trading_days"], 26)

    def test_accepts_daily_stats_as_list(self):
        profile = {"daily_stats_json": [{"date": "2026-08-09", "volume": 10.0, "trades": 1, "actual_pnl": 1.0}]}
        act = compute_activity(profile, now=NOW)
        self.assertEqual(act["trades_7d"], 1)

    def test_malformed_daily_stats_is_tolerated(self):
        act = compute_activity({"daily_stats_json": "{not json"}, now=NOW)
        self.assertEqual(act["trades_7d"], 0)
        self.assertEqual(act["active_days_7d"], 0)


if __name__ == "__main__":
    unittest.main()

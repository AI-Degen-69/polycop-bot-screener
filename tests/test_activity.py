#!/usr/bin/env python3
"""The activity bands and the counting of a scan across them.

The block-building half of this module moved to `first_party_adapter` at the
ADR 0012 cutover, and its tests moved with it. What is left is the vocabulary
both readers share, and the one property that matters most about it: an age
nobody could measure is unknown rather than stale.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from screener.activity import ACTIVITY_BUCKETS, bucket_for_hours, summarize_buckets


class TestBucketBoundaries(unittest.TestCase):
    def test_each_band_claims_the_hours_below_its_bound(self):
        self.assertEqual(bucket_for_hours(0.0), "live")
        self.assertEqual(bucket_for_hours(5.9), "live")
        self.assertEqual(bucket_for_hours(6.0), "today")
        self.assertEqual(bucket_for_hours(23.9), "today")
        self.assertEqual(bucket_for_hours(24.0), "d3")
        self.assertEqual(bucket_for_hours(71.9), "d3")
        self.assertEqual(bucket_for_hours(72.0), "d7")
        self.assertEqual(bucket_for_hours(167.9), "d7")
        self.assertEqual(bucket_for_hours(168.0), "stale")

    def test_an_unmeasurable_age_is_unknown_not_stale(self):
        """A wallet whose last fill could not be read has not been shown to
        have gone quiet, and reading it as stale would reject it for a gap in
        our data rather than a gap in its trading."""
        self.assertEqual(bucket_for_hours(None), "unknown")

    def test_the_bands_are_ordered_fastest_first(self):
        bounds = [upper for _key, _label, upper in ACTIVITY_BUCKETS]
        self.assertEqual(bounds, sorted(bounds))


class TestSummarizeBuckets(unittest.TestCase):
    def test_every_band_is_present_even_at_zero(self):
        counts = summarize_buckets([])
        for key, _label, _upper in ACTIVITY_BUCKETS:
            self.assertIn(key, counts)
        self.assertIn("unknown", counts)
        self.assertEqual(sum(counts.values()), 0)

    def test_a_scan_is_counted_across_the_bands(self):
        counts = summarize_buckets([
            {"activity_bucket": "live"},
            {"activity_bucket": "live"},
            {"activity_bucket": "stale"},
        ])
        self.assertEqual(counts["live"], 2)
        self.assertEqual(counts["stale"], 1)
        self.assertEqual(counts["today"], 0)

    def test_a_block_with_no_bucket_counts_as_unknown(self):
        self.assertEqual(summarize_buckets([{}])["unknown"], 1)


if __name__ == "__main__":
    unittest.main()

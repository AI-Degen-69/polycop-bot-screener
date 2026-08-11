#!/usr/bin/env python3
"""The compact v1 feed projection: what the page gets, and nothing more.

The pipeline writes one file — phase3_simulated_targets.json, ~6 MB for a
typical scan — and the page used to fetch it in full even though 92% of it is
`skip_reasons`, a decision log the page only ever shows 12 rows of. These
tests pin the projection's contract: the whitelist of wallet fields the page
reads, the 12-row caps with true totals, and the /api/feed/v1 HTTP behaviour.
The raw file is untouched — screen.py, the tests and the audit record still
read it. Loopback only, so the endpoint tests are CI-safe.
"""
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

import server.serve_web_app as serve_web_app  # noqa: E402
from server.feed_projection import FEED_VERSION, MODAL_LIST_CAP, project_feed  # noqa: E402
from server.serve_web_app import PolyCopScreenerWebHandler  # noqa: E402


def _wallet(addr, **overrides):
    wallet = {
        "address": addr,
        "name": "Trader",
        "triage_copyability_score": 85.0,
        "triage_grade": "A",
        "metrics": {
            "copy_pnl": 12.5, "polycop_site_score": 88, "r20_win_rate": 60,
            "pl_ratio": 1.2, "pnl_vol_ratio": 5.0, "markets": 30,
            "avg_invest": 50.0, "buy_price": 0.6,
        },
        "verdict_source": "simulation",
        "tier": "A-Tier (Strong Copy Target)",
        "edge_retention": 0.75,
        "simulated_copy_pnl_10": 4.2,
        "simulated_daily_green_rate": 0.6,
        "simulated_max_drawdown": -0.2,
        "copyable_window_share": 0.5,
        "scan_rank": 1,
        "activity": {"hours_since_active": 2.5, "trades_7d": 12},
        "is_hidden_gem": False,
        "bankroll_analysis": {"min_target_order_floor_usd": 5.0},
        "cap_sweep": [{"cap_usd": 5.0, "tier": "A-Tier (Strong Copy Target)"}],
        "breakdown": {"p1": 8.0},
        "breakdown_labels": {"p1": "Param 1"},
        "breakdown_points": {"p1": 10},
        "radar_labels": {"p1": "Param 1"},
        "skip_reasons": [{"action": "SKIP_FILTER", "msg": "refused"}] * 20,
        "balance_miss_details": [{"market": "Will X hit 1", "amount": 3.0}] * 20,
        # Fields the page does not read: the projection must drop them.
        "pnl_by_slippage_level": {"2.0": 1.0},
        "simulated_trading_days": 30,
    }
    wallet.update(overrides)
    return wallet


def _feed(targets):
    return {
        "timestamp": "2026-01-01T00:00:00Z",
        "copy_execution_profile": {"bankroll_usd": 100.0, "fingerprint": "abc"},
        "reduced_confidence": False,
        "fallback_reason": None,
        "total_targets_evaluated": len(targets),
        "simulated_survivors_count": len(targets),
        "cap_sweep_levels": [5.0, 10.0, 15.0, 20.0],
        "cap_sweep_baseline_cap": 5.0,
        "cap_sweep_backtested": len(targets),
        "cap_sweep_upgrades": [{"cap_usd": 10.0, "upgrades": 1}],
        "simulated_targets": targets,
    }


class TestProjectFeedContract(unittest.TestCase):
    def test_the_version_is_stamped(self):
        out = project_feed(_feed([_wallet("0xaaa")]))
        self.assertEqual(out["feed_version"], FEED_VERSION)

    def test_fields_the_page_does_not_read_are_dropped(self):
        out = project_feed(_feed([_wallet("0xaaa")]))
        wallet = out["simulated_targets"][0]
        self.assertNotIn("pnl_by_slippage_level", wallet)
        self.assertNotIn("simulated_trading_days", wallet)

    def test_every_field_the_page_reads_is_carried(self):
        out = project_feed(_feed([_wallet("0xaaa")]))
        wallet = out["simulated_targets"][0]
        for field in (
            "address", "name", "triage_copyability_score", "triage_grade",
            "metrics", "verdict_source", "tier", "edge_retention",
            "simulated_copy_pnl_10", "simulated_daily_green_rate",
            "simulated_max_drawdown", "copyable_window_share", "scan_rank",
            "activity", "is_hidden_gem", "bankroll_analysis",
            "cap_sweep", "breakdown", "breakdown_labels",
            "breakdown_points", "radar_labels",
        ):
            with self.subTest(field=field):
                self.assertIn(field, wallet)
        self.assertEqual(wallet["metrics"]["copy_pnl"], 12.5)

    def test_the_decision_lists_are_capped_at_twelve_with_true_totals(self):
        out = project_feed(_feed([_wallet("0xaaa")]))
        wallet = out["simulated_targets"][0]
        self.assertEqual(len(wallet["skip_reasons"]), MODAL_LIST_CAP)
        self.assertEqual(wallet["skip_reasons_total"], 20)
        self.assertEqual(len(wallet["balance_miss_details"]), MODAL_LIST_CAP)
        self.assertEqual(wallet["balance_miss_total"], 20)

    def test_a_wallet_without_the_lists_gets_empty_caps_and_zero_totals(self):
        fallback = _wallet("0xbbb")
        fallback.pop("skip_reasons", None)
        fallback.pop("balance_miss_details", None)
        out = project_feed(_feed([fallback]))
        wallet = out["simulated_targets"][0]
        self.assertEqual(wallet["skip_reasons"], [])
        self.assertEqual(wallet["skip_reasons_total"], 0)
        self.assertEqual(wallet["balance_miss_details"], [])
        self.assertEqual(wallet["balance_miss_total"], 0)

    def test_the_summary_fields_are_carried_through(self):
        out = project_feed(_feed([_wallet("0xaaa")]))
        for field in (
            "timestamp", "copy_execution_profile", "reduced_confidence",
            "fallback_reason", "total_targets_evaluated",
            "simulated_survivors_count", "cap_sweep_levels",
            "cap_sweep_baseline_cap", "cap_sweep_backtested",
            "cap_sweep_upgrades",
        ):
            with self.subTest(field=field):
                self.assertIn(field, out)
        self.assertEqual(out["cap_sweep_upgrades"][0]["upgrades"], 1)

    def test_the_raw_payload_is_not_mutated(self):
        feed = _feed([_wallet("0xaaa")])
        before = json.dumps(feed, sort_keys=True)
        project_feed(feed)
        self.assertEqual(json.dumps(feed, sort_keys=True), before)


class TestFeedEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), PolyCopScreenerWebHandler
        )
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        # A fresh temp data dir and a cold projection cache per test, so tests
        # never see each other's scans.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        serve_web_app._feed_cache["key"] = None

    def _write_feed(self, feed):
        with open(
            os.path.join(self._tmp.name, "phase3_simulated_targets.json"),
            "w", encoding="utf-8",
        ) as f:
            json.dump(feed, f)

    def _get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_feed_v1_serves_the_compact_projection(self):
        self._write_feed(_feed([_wallet("0xaaa"), _wallet("0xbbb")]))
        with mock.patch.object(serve_web_app, "DATA_DIR", self._tmp.name):
            status, body = self._get("/api/feed/v1")
        self.assertEqual(status, 200)
        self.assertEqual(body["feed_version"], FEED_VERSION)
        self.assertEqual(len(body["simulated_targets"]), 2)
        self.assertEqual(len(body["simulated_targets"][0]["skip_reasons"]), 12)
        self.assertEqual(body["simulated_targets"][0]["skip_reasons_total"], 20)

    def test_feed_v1_404s_when_no_scan_has_run(self):
        with mock.patch.object(serve_web_app, "DATA_DIR", self._tmp.name):
            status, body = self._get("/api/feed/v1")
        self.assertEqual(status, 404)
        self.assertIn("error", body)

    def test_feed_reprojects_when_the_source_file_changes(self):
        # The mtime-keyed cache must never serve a stale scan after a rewrite.
        self._write_feed(_feed([_wallet("0xaaa")]))
        with mock.patch.object(serve_web_app, "DATA_DIR", self._tmp.name):
            status, body = self._get("/api/feed/v1")
            self.assertEqual(len(body["simulated_targets"]), 1)

            self._write_feed(_feed([_wallet("0xaaa"), _wallet("0xbbb")]))
            os.utime(
                os.path.join(self._tmp.name, "phase3_simulated_targets.json"), None
            )
            status, body = self._get("/api/feed/v1")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["simulated_targets"]), 2)

    def test_rescan_returns_the_compact_projection(self):
        self._write_feed(_feed([_wallet("0xaaa")]))
        feed_path = os.path.join(self._tmp.name, "phase3_simulated_targets.json")
        with mock.patch.object(serve_web_app, "DATA_DIR", self._tmp.name), \
                mock.patch(
                    "pipeline.orchestrator.run_pipeline", return_value=feed_path
                ):
            status, body = self._get("/api/rescan")
        self.assertEqual(status, 200)
        self.assertEqual(body["feed_version"], FEED_VERSION)
        self.assertEqual(len(body["simulated_targets"]), 1)
        # A scan response is the same compact contract, not the raw payload.
        self.assertNotIn("pnl_by_slippage_level", body["simulated_targets"][0])


if __name__ == "__main__":
    unittest.main()

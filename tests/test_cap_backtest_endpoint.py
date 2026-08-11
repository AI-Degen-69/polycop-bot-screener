#!/usr/bin/env python3
"""The custom-caps backtest endpoint: parse validation and HTTP behaviour.

The custom-caps control in the wallet modal asks the server to backtest one
wallet at caller-chosen per-position caps. These tests start the real web
handler in-process on an ephemeral port (no external network, CI-safe — the
same pattern as test_web_app_served_labels.py) and patch the sweep out, so
they exercise the endpoint's parsing, status codes and payload shape without
hitting the live CLOB simulation API.
"""
import http.server
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))
from paths import DATA_DIR, PHASE3_FILE

from server.serve_web_app import (  # noqa: E402
    MAX_CUSTOM_CAP_LEVELS,
    PolyCopScreenerWebHandler,
    _parse_cap_levels,
)


def _fake_sweep(wallet, profile=None, cap_levels=None, slippage_levels=None,
                fetcher=None, cache_dir=None):
    """A stand-in for run_cap_sensitivity_sweep: one level per cap, flat 75%
    retention, no rejection."""
    results = []
    for cap in cap_levels:
        results.append({
            "cap_usd": cap,
            "window_min_usd": 33.33,
            "window_max_usd": round(cap / 0.03, 2),
            "max_single_position_usd": round(cap, 2),
            "copy_trade_usd": 3.0,
            "is_rejected": False,
            "rejection_reason": None,
            "endpoint_failure": False,
            "simulated_copy_pnl_10": round(cap * 0.5, 2),
            "edge_retention": 0.75,
        })
    return results


class TestParseCapLevels(unittest.TestCase):
    def test_parses_dedupes_and_sorts(self):
        self.assertEqual(_parse_cap_levels("20, 8, 8, 25"), [8.0, 20.0, 25.0])

    def test_single_cap(self):
        self.assertEqual(_parse_cap_levels("12"), [12.0])

    def test_rejects_empty(self):
        for bad in ("", "   ", ","):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    _parse_cap_levels(bad)

    def test_rejects_non_numeric_tokens(self):
        with self.assertRaises(ValueError):
            _parse_cap_levels("8, abc, 12")

    def test_rejects_non_positive_and_non_finite_caps(self):
        for bad in ("0", "-5", "nan", "inf"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    _parse_cap_levels(bad)

    def test_rejects_too_many_caps(self):
        many = ",".join(str(i) for i in range(1, MAX_CUSTOM_CAP_LEVELS + 2))
        with self.assertRaises(ValueError):
            _parse_cap_levels(many)


class TestCapBacktestEndpoint(unittest.TestCase):
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

    def _get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_custom_caps_return_levels_with_tiers(self):
        with mock.patch(
            "screener.simulated_verdict.run_cap_sensitivity_sweep",
            side_effect=_fake_sweep,
        ):
            status, body = self._get("/api/cap_backtest?wallet=0xabcdef1234567890&caps=8,25")
        self.assertEqual(status, 200)
        self.assertEqual(body["wallet"], "0xabcdef1234567890")
        self.assertEqual([level["cap_usd"] for level in body["levels"]], [8.0, 25.0])
        # The pipeline's tier verdict is stamped on every level.
        self.assertTrue(all(level["tier"] for level in body["levels"]))

    def test_bad_caps_return_400_with_a_ui_safe_message(self):
        status, body = self._get("/api/cap_backtest?wallet=0xabcdef1234567890&caps=abc")
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        self.assertNotIn("<", body["error"])  # safe to interpolate into the card

    def test_missing_wallet_returns_400(self):
        status, body = self._get("/api/cap_backtest?caps=8,20")
        self.assertEqual(status, 400)
        self.assertIn("wallet", body["error"])

    def test_a_non_address_wallet_returns_400_before_any_simulation(self):
        """A typo'd wallet must fail fast rather than burn live sim calls."""
        with mock.patch(
            "screener.simulated_verdict.run_cap_sensitivity_sweep",
            side_effect=AssertionError("the sweep must not be called for a bad wallet"),
        ) as sweep:
            status, body = self._get("/api/cap_backtest?wallet=notanaddress&caps=8")
        self.assertEqual(status, 400)
        self.assertIn("0x", body["error"])
        sweep.assert_not_called()

    def test_a_sweep_failure_returns_500_and_does_not_write_the_feed(self):
        feed = os.path.join(DATA_DIR, PHASE3_FILE)
        before = open(feed, "rb").read() if os.path.exists(feed) else None

        def boom(wallet, **kwargs):
            raise RuntimeError("Boom")

        with mock.patch(
            "screener.simulated_verdict.run_cap_sensitivity_sweep",
            side_effect=boom,
        ):
            status, body = self._get("/api/cap_backtest?wallet=0xabcdef1234567890&caps=8")
        self.assertEqual(status, 500)
        self.assertIn("Backtest failed", body["error"])

        after = open(feed, "rb").read() if os.path.exists(feed) else None
        self.assertEqual(after, before, "the endpoint must never rewrite the feed")


if __name__ == "__main__":
    unittest.main()

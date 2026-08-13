#!/usr/bin/env python3
"""The web JSON API behind its seam: endpoints, router, and framing.

The handler's five endpoints were extracted into module-level functions that
return (status, payload), behind a routing table (_API_ROUTES) and a pure
router (_dispatch) that maps errors to statuses, with one framing writer
(_send_json). These tests call that seam directly — no sockets, no network —
so the error mapping, the JSON 404 fallback, and the framing contract are
proven at the seam itself. One HTTP-level class re-boots the real handler to
prove do_GET wires the seam to the wire. The other endpoint tests
(test_cap_backtest_endpoint.py, test_web_app_served_labels.py) keep covering
the HTTP contract unchanged.
"""
import http.server
import io
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from server.serve_web_app import (  # noqa: E402
    PolyCopScreenerWebHandler,
    _dispatch,
    _send_json,
    endpoint_cap_backtest,
    endpoint_clear_data,
    endpoint_leaderboard,
    endpoint_measure_latency,
    endpoint_rescan,
)


class _FakeHandler:
    """The slice of the HTTP handler the framing helper touches."""

    def __init__(self):
        self.status = None
        self.headers = {}
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.headers[key] = value

    def end_headers(self):
        pass


def _fake_sweep(wallet, profile=None, cap_levels=None, slippage_levels=None,
                fetcher=None, cache_dir=None):
    """Stand-in for backtest_wallet_at_caps: one flat level per cap."""
    return [{"cap_usd": cap, "tier": "A-Tier"} for cap in cap_levels]


class TestRouting(unittest.TestCase):
    def test_a_matching_prefix_routes_to_its_endpoint(self):
        with mock.patch(
            "screener.simulated_verdict.backtest_wallet_at_caps",
            side_effect=_fake_sweep,
        ):
            status, payload = _dispatch(
                "/api/cap_backtest", "wallet=0xabcdef1234567890&caps=8"
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["wallet"], "0xabcdef1234567890")

    def test_an_unknown_api_path_is_a_json_404_not_a_static_fallthrough(self):
        status, payload = _dispatch("/api/does_not_exist", "")
        self.assertEqual(status, 404)
        self.assertIn("unknown endpoint", payload["error"])

    def test_a_non_api_path_falls_through_to_static_serving(self):
        self.assertIsNone(_dispatch("/index.html", ""))
        self.assertIsNone(_dispatch("/data/phase3_simulated_targets.json", ""))

    def test_the_query_string_is_passed_to_the_endpoint_untouched(self):
        with mock.patch(
            "server.serve_web_app.endpoint_measure_latency",
            return_value=(200, {"fake": True}),
        ) as ep:
            _dispatch("/api/measure_latency", "t=12345")
        ep.assert_called_once_with("/api/measure_latency", "t=12345")


class TestErrorMapping(unittest.TestCase):
    def test_a_value_error_becomes_a_400_with_its_message(self):
        # cap_backtest raises ValueError on bad input before any simulation.
        with mock.patch(
            "screener.simulated_verdict.backtest_wallet_at_caps",
            side_effect=AssertionError("the sweep must not be called"),
        ) as sweep:
            status, payload = _dispatch("/api/cap_backtest", "wallet=0xabcdef1234567890&caps=abc")
        self.assertEqual(status, 400)
        self.assertIn("not a number", payload["error"])
        sweep.assert_not_called()

    def test_a_failed_backtest_becomes_a_500_with_the_ui_prefix(self):
        def boom(wallet, **kwargs):
            raise RuntimeError("Boom")

        with mock.patch(
            "screener.simulated_verdict.backtest_wallet_at_caps",
            side_effect=boom,
        ):
            status, payload = _dispatch("/api/cap_backtest", "wallet=0xabcdef1234567890&caps=8")
        self.assertEqual(status, 500)
        self.assertIn("Backtest failed", payload["error"])

    def test_an_endpoint_that_raises_is_mapped_to_500_without_mangling_the_message(self):
        with mock.patch(
            "server.serve_web_app.endpoint_measure_latency",
            side_effect=RuntimeError('says "hi"'),
        ):
            status, payload = _dispatch("/api/measure_latency", "")
        self.assertEqual(status, 500)
        self.assertEqual(payload["error"], 'says "hi"')


class TestEndpointFunctions(unittest.TestCase):
    def test_clear_data_deletes_the_cache_and_reports_cleared(self):
        with mock.patch("pipeline.reset_data_cache.reset_data_cache") as reset:
            status, payload = endpoint_clear_data("/api/clear_data", "")
        reset.assert_called_once()
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "cleared")

    def test_rescan_returns_the_feed_the_pipeline_produced(self):
        # The response is the compact v1 projection, never the raw payload:
        # a finished scan fills the grid through the one path that knows how
        # to normalise it, and the page reads the same contract from the feed.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            feed = os.path.join(tmp, "feed.json")
            with open(feed, "w", encoding="utf-8") as f:
                json.dump({"simulated_targets": []}, f)
            with mock.patch("pipeline.orchestrator.run_pipeline", return_value=feed):
                status, payload = endpoint_rescan("/api/rescan", "")
        self.assertEqual(status, 200)
        # Read from the constant rather than pinned here: the projection owns
        # what version it speaks, and a bump should not need a test edit.
        from server.feed_projection import FEED_VERSION

        self.assertEqual(payload, {"feed_version": FEED_VERSION, "simulated_targets": []})

    def test_rescan_fails_when_the_pipeline_produces_no_file(self):
        # The status mapping lives in the router, so this goes through
        # _dispatch rather than calling the endpoint directly.
        with mock.patch(
            "pipeline.orchestrator.run_pipeline",
            return_value="/nonexistent/verified.json",
        ):
            status, payload = _dispatch("/api/rescan", "")
        self.assertEqual(status, 500)
        self.assertIn("Verified dataset file was not created", payload["error"])

    def test_leaderboard_forwards_path_and_query_and_passes_bytes_through(self):
        fake_resp = mock.MagicMock()
        fake_resp.read.return_value = b'{"upstream": true}'
        fake_resp.__enter__.return_value = fake_resp  # used as a context manager
        with mock.patch("urllib.request.urlopen", return_value=fake_resp) as urlopen:
            status, payload = endpoint_leaderboard(
                "/api/leaderboard", "limit=5"
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, b'{"upstream": true}')
        req = urlopen.call_args.args[0]
        self.assertEqual(
            req.full_url, "https://polycop.fun/api/leaderboard?limit=5"
        )

    def test_measure_latency_returns_the_benchmark_payload(self):
        with mock.patch(
            "server.serve_web_app._measure_latency_payload",
            return_value={"partial": False},
        ):
            status, payload = endpoint_measure_latency("/api/measure_latency", "")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"partial": False})


class TestFraming(unittest.TestCase):
    def _frame(self, status, payload):
        handler = _FakeHandler()
        _send_json(handler, status, payload)
        return handler

    def test_every_response_gets_json_type_cors_and_an_exact_content_length(self):
        handler = self._frame(200, {"wallet": "0xabc"})
        body = handler.wfile.getvalue()
        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.headers["Content-Type"], "application/json")
        self.assertEqual(handler.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(handler.headers["Content-Length"], str(len(body)))
        self.assertEqual(json.loads(body), {"wallet": "0xabc"})

    def test_an_error_message_with_quotes_still_serializes_to_valid_json(self):
        # The pre-refactor string-interpolated JSON broke on messages like this.
        handler = self._frame(500, {"error": 'says "hi"'})
        self.assertEqual(json.loads(handler.wfile.getvalue()), {"error": 'says "hi"'})

    def test_raw_bytes_payloads_pass_through_unchanged(self):
        handler = self._frame(200, b'{"upstream": true}')
        self.assertEqual(handler.wfile.getvalue(), b'{"upstream": true}')

    def test_a_client_that_disconnects_mid_write_does_not_raise(self):
        class Gone:
            def write(self, body):
                raise ConnectionResetError("client went away")

        handler = _FakeHandler()
        handler.wfile = Gone()
        _send_json(handler, 200, {"ok": True})  # must not raise


class TestHttpWiring(unittest.TestCase):
    """The real handler on an ephemeral port: do_GET wires seam to wire."""

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

    def test_static_pages_still_serve(self):
        with urllib.request.urlopen(self.base + "/", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("PolyCop Bot Screener", resp.read().decode("utf-8"))

    def test_an_unknown_api_path_is_a_json_404_over_http(self):
        try:
            with urllib.request.urlopen(self.base + "/api/nope", timeout=5) as resp:
                self.fail("expected HTTPError")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)
            body = json.loads(e.read().decode("utf-8"))
            self.assertIn("unknown endpoint", body["error"])
            self.assertEqual(e.headers["Content-Type"], "application/json")

    def test_a_bad_request_is_a_400_with_an_exact_content_length(self):
        try:
            with urllib.request.urlopen(
                self.base + "/api/cap_backtest?caps=abc", timeout=5
            ) as resp:
                self.fail("expected HTTPError")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            body = e.read()
            self.assertEqual(e.headers["Content-Length"], str(len(body)))
            self.assertIn("error", json.loads(body))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""The generated labels reach the page the browser loads, not just the files.

`tools/scoring_docs.py` regenerates the tier, gate and weight labels embedded
in the web assets, and its drift check fails when they diverge from
SCORING_SPEC. That check reads the files on disk; this test starts the real
web server in-process on an ephemeral port and asserts every generated label
is present in the HTTP responses a browser would receive. A label could be
correct on disk yet never served — this closes that gap.

Loopback only: no external network, no fixed port, so it is CI-safe and cannot
collide with a server another thread is already running on 8050.
"""
import http.server
import os
import sys
import threading
import unittest
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))
# Importing paths also puts tools/ on sys.path, which `import scoring_docs`
# below needs; the import is for that side effect, not for the name.
import paths  # noqa: E402

import scoring_docs  # noqa: E402
from server.serve_web_app import PolyCopScreenerWebHandler  # noqa: E402


class TestTheServedPageCarriesEveryGeneratedLabel(unittest.TestCase):
    """Every label the drift check guards is in what the server actually serves."""

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
        with urllib.request.urlopen(self.base + path, timeout=5) as resp:
            self.assertEqual(resp.status, 200, f"GET {path} should be served")
            return resp.read().decode("utf-8")

    def test_index_html_serves_every_html_label(self):
        body = self._get("/")
        for label in scoring_docs.UI_LABELS:
            if label["relpath"].endswith("index.html"):
                with self.subTest(description=label["description"]):
                    self.assertIn(label["expected"], body)

    def test_app_js_serves_every_js_label(self):
        body = self._get("/js/app.js")
        for label in scoring_docs.UI_LABELS:
            if label["relpath"].endswith("app.js"):
                with self.subTest(description=label["description"]):
                    self.assertIn(label["expected"], body)

    def test_the_page_served_is_the_real_page(self):
        body = self._get("/")
        self.assertIn("PolyCop Bot Screener", body)


if __name__ == "__main__":
    unittest.main()

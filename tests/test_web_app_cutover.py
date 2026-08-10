#!/usr/bin/env python3
"""The page renders what the pipeline computed, and nothing rescores in the browser.

These read the shipped assets as text rather than driving a browser. They cannot
tell you the page looks right; they can tell you the second scoring engine has
not come back and the page is not reading the triage feed again, which is what
the cutover was for. The live browser check lives in verify_web_app_live.py.
"""
import os
import re
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB_DIR = os.path.join(PROJECT_ROOT, "app", "web")
INDEX_HTML = os.path.join(WEB_DIR, "index.html")
APP_JS = os.path.join(WEB_DIR, "js", "app.js")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestTheBrowserNoLongerScores(unittest.TestCase):
    def test_the_javascript_scoring_engine_is_gone(self):
        self.assertFalse(
            os.path.exists(os.path.join(WEB_DIR, "js", "client_score_engine.js")),
            "a second scoring engine can disagree with the first, and the one on "
            "screen is the one that gets acted on",
        )

    def test_nothing_loads_the_engine(self):
        self.assertNotIn("client_score_engine", _read(INDEX_HTML))

    def test_no_scoring_function_survives_in_the_page_script(self):
        self.assertNotIn("calculateBankrollOptimizedScore", _read(APP_JS))


class TestThePageReadsTheSimulationFeed(unittest.TestCase):
    def setUp(self):
        self.app_js = _read(APP_JS)

    def test_it_fetches_the_simulation_output(self):
        self.assertIn("phase3_simulated_targets.json", self.app_js)

    def test_it_no_longer_fetches_the_triage_output(self):
        self.assertNotIn("phase2_verified_targets.json", self.app_js)

    def test_it_reads_the_simulated_targets_collection(self):
        self.assertIn("simulated_targets", self.app_js)

    def test_the_scan_path_rereads_the_feed_rather_than_parsing_the_response(self):
        """A finished scan must fill the grid, not empty it.

        The scan handler kept its own reading of the payload and it had
        drifted to `verified_targets`, a key no payload has ever carried, so
        every completed scan blanked the wallet grid and left a header count
        with nothing behind it. One reader means it cannot drift again.
        """
        scan_body = self.app_js.split("async function startLeaderboardScan()", 1)[1]
        scan_body = scan_body.split("\nasync function", 1)[0]
        self.assertIn("loadDataset()", scan_body)

    def test_no_key_the_feed_does_not_carry_is_read_anywhere(self):
        # Comments are stripped first: the one above the scan handler names
        # the dead key in order to explain why it must not come back.
        code = "\n".join(
            line for line in self.app_js.splitlines()
            if not line.lstrip().startswith("//")
        )
        for absent in ("verified_targets", "total_scraped_profiles", "total_verified_targets"):
            self.assertNotIn(
                absent, code, f"{absent} is not a key of the Phase 3 payload"
            )


class TestProvenanceIsOnThePage(unittest.TestCase):
    def setUp(self):
        self.app_js = _read(APP_JS)
        self.index = _read(INDEX_HTML)

    def test_the_page_has_somewhere_to_state_provenance(self):
        self.assertIn('id="provenanceBanner"', self.index)

    def test_a_degraded_run_is_announced(self):
        self.assertIn("reduced_confidence", self.app_js)
        self.assertRegex(self.app_js, r"triage order, not simulated results")

    def test_the_execution_profile_is_shown(self):
        for field in ("bankroll_usd", "copy_ratio", "slippage_pct", "fingerprint"):
            with self.subTest(field=field):
                self.assertIn(field, self.app_js)

    def test_an_unsimulated_wallet_is_marked_as_such(self):
        self.assertIn("Not simulated", self.app_js)

    def test_the_tier_shown_is_gated_on_the_verdict_source(self):
        # Without this check a triage grade renders in the Tier column and reads
        # exactly like a simulated verdict.
        self.assertRegex(self.app_js, r'verdict_source\s*===\s*"simulation"')


class TestTheNewFiguresAreRendered(unittest.TestCase):
    def setUp(self):
        self.app_js = _read(APP_JS)
        self.index = _read(INDEX_HTML)

    def test_edge_retention_is_rendered(self):
        self.assertIn("edge_retention", self.app_js)
        self.assertIn("Edge Retention", self.app_js)

    def test_copyable_window_share_is_rendered(self):
        self.assertIn("copyable_window_share", self.app_js)
        self.assertIn("Copyable Window Share", self.app_js)

    def test_balance_miss_has_a_home_and_a_renderer(self):
        self.assertIn('id="modalBalanceMiss"', self.index)
        self.assertIn("balance_miss_details", self.app_js)

    def test_the_copyability_score_is_still_shown_beside_the_verdict(self):
        self.assertIn("triage_copyability_score", self.app_js)

    def test_wallets_can_be_ordered_by_edge_retention(self):
        self.assertIn("retention-desc", self.index)
        self.assertIn("retention-desc", self.app_js)

    def test_the_pnl_sort_reads_the_simulated_figure_not_the_leaderboard(self):
        # The verdict page orders by the simulation's PnL, not the leaderboard's
        # modelled figure — the same provenance rule as every other verdict metric.
        self.assertIn("simulated_copy_pnl_10", self.app_js)
        self.assertIn("Highest Simulated Copy PnL", self.index)
        self.assertNotIn("b.metrics.copy_pnl - a.metrics.copy_pnl", self.app_js)


class TestUnmeasuredFiguresAreNotShownAsZero(unittest.TestCase):
    def test_an_absent_share_reads_as_unmeasured(self):
        app_js = _read(APP_JS)
        match = re.search(r"function formatShare\(value\)\s*\{(.+?)\n\}", app_js, re.S)
        self.assertIsNotNone(match, "formatShare should exist to handle absent figures")
        self.assertIn("Not measured", match.group(1))


if __name__ == "__main__":
    unittest.main()

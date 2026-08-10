#!/usr/bin/env python3
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "app", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from screener.score_wallets import calculate_bankroll_optimized_score, calculate_edge_retention

class TestScoreWalletsEngine(unittest.TestCase):
    def test_edge_retention_positive_pnl(self):
        """Test edge retention on positive PnLs."""
        self.assertAlmostEqual(calculate_edge_retention(80.0, 100.0), 0.8)

    def test_edge_retention_negative_pnl_returns_none(self):
        """Test edge retention gate ordering: negative PnL must return None."""
        self.assertIsNone(calculate_edge_retention(-5.95, -5.05))
        self.assertIsNone(calculate_edge_retention(-5.0, 10.0))
        self.assertIsNone(calculate_edge_retention(10.0, 0.0))

    
    def test_pass_target_high_score(self):
        """Test a clean S-Tier target passing all gates."""
        metrics = {
            "actual_pnl": 5000.0,
            "copy_pnl": 4900.0,
            "slippage": 2.0,
            "hedged_pct": 0.0,
            "pl_ratio": 5.0,
            "days_win_rate": 80.0,
            "r20_win_rate": 80.0,
            "r20_pnl": 800.0,
            "r20_slip": 2.0,
            "pnl_vol_ratio": 25.0,
            "avg_invest": 25.0,
            "markets": 150,
            "polycop_site_score": 85.0
        }
        res = calculate_bankroll_optimized_score(metrics, user_capital=100.0)
        self.assertEqual(len(res["rejection_reasons"]), 0)
        self.assertGreaterEqual(res["final_score"], 80.0)

    def test_whale_gate_at_200(self):
        """Test Hard Gate: Avg Invest > $200.00 USD."""
        metrics = {"polycop_site_score": 75.0, "actual_pnl": 1000.0, "copy_pnl": 950.0, "avg_invest": 250.0}
        res = calculate_bankroll_optimized_score(metrics)
        self.assertTrue(any("Whale Avg Invest" in r for r in res["rejection_reasons"]))

    def test_site_score_prefilter_removed_sanity_floor_at_40(self):
        """Test site score <= 60 no longer rejects, but < 40 sanity floor rejects."""
        # 55 passes (pre-filter removed)
        metrics_pass = {"polycop_site_score": 55.0, "actual_pnl": 1000.0, "copy_pnl": 950.0, "markets": 30, "r20_win_rate": 60.0}
        res_pass = calculate_bankroll_optimized_score(metrics_pass)
        self.assertFalse(any("PolyCop Site Score" in r for r in res_pass["rejection_reasons"]))

        # 35 fails (sanity floor at 40)
        metrics_fail = {"polycop_site_score": 35.0, "actual_pnl": 1000.0, "copy_pnl": 950.0}
        res_fail = calculate_bankroll_optimized_score(metrics_fail)
        self.assertTrue(any("PolyCop Site Score" in r for r in res_fail["rejection_reasons"]))

    def test_divergence_gate_negative_recent_vs_positive_lifetime(self):
        """Test Divergence Gate: r20_pnl < 0 while actual_pnl > 1000."""
        metrics = {"polycop_site_score": 75.0, "actual_pnl": 5000.0, "copy_pnl": 4500.0, "r20_pnl": -200.0}
        res = calculate_bankroll_optimized_score(metrics)
        self.assertTrue(any("Divergence Gate" in r for r in res["rejection_reasons"]))


if __name__ == "__main__":
    unittest.main()

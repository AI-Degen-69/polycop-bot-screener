#!/usr/bin/env python3
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "app", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from screener.score_wallets import calculate_bankroll_optimized_score

class TestScoreWalletsEngine(unittest.TestCase):
    
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

    def test_hard_gate_polycop_site_score(self):
        """Test Hard Gate 1: PolyCop Site Score <= 60."""
        metrics = {"polycop_site_score": 55.0, "actual_pnl": 1000.0, "copy_pnl": 900.0}
        res = calculate_bankroll_optimized_score(metrics)
        self.assertTrue(any("PolyCop Site Score" in r for r in res["rejection_reasons"]))

    def test_hard_gate_hedged_rate(self):
        """Test Hard Gate 4: Hedged Rate > 3.0%."""
        metrics = {"polycop_site_score": 75.0, "actual_pnl": 1000.0, "copy_pnl": 900.0, "hedged_pct": 5.0}
        res = calculate_bankroll_optimized_score(metrics)
        self.assertTrue(any("Hedged Rate" in r for r in res["rejection_reasons"]))

    def test_hard_gate_hft_bot(self):
        """Test Hard Gate 9: High Frequency Bot (markets > 300 & slip > 5%)."""
        metrics = {
            "polycop_site_score": 75.0,
            "actual_pnl": 12000.0,
            "copy_pnl": 10000.0,  # 16.6% slip rate
            "markets": 941
        }
        res = calculate_bankroll_optimized_score(metrics)
        self.assertTrue(any("High Frequency" in r for r in res["rejection_reasons"]))

if __name__ == "__main__":
    unittest.main()

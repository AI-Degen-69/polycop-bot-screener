import pytest
from app.src.execution.copy_execution_profile import CURRENT_PROFILE
from app.src.pipeline.phase3_simulation_rank import run_phase3_simulation_rank

def test_simulation_rank_ordering_and_tier_assignment():
    """Verify targets are ranked by edge retention and assigned simulated tiers."""
    sample_targets = [
        {
            "address": "0x1111",
            "name": "Target Alpha",
            "final_score": 85.0,
            "grade": "A-Tier",
            "metrics": {"avg_invest": 25.0}
        },
        {
            "address": "0x2222",
            "name": "Target Beta",
            "final_score": 92.0,
            "grade": "S-Tier",
            "metrics": {"avg_invest": 25.0}
        }
    ]

    # Target Alpha: 2% -> 100, 10% -> 90 (retention = 0.90 -> S-Tier)
    # Target Beta: 2% -> 100, 10% -> 75 (retention = 0.75 -> A-Tier)
    def mock_fetcher(payload):
        addr = payload["wallet"]
        slip = payload["slippage"]
        if addr == "0x1111":
            pnl = 100.0 if slip == 2.0 else 90.0
        else:
            pnl = 100.0 if slip == 2.0 else 75.0
        return {"sim_total_pnl": pnl, "target_total_pnl": 500.0, "logs": [{"type": "INTERCEPT"}]}

    out = run_phase3_simulation_rank(targets=sample_targets, profile=CURRENT_PROFILE, fetcher=mock_fetcher)

    assert out["reduced_confidence"] is False
    assert len(out["simulated_targets"]) == 2
    # Ranked by Edge Retention descending: Alpha (0.90) > Beta (0.75)
    assert out["simulated_targets"][0]["address"] == "0x1111"
    assert out["simulated_targets"][0]["edge_retention"] == 0.90
    assert out["simulated_targets"][0]["simulated_tier"] == "S-Tier (God-Tier Target)"

    assert out["simulated_targets"][1]["address"] == "0x2222"
    assert out["simulated_targets"][1]["edge_retention"] == 0.75
    assert out["simulated_targets"][1]["simulated_tier"] == "A-Tier (Strong Copy Target)"

def test_simulation_rank_endpoint_failure_fallback():
    """Verify fallback to copyability score ordering on endpoint failure."""
    sample_targets = [
        {"address": "0x1111", "final_score": 75.0, "name": "Trader One"},
        {"address": "0x2222", "final_score": 95.0, "name": "Trader Two"}
    ]

    def failing_fetcher(payload):
        raise RuntimeError("Network down")

    out = run_phase3_simulation_rank(targets=sample_targets, profile=CURRENT_PROFILE, fetcher=failing_fetcher)

    assert out["reduced_confidence"] is True
    assert out["fallback_reason"] == "Endpoint unavailable: Network down"
    # Ordered by triage copyability score descending (95.0 > 75.0)
    assert out["simulated_targets"][0]["address"] == "0x2222"
    assert out["simulated_targets"][0]["triage_copyability_score"] == 95.0

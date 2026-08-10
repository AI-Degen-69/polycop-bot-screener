import pytest
from app.src.execution.copy_execution_profile import CURRENT_PROFILE
from app.src.screener.slippage_sweep import run_slippage_sensitivity_sweep

def test_slippage_sweep_all_four_levels():
    """Verify sweep executes 4 simulation runs across 2%, 5%, 10%, and 15% slippage."""
    call_slippages = []
    def mock_fetcher(payload):
        call_slippages.append(payload["slippage"])
        return {
            "sim_total_pnl": 100.0 - payload["slippage"] * 2.0,
            "target_total_pnl": 500.0,
            "logs": []
        }

    wallet = "0x1111111111111111111111111111111111111111"
    res = run_slippage_sensitivity_sweep(wallet, profile=CURRENT_PROFILE, fetcher=mock_fetcher)

    assert call_slippages == [2.0, 5.0, 10.0, 15.0]
    assert res["is_rejected"] is False
    assert res["edge_retention"] == pytest.approx(0.8333, abs=0.001)  # (100 - 20) / (100 - 4) = 80 / 96 = 0.8333

def test_slippage_sweep_negative_pnl_at_10_percent_rejected():
    """Regression test: wallet losing at all 4 levels is rejected with NO retention figure."""
    pnl_map = {2.0: -5.05, 5.0: -5.40, 10.0: -5.95, 15.0: -6.45}
    def mock_fetcher(payload):
        return {
            "sim_total_pnl": pnl_map[payload["slippage"]],
            "target_total_pnl": 99000.0,
            "logs": []
        }

    wallet = "0xeafc018ccbca46db203ba57c3e798ce0e84fe4c4"
    res = run_slippage_sensitivity_sweep(wallet, profile=CURRENT_PROFILE, fetcher=mock_fetcher)

    assert res["is_rejected"] is True
    assert "10% slippage" in res["rejection_reason"]
    assert res["edge_retention"] is None

def test_slippage_sweep_edge_decay_vs_inversion():
    """Distinguish gradual edge decay from inverted edge mirage."""
    # Gradual decay: 2% -> 100 PnL, 10% -> 80 PnL (retention = 0.8)
    def gradual_fetcher(p):
        return {"sim_total_pnl": 100.0 if p["slippage"] == 2.0 else 80.0, "target_total_pnl": 200.0, "logs": []}
    
    res1 = run_slippage_sensitivity_sweep("0x1111", fetcher=gradual_fetcher)
    assert res1["edge_retention"] == 0.8

    # Inverted mirage: 2% -> 100 PnL, 10% -> 10 PnL (retention = 0.1)
    def inverted_fetcher(p):
        return {"sim_total_pnl": 100.0 if p["slippage"] == 2.0 else 10.0, "target_total_pnl": 200.0, "logs": []}

    res2 = run_slippage_sensitivity_sweep("0x2222", fetcher=inverted_fetcher)
    assert res2["edge_retention"] == 0.1

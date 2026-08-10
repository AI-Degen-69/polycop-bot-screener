import os
import sys

import pytest

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "src"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from execution.copy_execution_profile import CURRENT_PROFILE  # noqa: E402
from screener.slippage_sweep import run_slippage_sensitivity_sweep  # noqa: E402

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


def test_a_failed_fetch_is_an_absent_measurement_not_a_measured_zero():
    """ADR 0007: a raising fetcher must produce a rejection whose reason names
    the endpoint failure and a `None` PnL at the failed level — never a
    fabricated "$0.00 measured rejection".
    """
    def failing_fetcher(payload):
        raise RuntimeError("Endpoint unavailable")

    res = run_slippage_sensitivity_sweep("0xaaaa", profile=CURRENT_PROFILE, fetcher=failing_fetcher)

    assert res["is_rejected"] is True
    assert res["rejection_reason"] == "Simulation unavailable at 10% slippage threshold (endpoint failure)"
    assert res["pnl_by_level"][10.0] is None
    assert res["edge_retention"] is None
    assert res["endpoint_failure"] is True


def test_a_genuinely_measured_zero_keeps_the_measured_rejection_wording():
    """The two cases must stay distinguishable: a real break-even at 10%
    keeps the measured wording and is not an endpoint failure.
    """
    def measured_zero_fetcher(payload):
        return {"sim_total_pnl": 0.0, "target_total_pnl": 500.0, "logs": []}

    res = run_slippage_sensitivity_sweep("0xbbbb", profile=CURRENT_PROFILE, fetcher=measured_zero_fetcher)

    assert res["is_rejected"] is True
    assert res["rejection_reason"] == "Non-positive Simulated Copy PnL ($0.00) at 10% slippage threshold"
    assert res["pnl_by_level"][10.0] == 0.0
    assert res["endpoint_failure"] is False


def test_a_failed_non_gated_level_records_none_but_does_not_reject():
    """Only the gated levels (10%, 2%) disqualify a wallet. A failed 5% or
    15% fetch is a `None` gap in the decay curve, not a rejection.
    """
    def flaky_fetcher(payload):
        if payload["slippage"] == 5.0:
            raise RuntimeError("Network down")
        return {
            "sim_total_pnl": 100.0 if payload["slippage"] == 2.0 else 80.0,
            "target_total_pnl": 500.0,
            "logs": []
        }

    res = run_slippage_sensitivity_sweep("0xcccc", profile=CURRENT_PROFILE, fetcher=flaky_fetcher)

    assert res["is_rejected"] is False
    assert res["pnl_by_level"][5.0] is None
    assert res["pnl_by_level"][10.0] == 80.0
    assert res["edge_retention"] == pytest.approx(0.8)
    assert res["endpoint_failure"] is False

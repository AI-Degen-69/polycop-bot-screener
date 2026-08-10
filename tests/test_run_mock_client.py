import pytest
from app.src.pipeline.run_mock_client import build_run_mock_payload, parse_run_mock_response, calculate_copyable_window_share

def test_build_run_mock_payload_defaults():
    wallet = "0xeafc018ccbca46db203ba57c3e798ce0e84fe4c4"
    payload = build_run_mock_payload(wallet)
    
    assert payload["wallet"] == wallet
    assert payload["fetch_mode"] == "limit"
    assert payload["limit"] == 4000
    assert payload["copy_pct"] == 3
    assert payload["slippage"] == 10
    assert payload["capital"] == 100
    assert payload["target_max_price"] == 0.95
    assert payload["target_min_price"] == 0.05

def test_parse_run_mock_response_summary():
    mock_data = {
        "sim_total_pnl": -5.953,
        "target_total_pnl": 99295.84,
        "max_drawdown": 7.18,
        "pl_ratio": 0.45,
        "win_rate": 0.33,
        "winning_days": 1,
        "losing_days": 2,
        "flat_days": 0,
        "trading_days": 3,
        "intercepted": 46,
        "total_trades": 3,
        "logs": [
            {"action": "BUY", "status": "INTERCEPT"},
            {"action": "SKIP_FILTER", "status": "REJECT"},
            {"action": "SKIP_CAP", "status": "REJECT"}
        ]
    }
    
    parsed = parse_run_mock_response(mock_data)
    assert parsed["sim_total_pnl"] == -5.953
    assert parsed["target_total_pnl"] == 99295.84
    assert parsed["max_drawdown"] == 7.18
    assert parsed["total_decisions"] == 3
    assert parsed["executed_trades"] == 3

def test_calculate_copyable_window_share_reconciliation():
    mock_data = {
        "intercepted": 46,
        "total_trades": 3,
        "logs": [
            {"type": "INTERCEPT"},
            {"type": "INTERCEPT"},
            {"type": "SKIP_FILTER"},
            {"type": "SKIP_FILTER"}
        ]
    }
    # 2 INTERCEPT decisions out of 4 total target trade signals evaluated
    share = calculate_copyable_window_share(mock_data)
    assert share == 0.5

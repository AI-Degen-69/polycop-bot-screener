import os
import sys

import pytest

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "src"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from pipeline.run_mock_client import build_run_mock_payload  # noqa: E402
from screener.simulated_copy_run import (  # noqa: E402
    calculate_copyable_window_share,
    parse_simulated_run_response,
)

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
            {"type": "BUY", "action": "BUY"},
            {"type": "INTERCEPT", "action": "SKIP_FILTER"},
            {"type": "WARNING", "action": "SKIP_CAP"}
        ]
    }

    parsed = parse_simulated_run_response(mock_data)
    assert parsed["sim_total_pnl"] == -5.953
    assert parsed["target_total_pnl"] == 99295.84
    assert parsed["max_drawdown"] == 7.18
    assert parsed["target_trades"] == 3
    # `total_trades` is a count of markets the simulation traded, and
    # `intercepted` a count of exits it could not follow — spike 0002.
    assert parsed["traded_markets"] == 3
    assert parsed["ghost_exits"] == 46
    assert parsed["mirrored_orders"] == 1

def _log(action, verb, market="mkt"):
    """A decision log entry shaped like the upstream one — see spike 0002."""
    coarse = "INTERCEPT" if action in ("SKIP_FILTER", "INTERCEPT") else action
    return {
        "type": "WARNING" if action == "SKIP_CAP" else coarse,
        "action": action,
        "market_id": market,
        "msg": f"[{market}] Target {verb} 100.00 shares @ $0.500."
    }

def test_copyable_window_share_counts_entry_signals_the_window_admits():
    # Four target BUYs, of which the window refused two. The exits belong in
    # neither term: a size window has no say once the position is open.
    mock_data = {
        "intercepted": 3,
        "total_trades": 1,
        "logs": [
            _log("BUY", "BUY"),
            _log("SKIP_CAP", "BUY"),
            _log("SKIP_FILTER", "BUY"),
            _log("SKIP_FILTER", "BUY"),
            _log("INTERCEPT", "SELL"),
            _log("INTERCEPT", "REDEEM"),
            _log("SELL", "SELL"),
        ]
    }
    assert calculate_copyable_window_share(mock_data) == 0.5

def test_copyable_window_share_does_not_count_missed_exits_as_copyable():
    # The whale of spike 0001: every exit is a ghost position against empty
    # inventory, which is a miss. A wallet the window never let us enter
    # scores zero, not the 0.42 the `intercepted` reading used to return.
    mock_data = {
        "intercepted": 2,
        "total_trades": 0,
        "logs": [
            _log("SKIP_FILTER", "BUY"),
            _log("SKIP_FILTER", "BUY"),
            _log("INTERCEPT", "SELL"),
            _log("INTERCEPT", "REDEEM"),
        ]
    }
    assert calculate_copyable_window_share(mock_data) == 0.0

def test_copyable_window_share_is_zero_when_the_target_never_entered():
    # Exits only, so there is no entry population to take a share of.
    mock_data = {"intercepted": 2, "logs": [_log("INTERCEPT", "SELL")]}
    assert calculate_copyable_window_share(mock_data) == 0.0
    assert calculate_copyable_window_share({"logs": []}) == 0.0

def test_copyable_window_share_falls_back_to_action_without_a_message():
    # Messages are the authority on the target verb, but the refusals only
    # ever land on entries, so an action-only log is still measurable.
    mock_data = {
        "logs": [
            {"type": "BUY", "action": "BUY"},
            {"type": "INTERCEPT", "action": "SKIP_FILTER"},
        ]
    }
    assert calculate_copyable_window_share(mock_data) == 0.5

def test_fetch_simulated_copy_run_caching_and_injected_fetcher(tmp_path):
    from execution.copy_execution_profile import CopyExecutionProfile

    from pipeline.run_mock_client import fetch_simulated_copy_run

    profile1 = CopyExecutionProfile(bankroll_usd=100.0, copy_ratio=0.03)
    profile2 = CopyExecutionProfile(bankroll_usd=200.0, copy_ratio=0.05)
    
    call_count = 0
    def mock_fetcher(payload):
        nonlocal call_count
        call_count += 1
        return {"sim_total_pnl": 50.0, "target_total_pnl": 100.0, "logs": []}

    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    cache_dir = str(tmp_path)

    # First fetch: Cache MISS -> fetcher called
    res1 = fetch_simulated_copy_run(wallet, profile=profile1, fetcher=mock_fetcher, cache_dir=cache_dir)
    assert res1["success"] is True
    assert res1["cached"] is False
    assert call_count == 1

    # Second fetch with identical profile: Cache HIT -> fetcher NOT called
    res2 = fetch_simulated_copy_run(wallet, profile=profile1, fetcher=mock_fetcher, cache_dir=cache_dir)
    assert res2["success"] is True
    assert res2["cached"] is True
    assert call_count == 1

    # Third fetch with modified profile: Cache MISS -> fetcher called again
    res3 = fetch_simulated_copy_run(wallet, profile=profile2, fetcher=mock_fetcher, cache_dir=cache_dir)
    assert res3["success"] is True
    assert res3["cached"] is False
    assert call_count == 2

def test_fetch_simulated_copy_run_unavailable_result(tmp_path):
    from execution.copy_execution_profile import CURRENT_PROFILE
    from pipeline.run_mock_client import fetch_simulated_copy_run


    def failing_fetcher(payload):
        raise ConnectionError("Service unavailable")

    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    res = fetch_simulated_copy_run(wallet, profile=CURRENT_PROFILE, fetcher=failing_fetcher, cache_dir=str(tmp_path))

    assert res["success"] is False
    assert res["error"] == "Endpoint unavailable: Service unavailable"
    assert res["data"] is None


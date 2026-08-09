import pytest
from tools.measure_latency_slippage import calculate_vwap_slippage, filter_prediction_markets

def test_calculate_vwap_slippage_basic():
    # Orderbook asks: list of lists
    asks_list = [["0.50", "20"], ["0.55", "100"]]
    
    res_10 = calculate_vwap_slippage(asks_list, 10.0)
    assert res_10["best_ask"] == 0.50
    assert res_10["vwap"] == 0.50
    assert res_10["slippage_pct"] == 0.0

    res_30 = calculate_vwap_slippage(asks_list, 30.0)
    assert res_30["best_ask"] == 0.50
    assert res_30["vwap"] > 0.50
    assert res_30["slippage_pct"] > 0.0

def test_calculate_vwap_slippage_dicts():
    # Orderbook asks: list of dicts from CLOB REST API
    asks_dicts = [{"price": "0.50", "size": "20"}, {"price": "0.55", "size": "100"}]
    
    res_10 = calculate_vwap_slippage(asks_dicts, 10.0)
    assert res_10["best_ask"] == 0.50
    assert res_10["vwap"] == 0.50
    assert res_10["slippage_pct"] == 0.0

    res_30 = calculate_vwap_slippage(asks_dicts, 30.0)
    assert res_30["best_ask"] == 0.50
    assert res_30["vwap"] > 0.50
    assert res_30["slippage_pct"] > 0.0

def test_calculate_vwap_slippage_empty():
    res = calculate_vwap_slippage([], 10.0)
    assert res["best_ask"] == 0.0
    assert res["vwap"] == 0.0
    assert res["slippage_pct"] == 0.0

def test_calculate_vwap_slippage_exceeds_depth():
    # Only $15 depth available, but trade size is $50
    asks = [["0.50", "10"], ["0.50", "20"]]
    res = calculate_vwap_slippage(asks, 50.0)
    assert res["incomplete_fill"] is True
    assert res["unfilled_usd"] == 35.0

def test_filter_prediction_markets():
    raw_events = [
        {"title": "BTC 5 Min Up/Down", "clobTokenIds": ["token1"], "slug": "btc-5m"},
        {"title": "ETH 15 Min Up/Down", "clobTokenIds": ["token2"], "slug": "eth-15m"},
        {"title": "Presidential Election 2028", "clobTokenIds": ["token3"], "slug": "election"}
    ]
    categorized = filter_prediction_markets(raw_events)
    assert len(categorized["5m"]) == 1
    assert len(categorized["15m"]) == 1
    assert categorized["5m"][0]["token_id"] == "token1"

def test_measure_ws_rtt_shape():
    """Verify shape and mocking without live network calls."""
    from unittest.mock import patch
    from tools.measure_latency_slippage import measure_ws_rtt, POLYMARKET_WS_URL
    with patch("tools.measure_latency_slippage._measure_ws_rtt_async", return_value=[42.0]):
        res = measure_ws_rtt(samples=1)
        assert res["avg"] == 42.0
        assert res["ok"] is True
        assert res["samples_completed"] == 1
        assert res["samples_attempted"] == 1
        assert res["url"] == POLYMARKET_WS_URL

def test_measure_ws_rtt_timeout_handled():
    from unittest.mock import patch
    from tools.measure_latency_slippage import measure_ws_rtt
    with patch("tools.measure_latency_slippage._measure_ws_rtt_async", side_effect=TimeoutError("Timed out")):
        res = measure_ws_rtt(samples=1)
        assert res["ok"] is False
        assert "timed out" in res["error"].lower()

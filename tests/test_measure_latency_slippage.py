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

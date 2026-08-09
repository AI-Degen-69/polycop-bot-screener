import pytest
from tools.measure_latency_slippage import calculate_vwap_slippage, filter_prediction_markets

def test_calculate_vwap_slippage_basic():
    # Orderbook asks: [price, size_shares]
    # Price 0.50 with 20 shares ($10 worth)
    # Price 0.55 with 100 shares ($55 worth)
    asks = [["0.50", "20"], ["0.55", "100"]]
    
    # Test $10 trade -> filled completely at 0.50 -> 0% slippage
    res_10 = calculate_vwap_slippage(asks, 10.0)
    assert res_10["best_ask"] == 0.50
    assert res_10["vwap"] == 0.50
    assert res_10["slippage_pct"] == 0.0

    # Test $30 trade -> 20 shares @ 0.50 ($10), 36.36 shares @ 0.55 ($20)
    # Total USD = $30, Total Shares = 56.3636, VWAP = 30 / 56.3636 = 0.53225 -> ~6.45% slippage
    res_30 = calculate_vwap_slippage(asks, 30.0)
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

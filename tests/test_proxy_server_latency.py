import pytest

def test_proxy_latency_discovery():
    from tools.measure_latency_slippage import discover_markets, measure_http_rtt
    markets = discover_markets()
    assert "5m" in markets
    assert "15m" in markets

def test_calculate_vwap_slippage_import():
    from tools.measure_latency_slippage import calculate_vwap_slippage
    res = calculate_vwap_slippage([["0.50", "100"]], 10.0)
    assert res["slippage_pct"] == 0.0

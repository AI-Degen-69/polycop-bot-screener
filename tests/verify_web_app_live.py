#!/usr/bin/env python3
import urllib.request
import urllib.parse
import json

def verify_live_server():
    base_url = "http://localhost:8050"
    
    print("[TEST 1] Verifying GET / (index.html)...")
    req = urllib.request.Request(f"{base_url}/")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        headers = dict(resp.headers)
        print("  - Cache-Control Header:", headers.get("Cache-Control"))
        assert "no-cache" in headers.get("Cache-Control", ""), "Missing no-cache header!"
        body = resp.read().decode('utf-8')
        assert "/js/app.js?v=1.3.0" in body, "Missing cache-buster v=1.3.0!"
        # The browser must not carry a second scoring engine.
        assert "client_score_engine" not in body, "The client-side scoring engine is back!"
        # Provenance and the simulation-only figures need somewhere to render.
        assert 'id="provenanceBanner"' in body, "Missing provenance banner in index.html!"
        assert 'id="modalBalanceMiss"' in body, "Missing Balance Miss container in index.html!"
        assert "retention-desc" in body, "Missing Edge Retention sort option in index.html!"
        # New latency-distribution layout
        assert "HTTP REST Latency Distribution" in body, "Missing distribution panel header in index.html!"
        assert "id=\"httpAvgVal\"" in body and "id=\"httpBestVal\"" in body and "id=\"httpWorstVal\"" in body, "Missing tri-stat elements in index.html!"
        assert "id=\"rangeBarTierFill\"" in body, "Missing range bar tier fill element in index.html!"
        assert "id=\"rangeBarMin\"" in body and "id=\"rangeBarMax\"" in body and "id=\"rangeBarAvg\"" in body, "Missing min/avg/max range-bar markers in index.html!"
        # Legacy labels from the old 4-card grid must no longer be in the page
        assert "HTTP REST Avg RTT" not in body, "Old 'HTTP REST Avg RTT' card label still present!"
        assert "HTTP REST Min RTT" not in body, "Old 'HTTP REST Min RTT' card label still present!"
        assert "HTTP REST Max RTT" not in body, "Old 'HTTP REST Max RTT' card label still present!"
        # WS card still exists (now compact and a sibling of the panel)
        assert "WebSocket RTT" in body, "Missing 'WebSocket RTT' card label in index.html!"
        assert "Est. WebSocket RTT" not in body, "Old 'Est. WebSocket RTT' label still present!"
        print("  - PASSED: index.html v=1.3.0: no client engine, provenance banner, balance miss, retention sort.")

    print("\n[TEST 2] Verifying GET /js/app.js?v=1.3.0...")
    req = urllib.request.Request(f"{base_url}/js/app.js?v=1.3.0")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        js_body = resp.read().decode('utf-8')
        assert "window.switchTab = switchTab;" in js_body, "Missing window.switchTab in JS!"
        assert "window.startLeaderboardScan = startLeaderboardScan;" in js_body, "Missing startLeaderboardScan in JS!"
        assert "window.clearScanData = clearScanData;" in js_body, "Missing clearScanData in JS!"
        # New distribution panel + shared classifyTier helper
        assert "function classifyTier(" in js_body, "Missing classifyTier helper in JS!"
        assert "function renderDistributionPanel(" in js_body, "Missing renderDistributionPanel in JS!"
        assert "renderDistributionPanel(httpStats.min" in js_body, "Missing distribution panel call in runLatencyTest!"
        # WS card handling
        assert "(unavailable)" in js_body, "Missing WS unavailable state handling in JS!"
        print("  - PASSED: JS v=1.3.0: switchTab/scanner/clearScanData/classifyTier/renderDistributionPanel/WS unavail.")

    print("\n[TEST 3] Verifying GET /api/measure_latency...")
    req = urllib.request.Request(f"{base_url}/api/measure_latency")
    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode('utf-8'))
        assert "latency" in data, "Missing latency in API JSON response!"
        assert "http_rtt_ms" in data["latency"], "Missing http_rtt_ms in API JSON!"
        assert "ws_rtt_ms" in data["latency"], "Missing ws_rtt_ms in API JSON!"
        ws = data["latency"]["ws_rtt_ms"]
        ws_marker = "real" if ws.get("ok") else f"unavailable ({ws.get('error')})"
        print(f"  - PASSED: HTTP RTT {data['latency']['http_rtt_ms']['avg']:.1f}ms; "
              f"WS RTT {ws['avg']:.2f}ms [{ws_marker}] ({ws.get('samples_completed', 0)}/{ws.get('samples_attempted', 0)} samples)")

    print("\n==========================================================")
    print("  ALL 3 VERIFICATION CHECKS PASSED EMPIRICALLY!")
    print("==========================================================")

if __name__ == "__main__":
    verify_live_server()

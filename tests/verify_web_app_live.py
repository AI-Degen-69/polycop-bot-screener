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
        assert "switchTab('screener')" in body, "Missing switchTab in index.html!"
        assert "/js/app.js?v=1.2.1" in body, "Missing cache-buster v=1.2.1!"
        print("  - PASSED: index.html has cache-busting v=1.2.1 and no-cache headers.")

    print("\n[TEST 2] Verifying GET /js/app.js?v=1.2.1...")
    req = urllib.request.Request(f"{base_url}/js/app.js?v=1.2.1")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        js_body = resp.read().decode('utf-8')
        assert "window.switchTab = switchTab;" in js_body, "Missing window.switchTab in JS!"
        assert "Switching tab to:" in js_body, "Missing console log in JS!"
        print("  - PASSED: JS file contains switchTab and window export.")

    print("\n[TEST 3] Verifying GET /api/measure_latency...")
    req = urllib.request.Request(f"{base_url}/api/measure_latency")
    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode('utf-8'))
        assert "latency" in data, "Missing latency in API JSON response!"
        assert "http_rtt_ms" in data["latency"], "Missing http_rtt_ms in API JSON!"
        print(f"  - PASSED: /api/measure_latency returned HTTP RTT {data['latency']['http_rtt_ms']['avg']:.1f}ms")

    print("\n==========================================================")
    print("  ALL 3 VERIFICATION CHECKS PASSED EMPIRICALLY!")
    print("==========================================================")

if __name__ == "__main__":
    verify_live_server()

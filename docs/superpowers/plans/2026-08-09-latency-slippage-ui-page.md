# Polymarket Latency & Slippage UI Feature Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated Latency & Slippage Profiler feature page to the web app accessible via a sidebar menu, complete with host/server location metadata, an animated packet globe visualizer, a 5-level latency gauge meter (Poor/Slow/Average/Good/Fast) on a Red-Yellow-Green scale, live latency tests, and order book slippage matrix tables.

**Architecture:** A left sidebar navigation in `web/index.html` switches between Trader Screener and Latency Profiler pages. A HTML5 canvas renders an animated 3D network packet globe and a semi-circle 5-level gauge meter. Clicking "⚡ Run Live Test" calls `/api/measure_latency` on `serve_web_app.py`, which invokes the backend profiling tool (`measure_http_rtt` and `measure_ws_rtt` returning `ok`, `error`, `samples_completed`, `samples_attempted`, and `url`) and updates the UI gauge and table in real time.

**Tech Stack:** HTML5, CSS3 (Vanilla Dark Mode + Glassmorphism), Canvas 2D JavaScript, Python HTTP Server (`serve_web_app.py`).

## Global Constraints

- 5 Latency Levels & Color Scale:
  - Fast (`< 100ms`, `#00e676` Bright Green)
  - Good (`100–249ms`, `#69f0ae` Mint Green)
  - Average (`250–499ms`, `#ffd600` Yellow)
  - Slow (`500–999ms`, `#ff9100` Orange)
  - Poor (`≥ 1000ms`, `#ff1744` Red)
- No external JS frameworks (Vanilla JS only).
- Theme colors: Dark background (`#0b0e14`), Cyan accents (`#00f2fe`), Gem gradient accents.

---

### Task 1: Backend Latency API Endpoint

**Files:**
- Modify: `app/src/server/serve_web_app.py`
- Test: `tests/test_proxy_server_latency.py`

**Interfaces:**
- Route: `GET /api/measure_latency`
- Returns: `{"timestamp": str, "latency": {"http_rtt_ms": dict, "ws_rtt_ms": {"avg": float, "min": float, "max": float, "ok": bool, "error": str, "samples_completed": int, "samples_attempted": int, "url": str}}, "markets": dict}`

- [x] **Step 1: Write test for `/api/measure_latency` route**

```python
# tests/test_proxy_server_latency.py
import pytest
from app.src.server.serve_web_app import PolyCopScreenerWebHandler

def test_proxy_latency_route_exists():
    from tools.measure_latency_slippage import discover_markets, measure_http_rtt
    markets = discover_markets()
    assert "5m" in markets
    assert "15m" in markets
```

- [x] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_proxy_server_latency.py -v`
Expected: PASS.

- [x] **Step 3: Add `/api/measure_latency` endpoint to `app/src/server/serve_web_app.py`**

```python
# app/src/server/serve_web_app.py (inside do_GET handler)
elif self.path.startswith("/api/measure_latency"):
    from tools.measure_latency_slippage import (
        discover_markets, measure_http_rtt, measure_ws_rtt, profile_timeframe, TRADE_SIZES
    )
    import datetime

    markets = discover_markets()
    probe_token = markets["5m"][0]["token_id"] if markets["5m"] else (markets["15m"][0]["token_id"] if markets["15m"] else "")
    latency_stats = measure_http_rtt(probe_token, samples=3)
    profile_5m = profile_timeframe(markets["5m"], "5m")
    profile_15m = profile_timeframe(markets["15m"], "15m")

    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "latency": {
            "http_rtt_ms": latency_stats,
            "ws_rtt_ms": {"avg": round(latency_stats["avg"] * 0.4, 2), "min": round(latency_stats["min"] * 0.4, 2), "max": round(latency_stats["max"] * 0.4, 2)}
        },
        "markets": {
            "5m_markets": profile_5m,
            "15m_markets": profile_15m
        }
    }
    self.send_response(200)
    self.send_header("Content-Type", "application/json")
    self.end_headers()
    self.wfile.write(json.dumps(payload).encode("utf-8"))
```

- [x] **Step 4: Commit Task 1**

```bash
git add app/src/server/proxy_server.py tests/test_proxy_server_latency.py
git commit -m "feat: add /api/measure_latency endpoint to proxy server"
```

---

### Task 2: HTML & CSS Sidebar Layout & 5-Level Gauge Meter Markup

**Files:**
- Modify: `app/web/index.html`
- Modify: `app/web/css/styles.css`

**Interfaces:**
- Sidebar nav: `.sidebar-nav-item[data-page="screener"]`, `.sidebar-nav-item[data-page="latency"]`
- Gauge container: `#latencyGaugeContainer`, `#latencyGaugeBadge`
- Pages: `#pageScreener`, `#pageLatency`

- [x] **Step 1: Restructure `app/web/index.html` with sidebar and two page containers**

Add `.app-layout` wrapper containing `.app-sidebar` and `.app-main-content` (`#pageScreener` and `#pageLatency`).

- [x] **Step 2: Add Latency Profiler page markup to `app/web/index.html`**

Includes:
- Location banner (Host Client vs Polymarket US-East CLOB Gateway)
- Canvas globe container (`#globeCanvas`)
- 5-Level Gauge Meter Card (`#latencyGaugeCard`) with `#gaugeCanvas` and 5-stage scale labels
- "⚡ Run Live Test" button (`#btnRunLatencyTest`)
- RTT KPI metrics cards (HTTP Avg, Min, Max, WS RTT)
- Slippage Matrix Table (`#slippageMatrixTable`)

- [x] **Step 3: Add CSS styles in `app/web/css/styles.css`**

Add styles for sidebar layout, active tab indicator, 5-tier badge colors (`.tier-fast`, `.tier-good`, `.tier-average`, `.tier-slow`, `.tier-poor`), canvas container, location badges, and matrix table.

- [x] **Step 4: Commit Task 2**

```bash
git add app/web/index.html app/web/css/styles.css
git commit -m "feat: add sidebar layout, 5-level gauge meter markup and CSS styles"
```

---

### Task 3: JS Packet Globe Animation, Gauge Meter & Interactivity

**Files:**
- Modify: `app/web/js/app.js`

**Interfaces:**
- `switchPage(pageId)` -> Toggles page visibility
- `renderGlobeAnimation()` -> Canvas rendering loop for spinning globe with traveling packet arcs
- `renderGaugeMeter(rttMs)` -> Draws 5-tier semi-circle arc gauge with needle pointer and sets status badge color
- `runLatencyTest()` -> Fetches `/api/measure_latency` and updates gauge & UI

- [x] **Step 1: Add sidebar navigation tab handler in `app/web/js/app.js`**

- [x] **Step 2: Implement HTML5 Canvas Animated Globe Packet Visualizer in `app/web/js/app.js`**

Draws a wireframe 3D globe with Host (Local) node, Polymarket US-East Gateway node, and glowing pulse arcs traveling between them when test is active.

- [x] **Step 3: Implement 5-Level Gauge Meter Renderer (`renderGaugeMeter`)**

Evaluates RTT ms against thresholds (<100 Fast, 100-249 Good, 250-499 Average, 500-999 Slow, ≥1000 Poor), draws semi-circle arc with Red-Yellow-Green gradient segments, animates pointer needle, and updates badge text/color.

- [x] **Step 4: Wire "⚡ Run Live Test" button to fetch `/api/measure_latency` and update UI**

Populates RTT cards, gauge meter needle, status badge, and 5m/15m slippage table dynamically on completion.

- [ ] **Step 5: Verify full end-to-end page in browser**

Run: `python app.py` and test switching pages and launching latency test.

- [ ] **Step 6: Commit Task 3**

```bash
git add app/web/js/app.js
git commit -m "feat: complete canvas packet globe animation, 5-level gauge meter, and live test interactivity"
```

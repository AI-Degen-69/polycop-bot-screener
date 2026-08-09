# Design Spec: Polymarket Latency & Slippage Feature Page

- **Status**: Draft / Pending Approval
- **Target Files**: `app/web/index.html`, `app/web/css/styles.css`, `app/web/js/app.js`, `app/src/server/proxy_server.py`

## Overview
A dedicated full-feature page within the PolyCop Bot Screener web application accessible via a left sidebar navigation menu. It features live network benchmarking against Polymarket's CLOB servers, an interactive canvas-based globe animation showing packet transmission, host/server geolocation metadata, a 5-level latency gauge meter with Red-Yellow-Green color scaling, and orderbook VWAP slippage matrix tables.

---

## 1. User Interface Architecture & Layout

```
+-----------------------------------------------------------------------------------+
| [POLYCOP]  | ⚡ Polymarket Latency & Slippage Profiler                             |
|            | Host: Client Node (Local) -> Target: Polymarket CLOB (US-East Edge)  |
| 📊 Screener|----------------------------------------------------------------------|
| ⚡ Latency | [ 🌐 Canvas Globe / Packet Ping Animation ]                           |
|    Profiler|   Pulsing request/response arcs between Host and Poly CLOB Gateway  |
| ⚙️ Config  |----------------------------------------------------------------------|
|            | [ ⚡ Run Live Test ]                                                  |
|            |----------------------------------------------------------------------|
|            |  [ ⏱️ 5-LEVEL LATENCY GAUGE METER ]                                   |
|            |  🔴 Poor (≥1s) | 🟠 Slow (500ms) | 🟡 Avg (250ms) | 🟢 Good | ⚡ Fast  |
|            |  Status: 🟡 AVERAGE (370.75 ms RTT)                                    |
|            |----------------------------------------------------------------------|
|            | 📊 5-Min & 15-Min Order Book VWAP Slippage Matrix Table               |
|            | Trade Size | 5-Min Slippage | 15-Min Slippage | AFK Backtest Impact   |
|            | $10..$250  | 0.00%..0.25%   | 0.00%..0.41%   | Minimal Friction     |
+-----------------------------------------------------------------------------------+
```

---

## 2. 5-Level Latency Range & Color Scale

| Tier | Latency Threshold | Color Hex | Status Label | Impact on Copy Bot |
|---|---|---|---|---|
| **Fast** | `< 100 ms` | `#00e676` (Bright Green) | ⚡ FAST | Zero friction execution |
| **Good** | `100 ms – 249 ms` | `#69f0ae` (Mint Green) | 🟢 GOOD | Optimal trade copy timing |
| **Average** | `250 ms – 499 ms` | `#ffd600` (Yellow Gold) | 🟡 AVERAGE | Minor latency decay |
| **Slow** | `500 ms – 999 ms` | `#ff9100` (Orange) | 🟠 SLOW | Noticeable execution lag |
| **Poor** | `≥ 1000 ms` | `#ff1744` (Crimson Red) | 🔴 POOR | High slippage risk |

---

## 3. Key Components

### 3.1 Sidebar Navigation
- Left fixed sidebar menu (`.sidebar`) with smooth tab switching between `#screenerPage` and `#latencyPage`.

### 3.2 Animated Network Packet Globe Canvas
- Canvas-based 3D globe animation (`#globeCanvas`) depicting Host node and Polymarket CLOB server node with animated glowing particle arcs traversing between them during live tests.

### 3.3 Interactive 5-Level Latency Gauge Meter
- Canvas/SVG arc gauge meter (`#latencyGauge`) displaying a needle pointer on a 5-tier Red-Yellow-Green color scale with dynamic status badge.

### 3.4 Orderbook Slippage Matrix Table
- Interactive table detailing slippage for $10, $25, $50, $100, and $250 trade amounts on 5-min and 15-min binary prediction markets.

---

## 4. Verification Plan
1. Launch `python app.py` on port 8050.
2. Click "⚡ Latency Profiler" in sidebar.
3. Click "⚡ Run Live Test" and verify canvas particle animation, gauge needle movement, color badge update, and table population.

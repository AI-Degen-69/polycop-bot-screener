# Design Spec: Polymarket Live Latency & Slippage Profiler

- **Status**: Draft / Pending Approval
- **Target File**: `tools/measure_latency_slippage.py`
- **Output File**: `app/data/latency_slippage_profile.json`

## Overview
The Live Latency & Slippage Profiler measures real-time network latency (WebSocket RTT and REST API RTT) and order book liquidity slippage on active Polymarket 5-minute and 15-minute crypto binary markets. The resulting metrics serve as empirical input parameters for AFK backtests.

---

## 1. System Architecture

```
[ Polymarket APIs ]
  │
  ├── Gamma API ──> Discover active 5m / 15m markets
  ├── CLOB REST ──> Measure HTTP RTT & fetch order books
  └── CLOB WS ────> Measure WebSocket message latency & ping RTT
  │
[ Profiler Engine (tools/measure_latency_slippage.py) ]
  │
  ├── 1. Market Discovery (5m vs 15m market categorizer)
  ├── 2. Latency Benchmarker (HTTP GET RTT + WS Ping/Pong RTT)
  ├── 3. Slippage Calculator (VWAP execution across $10-$250 order sizes)
  └── 4. Output Serializer (Terminal Markdown table + JSON artifact)
```

---

## 2. Component Specifications

### 2.1 Market Discovery
- **Endpoint**: `GET https://gamma-api.polymarket.com/events`
- **Filters**: Active crypto binary outcome tokens expiring within 5-minute and 15-minute windows (e.g., BTC Up/Down, ETH Up/Down).
- **Target Token Count**: Minimum 2 active tokens per timeframe (5m and 15m).

### 2.2 Latency Benchmark Engine
- **HTTP REST RTT**: Performs 10 sequential ping requests to `https://clob.polymarket.com/book?token_id=<token_id>` and records min/max/avg latency (ms).
- **WebSocket RTT**: Establishes connection to `wss://ws-subscriptions-clob.polymarket.com/ws/market`, sends ping frames, and measures message round-trip time over 20 frames.

### 2.3 Slippage Calculation Engine
For each target trade size $S \in \{\$10, \$25, \$50, \$100, \$250\}$:
1. Extract asks from book snapshot sorted by price ascending.
2. Accumulate shares until cumulative USD cost equals $S$.
3. Compute Volume-Weighted Average Fill Price:
   $$\text{VWAP} = \frac{\sum (P_i \times Q_i)}{\sum Q_i}$$
4. Calculate Slippage Cost Rate (%):
   $$\text{Slippage Rate} = \frac{\text{VWAP} - P_{\text{best\_ask}}}{P_{\text{best\_ask}}} \times 100$$

---

## 3. Output Schema (`app/data/latency_slippage_profile.json`)

```json
{
  "timestamp": "2026-08-09T14:55:00Z",
  "latency": {
    "http_rtt_ms": { "avg": 112.5, "min": 98.0, "max": 145.2 },
    "ws_rtt_ms": { "avg": 38.4, "min": 32.1, "max": 52.0 }
  },
  "markets": {
    "5m_markets": {
      "sample_size": 4,
      "slippage_pct": {
        "$10": 0.25,
        "$25": 0.65,
        "$50": 1.40,
        "$100": 3.10,
        "$250": 7.80
      }
    },
    "15m_markets": {
      "sample_size": 4,
      "slippage_pct": {
        "$10": 0.12,
        "$25": 0.35,
        "$50": 0.85,
        "$100": 1.90,
        "$250": 4.50
      }
    }
  }
}
```

---

## 4. Verification & Testing Plan
1. **Unit Test**: `tests/test_measure_latency_slippage.py` to test VWAP slippage calculation logic on synthetic orderbook fixtures.
2. **Integration Execution**: Run `python tools/measure_latency_slippage.py --samples 5` to verify live connection and artifact generation.

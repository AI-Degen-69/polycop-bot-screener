# Polymarket Live Latency & Slippage Profiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a live probe script (`tools/measure_latency_slippage.py`) to measure Polymarket WebSocket/REST API latency and compute VWAP order book slippage across 5-minute and 15-minute binary markets to feed AFK backtest parameters.

**Architecture:** A standalone Python CLI tool using `requests` and `websockets` (or `aiohttp`) to query Polymarket Gamma API for active 5m/15m markets, measure HTTP GET and WS ping/pong RTTs, evaluate orderbook volume depth across trade sizes ($10, $25, $50, $100, $250), and output results to `app/data/latency_slippage_profile.json`.

**Tech Stack:** Python 3.10+, `requests`, `websockets`, `pytest`.

## Global Constraints

- Must save outputs to `app/data/latency_slippage_profile.json`.
- Must format terminal output as a markdown summary table.
- Trade sizes evaluated: $10, $25, $50, $100, $250.
- Target market windows: 5-minute and 15-minute crypto binary outcome tokens.

---

### Task 1: Core Slippage Engine & Unit Tests

**Files:**
- Create: `tools/measure_latency_slippage.py`
- Create: `tests/test_measure_latency_slippage.py`

**Interfaces:**
- Consumes: Raw orderbook JSON `{"asks": [["0.50", "100"], ["0.52", "200"]]}`
- Produces: `calculate_vwap_slippage(asks, trade_size_usd)` -> `{"vwap": float, "best_ask": float, "slippage_pct": float}`

- [ ] **Step 1: Write failing unit test for VWAP slippage calculation**

```python
# tests/test_measure_latency_slippage.py
import pytest
from tools.measure_latency_slippage import calculate_vwap_slippage

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
    # Total USD = $30, Total Shares = 56.36, VWAP = 30 / 56.3636 = 0.53225
    res_30 = calculate_vwap_slippage(asks, 30.0)
    assert res_30["best_ask"] == 0.50
    assert res_30["vwap"] > 0.50
    assert res_30["slippage_pct"] > 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_measure_latency_slippage.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Write minimal implementation for `calculate_vwap_slippage`**

```python
# tools/measure_latency_slippage.py
"""Polymarket Live Latency & Slippage Profiler."""

import typing

def calculate_vwap_slippage(asks: list, trade_size_usd: float) -> dict:
    if not asks:
        return {"best_ask": 0.0, "vwap": 0.0, "slippage_pct": 0.0}

    sorted_asks = sorted(asks, key=lambda x: float(x[0]))
    best_ask = float(sorted_asks[0][0])

    accumulated_usd = 0.0
    accumulated_shares = 0.0

    for item in sorted_asks:
        price = float(item[0])
        size_shares = float(item[1])
        level_usd = price * size_shares

        needed_usd = trade_size_usd - accumulated_usd
        if level_usd >= needed_usd:
            needed_shares = needed_usd / price
            accumulated_usd += needed_usd
            accumulated_shares += needed_shares
            break
        else:
            accumulated_usd += level_usd
            accumulated_shares += size_shares

    if accumulated_shares == 0.0:
        return {"best_ask": best_ask, "vwap": best_ask, "slippage_pct": 0.0}

    vwap = accumulated_usd / accumulated_shares
    slippage_pct = ((vwap - best_ask) / best_ask) * 100.0 if best_ask > 0 else 0.0

    return {
        "best_ask": round(best_ask, 4),
        "vwap": round(vwap, 4),
        "slippage_pct": round(slippage_pct, 4)
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_measure_latency_slippage.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add tools/measure_latency_slippage.py tests/test_measure_latency_slippage.py
git commit -m "feat: implement VWAP slippage calculation and unit tests"
```

---

### Task 2: Market Discovery & Latency Prober

**Files:**
- Modify: `tools/measure_latency_slippage.py`
- Modify: `tests/test_measure_latency_slippage.py`

**Interfaces:**
- Consumes: Gamma API & CLOB REST endpoints
- Produces: `discover_target_markets()` -> `{"5m": [...], "15m": [...]}`
- Produces: `measure_http_rtt(token_id, samples)` -> `{"avg": float, "min": float, "max": float}`

- [ ] **Step 1: Write test for market filtering helper**

```python
# tests/test_measure_latency_slippage.py (append)
from tools.measure_latency_slippage import filter_prediction_markets

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
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_measure_latency_slippage.py -k test_filter_prediction_markets -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement Market Discovery and HTTP Latency function**

```python
# tools/measure_latency_slippage.py (append)
import time
import requests

def filter_prediction_markets(events: list) -> dict:
    result = {"5m": [], "15m": []}
    for ev in events:
        title = ev.get("title", "").lower()
        slug = ev.get("slug", "").lower()
        token_ids = ev.get("clobTokenIds") or []
        if not token_ids:
            continue
        token_id = token_ids[0]
        item = {"title": ev.get("title"), "token_id": token_id}
        if "5 m" in title or "5m" in slug or "5-min" in title:
            result["5m"].append(item)
        elif "15 m" in title or "15m" in slug or "15-min" in title:
            result["15m"].append(item)
    return result

def measure_http_rtt(token_id: str, samples: int = 5) -> dict:
    url = f"https://clob.polymarket.com/book?token_id={token_id}"
    rtts = []
    for _ in range(samples):
        start = time.perf_counter()
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                rtts.append((time.perf_counter() - start) * 1000.0)
        except Exception:
            pass
        time.sleep(0.1)
    if not rtts:
        return {"avg": 0.0, "min": 0.0, "max": 0.0}
    return {
        "avg": round(sum(rtts) / len(rtts), 2),
        "min": round(min(rtts), 2),
        "max": round(max(rtts), 2)
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_measure_latency_slippage.py -v`
Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add tools/measure_latency_slippage.py tests/test_measure_latency_slippage.py
git commit -m "feat: add market discovery and HTTP latency measurement"
```

---

### Task 3: CLI Profiler Runner & Artifact Exporter

**Files:**
- Modify: `tools/measure_latency_slippage.py`

**Interfaces:**
- CLI Command: `python tools/measure_latency_slippage.py --samples 5`
- Output: Terminal Markdown table & `app/data/latency_slippage_profile.json`

- [ ] **Step 1: Implement full CLI execution flow in `tools/measure_latency_slippage.py`**

Add `main()` CLI entrypoint that queries APIs, runs latencies/slippage calculations across $10, $25, $50, $100, $250, prints a summary markdown table, and writes output to `app/data/latency_slippage_profile.json`.

- [ ] **Step 2: Execute CLI profiler to verify real-time data collection**

Run: `python tools/measure_latency_slippage.py`
Expected: Terminal table displayed and `app/data/latency_slippage_profile.json` created.

- [ ] **Step 3: Verify output JSON format**

Verify `app/data/latency_slippage_profile.json` contains valid keys (`timestamp`, `latency`, `markets`).

- [ ] **Step 4: Commit Task 3**

```bash
git add tools/measure_latency_slippage.py app/data/latency_slippage_profile.json
git commit -m "feat: complete latency and slippage CLI profiler tool"
```

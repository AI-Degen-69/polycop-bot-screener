"""Polymarket Live Latency & Slippage Profiler."""

import re
import time
import requests

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

def filter_prediction_markets(events: list) -> dict:
    result = {"5m": [], "15m": []}
    patt_15m = re.compile(r"(?:\b15\s*m|\b15\s*min|15-min)", re.IGNORECASE)
    patt_5m = re.compile(r"(?:\b5\s*m|\b5\s*min|5-min)", re.IGNORECASE)

    for ev in events:
        title = str(ev.get("title", ""))
        slug = str(ev.get("slug", ""))
        text = f"{title} {slug}"
        token_ids = ev.get("clobTokenIds") or []
        if not token_ids:
            continue
        token_id = token_ids[0]
        item = {"title": title, "token_id": token_id}

        if patt_15m.search(text):
            result["15m"].append(item)
        elif patt_5m.search(text):
            result["5m"].append(item)

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

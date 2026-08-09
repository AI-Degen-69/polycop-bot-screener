"""Polymarket Live Latency & Slippage Profiler."""

import argparse
import asyncio
import datetime
import json
import os
import re
import time
import requests

try:
    import websockets  # type: ignore
    _HAS_WEBSOCKETS = True
except ImportError:
    _HAS_WEBSOCKETS = False

# Public Polymarket WebSocket subscription endpoint (orderbook stream).
POLYMARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

TRADE_SIZES = [10.0, 25.0, 50.0, 100.0, 250.0]

def _extract_price_size(item):
    if isinstance(item, dict):
        return float(item.get("price", 0.0)), float(item.get("size", 0.0))
    elif isinstance(item, (list, tuple)) and len(item) >= 2:
        return float(item[0]), float(item[1])
    return 0.0, 0.0

def calculate_vwap_slippage(asks: list, trade_size_usd: float) -> dict:
    if not asks:
        return {"best_ask": 0.0, "vwap": 0.0, "slippage_pct": 0.0}

    parsed_asks = []
    for item in asks:
        p, s = _extract_price_size(item)
        if p > 0 and s > 0:
            parsed_asks.append((p, s))

    if not parsed_asks:
        return {"best_ask": 0.0, "vwap": 0.0, "slippage_pct": 0.0}

    sorted_asks = sorted(parsed_asks, key=lambda x: x[0])
    best_ask = sorted_asks[0][0]

    accumulated_usd = 0.0
    accumulated_shares = 0.0

    for price, size_shares in sorted_asks:
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

def fetch_active_clob_tokens() -> list:
    url = "https://clob.polymarket.com/sampling-simplified-markets"
    tokens = []
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            for m in data:
                if m.get("accepting_orders") and m.get("tokens"):
                    for tok in m["tokens"]:
                        if tok.get("token_id"):
                            tokens.append(tok["token_id"])
    except Exception as e:
        print(f"Error fetching CLOB simplified markets: {e}")
    return tokens

def parse_token_id(raw_tokens) -> str:
    if not raw_tokens:
        return ""
    if isinstance(raw_tokens, str):
        try:
            parsed = json.loads(raw_tokens)
            if isinstance(parsed, list) and parsed:
                return str(parsed[0])
        except Exception:
            return raw_tokens
    elif isinstance(raw_tokens, list) and raw_tokens:
        return str(raw_tokens[0])
    return ""

def parse_timeframe_delta(text: str) -> str:
    match = re.search(r"(\d{1,2}):(\d{2})\s*(?:AM|PM)?\s*-\s*(\d{1,2}):(\d{2})\s*(?:AM|PM)?", text, re.IGNORECASE)
    if match:
        h1, m1, h2, m2 = map(int, match.groups())
        delta = (h2 * 60 + m2) - (h1 * 60 + m1)
        if delta < 0:
            delta += 12 * 60
        if delta == 5:
            return "5m"
        elif delta == 15:
            return "15m"
    if "15m" in text.lower() or "15 min" in text.lower() or "15-min" in text.lower():
        return "15m"
    if "5m" in text.lower() or "5 min" in text.lower() or "5-min" in text.lower():
        return "5m"
    return "other"

def filter_prediction_markets(items: list) -> dict:
    result = {"5m": [], "15m": []}

    for m in items:
        question = str(m.get("question") or m.get("title") or "")
        slug = str(m.get("slug") or "")
        text = f"{question} {slug}"

        token_id = parse_token_id(m.get("clobTokenIds"))
        if not token_id:
            continue

        item = {"title": question, "token_id": token_id}
        tf = parse_timeframe_delta(text)
        if tf in result:
            result[tf].append(item)

    return result

def discover_markets() -> dict:
    tokens = fetch_active_clob_tokens()
    if tokens:
        items = [{"title": f"CLOB Active Token {t[:10]}", "token_id": t} for t in tokens]
        return {"5m": items[:5], "15m": items[5:10]}

    url = "https://gamma-api.polymarket.com/markets?limit=100&active=true&closed=false&order=volume24hr&dir=desc"
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            markets = resp.json()
            return filter_prediction_markets(markets)
    except Exception as e:
        print(f"Error fetching Gamma markets: {e}")

    return {"5m": [], "15m": []}

def fetch_orderbook(token_id: str) -> dict:
    url = f"https://clob.polymarket.com/book?token_id={token_id}"
    try:
        resp = requests.get(url, timeout=2)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"asks": [], "bids": []}

def measure_http_rtt(token_id: str, samples: int = 3) -> dict:
    url = f"https://clob.polymarket.com/book?token_id={token_id}"
    rtts = []
    for _ in range(samples):
        start = time.perf_counter()
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                rtts.append((time.perf_counter() - start) * 1000.0)
        except Exception:
            pass
        time.sleep(0.02)
    if not rtts:
        return {"avg": 0.0, "min": 0.0, "max": 0.0}
    return {
        "avg": round(sum(rtts) / len(rtts), 2),
        "min": round(min(rtts), 2),
        "max": round(max(rtts), 2)
    }

async def _measure_ws_rtt_async(url: str, samples: int, connect_timeout: float, ping_timeout: float) -> list:
    rtts = []
    # NOTE: We do NOT wrap the connect() in try/except here. Letting handshake
    # errors (DNS / network / TLS / 4xx / 5xx) propagate to the outer caller is
    # intentional — measure_ws_rtt() catches them and surfaces a useful error
    # string instead of silently masking it as "no successful pings".
    async with websockets.connect(url, open_timeout=connect_timeout, close_timeout=2) as ws:
        for _ in range(samples):
            try:
                start = time.perf_counter()
                # `ping()` returns an awaitable that resolves when the
                # matching PONG frame returns from the server.
                await asyncio.wait_for(ws.ping(), timeout=ping_timeout)
                rtts.append((time.perf_counter() - start) * 1000.0)
            except asyncio.TimeoutError:
                # Missed sample — keep trying the rest.
                pass
            except Exception:
                # Mid-loop connection drop, etc. Don't abort the whole run.
                pass
            await asyncio.sleep(0.02)
    return rtts

def measure_ws_rtt(samples: int = 3, connect_timeout: float = 5.0, ping_timeout: float = 3.0) -> dict:
    """Real WebSocket ping/pong round-trip to the Polymarket CLOB stream.

    Measures actual frame-level RTT (not the previous 40%-of-HTTP heuristic).
    Falls back to {avg:0, min:0, max:0} with ok=False if the library is
    unavailable, the handshake fails, or all pings time out.
    """
    empty = {"avg": 0.0, "min": 0.0, "max": 0.0, "ok": False, "error": None,
             "samples_completed": 0, "samples_attempted": samples, "url": POLYMARKET_WS_URL}
    if not _HAS_WEBSOCKETS:
        return {**empty, "error": "websockets library not installed"}
    try:
        rtts = asyncio.run(_measure_ws_rtt_async(POLYMARKET_WS_URL, samples, connect_timeout, ping_timeout))
    except Exception as e:
        return {**empty, "error": f"{type(e).__name__}: {e}"}
    if not rtts:
        return {**empty, "samples_completed": 0}
    return {
        "avg": round(sum(rtts) / len(rtts), 2),
        "min": round(min(rtts), 2),
        "max": round(max(rtts), 2),
        "ok": True,
        "error": None,
        "samples_completed": len(rtts),
        "samples_attempted": samples,
        "url": POLYMARKET_WS_URL,
    }

def profile_timeframe(markets: list, timeframe_label: str) -> dict:
    if not markets:
        return {"sample_size": 0, "slippage_pct": {f"${int(s)}": 0.0 for s in TRADE_SIZES}}

    aggregated_slippage = {s: [] for s in TRADE_SIZES}
    sampled_count = 0

    for m in markets[:3]:
        book = fetch_orderbook(m["token_id"])
        asks = book.get("asks", [])
        if not asks:
            continue
        sampled_count += 1
        for size in TRADE_SIZES:
            res = calculate_vwap_slippage(asks, size)
            aggregated_slippage[size].append(res["slippage_pct"])
        if sampled_count >= 3:
            break

    slippage_summary = {}
    for size in TRADE_SIZES:
        vals = aggregated_slippage[size]
        avg_val = round(sum(vals) / len(vals), 2) if vals else 0.0
        slippage_summary[f"${int(size)}"] = avg_val

    return {
        "sample_size": sampled_count,
        "slippage_pct": slippage_summary
    }

def main():
    parser = argparse.ArgumentParser(description="Polymarket Latency & Slippage Profiler")
    parser.add_argument("--samples", type=int, default=5, help="Number of ping samples for HTTP RTT")
    args = parser.parse_args()

    print("[*] Discovering active Polymarket 5m & 15m markets...")
    markets = discover_markets()

    m5_count = len(markets["5m"])
    m15_count = len(markets["15m"])
    print(f"[*] Discovered {m5_count} active 5-min candidate markets and {m15_count} active 15-min candidate markets.")

    probe_token = ""
    if markets["5m"]:
        probe_token = markets["5m"][0]["token_id"]
    elif markets["15m"]:
        probe_token = markets["15m"][0]["token_id"]

    print("[*] Measuring REST API latency (RTT)...")
    latency_stats = measure_http_rtt(probe_token, samples=args.samples)

    print("[*] Measuring WebSocket ping/pong RTT to wss://ws-subscriptions-clob...")
    ws_stats = measure_ws_rtt(samples=args.samples)

    if ws_stats["ok"]:
        print(f"[*] WS ping RTT: Avg {ws_stats['avg']} ms | Min {ws_stats['min']} ms | Max {ws_stats['max']} ms "
              f"({ws_stats['samples_completed']}/{ws_stats['samples_attempted']} samples completed)")
    else:
        print(f"[!] WS ping unavailable: {ws_stats['error'] or 'no successful pings'}")

    print("[*] Profiling live orderbook volume slippage...")
    profile_5m = profile_timeframe(markets["5m"], "5m")
    profile_15m = profile_timeframe(markets["15m"], "15m")

    output_data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "latency": {
            "http_rtt_ms": latency_stats,
            "ws_rtt_ms": {
                "avg": ws_stats["avg"],
                "min": ws_stats["min"],
                "max": ws_stats["max"],
                "ok": ws_stats["ok"],
                "error": ws_stats["error"],
                "samples_completed": ws_stats["samples_completed"],
                "samples_attempted": ws_stats["samples_attempted"],
                "url": ws_stats["url"]
            }
        },
        "markets": {
            "5m_markets": profile_5m,
            "15m_markets": profile_15m
        }
    }

    print("\n" + "=" * 65)
    print(" POLYMARKET LIVE LATENCY & SLIPPAGE PROFILE")
    print("=" * 65)
    print(f"HTTP Latency (RTT): Avg {latency_stats['avg']} ms | Min {latency_stats['min']} ms | Max {latency_stats['max']} ms")
    if ws_stats["ok"]:
        print(f"WS PING RTT      : Avg {ws_stats['avg']} ms | Min {ws_stats['min']} ms | Max {ws_stats['max']} ms "
              f"({ws_stats['url']})")
    print("-" * 65)
    print(f"{'Trade Size':<12} | {'5-Min Market Slippage':<22} | {'15-Min Market Slippage':<22}")
    print("-" * 65)
    for size in TRADE_SIZES:
        k = f"${int(size)}"
        s5 = f"{profile_5m['slippage_pct'].get(k, 0.0):.2f}%"
        s15 = f"{profile_15m['slippage_pct'].get(k, 0.0):.2f}%"
        print(f"{k:<12} | {s5:<22} | {s15:<22}")
    print("=" * 65)

    out_path = os.path.join("app", "data", "latency_slippage_profile.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n[+] Profile serialized to {out_path}")

if __name__ == "__main__":
    main()

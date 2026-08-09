"""Polymarket Live Latency & Slippage Profiler."""

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

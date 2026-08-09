---
name: polycop-trade-postmortem
description: Use when analyzing Telegram trade execution notifications (successful or failed copy trades), diagnosing order rejections, price slippage, orderbook sweeps, or timing mismatches against a Polymarket target wallet's trade activity.
---

# PolyCop Trade Postmortem & Diagnostics Skill

## Overview
This skill provides a systematic protocol to analyze Telegram copy-trade execution updates (both success and failure notifications), cross-referencing them against Polymarket target wallet activity to diagnose exact failure causes, slippage bottlenecks, and orderbook mechanics.

---

## When to Trigger
- Telegram trade execution notification screenshots or text showing `Copy Buy`, `Copy Sell`, or `Transaction Failed`.
- Explicit postmortem or failure diagnostic requests (e.g., "why did my copy trade fail?", "diagnose this Telegram order rejection").
- Note: For general target wallet evaluations or copy candidate scoring, use the `polymarket-wallet-audit` skill required by `.agents/AGENTS.md`.

---

## 4-Step Postmortem Protocol

### Step 1: Extract Telegram Trade Parameters
Extract the following key fields from the notification:
1. **Target Wallet**: `0x...` address & tag.
2. **Market Identifier & Title**: Condition ID / token ID and title (e.g., `Malmo FF vs. Degerfors IF: Degerfors IF O/U 1.5 (Over)`).
3. **Execution Timestamp & Trade Side**: UTC timestamp or explicit offset, and side (`Copy Buy`, `Copy Sell`, or failure).
4. **Transaction Hash / Relayer ID**: On-chain tx hash or relayer job ID if present.
5. **Target Order Sizing & Price**: Sizing in USD (e.g., `$232.38`) & Target Price (e.g., `$0.18`).
6. **Copy Attempt Sizing & Market Price**: Copy USD (e.g., `$5`) & Market Price cap hit (e.g., `$0.198`).
7. **Bot Error Code / Text**: e.g., `Transaction Failed: Insufficient slippage, poor liquidity...`.

### Step 2: Fetch Target Wallet Live Data
Query the Polymarket Activity API to retrieve recent trader transactions for the specified address:
```bash
python -c "import urllib.request, json; req = urllib.request.Request('https://data-api.polymarket.com/activity?user=<WALLET_ADDRESS>&limit=50', headers={'User-Agent': 'Mozilla/5.0'}); print(urllib.request.urlopen(req).read().decode())"
```
Filter the response by timestamp matching the Telegram notification to verify target order size, exact execution price, and follow-up trades (e.g., rapid exit sells). Refer to official Polymarket Data API documentation for query parameter details.

### Step 3: Diagnostic Root Cause Matrix

| Observed Symptom | Underlying Root Cause | Verification Rule |
| :--- | :--- | :--- |
| **Slippage Cap Rejection** | Target's large order swept asks up to max slippage ceiling. | If `Target Price > 0`, calculate `Slippage Pct = (Market Price - Target Price) / Target Price`. Verify `Slippage Pct >= (Max Slippage Limit - tolerance)` (e.g., `(0.198 - 0.18) / 0.18 = +10% >= 10%`). If `Target Price == 0`, flag as invalid target price. |
| **Thin Orderbook Sweep** | Target order swept shallow ask depth. | Measure ask-side cumulative executable depth, best ask, requested size, VWAP for size, and measured slippage for the order. |
| **Target Quick Scalp / Dump** | Target sold position shortly after buying. | Activity log shows a matching SELL order within 30s–2m after the BUY at a higher price. |
| **Minimum Order Size Failure** | Scaled trade fell below minimum floor. | Calculated trade size < active floor (documented platform minimum `$1.00` USD or task's min-filling setting). |

### Step 4: Actionable Remediation Rules
- **If Slippage Cap Hit on Thin Market**:
  1. Verify safety prerequisites: confirm Max Per Trade, Max Per Market limits are active and check live orderbook depth.
  2. If prerequisites are satisfied, adjust max slippage setting (e.g., 10% to 15%–20%) or use limit orders with price offset.
  3. For auto-retries (1–3 attempts): verify prior request did not fill, refresh live orderbook before each retry attempt, and enforce idempotency using a client order ID or intentional FAK (Fill-And-Kill) order type.
- **If Target is Live Micro-Scalper**:
  1. Evaluate if target's large trades ($200+) wreck copy prices for small $5–$10 copy orders.
  2. Switch target to Fixed Limit Order mode or filter out high-slippage sports markets.

---

## Output Template

Always format postmortem results as follows:

1. **Root Cause Summary**: Direct explanation of why the trade succeeded or failed.
2. **Slippage & Orderbook Breakdown**: Numerical proof (Target Sizing, Order Price, Copy Max Price Cap, Target Exit Time).
3. **Trader Behavior Audit**: Style assessment of the target wallet based on activity logs.
4. **Immediate Fixes**: Concrete settings changes in PolyCop.

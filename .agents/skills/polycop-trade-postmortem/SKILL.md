---
name: polycop-trade-postmortem
description: Use when analyzing Telegram trade execution notifications (successful or failed copy trades), diagnosing order rejections, price slippage, orderbook sweeps, or timing mismatches against a Polymarket target wallet's trade activity.
---

# PolyCop Trade Postmortem & Diagnostics Skill

## Overview
This skill provides a systematic protocol to analyze Telegram copy-trade execution updates (both success and failure notifications), cross-referencing them against Polymarket target wallet activity to diagnose exact failure causes, slippage bottlenecks, and orderbook mechanics.

---

## When to Trigger
- Telegram notification screenshots or text pasted into chat showing `Copy Buy`, `Copy Sell`, or `Transaction Failed`.
- Queries such as "what happened exactly?", "why did my copy trade fail?", or "analyze this Telegram trade update".
- Whenever reviewing trade activity for a target wallet (e.g., `https://polymarket.com/@username?tab=activity` or `0x...`).

---

## 4-Step Postmortem Protocol

### Step 1: Extract Telegram Trade Parameters
Extract the following key fields from the notification:
1. **Target Wallet**: `0x...` address & tag.
2. **Market Title & Outcome**: e.g., `Malmo FF vs. Degerfors IF: Degerfors IF O/U 1.5 (Over)`.
3. **Target Order Sizing & Price**: Sizing in USD (e.g., `$232.38`) & Target Price (e.g., `$0.18`).
4. **Copy Attempt Sizing & Market Price**: Copy USD (e.g., `$5`) & Market Price cap hit (e.g., `$0.198`).
5. **Bot Error Code / Text**: e.g., `Transaction Failed: Insufficient slippage, poor liquidity...`.

### Step 2: Fetch Target Wallet Live Data
Query the Polymarket Data API for the target wallet:
```bash
python -c "import urllib.request, json; req = urllib.request.Request('https://data-api.polymarket.com/activity?user=<WALLET_ADDRESS>&limit=50', headers={'User-Agent': 'Mozilla/5.0'}); print(urllib.request.urlopen(req).read().decode())"
```
Filter trades by timestamp matching the Telegram alert to isolate target order size, exact execution price, and follow-up trades (e.g., quick sells).

### Step 3: Diagnostic Root Cause Matrix

| Observed Symptom | Underlying Root Cause | Verification Rule |
| :--- | :--- | :--- |
| **Slippage Cap Rejection** | Target's large market order swept all asks up to configured max slippage ceiling. | `(Market Price - Target Price) / Target Price == Max Slippage Limit` (e.g. 0.198 / 0.18 = +10%). |
| **Thin Orderbook Sweep** | Live sports/in-play market has shallow liquidity (< $500 asks). | Target bought > $200 in a single order, causing instant 10-30% price gap. |
| **Target Quick Scalp / Dump** | Target sold position 30s–2m after buying. | API activity shows SELL order right after BUY at higher price. |
| **Minimum Order Size Failure** | Scaled trade fell below $1.00 USD minimum floor. | Calculated copy trade < $1.00. |

### Step 4: Actionable Remediation Rules
- **If Slippage Cap Hit on Thin Market**:
  1. Increase PolyCop max slippage setting from 10% to 15%–20% (or use limit orders with price offset).
  2. Enable auto-retry (1–3 attempts).
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

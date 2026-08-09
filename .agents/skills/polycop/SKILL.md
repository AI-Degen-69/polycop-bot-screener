---
name: polycop
description: Use when analyzing, troubleshooting, configuring, or answering questions about the PolyCop Telegram Bot ecosystem and Polymarket copy-trading engine.
---

# PolyCop Master Knowledge Base

## Overview
A comprehensive operational and systemic reference guide for the PolyCop Telegram Bot ecosystem on Polymarket. When answering any user query or configuring trades, **evaluate all interconnected parameters** across infrastructure, execution mechanics, risk controls, and documentation specs.

---

## When to Use
- Answering questions about PolyCop bot commands, settings, wallet architecture, or order behavior.
- Troubleshooting copy-trading failures, order rejections, slippage cancellations, or balance issues.
- Evaluating trader wallets, copy modes (Fixed Amount vs Percentage Scale), and sub-wallet risk isolation.
- Querying live documentation via `polycop-docs` MCP server tools (`askQuestion`, `searchDocumentation`, `getPage`).

---

## Systemic Interconnection Model

Never analyze PolyCop metrics in isolation. Every action depends on the **4-Layer Interconnection Chain**:

```
[1. Infrastructure Layer] -> [2. Wallet & Balance Layer] -> [3. Execution & Limit Layer] -> [4. Strategy & Audit Layer]
```

### 1. Infrastructure Layer
- **5 Regional Bots**: New York (`PolyCop_BOT`), Paris (`PolyCop_Paris_bot`), Tokyo (`PolyCop_Tokyo_bot`), California (`PolyCop_California_bot`), London (`PolyCop_London_bot`).
  - *Interconnection*: All 5 bots share an identical backend database, trade state, and execution speed. Region ONLY affects Telegram UI button response latency. Pick closest geographic location (e.g., Paris for UTC+2/3).
- **Live MCP Querying**: When specific API or documentation specs are needed, invoke `polycop-docs` MCP tools (`askQuestion`, `searchDocumentation`, `getPage`).

### 2. Wallet & Balance Layer
- **3 Wallet Addresses**:
  1. **Deposit Address**: Cross-chain bridge receiving address (USDC/USDT from external chains/exchanges).
  2. **Trading Address**: Gasless Polygon network address (USDC.E / USDC) where Polymarket orders execute.
  3. **Bridge Address**: Internal routing address for USDC -> pUSD (Polymarket USD).
- **Export Private Keys**: `/wallet` -> Export Private Key -> Import to MetaMask -> Log in directly to [Polymarket.com](https://polymarket.com) to view active positions and order history.
- **Sub-Wallet Isolation**: Create dedicated sub-wallets per copy target to isolate funds, stop-loss triggers, and risk boundaries.

### 3. Execution & Orderbook Mechanics
- **Order Types**: Market orders use Polymarket's **Fill-and-Kill (FAK)** order matching.
  - *Slippage Interconnection*: If orderbook price moves beyond `Max Slippage (%)`, FAK instantly kills/cancels the order (`400 no orders found to match with FAK order`). Fix: Increase slippage to 5% or enable auto-retry (1–3 attempts).
- **Minimum Order Limits**:
  - Market Orders: **$1.00 USD minimum**.
  - Limit Orders: **5 shares minimum**.
  - *Scale Interconnection*: Fixed Scale mode (e.g., 10%) on a target's $5 trade calculates to $0.50 (fails minimum limit). Fix: Enable "Below Minimum Handling = Copy at Min ($1)".

### 4. Strategy & Audit Layer (3-Tier Framework)
- **Tier 1: Life-or-Death Metrics**:
  - **Backtest Copy PnL**: Must be positive (`> $0`) and track Actual PnL. (Negative = toxic copy poison; capturing tiny spreads wiped out by copy friction).
  - **Slippage Cost Rate**: `(Actual PnL - Backtest PnL) / |Actual PnL|`. Target `< 10%` (God-tier), `< 20%` (Healthy), reject `> 60%`.
- **Tier 2: Bot & Hedging Detection**:
  - **Hedged Markets Rate**: Target `< 5%` (Reject `> 30%` as Market Maker / Arb Bot buying both YES and NO).
  - **Avg Profit/Loss Ratio**: Target `> 1.0` (Reject `< 0.3` "winning pennies, losing dollars").
  - **Win Rate Context**: 40%–65% is standard for high-ROI trend traders (e.g., $0.19 entry → $0.77 exit). 90%+ win rate with tiny PnL signals micro-scalping bots.
- **Tier 3: Recent Momentum**:
  - **Recent 20 Backtest Copy PnL**: Must be positive. Reject historical winners currently in an active drawdown slump.

---

## Official Setup Copy Trade Workflow (Telegram Bot)

### Quick Start (5 Steps)
1. **Target Wallet**: Enter the target wallet address (`0x...`) to copy.
2. **Tag**: Assign a custom label for easy tracking (e.g. `Target-1-A-Tier`).
3. **Copy Percentage / Fixed Amount**:
   - **Percentage Scale**: `Your Trade Value = Target Trade Value × Copy %` (Recommended: `3%`).
   - **Fixed Amount**: Every copied trade buys a fixed USD amount (e.g. `$50`).
4. **Configure Optional Risk Settings**: Adjust limit vs market execution, minimum floor handling, and trade thresholds.
5. **Confirm**: Tap `Confirm` to activate the copy-trading task.

### Optional Settings & Parameter Invariants
- **Limit / Market Order Copy Buy**:
  - **Market Orders**: Executed immediately via FAK (Fill-and-Kill).
  - **Limit Orders**: Placed at target's price with 2 optional controls:
    - *Duration*: Auto-cancels the limit order after a set timeframe.
    - *Price Offset*: Places your limit order a fixed amount above/below target price.
- **Below Min Limit, Buy at Min**:
  - *Enabled (Recommended)*: If your calculated copy trade falls below minimum ($1.00 for market orders, 5 shares for limit orders), it automatically buys at minimum instead of skipping.
- **Ignore Target Wallet Trades Under**:
  - Filters out target's test/dust trades below a specified USD value (e.g. ignore trades under `$25.00`).
- **TP/SL (Take Profit / Stop Loss)**:
  - Sets automated exit targets. *Note*: TP/SL does not execute when sell orders use limit orders.

---

## Quick Reference Command Cheatsheet

| Command | Systemic Purpose |
| :--- | :--- |
| `/wallet` | View addresses, deposit/withdraw, export keys, manage sub-wallets, switch active main wallet |
| `/copytrade` | Access copy trading tasks, fixed vs scale mode, max spend caps, slippage, and sell control |
| `/positions` | Overview of active positions, unrealized PnL, cash-outs, and share holdings |
| `/manual` | Search Polymarket events and place instant manual YES/NO market orders |
| `/limit` | Create and manage limit orders for target price execution |
| `/convert` | Unwrap WCOL (Wrapped Collateral) balances back to USDC |
| `/topuser` | Real-time leaderboard of top copy traders with backtested PnL filtering |
| `/settings` | Global bot defaults, gas priority fees, and default slippage tolerance |

---

## Exhaustive True-to-Source Reference

For the un-truncated 37-page documentation reference combining all GitBook guides:
`references/full_guide.md`

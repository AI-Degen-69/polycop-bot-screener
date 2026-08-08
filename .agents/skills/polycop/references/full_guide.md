# PolyCop Complete Documentation Reference



<!-- PAGE: afk-auto-trade.md -->
# AFK AUTO TRADE

Welcome to the AFK (Away From Keyboard) Automated Strategy Engine, built by PolyCop specifically for Polymarket's short-term **crypto** prediction markets:

* **Assets:** BTC, ETH, SOL, XRP&#x20;
* **Timeframes:** 5 min, 15 min, 1h, 4h<br>

In fast-moving prediction markets, the AFK engine lets you preset multi-dimensional trigger conditions. The bot monitors order books and price data streams in real time on the cloud, executing precise trades on your behalf — even when you're away.

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/mClDBnwC574QWuwTae3C" %}
[How to Start](/afk-auto-trade/how-to-start.md)
{% endcontent-ref %}

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/Mn1PiXymFYonpd7g5k2K" %}
[Creating a Strategy](/afk-auto-trade/creating-a-strategy.md)
{% endcontent-ref %}

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/YE8htDHrXydiwKeC00YA" %}
[Strategy Templates](/afk-auto-trade/strategy-templates.md)
{% endcontent-ref %}

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/BC79ciJWVz5SPNplLpDG" %}
[Pro Tips](/afk-auto-trade/pro-tips.md)
{% endcontent-ref %}


---



<!-- PAGE: afk-auto-trade_creating-a-strategy.md -->
# Creating a Strategy

## Markets

Select the asset (**BTC, ETH, SOL, XRP**) and the market timeframe (**5 min, 15 min, 1h, 4h**) using the toggle buttons at the top of the panel. Each strategy is tied to one asset.<br>

<figure><img src="/files/ZNc1F6k6Bs49mxDDoThe" alt="" width="563"><figcaption><p>Tap to type in your triggers</p></figcaption></figure>

## 3 Triggers

This is the core of the system. You combine 3 filters, and the bot only trades when all three are satisfied at the same time — all conditions must be met simultaneously for a buy to trigger.

{% stepper %}
{% step %}

### **Trigger Time Range**

The window within each round during which the bot monitors conditions, measured from the start of the round.

* Input format: **`MM:SS, MM:SS`**
* Example: `12:30, 14:40` means the bot only evaluates conditions between the 12-minute-30-second mark and the 14-minute-40-second mark of each round. Outside that window, it does nothing.
  {% endstep %}

{% step %}

### **Trigger Up Price Range**

The UP share price range you are willing to enter. This prevents chasing an asset that has already moved too far.

* Input format: **`0.001, 0.999`** (prices are between 0 and 1)
* Example: `0.50, 0.80` means the bot only buys UP if the share price is somewhere between 50 cents and 80 cents.

> To trade the downside, tap the **Buy Up** button to toggle it to **Buy Down**, then set your **Min Down Price** and **Max Down Price**. Same logic, opposite direction.
> {% endstep %}

{% step %}

### **Trigger Price Change**

The absolute change in spot price compared to the opening price of the current round. Supports negative values for drops.

* Input format: **`minimum BTC price change, maximum BTC price change`** in USD
* Example 1: `30, 9999` — BTC has already moved up $30 or more since the round started. The 9999 ceiling is effectively unlimited, since BTC cannot realistically move $9,999 in 15 minutes or 4h.
* Example 2: `-500, -50` — BTC has dropped between $50 and $500 since the round opened.
* Example 3: `40, 300`— BTC has already moved up at least $40, but less than $300 since the round started.
  {% endstep %}
  {% endstepper %}

## Trade Settings

These settings define how the order is placed once all three trigger conditions are met.

### **Direction**

Toggle between **Buy UP** and **Buy DOWN** with a single button.

### MACD / KDJ / ATR Filters

PolyCop offers three independent indicator filters for your AFK strategy. Enable any one, two, or all three — each works independently. A trade is only blocked by a filter you've actively enabled.&#x20;

📖 Understanding these filters requires some basic knowledge of technical indicators — reference links are included in each section below.

👉 **How to enable:** Tap the MACD / KDJ / ATR button in your `/afk` settings. When you see ✅, it's active.

**Filter 1 — MACD Trend Filter**

MACD (Moving Average Convergence Divergence) measures the gap between a 12-period and 26-period EMA. The difference between these two lines produces a Histogram — when it's growing, momentum is accelerating; when it's shrinking, momentum is fading.

> 📖 [Learn more about MACD → Investopedia](https://www.investopedia.com/terms/m/macd.asp)

Prevents you from entering during accelerating moves against your position — waterfall dumps for UP trades, short squeezes for DOWN trades.

* **For UP trades:** Trade is blocked if Histogram is negative AND still falling (accelerating dump).
* **For DOWN trades:** Trade is blocked if Histogram is positive AND still rising (accelerating squeeze).

**Filter 2 — KDJ Entry Sniper**

KDJ is a momentum oscillator based on the Stochastic Oscillator, measuring overbought and oversold conditions. It produces three lines — K, D, and J — where the J line is the most sensitive, calculated as **J = 3K − 2D**. J values range from 0 to 100.

> 📖 [Learn more about KDJ → Google](https://share.google/aimode/Jt6Nmn4fIg8gOcmND)

Ensures you only enter at extreme price levels, giving you the best possible entry cost.

* **For UP trades:** Trade is only allowed when J < 30 (market heavily oversold — buyers washed out).
* **For DOWN trades:** Trade is only allowed when J > 70 (market heavily overbought — momentum overextended).

**Filter 3 — ATR Dynamic Threshold**

ATR (Average True Range) measures how much an asset typically moves within a given period, using Wilder's Smoothing over the past 14 candles. It reflects volatility only — not direction. This represents the average price movement level over a recent period.

> 📖 [Learn more about ATR → Investopedia](https://www.investopedia.com/terms/a/atr.asp#toc-example-of-how-to-use-the-atr)

In addition to your fixed minimum price delta, ATR adds a dynamic threshold that automatically adapts to market conditions.

* **Formula:** Required Price Jump >= 1-min ATR × 1.5
* **For UP/DOWN trades:** a trade is only placed when the asset's price change exceeds this dynamic level.

> ⚠️ **Important:** These filters improve entry quality but do not guarantee profitability. Always backtest at [polycop.fun](https://polycop.fun/afk-backtest) before going live.\
> All three filters are calculated on 1-minute candles. This means that within a 5-min AFK trade, if the 1-min MACD shows a death cross, the UP trigger will not fire. For longer timeframes like 1H and 4H, enabling these filters may be too restrictive and is not necessarily recommended.

### **Order Type**

Choose between a Market Order or a Limit Order (you set the exact price).

* For **market orders**, you can also set a **Slippage tolerance** — for example, 30% — to control how much price movement you are willing to accept on fill.
* **Limit Price and Duration (Time To Live)**\
  If you use a **limit order**, set the target price and how long the order stays open. If it does not fill before the duration expires, PolyCop cancels it automatically. You will not be left holding a stale order at the wrong price.

### Buy Amount per Round

The USD amount to buy per trade. Minimum $1.2.

> Input: `5` (minimum $1.2 USD)

{% hint style="info" %}
Note: If you're using Limit Orders, the minimum is **5 shares**. Orders below this threshold will fail — this is a Polymarket protocol requirement. We recommend setting a minimum buy amount of **$5 or above** when using Limit Orders.
{% endhint %}

### **Number of Rounds**

The number of consecutive rounds this strategy will run. Each round is 5 min, 15 min, 1h, or 4h depending on your selected market. Only successfully executed trades count as a completed round.<br>

## Position Management (TP / SL)

After a successful fill, the system automatically places a take-profit or stop-loss order on your behalf. You can set this by price or percentage — the maximum order price is capped at 0.999.

**Take Profit (TP)**: Enter a percentage (0.1% – 100%) or a price (0.001 – 0.999). If you enter a percentage, the system calculates the take-profit price based on your purchase price.

**Stop Loss (SL)**: Same format as TP. Once the stop-loss condition is met, the system will immediately place an order.

> 💡 If the position size is under 5 shares, TP/SL orders are automatically executed as market orders — Polymarket requires a minimum of 5 shares for limit orders, so PolyCop handles this conversion for you.

***

Once you’ve configured all your settings, <mark style="background-color:$warning;">hit the</mark> <mark style="background-color:$warning;"></mark><mark style="background-color:$warning;">**Create**</mark> <mark style="background-color:$warning;"></mark><mark style="background-color:$warning;">button</mark> at the bottom of the menu to launch your strategy. Every hour, the bot will send you a notification to confirm your strategy is still running.

When a market closes every round, your winnings are redeemed automatically. No manual claiming. No extra steps.


---



<!-- PAGE: afk-auto-trade_how-to-start.md -->
# How to Start

From the main PolyCop menu, tap **AFK Auto Trade**. You will see:

* **Create AFK Auto Trade** — open a new strategy panel
* **Run BackTest** — test your parameters against historical data

<figure><img src="/files/nwkqpIhOEx2rrmey1IeO" alt="" width="563"><figcaption></figcaption></figure>

✅ checkmark next to a strategy means it is active. ❌ means it is paused.

You can run multiple strategies simultaneously; each one runs in its own isolated environment without interfering with others.


---



<!-- PAGE: afk-auto-trade_non-crypto-markets.md -->
# Non-Crypto Markets

This page covers the **non-crypto market types**: Sports, Weather, Esports, Politics, Culture, Tech, and Finance.

> Crypto markets follow a separate setup flow. See [AFK Auto Trade · Crypto](https://docs.polycop.ai/afk-auto-trade/creating-a-strategy) for details.

## How It Works

AFK Auto Trade **scans** Polymarket markets **every 5 minutes** and places trades automatically based on the conditions you set. Your settings are organized into four parts:

{% columns %}
{% column %}
**Market Filter:** Defines which markets and outcomes the bot considers. Any outcome that doesn't meet your filter criteria — price range, spread, depth, volume, or time to close — is skipped before any further checks are done.

**Trigger Conditions:** Define **the price pattern** the bot looks for. Once an outcome passes the market filter, the bot calculates indicators from its price history and checks whether your conditions are all met. Every enabled condition must be satisfied at the same time for a buy signal to fire.

**Buy** settings: Control how the order is placed — order type, slippage tolerance, buy amount, and maximum buy price. When a signal triggers, the bot places the order immediately using your buy settings.

**Sell** settings: Control when the bot exits the position. After buying, the bot monitors the price and sells as soon as any one of your exit conditions is met — whichever comes first: Take Profit, Stop Loss, or Duration Auto Sell.
{% endcolumn %}

{% column %}

<figure><img src="/files/jlWMuWHwA305atPoPEwi" alt=""><figcaption></figcaption></figure>
{% endcolumn %}
{% endcolumns %}

###

## Getting Started

From the AFK Auto Trade list page, tap **＋** **Create AFK Auto Trade** → choose a market type → choose a strategy template.

Templates pre-fill all settings for you. You can adjust any value after selecting one.

{% columns %}
{% column %}

<figure><img src="/files/oHzbzAMmplIK6wr6QULO" alt=""><figcaption><p>(1) tap <strong>＋ Create AFK Auto Trade</strong></p></figcaption></figure>
{% endcolumn %}

{% column %}

<figure><img src="/files/tuiCaQnpMy6AufV7ko5X" alt=""><figcaption><p>(2) Choose a market type</p></figcaption></figure>
{% endcolumn %}

{% column %}

<figure><img src="/files/qa7ZiD02kY0JfrOyVmQ4" alt=""><figcaption><p>(3) Choose a strategy template.</p></figcaption></figure>
{% endcolumn %}
{% endcolumns %}

## Strategy Templates

Each template represents a different price pattern and trading approach. Choose the one that matches the market behavior you want to trade.

**🚀 Breakout** Price consolidates in a tight range, then breaks out above resistance. Best for: outcomes that have been stable for a while and are starting to move.

**📈 Momentum** Price trends upward from a low base with minimal pullback. Best for: outcomes with a clean, sustained upward move.

**↩ Rebound** Price dips then recovers — buy the bounce. Best for: outcomes that pulled back but are turning back up.

**🔄 Range Trade** Price oscillates between support and resistance — buy the dip, take profit at the top. Best for: outcomes that repeatedly move between two price levels.

**⚡ Swing Reversal** Sharp price drop — buy the rebound or ride the momentum. Best for: outcomes with sudden, large price swings.

**🧩 Custom** Start with no conditions — build your own trigger from scratch. Best for: experienced users with a specific setup in mind.

## Parameter Guide

Settings are grouped into **four sections**: Market Filter, Trigger Conditions, Buy, and Sell.

{% hint style="info" %}

* Any condition set to `-` is skipped.
* In the bot, tap any parameter button to see its input guide
  {% endhint %}

### 1. Market Filter

Market Filter runs first. Before the bot evaluates any trigger conditions, it checks every outcome against your market filter settings. Anything that doesn't qualify is skipped entirely.

<table data-first-column-sticky><thead><tr><th width="125.4296875">Parameter</th><th width="537.28515625">What it does</th><th>Input</th></tr></thead><tbody><tr><td><strong>Market Type</strong></td><td><ul><li>Choose the category of Polymarket markets the bot scans. </li><li>You can only select one in every AFKstratrgy. Choosing All Market scans across all non-crypto categories at once.</li></ul></td><td>Tap one as ✅</td></tr><tr><td><strong>Ends ≤</strong></td><td><ul><li>Set the maximum time remaining before a market closes. Only markets ending within this many hours are scanned. </li><li>Markets closer to resolution tend to have more decisive price movement, making this a useful way to stay focused on active opportunities.</li></ul></td><td>Number of hours, <code>1</code>~<code>720</code></td></tr><tr><td><strong>Price Min</strong></td><td><ul><li>Set the <strong>minimum current price</strong> for outcomes the bot will consider. Outcomes priced below this value are skipped. </li></ul></td><td>Cents, <code>1</code>~<code>99</code></td></tr><tr><td><strong>Price Max</strong></td><td><ul><li>Set the <strong>maximum current price</strong> for outcomes the bot will consider. Outcomes priced above this value are skipped. </li><li>Outcomes already priced very high leave little room for further upside and may be difficult to exit at a profit (that depends on your exit strategy). </li><li><strong>Price Max</strong> and <strong>Price Min</strong> together establish the <strong>price range</strong> you're looking for, defining the <mark style="background-color:$warning;"><strong>current price interval</strong></mark>.</li></ul></td><td>Cents, <code>1</code>~<code>99</code></td></tr><tr><td><strong>Spread</strong></td><td><ul><li>Set the maximum allowed gap between the best bid and best ask. Outcomes with a wider spread are skipped. </li><li>A wide spread means you pay more to buy and receive less when you sell — it's an immediate, hidden cost on every trade.</li></ul></td><td>Cents, <code>1</code>~<code>99</code></td></tr><tr><td><strong>Depth</strong></td><td><ul><li>Set the minimum order book liquidity required. Depth is the total value of all ask-side orders available for this outcome — outcomes below this threshold are skipped. </li><li>Low depth risks poor fill prices or moving the market against you just by placing an order.</li></ul></td><td>USD, <code>1</code>~<code>1,000,000</code> </td></tr><tr><td><strong>Volume</strong></td><td><ul><li>Set the minimum total trading volume for a market to be scanned. Low-volume markets are skipped. </li><li>Volume is a signal of genuine market activity — a market with very low volume may have stale prices or unreliable liquidity even if the order book looks acceptable at the moment of scanning.</li></ul></td><td>USD, <code>1</code>~<code>100,000,000</code></td></tr></tbody></table>

### 2. Trigger Conditions

Trigger conditions define the price pattern the bot looks for. The Window setting is the foundation every historical condition is built on — Past Min, Past Max, Start Price, and Max Pullback are all calculated strictly from price data inside this window, so changing it changes what those numbers mean.

All indicators are calculated from the price history of each outcome's token independently. All enabled conditions must be met at the same time for a buy signal to fire.&#x20;

<table data-first-column-sticky><thead><tr><th width="125.4296875">Parameter</th><th width="588.1484375">What it does</th><th width="154.53125">Input</th></tr></thead><tbody><tr><td><strong>Window</strong></td><td><ul><li>Choose <strong>the lookback period</strong> for historical price calculations — <strong>Past Min, Past Max, Start Price, and Max Pullback are all derived from price data within this window.</strong> </li><li>A shorter window (e.g. <code>5m</code>) captures very recent momentum; a longer window (e.g. <code>6h</code>) reflects how the outcome has been trading over a broader period. </li><li>Choose based on the pattern you're trying to detect.</li></ul></td><td>Type <code>5m</code> / <code>15m</code> / <code>1h</code> / <code>6h</code> / <code>1d</code></td></tr><tr><td><strong>Past Min</strong></td><td><ul><li>Set the <strong>minimum</strong> allowed low <strong>within the observation window</strong>. The bot checks that the lowest price reached during this period is at or above your threshold — meaning the outcome never fell below your floor at any point, not just at the end.</li><li>Useful for confirming sustained support rather than a temporary recovery from a much lower base.</li></ul></td><td>Cents, <code>1</code>~<code>99</code></td></tr><tr><td><strong>Past Max</strong></td><td><ul><li>Set the <strong>maximum</strong> allowed high <strong>within the observation window</strong>. The bot checks that the highest price reached during this period is at or below your threshold — meaning the outcome never broke above this ceiling during the window. </li><li>Used together with <strong>Past Min</strong>, these two values define a <strong>historical price range</strong>. If the current price has since moved above Past Max, it may indicate a potential breakout.</li></ul></td><td>Cents, <code>1</code>~<code>99</code></td></tr><tr><td><strong>Start Price</strong></td><td><ul><li>Set the <strong>maximum</strong> price at <strong>the start of the observation window</strong>. The bot checks that the price at the very first data point of the window was at or below your threshold. </li><li>When used alongside a high <strong>Current Price</strong>, this confirms a meaningful upward move occurred within the window — ruling out outcomes that were already at a high price throughout the entire period.</li></ul></td><td>Cents, <code>1</code>~<code>99</code></td></tr><tr><td><strong>Current Price</strong></td><td><ul><li>Set the <strong>minimum</strong> current price required to trigger a buy signal. The bot checks that the outcome's latest price at the time of the scan is at or above your threshold. </li><li>This confirms the outcome is currently at the price level you're targeting right now — not that it merely passed through it at some point during the window.</li></ul></td><td>Cents, <code>1</code>~<code>99</code></td></tr><tr><td><strong>Max Pullback</strong></td><td><ul><li>Set the <strong>maximum</strong> allowed drop from the peak price <strong>within the observation window</strong>. The bot checks the largest drop from any local peak to any subsequent low — for example, if the price rose to 78¢, dipped to 73¢, then continued upward, the pullback is 5¢. </li><li>This filters out volatile or choppy upward moves and keeps only outcomes where the price climbed without significant reversals along the way.</li></ul></td><td>Cents, <code>1</code>~<code>99</code></td></tr><tr><td><strong>Breakout Price</strong></td><td><ul><li>A buy order will only be triggered if the current price is equal to or higher than this price. </li><li>Typically set above Past Max in Breakout Template — if Past Max defines the top of the historical range, Breakout Price confirms the price has pushed meaningfully beyond it, rather than simply touching the ceiling and retreating. </li><li>The gap between Past Max and Breakout Price acts as a buffer against false breakouts.</li></ul></td><td>Cents, <code>1</code>~<code>99</code></td></tr><tr><td><strong>5m Direction</strong></td><td><ul><li>Set the required price direction over the last 5 minutes. The bot compares the current price to the price exactly 5 minutes ago — <code>Up</code> means current price is higher now; <code>Down</code> means lower. </li><li>Acts as a short-term momentum check on top of the longer-window historical conditions, confirming the price is still moving in the expected direction at the moment the signal fires.</li></ul></td><td>Type <code>Up</code> / <code>Down</code>.</td></tr><tr><td><strong>5m Change</strong></td><td><ul><li>Set the <strong>minimum</strong> price movement over the last 5 minutes, in the direction set by 5m Direction — if 5m Direction is <code>Up</code>, this is how much the price must have risen; if <code>Down</code>, how much it must have fallen. </li><li>Filters out slow or marginal moves — only outcomes showing clear, decisive short-term momentum will trigger.</li></ul></td><td><p>Enter a positive number. </p><p>Cents, <code>1</code>~<code>99</code></p></td></tr></tbody></table>

### 3. Buy

These settings control how the bot places the buy order once a signal is triggered. The bot checks the live order book one more time before placing the order — if the price or liquidity has changed since the last scan and no longer meets your settings, the order will not be placed.

<table data-first-column-sticky><thead><tr><th width="146.375">Parameter</th><th width="456.640625">What it does</th><th>Input</th></tr></thead><tbody><tr><td><strong>Slippage</strong></td><td><ul><li>Set the maximum slippage you'll accept. If the estimated fill price exceeds this threshold, the bot cancels the order rather than overpaying</li></ul></td><td>Percent, <code>0.1</code>~<code>100</code></td></tr><tr><td><strong>Single buy amount</strong></td><td><ul><li>Set how much the bot spends per triggered signal. </li></ul></td><td>USD, <code>1</code>~<code>10,000</code></td></tr><tr><td><strong>Max buy price</strong></td><td><ul><li>Set the maximum price the bot will pay to fill a buy order, applied after slippage is calculated. </li><li>Even if slippage is within your limit, the order is cancelled if the actual fill price would exceed this value. </li><li>Prevents the bot from buying into an outcome that has already moved too far by the time the order is placed.</li></ul></td><td>Cents, <code>1</code>~<code>99</code></td></tr></tbody></table>

{% hint style="warning" icon="lightbulb" %}
**Deduplication & Cooldown**：Each strategy only buys a given outcome once — after the first buy, that outcome in the same market won't trigger again under the same strategy, whether it's currently held, already sold, or the conditions match again on a later scan.
{% endhint %}

### 4. Sell

After a buy order fills, the bot continuously monitors the position and exits as soon as any one of the following conditions is triggered. Only one needs to trigger — whichever fires first closes the position.

<table data-first-column-sticky><thead><tr><th width="157.140625">Parameter</th><th width="508.421875">What it does</th><th>Input</th></tr></thead><tbody><tr><td><strong>TP (Take Profit)</strong></td><td><ul><li>Set the take profit. The bot sells when the current price rises by this many cents above your actual fill price. </li><li>The reference point is the fill price, not the price at the time the signal triggered. For example, if TP is <code>6</code> and the order filled at 80¢, the bot sells when the price reaches 86¢.</li></ul></td><td>Cents, <code>1</code>~<code>99</code> </td></tr><tr><td><strong>SL (Stop Loss)</strong></td><td><ul><li>Set the stop loss. The bot sells when the current price falls by this many cents below your fill price. </li><li>For example, if SL is <code>4</code> and the order filled at 80¢, the bot sells when the price drops to 76¢. This caps your maximum loss on any single trade.</li></ul></td><td>Cents, <code>1</code>~<code>99</code> </td></tr><tr><td><strong>Duration Auto Sell</strong></td><td><ul><li>Set the maximum holding time. The bot automatically closes the position after this many seconds, regardless of whether TP or SL has been reached. </li><li>The timer starts from the moment the buy order fills, not from when the signal triggered. </li><li>Useful for short-term strategies where you want to limit exposure time even if price hasn't moved significantly in either direction.</li></ul></td><td>Seconds, <code>1</code>~<code>86,400</code></td></tr></tbody></table>

## Template Default Settings

All templates share the same default Market Filter and Buy / Sell values. Trigger conditions differ per template.

{% hint style="info" %}
These templates come pre-configured by Bot as a starting point. Once you've selected one in the bot, every value shown below is fully editable — adjust any setting to match your own view of the market.
{% endhint %}

### **Shared defaults** — Market Filter/Buy/Sell

{% columns %}
{% column %}

<table><thead><tr><th width="164.4453125">Setting</th><th width="158.54296875">Default</th></tr></thead><tbody><tr><td>Ends</td><td>≤24h</td></tr><tr><td>Price Min</td><td>40¢</td></tr><tr><td>Price Max</td><td>90¢</td></tr><tr><td>Spread</td><td>≤5¢</td></tr><tr><td>Depth</td><td>≥$1,000</td></tr><tr><td>Volume</td><td>≥$10,000</td></tr><tr><td>Order Type</td><td>Market Order Buy</td></tr><tr><td>Slippage</td><td>30%</td></tr><tr><td>Single buy amount</td><td>$5</td></tr><tr><td>Max buy price</td><td>90¢</td></tr><tr><td>TP</td><td>+6¢</td></tr><tr><td>SL</td><td>−4¢</td></tr><tr><td>Duration Auto Sell</td><td>−</td></tr></tbody></table>
{% endcolumn %}

{% column %}

<figure><img src="/files/CxwGK64BfBcWi4ZG80cA" alt=""><figcaption></figcaption></figure>
{% endcolumn %}
{% endcolumns %}

### **Trigger conditions by template**

Each template is designed to illustrate a distinct price pattern and give you a reasonable starting range for that pattern — not to recommend a specific trade or guarantee an outcome. Review and adjust every value before activating a strategy, and use them at your own discretion.

| Condition      | Breakout | Momentum | Rebound | Range Trade | Swing Reversal |
| -------------- | -------- | -------- | ------- | ----------- | -------------- |
| Window         | 1h       | 1h       | 1h      | 6h          | 5m             |
| Past Min       | ≥55¢     | −        | −       | ≥72¢        | −              |
| Past Max       | ≤72¢     | −        | −       | ≤79¢        | −              |
| Start Price    | ≤60¢     | ≤60¢     | −       | −           | −              |
| Current Price  | ≥80¢     | ≥80¢     | ≥72¢    | ≥72¢        | −              |
| Max Pullback   | −        | ≤5¢      | −       | −           | −              |
| Breakout Price | ≥78¢     | −        | −       | −           | −              |
| 5m Direction   | Up       | Up       | Up      | −           | Down           |
| 5m Change      | ≥8¢      | ≥8¢      | −       | −           | ≥20¢           |

> *Disclaimer: These default values are not investment advice.*&#x20;

### Reading the Templates: Breakout vs. Momentum

To see how these settings actually work together, here's a walkthrough of two templates using their default values.

{% columns %}
{% column %}
**Breakout**

<figure><img src="/files/oajXdm8RpdUB0d7w5LV5" alt="" width="342"><figcaption></figcaption></figure>

Past Min (55¢) and Past Max (72¢) require the price to have stayed inside a 55¢–72¢ band for the full 1-hour window — confirming the outcome was genuinely range-bound, not just briefly touching those levels. Start Price (≤60¢) confirms it was still in the lower part of that band an hour ago.

The trigger requires Current Price ≥80¢ and Breakout Price ≥78¢ — both well above the 72¢ ceiling, confirming a real break out of the range. 5m Direction = Up and 5m Change ≥8¢ confirm it's happening right now, not a move that already faded.

In short: an outcome that consolidated for an hour, then broke decisively above that range in the last few minutes.
{% endcolumn %}

{% column %}
**Momentum**

<figure><img src="/files/MaWKcUrWktz2w1aYz3Mm" alt="" width="331"><figcaption></figcaption></figure>

Same 1-hour window, but Past Min and Past Max are disabled — this template doesn't care whether the price was range-bound. Start Price (≤60¢) and Current Price (≥80¢) confirm a low-to-high climb over the hour, while Max Pullback (≤5¢) requires the price never dropped more than 5¢ from any local high along the way. 5m Direction = Up and 5m Change ≥8¢ confirm the move is still active.

In short: a smooth, steady climb with no sharp reversals — regardless of where the price started from.

The core difference: Breakout asks "did this just escape a range it was stuck in?" Momentum asks "has this been climbing cleanly the whole time?" A smooth climb from an unconfined level would trigger Momentum but not Breakout; a sharp spike out of a flat range might trigger Breakout but fail Momentum's pullback check.
{% endcolumn %}
{% endcolumns %}

{% hint style="info" %}
The remaining templates — Rebound, Range Trade, Swing Reversal — follow the same idea but encode different price action patterns. Understanding which pattern fits your view of the market benefits from some trading background. If you're not already familiar with these concepts, it's worth spending time with an AI assistant or other resources to learn the basics of price action before relying heavily on these template.
{% endhint %}

## Managing Your Strategies

**Status** Pause or resume this strategy — a paused strategy won't scan or place any orders until reactivated. Enter `Active` or `Paused`:

**Delete** Delete this strategy? All settings will be permanently removed. This action cannot be undone. Type `DELETE` to confirm, or press Back to cancel:

**Duplicate** You can create multiple instances of the same template with different settings. Strategies run independently and won't interfere with each other.

## Key Rules

* **Scans run every 5 minutes, around the clock.** The bot doesn't need your device to stay on or your account to be active — once a strategy is set to Active, it keeps watching Polymarket independently in the cloud.
* **One buy per market, per strategy.** Once a strategy buys into an outcome, it won't trigger again on that same market — whether it's still held, already sold, or the same conditions reappear on a later scan. This prevents the bot from repeatedly piling into the same position.
* **All conditions must align — there's no partial match.** Every enabled trigger condition is checked together using AND logic. A near-miss doesn't trigger a trade; the full set of conditions has to be true at the same time.
* Any setting shown as `-` is disabled and not evaluated.
* **Multiple strategies can run side by side without interfering with each other.** You can run a Breakout strategy on Sports and a Range Trade strategy on Politics at the same time — each operates independently, with its own filters, conditions, and position tracking.


---



<!-- PAGE: afk-auto-trade_pro-tips.md -->
# Pro Tips

* You can run multiple strategies with different time ranges or aggression levels simultaneously — including across different assets (e.g. BTC 5min and ETH 15min). Default names are AFK 1, AFK 2, etc.
* Use the **Run BackTest** feature to validate your parameters before going live.
* TTL on limit orders is important — without it, unfilled orders can remain open into the next round.
* For the Flash Crash template, keep position size small. The edge is in the payout multiple, not the win rate.


---



<!-- PAGE: afk-auto-trade_strategy-templates.md -->
# Strategy Templates

## Template 1: Theta Harvester (Late-Stage)

Captures time decay in the final minutes of a round when BTC has already established a clear direction.

* Time Range: `13:00, 14:55`
* UP Price: `0.70, 0.90`
* BTC Change: `40, 9999`
* Buy Params: `🟢 Buy UP` | Limit `0.90`
* TP/SL: None (Hold directly until the 15-minute round ends, waiting for automatic settlement to get 1 USDC)

Logic: With less than 2 minutes remaining and BTC up $40+, the probability of a reversal is low. Buy and hold for automatic settlement at 1 USDC.

## Template 2: Breakout Scalper (Opening Range)

Captures momentum from sudden news or large spot market moves in the first 30–60 seconds of a round.

* Time Range: `00:30, 01:00`
* UP Price: `0.01, 0.89`
* BTC Change: 5`0, 9999`
* Buy Params: `🟢 Buy UP` | Market Buy
* TP/SL: NO

Logic: The first minute of BTC price action is a strong predictor of round direction. A $50+ move up in the opening 60 seconds suggests the round resolves UP.

## Template 3: Flash Crash Rebound

A small contrarian bet when panic selling drives UP prices to extreme lows mid-round.

* Time Range: `04:00, 11:00`
* UP Price: `0.01, 0.15`
* BTC Change: `-200, -10`
* Buy Params: `🟢 Buy UP` | Amount `$5` (Lottery play, control position size strictly)
* TP/SL: TP `0.45` / SL None (Run if it doubles, treat a wipeout like a losing lottery ticket)

Logic: Extreme mid-round price dislocations sometimes mean-revert. This is a low-probability, high-reward bet with a strictly controlled position size. Treat a total loss like a losing lottery ticket.


---



<!-- PAGE: copy-trading.md -->
# COPY TRADING

Copy Trade lets you automatically mirror any target wallet's trades on Polymarket. Once set up, every time the target buys or sells, your bot executes the same action based on configured parameters

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/pUJ6251BuqzMUBFKSCn5" %}
[How to Copy](/copy-trading/how-to-copy.md)
{% endcontent-ref %}

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/YyyXGmX1xFhe7AZILpzR" %}
[Copy Trading Settings Guide](/copy-trading/copy-trading-settings-guide.md)
{% endcontent-ref %}

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/oVwI1kT7N3Tr2iPcGBFG" %}
[Sub-Wallet Copy Trading](/copy-trading/sub-wallet-copy-trading.md)
{% endcontent-ref %}

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/ayYzz16GFbFW7yW19R5o" %}
[Pro Tips](/copy-trading/pro-tips.md)
{% endcontent-ref %}

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/Ud4mCb6sznqUIgUkMR0z" %}
[Positions](/copy-trading/positions.md)
{% endcontent-ref %}

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/8ALwQzIKTap07NXf9uZJ" %}
[Referrals](/fees-and-referrals/referrals.md)
{% endcontent-ref %}

{% content-ref url="/spaces/6RH958mIbJRqog5izKje/pages/xR1HqQDQc4nWFI0uQHn9" %}
[FAQs](/copy-trading/faqs.md)
{% endcontent-ref %}


---



<!-- PAGE: copy-trading_copy-trading-settings-guide.md -->
# Copy Trading Settings Guide

## Parameter Guide

{% hint style="info" %}
The following describes each parameter as it appears in the `/copytrade` settings, ordered by button position from top to bottom, right to left.
{% endhint %}

<details>

<summary><strong>1. Copy Percentage / Fixed Amount ($)</strong></summary>

Determines how much you invest per trade relative to the target.

* Percentage Mode (e.g., 10%): If the target buys $100 worth of shares, you buy $10.
* Fixed Amount Mode (e.g., $50): You always buy $50 regardless of the target's trade size.
* How to Switch: Type the number with or without the `%` symbol when prompted.

</details>

<details>

<summary><strong>2. Market Order Copy Buy</strong></summary>

</details>

<details open>

<summary>    <strong>2.1. Market Order Slippage</strong></summary>

* Description: Represents the maximum price deviation you are willing to accept. The system always prioritizes the best available market price.
* *Note on FAK Logic: If slippage is too low, you may see error `400 no orders found to match with FAK order`. Polymarket uses Fill-and-Kill (FAK) logic; if liquidity isn't found within your slippage range, the order is partially filled or killed entirely to prevent unfavorable prices.*

</details>

<details>

<summary>    <strong>2.2. Retry for Failure</strong></summary>

* Description: When a Market Order copy trade fails, PolyCop will automatically retry the trade. You can set the number of retry attempts between 0 and 3.
* Input Requirements: Tap the button to cycle through the options: **1** → **2** → **3**→ **0** (no retry) .

</details>

<details>

<summary><strong>3. Limit Order Copy</strong></summary>

* Tap the **Market Order Copy Buy** button to switch to Limit Order mode for copy trading. The following 3.1 \~3.4 explains the parameters for Limit Order copy trading.

</details>

<details>

<summary>    <strong>3.1. Limit Price Offset</strong></summary>

* Description: Sets a price offset for limit orders so your purchase price is slightly higher or lower than the target’s, increasing fulfillment likelihood.
* Input Requirements: Can be negative, range `-0.99` \~ `0.99`, or enter `reset` to clear.
* Recommended Setting: Enter `0.02` to buy at $0.02 above the target price for better execution.

</details>

<details>

<summary>    <strong>3.2. Limit Order Duration</strong></summary>

* Description: Sets the lifespan of a limit order — unfilled limit orders are auto-cancelled after this many seconds.
* Input Requirements: Seconds (positive integer), minimum 125 seconds, no upper limit.
* Minimum 125 seconds due to a new Polymarket protocol update on GTD (Good-Til-Date) orders and network timing.

</details>

<details>

<summary>    <strong>3.3. Bid L1/.../Ask L3 (Order Book Pricing)</strong></summary>

* Descriptio&#x6E;**:**
  * Alternatively, you can place limit orders at these live order book price levels. You can select from specific depth levels: Bid L1/L2/L3, Ask L1/L2/L3, or the Mid-Price (refer to the diagram below).
  * **Bid L1** represents the highest price buyers are currently willing to pay, while **Ask L1** is the lowest price sellers are willing to accept. The **Mid-Price** is the exact center of the spread: (Bid L1+Ask L1)/2.
* Input Requirements: Click this button to switch between the order book prices. You have 7 different price levels to choose from, ranging from Bid L1 to Ask L3.
* Mode Switching: Selecting an order book price "Bid L1/.../Ask L1" automatically disables the previous "Price Offset" function. In the bot, you can easily toggle between these two pricing modes at any time. Just look for the green checkmark (✅) to confirm which mode is currently activ&#x65;**.**

<figure><img src="/files/ItI5rwIgQqG3ffR1SffW" alt=""><figcaption><p><strong>Example: Order book price levels in a 5-minute BTC market</strong></p></figcaption></figure>

</details>

<details>

<summary>    <strong>3.4. Limit to Market at Expiration</strong></summary>

* Descriptio&#x6E;**:** When selecting a Limit Order for copy trading and the set duration expires, this feature will **automatically convert it into a Market Order** to execute.
* Input Requirements: Tap the button to toggle. **ON** = enabled, **OFF** = disabled.

</details>

<details>

<summary><strong>4. Turbo Mode</strong></summary>

* Descriptio&#x6E;**:** Turbo Mode cuts out extra settings, lookups and queue waiting — so your copy trades fire faster, even under heavy traffic.
* Input Requirements: Tap the button to toggle. ✅ = enabled, ❌ = disabled.

</details>

<details>

<summary><strong>5. Stop Loss % / Price</strong></summary>

* Input: Percentage (`0.1%` \~ `100%`) or Fixed Price (`0.01` \~ `0.99`).
* Execution Logic: All Stop Loss orders use Market Orders. When prices move sharply, market orders may experience price slippage.

</details>

<details>

<summary><strong>6. Take Profit % / Price</strong></summary>

* Input: Percentage (`0.1%` \~ `100%`) or Fixed Price (`0.01` \~ `0.99`).
* Execution Logic (PM Constraints):
  * For orders ≥ 5 shares: The system places a Limit Order immediately to lock in gains.
  * For orders < 5 shares: The system uses Market Orders. Note that market orders may experience slippage during volatility.

</details>

<details>

<summary><strong>7. Balance SL</strong></summary>

* Description: Once set, the system checks your address balance every 10 minutes. If the balance falls below the Stop Loss threshold, the copy trading task will be automatically stopped. No positions will be closed or any other actions triggered.
* Input: Enter your Stop Loss threshold in USD, e.g. `100`.

</details>

<details>

<summary><strong>8. Balance TP</strong></summary>

* Description: Once set, the system checks your address balance every 10 minutes. If the balance exceeds the Take Profit threshold, the copy trading task will be automatically stopped. No positions will be closed or any other actions triggered.
* Input: Enter your Take Profit threshold in USD, e.g. `10000`.

</details>

<details>

<summary><strong>9. Below min limit, buy at min</strong></summary>

* Description: If enabled, when the calculated copy amount is lower than the platform's minimum requirement, the trade executes at the minimum.
* PolyMarket Minimum Requirements: $1 for market orders; 5 shares for limit orders.

{% hint style="info" icon="lightbulb-on" %}
Pro Tip: Best used in combination with Item #10.
{% endhint %}

</details>

<details>

<summary><strong>10. Ignore Trades Under/Above</strong></summary>

* Description: Sets a minimum or maximum trade amount filter for copy trading. Trades outside your specified range will be automatically ignored. You can set either one or both limits.
  * **Min Trade Amount**: Enter a value (`0`–`9,999,999`) to skip any trade where the target address trades below this amount. If Target Trade Amount < your minimum → trade is ignored
  * **Max Trade Amount**: Enter a value (`0`–`9,999,999`) to skip any trade where the target address trades above this amount. If Target Trade Amount > your maximum → trade is ignored

{% hint style="info" icon="lightbulb-on" %}
Anti-Noise Strategy:

* Setup: Set `Ignore` to $10–$50 and Enable `Below min limit`.
* Result: This filters out "dust" trades (noise). When the target makes a "real" trade (e.g., $100), even if your 1% copy ratio equals $1, the bot will ensure you enter the position at the platform minimum.
  {% endhint %}

</details>

<details>

<summary><strong>11. Max Price &#x26; Min Price</strong></summary>

* Max Price: Highest price to copy buy (`0.001` \~ `0.999`). Trades above this are ignored.
* Min Price: Lowest price to copy buy (`0.001` \~ `0.999`). Trades below this are ignored.

</details>

<details>

<summary><strong>12. Total Spend Limit (Trader Limit)</strong></summary>

* Description: Total amount to spend across all assets.
* Logic: If total exposure exceeds this, copying stops. It automatically resumes after you sell or claim positions and exposure drops below the limit.

</details>

<details>

<summary><strong>13. Max Per Trade</strong></summary>

* Description: Maximum amount per copy trade.
* Input: `1` \~ `9,999,999`, `reset`, or `-` for no limit.
* Logic: If the calculated amount exceeds this, the trade is capped at this value.

</details>

<details>

<summary><strong>14. Min Per Trade</strong></summary>

* Description: Minimum amount per copy trade.
* Input: `1` \~ `9,999,999`, `reset`, or `-` for no limit.
* Logic: If the calculated copy amount is lower than this value, it executes at this minimum.

</details>

<details>

<summary><strong>15. Max Per Market (Market Limit)</strong></summary>

* Description: Maximum capital allocated to a single Market / ConditionId.
* Logic: Sums the total USD spent on both Yes and No options within the same market to prevent over-concentration in a single event.

</details>

<details>

<summary><strong>16. Max Per Yes/No (Asset Limit)</strong></summary>

* Description: Maximum USD amount allocated to a single Asset (token).
* Calculation Includes: Successfully executed orders + Open limit orders (from this bot) + The current pending trade.
* Note: This represents your cumulative exposure per specific asset.

</details>

<details>

<summary><strong>17. Only Copy 5/15min Market Final Time</strong></summary>

* What it is: The "Last-Minute" or late-entry mode.
* What it does: If you set this to `60s`, your bot will **ONLY** copy trades made when there are **less than 60 seconds left** before the market closes. Any trades made earlier in the market will be ignored.

</details>

<details>

<summary><strong>18. Only Copy 5/15min Market start Time</strong></summary>

* What it is: The "Sniper" or early-entry mode.
* What it does: If you set this to `60s`, your bot will **ONLY** copy trades made within the **first 60 seconds** after the market opens. Any trades made by the target wallet after the first 60 seconds will be ignored.

</details>

<details>

<summary> <strong>19. No. of Markets Held</strong></summary>

* Description: Maximum number of distinct markets (`ConditionIds`) you can hold simultaneously. A count-based limit to ensure portfolio diversification.
* Input: `1` \~ `999`, or `-1` for unlimited.

</details>

<details>

<summary> 20<strong>. Only Copy Specific Market Types</strong></summary>

* Select only the market types you want to copy — Sports, Crypto, Politics, Weather, and more. (Crypto even has sub-options for 5-minute intervals, BTC, ETH). Only markets marked ✅ get copied.

  *Esports are included in Sports*
* Advanced Keywords Control:&#x20;
  * **Blacklist Markets Containing Keywords:** Skip any market whose name contains specific words (e.g., Blacklist "5min" to skip all short-interval crypto markets).&#x20;
  * **Only Buy Markets Containing Keywords**: Whitelist Keywords; only copy markets whose name matches specific words (e.g., Whitelist "LoL" to only copy LoL games)

</details>

<details>

<summary><strong>20. Copy Buy / Copy Sell Toggles</strong></summary>

* Disable Copy Buy: Stops replicating buys; continues replicating sells.
* Disable Copy Sell: Stops replicating sells; continues replicating buys.
* Disable Both: Pauses all copy-trading activity.

</details>

<details>

<summary><strong>21. Sell: Market Order / Sell: Limit Order</strong></summary>

* Market Order: Allows slippage configuration.
* Limit Order: Allows Price Offset and Expiration configuration.

{% hint style="warning" %}
🚨 TP/SL Compatibility: If you switch Sell mode to Limit Order, TP/SL will no longer function. TP/SL is only compatible with Market Orders because Polymarket does not allow two concurrent limit orders on the same position.
{% endhint %}

</details>

<details>

<summary><strong>22. Reverse Copy</strong></summary>

* What it is: A toggle that mirrors the target wallet's trades in the opposite direction. When enabled, if the target buys UP, you buy DOWN — and vice versa.
* What it does: Reverses the copy direction on every trade from the target wallet. All other parameters (copy amount, filters, TP/SL, etc.) remain in effect as normal.

</details>

## Recommended Settings by Trader Type

Not sure how to configure your copy trade? Use these profiles as a starting point based on the type of trader you're following.

### **Golden Principles**

Before you begin, remember the Golden Principles:

* **The Proportionality Principle**: Ensure your single trade size relative to your total balance matches the target’s. This ensures your profit margins align.
* **The Anti-Drawdown Principle**: Do not allow your balance to be exhausted quickly. Always leave room for market volatility.
* **Strategy Alignment**: Observe the target’s trade history and current positions, then select the matching profile below.

### **Profile Overview**

<table data-header-hidden><thead><tr><th width="82.48828125"></th><th width="256.046875"></th><th width="375.53515625"></th><th width="374.98828125"></th></tr></thead><tbody><tr><td><strong>Profile</strong></td><td><strong>Trader Type</strong></td><td><strong>Main Risk</strong></td><td><strong>Key Strategy</strong></td></tr><tr><td>1</td><td>Stable / Professional Trader</td><td>May suddenly place a very large bet</td><td>Copy proportionally + set a spending cap</td></tr><tr><td>2</td><td>Whale ($1M+ funds)</td><td>Their huge trades will drain your balance</td><td>Skip small moves + cap your market exposure</td></tr><tr><td>3</td><td>High-Frequency / Algorithm</td><td>Too many tiny trades = fees eat your profit</td><td>Filter weak signals + auto take profit</td></tr><tr><td>4</td><td>News / Event Trader</td><td>Prices move wildly and fast</td><td>Enter fast, don't worry about exact price</td></tr><tr><td>5</td><td>Low Liquidity / Price Sensitive</td><td>Bad entry price = lost money</td><td>Use limit orders + strict price control</td></tr><tr><td>6</td><td>Long-Term / Value Investor</td><td>Short-term swings may scare you out early</td><td>Wide stop loss + ignore small adjustments</td></tr></tbody></table>

{% tabs %}
{% tab title="Profile 1: Stable / Professional Trader" %}
**Who is this?** A careful trader with a steady record — they manage their trades well, win consistently, and never bet everything at once. Great for beginners to follow long-term.

**Goal:** Mirror the expert's win-rate model with a safety cap on extreme bets.

| **Setting**                 | **Recommended Value**                                | **Why**                                                            |
| --------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------ |
| Copy Percentage             | 10%–20% (based on your balance vs. theirs)           | Keeps your trades in proportion to theirs                          |
| **Max Spend Per Trade**     | The most you're okay losing in one trade (e.g., $50) | **Important** — protects you if they suddenly bet big              |
| Below Min Limit, Buy at Min | ✅ ON                                                 | Makes sure you still enter even when the copy amount is very small |
| Ignore Trades Under         | $5–$10                                               | Skips tiny "leftover" trades that aren't worth copying             |
| {% endtab %}                |                                                      |                                                                    |

{% tab title="Profile 2: The Whale" %}
**Who is this?** A trader with $1M+ in funds. Their single bets can be tens of thousands of dollars — way more than most people can follow. They also cancel and adjust orders a lot.

**Goal:** Only follow their big, meaningful moves. Ignore the noise. Make sure their huge trades don't drain your balance.

| **Setting**          | **Recommended Value**     | **Why**                                                              |
| -------------------- | ------------------------- | -------------------------------------------------------------------- |
| Ignore Trades Under  | $500–$1,000               | Only copy their serious moves, not their "testing" trades            |
| Min Per Trade        | $5–$10                    | Makes sure each copied trade is worth placing                        |
| Max Spend Per Market | 10% of your total balance | A whale can afford to lose $50k on one market — you can't            |
| Limit Price Offset   | +0.02                     | Whales move prices fast; bid a little higher to make sure you get in |
| {% endtab %}         |                           |                                                                      |

{% tab title="Profile 3: High-Frequency / Algorithm" %}
**Who is this?** A trading bot (or bot-like trader) that makes hundreds of trades every day, grabbing tiny profits each time. Trades are very short and often use complex logic.

**Goal:** Follow the bot's best signals while filtering out the tiny, low-value trades that would just cost you in fees.

| **Setting**            | **Recommended Value**           | **Why**                                                             |
| ---------------------- | ------------------------------- | ------------------------------------------------------------------- |
| Copy Percentage        | % mode (based on their history) | Scales your trade size with the signal strength                     |
| Ignore Trades Under    | $5                              | Key filter — removes micro-trades that aren't worth copying         |
| Max Copy Market Number | 5–10                            | Stops your money from being spread too thin across too many markets |
| Take Profit            | 5%–10%                          | Bots take profits quickly — auto-exit so you don't miss the gain    |
| {% endtab %}           |                                 |                                                                     |

{% tab title="Profile 4: News / Event Trader" %}
**Who is this?** A trader who reacts instantly to breaking news (court rulings, big announcements, viral tweets). Prices can spike or crash in seconds.**Goal:** Get in as fast as possible — speed matters more than getting the perfect price.

| **Setting**                      | **Recommended Value**    | **Why**                                                                      |
| -------------------------------- | ------------------------ | ---------------------------------------------------------------------------- |
| <p>Market Order Slippage<br></p> | 5%–15%                   | Lets you buy even when the price is moving fast — avoids failed orders       |
| Sell Mode                        | Market Order             | Prices drop fast once news is "priced in" — exit immediately at market price |
| Below Min Limit, Buy at Min      | ✅ ON                     | Even a $1 entry is better than missing the move entirely                     |
| Max Spend Per Market             | Fixed amount (e.g., $50) | These trades can go to zero — never risk a large chunk of your balance       |
| {% endtab %}                     |                          |                                                                              |

{% tab title="Profile 5: Low Liquidity / Price Sensitive" %}
**Who is this?** A trader who operates in small, less popular markets where there aren't many buyers and sellers. Entry price matters a lot here — a bad fill can wipe out your profit.

**Goal:** Control your entry price carefully — don't overpay.

| **Setting**          | **Recommended Value** | **Why**                                                                   |
| -------------------- | --------------------- | ------------------------------------------------------------------------- |
| Buy Mode             | Limit Order Copy      | You set the exact price you're willing to pay                             |
| Limit Price Offset   | 0 or +0.01            | Match the trader's price exactly, or go just $0.01 higher to get in line  |
| Limit Order Duration | 120s                  | If not filled in 2 minutes, the price has moved too far — cancel and skip |
| Sell Mode            | Limit Order           | Try to sell at a better price and capture the spread                      |
| {% endtab %}         |                       |                                                                           |

{% tab title="Profile 6: Long-Term / Value Investor" %}
**Who is this?** A patient trader who holds positions for months, waiting for a big event outcome (like an election). They don't react to daily price swings.

**Goal:** Make sure you get in, and don't get scared out by normal short-term price moves.

| **Setting**         | **Recommended Value**          | **Why**                                                  |
| ------------------- | ------------------------------ | -------------------------------------------------------- |
| Limit Price Offset  | +0.03 or higher                | Helps you get filled in low-volume, long-term markets    |
| Stop Loss           | None or very wide (e.g., -50%) | Avoid being kicked out before the final result comes in  |
| Ignore Trades Under | $10–$50                        | Follow their big entries — ignore small portfolio tweaks |
| {% endtab %}        |                                |                                                          |
| {% endtabs %}       |                                |                                                          |

## **Summary: Two Rules That Apply to Every Profile**

**Rule 1 — Maintain Proportionality:** Keep your position ratio identical to the target's. This is the only way to match their ROI %.

**Rule 2 — Set a Circuit Breaker:** Always configure **Max Per Trade** and **Max Per Market**. Even if an expert makes a mistake or gets "tilted," your account will survive to trade another day.


---



<!-- PAGE: copy-trading_faqs.md -->
# FAQs

<details>

<summary><strong>1. How to set up copy trading?</strong></summary>

Two principles for **setting copy trading** parameters:

1\. **Match the position ratio of the target address**.

2\. Don’t spend all your funds too quickly, to avoid small fluctuations wiping out your principal.With small capital, results rely more on luck.

Having **sufficient capital** and following these principles leads to more reasonable and stable settings.You can set up copy trading by following the steps below. If you stick to these, you’ll generally avoid problems:

1. Choose the target address
2. First, confirm which address you want to copy. Try to choose addresses that are not high frequency arbitrage and have a stable trading logic.
3. Choose the copy mode
4. There are two common options:
5. Fixed amount mode: copy each trade with a fixed amount, suitable for testing.
6. Percentage mode: copy based on the target address’s position ratio, which is better for matching long term returns.
7. Set the copy ratio or amount
8. In percentage mode, make sure your capital is sufficient. Otherwise, the calculated amount may fall below the minimum order requirement.
9. Control how fast your funds are used
10. Do not spend all your funds too quickly. Leave room for follow up buys and market fluctuations to avoid small movements wiping out your principal.
11. Check minimum order requirements
12. Both market orders and limit orders have minimum requirements. Orders below the minimum will fail to copy.
13. Confirm sell rules
14. Check whether Sell uses a market order or a limit order.
15. Note that TP and SL only work when Sell uses a market order.
16. Check switch status
17. Make sure copy trading is enabled and not restricted by conditions such as max price or max spend.

In short:Test first, then add more funds. Copy by ratio and always leave enough buffer. More detail, please check "[How To Copy](https://polycop.gitbook.io/polycop-docs/copy-trading/discover-wallets)"

</details>

<details>

<summary><strong>2. How to Find smart money wallets?</strong></summary>

You can find **smart money wallets** through the following methods:

1. **Recommendations on X (Twitter)**.
2. **Top Holders list** under each market on the **official Polymarket website**.
3. The following third-party sites:
   1. <https://polymarket.com/leaderboard>
   2. <https://predicting.top/>
   3. <https://polymarketanalytics.com/traders>
   4. <https://app.future.fun/scouter>

To learn more, please check "[Discover Wallets](/discover-wallets.md)"

</details>

<details>

<summary><strong>3. What kind of smart money is worth copying?</strong></summary>

* **Consistently profitable over time.**
* **Has a large gap between profit and loss,** the total profit amount should be significantly higher than the total loss amount.
* **Operates in markets with sufficient liquidity**, so when you copy their trades, you can enter at similar prices and with comparable position sizes.

</details>

<details>

<summary><strong>4. Why does my total balance change abnormally whenever I buy or sell?</strong></summary>

Polymarket’s billing calculation can be delayed. When you sell, it records both the value of the position you closed and the amount you received after selling. The position value aggregation can also be delayed. That’s why your balance may sometimes appear inaccurate.

However, in PolyCop, the price and value of each token shown in your positions are calculated independently using real time data. The total balance, on the other hand, relies on Polymarket’s data, so it may experience delays

</details>

<details>

<summary><strong>5. Why does it fail when I click Redeem or Auto Redeem?</strong></summary>

Because there are too many users and too many requests, Polymarket has limits on Redeem feature. You need to try again later

or check whether the market for your current token is in a dispute resolution period. Trading are not permitted while a market is in the dispute resolution phase.

</details>

<details>

<summary><strong>6. Why didn't my copy trade buy / sell?</strong></summary>

There are several reasons a trade might get skipped. Work through the checklist below.

**🔴 Didn't Buy — Common Causes**

1\. Your copy amount is below the platform minimum

> Polymarket has a minimum order size: **$1 for market orders** and **5 shares for limit orders**. If your copy ratio is small (e.g. 1%), a target trade of $20 only generates a $0.20 order — which gets rejected automatically.

**Fix:** Enable **"Below Min Limit, Buy at Min ✅"** so the bot rounds up to the minimum instead of skipping. Pair this with **"Ignore Target Trades Under $10–$50"** to make sure you only round up on meaningful trades, not dust.

\
2\. Slippage is too tight — the order was killed (FAK error)

> Polymarket uses **Fill-and-Kill (FAK)** logic on market orders. If the market doesn't have enough liquidity within your slippage range, the order is partially filled or cancelled entirely.

**Fix:** Increase your market order slippage tolerance. Alternatively, switch to a **limit order** and set a **Limit Price Offset of `+0.02`** — this bids slightly above the target's price, improving your fill rate.

\
3\. A spend limit has been hit

> If any of the following limits are maxed out, the bot will skip new buys silently:
>
> * Max Spend Per Yes/No
> * Max Spend Per Market
> * Total Spend Limit
> * Available USDC

**Fix:** Review each limit in your task settings. Sell or close existing positions to free up room — the bot will automatically resume once exposure drops below the limit.

\
**🔴 Didn't Sell — Common Causes**

**1. Sell mode is set to Limit Order, but no one is taking the other side**

> Limit sell orders wait for a counterparty. In low-liquidity markets, your order may sit unfilled indefinitely.

**Fix:** Switch to **Market Order** for selling if you need faster execution. Or check whether your limit order has already expired.

</details>

<details>

<summary><strong>7. I set a 20% stop loss — why did I lose more than 20%?</strong></summary>

There are two common reasons for this：

**Reason 1: Stop loss uses a market order, which has slippage**

All Stop Loss orders execute as **market orders**. When the price hits your stop level, the bot sends an immediate sell at whatever price the market will take.

> In a fast-moving or illiquid market, the actual fill price can be significantly worse than your trigger price — so a 20% stop loss might result in a 25–30% loss by the time the order fills.

**Fix:** This is a fundamental characteristic of market-order stop losses. To account for it, set your stop loss a few percentage points tighter than your actual maximum tolerance. For example, if you can accept 20% loss, set the stop at 15–17%.

**Reason 2: Stop loss silently stopped working after you switched Sell mode**

This is the most commonly missed issue.

> **If your Sell mode is set to Limit Order, TP/SL will NOT function.** The stop loss setting is still visible, but it will not trigger.

This happens because Polymarket does not allow two concurrent limit orders on the same position — so the bot cannot place a stop-loss limit order if a sell limit order is already in place.

**Fix:** Go to your task settings and confirm that **Sell is set to Market Order**. TP/SL only works with market order sell mode.

</details>

<details>

<summary><strong>8. I'm getting an error — "Max holder market limit exceeded". What does this mean?</strong></summary>

> How it works: Every time you enter a new market (a new event/question on Polymarket), it counts as +1 toward this limit. Once you hit the cap, the bot will refuse to copy any new markets — even if you have plenty of funds available.
>
> Exampl&#x65;**:** If Max Copy Market Number = 5 and you're already holding positions in 5 different events, the next trade in a new event will be skipped and trigger this error.

**Fix:**

**Option A — Free up market slots:** Close or sell your positions in one or more existing markets. The count will drop, and the bot will automatically resume copying new markets.

**Option B — Raise the limit:** Increase your Max Copy Market Number setting if you're comfortable holding more markets at once. If you don't want this restriction at all, set it to a large number like `999`.

</details>

<details>

<summary>9<strong>. What is a Merge, and will PolyCop copy it?</strong></summary>

Merge is when a trader combines equal amounts of Yes and No shares in the same market back into pUSD — without waiting for the market to resolve. When your target address performs a Merge, **PolyCop will follow and execute the same Merge operation** on your behalf.

```
100 Yes tokens + 100 No tokens → $100 pUSD
```

Due to slippage during copy trading, your Yes and No share counts may end up slightly unequal. When a Merge occurs, PolyCop **takes the smaller of the two as the limit and merges them in equal amounts** — any leftover shares cannot be merged further. You can either wait for the market to resolve and redeem them at settlement, or manually sell them at any time.

</details>


---



<!-- PAGE: copy-trading_how-to-copy.md -->
# How to Copy

✅️ Indicates a copy trade setup is active.\
❌ Indicates a copy trade setup is paused.

## Set Up Copy Task

{% stepper %}
{% step %}

#### **Access Copy Trade**

Type `/copytrade` in the PolyCop Bot chat, or access it from the main menu. Then click on `+Create Copy Trade`

<figure><img src="/files/k37Wm2Px8RqYR9a3qnFr" alt="" width="563"><figcaption></figcaption></figure>
{% endstep %}

{% step %}

#### **Add a Target Wallet**

Paste the **Wallet Address** or **Polymarket Profile Link** of the trader you want to follow into the bot chat. The bot will generate a control panel for that specific target.

<figure><img src="/files/MoPQlhNUgj9CwHym2Tyb" alt="" width="375"><figcaption></figcaption></figure>
{% endstep %}

{% step %}

#### Configure Your Copy Settings

Before activating, configure your copy parameters. You can either:

* Set **Default Copy Trading Settings** — applies to all new copy tasks automatically
* Or customize settings **per individual target**

{% hint style="info" %}
For a full explanation of every parameter, see the [**Parameter Guide**](/copy-trading/copy-trading-settings-guide.md#parameter-guide)
{% endhint %}
{% endstep %}

{% step %}

#### Activate the Task

Click **"Active"** — the button turns **Green ✅**.

{% hint style="warning" %}
Make sure you have enough **Available USDC** in your PolyCop wallet. Funds locked in open positions cannot be used for new copy trades.
{% endhint %}
{% endstep %}

{% step %}

#### Stop or Pause

* **Pause**: Toggle the task off (turns ❌). No new trades will be copied, but existing positions remain open.
* **Delete**: Removes the copy task entirely. Existing positions are **not** automatically closed.
  {% endstep %}
  {% endstepper %}

## Key Mechanics to Understand

How buy amounts are calculated

> Your copy buy value = **Target's trade value × Your percentage**
>
> *Example: Target buys $200, your copy % is 10% → You buy $20*

How sell amounts are calculated

> Your sell value = **Target's sell value ÷ Target's position × Your position**
>
> Selling is proportional — if the target sells 50% of their position, you sell 50% of yours.

## Quick-Start Checklist

* [ ] Paste target wallet address into the bot
* [ ] Set Copy Percentage or Fixed Amount
* [ ] Enable "Below Min Limit, Buy at Min" if using small %
* [ ] Set "Ignore Target Wallet Trades Under" to $5–$10 (filters dust trades)
* [ ] Set a Max Spend limit to protect your capital
* [ ] Click **Active** ✅


---



<!-- PAGE: copy-trading_positions.md -->
# Positions

## **How to Open the Positions Page**

Type `/positions` in the PolyCop Bot chat to open your Positions dashboard.

<figure><img src="/files/fkndicU7aeJGLCqJsS3V" alt="" width="563"><figcaption></figcaption></figure>

## **What You'll See**

At the top of the page, you'll find a snapshot of your account:

| **Field**             | **What it means**                                         |
| --------------------- | --------------------------------------------------------- |
| **Total Balance**     | Your total funds in the wallet (including open positions) |
| **Available Balance** | Funds you can still use to place new trades               |
| **Positions Value**   | The current market value of all your open positions       |
| **Positions PNL**     | Your total profit or loss across all open positions       |

## **Tips**

* **Use** Refresh if your balance or positions seem outdated — PolyMarket data can sometimes lag.
* Enable **Auto Redeem** so you never miss claiming your winnings after a market resolves.
* Use **AI Find Copyable Wallets** to discover profitable traders to copy if you're not sure who to follow.


---



<!-- PAGE: copy-trading_pro-tips.md -->
# Pro Tips

* **New to copy trading?** Start with a small % (e.g., 5%), observe for a few days, then scale up.
* **Following a whale?** Use Copy Percentage + set Max Per Trade to cap your exposure.
* **Following a high-frequency bot?** Enable "Below Min Limit" + set "Ignore Under $5" to filter noise.
* **Not sure which settings to use?** → See [**Recommended Settings by Trader Type →**](/copy-trading/copy-trading-settings-guide.md#recommended-settings-by-trader-type)


---



<!-- PAGE: copy-trading_sub-wallet-copy-trading.md -->
# Sub-Wallet Copy Trading

## Core Concepts

| Term        | Description                                                                                   |
| ----------- | --------------------------------------------------------------------------------------------- |
| Main Wallet | Your primary wallet and the source of funds                                                   |
| Sub-Wallet  | A new wallet automatically generated by the system, dedicated to a specific copy trading task |

{% hint style="info" %}
Each sub-wallet created in PolyCop is a fully independent Polymarket wallet. This means every sub-wallet has its own Polymarket profile address and trading history — and may be independently eligible for any future Polymarket airdrops.
{% endhint %}

## How to Set Up Sub-Wallet Copy Trading

{% stepper %}
{% step %}

#### Go to the Copy Trade Homepage

Open the Copy Trade page. You will see the following options:

* `Create Copy Trade` — Copy trade using your main wallet
* `Use Sub-Wallet Create Copy` — Click this to copy trade using a sub-wallet
  {% endstep %}

{% step %}

#### Enter the Target Wallet Address

Enter the address of the wallet you want to copy
{% endstep %}

{% step %}

#### System Generates a New Sub-Wallet

* Upon confirmation, the system will automatically generate a brand new sub-wallet for you
* You will be immediately prompted to transfer funds from your main wallet into this sub-wallet
  {% endstep %}

{% step %}

#### Transfer Funds

* Confirm the prompt to transfer funds from your main wallet to the sub-wallet
* If the transfer fails and the balance shows as 0, you can manually add funds using the "Add Funds" button at the bottom of the task page
* If the balance appears incorrect, try refreshing the page first before taking further action
  {% endstep %}

{% step %}

#### View and Manage Your Task

* Once created, click to view the copy trading task details
* At the bottom of the task details page, there is a button to export the private key of your sub-wallet. Keep this stored safely.
  {% endstep %}
  {% endstepper %}

## FAQs

<details>

<summary><strong>Is the sub-wallet a new wallet or my existing wallet?</strong></summary>

Each time you use the "Use Sub-Wallet Create Copy" feature, the system automatically generates a completely new and independent wallet address.

</details>

<details>

<summary><strong>I am currently copy trading with my main wallet and want to switch to sub-wallets to copy 3 different addresses. How do I do this?</strong></summary>

First, stop or delete your existing copy trading task on the main wallet. Then, click `+ Use Sub-Wallet Create Copy` separately for each target address. Each sub-wallet will operate independently without affecting the others.

</details>

<details>

<summary><strong>How are funds allocated to the sub-wallet?</strong></summary>

When creating a sub-wallet copy trading task, the system will prompt you to transfer funds from your main wallet. You can allocate a different amount to each sub-wallet, keeping funds fully separated across tasks.

</details>

<details>

<summary><strong>The sub-wallet balance shows 0 after creation. What should I do?</strong></summary>

First, tap "**Refresh"** in the page. If the balance still shows 0, the initial transfer may have failed. Use the "**Add Funds**" button at the bottom of the task page to manually deposit funds into the sub-wallet.

</details>

<details>

<summary><strong>How do I retrieve the private key of my sub-wallet?</strong></summary>

Navigate to the relevant copy trading task details page. At the bottom of the page, there is an option to export the private key of the sub-wallet.

</details>

<details>

<summary><strong>Can the same target address be copied by both my main wallet and a sub-wallet at the same time?</strong></summary>

Yes, main and sub-wallets can now copy the exact same target address simultaneously.

</details>

## Important Notes

* Always export and securely store the private key of each sub-wallet. It cannot be recovered if lost.
* Each sub-wallet holds funds independently and does not interfere with other sub-wallets or your main wallet.


---



<!-- PAGE: discover-wallets.md -->
# DISCOVER WALLETS

## Method 1: Use the PolyCop Leaderboard

A dashboard of Top copy performing addresses, generated by a backtesting algorithm that simulates the slippage behavior occurring in real-world copy trading.

<https://polycop.ai/leaderboard>

<img src="/files/LUyJS5G7VrFUbXpHXvIl" alt="" width="563">

## Method 2: PolyCop Top Profitable Users (In-Bot Leaderboard)

The fastest way to find proven wallets — without leaving the bot. PolyCop maintains its own **Profit Leaderboard** built exclusively from real PolyCop users' trading activity. These are addresses that have already been trading on Polymarket through PolyCop, so their performance is directly relevant to copy trading.

{% stepper %}
{% step %}
**Tap PolyCop Top Profitable Users from the main menu**

<figure><img src="/files/YlFUAReZyRarlGs8MAlf" alt="" width="563"><figcaption></figcaption></figure>
{% endstep %}

{% step %}
**What You'll See**

The leaderboard displays the **top 25 most profitable PolyCop user addresses**, ranked by PnL over your selected time window (1D/7D/30D/90D)

{% hint style="info" %}
**Tip:** Switch between time windows to find wallets that are consistently profitable — not just a one-day spike. A wallet that ranks highly on both **7D** and **30D** is a much stronger copy trading candidate.
{% endhint %}
{% endstep %}

{% step %}
**How to Use This List**

1. Browse the leaderboard and tap any address that catches your eye
2. Use **🧠 AI Analysis Copyable Wallets** to run a full analysis on that address before copying
3. If the AI report looks good, tap **Copy Trade** to start copying

> Rankings are refreshed regularly — tap **🔄 Refresh** to get the latest data.
> {% endstep %}
> {% endstepper %}

## Method 3: Find Wallets from Polymarket Markets

{% stepper %}
{% step %}
**Open the Polymarket official website and click any market**

<https://polymarket.com/>

<img src="/files/HjZlWn1lpc6aRaFjrkHC" alt="" width="563">
{% endstep %}

{% step %}
**Scroll down and click Top Holder**

<img src="/files/LHDgJXIj4WLZjQXMjglp" alt="" width="563">
{% endstep %}

{% step %}
**Hover over the name to see the profit amount. Find addresses with strong profitability and click to enter their profile**

<img src="/files/KZomQdfr8aWUViIc3vTU" alt="" width="563">

The address shown above is not suitable for copy trading, because 58k ÷ 8m = 0.725%. It has less than 1% profit. You should look for addresses with higher profit rates, preferably above 2%.

The address below has a profit rate of 9.7%, which is OK. This is an initial screening method; you need to continue checking the Gain/Loss ratio on the address’s main page.

<img src="/files/rzZNnp14XTekIsCe2Hpc" alt="" width="563">
{% endstep %}

{% step %}
**Check the address profit curve and trading activity.**

If it is suitable for copy trading, copy this address

Ps. The bigger the Gain/Loss, the better. Personally, I prefer Gain/Loss greater than 2.

<img src="/files/buADt3ftpsZx5w9p8lEf" alt="" width="563">

&#x20;

<img src="/files/HfBJbH7fstIFjoj2H1Yj" alt="" width="563">
{% endstep %}

{% step %}
**Paste the address directly into the PolyCop Bot input box and send it**

<https://t.me/PolyCop_BOT?start=ref_WalletBook>

<img src="/files/XYH50TDnFmatYqAL9mC7" alt="" width="563">

&#x20;

<img src="/files/hCth9PCItG5z2y1ONC88" alt="" width="563">
{% endstep %}
{% endstepper %}

## Method 4: Use the Polymarket Leaderboard

### **Polymarket user dashboard**

<https://polymarket.com/leaderboard>

You can **filter** profitable addresses by **Weekly, Monthly, or All time** performance. You can also **filter by categories** such as **Sports, Crypto**, and more. The leaderboard is **continuously updated**:

<img src="/files/8kHxwSi8Pg3sqC03UXzg" alt="" width="563">

## Method 5: Use External Trader Dashboards

### **X Traders dashboard**

<https://predicting.top/>

<img src="/files/EbmgZ7LDyDDvMbH4VmqK" alt="" width="563">

Do your own research. It helps you make profits.

Do not copy addresses that are not suitable for copy trading.

**Do not copy addresses that buy and sell immediately just to make a few cents.**

**Be cautious when copying addresses with a “perfect” equity curve and 0 drawdown.**

A simple rule of thumb is to **look for addresses** with a **high Gain to Loss ratio.**

When viewing a Polymarket wallet page on desktop or with your phone in landscape mode, you can click the ⓘ icon to see the Gain and Loss data.

<img src="/files/tie9vG87WG5ycOYsbEi5" alt="" width="563">

### **Two principles for setting copy trading parameters:**

1. Match the position ratio of the target address.
2. Don’t spend all your funds too quickly, to avoid small fluctuations wiping out your principal.

With small capital, results rely more on luck. Having **sufficient capital** and following these principles leads to more reasonable and stable settings.

For deeper analysis, check the trading activity and the Closed positions list. Switch the Closed list to time order to review the wallet’s historical profit and loss performance.

<img src="/files/dVEQTVGuTCY6j6FUFIj0" alt="" width="563">


---



<!-- PAGE: discover-wallets_ai-analysis-copyable-wallets.md -->
# AI Analysis: Copyable Wallets

The core value of PolyCop AI is its ability to cut through surface-level stats and reveal true copy-trading profitability. A Polymarket trader with a 90% win rate and tens of thousands in profit may look impressive — but that doesn't always mean they're worth copying.

Use PolyCop's AI analysis to determine whether a wallet is a genuine edge trader or simply an arbitrage machine exploiting market inefficiencies.

Two ways to get started:

* &#x20;**Leaderboard** — Browse and shortlist addresses for analysis: <https://polycop.ai/leaderboard>
* &#x20;**PolyCop Bot** — Paste any address directly into the bot and tap the AI Analysis button to receive your full report: <https://t.me/PolyCop_BOT>

## How to Use It

{% stepper %}
{% step %}
**Copy Wallet Address from PolyMarket**

<figure><img src="/files/ZCqYT3euQvokiQ9wb4a2" alt="" width="563"><figcaption></figcaption></figure>
{% endstep %}

{% step %}
**Paste**

Paste the wallet address directly on our bot and click "AI Analysis".

<figure><img src="/files/rakkV9mPvs2VPxYzgNb7" alt="" width="188"><figcaption></figcaption></figure>
{% endstep %}

{% step %}
**The PolyCop AI engine will return a full analysis report within seconds.**
{% endstep %}
{% endstepper %}

{% hint style="info" %}
Pro Tips: In rare cases, some Polymarket traders hide their real transaction address. If your copy trading never triggers, this could be why.

👉 For the full guide, see: [Medium - How to Find a Polymarket Trader’s Real Transaction Address](https://polycoptrader.medium.com/how-to-find-a-polymarket-traders-real-transaction-address-d86ad089d870)
{% endhint %}

## Understanding the Report

### Tier 1: The "Life or Death" Copy-Trading Metrics

These three metrics dictate whether you should copy-trade an address. If this section flashes red or shows negative numbers, abandon the address immediately.

{% hint style="info" %}
All data is based on the address's most recent 4,000 transactions. It does not include all transaction data.
{% endhint %}

<details>

<summary><strong>1. Actual Total PnL</strong></summary>

* Meaning: The real net profit of this address across all historical trades on Polymarket.
* Note: This data includes Unrealized PnL (floating profits and losses from open positions). We automatically calculate the value of their unsettled holdings based on the current market order book prices to give you the most accurate real-time net worth.

</details>

<details>

<summary><strong>2. Backtest Copy Pnl —— 【The Most Crucial Metric】</strong></summary>

* Meaning: If you used a copy-trading bot to perfectly replicate all their actions, but assumed a 2% higher cost on every buy and a 2% lower return on every sell (simulating slippage friction from thin order books, gas fees, copy delays, etc.), how much money would you actually make?

**Evaluation Criteria:**

* Positive & close to Actual PnL: An excellent address! This indicates their profit margins are substantial and completely immune to copy-trading friction.
* Negative: Absolute copy-trading poison (Toxic). Even if they are actually profitable, they are only capturing a tiny 1%\~2% spread. If you copy them, the slippage will guarantee a net loss for your wallet.

</details>

<details>

<summary><strong>3. Slippage Cost Rate</strong></summary>

* Meaning: The percentage of their actual profit that would be eaten away by copy-trading friction. Formula: `(Actual PnL - Backtest Copy PnL) / |Actual PnL|`.

Evaluation Criteria:

`< 10%`: A god-tier hunter with extremely lucrative profit margins.

`10% - 30%`: Healthy, representing normal trading friction.

`> 60%`: Danger zone, indicating high-frequency, low-margin trading.

`> 100%`: A pure hedging/arbitrage bot. Copying will result in guaranteed losses.

</details>

### Tier 2: Trading Style & Habit Metrics <a href="#tier-2-trading-style-and-habit-metrics" id="tier-2-trading-style-and-habit-metrics"></a>

This section helps you understand the address's trading style (e.g., long-term trend trading vs. microscopic scalping).

<details>

<summary><strong>4. Avg Profit/Loss Ratio</strong></summary>

* Meaning: Total Gross Profit ÷ Total Gross Loss.

**Evaluation Criteria:**

If `> 1.0`, it means they win big and cut losses quickly—the ideal copy-trading target.

If `< 0.3`, they are "winning pennies and losing dollars," posing a massive liquidation risk if you follow them long-term.

</details>

<details>

<summary><strong>5. Hedged Markets</strong></summary>

* Meaning: The percentage of markets where this address bought both 'Yes' and 'No' shares simultaneously.
* Deep Dive: Why avoid high hedging rates? Because retail traders rarely buy both sides. A hedging rate `> 30%` usually indicates a "Market Maker" or "Arb Bot". They are scraping microscopic order book spreads, and these tiny profits will be instantly wiped out by your copy-trading slippage.

</details>

<details>

<summary><strong>6. Win Rate</strong></summary>

* Meaning: The percentage of historical markets traded that resulted in a positive return (profit).
* Busting the Myth: On Polymarket, a 90% win rate does not make someone a master! Many arbitrage bots boast 95% win rates with abysmal actual profits. True masters (those who hunt for massive upsets or ride long-term trends) might only have a `40% - 65%` win rate, but a single win yields multi-fold returns that cover all previous losses.

</details>

<details>

<summary><strong>7. Avg Market ROI</strong></summary>

* Meaning: The average percentage return they achieve per market entered. A higher number indicates a preference for capturing "high-odds" longshots or maintaining extremely thick profit margins.

</details>

<details>

<summary><strong>8. Total Markets Traded &#x26; Volume</strong></summary>

* Meaning: Reflects the account's activity level and capital size. Accounts with massive trading volume but tiny PnL are often institutions or market makers not suitable for retail copying.

</details>

### Tier 3: Recent Momentum & Trend Metrics <a href="#tier-3-recent-momentum-and-trend-metrics" id="tier-3-recent-momentum-and-trend-metrics"></a>

A stellar historical record doesn't guarantee future success. Because Polymarket trends shift rapidly, we specifically extract data from the address's last 20 markets.

**Recent 20 Markets**

Includes the Win Rate, Actual PnL, Backtest Copy PnL, and Slippage Cost Rate for their most recent 20 trades.

{% hint style="success" icon="eyes" %}
Why it matters: If an address has a historical Total PnL of +$50,000 but a Recent 20 Backtest Copy PnL of -$5,000, it means their strategy has failed, the market narrative has shifted, or they are enduring a severe drawdown streak. Only copy addresses with hot recent form.
{% endhint %}

## Summary: How to Spot the Perfect Copy Target?

When you review a PolyCop AI report, a highly profitable and safe target to copy usually checks these boxes:

1\. PolyCop Score > 60/100.

2\. Backtest Copy Pnl is solidly positive and relatively close to the Actual PnL.

3\. Slippage Cost Rate is low (preferably `< 20%`).

4\. Hedged Markets ratio is minimal (`< 30%`), proving they take directional bets rather than just market-making.

5\. Recent 20 Markets show sustained profitability without a sudden cliff-drop in performance.

You should avoid such examples:

`Actual PnL: +$12,000`

`Backtest Copy Pnl: -$3,000`

`Hedged Markets: 85%`

By filtering wallets through these rigorous metrics, PolyCop ensures you follow the smartest money on the chain. Please note that these methods are only intended to help you filter out 80% of incorrect addresses. They are not a 100% guarantee that an address is suitable for copy trading. For example, you may also need to manually check the market's order book liquidity when the target address places an order. You should verify whether the liquidity is sufficient or if the spread between the buy and sell orders is very large.

You still need to perform further analysis based on your own experience and other behavioral patterns. Ultimately, the final judgment remains your responsibility.

## Next Step

Once you've found a wallet worth copying, tap **Copy Trade** directly from the report to set up your copy trading parameters.

For guidance on configuring your parameters, see the [Copy Trading Settings Guide](https://docs.polycop.ai/copy-trading/copy-trading-settings-guide).


---



<!-- PAGE: discover-wallets_openclaw-finding-and-analyzing-wallets.md -->
# OpenClaw: Finding and Analyzing Wallets

You can have OpenClaw search for holders within a specific market and extract their trading data. By calculating the backtested copy-trading profit using a specific model (Buy with +2% slippage, Sell with -2% slippage, and Redeem with 0 loss), a positive result indicates that the address is suitable for copy trading.

* Actual Total PnL: **$5935.88**
* Backtest Total PnL: **$5406.58** (Buy +2%, Sell -2%, Redeem 0 Slippage)
* Slippage Cost Rate: **12.92%**
* Avg Profit/Loss Ratio: **1.24**
* Avg Market ROI: **11.15%**
* Total Markets Traded: **121**
* Hedged Markets: **7 (5.8%)**
* Win Rate: **58.82%**

Additionally, you can have it analyze the PnL of the last 20 trades to evaluate the address's recent performance.

* API for retrieving market Holder addresses: GET <https://data-api.polymarket.com/v1/market-positions?market={condition\\_id}\\&status=ALL\\&sortBy=TOTAL\\_PNL\\&sortDirection=DESC\\&limit=20>
* API for retrieving an address's transaction history: GET <https://data-api.polymarket.com/activity?user={wallet\\_address}\\&limit=500\\&offset={offset}>

<img src="/files/LTst0A47G6Yb2yjPCav9" alt="" width="563">


---



<!-- PAGE: fees-and-referrals.md -->
# FEES & REFERRALS

- [Fees](https://docs.polycop.ai/fees-and-referrals/fees-and-referrals.md)
- [Referrals](https://docs.polycop.ai/fees-and-referrals/referrals.md): Invite friends to PolyCop and earn passive rewards every time they trade. Track your earnings, monitor your referral network, and grow your income — all from one place.


---



<!-- PAGE: fees-and-referrals_fees-and-referrals.md -->
# Fees

### 1. Transaction Fees (The Lowest in the Market)

We charge a flat 0.5% transaction fee, which is exactly half of the standard market rate. We are proud to offer the lowest fees available among Polymarket copy trading bots.

Additionally, as an extra benefit to our users, **we cover the gas fees** on your behalf whenever you redeem your funds.

When using sub-wallet copy trading, PolyCop's fees are deducted from your **main wallet**. Please ensure your main wallet maintains a sufficient balance to cover fees.

### 2. Gas Fees: Always $0

You **do not** need to hold POL (formerly MATIC) in your wallet to pay for network gas fees.

* **Redeems:** To improve your capital utilization, Auto Redeem will sell your settled markets faster and more automatically than PolyMarket. **We specifically cover the gas fees for all your Redeem actions.** When a market resolves, you can claim your winnings seamlessly without ever worrying about having enough gas tokens.
* **Seamless Trading:** You can start copying, trading, and claiming profits immediately with just your stablecoins.

### 3. Deposit & Transfer Fees

We do not charge any internal transfer fees. However, depending on how you fund your wallet, standard blockchain network costs may apply:

* **Direct Deposit (Zero Fee):** Send **USDC.e** (Bridged USDC) directly to your trading address via the **Polygon Network**. This incurs no additional fees from our side.
* **Cross-Chain / Swap Deposits (Low Fee):** If you send Native USDC or USDT to your deposit address, the system will automatically handle the conversion. This will incur very low, standard cross-chain bridge or DEX swap routing fees (charged by the network, not by us).

> **100% On-Chain Transparency**
>
> We believe in absolute transparency. Every single transaction, trade, and fee deduction is recorded on the blockchain.
>
> **How to verify your fees:**
>
> 1. Copy your bot's wallet address.
> 2. Paste it into [Polygonscan](https://polygonscan.com/).
> 3. You can view all your transactions or download a CSV file of your complete transaction history to independently calculate and verify your trading volume and fees.


---



<!-- PAGE: fees-and-referrals_referrals.md -->
# Referrals

## **How it Works**

PolyCop uses a **2-level referral system**:

| **Level**   | **Who**                      | **Your Reward**              |
| ----------- | ---------------------------- | ---------------------------- |
| **Level 1** | People you invite directly   | **25%** of the fees they pay |
| **Level 2** | People your referrals invite | **3%** of the fees they pay  |

## **Getting Started**

{% stepper %}
{% step %}

#### 1. Open the Referrals Page

Type `/referrals` in the PolyCop Bot chat, or access it from the main menu.

<figure><img src="/files/Bw4y27iH06A3itc0avgb" alt="" width="563"><figcaption></figcaption></figure>
{% endstep %}

{% step %}

#### 2. Copy Your Referral Link

Your personal referral link is displayed at the bottom of the page. Tap it to copy and share it with friends, your community, or on social media.&#x20;

You can also update your own referral code. For more details, see [Change Referral Code](https://app.gitbook.com/o/ju5TX3kfy1dQBiMDBn9v/s/6RH958mIbJRqog5izKje/~/edit/~/changes/31/fees-and-referrals/referrals#change-your-referral-code).

`https://t.me/PolyCop_BOT?start=ref_yourcode`
{% endstep %}

{% step %}

#### Share & Earn

Once someone signs up using your link and starts trading, you'll automatically start earning a share of their fees.
{% endstep %}
{% endstepper %}

## **Your Referral Stats**

Your stats are **updated every 30 minutes**. Here's what each field means:

| Field              | What it means                                              |
| ------------------ | ---------------------------------------------------------- |
| **Users Referred** | Total number of people you've referred (direct + indirect) |
| **Total Rewards**  | All rewards you've earned so far                           |
| **Total Paid**     | Rewards that have already been sent to your wallet         |
| **Total Unpaid**   | Rewards that are pending payout                            |

## **Payouts**

* Rewards are **paid out** **daily** at approximately 8:00 UTC and sent directly to your Polymarket Profile address. Due to network conditions, payouts may occasionally be delayed by 10 minutes or more — please be patient.
* You must have at least **$10 in unpaid rewards** to be eligible for a payout.
* PolyCop's fee is only deducted once users' accumulated trading volume reaches $600. This means you won't see any commissions when users first start trading — they will appear once their volume threshold is reached. For more details, see [Fees](https://docs.polycop.ai/fees-and-referrals/pages/x5Q3GrJeCDwPa2HP7QOu#id-1.-transaction-fees-the-lowest-in-the-market).
* Rewards are paid in **pUSD**.

> ⚠️ If your unpaid balance is below $10, your rewards will carry over until the threshold is reached.

## **Change Your Referral Code**

Want a custom referral code? You can change it anytime:

1. Open `/referrals`
2. Tap **Change Referral Code**
3. Enter your desired code when prompted


---



<!-- PAGE: getting-started.md -->
# GETTING STARTED

- [Wallet Setup](https://docs.polycop.ai/getting-started/wallet-setup.md): Set up your PolyCop wallet for Polymarket copy trading and manual trading. Learn your deposit address, trading address, private key export, MetaMask import, and direct Polymarket login.
- [Deposit](https://docs.polycop.ai/getting-started/deposit.md): To start copy trading or place manual trades on PolyCop, you need to deposit funds into your PolyCop wallet first.
- [Withdraw](https://docs.polycop.ai/getting-started/withdraw.md): You can withdraw your funds from PolyCop at any time. Withdrawals are sent to your personal external wallet address on the Polygon network.
- [FAQs](https://docs.polycop.ai/getting-started/faqs.md)


---



<!-- PAGE: getting-started_deposit.md -->
# Deposit

## Which Address Should I Deposit To?

Use the **Deposit Address** displayed in the `/start` menu or the **Wallet** page in the bot.You have two deposit options:

| **Method**                                                                   | **Address to Use**                                                 | **Min Amount**                           | **Notes**                                              |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------ | ---------------------------------------- | ------------------------------------------------------ |
| **Option A:** Cross-chain (**Solana**, Polygon, **ETH, BSC**, ARB, OP, Base) | Deposit Address                                                    | $10 USDC / USDT                          | Low cross-chain bridge fee / very low swap fee         |
| **Option B**: Directly on Polygon - USDC.e / USDC / USDT / pUSD (Polygon)    | <p>Trading Address</p><p><em>(Polymarket Profile Address)</em></p> | <p>$5 USDC.e / USDC / USDT/ pUSD<br></p> | <p>No fee — <strong>fastest</strong> </p><p>option</p> |

{% hint style="info" %}
Cross-chain transfers can sometimes take 10 minutes or more — please be patient. Remember to tap **Refresh** in your `/wallet` to check your updated balance!
{% endhint %}

{% tabs %}
{% tab title="Option A" %}
**Option A: Deposit Address (Multi-chain, recommended for most users)**

Send funds to your **Deposit Address** from any supported network. PolyCop integrates Polymarket's official cross-chain bridge to handle the conversion automatically.**Supported Networks:**

| **Network**  | **Supported Tokens**                     |
| ------------ | ---------------------------------------- |
| **Polygon**  | USDC, USDT *(No cross-chain bridge fee)* |
| **Ethereum** | ETH, USDC, USDT                          |
| **Arbitrum** | ARB, USDC, USDT                          |
| **OP**       | USDC, USDT                               |
| **Base**     | USDC, USDT                               |
| **BSC**      | BNB, USDC, USDT                          |
| **Solana**   | SOL, USDC                                |
| {% endtab %} |                                          |

{% tab title="Option B" %}
**Option B: PolyMarket Profile Address (Polygon only, zero fee)**

Send **USDC.E / USDC / USDT**/ **pUSD** directly to your **PolyMarket Profile Address** on the **Polygon network only**.

* Minimum: **$5**
* No cross-chain bridge fee, no swap fee.

{% hint style="danger" %}
Only use this option if you are sending from Polygon.
{% endhint %}
{% endtab %}
{% endtabs %}

## Minimum Deposit Requirements

* **Minimum for cross-chain bridge deposit:** $10
* **Minimum to start copy trading:** <mark style="background-color:$warning;">$50</mark>

{% hint style="info" %}
**Why $50 for copy trading?** If your capital is too low, trades cannot be copied proportionally, which results in very poor performance. After initial testing, use more funds to ensure you can truly match the target address's returns.
{% endhint %}

## How to Deposit (Step-by-Step)

1. Open the PolyCop bot and tap **`Wallet`** from the main menu.
2. Your deposit addresses for each network are listed — tap any address to copy it.
3. Send funds from your external wallet or exchange to the corresponding address.

<figure><img src="/files/wip0XhtS90PRIWdX0f5L" alt="" width="563"><figcaption></figcaption></figure>

<figure><img src="https://ecnasykcedui.feishu.cn/space/api/box/stream/download/asynccode/?code=NzE1MGNkZWEwZWNlNjM0ZmJiZTVjMGZjY2E0MzM4ZGRfYjJWQ3dWN2ozNGxlVjdxYktYeE5FSW5ES1lWQW8zOUZfVG9rZW46QzR2a2JxcjVFb3NpY2Z4enZmZ2NuenlYblZlXzE3NzUwNDEyODM6MTc3NTA0NDg4M19WNA" alt=""><figcaption></figcaption></figure>

## Deposit Troubleshooting

PolyCop directly integrates the official Polymarket Cross-Chain Bridge. For detailed instructions or troubleshooting, refer to:

* 📖 **Step-by-Step Tutorial:** [Polymarket Transfer Guide & FAQs](https://intercom.help/funxyz/en/articles/10003876-transfer-crypto-guide-faqs#h_2834613ca7)
* 💬 **Customer Support:** If your deposit has not arrived, contact the Polymarket team via the "Let's Talk" button at [fun.xyz](https://fun.xyz/).
* 🔧 **Wrong network / sent POL by mistake?** Recover your funds here: <https://recovery.polymarket.com/> *(Select the correct blockchain network before connecting your wallet.)*

## Deposit with Fiat Currency

> This guide explains how to deposit fiat currency (e.g. USD, EUR) directly into your PolyCop wallet if you don't already hold crypto. There are two methods depending on whether you have an existing exchange account.

### Overview

To trade on Polymarket, you need stablecoin on the **Polygon network** in your Polymarket Profile Address. This guide covers two ways to get there:

* **Method 1** — Transfer from an existing exchange (Coinbase, Binance, Kraken, etc.)
* **Method 2** — Buy directly with a credit/debit card using **MoonPay** (no exchange account needed)

### Before You Begin

Regardless of which method you choose, you first need to find your **Polymarket Profile Address** — this is the on-chain wallet address on the Polygon network where your funds will be deposited.

1. Open the PolyCop bot and run `/wallet`.
2. Copy your **Polymarket Profile Address**.

> ⚠️ Always double-check the address before confirming any transaction. Crypto transactions cannot be reversed once sent.

### Method 1: Buy Directly with MoonPay&#x20;

If you don't have a crypto exchange account, **MoonPay** is the easiest way to purchase USDC and send it directly to your Polymarket Profile Address in one step.

> **What is MoonPay?** MoonPay is a regulated fiat-to-crypto payment platform, founded in 2019 and trusted by over 35 million verified users across 180+ countries. It lets you buy cryptocurrency using a credit card, debit card, Apple Pay, Google Pay, bank transfer, or PayPal — no separate exchange account required.

{% stepper %}
{% step %}

#### **Access MoonPay and Create an Account**

* **Web:** <https://www.moonpay.com>
* **Mobile:** Download the MoonPay app from the App Store or Google Play

> 🔒 Only download from official channels. Verify the URL or app publisher before proceeding — always use official sources to stay safe.

* Sign up with your email address.
  {% endstep %}

{% step %}

#### **Select the Crypto  and Amount to Buy**

* Tap **Buy**.
* Click the currency selector and search for **USDC**.
* Select **USDC on Polygon** (look for the Polygon logo).
* Enter the amount

<figure><img src="/files/KU7NoI19jHTsfYrMtndg" alt=""><figcaption></figcaption></figure>
{% endstep %}

{% step %}

#### **Complete Identity Verification (KYC)**

Prepare a government-issued ID and complete the facial recognition step. This is a one-time process and typically takes a few minutes.
{% endstep %}

{% step %}

#### **Enter Your Polymarket Profile Address**

* Paste your **Polymarket Profile Address** copied from `/wallet` in the PolyCop bot.
* Confirm the selected network is **Polygon** before proceeding.
  {% endstep %}

{% step %}

#### **Select Payment Method and Confirm**

Choose your payment method, enter the amount, review the fees, and confirm. Your USDC will be sent and converted to pUSD (Polymarket USD) directly to your Polymarket Profile Address on Polygon.
{% endstep %}

{% step %}

#### Delivery and Tracking

* You'll receive a confirmation email or tap the Activity (🕓 icon) in the top right corner of the MoonPay app to track the order status.&#x20;
* Once the transaction finalizes, run `/start` or `/wallet` and tap Refresh in the PolyCop bot to confirm your funds have arrived. This usually takes 10 minutes or longer.
  {% endstep %}
  {% endstepper %}

> - **Fees:** MoonPay charges a service fee on each transaction. For credit/debit card and PayPal payments, fees typically range from **3%–5%**. The exact amount is always shown before you confirm, so check the **"You will receive"** figure to understand the net amount after fees.
> - **Regional availability:** MoonPay is available in most countries, but supported payment methods vary by region. For example, PayPal is only available in the US, UK, and EU; Venmo is US-only; SEPA bank transfers are available across EU countries. Check the full list of supported countries and payment methods here: [MoonPay Supported Payment Methods](https://support.moonpay.com/en/articles/380823-moonpay-s-supported-payment-methods).
> - Need More Help? For further assistance with your MoonPay purchase, visit the [MoonPay Help Center](https://support.moonpay.com/en/).

### Method 2: Transfer from a Crypto Exchange

If you already have an account on a major exchange such as **Coinbase**, **Binance**, or **Kraken**, this is the fastest method.

1. Log in to your exchange account.
2. Purchase **USDC** or **USDT** using your fiat currency (e.g. via bank transfer or card). Typically, you'll find this under **"Deposit"** or **"Add Funds”** on the exchange, which offers options to deposit fiat currency.
3. Go to the **Withdraw / Send** section of the exchange.
4. Paste your **Polymarket Profile Address** as the destination.
5. **Important:** Set the withdrawal network to **Polygon**. Do not use Ethereum mainnet.
6. Confirm and submit the transaction.

Your funds will arrive in your PolyCop wallet within a few minutes once confirmed on-chain.

### Summary

| Item                    | Method 1: Exchange Transfer  | Method 2: MoonPay        |
| ----------------------- | ---------------------------- | ------------------------ |
| Exchange account needed | Yes                          | No                       |
| KYC required            | Already done                 | First-time only          |
| Network                 | Must select Polygon manually | Must select Polygon USDC |
| Speed                   | A few minutes                | A few minutes after KYC  |

> ⚠️ **Security reminder:** Always use official sources when downloading apps or visiting payment platforms. Be cautious of phishing sites and fake apps.

##

## What Can I Do After Depositing?

After depositing funds, you can:

1. [**Create copy trades**](https://docs.polycop.ai/copy-trading/how-to-copy) — follow target addresses and auto-copy their trades.
2. [**Place your own trades**](/manual-trading/how-to-start-manual-trading.md) — use market or limit orders directly.
3. **Monitor your positions** — track PnL, open trades, and account balance.
4. **Adjust copy settings** — change percentages, max spend, or risk limits.
5. **Withdraw funds** — anytime, to your deposit or personal wallet address.


---



<!-- PAGE: getting-started_faqs.md -->
# FAQs

<details>

<summary><strong>Why is the wallet address I exported different from my Deposit Address or Trading Address?</strong></summary>

Polymarket's system generates **three distinct addresses** for you. This is a common source of confusion — here's what each one does:

| Address                                               | Role                                                                                                            |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Deposit Address**                                   | Receives funds from other blockchains                                                                           |
| **Bridge Address** *(Internal — not visible to user)* | Polymarket's internal address that automatically converts USDC → USDC.e. You never interact with this directly. |
| **Trading Address**                                   | Used for gasless trade execution on Polymarket                                                                  |

**Which one should I use for what?**

| Scenario                                                          | Use This                                |
| ----------------------------------------------------------------- | --------------------------------------- |
| Sending funds in from an exchange or external wallet              | Deposit Address                         |
| Sending USDC / USDC.E / USDT directly on Polygon (zero fee)       | Trading Address                         |
| Logging into [Polymarket.com](http://polymarket.com) via MetaMask | Export private key → import to MetaMask |

They look different, but they all belong to you.<br>

For a full explanation and step-by-step guide, see the [**Wallet**](https://site.monica.cool/wallet) page.

</details>

<details>

<summary><strong>What is the minimum amount I need to deposit?</strong></summary>

* Min **deposit requirement** for the **PolyMarket's cross-chain bridge** is **$10**.
* However, **for Create copy trading, a min of $50 is required**. This is because if your capital is too low, the trades cannot be copy proportionally, which results in very poor performance.
* After testing is complete, try to use more funds to ensure you can copy the target address’s trades proportionally. Only then can you truly match the target address’s returns.

</details>

<details>

<summary><strong>Why hasn't my deposit arrived?</strong></summary>

{% hint style="info" %}
**The most common reason: you selected the wrong blockchain network.**
{% endhint %}

Before sending, always double-check:

1. **Are you sending to the correct address type?**
   1. Multi-chain deposits → use your **Deposit Address**
   2. Polygon-only → use your **Trading Address**
2. **Are you on the correct network?**

| Destination Address | Supported Networks                         |
| ------------------- | ------------------------------------------ |
| Deposit Address     | Polygon, Ethereum, Arbitrum, OP, Base, BSC |
| Trading Address     | Polygon only                               |

{% hint style="warning" %}
❌ Sending from BSC to your Trading Address will **not** arrive — the Trading Address only accepts Polygon transactions.
{% endhint %}

3. **Did you send a supported token?** Only **USDC** and **USDT** are supported. Sending other tokens (e.g., POL, BNB) will not credit your balance.
4. **Has enough time passed?** Cross-chain bridge transactions can take a few minutes. Wait at least 5–10 minutes before troubleshooting.

**Still not arrived?**

* 📖 Check the official guide: [Polymarket Transfer Guide & FAQs](https://intercom.help/funxyz/en/articles/10003876-transfer-crypto-guide-faqs#h_2834613ca7)
* 💬 Contact Polymarket support via the "Let's Talk" button at [fun.xyz](https://fun.xyz/)
* 🔧 Sent POL tokens or used the wrong network to the Trading Address? Recover here: [recovery.polymarket.com](https://recovery.polymarket.com/) *(select the correct blockchain network before connecting)*

</details>


---



<!-- PAGE: getting-started_wallet-setup.md -->
# Wallet Setup

## Understand Your Wallet Addresses

Polymarket's system generates **three distinct addresses** for you. This is a common source of confusion — here's what each one does:

<table data-header-hidden><thead><tr><th></th><th width="374"></th><th></th></tr></thead><tbody><tr><td><strong>Address Type</strong></td><td><strong>What It's For</strong></td><td><strong>Where To Find</strong></td></tr><tr><td><strong>Deposit Address</strong></td><td>Used to receive funds from other blockchains via cross-chain bridge.</td><td><img src="/files/CEwN2EadFoPUxhmHYOWQ" alt="" data-size="original"></td></tr><tr><td><strong>Trading Address</strong> <em>(Polymarket Profile Address)</em></td><td>Used for gasless trade execution on Polymarket.</td><td><img src="/files/5AVkgomjxK3OibHrjFbW" alt="" data-size="original"></td></tr><tr><td><strong>Bridge Address</strong> <em>(Internal — not visible to user)</em></td><td>Polymarket's internal address that automatically converts USDC → pUSD (Polymarket USD). You never interact with this directly.</td><td>Not visible</td></tr></tbody></table>

{% hint style="danger" %}
This is why the wallet addresses may look different — they they each serve a different role within the Polymarket system.
{% endhint %}

## Which Address Should I Use? (Quick Reference)

| **Scenario**                                                | **Use This Address**                                   |
| ----------------------------------------------------------- | ------------------------------------------------------ |
| Transferring funds in from an exchange or external wallet   | ✅ **Deposit Address**                                  |
| Sending USDC / USDC.E / USDT directly on Polygon (zero fee) | ✅ **Trading Address** (Polygon only, stablecoins only) |

{% hint style="info" %}
If you mistakenly sent **POL tokens** to this address, or sent funds via the wrong network, you can recover them here: <https://recovery.polymarket.com/> *(Make sure to select the correct blockchain network before connecting your wallet.)*
{% endhint %}

## Create or Import a Wallet

Go to **Wallet** from the main menu or type `/wallet`

* **Create Wallet** — PolyCop will automatically generate a new wallet for you.
* **Import Wallet** — If you already have a wallet, you can import it using a private key.

<div align="center"><figure><img src="/files/298wdqIS4vFdU1P31beq" alt="" width="563"><figcaption></figcaption></figure></div>

<figure><img src="https://ecnasykcedui.feishu.cn/space/api/box/stream/download/asynccode/?code=MGE2MTc3NGM2NGU4YjY3YWRlZWRjMGViYWM0ZWFkMDBfZjg4Y2tSMElEYUtRYkNxNExOS2E1b2hkUUREVlZDSVRfVG9rZW46QkpiQ2JQTHhTb21Bc1Z4Y2sxd2NHZlRPbkZQXzE3NzUwNDEwMzI6MTc3NTA0NDYzMl9WNA" alt=""><figcaption></figcaption></figure>

## Export Your Private Key

You can export your private key at any time from the **Wallet** page by clicking **Export Keys**.

{% hint style="danger" %}
**Keep your private key safe.** Anyone with your private key has full control of your wallet.

Never share your private key with anyone — not even customer support, developers, or trusted friends. No legitimate service will ever ask for it.

Write it down and store it securely offline. Your private key = your funds. Lose it, and everything is gone forever.
{% endhint %}

## Login to Polymarket with Your PolyCop Wallet

You can fully view and use your PolyCop wallet on the official Polymarket website. This lets you see your copy trading positions, trade history, and manage funds directly.

{% stepper %}
{% step %}

#### **Step 1: Import Wallet to MetaMask**

*Use this method if you have your Private Key generated by PolyCop*

1. Open **MetaMask** and click the **Circle Icon** (Account) at the top-right.
2. Select **"Add account or hardware wallet"** -> **"Import Account"**.
3. Paste the **Private Key** provided by PolyCop and click **Import**.

<figure><img src="/files/W1aShm835qVmYaZEH63E" alt="" width="563"><figcaption></figcaption></figure>

{% hint style="info" %}
*Do not confuse this with your Seed Phrase. Select "Private Key" as the type.*
{% endhint %}
{% endstep %}

{% step %}

#### **Step 2: Connect to Polymarket**

Now that your wallet is in MetaMask, you can use it to access Polymarket directly:

1. Go to [Polymarket.com](https://polymarket.com/).
2. Click **Log In / Sign Up**.
3. Select **MetaMask** and choose the account you just imported (e.g., "Account 2").
4. **Done!** You can now see your copy trading positions, trade history, and deposit/withdraw funds directly on the official site.

<figure><img src="/files/DOCgWyn0MXcGGp0xH4jr" alt="" width="563"><figcaption></figcaption></figure>
{% endstep %}
{% endstepper %}

<figure><img src="https://ecnasykcedui.feishu.cn/space/api/box/stream/download/asynccode/?code=NTRhZmM1ODk3NjhkZTYwNDM0MzE2NGI2MGMyYTBjYjNfQUhiaDRhbWdGcXZnaVI0Uk9pTGs2V2RYZEozaDR3VFpfVG9rZW46RFkwU2I4S084b0Y3N1d4cWhFWWN1R2xpblJmXzE3NzUwNDEwNTc6MTc3NTA0NDY1N19WNA" alt=""><figcaption></figcaption></figure>

## **Wallet Password Protection**

An optional security feature for your wallet. Enable it if you want extra protection for sensitive actions.

**Setup:** Go to `/wallet` and tap the **Wallet Password Protection** button at the bottom to set your unique password. Up to 12 characters, letters and numbers only.

**Action-Locked:** Once enabled, this password is required for all sensitive actions, including withdrawing funds and exporting private keys.

{% hint style="warning" %}
Once set, make sure you remember your password. There is no recovery option if it is lost. Store it safely — and never share it with anyone, especially anyone who DMs you first claiming to be a PolyCop admin→ it's a scam.
{% endhint %}

## **Security Reminder** - Read This

> Telegram's open nature makes it easy for anyone to create fake bots, buy ads, or impersonate existing services — no verification required. Telegram also displays third-party ads in our bots without our approval — we have no control over what appears there.

Your security is PolyCop's top priority. Please take a moment to read this to keep your assets safe.

### **Dos and Don'ts**

❌ **DO NOT click the ad at the top of our bot**. These are third-party scam ads placed via Telegram's ad network, not from us. There is **NO "premium version", "V2", or separate upgrade bot**. Anyone asking you to export your key into another bot is a scammer.

❌ **DO NOT search "PolyCop" in Telegram's search bar**. Fake copycat bots are showing up in search results. You could be handing your funds to a scammer.

❌ **DO NOT** **click links, scan QR codes, or "login" / "verify"** through any message you receive.

🚨 **PolyCop Admin will NEVER DM you first** **or ask for your key**. Scammers impersonate our admins to message or even call you directly — especially right after you ask a question in the group. Their usernames may look almost identical to real admins. If someone DMs you first claiming to be PolyCop → it's a scam. Block them immediately.

✅ <mark style="background-color:$primary;">**PIN the official bot to the top of your chat list**</mark> (Long-press on mobile or right-click on desktop). Always access PolyCop directly from your pinned chats or our official link below. Nothing else.

<figure><img src="/files/v6Yv9io5lT3f8la3JvoR" alt="" width="375"><figcaption></figcaption></figure>

### Official Links

✅ **Our ONLY Official Bots, pick yours and PIN it:**

* New York: <https://t.me/PolyCop_BOT>
* Paris: <https://t.me/PolyCop_Paris_bot>
* Tokyo: <https://t.me/PolyCop_Tokyo_bot>
* California: <https://t.me/PolyCop_California_bot>
* London: <https://t.me/PolyCop_London_bot>

Your choice of bot location affects the perceived response speed (latency) when interacting with the bot — not the actual trade execution speed. **All bots share the same backend and have identical internal processing speeds.**

Choosing a bot **closer to your physical location** can improve responsiveness for actions like viewing `/positions`, but it has no impact on how quickly trades are sent to the market.

✅ **Our officail links:**

* **Website:** [polycop.ai](https://polycop.ai)
* **Analytics:** [polycop.fun](https://polycop.fun)

### Extra Protection

* **Wallet Password Protection**\
  Go to `/wallet` → tap **Wallet Password Protection** → set a unique password (up to 12 characters, letters and numbers only). Once enabled, this password is required for withdrawing funds and exporting private keys.

{% hint style="warning" %}
Once set, make sure you remember your password. There is no recovery option if it is lost. Store it safely — and never share it with anyone, especially anyone who DMs you first claiming to be a PolyCop admin → it's a scam.
{% endhint %}

* **Block Unwanted Calls & DMs**

> Scammers now create usernames almost identical to our admins and **call you directly**. A live phone call catches you off guard — you don't have time to think, verify, or realize it's a scam. That's exactly what they're counting on.

To prevent scammers from contacting you:

1. **For Calls:** Telegram → **Settings** → **Privacy and Security** → **Calls** → Set **Who can call me** → **My Contacts**
2. **For DMs:** Telegram → **Settings** → **Privacy and Security** → **Messages** → Set **Who can message me** → **My Contacts**

Now only people saved in your contacts can Call or DM you first.

🛡️ Stay vigilant and trade safely.&#x20;

## Multiple Main Wallets

PolyCop now supports multiple main wallets. You can create new wallets or switch between existing ones at any time — all from `/wallet`.

#### Create a New Wallet

Tap **Create New Wallet** in `/wallet` to generate a brand new wallet address. Your existing wallet stays intact — you're simply switching your active wallet to the new one.

#### Switch Between Wallets

All wallets you've ever created or imported are saved. Switch between them freely at any time. Your currently active wallet is marked with ✅.

> ⚠️ Always check the wallet label when viewing positions or balance — make sure you're on the right wallet.

#### What Carries Over When You Switch

All copy trading tasks, AFK strategies, and sub-wallet tasks are fully inherited by your new active wallet — everything carries over seamlessly.

Sub-Wallet Funds: Any **Add Funds** or **Withdraw** actions for sub-wallets always interact with your **currently active main wallet**. Make sure you're on the right wallet before moving funds.


---



<!-- PAGE: getting-started_withdraw.md -->
# Withdraw

## How to Withdraw (Step-by-Step)

1. Open the PolyCop bot and tap **Wallet** from the main menu.
2. Select **Withdraw USDC**, **Withdraw USDC.e**, **Withdraw USDT** or **Withdraw pUSD** depending on which token you want to withdraw.
3. Enter your personal **Polygon** wallet address and the amount you wish to transfer out.
4. Confirm the transaction.

{% hint style="info" %}
Withdrawals use Polymarket's official system — **no gas fees required**. You do not need to hold POL.
{% endhint %}

## Supported Withdrawal Tokens

| **Token** | **Network** |
| --------- | ----------- |
| USDC      | Polygon     |
| USDC.e    | Polygon     |
| USDT      | Polygon     |
| pUSD      | Polygon     |

## Withdraw to Polymarket Directly

If you prefer to manage withdrawals directly on the Polymarket website, you can import your PolyCop wallet into MetaMask and connect it to Polymarket:

1. In the bot, go to **Wallet** → tap **Export Keys** to get your private key.
2. Import the private key into **MetaMask**
3. Go to [Polymarket.com](https://polymarket.com/), log in with MetaMask using the imported account.
4. Use Polymarket's native interface to withdraw or manage your funds.

<figure><img src="/files/b9FhtZ4RZjmtKcv43wCS" alt="" width="563"><figcaption></figcaption></figure>

{% hint style="info" %}
See the [Wallet](/getting-started/wallet-setup.md#login-to-polymarket-with-your-polycop-wallet) page for detailed step-by-step instructions on importing to MetaMask and connecting to Polymarket.
{% endhint %}


---



<!-- PAGE: manual-trading.md -->
# MANUAL TRADING

- [Start Manual Trading](https://docs.polycop.ai/manual-trading/how-to-start-manual-trading.md)
- [Place a Manual Trade](https://docs.polycop.ai/manual-trading/how-to-manual-trading.md)


---



<!-- PAGE: manual-trading_how-to-manual-trading.md -->
# Place a Manual Trade

Once you've entered a market, the bot displays the **Market Dashboard**:

{% columns %}
{% column %}

* **Market Name** — the question being predicted
* **Prices** — current Yes and No prices
* **Stats** — 24h volume and liquidity
* **Order Book** — live bid and ask levels
* **Trading Panel** — action buttons below
  {% endcolumn %}

{% column %}

<figure><img src="/files/ybMjKEP7eXvcUomAi5t4" alt=""><figcaption></figcaption></figure>
{% endcolumn %}
{% endcolumns %}

{% hint style="info" %}
For some markets, tap **More** to see additional related outcomes. For example, in a sports match you may find options beyond just the winner — such as spreads, totals, both team tp score and more.
{% endhint %}

### **Step 1** — **Select Outcome**

Tap the outcome you want to buy. Depending on the market type, this may appear as **Yes / No**, **UP / DOWN**, or a **specific team or candidate**.

### Step 2 — Buy

{% columns %}
{% column %}
**Market Order (Buy)**&#x20;

* Executes immediately at the current best available price. Best for speed and ensuring you don't miss the trade.
* Default quick-buy buttons are available at **$50**, **$100**, and **$200**, or tap to enter a **custom** amount.&#x20;

**Limit Order (Buy)**&#x20;

* Set a specific price you're willing to pay. Best for controlling your entry price and avoiding slippage.
* Input:
* Tap **Bid 1 Buy** to place a limit order at the current best bid price from the order book,&#x20;
* Or tap **Limit Buy** to manually enter your desired price and amount.&#x20;
  {% endcolumn %}

{% column %}

<figure><img src="/files/0silwohzZRjQYhBsg8YG" alt=""><figcaption><p>Manual Trading Panel — Spurs vs Thunder</p></figcaption></figure>
{% endcolumn %}
{% endcolumns %}

{% hint style="info" icon="lightbulb-on" %}
Pro tips: Specifically for sports markets, outstanding limit orders are **automatically cancelled** once the game begins, clearing the order book at the official start time. Always monitor your orders closely around game start times.
{% endhint %}

### Step 3 — Sell

{% columns %}
{% column %}
**Market Sell**

* Sells at the current best available price.
* Default sell amount is **50%** of your position, or enter a **custom percentage** manually.

**Limit Sell**

* Follow the prompts to enter your desired **price and sell percentage** to place a limit sell order.
  {% endcolumn %}

{% column %}

<figure><img src="/files/tzEpw4jyylSikwmvlrkm" alt=""><figcaption><p>Manual Trading Panel — Spurs vs Thunder</p></figcaption></figure>
{% endcolumn %}
{% endcolumns %}

####

### Step 3 — The Opposite Side Panel

Below the main trading panel, you'll see a trading panel for the opposite outcome. To bet on the other side, simply place your order here — the same rules apply.

Note that **Bid 1 Buy** becomes **Ask 1 Buy** here, because the order book prices for each side are mirrored. For example, in a Spurs vs Thunder market, buying Thunder at Bid 1 (43¢) corresponds to the Spurs' Ask 1 price (43¢) on the opposite panel.

### Additional Settings

* **Default Manual Trade Template** — Adjust your default buy amount and sell percentage under Buy / Sell Setting. See [Settings → Buy / Sell Setting](https://docs.polycop.ai/other-commands/settings#buy-sell-setting) for details.
* **Manage Limit Orders** — Tap `/limit` in the bottom-left menu to view and manage all active limit orders across Copy Trading, Manual, and AFK.


---



<!-- PAGE: manual-trading_how-to-start-manual-trading.md -->
# Start Manual Trading

**You can find a market in three ways:**

{% stepper %}
{% step %}

#### Paste a Market Link

Simply paste a Polymarket market link directly into the chat.
{% endstep %}

{% step %}

#### Search by Text

* Type keywords into the bot to search for a market (e.g., "Bitcoin", "Trump", "NBA").&#x20;
* The bot will return a list of matching markets for you to choose from.
  {% endstep %}

{% step %}

#### Browse via /market

* Tap `/market` in the bottom-left menu, or use the **Market** button on the `/start` page.
* Browse trending markets across all categories, synced with official Polymarket categories for fast and familiar navigation.
  {% endstep %}
  {% endstepper %}

Then tap **Trade** on any market to enter the manual trading page for that market.


---



<!-- PAGE: other-commands.md -->
# OTHER COMMANDS

Tap the menu icon at the bottom left of the bot to view all available commands starting with /xxx. This section covers some key commands and what they do.

{% content-ref url="/pages/3t4smWPIKxgDRbLuG8xK" %}
[/settings](/other-commands/settings.md)
{% endcontent-ref %}

{% content-ref url="/pages/2bUR51VlhMhEeA9UHJox" %}
[/convert](/other-commands/convert.md)
{% endcontent-ref %}

{% content-ref url="/pages/ss2kZHDAeEdxKJOMAA5o" %}
[/limit](/other-commands/limit.md)
{% endcontent-ref %}

{% content-ref url="/pages/dEZvxpslb1bI386Ac3u4" %}
[/topuser](/other-commands/topuser.md)
{% endcontent-ref %}


---



<!-- PAGE: other-commands_convert.md -->
# /convert

## What is WCOL?

Polymarket does not use USDC as the underlying collateral for all markets. Some older markets internally used **WCOL (Wrapped Collateral)** — a Polymarket-defined internal settlement token that needs to be unwrapped before it can be converted back to USDC.

If you have WCOL sitting in your account, your visible balance may be lower than expected. Converting it back to USDC will restore your full available funds.

## How to Convert

👉 Tap the **menu icon** at the bottom left of the bot to view all available commands, then tap **`/convert`** to unwrap your WCOL back to USDC.

## Is This Still Relevant?

This is a legacy issue. After Polymarket's **CLOB V2 upgrade**, all trading now uses **pUSD** as the standard collateral token — a standard ERC-20 token on Polygon, strictly backed 1:1 by USDC on-chain.

If you've only traded on Polymarket after the CLOB V2 update, you are unlikely to have any WCOL in your account. However, if you've been using Polymarket for a while, it's worth running `/convert` to check and clear any remaining WCOL balance.


---



<!-- PAGE: other-commands_limit.md -->
# /limit

View and manage your active limit orders across all trading modes — Copy Trading, Manual, and AFK.

**What you can do here:**

* View all **currently open limit orders**
* Cancel any existing limit order

{% hint style="info" %}
Pro tips:&#x20;

* Only active (unfilled) limit orders appear here. For orders that have already been executed, go to `/positions`.
* Specifically for sports markets, outstanding limit orders are **automatically cancelled** once the game begins, clearing the order book at the official start time. However, game start times can shift — if a game starts earlier than scheduled, orders may not be cleared in time. Always monitor your orders closely around game start times.
  {% endhint %}


---



<!-- PAGE: other-commands_settings.md -->
# /settings

## Global Settings

Access your global settings via `/settings` in the bot, or tap the menu icon at the bottom left and select **settings**.

### Auto Redeem

**Default: ON** ✅— It is not recommended to turn this off.

After a market resolves, Auto Redeem automatically exchanges your winning tokens back to USDC. Keeping this enabled ensures your funds are returned to your account without any manual action after each market settles.

### Copy Mode

Switch between two copy trading execution modes depending on your priority — speed or safety.

* **Mempool (Fast)**: Executes your copy trade the moment the target broadcasts a transaction. Note: if the target's transaction ultimately fails on-chain, your copy trade will still execute.
* **Wait Confirmed Tx (Safe)**: Waits for block confirmation before copying. Slightly slower, but guarantees you will never copy failed or reverted transactions.

👉 Tap **Copy Mode** in settings to toggle between the two modes.

### Manual Trade Confirm

Tap to toggle between enabled ✅ and disabled ❌.

When enabled, a confirmation prompt will appear before any manual trade is placed, giving you a chance to review before execution.

### Buy / Sell Setting

Set your **default parameters for manual trading**, including buy/sell amount, percentage, order book price selection for limit orders, etc. The values configured here will be used as the **default template** every time you place a manual trade.

👉 Tap any parameter to modify. Enter a number to update the default value.


---



<!-- PAGE: other-commands_topuser.md -->
# /topuser

### Profit Leaderboard

Access the Profit Leaderboard via `/topuser`  in your bot, or tap the menu icon at the bottom left and select `topuser`.

The leaderboard displays the top-performing **real PolyCop users**, ranked by PnL over your selected time period.

Time periods:

* **1D** — last 24 hours
* **7D** — last 7 days (default)
* **30D** — last 30 days

### Trading Competition

You can also find Trading Competition info here. We run competitions from time to time with generous rewards.

🏆 <mark style="background-color:$primary;">**Upcoming: World Cup Celebration Trading Competition**</mark> <mark style="background-color:$primary;">**June 11 — July 19**</mark>

📢 Stay tuned for more details!&#x20;

### Hide My Address&#x20;

Tap **Hide My Address** to make your wallet address non-clickable on the leaderboard — others can see a truncated version but cannot trace it back to your Polymarket profile. When enabled, you'll see ✅ next to the button.


---



<!-- PAGE: performance-and-reports.md -->
# PERFORMANCE & REPORTS

## Copy Trade History

Track the performance of each individual copy task directly from your `/copytrade` page.

👉 Go to `/copytrade` → tap into any copy task → tap **Copy History in web 🔗** below the details panel.

This opens a web-based history page showing a full breakdown of every trade copied from that target address:

| Column           | Details                             |
| ---------------- | ----------------------------------- |
| **Market**       | The market traded                   |
| **Target Trade** | Entry price / Shares / Total amount |
| **Your Copy**    | Entry price / Shares / Total amount |
| **Status**       | Whether the copy was successful     |

You can also **export the full history as an Excel file** for deeper analysis.

## P\&L Reports

Track your full P\&L across all trading strategies.

* **Overall P\&L Report**

`/positions` → tap **"PNL Report"** → view Copy, AFK & Manual P\&L

* **Copy Trade Report**

&#x20;`/copytrade` → select a copy task in your main wallet → view Copy Trade Report

* **AFK Trade Report**

`/afk` → select a strategy → view AFK Trade Report<br>

**Pending Markets** in the reports refers to markets that have not yet been settled — the event has occurred or is ongoing, but the final result has not yet been officially confirmed and resolved.


---



<!-- PAGE: q-and-a.md -->
# Q\&A

- [Q\&A](https://docs.polycop.ai/q-and-a/q-and-a.md)
- [Troubleshooting & Errors](https://docs.polycop.ai/q-and-a/troubleshooting-and-errors.md)


---



<!-- PAGE: q-and-a_q-and-a.md -->
# Q\&A

<details>

<summary>1. What is the min amount of funds I need to deposit?</summary>

* Min **deposit requirement** for the **PolyMarket's cross-chain bridge** is **$10**.
* However, **for Create copy trading, a min of $50 is required**. This is because if your capital is too low, the trades cannot be copy proportionally, which results in very poor performance.
* After testing is complete, try to use more funds to ensure you can copy the target address’s trades proportionally. Only then can you truly match the target address’s returns.

</details>

<details>

<summary>2. How to set up copy trading?</summary>

Two principles for **setting copy trading** parameters:

1. **Match the position ratio of the target address**.
2. Don’t spend all your funds too quickly, to avoid small fluctuations wiping out your principal.

With small capital, results rely more on luck. Having **sufficient capital** and following these principles leads to more reasonable and stable settings.

You can set up copy trading by following the steps below. If you stick to these, you’ll generally avoid problems:

Choose the target addressFirst, confirm which address you want to copy. Try to choose addresses that are not high frequency arbitrage and have a stable trading logic.Choose the copy modeThere are two common options:Fixed amount mode: copy each trade with a fixed amount, suitable for testing.Percentage mode: copy based on the target address’s position ratio, which is better for matching long term returns.Set the copy ratio or amountIn percentage mode, make sure your capital is sufficient. Otherwise, the calculated amount may fall below the minimum order requirement.Control how fast your funds are usedDo not spend all your funds too quickly. Leave room for follow up buys and market fluctuations to avoid small movements wiping out your principal.Check minimum order requirementsBoth market orders and limit orders have minimum requirements. Orders below the minimum will fail to copy.Confirm sell rulesCheck whether Sell uses a market order or a limit order.Note that TP and SL only work when Sell uses a market order.Check switch statusMake sure copy trading is enabled and not restricted by conditions such as max price or max spend.

In short:

Test first, then add more funds. Copy by ratio and always leave enough buffer.

</details>

<details>

<summary>3. How to Find <strong>smart money wallets</strong>?</summary>

You can find **smart money wallets** through the following methods:

1. **Recommendations on X (Twitter)**.
2. **Top Holders list** under each market on the **official Polymarket website**.
3. The following third-party sites:
   * <https://polymarket.com/leaderboard>
   * <https://predicting.top/>
   * <https://polymarketanalytics.com/traders>
   * <https://app.future.fun/scouter>

To learn more, please check " [Discover Wallets](/discover-wallets.md)"

</details>

<details>

<summary>4. What kind of smart money is worth copying?</summary>

1. **Consistently profitable over time.**
2. **Has a large gap between profit and loss,** the total profit amount should be significantly higher than the total loss amount.
3. **Operates in markets with sufficient liquidity**, so when you copy their trades, you can enter at similar prices and with comparable position sizes.

</details>

<details>

<summary>5. Why is the wallet address I exported different from the deposit address / Trade address?</summary>

We use Polymarket's official Wallet system for **gas-free** trading:

* In Polymarket, when you connect your wallet, Polymarket will, based on your wallet, generate a trading sub-address and a deposit sub-address. You will have a total of three different types of addresses.

1. Trading Address

   This address is generated specifically for gasless trading. You do not need to pay gas fees when placing trades.
2. Deposit Address

   This address is used for cross-chain deposits. You can transfer funds to it from different blockchains.
3. Your Wallet

   This is the original wallet address you use to log in.

* You can fully view and use the wallet address generated for you by PolyCop on the Polymarket website by following these steps:

1. On the PolyCop “wallet” page, click “Export Private Key”
2. Import the private key into MetaMask, then open the Polymarket website and connect this wallet
3. Go to your Polymarket personal profile page and click Copy Address to view your trading address
4. Click the Deposit button to view your deposit address.

You can send USDC.E (Only USDC.E, Only Polygon Network) to the trading address on Polygon Network (No fee) , and send USDC or USDT to the deposit address(Low Cross-chain bridge fee / Very Low Swap fee).

</details>

<details>

<summary>6. What are min trading limits on Polymarket?</summary>

For market orders, the minimum limit is $1. For limit orders, the minimum requirement is 5 shares.

> Note: You may notice transactions smaller than $1 at certain addresses. This occurs when a limit order is partially filled, resulting in a trade execution below the initial minimum threshold.

</details>

<details>

<summary>7. Which bot is faster: Tokyo, California, or others?</summary>

All our bots are powered by the same high-performance engine, meaning their internal processing copy speeds are identical.

However, the perceived response speed (latency) depends on your physical location relative to Telegram's data centers. To get the best experience:

* Pick the most responsive one: Start by testing any bot; the one that replies to you instantly is the best match for your current network.
* Switch if it feels laggy: If you experience delays in button interaction (usually due to Telegram's regional network congestion), simply switch to a different bot. All bots share the same backend data and functionality.

</details>

<details>

<summary>8. Airdrop Eligibility: Am I eligible for the Polymarket $POLY airdrop?</summary>

Yes, your trading activity on PolyCop counts toward eligibility.

Since you are using the dedicated wallet address generated by Polymarket within the PolyCop platform, your on-chain interactions are fully integrated with Polymarket's ecosystem.

**Key Points on Eligibility:**

* On-chain Recording: As long as your trading activity meets Polymarket’s official airdrop criteria (such as volume, consistency, or market participation), all related data will be properly recorded and counted toward your eligibility.
* Official Builder Advantage: PolyCop is an officially recognized Polymarket Builder. This status ensures that trades routed through our platform are correctly attributed. Additionally, using a recognized Builder platform may potentially provide extra advantages or specific rewards within the ecosystem.

{% hint style="warning" %}
Disclaimer: Airdrop eligibility, rules, and distribution are entirely determined by the Polymarket team. PolyCop does not control the snapshot timing or the final allocation criteria. Please follow official Polymarket channels for the most accurate and up-to-date information regarding the $POLY token launch.
{% endhint %}

</details>

<details>

<summary>9. Security Alert: Will an admin ever DM me first?</summary>

**Admins will never message you first**

Scammers will impersonate admins by copying admin name and avatar.

Never give them your private key or verification codes. They might also give you a fake bot. The only real bot is **@PolyCop\_BOT** (they may try to replace the lowercase “l” with a capital “I” or something similar)

**Block and report them immediately**

</details>

<details>

<summary>10. Why does my total balance change abnormally whenever I buy or sell?</summary>

Polymarket’s billing calculation can be delayed. When you sell, it records both the value of the position you closed and the amount you received after selling. The position value aggregation can also be delayed. That’s why your balance may sometimes appear inaccurate.

However, in PolyCop, the price and value of each token shown in your positions are calculated independently using real time data. The total balance, on the other hand, relies on Polymarket’s data, so it may experience delays

</details>

<details>

<summary>11. Why does it fail when I click Redeem or Auto Redeem?</summary>

because there are too many users and too many requests, Polymarket has limits on Redeem feature. You need to try again later

or check whether the market for your current token is in a dispute resolution period. Trading are not permitted while a market is in the dispute resolution phase.

</details>

<details>

<summary>12. Why did the transaction result in an FAK error?</summary>

There are two main reasons for this:

1. Your slippage tolerance is set too low while market prices are changing too rapidly.
2. The market is nearing its close, and there are currently no limit orders available for sale.

</details>

<details>

<summary>13. Why hasn't my deposit arrived?</summary>

{% hint style="info" %}
**The most common reason: you selected the wrong blockchain network.**
{% endhint %}

Before sending, always double-check:

1. **Are you sending to the correct address type?**
   1. Multi-chain deposits → use your **Deposit Address**
   2. Polygon-only → use your **Trading Address**
2. **Are you on the correct network?**

| Destination Address | Supported Networks                         |
| ------------------- | ------------------------------------------ |
| Deposit Address     | Polygon, Ethereum, Arbitrum, OP, Base, BSC |
| Trading Address     | Polygon only                               |

{% hint style="danger" %}
Sending from BSC to your Trading Address will **not** arrive — the Trading Address only accepts Polygon transactions.
{% endhint %}

3. **Did you send a supported token?** Only **USDC** and **USDT** are supported. Sending other tokens (e.g., POL, BNB) will not credit your balance.
4. **Has enough time passed?** Cross-chain bridge transactions can take a few minutes. Wait at least 5–10 minutes before troubleshooting.

**Still not arrived?**

* 📖 Check the official guide: [Polymarket Transfer Guide & FAQs](https://intercom.help/funxyz/en/articles/10003876-transfer-crypto-guide-faqs#h_2834613ca7)
* 💬 Contact Polymarket support via the "Let's Talk" button at [fun.xyz](https://fun.xyz/)
* 🔧 Sent POL tokens or used the wrong network to the Trading Address? Recover here: [recovery.polymarket.com](https://recovery.polymarket.com/) *(select the correct blockchain network before connecting*

</details>

<details>

<summary>14. Why didn't my copy trade buy / sell?</summary>

There are several reasons a trade might get skipped. Work through the checklist below.

**🔴 Didn't Buy — Common Causes**

1\. Your copy amount is below the platform minimum

> Polymarket has a minimum order size: **$1 for market orders** and **5 shares for limit orders**. If your copy ratio is small (e.g. 1%), a target trade of $20 only generates a $0.20 order — which gets rejected automatically.

**Fix:** Enable **"Below Min Limit, Buy at Min ✅"** so the bot rounds up to the minimum instead of skipping. Pair this with **"Ignore Target Trades Under $10–$50"** to make sure you only round up on meaningful trades, not dust.

\
2\. Slippage is too tight — the order was killed (FAK error)

> Polymarket uses **Fill-and-Kill (FAK)** logic on market orders. If the market doesn't have enough liquidity within your slippage range, the order is partially filled or cancelled entirely.

**Fix:** Increase your market order slippage tolerance. Alternatively, switch to a **limit order** and set a **Limit Price Offset of `+0.02`** — this bids slightly above the target's price, improving your fill rate.

\
3\. A spend limit has been hit

> If any of the following limits are maxed out, the bot will skip new buys silently:
>
> * Max Spend Per Yes/No
> * Max Spend Per Market
> * Total Spend Limit
> * Available USDC

**Fix:** Review each limit in your task settings. Sell or close existing positions to free up room — the bot will automatically resume once exposure drops below the limit.

\
**🔴 Didn't Sell — Common Causes**

**1. Sell mode is set to Limit Order, but no one is taking the other side**

> Limit sell orders wait for a counterparty. In low-liquidity markets, your order may sit unfilled indefinitely.

**Fix:** Switch to **Market Order** for selling if you need faster execution. Or check whether your limit order has already expired.

</details>

<details>

<summary>15. I set a 20% stop loss — why did I lose more than 20%?</summary>

There are two common reasons for this：

**Reason 1: Stop loss uses a market order, which has slippage**

All Stop Loss orders execute as **market orders**. When the price hits your stop level, the bot sends an immediate sell at whatever price the market will take.

> In a fast-moving or illiquid market, the actual fill price can be significantly worse than your trigger price — so a 20% stop loss might result in a 25–30% loss by the time the order fills.

**Fix:** This is a fundamental characteristic of market-order stop losses. To account for it, set your stop loss a few percentage points tighter than your actual maximum tolerance. For example, if you can accept 20% loss, set the stop at 15–17%.

**Reason 2: Stop loss silently stopped working after you switched Sell mode**

This is the most commonly missed issue.

> **If your Sell mode is set to Limit Order, TP/SL will NOT function.** The stop loss setting is still visible, but it will not trigger.

This happens because Polymarket does not allow two concurrent limit orders on the same position — so the bot cannot place a stop-loss limit order if a sell limit order is already in place.

**Fix:** Go to your task settings and confirm that **Sell is set to Market Order**. TP/SL only works with market order sell mode.

</details>

<details>

<summary>16. I'm getting an error — "Max holder market limit exceeded". What does this mean?</summary>

> How it works: Every time you enter a new market (a new event/question on Polymarket), it counts as +1 toward this limit. Once you hit the cap, the bot will refuse to copy any new markets — even if you have plenty of funds available.
>
> Exampl&#x65;**:** If Max Copy Market Number = 5 and you're already holding positions in 5 different events, the next trade in a new event will be skipped and trigger this error.

**Fix:**

**Option A — Free up market slots:** Close or sell your positions in one or more existing markets. The count will drop, and the bot will automatically resume copying new markets.

**Option B — Raise the limit:** Increase your Max Copy Market Number setting if you're comfortable holding more markets at once. If you don't want this restriction at all, set it to a large number like `999`.<br>

</details>


---



<!-- PAGE: q-and-a_troubleshooting-and-errors.md -->
# Troubleshooting & Errors

#### Error Code Analysis

| Error Code / Message                                         | Reason                                                                                                    | Solution                                                                                                  |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Admin code = 1004** `chain network error`                  | <p><strong>Chain Network Congestion.</strong><br>Usually due to unstable RPC nodes.</p>                   | This is temporary. The Bot will retry automatically. Wait a moment.                                       |
| **fail to place order** `insufficient balance` / `allowance` | <p><strong>Low Balance or Allowance.</strong><br>Not enough USDC to buy, or not enough MATIC for Gas.</p> | <p>1. Check USDC balance.<br>2. Ensure you have small amount of MATIC (POL).<br>3. Deposit and retry.</p> |
| **fail to sell position** `reason: no match`                 | <p><strong>Low Liquidity.</strong><br>Polymarket order book is thin; no buyers at your price.</p>         | Not a Bot error. It's a market issue. Retry later or adjust your sell price.                              |
| <p><strong>contract call failed</strong><br>(Withdrawal)</p> | **Network Fluctuation or Gas Estimation Error.**                                                          | Try restarting the Bot (`/start`) and withdraw again. If it fails repeatedly, contact support.            |

#### Status Issues

<details>

<summary>Q: Why did copy notifications stop suddenly?</summary>

A: Please check:

1. Did the Bot stop running? (Send `/start` to wake it up).
2. Did you accidentally block the Bot in Telegram settings?
3. Has the target trader actually made any trades recently?

</details>

<details>

<summary>Q: The event ended, why haven't I received my winnings?</summary>

A: This is a **Polymarket Platform** process.

* After market resolution, there is a delay in settlement. Please wait patiently for the platform to distribute funds.

</details>


---



<!-- PAGE: readme.md -->
# Welcome to PolyCop

**PolyCop** is a **Telegram** bot that lets you automatically copy trades from profitable "smart money" wallets on **Polymarket** — the world's largest prediction market.

No manual monitoring. No missed entries. Just set your target wallet, configure your parameters, and let the bot trade for you.

## Why PolyCop?

* **Ultra-fast execution**
  * 30% of copy trades execute in 0 blocks (0 seconds), giving you the same entry price as high-frequency traders.&#x20;
  * The remaining 70% execute in 1 block.
* **Flexible copy settings** — Copy proportionally, set fixed amounts, use limit or market orders, and configure stop-loss / take-profit per trader.
* **Full capital control** — Set max spend per trade, per market, and per Yes/No position. Never over-expose your balance.
* **Sub-wallet isolation** — Assign a dedicated wallet to each copy target for clean, independent fund management.

![](/files/UMyDf5uduB5ANlpZnJzX)

## What You Can Do with PolyCop

* **Copy Trading** — Mirror any wallet with market or limit orders. Fine-tune with price offsets, expiration times, per-market caps, proportional sizing, and minimum-amount handling.
* **AFK Auto Trade** — Automated strategies on BTC, ETH, SOL & XRP short-term markets, with optional MACD / KDJ / ATR filters.
* **Manual Trading** — Trade any market with a live order book, directly in Telegram.
* **AI Wallet Analysis** — Paste any address and get a full copyability report in seconds.
* **Wallet & Position Management** — Multiple main wallets, sub-wallets, private key import/export, and withdrawals.

## How to Start Copy Trading — 3 Steps

1. **Set up your wallet and deposit** → Fund it with USDC/USDT/... (min. $50 to start copy trading)
2. **Find a smart money wallet** → Use the PolyCop Leaderboard, Polymarket Top Holders, or in-bot AI analysis&#x20;
3. **Start copying** → Configure your settings and tap Active ✅

More details: \[[Wallet Setup](https://docs.polycop.ai/getting-started/wallet-setup)] → \[[Discover Wallets](https://docs.polycop.ai/discover-wallets)] → \[[Copy Trade](https://docs.polycop.ai/copy-trading)]

##

## Copy Trading Features

{% hint style="info" %}
PolyCop offers the most advanced copy trading toolkit on Polymarket — and with that comes depth. It might feel overwhelming at first, but every parameter is there for a reason. Take your time to discover the right wallets, fine-tune your settings, and run a backtest before going live. The results are worth the effort.
{% endhint %}

* **Limit Order Copying:**
  1. Supports setting a price offset, copy at a price higher or lower than the trader’s.
  2. Supports setting an expiration time for limit orders.
  3. Supports market order copying.
  4. Allows setting a maximum buy amount per Yes/No.
  5. Allows setting a total position.
  6. Supports copying trades **proportionally to the trader’s position size**.
  7. When your calculated trade amount (based on your copy ratio) is **below the minimum trade limit**, you can choose either to **copy at the minimum amount** or **skip the trade**.
* **Position Management:** View current positions and manually close (sell) them.
* **Wallet Management:** Supports importing/exporting private keys and withdrawals.
* **Copy Backtesting**

<img src="/files/QGGejHBHD8iWQ1g3TLSB" alt="" width="375">

<figure><img src="/files/NwWKJVPYphhtUV61vf4H" alt="" width="375"><figcaption></figcaption></figure>

<p align="center">Copy Backtesting：<a href="https://polycop.fun/copy-backtest">https://polycop.fun/copy-backtest</a></p>

## Find smart money wallets

You can find **smart money wallets** through the following methods:

1. **Recommendations on X (Twitter)**.
2. **Top Holders list** under each market on the **official Polymarket website**.
3. The following third-party sites:
   * <https://polymarket.com/leaderboard>

To learn more, please check "[Discover Wallets](/discover-wallets.md)"

## How to set up copy trading?

<details>

<summary>Two principles for setting copy trading parameters:</summary>

1. **Match the position ratio of the target address**.
2. Don’t spend all your funds too quickly, to avoid small fluctuations wiping out your principal.

With small capital, results rely more on luck. Having **sufficient capital** and following these principles leads to more reasonable and stable settings.

To learn more, please check "[How to Copy](/copy-trading/how-to-copy.md)"

</details>

## What kind of smart money is worth copying?

<details>

<summary>What kind of smart money is worth copying?</summary>

1. **Consistently profitable over time**.
2. **Has a large gap between profit and loss,** the total profit amount should be significantly higher than the total loss amount.
3. **Operates in markets with sufficient liquidity**, so when you copy their trades, you can enter at similar prices and with comparable position sizes.

If you’re not certain but you trust them, test first.

</details>

A **PolyCop user** **turned $305 into $48,786** using copy trading, In just 30 days. 🚀

Click the Use /tradingcompetition command in PolyCop Bot to view the details, and Verify the authenticity on Polymarket and a blockchain explorer.

[PolyCop Bot - New York](https://t.me/PolyCop_BOT?start=contest_back)

<figure><img src="/files/R56E6hHy9Nf5NQXCUJbB" alt=""><figcaption></figcaption></figure>

<p align="center">Polymarket Profile Link: <a href="https://polymarket.com/@ryanbignose#IHaLgz8">https://polymarket.com/@ryanbignose#IHaLgz8</a></p>

Good luck everyone, go explore **copying strategies** and discover more **profitable smart money addresses** on **Polymarket**.

**🔗 Website:** [**polycop.ai**](https://polycop.ai)

**📱 Bot:** [**t.me/PolyCop\_BOT**](https://t.me/PolyCop_BOT)


---
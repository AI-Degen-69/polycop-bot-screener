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

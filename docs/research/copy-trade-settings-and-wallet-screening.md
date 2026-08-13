# Deep Research: Polymarket Copy-Trade Settings & Wallet-Screening Parameters

**Date:** 2026-08-10 · **Depth:** Thorough (14 searches, ~18 sources) · **Tool:** Firecrawl deep research

---

## Executive Summary

Copy trading on Polymarket is not a shortcut to a trader's returns — it copies their **decisions** and charges you three separate taxes on each one: the **price drift** accumulated during your detection lag, the **taker fee** on your entry, and the **worse fills** the master's own order helped create. The arithmetic is brutal and public: near 50¢ entries, a 2¢ drift and the peak crypto taker fee means a master needs roughly **6% ROI per trade just for you to break even** — a 5%-per-trade master, which looks strongly profitable, can still lose you money. The single most important "setting" is therefore not a ratio or a tolerance; it is the **edge-to-cost bar**: *copy only wallets whose per-trade edge exceeds your measured drift plus your fees plus any service split, with headroom.*

On the wallet-selection side, the consensus across sources converges on a specific profile: **long history** (6+ months, hundreds of closed trades — ~1,000 trades to distinguish a 53% win rate from a coin flip at 95% confidence), **mid-50s win rate at near-even entries** (very high win rates usually mean buying expensive favorites with a per-trade edge too thin to survive your drift), **consistent monthly gains** rather than one hot streak, **steady position sizing relative to bankroll**, and **absence of wash-trading and bot signatures**. Only ~12.7% of Polymarket users are profitable and only ~1% of wallets have earned over $1,000, so the pool of genuinely copyable addresses is small — and the platform's own leaderboard is the worst starting point because it is dominated by exactly the bots and wash-trading accounts you cannot beat or should not trust (Columbia research estimates ~25% of historical volume is fake).

---

## Key Findings

1. **Polymarket has no native copy trading.** Everything is third-party: dashboards, Telegram bots, open-source scripts that watch a wallet's public on-chain activity and mirror it from your wallet. Prefer **non-custodial** tools (your key never leaves you). ([TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/))

2. **The copier's equation is `EV = w − p`.** A master's edge per share is win probability minus entry price. You inherit the *decision* but pay `p + δ` (δ = drift during your lag), so you win less than they do and lose more — *"same call, worse price, both ways."* The asymmetry is structural, from the entry price, not from sizing; no allocation scheme removes it. ([TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/))

3. **Detection lag is seconds, not milliseconds, and you only control the tail of it.** A fill prints anonymously on the public websocket within ~1s; the *identity* becomes readable only after on-chain settlement (~2s Polygon blocks) and indexing. Measured Data-API polling lag on 5-minute BTC markets: **~4–5 seconds** (July 2026). Watching settlement logs directly trims some of it; nothing you buy removes the first stages — so tools advertising "sub-second mirroring" are marketing, not physics. ([TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/))

4. **Slippage is an orderbook-depth problem, and Polymarket books are shallow where it matters.** Thin books mean large orders walk the book (MetaMask's slippage explainer applies directly). On Polymarket: **depth concentrates at the top levels** and **decays sharply near resolution** (arXiv stylized facts), and per-window volume in fast markets is small — so "your own mirrored size moves the price again." The rule: **cap copy size by visible book depth at your price limit, not by proportionality to the master.** ([arXiv 2604.24366](https://arxiv.org/html/2604.24366v1), [MetaMask](https://metamask.io/news/what-is-slippage), [TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/))

5. **All Polymarket orders are limit orders.** GTC/GTD, with post-only support; market orders execute at the best available price and you pay the spread; "large orders may move the price." Rate limits matter for bots: Data API `/trades` is 200 req/10s; CLOB ledger 900 req/10s; `/data/orders` and `/data/trades` 500 req/10s. ([Polymarket docs](https://docs.polymarket.com/trading/place-orders), [Prices & Order Books](https://docs.polymarket.com/concepts/prices-orderbook), [Rate Limits](https://docs.polymarket.com/api-reference/rate-limits))

6. **Wallet screening consensus:** ≥50 closed positions minimum, ≥6-month history, **win rate >55% suggests skill** while **>90% is a red flag** (or an expensive-favorites trap), >$100k volume for "real" engagement, consistent monthly gains, and steady bet sizes relative to bankroll. Red flags: profits concentrated in a single market, **high volume with minimal P&L (wash-trading signature)**, and trades clustered suspiciously close to major news. ([QuantVPS](https://www.quantvps.com/blog/polymarket-copy-trading-bot), [Medium — Top Wallets](https://medium.com/@gemQueenx/top-polymarket-wallets-how-to-find-best-traders-for-copy-trading-26704fdfd836))

7. **Sample-size math disqualifies most leaderboard darlings.** Distinguishing a 53% win rate from a coin flip at ~95% confidence takes ~1,000 trades; a 55% claim needs a few hundred. Below those counts the record is noise. Edge must also persist across weeks/volatility regimes, not one hot streak. ([TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/))

8. **High win rate is usually the wrong target.** Very high win rates come from buying expensive favorites — each win earns little and one loss erases many wins — leaving a per-trade edge too thin to survive a copier's drift and fees. Wallets with **mid-50s win rates at near-even (30¢–70¢) entries** carry the fat per-trade edges copy trading needs. ([TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/), [Reddit counter-trading thread](https://www.reddit.com/r/PredictionsMarkets/comments/1te0lnl/i_stopped_copytrading_polymarket_whales_and/))

9. **Wash trading is a first-order hazard for wallet screening.** Columbia research estimates **~25% of Polymarket's historical volume is fake**, peaking at ~60% of weekly trades in Dec 2024, including a coordinated network of 43,000+ wallets doing sub-penny trades with self-counterparty loops; arXiv independently documents a **self-counterparty wash share** as a stylized fact. Wash-trading wallets exist to game incentives/rankings, not to profit — copying one is copying a mirage. ([CoinDesk](https://www.coindesk.com/markets/2025/11/07/polymarket-s-trading-volume-may-be-25-fake-columbia-study-finds), [SSRN 5714122](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5714122), [arXiv 2604.24366](https://arxiv.org/html/2604.24366v1))

10. **A large share of top wallets are bots you cannot out-execute.** Community analysis of the top 20 leaderboard wallets found **14 are bots**, and the top bot P&L is largely speed-based — reacting faster than you can copy, meaning you inherit the tail of their edge at best. The 1.3M-wallet analysis adds the practical filters: *wallets older than 6 months, no bots, recent win rate weighted more heavily* — even the best wallets **drift**, so recency matters. ([Reddit r/AI_Agents](https://www.reddit.com/r/AI_Agents/comments/1v21grs/14_of_the_top_20_polymarket_wallets_are_bots_and/), [Reddit r/passive_income](https://www.reddit.com/r/passive_income/comments/1q0ev57/are_we_all_copy_trading_polymarket_wrong_i/))

11. **Fees compound the drift problem.** The platform charges no trading fees on Polymarket, but takers pay the **taker fee** (gas + protocol fee; "peak crypto taker fee" is significant near 50¢ entries) and your copy tool adds its own fee/split — PolyCop, e.g., charges 0.5%. Tool fees enter the same break-even math as the platform's taker fee. ([TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/), [Medium — Bots](https://medium.com/@gemQueenx/best-polymarket-bots-for-copy-trade-and-sniper-on-web-and-telegram-4992d9f24004))

12. **Fast markets are the hardest place to copy.** 5-minute Bitcoin windows have small per-window volume, so the master's fill visibly moves the price you inherit and your mirrored size moves it again — and your ~4–5s lag is a large fraction of a 5-minute window. Slow political markets have a much lower bar. ([TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/))

---

## Detailed Analysis

### A. The settings that actually matter (and why)

Community guides and bot-architecture write-ups agree on the dials; the differences are in how each dial is set defensibly.

| Setting | Typical range / default | Defensible setting (per sources) |
|---|---|---|
| **Copy ratio** | 0.1×–1.0× of master notional | Start **0.1×–0.3×**; never mirror a whale's *size* into a thin book — cap by **visible depth at your price limit** |
| **Slippage tolerance** | bot-dependent (e.g. 2%–10%) | Tune to your **measured drift + spread**, not an arbitrary %; retry within tolerance a bounded number of times, then log the miss |
| **Max order / allocation ceiling** | per-wallet cap | Hard ceiling as a fraction of **your bankroll**, independent of the master |
| **Price bound per order** | optional | **Always set one** (limit price); "market" orders on Polymarket pay the full spread |
| **Market filters** | — | Price band **30¢–70¢** (near-even entries carry the edges); avoid sub-penny, near-resolution windows (depth decays), and 5-minute windows you cannot reach in time |
| **Detection path** | Data-API polling vs on-chain logs | On-chain/websocket monitoring if your lag budget demands it; measure your own end-to-end lag |
| **Stop-copy rule** | none | Write it down: **win-rate decay detection** + performance review cadence; even the best wallets drift |
| **Fees to budget** | 0–0.5% tool fee + taker fee | Include the tool fee and taker fee in the break-even math *before* wiring a wallet |

*Sources: [Suffescom](https://www.suffescom.com/development/polymarket-copy-trading-bot-development) (ratio 0.1×–1.0×, retry/slippage logic, capital needs), [TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/) (depth-capped sizing, price bounds, stop rules), [Polymarket docs](https://docs.polymarket.com/concepts/prices-orderbook) (market orders pay the spread), [Medium — Bots](https://medium.com/@gemQueenx/best-polymarket-bots-for-copy-trade-and-sniper-on-web-and-telegram-4992d9f24004) (PolyCop 0.5% fee, slippage cons, win-rate decay), [Reddit counter-trading](https://www.reddit.com/r/PredictionsMarkets/comments/1te0lnl/i_stopped_copytrading_polymarket_whales_and/) (30¢–70¢ band).*

**Capital reality check** (Suffescom's worked numbers): copying $50–$500 positions at 0.1× needs roughly **$200–$500** in the trading wallet to clear minimum order thresholds; 1× on a whale placing $1k–$5k positions needs **$5k–$20k**.

### B. The break-even bar, made concrete

The master's per-trade ROI you *need* to copy profitably:

```
required_master_ROI ≈ (your measured drift δ) + (your taker fee) + (tool fee/split), as % of stake
```

Worked example from TradoxVPS: near 50¢ entries, 2¢ drift, peak crypto taker fee → **~6% per trade just to break even**. A 5%-per-trade master fails the bar. Two consequences: (1) *replay-test every candidate at your own lag and fees before going live*; (2) demand **headroom** above the bar, because drift is a floor, not a ceiling.

### C. The screening funnel that the sources collectively imply

1. **History gate** — age ≥ 6 months; ≥ 50 (preferably 200–1,000) closed positions. Below this, win rate is noise.
2. **Edge gate** — per-trade edge (avg win probability − avg entry) that clears *your* break-even bar with headroom; prefer mid-50s win rate at 30¢–70¢ entries over 90% favorites-buyers.
3. **Consistency gate** — monthly gains across multiple regimes, not one hot streak; recent performance weighted over all-time.
4. **Discipline gate** — steady position sizing vs bankroll; no single-market concentration; real (nonzero) drawdowns — zero-drawdown "wonders" are fabrication or wash accounts.
5. **Integrity gate** — wash-trading signatures: self-counterparty loops, sub-penny churn, high volume / low P&L, profits in one market, trades hugging news events.
6. **Beatability gate** — is the wallet a bot (speed-based edge)? If you can't match its latency, you inherit the tail of the edge, not the edge.

*Sources: [QuantVPS](https://www.quantvps.com/blog/polymarket-copy-trading-bot), [TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/), [Medium — Top Wallets](https://medium.com/@gemQueenx/top-polymarket-wallets-how-to-find-best-traders-for-copy-trading-26704fdfd836), [CoinDesk](https://www.coindesk.com/markets/2025/11/07/polymarket-s-trading-volume-may-be-25-fake-columbia-study-finds), [arXiv](https://arxiv.org/html/2604.24366v1).*

### D. Implications for this repo (polycop-bot-screener)

The research validates the screener's existing design and points at specific knobs:

- The **Edge-to-Friction** (24 pts) and **Slippage** (17 pts) parameters are exactly the two terms of the copier's equation — the report's break-even math is a direct justification for the gate thresholds already derived in `SCORING_SPEC`.
- The report adds weight to **not** trusting the leaderboard's headline PnL alone (wash trading, bots, survivorship) — consistent with the project's existing decision to read verdict metrics from the **simulation feed** rather than the leaderboard.
- Candidate additions the research supports: a **sample-size gate** (≥50–200 closed positions), a **wash-trading signature check** (self-counterparty churn / sub-penny volume / high-volume-low-PnL), a **bot-latency caveat** (flag wallets whose edge is likely speed-based), and **recency weighting** (even the best wallets drift). Note the arXiv paper finds a *longshot spread premium* and *maker-wallet concentration* — evidence the cheapest-to-copy wallet may not be the highest-scored one.

---

## Contrarian Views And Risks

- **Copy trading structurally underperforms the copied trader** — this is the strongest, most under-cited claim in the material. "Same call, worse price, both ways" is arithmetic, not opinion; the entire strategy is a bet that the master's edge minus your taxes is still positive. ([TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/))
- **The counter-trading counter-thesis:** a practitioner who stopped copying whales reports better results *countering* them in 30¢–70¢ ranges — betting against whale behavior rather than mirroring it. If true, the copyable-wallet search is partly a search for *predictable* behavior, not just profitable behavior. ([Reddit](https://www.reddit.com/r/PredictionsMarkets/comments/1te0lnl/i_stopped_copytrading_polymarket_whales_and/))
- **The "rich traders" you see may not be real.** WSJ documented influencers displaying phony trades on dummy sites designed to resemble Polymarket; Columbia documented coordinated wash networks gaming rankings. Leaderboard position is a weak prior on skill. ([WSJ](https://www.wsj.com/business/media/polymarket-social-media-bets-prediction-market-441cdeb5), [CoinDesk](https://www.coindesk.com/markets/2025/11/07/polymarket-s-trading-volume-may-be-25-fake-columbia-study-finds))
- **Not everyone agrees the manipulation narrative is real** — Rutgers statistician Harry Crane argues manipulation concerns are overblown/politically motivated. Flagged for balance; the operational advice (screen for wash signatures) survives either way. ([CoinDesk](https://www.coindesk.com/markets/2025/11/07/polymarket-s-trading-volume-may-be-25-fake-columbia-study-finds))
- **Infrastructure does not create edge.** A VPS removes preventable failures (sleeping laptop, dropped connections — each a trade at maximum drift) but cannot shorten Polymarket's settlement pipeline or un-pay the taker fee. Replay-test first; buy infrastructure only if the math survives. ([TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/))
- **Jurisdiction & platform risk.** International-platform wallet copying is restricted in the US, UK, France, Germany and others; Polymarket US is identity-verified with no public wallet trail, so the strategy doesn't port there. And **CLOB V2 cutover (April 28, 2026)** broke older open-source copy scripts (V1 clients, USDC.e funding) — check tool currency. ([TradoxVPS](https://tradoxvps.com/polymarket-copy-trading/))
- **Source-quality caveats.** TradoxVPS/QuantVPS/Suffescom are commercial (VPS/dev vendors) with a profit motive to make copy trading look viable; Reddit threads are anecdotal; the arXiv paper and Columbia study are the highest-quality evidence here, and both cut *against* naive optimism.

---

## Open Questions

1. **What is *your* measured detection lag and taker fee?** Every break-even number in this report is parametric; the correct settings for a given deployment depend on measuring these end-to-end on the market type being copied.
2. **How should win-rate decay be detected?** Community feedback names it as the main reason copied wallets stop paying, but no source gives a principled threshold (rolling-window decline? drawdown-based? regime-shift test?).
3. **Can wash-trading and bot signatures be scored automatically at screening scale?** The Columbia algorithm and arXiv's self-counterparty share suggest yes, but neither is packaged as a screening metric.
4. **Does the counter-trading thesis replicate?** One detailed practitioner report vs. the copy-trading mainstream; it needs a controlled test before being adopted.
5. **How do fast-market copy bars interact with min-order floors?** PolyCop feedback notes minimum share requirements skip small-value trades when copying whales — a sizing-model edge case this repo's `min_target_order_floor_usd` already touches.
6. **Post-CLOB-V2 drift:** has the April 2026 migration changed slippage/spread behavior in the fast markets the arXiv paper studied pre-migration?

---

## Sources

1. Polymarket Docs — *Place Orders* (limit, GTC/GTD, post-only): https://docs.polymarket.com/trading/place-orders
2. Polymarket Docs — *Prices & Order Books* (market orders, spread, depth): https://docs.polymarket.com/concepts/prices-orderbook
3. Polymarket Docs — *Order Lifecycle* (all orders are limit orders): https://docs.polymarket.com/concepts/order-lifecycle
4. Polymarket Docs — *Rate Limits*: https://docs.polymarket.com/api-reference/rate-limits
5. TradoxVPS Engineering — *Polymarket Copy Trading: The Math That Decides Whether Following a Wallet Pays* (copier's equation, lag anatomy, break-even bar, pre-copy checklist): https://tradoxvps.com/polymarket-copy-trading/ (commercial source)
6. QuantVPS — *Polymarket Copy Trading Bot: How Traders Find Alpha* (screening stats: 12.7% profitable, ≥50 positions, 55% win rate, wash red flags): https://www.quantvps.com/blog/polymarket-copy-trading-bot (commercial source)
7. Suffescom — *Polymarket Copy Trading Bot Development* (copy ratio 0.1×–1.0×, retry/slippage logic, capital needs): https://www.suffescom.com/development/polymarket-copy-trading-bot-development (commercial source)
8. arXiv 2604.24366 — *The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book* (longshot spread premium, depth concentration, maker-wallet concentration, wash share, depth decay near resolution): https://arxiv.org/html/2604.24366v1
9. CoinDesk — *Polymarket's Trading Volume May Be 25% Fake, Columbia Study Finds* (wash-trading estimates, 43k-wallet cluster, incentives gaming): https://www.coindesk.com/markets/2025/11/07/polymarket-s-trading-volume-may-be-25-fake-columbia-study-finds
10. SSRN 5714122 — *Network-Based Detection of Wash Trading* (Columbia, primary paper behind #9): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5714122
11. WSJ — *They Looked Like They Were Getting Rich on Polymarket—but None of It Was Real* (phony trades on dummy sites): https://www.wsj.com/business/media/polymarket-social-media-bets-prediction-market-441cdeb5
12. Medium (Solana Levelup) — *Top Polymarket Wallets: How to Find Best Traders for Copy Trading* (≥2% profit rates, gain/loss >2, zero-drawdown red flag, top-holders scanning): https://medium.com/@gemQueenx/top-polymarket-wallets-how-to-find-best-traders-for-copy-trading-26704fdfd836
13. Medium (Solana Levelup) — *Best PolyMarket Trading Bots* (PolyCop settings/0.5% fee/slippage cons/win-rate decay, Polygun, Ratio): https://medium.com/@gemQueenx/best-polymarket-bots-for-copy-trade-and-sniper-on-web-and-telegram-4992d9f24004
14. Reddit r/passive_income — *Are we all copy trading Polymarket wrong? I analyzed 1.3M wallets* (age >6 months, no bots, recency weighting, drift): https://www.reddit.com/r/passive_income/comments/1q0ev57/are_we_all_copy_trading_polymarket_wrong_i/
15. Reddit r/PredictionsMarkets — *Best Polymarket Copy Trading Settings 2026 | Guide* (workflow: Add Task → paste wallet → amount): https://www.reddit.com/r/PredictionsMarkets/comments/1rehut2/best_polymarket_copy_trading_settings_2026_guide/
16. Reddit r/PredictionsMarkets — *I stopped copytrading Polymarket whales and started counter-trading* (30¢–70¢ price band, counter 50/50 markets): https://www.reddit.com/r/PredictionsMarkets/comments/1te0lnl/i_stopped_copytrading_polymarket_whales_and/
17. Reddit r/AI_Agents — *14 of the top 20 Polymarket wallets are bots* (latency: top bot P&L is speed-based; why copying loses): https://www.reddit.com/r/AI_Agents/comments/1v21grs/14_of_the_top_20_polymarket_wallets_are_bots_and/
18. MetaMask — *What is slippage?* (orderbook depth → slippage mechanics): https://metamask.io/news/what-is-slippage
19. Binance Square — *From AMM to Order Book: Interpreting the Transition of Polymarket's CLOB* (mature books absorb size → lower slippage): https://www.binance.com/en-AE/square/post/27633854088641
20. Medium (The Capital) — *The Complete Polymarket Playbook* ($9B prediction-market context, algo traders running sub-second execution): https://medium.com/thecapital/the-complete-polymarket-playbook-finding-real-edges-in-the-9b-prediction-market-revolution-a2c1d0a47d9d

---

## Rerun Inputs

```
workflow: firecrawl-deep-research
topic: Polymarket copy-trade settings and wallet-screening parameters for copy-trading addresses
depth: thorough
output: markdown
```

*Not financial advice. Prediction-market and copy-trading risk includes total loss of staked funds; verify jurisdiction eligibility, fee schedules, and current platform mechanics against Polymarket's live documentation before trading.*

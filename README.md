# PolyCop Bot Screener 🎯 Bot Copy-Trading Audit Engine

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Build Status](https://github.com/AI-Degen-69/polycop-bot-screener/actions/workflows/ci.yml/badge.svg)

An automated screening, scoring, and analysis engine for Polymarket copy-trading target selection. **PolyCop Bot Screener** evaluates Polymarket trader wallets against strict hard-rejection safety gates and a continuous 100-point audit scoring model specifically tailored for small-to-mid bankroll copy-traders ($100–$1,000 capital).

---

## 🚀 Quick Start

### 1. Requirements & Setup
- Python 3.10 or higher
- Standard library dependencies (`urllib.request`, `json`, `http.server`)

```bash
git clone https.github.com/AI-Degen-69/polycop-bot-screener.git
cd polycop-bot-screener
```

### 2. Launch the Web Screener
To start the local web application with the pre-cached target dataset:

```bash
python screen.py
# or using npm / pnpm:
npm start
```
This automatically starts an HTTP server at `http://localhost:8080` and opens the interactive dashboard in your default browser.

### 3. Serve Only (Skip Scan Pipeline)
To launch the dashboard directly without running any scan:

```bash
python screen.py --serve-only
# or using npm / pnpm:
npm run dev
# pnpm dev
```

### 4. Force Rescan & Re-screen
To pull fresh leaderboard data and re-evaluate all candidates:

```bash
python screen.py --rescan
# or using npm / pnpm:
npm run rescan
```

---

## ⚡ 100-Point Weighted Scoring Model

PolyCop Bot Screener scores wallets in two stages: the 100-point Copyability Score below triages which
candidates are worth simulating, and a Slippage Sensitivity Sweep of Simulated Copy Runs decides the
verdict. Tiers shown on the dashboard come from simulated performance, not from the score. The gate
values, weights and tier bands below are generated from `app/src/screener/score_wallets.py` (the single
source of truth) — never edit this section by hand, and CI fails if it drifts from the code.

<!-- SCORING-SPEC:BEGIN -->

### Scoring Engine — Gates, Parameters and Tiers

> This section is generated from `app/src/screener/score_wallets.py` via
> `tools/scoring_docs.py`. Do not edit it by hand — change the code and run
> `python tools/scoring_docs.py generate`, or CI will fail the drift check.

#### Hard Rejection Gates (instant disqualification, never traded off)

| Gate | Condition | Why |
| :--- | :--- | :--- |
| PolyCop Site Score sanity floor | `< 40 / 100` | stops manually pasted garbage from being scored once the leaderboard pre-filter is gone |
| Toxic Copy Poison | `Modelled Copy PnL < $0` | a modelled copy that loses money is not a target |
| Slippage Cost Rate | `> 5.0% modelled` | roughly 21% real under the Friction Realism Multiplier (ADR 0001) |
| Hedged Rate | `> 3.0%` | market-making signature and doubled friction legs |
| Profit/Loss Ratio | `< 0.3` | winning pennies, losing dollars |
| Track Record Length | `< 25 lifetime markets` | a short record is a streak, not a track record; measured in lifetime markets because the daily activity series is a rolling window that cannot measure lifetime trades |
| Whale Avg Invest | `> $200` | a typical trade that dwarfs the bankroll cannot be mirrored |
| Divergence | `r20_pnl < $0 while actual_pnl > $1,000` | a dead edge must not be carried by history |

#### Continuous Parameters (100 points total)

| Parameter | Points | Zero points | Full marks |
| :--- | :---: | :--- | :--- |
| Edge-to-Friction Ratio | 24 | <= 1.0 (break-even) | >= 3.0 — edge per dollar of friction; the cheapest disqualifying arithmetic runs first |
| Slippage Cost Rate | 17 | >= 5.0% | <= 1.0% — modelled, before the Friction Realism Multiplier |
| Drawdown Depth | 13 | >= 0.50 of peak | 0.0 — from the lifetime equity curve |
| Recent Form | 11 | PnL <= $0 or slip unmeasured | >= 100% return over the recent-20 window at 0% slip — return on deployed capital, judged against the friction it came through (ADR 0004) |
| Daily Green Rate | 9 | <= 40% or fewer than 10 observed days | >= 85% — copy-adjusted, measured from real per-day simulated results |
| Profit/Loss Ratio | 9 | <= 0.3 | >= 3.0 |
| Sizing Fit | 6 | outside the Copyable Trade Window | at the window midpoint — peak derived from the Copy Execution Profile, never hand-picked |
| Hedged Control | 6 | >= 3.0% | 0% |
| Markets Sample | 3 | <= 25 | >= 200 |
| Capital Efficiency | 2 | 0 | >= 30 PnL/volume ratio |

#### Copyability Score Tier Bands (triage only — verdicts come from simulation)

| Tier | Score |
| :--- | :--- |
| S-Tier (God-Tier Target) | &ge; 80 |
| A-Tier (Strong Copy Target) | &ge; 71 |
| B-Tier (Moderate Copy Target) | &ge; 65 |
| C-Tier (High Risk / Volatile) | &ge; 56 |
| F-Tier (Toxic / Rejection) | < 56 |

#### Simulated Verdict Tier Bands (Edge Retention — the verdict)

| Tier | Edge Retention |
| :--- | :--- |
| S-Tier (God-Tier Target) | &ge; 0.85 |
| A-Tier (Strong Copy Target) | &ge; 0.70 |
| B-Tier (Moderate Copy Target) | &ge; 0.50 |
| C-Tier (High Risk / Volatile) | &ge; 0.30 |
| F-Tier / REJECT | < 0.30 |

<!-- SCORING-SPEC:END -->

---

## 🛠️ Project Structure

```
polycop-bot-screener/
├── app/
│   ├── data/                   # Scraped and verified JSON datasets
│   ├── src/
│   │   ├── pipeline/           # Phase 1 leaderboard scrape & Phase 2 verification
│   │   ├── screener/           # Python 100-Point audit scoring engine
│   │   └── server/             # Local Web App HTTP proxy server
│   └── web/                    # Frontend dashboard (HTML/CSS/JS)
│       ├── css/styles.css      # Dark-mode glassmorphism stylesheet
│       └── js/                 # Dashboard UI controller
├── tasks/                      # Project roadmap & planning notes
├── tests/                      # Unit tests for scoring engine
└── screen.py                   # Master entry point script
```

---

## 🧪 Running Tests

The suite mixes `unittest` classes and plain pytest functions, so it must be run with pytest. Run the full offline suite:

```bash
python -m pytest tests/ --ignore=tests/verify_web_app_live.py -k "not test_proxy_latency_discovery"
# or using npm / pnpm:
npm test
```

`tests/verify_web_app_live.py` is a live end-to-end verifier, excluded above because it requires a
running server. To run it, start the app in one terminal and the verifier in another:

```bash
python screen.py --serve-only
```

```bash
python tests/verify_web_app_live.py
```

> **Note:** `python -m unittest discover tests` collects only the `unittest`-class tests and silently
> skips the pytest-style ones. Use pytest. Requires `pytest` installed (`pip install pytest`).

---

## 📄 License

MIT License. Developed for automated Polymarket copy-trading research.

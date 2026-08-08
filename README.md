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
```
This automatically starts an HTTP server at `http://localhost:8080` and opens the interactive dashboard in your default browser.

### 3. Force Rescan & Re-screen
To pull fresh leaderboard data and re-evaluate all candidates:

```bash
python screen.py --rescan
```

---

## ⚡ 100-Point Weighted Scoring Model

PolyCop Bot Screener scores wallets using a multi-factor continuous model and instant disqualification gates.

### 🛑 Hard Rejection Gates (Instant Disqualification)
- **Toxic Copy Poison**: Backtest Copy PnL < $0
- **High Slippage Rate**: Slippage Cost Rate `(Actual - Copy) / |Actual| > 100%`
- **Hedged Rate Violation**: Hedged Position Rate > 3.0%
- **Poor Risk/Reward**: P/L Ratio < 0.3
- **Short Track Record**: Active Markets < 20
- **Whale Trade Sizing**: Avg Investment > $300 USD
- **High-Frequency Arbitrage Bot**: Markets > 300 & Slippage Rate > 5.0%

### 📊 Weighted Scoring Breakdown (100 Points Total)
| Parameter | Weight | Target Criteria |
| :--- | :---: | :--- |
| **Slippage Cost Rate** | 20% | `< 10%` slippage cost rate |
| **Recent 20 PnL & Slip** | 15% | PnL > $1,000 & Slip < 5% |
| **Hedged Position Rate** | 15% | `< 3.0%` total hedged rate |
| **Daily Green Rate** | 15% | `> 85%` winning days |
| **Recent 20 Win Rate** | 10% | `> 75%` win rate |
| **Avg Profit / Loss Ratio** | 10% | `> 3.0` P/L ratio |
| **PnL / Volume Ratio** | 5% | `> 30%` profit efficiency |
| **Markets Sample Size** | 5% | `> 200` total markets traded |
| **Continuous Sizing Fit** | 5% | `$25` optimal peak sizing |

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
│       └── js/                 # Dashboard UI controller & JS scoring engine
├── tasks/                      # Project roadmap & planning notes
├── tests/                      # Unit tests for scoring engine
└── screen.py                   # Master entry point script
```

---

## 🧪 Running Tests

To run the automated unit test suite:

```bash
python -m unittest discover tests
```

---

## 📄 License

MIT License. Developed for automated Polymarket copy-trading research.

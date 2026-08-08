# Plan: PolyCop Address Screener Web Application Restructuring

Restructuring the entire repository from loose root scripts into a modular, production-ready PolyCop Address Screener Web Application architecture.

## Proposed Directory Hierarchy & Naming Convention

```
poly-cop-bot/
├── app.py                      # Master Web App & Scanner Launcher CLI
├── data/                       # Processed scan data files
│   ├── .gitkeep
│   ├── raw_leaderboard.json    # Scraped leaderboard profiles (PolyCop Score > 60)
│   └── clean_targets.json      # Screened 100% PASS copy targets
├── src/                        # Python Application Source
│   ├── __init__.py
│   ├── pipeline/               # Data ingestion & cleaning modules
│   │   ├── __init__.py
│   │   ├── scraper.py          # Leaderboard pagination & API fetcher
│   │   ├── exporter.py         # Clean target exporter & serializer
│   │   └── cleaner.py          # Cache clearing & reset utility
│   ├── screener/               # $100 Bankroll Audit Engine
│   │   ├── __init__.py
│   │   └── rules_engine.py     # 8 Hard Rejection Gates & 9 Continuous Parameters
│   └── server/                 # Backend HTTP & CORS proxy server
│       ├── __init__.py
│       └── proxy_server.py     # Port 8050 server + API routes (/api/...)
└── web/                        # Frontend Web Application
    ├── index.html              # Single Page Application HTML markup
    ├── css/
    │   └── styles.css          # Design system, sparkly gem borders & theme
    └── js/
        ├── app.js              # UI state management & modal navigation
        └── screener_engine.js  # Client-side JS engine mirror
```

## Work Breakdown

### Phase 1: Python Core Engine & Pipeline Restructuring
- Create `src/screener/rules_engine.py` (migrated from `.agents/skills/.../wallet_screener.py`).
- Create `src/pipeline/scraper.py` (migrated from `scan_all_leaderboard_wallets.py`).
- Create `src/pipeline/exporter.py` (migrated from `export_clean_targets.py`).
- Create `src/pipeline/cleaner.py` (migrated from `clear_scan_data.py`).
- Create `src/server/proxy_server.py` (migrated from `serve_visualizer.py`).

### Phase 2: Web App Frontend Refactoring
- Modularize `wallet_audit_visualizer.html` into `web/index.html`, `web/css/styles.css`, and `web/js/app.js` + `web/js/screener_engine.js`.
- Ensure `web/index.html` feeds cleanly from `data/clean_targets.json` or `/api/leaderboard` proxy.

### Phase 3: Root Entry Point & Verification
- Create root `app.py` launcher script (`python app.py` launches server + opens browser).
- Verify server on `http://localhost:8050`.

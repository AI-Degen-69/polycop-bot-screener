# Task Checklist: Web App Restructuring

- [x] **Task 1**: Create directory structure (`src/screener`, `src/pipeline`, `src/server`, `web/css`, `web/js`, `data`, `tests`)
- [x] **Task 2**: Refactor Python backend into modular package (`src/screener/score_wallets.py`, `src/pipeline/phase1_scrape_leaderboard.py`, `src/pipeline/phase2_filter_targets.py`, `src/pipeline/reset_data_cache.py`, `src/server/serve_web_app.py`)
- [x] **Task 3**: Create master `screen.py` launcher CLI
- [x] **Task 4**: Modularize frontend into `web/index.html`, `web/css/styles.css`, `web/js/client_score_engine.js`, `web/js/app.js`
- [x] **Task 5**: Delete old loose root files (`clear_scan_data.py`, `export_clean_targets.py`, `scan_all_leaderboard_wallets.py`, `serve_visualizer.py`, `wallet_audit_visualizer.html`)
- [x] **Task 6**: End-to-end verification of `python screen.py` and dataset rendering (119 verified targets live)

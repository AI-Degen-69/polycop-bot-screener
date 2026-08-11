#!/usr/bin/env python3
"""
PolyCop Bot Screener - Master Entry Point & Server Launcher
Usage:
    python screen.py
    python screen.py --rescan
"""

import os
import sys
import webbrowser

# Running `python screen.py` puts the repo root on sys.path; `paths` lives
# in app/src, so the one-line header below makes it reachable.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "src"))
from paths import DATA_DIR, PHASE3_FILE
# The page renders the simulation feed, so that is the file whose absence means
# the pipeline has not run — not the triage feed it is built from.
VERIFIED_DATA_FILE = os.path.join(DATA_DIR, PHASE3_FILE)

from pipeline.orchestrator import run_pipeline
from server.serve_web_app import start_server, PORT

def main():
    force_rescan = "--rescan" in sys.argv
    skip_scan = "--serve-only" in sys.argv or "--no-scan" in sys.argv
    test_mode = "--test" in sys.argv

    print("==========================================================")
    print("  [PolyCop Bot Screener] - Master Web App Launcher")
    print("==========================================================")

    # Step 1: Ensure dataset exists or run pipeline
    if skip_scan:
        print("\n[PIPELINE] Serve-only mode requested. Skipping wallet scan pipeline.")
    elif force_rescan or not os.path.exists(VERIFIED_DATA_FILE):
        print("\n[PIPELINE] Dataset missing or rescan requested. Running pipeline...")
        run_pipeline()
    else:
        print(f"\n[PIPELINE] Verified dataset found: {VERIFIED_DATA_FILE}")

    if test_mode:
        print("[TEST] Startup check completed successfully.")
        return

    # Step 2: Open browser
    app_url = f"http://localhost:{PORT}"
    print(f"\n[SERVER] Launching PolyCop Bot Screener Web App at {app_url}...")
    try:
        webbrowser.open(app_url)
    except Exception as e:
        print(f"[NOTICE] Could not auto-open browser: {e}")

    # Step 3: Start HTTP Proxy Server
    start_server(PORT)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Where the repo lives and what the pipeline's files are called.

The single source for every directory and dataset filename in the project.
Everything else imports from here instead of re-deriving paths from __file__,
so a renamed data file or a moved directory is a one-line change and the
pipeline, the server and the tests all follow.

Importing this module also ensures `app/src` and `tools` are importable by
their package names (pipeline, screener, server, execution, tools) — the one
place that sys.path surgery happens. Entry scripts still need one line before
they can import this module: a module that can be run directly inserts its own
`app/src` directory first (see the canonical header at the top of any module
that uses this one), and a pure-library module simply relies on its caller to
have done that.
"""
import os
import sys

# app/src/paths.py -> app/src -> app -> repo root
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SRC_DIR)
PROJECT_ROOT = os.path.dirname(APP_DIR)

WEB_DIR = os.path.join(APP_DIR, "web")
DATA_DIR = os.path.join(APP_DIR, "data")
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")

# The dataset file inventory. The pipeline writes these names, screen.py
# decides staleness from the feed, and the server serves it — one constant so
# a rename cannot split the writers from the readers.
PHASE1_FILE = "phase1_scraped_wallets.json"
PHASE2_FILE = "phase2_verified_targets.json"
PHASE3_FILE = "phase3_simulated_targets.json"

# The scanner's first-party measurements, one record per wallet. Phase 1
# discovers addresses; every figure the audit scores comes from here (ADR 0012).
SCANNED_WALLETS_FILE = "scanned_wallets.json"

# Make the app/src packages (pipeline, screener, server, execution) and the
# tools package importable by name. `tools` is a package under the repo root,
# so it needs PROJECT_ROOT on the path — inserting TOOLS_DIR alone would make
# `import tools.x` look for tools/tools/x. TOOLS_DIR is also inserted because
# the tools scripts are imported by bare name (`import scoring_docs`) from
# tests. Idempotent and cheap; safe to import from any number of modules.
for _entry in (SRC_DIR, PROJECT_ROOT, TOOLS_DIR):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

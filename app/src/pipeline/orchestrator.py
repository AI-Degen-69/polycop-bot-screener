#!/usr/bin/env python3
"""Run the full scan pipeline: scrape, filter, simulate.

The three phases are tightly coupled by the data they produce — each writes a
file the next reads — but they are also legitimately separable: each can be
run independently against a fixture, which is exactly how the tests exercise
them. This module exists so that the pipeline-orchestration logic (phase1→2→3)
lives in one place rather than being duplicated across screen.py and the web
handler. Adding a phase now touches one call site, not two.
"""
import os

# A library module: the caller has already made app/src importable, so this
# reaches the inventory through the one paths module.
from paths import DATA_DIR, PHASE3_FILE  # noqa: E402
from pipeline.phase1_scrape_leaderboard import fetch_and_scrape_leaderboard  # noqa: E402
from pipeline.phase2_filter_targets import run_phase2_filter  # noqa: E402
from pipeline.phase3_simulation_rank import run_phase3_simulation_rank  # noqa: E402


def run_pipeline():
    """Run all three phases in order and return the Phase 3 output file path."""
    print("\n[PIPELINE] Running full scan pipeline...")
    fetch_and_scrape_leaderboard()
    run_phase2_filter()
    run_phase3_simulation_rank()
    phase3_file = os.path.join(DATA_DIR, PHASE3_FILE)
    return phase3_file
#!/usr/bin/env python3
"""The boundary ADR 0012 drew, enforced rather than described.

The decision is that the aggregator supplies candidate addresses and every
judgment derives from Polymarket's own fills. Prose in an ADR does not stop a
convenient precomputed field from being read back three refactors later, and
the failure would be silent: a wallet would score, the number would look
reasonable, and nothing would say where it came from.

So the boundary is a test. It reads the source and fails when an aggregator
metric name appears anywhere it could reach a score.
"""
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "app", "src")

# The aggregator's precomputed judgments. Each was read by a gate or a scored
# parameter before the cutover; none has a first-party meaning.
AGGREGATOR_METRIC_FIELDS = (
    "polycop_site_score",
    "copy_backtest_pnl",
    "avg_profit_loss_ratio",
    "hedged_percentage",
    "r20_wr",
    "recent_20_win_rate",
    "recent_20_slippage",
    "daily_stats_json",
    "all_pnl_json",
    "markets_traded",
    "bt_copy_pnl",
)

# Where an aggregator name is still legitimate, and why.
EXEMPT = {
    # Drops every field but the address - it has to name them to drop them.
    "pipeline/phase1_scrape_leaderboard.py":
        "the phase-1 boundary, which is what does the dropping",
    # The Simulated Verdict still leaves the building (ADR 0012, accepted risk).
    "pipeline/run_mock_client.py":
        "the verdict endpoint, still third-party by decision",
    # Parses the aggregator's series shapes; now fed first-party curves.
    "screener/derived_metrics.py":
        "series parsers, now fed by first-party curves",
    # Proxies the aggregator's site for the page; touches no scoring path.
    "server/serve_web_app.py":
        "the read-only site proxy",
}


def _source_files():
    for root, _dirs, files in os.walk(SRC_DIR):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, SRC_DIR).replace(os.sep, "/")
            yield rel, path


def _offending_fields(text):
    return [
        field for field in AGGREGATOR_METRIC_FIELDS
        if re.search(rf"\b{re.escape(field)}\b", text)
    ]


def test_no_aggregator_metric_reaches_a_scoring_path():
    offenders = {}
    for rel, path in _source_files():
        if rel in EXEMPT:
            continue
        with open(path, encoding="utf-8") as handle:
            found = _offending_fields(handle.read())
        if found:
            offenders[rel] = found
    assert not offenders, (
        "aggregator-computed fields reached a scoring path (ADR 0012): "
        f"{offenders}. Derive the figure from first-party fills, or add the "
        "file to EXEMPT with the reason it is allowed."
    )


def test_the_scanner_reads_no_aggregator_metric():
    """The scanner discovers addresses and measures from `data-api`. An
    aggregator judgment appearing here would be laundered into the record, and
    every downstream check would then pass."""
    path = os.path.join(REPO_ROOT, "overnight_scanner.py")
    with open(path, encoding="utf-8") as handle:
        found = _offending_fields(handle.read())
    assert not found, f"the scanner read aggregator-computed fields: {found}"


def test_every_exemption_names_a_file_that_exists():
    """An exemption for a deleted file is a hole nobody is watching."""
    present = {rel for rel, _path in _source_files()}
    missing = sorted(set(EXEMPT) - present)
    assert not missing, f"exemptions for files that no longer exist: {missing}"


def test_no_aggregator_adapter_remains_to_be_rewired():
    """The module that mapped the aggregator's shape into engine metrics is
    gone. Its absence is the strongest form of the rule: there is nothing left
    to point back at the engine."""
    assert not os.path.exists(os.path.join(SRC_DIR, "pipeline", "leaderboard_adapter.py"))

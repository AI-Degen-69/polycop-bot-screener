#!/usr/bin/env python3
"""The Simulated Copy Run response, read as metrics.

The run_mock endpoint replays a target's transaction history through the Copy
Execution Profile and returns a per-run report plus a decision log. This module
is the adapter that turns that upstream response into the metrics the screen
reads: the headline figures and the Copyable Window Share.

It lives in the screener, not beside the transport, because it is domain
logic — what a response means for copyability. The transport module
(`pipeline.run_mock_client`) fetches; this module reads.
"""
from typing import Any, Dict


def parse_simulated_run_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """The headline figures of a Simulated Copy Run, as the screen reads them."""
    logs = data.get("logs", [])
    return {
        "sim_total_pnl": float(data.get("sim_total_pnl", 0.0)),
        "target_total_pnl": float(data.get("target_total_pnl", 0.0)),
        "max_drawdown": float(data.get("max_drawdown", 0.0)),
        "pl_ratio": float(data.get("pl_ratio", 0.0)),
        "win_rate": float(data.get("win_rate", 0.0)),
        "winning_days": int(data.get("winning_days", 0)),
        "losing_days": int(data.get("losing_days", 0)),
        "flat_days": int(data.get("flat_days", 0)),
        "trading_days": int(data.get("trading_days", 0)),
        "intercepted": int(data.get("intercepted", 0)),
        "executed_trades": int(data.get("total_trades", 0)),
        "total_decisions": len(logs),
        "logs": logs
    }


def calculate_copyable_window_share(data: Dict[str, Any]) -> float:
    """The share of a target's trade signals inside the Copyable Trade Window.

    Reconciles the decision log entries (INTERCEPT vs SKIP_FILTER / SKIP_CAP):
    an intercepted signal is one the follower gets to mirror at all. Absent
    logs mean nothing was measured, which reads as zero rather than as a
    measured verdict.
    """
    logs = data.get("logs", [])
    if not logs:
        return 0.0

    intercept_count = sum(
        1 for item in logs
        if item.get("type") == "INTERCEPT" or item.get("status") == "INTERCEPT"
    )
    return intercept_count / float(len(logs))

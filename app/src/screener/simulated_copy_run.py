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
import re
from typing import Any, Dict, List

# The decision log types one entry per target trade. `type` is coarse and says
# INTERCEPT for both refusals and ghost positions; `action` is the field that
# partitions the log. Spike 0002 established this against the trade count
# `market_stats[].target_trades` supplies independently.
_MIRRORED_ACTIONS = ("BUY", "SELL", "REDEEM")
_REFUSED_BY_WINDOW = "SKIP_FILTER"
_STOPPED_BY_RISK_CAP = "SKIP_CAP"

# The target-side verb the message reports, which is what says whether a
# decision was an entry signal at all. Exits are not admitted or refused by a
# size window — they inherit whatever the entry did.
_TARGET_VERB = re.compile(r"Target (BUY|SELL|REDEEM|MERGE)")


def _decision_action(entry: Dict[str, Any]) -> str:
    """The decision an entry records, tolerating the older `status` spelling."""
    return str(entry.get("action") or entry.get("status") or entry.get("type") or "")


def _target_verb(entry: Dict[str, Any]) -> str:
    """The verb the target itself played, read off the log message."""
    match = _TARGET_VERB.search(str(entry.get("msg", "")))
    return match.group(1) if match else ""


def _is_entry_signal(entry: Dict[str, Any]) -> bool:
    """Whether a decision is a target entry, so the window had a say in it.

    The message is the authority when it carries a verb. Without one the action
    still identifies the refusals, which only ever land on entries.
    """
    verb = _target_verb(entry)
    if verb:
        return verb == "BUY"
    return _decision_action(entry) in (_REFUSED_BY_WINDOW, _STOPPED_BY_RISK_CAP, "BUY")


def _coerce_float(value, default: float) -> float:
    """An upstream figure coerced to float, or the default when it is missing
    or malformed. Phase 3 now reads this parser on the live scan path, so a
    malformed upstream field must read as unmeasured rather than crash a scan
    — the same tolerance `derived_metrics._load` and the adapter's
    `_optional_float` apply.
    """
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _coerce_int(value, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_simulated_run_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """The headline figures of a Simulated Copy Run, as the screen reads them."""
    logs = data.get("logs", [])
    return {
        "sim_total_pnl": _coerce_float(data.get("sim_total_pnl"), 0.0),
        "target_total_pnl": _coerce_float(data.get("target_total_pnl"), 0.0),
        # None when the response did not report one — a missing drawdown must
        # not masquerade as a measured "no drawdown" of 0.0 (ADR 0007's absent
        # stays absent discipline applies to the verdict side too).
        "max_drawdown": _coerce_float(data.get("max_drawdown"), None),
        "pl_ratio": _coerce_float(data.get("pl_ratio"), 0.0),
        "win_rate": _coerce_float(data.get("win_rate"), 0.0),
        "winning_days": _coerce_int(data.get("winning_days"), 0),
        "losing_days": _coerce_int(data.get("losing_days"), 0),
        "flat_days": _coerce_int(data.get("flat_days"), 0),
        "trading_days": _coerce_int(data.get("trading_days"), 0),
        # `intercepted` counts target exits the simulation could not follow for
        # want of inventory — ghost positions, a miss rather than a copy — and
        # `total_trades` counts markets the simulation traded, not orders. The
        # names here say which is which so neither can be read as the other.
        "ghost_exits": _coerce_int(data.get("intercepted"), 0),
        "traded_markets": _coerce_int(data.get("total_trades"), 0),
        "mirrored_orders": sum(
            1 for entry in logs if _decision_action(entry) in _MIRRORED_ACTIONS
        ),
        "target_trades": len(logs),
        "logs": logs
    }


def extract_skip_reasons(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """The decision-log entries that stopped a target entry signal from
    becoming a copy, as readable reasons.

    Spec #13 asks for the simulation's decision log retained so a reader can
    see why a specific trade was skipped rather than infer it. The window's
    refusal (SKIP_FILTER) and the bankroll's risk cap (SKIP_CAP) are the two
    ways an entry does not get copied; mirrored actions and ghost exits are
    not skips. Each reason carries the upstream message, which names the
    failing filter.
    """
    return [
        {"action": _decision_action(entry), "msg": str(entry.get("msg", "")).strip()}
        for entry in data.get("logs", [])
        if _decision_action(entry) in (_REFUSED_BY_WINDOW, _STOPPED_BY_RISK_CAP)
    ]


def calculate_copyable_window_share(data: Dict[str, Any]) -> float:
    """The share of a target's entry signals the Copyable Trade Window admits.

    The window is a range of trade sizes, and it has a say only where the
    target opens a position: exits inherit whatever the entry did, so they
    belong in neither term. The denominator is therefore the target's BUY
    decisions and the numerator is those the window did not refuse.

    A SKIP_CAP counts as admitted — the window let the trade through and the
    bankroll's risk cap stopped it, which is Balance Miss's subject, not this
    metric's. Absent logs, or a target that never bought inside the fetched
    window, mean nothing was measured, which reads as zero rather than as a
    measured verdict.

    See `docs/spikes/0002-run-mock-field-semantics.md` — the earlier formula
    read `intercepted`, which counts the exits the follower *missed*.
    """
    entry_signals = [entry for entry in data.get("logs", []) if _is_entry_signal(entry)]
    if not entry_signals:
        return 0.0

    admitted = sum(
        1 for entry in entry_signals
        if _decision_action(entry) != _REFUSED_BY_WINDOW
    )
    return admitted / float(len(entry_signals))

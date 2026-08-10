import os
import sys
from typing import Dict, Any, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# SCRIPT_DIR is app/src/screener -> SRC_DIR is app/src
SRC_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from execution.copy_execution_profile import CURRENT_PROFILE
from pipeline.run_mock_client import fetch_simulated_copy_run
from screener.score_wallets import calculate_edge_retention


DEFAULT_SLIPPAGE_LEVELS = [2.0, 5.0, 10.0, 15.0]

def run_slippage_sensitivity_sweep(
    wallet: str,
    profile=None,
    slippage_levels: Optional[List[float]] = None,
    fetcher=None,
    cache_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run Slippage Sensitivity Sweep for a wallet across specified slippage levels.
    Enforces rejection gate ordering: Reject if PnL at 10% <= 0 BEFORE computing retention.

    Per ADR 0007, a level whose fetch failed records `None` in `pnl_by_level`
    (an absent measurement), never `0.0`. An unmeasured gated level (10% or
    2%) rejects the wallet with an endpoint-failure reason and sets
    `endpoint_failure: True`; a genuinely measured `<= 0` keeps the measured
    rejection wording. A failed non-gated level (5% or 15%) records a `None`
    gap but does not reject.
    """
    if profile is None:
        profile = CURRENT_PROFILE
    if slippage_levels is None:
        slippage_levels = DEFAULT_SLIPPAGE_LEVELS

    sweep_results = {}
    pnl_by_level = {}

    for slip in slippage_levels:
        res = fetch_simulated_copy_run(
            wallet=wallet,
            profile=profile,
            slippage=slip,
            fetcher=fetcher,
            cache_dir=cache_dir
        )
        if res.get("success") and res.get("data"):
            pnl = float(res["data"].get("sim_total_pnl", 0.0))
        else:
            # ADR 0007: a fetch that failed is an absent measurement, not a
            # measured zero. Recording None keeps a network failure and a
            # genuine break-even distinguishable in every downstream reader.
            pnl = None

        sweep_results[slip] = res
        pnl_by_level[slip] = pnl

    # `None` means the endpoint never answered for that level (ADR 0007), so
    # every level is read as Optional[float], never as a fabricated zero.
    pnl_10 = pnl_by_level.get(10.0)
    pnl_2 = pnl_by_level.get(2.0)

    # --- GATE ORDERING CHECK ---
    # 1. 10% figure unmeasured -> reject with the endpoint-failure reason,
    #    never a fabricated dollar figure (ADR 0007)
    if pnl_10 is None:
        return {
            "wallet": wallet,
            "is_rejected": True,
            "rejection_reason": "Simulation unavailable at 10% slippage threshold (endpoint failure)",
            "edge_retention": None,
            "endpoint_failure": True,
            "pnl_by_level": pnl_by_level,
            "sweep_results": sweep_results
        }

    # 2. Negative or zero PnL at 10% slippage -> Reject wallet (measured wording)
    if pnl_10 <= 0.0:
        return {
            "wallet": wallet,
            "is_rejected": True,
            "rejection_reason": f"Non-positive Simulated Copy PnL (${pnl_10:.2f}) at 10% slippage threshold",
            "edge_retention": None,
            "endpoint_failure": False,
            "pnl_by_level": pnl_by_level,
            "sweep_results": sweep_results
        }

    # 3. 2% figure unmeasured -> endpoint failure (no baseline, no retention)
    if pnl_2 is None:
        return {
            "wallet": wallet,
            "is_rejected": True,
            "rejection_reason": "Simulation unavailable at 2% slippage baseline (endpoint failure)",
            "edge_retention": None,
            "endpoint_failure": True,
            "pnl_by_level": pnl_by_level,
            "sweep_results": sweep_results
        }

    # 4. Negative or zero PnL at 2% baseline -> Reject wallet (measured wording)
    if pnl_2 <= 0.0:
        return {
            "wallet": wallet,
            "is_rejected": True,
            "rejection_reason": f"Non-positive Simulated Copy PnL (${pnl_2:.2f}) at 2% slippage baseline",
            "edge_retention": None,
            "endpoint_failure": False,
            "pnl_by_level": pnl_by_level,
            "sweep_results": sweep_results
        }

    # 5. Only calculate Edge Retention if both survive positive check
    retention = calculate_edge_retention(pnl_10_pct=pnl_10, pnl_2_pct=pnl_2)

    return {
        "wallet": wallet,
        "is_rejected": False,
        "rejection_reason": None,
        "edge_retention": retention,
        "endpoint_failure": False,
        "pnl_by_level": pnl_by_level,
        "sweep_results": sweep_results
    }

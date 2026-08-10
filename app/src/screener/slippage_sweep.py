from typing import Dict, Any, List, Optional

try:

    from pipeline.run_mock_client import fetch_simulated_copy_run
    from screener.score_wallets import calculate_edge_retention
    from execution.copy_execution_profile import CURRENT_PROFILE
except ModuleNotFoundError:
    from app.src.pipeline.run_mock_client import fetch_simulated_copy_run
    from app.src.screener.score_wallets import calculate_edge_retention
    from app.src.execution.copy_execution_profile import CURRENT_PROFILE


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
            pnl = 0.0
        
        sweep_results[slip] = res
        pnl_by_level[slip] = pnl

    pnl_10 = pnl_by_level.get(10.0, 0.0)
    pnl_2 = pnl_by_level.get(2.0, 0.0)

    # --- GATE ORDERING CHECK ---
    # 1. Negative or zero PnL at 10% slippage -> Reject wallet
    if pnl_10 <= 0.0:
        return {
            "wallet": wallet,
            "is_rejected": True,
            "rejection_reason": f"Non-positive Simulated Copy PnL (${pnl_10:.2f}) at 10% slippage threshold",
            "edge_retention": None,
            "pnl_by_level": pnl_by_level,
            "sweep_results": sweep_results
        }

    # 2. Negative or zero PnL at 2% baseline -> Reject wallet
    if pnl_2 <= 0.0:
        return {
            "wallet": wallet,
            "is_rejected": True,
            "rejection_reason": f"Non-positive Simulated Copy PnL (${pnl_2:.2f}) at 2% slippage baseline",
            "edge_retention": None,
            "pnl_by_level": pnl_by_level,
            "sweep_results": sweep_results
        }

    # 3. Only calculate Edge Retention if both survive positive check
    retention = calculate_edge_retention(pnl_10_pct=pnl_10, pnl_2_pct=pnl_2)

    return {
        "wallet": wallet,
        "is_rejected": False,
        "rejection_reason": None,
        "edge_retention": retention,
        "pnl_by_level": pnl_by_level,
        "sweep_results": sweep_results
    }

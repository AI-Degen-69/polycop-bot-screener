import json
from typing import Dict, Any, Optional

def build_run_mock_payload(
    wallet: str,
    copy_pct: float = 3.0,
    slippage: float = 10.0,
    capital: float = 100.0,
    limit: int = 4000
) -> Dict[str, Any]:
    """
    Build payload for POST /api/run_mock endpoint per Spike 0001 specification.
    """
    return {
        "wallet": wallet,
        "fetch_mode": "limit",
        "limit": limit,
        "start_time": None,
        "end_time": None,
        "copy_pct": copy_pct,
        "slippage": slippage,
        "capital": capital,
        "target_max_price": 0.95,
        "target_min_price": 0.05,
        "target_max_usd": 167,
        "target_min_usd": 33,
        "sim_max_per_token": 5,
        "sim_max_global": 100,
        "allowed_categories": [],
        "exclude_words": [],
        "blacklist": [],
        "whitelist": []
    }

def parse_run_mock_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse response dictionary returned by run_mock endpoint.
    """
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
    """
    Calculate the ratio of target trade signals that fell into copyable trade window bounds.
    Reconciles log decision entries (INTERCEPT vs SKIP_FILTER / SKIP_CAP).
    """
    logs = data.get("logs", [])
    if not logs:
        return 0.0
    
    intercept_count = sum(1 for item in logs if item.get("type") == "INTERCEPT" or item.get("status") == "INTERCEPT")
    return intercept_count / float(len(logs))

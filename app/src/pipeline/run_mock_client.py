import json
import os
import sys
import time
from typing import Dict, Any, Optional

from execution.copy_execution_profile import CURRENT_PROFILE, CopyExecutionProfile

def build_run_mock_payload(
    wallet: str,
    copy_pct: Optional[float] = None,
    slippage: float = 10.0,
    capital: float = 100.0,
    limit: int = 4000,
    profile: Optional[CopyExecutionProfile] = None
) -> Dict[str, Any]:
    """
    Build payload for POST /api/run_mock endpoint per Spike 0001 specification.

    The window and cap fields are derived from the Copy Execution Profile, so
    the simulation always tests the same execution settings the score was
    computed under. They were literals here (33 / 167 / 5) and could drift
    from the profile — which is exactly what would have made a widened-cap
    backtest a fiction: the endpoint would keep simulating a $5 position
    however wide the profile claimed the window was.

    `copy_pct` is derived from the same profile for the same reason: a literal
    default would let a caller who selected a 5% profile simulate a 3% copy
    ratio against that profile's window and cap fields. An explicit value is
    still honoured, since a sweep varies one field at a time.
    """
    if profile is None:
        profile = CURRENT_PROFILE
    if copy_pct is None:
        copy_pct = profile.copy_ratio * 100.0
    return {
        "wallet": wallet,
        "fetch_mode": "limit",
        "limit": limit,
        "start_time": None,
        "end_time": None,
        "copy_pct": copy_pct,
        "slippage": slippage,
        "capital": capital,
        "target_max_price": profile.max_price,
        "target_min_price": profile.min_price,
        "target_max_usd": int(round(profile.window_max_usd)),
        "target_min_usd": int(round(profile.window_min_usd)),
        "sim_max_per_token": int(round(profile.max_single_position_usd)),
        "sim_max_global": int(round(profile.global_cap_usd)),
        "allowed_categories": [],
        "exclude_words": [],
        "blacklist": [],
        "whitelist": []
    }

_last_request_time = 0.0

def fetch_simulated_copy_run(
    wallet: str,
    profile=None,
    slippage: float = 10.0,
    fetcher=None,
    cache_dir: Optional[str] = None,
    throttle_seconds: float = 0.1
) -> Dict[str, Any]:
    """
    Fetch a Simulated Copy Run for a wallet under a specific Copy Execution Profile.
    Cached by wallet + profile fingerprint + slippage level.
    """
    if profile is None:
        profile = CURRENT_PROFILE

    wallet_clean = wallet.lower().strip()
    cache_filename = f"{wallet_clean}_{profile.fingerprint}_{int(slippage)}.json"
    
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, cache_filename)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                return {"success": True, "cached": True, "data": cached_data}
            except Exception:
                pass
    else:
        cache_path = None

    payload = build_run_mock_payload(
        wallet=wallet_clean,
        slippage=slippage,
        capital=profile.bankroll_usd,
        profile=profile
    )

    if fetcher is None:
        def default_fetcher(p):
            import urllib.request
            url = "https://polycop.fun/api/run_mock"
            data_bytes = json.dumps(p).encode("utf-8")
            req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                return json.loads(resp.read().decode("utf-8"))
        fetcher = default_fetcher

    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < throttle_seconds:
        time.sleep(throttle_seconds - elapsed)
    _last_request_time = time.time()

    try:
        raw_res = fetcher(payload)
    except Exception as e:
        return {
            "success": False,
            "error": f"Endpoint unavailable: {str(e)}",
            "data": None
        }

    if cache_path:
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(raw_res, f, indent=2)
        except Exception:
            pass

    return {
        "success": True,
        "cached": False,
        "data": raw_res
    }


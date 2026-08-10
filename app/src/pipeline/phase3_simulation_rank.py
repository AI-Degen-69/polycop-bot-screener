import json
import os
import sys
import time
from typing import Dict, Any, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SRC_DIR = os.path.join(APP_DIR, "src")
DATA_DIR = os.path.join(APP_DIR, "data")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    from execution.copy_execution_profile import CURRENT_PROFILE
    from screener.slippage_sweep import run_slippage_sensitivity_sweep
    from pipeline.run_mock_client import parse_run_mock_response, calculate_copyable_window_share
except ModuleNotFoundError:
    from app.src.execution.copy_execution_profile import CURRENT_PROFILE
    from app.src.screener.slippage_sweep import run_slippage_sensitivity_sweep
    from app.src.pipeline.run_mock_client import parse_run_mock_response, calculate_copyable_window_share

def assign_simulated_tier(edge_retention: Optional[float], sim_pnl_10: float) -> str:
    """
    Assign Tier based on simulated edge retention performance.
    """
    if edge_retention is None or sim_pnl_10 <= 0:
        return "F-Tier / REJECT"
    if edge_retention >= 0.85:
        return "S-Tier (God-Tier Target)"
    elif edge_retention >= 0.70:
        return "A-Tier (Strong Copy Target)"
    elif edge_retention >= 0.50:
        return "B-Tier (Moderate Copy Target)"
    elif edge_retention >= 0.30:
        return "C-Tier (High Risk / Volatile)"
    else:
        return "F-Tier / REJECT"

def _carry_through_triage(target: Dict[str, Any]) -> Dict[str, Any]:
    """Everything triage already established about a wallet, passed along intact.

    Phase 3 publishes the feed the web app reads, so anything it drops here
    disappears from the page. Activity, the score breakdown and the bankroll
    analysis are all triage's work and none of them is invalidated by running a
    simulation on top, so they travel with the row rather than forcing the page
    to fetch and join two files.
    """
    return {
        "address": target.get("address"),
        "name": target.get("name"),
        "triage_copyability_score": target.get("final_score"),
        "triage_grade": target.get("grade"),
        "is_hidden_gem": target.get("is_hidden_gem"),
        "activity": target.get("activity"),
        "breakdown": target.get("breakdown"),
        "bankroll_analysis": target.get("bankroll_analysis"),
        "metrics": target.get("metrics"),
    }


def run_phase3_simulation_rank(
    targets: Optional[List[Dict[str, Any]]] = None,
    profile=None,
    fetcher=None,
    cache_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Phase 3: Simulation Rank Phase.
    Takes Phase 2 triage targets, puts them through Slippage Sensitivity Sweep,
    ranks survivors by Edge Retention, assigns Tiers from simulated performance,
    and publishes precomputed targets feed.
    """
    if profile is None:
        profile = CURRENT_PROFILE

    if targets is None:
        in_file = os.path.join(DATA_DIR, "phase2_verified_targets.json")
        if os.path.exists(in_file):
            with open(in_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            targets = data.get("verified_targets", [])
        else:
            targets = []

    simulated_results = []
    reduced_confidence = False
    fallback_reason = None

    for target in targets:
        addr = target.get("address")
        if not addr:
            continue

        try:
            sweep_out = run_slippage_sensitivity_sweep(
                wallet=addr,
                profile=profile,
                fetcher=fetcher,
                cache_dir=cache_dir
            )
            # Check if all runs failed due to endpoint unavailability
            failed_runs = [r for r in sweep_out.get("sweep_results", {}).values() if not r.get("success")]
            if failed_runs:
                reduced_confidence = True
                fallback_reason = failed_runs[0].get("error", "Endpoint unavailable")
                break
        except Exception as e:
            reduced_confidence = True
            fallback_reason = f"Endpoint unavailable: {str(e)}"
            break


        if sweep_out.get("is_rejected"):
            continue

        retention = sweep_out.get("edge_retention")
        pnl_10 = sweep_out.get("pnl_by_level", {}).get(10.0, 0.0)
        sim_tier = assign_simulated_tier(retention, pnl_10)

        # Extract per-market detail & balance miss from 10% slippage run
        res_10 = sweep_out.get("sweep_results", {}).get(10.0, {}).get("data", {})
        parsed_10 = parse_run_mock_response(res_10) if res_10 else {}
        window_share = calculate_copyable_window_share(res_10) if res_10 else None

        entry = _carry_through_triage(target)
        entry.update({
            # The tier a simulation produced, labelled as such. A reader cannot
            # tell a simulated verdict from a triage grade by looking at the
            # letter, so the provenance travels beside it rather than being
            # inferred from which fields happen to be populated.
            "verdict_source": "simulation",
            "tier": sim_tier,
            "edge_retention": round(retention, 4) if retention is not None else None,
            "simulated_copy_pnl_10": round(pnl_10, 2),
            "copyable_window_share": round(window_share, 4) if window_share is not None else None,
            "balance_miss_details": parsed_10.get("logs", []),
            "pnl_by_slippage_level": sweep_out.get("pnl_by_level"),
        })
        simulated_results.append(entry)

    # Error Fallback: if endpoint failed, fall back to triage copyability score ordering
    if reduced_confidence:
        simulated_results = []
        for target in targets:
            entry = _carry_through_triage(target)
            entry.update({
                # No simulation ran, so there is no simulated tier. The triage
                # grade is still here under its own name; presenting it as a
                # simulated verdict would be the same letter meaning something
                # weaker, which is exactly the confusion this feed must not ship.
                "verdict_source": "triage",
                "tier": None,
                "edge_retention": None,
                "simulated_copy_pnl_10": None,
                "copyable_window_share": None,
                "balance_miss_details": [],
                "pnl_by_slippage_level": None,
            })
            simulated_results.append(entry)
        simulated_results.sort(key=lambda x: x.get("triage_copyability_score", 0.0), reverse=True)
    else:
        # Rank survivors by Edge Retention descending
        simulated_results.sort(key=lambda x: (x.get("edge_retention") or 0.0, x.get("triage_copyability_score") or 0.0), reverse=True)

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "copy_execution_profile": dict(profile.as_dict(), fingerprint=profile.fingerprint),
        "reduced_confidence": reduced_confidence,
        "fallback_reason": fallback_reason,
        "total_targets_evaluated": len(targets),
        "simulated_survivors_count": len(simulated_results),
        "simulated_targets": simulated_results
    }

    out_file = os.path.join(DATA_DIR, "phase3_simulated_targets.json")
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except Exception:
        pass

    return summary

if __name__ == "__main__":
    res = run_phase3_simulation_rank()
    print(f"Phase 3 Complete: {res['simulated_survivors_count']} targets ranked.")

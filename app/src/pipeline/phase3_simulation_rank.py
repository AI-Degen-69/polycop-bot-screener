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

from execution.copy_execution_profile import CURRENT_PROFILE
from screener.simulated_copy_run import (
    calculate_copyable_window_share,
    extract_skip_reasons,
    parse_simulated_run_response,
)
from screener.score_wallets import SIM_TIER_A_MIN, SIM_TIER_B_MIN, SIM_TIER_C_MIN, SIM_TIER_S_MIN
from screener.slippage_sweep import run_slippage_sensitivity_sweep

def assign_simulated_tier(edge_retention: Optional[float], sim_pnl_10: float) -> str:
    """
    Assign Tier based on simulated edge retention performance.

    Bands come from the same constants that generate the docs (SCORING_SPEC
    "sim_tiers"), so the verdict shown on the page cannot drift from what the
    documentation says. See ADR 0002.
    """
    if edge_retention is None or sim_pnl_10 <= 0:
        return "F-Tier / REJECT"
    if edge_retention >= SIM_TIER_S_MIN:
        return "S-Tier (God-Tier Target)"
    elif edge_retention >= SIM_TIER_A_MIN:
        return "A-Tier (Strong Copy Target)"
    elif edge_retention >= SIM_TIER_B_MIN:
        return "B-Tier (Moderate Copy Target)"
    elif edge_retention >= SIM_TIER_C_MIN:
        return "C-Tier (High Risk / Volatile)"
    else:
        return "F-Tier / REJECT"

def extract_balance_miss(sweep_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The per-market record of trades the bankroll could not fund.

    Balance Miss lives on `market_stats`, one entry per market, as
    `sim_missed_amount`. The decision `logs` are a different array answering a
    different question — why a trade was filtered out, not whether the money
    ran out — so reading the miss off them yields nothing at all.

    Markets that funded everything carry a zero and are dropped here, so an
    empty list is the honest signal that nothing was missed. No captured
    response pins the market label yet, so the usual candidates are tried in
    turn rather than one being assumed.
    """
    entries = []
    for market in sweep_data.get("market_stats") or []:
        try:
            amount = float(market.get("sim_missed_amount", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if amount <= 0:
            continue
        label = (
            market.get("title")
            or market.get("market")
            or market.get("question")
            or market.get("slug")
            or "Unnamed market"
        )
        entries.append({"market": label, "amount": round(amount, 2)})
    entries.sort(key=lambda item: item["amount"], reverse=True)
    return entries


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
        "breakdown_labels": target.get("breakdown_labels"),
        "radar_labels": target.get("radar_labels"),
        "breakdown_points": target.get("breakdown_points"),
        "bankroll_analysis": target.get("bankroll_analysis"),
        "metrics": target.get("metrics"),
    }


def run_phase3_simulation_rank(
    targets: Optional[List[Dict[str, Any]]] = None,
    profile=None,
    fetcher=None,
    cache_dir: Optional[str] = None,
    endpoint_failure_threshold: int = 3
) -> Dict[str, Any]:
    """
    Phase 3: Simulation Rank Phase.
    Takes Phase 2 triage targets, puts them through Slippage Sensitivity Sweep,
    ranks survivors by Edge Retention, assigns Tiers from simulated performance,
    and publishes precomputed targets feed.

    Issue #25: a single wallet the endpoint did not answer for is rejected with
    an endpoint-failure reason (ADR 0007) while the scan continues. Only a
    sustained run of `endpoint_failure_threshold` consecutive endpoint-failure
    wallets is treated as an outage: the scan stops, the verdicts already
    computed are kept, and the unreached wallets fall back to triage ordering.
    """
    if profile is None:
        profile = CURRENT_PROFILE

    # Whether this run is the production path, decided before `targets` is
    # filled in from the Phase 2 file. Asking `targets is None` after that
    # point answers "did the file happen to be empty", not "who supplied the
    # targets", and the two diverge on exactly the run that publishes.
    publishes_feed = targets is None

    if publishes_feed:
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
    # Consecutive wallets the endpoint did not answer for (issue #25). A
    # measured rejection is not an outage signal: the endpoint answered, the
    # wallet simply failed the gate.
    consecutive_failures = 0
    unreached = []

    for index, target in enumerate(targets):
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
        except Exception as e:
            # The sweep itself raised — the endpoint did not answer for this
            # wallet, so it counts against the failure streak.
            sweep_out = None
            endpoint_failure = True
            failure_error = f"Endpoint unavailable: {str(e)}"
        else:
            # ADR 0007: a rejection caused by an unmeasured gated level is an
            # endpoint signal; a measured rejection is not.
            endpoint_failure = bool(sweep_out.get("endpoint_failure"))
            if endpoint_failure:
                failed = [r for r in sweep_out.get("sweep_results", {}).values() if not r.get("success")]
                failure_error = failed[0].get("error", "Endpoint unavailable") if failed else "Endpoint unavailable"
            else:
                failure_error = None

        if endpoint_failure:
            consecutive_failures += 1
            fallback_reason = failure_error
            # A sustained run of wallets the endpoint did not answer for is an
            # outage, not a flake: stop hammering the dead endpoint and let the
            # wallets we never reached fall back to triage ordering. The
            # verdicts already computed are kept — one transient failure no
            # longer throws a whole scan's simulation work away (issue #25).
            if consecutive_failures >= endpoint_failure_threshold:
                reduced_confidence = True
                unreached = targets[index:]
                break
        else:
            consecutive_failures = 0
            # The endpoint answered for this wallet, so whatever failure came
            # before was a flake, not an outage — carrying its error into the
            # summary would publish a fallback reason on a scan that did not
            # degrade.
            fallback_reason = None

        if sweep_out is None or sweep_out.get("is_rejected"):
            continue

        retention = sweep_out.get("edge_retention")
        pnl_10 = sweep_out.get("pnl_by_level", {}).get(10.0, 0.0)
        sim_tier = assign_simulated_tier(retention, pnl_10)

        # Extract per-market detail & balance miss from 10% slippage run
        res_10 = sweep_out.get("sweep_results", {}).get(10.0, {}).get("data", {})
        window_share = calculate_copyable_window_share(res_10) if res_10 else None

        # Verdict-side figures from the same 10% run (issue #26): the spec
        # wants Daily Green Rate and Drawdown Depth to describe the follower's
        # simulation, not the target's leaderboard lifetime, and the decision
        # log retained so a reader can see why a trade was skipped.
        sim_parsed = parse_simulated_run_response(res_10) if res_10 else None
        trading_days = sim_parsed["trading_days"] if sim_parsed else 0
        if sim_parsed is not None and trading_days > 0:
            # A rate drawn from zero days is not a rate of zero; it is nothing
            # measured (the triage side refuses the same way via MIN_OBSERVED_DAYS).
            daily_green = round((sim_parsed["winning_days"] / float(trading_days)) * 100.0, 2)
        else:
            daily_green = None
        sim_drawdown = sim_parsed["max_drawdown"] if sim_parsed else None

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
            "simulated_daily_green_rate": daily_green,
            "simulated_trading_days": trading_days,
            "simulated_max_drawdown": round(sim_drawdown, 2) if sim_drawdown is not None else None,
            "skip_reasons": extract_skip_reasons(res_10) if res_10 else [],
            "balance_miss_details": extract_balance_miss(res_10),
            "pnl_by_slippage_level": sweep_out.get("pnl_by_level"),
        })
        simulated_results.append(entry)

    # A degraded scan keeps the verdicts already computed and falls back only
    # the wallets the outage stopped us from reaching, each labelled so the
    # page can tell a simulated tier from a triage grade.
    if reduced_confidence:
        simulated_results.sort(
            key=lambda x: (x.get("edge_retention") or 0.0, x.get("triage_copyability_score") or 0.0),
            reverse=True
        )
        fallbacks = []
        for target in unreached:
            if not target.get("address"):
                continue
            entry = _carry_through_triage(target)
            entry.update({
                # No simulation ran for this wallet, so there is no simulated
                # tier. The triage grade is still here under its own name;
                # presenting it as a simulated verdict would be the same letter
                # meaning something weaker, which is exactly the confusion this
                # feed must not ship.
                "verdict_source": "triage",
                "tier": None,
                "edge_retention": None,
                "simulated_copy_pnl_10": None,
                "copyable_window_share": None,
                "simulated_daily_green_rate": None,
                "simulated_trading_days": 0,
                "simulated_max_drawdown": None,
                "skip_reasons": [],
                "balance_miss_details": [],
                "pnl_by_slippage_level": None,
            })
            fallbacks.append(entry)
        fallbacks.sort(key=lambda x: x.get("triage_copyability_score", 0.0), reverse=True)
        simulated_results.extend(fallbacks)
    else:
        # Rank survivors by Edge Retention descending
        simulated_results.sort(
            key=lambda x: (x.get("edge_retention") or 0.0, x.get("triage_copyability_score") or 0.0),
            reverse=True
        )

    # The rank a wallet holds within this scan, read off the final ordering
    # (1-based). It travels beside the tier so a reader sees both where a wallet
    # sits and why it sits there. Stamped after sorting so it always reflects
    # the ordering the feed actually ships, whichever branch produced it.
    for index, entry in enumerate(simulated_results, start=1):
        entry["scan_rank"] = index

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "copy_execution_profile": dict(profile.as_dict(), fingerprint=profile.fingerprint),
        "reduced_confidence": reduced_confidence,
        "fallback_reason": fallback_reason,
        "total_targets_evaluated": len(targets),
        "simulated_survivors_count": len(simulated_results),
        "simulated_targets": simulated_results
    }

    # The feed the web app serves is written only on the production path
    # (targets read from the Phase 2 file). Runs that were handed explicit
    # targets — every test in this repo — must not touch the live data dir;
    # an earlier version wrote unconditionally and every test-suite run
    # clobbered the feed with fixture wallets.
    if publishes_feed:
        out_file = os.path.join(DATA_DIR, "phase3_simulated_targets.json")
        # Written beside the feed and moved onto it, so a reader never sees a
        # half-written scan: the web app polls this file while scans run. A
        # failure here is raised rather than swallowed — a scan that could not
        # publish has not succeeded, and the silence of the earlier version is
        # what let a broken publish path go unnoticed through a whole day of
        # scans that looked like they had worked.
        tmp_file = out_file + ".tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            os.replace(tmp_file, out_file)
        finally:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    return summary

if __name__ == "__main__":
    res = run_phase3_simulation_rank()
    print(f"Phase 3 Complete: {res['simulated_survivors_count']} targets ranked.")

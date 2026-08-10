"""Phase 3: the scan loop, the outage degradation, and the feed publish.

The per-wallet interpretation of a sweep — the ADR 0007 classification, the
simulated tier, the verdict-side metrics and the per-cap backtest — lives
behind the Simulated Verdict seam (`screener.simulated_verdict`). This
module owns the orchestration that surrounds it: the failure streak, the
outage fallback, ranking, the cap-upgrade summary and the feed write.
"""
import json
import os
import sys
import time
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import DATA_DIR, PHASE2_FILE, PHASE3_FILE

from execution.copy_execution_profile import CURRENT_PROFILE
from screener.simulated_verdict import triage_fallback_verdict, verdict_for_wallet
from screener.slippage_sweep import DEFAULT_CAP_LEVELS


# Ordinal for comparing tiers against each other, so the summary can say how
# many wallets would *upgrade* under a wider cap. Higher is better; a tier the
# pipeline never produced still gets a rank of zero rather than a crash.
_TIER_RANK = {"S": 5, "A": 4, "B": 3, "C": 2, "F": 1}


def _tier_rank(tier: Optional[str]) -> int:
    if not tier:
        return 0
    # "S-Tier (God-Tier Target)" -> "S-Tier" -> "S". The dict keys are the
    # single letters, not the full rank label.
    return _TIER_RANK.get(tier.split(" ")[0][:1], 0)


def summarize_cap_upgrades(
    results: List[Dict[str, Any]], baseline_cap: float, cap_levels: List[float]
) -> (List[Dict[str, Any]], int):
    """How many backtested wallets would earn a better tier at each wider cap.

    A wallet upgrades when the tier its per-cap backtest produced at a level
    outranks the tier of its headline verdict (the cap the scan actually runs
    under). Wallets whose backtest errored, and triage fallbacks with no
    backtest at all, are not counted anywhere — an unknown is not a zero (ADR
    0007), and the `backtested` denominator says how many wallets the count
    was drawn from.

    Every level above the baseline is reported, a zero count included: the
    header's question is "how many upgrade at each cap", and an answer of
    zero is an answer. With nothing backtested there is no answer at all, so
    the list stays empty rather than claiming zeros.

    Returns a list of `{"cap_usd", "upgrades"}` entries for the levels above
    the baseline cap, and the number of wallets whose backtests contributed.
    """
    counts = {}
    backtested = 0
    for entry in results:
        sweep = entry.get("cap_sweep") or []
        if not sweep or sweep[0].get("error"):
            continue
        backtested += 1
        headline_rank = _tier_rank(entry.get("tier"))
        for level in sweep:
            cap = level.get("cap_usd")
            if cap is None or cap <= baseline_cap:
                continue
            if _tier_rank(level.get("tier")) > headline_rank:
                counts[cap] = counts.get(cap, 0) + 1
    if backtested == 0:
        return [], 0
    upgrades = [
        {"cap_usd": cap, "upgrades": counts.get(cap, 0)}
        for cap in sorted(cap for cap in cap_levels if cap > baseline_cap)
    ]
    return upgrades, backtested


def run_phase3_simulation_rank(
    targets: Optional[List[Dict[str, Any]]] = None,
    profile=None,
    fetcher=None,
    cache_dir: Optional[str] = None,
    endpoint_failure_threshold: int = 3,
    cap_levels: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Phase 3: Simulation Rank Phase.
    Takes Phase 2 triage targets, puts them through the Simulated Verdict seam
    (slippage sweep + tier + verdict metrics + per-cap backtest), ranks
    survivors by Edge Retention, and publishes the precomputed targets feed.

    Issue #25: a single wallet the endpoint did not answer for is rejected with
    an endpoint-failure reason (ADR 0007) while the scan continues. Only a
    sustained run of `endpoint_failure_threshold` consecutive endpoint-failure
    wallets is treated as an outage: the scan stops, the verdicts already
    computed are kept, and the unreached wallets fall back to triage ordering.

    Each survivor is also backtested under rising per-position caps
    (`cap_levels`), which adds two simulation jobs per cap level per wallet
    (the two gated slippage levels) on top of the headline sweep's four —
    about three times the uncached load of a scan without it. The results are
    cached per derived profile fingerprint, so rescans are cheap.
    """
    if profile is None:
        profile = CURRENT_PROFILE
    if cap_levels is None:
        cap_levels = DEFAULT_CAP_LEVELS

    # Whether this run is the production path, decided before `targets` is
    # filled in from the Phase 2 file. Asking `targets is None` after that
    # point answers "did the file happen to be empty", not "who supplied the
    # targets", and the two diverge on exactly the run that publishes.
    publishes_feed = targets is None

    if publishes_feed:
        in_file = os.path.join(DATA_DIR, PHASE2_FILE)
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

        # The seam answers "what did this wallet's sweep mean" — failure
        # classification included. The loop only keeps the streak that
        # decides whether the scan degrades.
        verdict = verdict_for_wallet(
            wallet=addr,
            target=target,
            profile=profile,
            fetcher=fetcher,
            cache_dir=cache_dir,
            cap_levels=cap_levels,
        )

        if verdict.endpoint_failure:
            consecutive_failures += 1
            fallback_reason = verdict.failure_error
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

        # A measured rejection and an endpoint failure both produce no row;
        # the verdict carries the classification, the loop the streak.
        if verdict.entry is None:
            continue

        simulated_results.append(verdict.entry)

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
            fallbacks.append(triage_fallback_verdict(target))
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

    # How many wallets would upgrade tier under a wider per-position cap — the
    # answer the header summary asks for. The baseline is the binding cap the
    # headline verdicts were computed under, not the stated per-token field:
    # if the bankroll-share rule binds lower, the headline was never the $5
    # cap in the first place.
    cap_upgrades, cap_backtested = summarize_cap_upgrades(
        simulated_results, profile.max_single_position_usd, cap_levels
    )

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "copy_execution_profile": dict(profile.as_dict(), fingerprint=profile.fingerprint),
        "reduced_confidence": reduced_confidence,
        "fallback_reason": fallback_reason,
        "total_targets_evaluated": len(targets),
        "simulated_survivors_count": len(simulated_results),
        "cap_sweep_levels": list(cap_levels),
        "cap_sweep_baseline_cap": profile.max_single_position_usd,
        "cap_sweep_backtested": cap_backtested,
        "cap_sweep_upgrades": cap_upgrades,
        "simulated_targets": simulated_results
    }

    # The feed the web app serves is written only on the production path
    # (targets read from the Phase 2 file). Runs that were handed explicit
    # targets — every test in this repo — must not touch the live data dir;
    # an earlier version wrote unconditionally and every test-suite run
    # clobbered the feed with fixture wallets.
    if publishes_feed:
        out_file = os.path.join(DATA_DIR, PHASE3_FILE)
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

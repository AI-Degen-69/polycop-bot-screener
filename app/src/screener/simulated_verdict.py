"""The Simulated Verdict: what a sweep result means, in one place.

The interpretation of a Slippage Sensitivity Sweep's outcome for a single
wallet — the ADR 0007 endpoint-failure classification, the simulated tier,
the verdict-side metrics and the per-cap backtest — lives behind this
module's seam, so the scan loop, the web endpoint and the tests all cross
one interface instead of each re-implementing the interpretation.

This is the verdict side only (ADR 0002): triage grades stay
leaderboard-fed and keep working when the endpoint is down. The concept is
the "Simulated Verdict" term in CONTEXT.md; the module is named after it.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from execution.copy_execution_profile import CURRENT_PROFILE
from screener.simulated_copy_run import (
    calculate_copyable_window_share,
    extract_skip_reasons,
    parse_simulated_run_response,
)
from screener.score_wallets import (
    SIM_TIER_A_MIN,
    SIM_TIER_B_MIN,
    SIM_TIER_C_MIN,
    SIM_TIER_S_MIN,
)
from screener.slippage_sweep import (
    DEFAULT_CAP_LEVELS,
    run_cap_sensitivity_sweep,
    run_slippage_sensitivity_sweep,
)


@dataclass
class Verdict:
    """What the seam concluded about one wallet's sweep.

    `endpoint_failure` is True when the endpoint did not answer for this
    wallet (ADR 0007); the scan loop counts it toward the outage streak and
    reads `failure_error` for the fallback reason. `entry` is the feed row
    to publish, or None when the wallet produced no row — an endpoint
    failure and a measured rejection both yield None, and only the flag
    says which.
    """

    endpoint_failure: bool
    failure_error: Optional[str]
    entry: Optional[Dict[str, Any]]


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


def _assign_cap_sweep_tiers(cap_sweep: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stamp the simulated tier verdict on each level of a cap backtest.

    Shared by the scan (which backtests every survivor) and the web endpoint
    (which backtests one wallet at caller-chosen caps), so a level's tier can
    never be assigned two ways.
    """
    for level in cap_sweep:
        level["tier"] = assign_simulated_tier(
            level["edge_retention"], level["simulated_copy_pnl_10"] or 0.0
        )
    return cap_sweep


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


def triage_fallback_verdict(target: Dict[str, Any]) -> Dict[str, Any]:
    """The row for a wallet the outage stopped us from simulating.

    No simulation ran for this wallet, so there is no simulated tier. The
    triage grade is still here under its own name; presenting it as a
    simulated verdict would be the same letter meaning something weaker, which
    is exactly the confusion this feed must not ship. Absence semantics follow
    ADR 0007: nothing measured is None, not a fabricated zero.
    """
    entry = _carry_through_triage(target)
    entry.update({
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
        "cap_sweep": [],
    })
    return entry


def backtest_wallet_at_caps(
    wallet: str,
    cap_levels: List[float],
    profile=None,
    fetcher=None,
    cache_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Backtest one wallet at caller-chosen per-position caps, on demand.

    This is the single-wallet counterpart of the scan's per-cap backtest, used
    by the web endpoint behind the custom-caps control. It runs the same
    sweep with the same rejection semantics (ADR 0007) and stamps the same
    simulated tier per level. Each cap is derived with `with_position_cap`, so
    the profile defaults — and the cache fingerprints of every already-computed
    result — are left untouched.
    """
    if profile is None:
        profile = CURRENT_PROFILE
    cap_sweep = run_cap_sensitivity_sweep(
        wallet=wallet,
        profile=profile,
        cap_levels=cap_levels,
        fetcher=fetcher,
        cache_dir=cache_dir,
    )
    return _assign_cap_sweep_tiers(cap_sweep)


def verdict_for_wallet(
    wallet: str,
    target: Dict[str, Any],
    profile=None,
    fetcher=None,
    cache_dir: Optional[str] = None,
    cap_levels: Optional[List[float]] = None,
) -> Verdict:
    """Interpret one wallet's sweep: the classification and the row to publish.

    Runs the Slippage Sensitivity Sweep, classifies the outcome (ADR 0007: a
    rejection caused by an unmeasured gated level is an endpoint signal; a
    measured rejection is not), and on success stamps the simulated tier and
    every verdict-side metric — window share, daily green rate, drawdown,
    skip reasons, balance miss, and the per-cap backtest — into the feed row.
    The cap backtest is extra analysis on top of the headline verdict: an
    unexpected failure there is recorded, never allowed to reject a wallet
    whose headline simulation already succeeded.

    Returns a Verdict carrying the classification and, when the wallet
    produced a row, the row itself. The scan loop owns the streak arithmetic;
    what a sweep result *means* lives here.
    """
    if profile is None:
        profile = CURRENT_PROFILE
    if cap_levels is None:
        cap_levels = DEFAULT_CAP_LEVELS

    try:
        sweep_out = run_slippage_sensitivity_sweep(
            wallet=wallet,
            profile=profile,
            fetcher=fetcher,
            cache_dir=cache_dir,
        )
    except Exception as e:
        # The sweep itself raised — the endpoint did not answer for this
        # wallet, so it counts against the failure streak.
        return Verdict(
            endpoint_failure=True,
            failure_error=f"Endpoint unavailable: {str(e)}",
            entry=None,
        )

    if sweep_out.get("endpoint_failure"):
        failed = [r for r in sweep_out.get("sweep_results", {}).values() if not r.get("success")]
        return Verdict(
            endpoint_failure=True,
            failure_error=failed[0].get("error", "Endpoint unavailable") if failed else "Endpoint unavailable",
            entry=None,
        )

    # A measured rejection (the endpoint answered, the wallet failed the gate)
    # produces no row — ADR 0007 keeps it distinct from an endpoint failure.
    if sweep_out.get("is_rejected"):
        return Verdict(endpoint_failure=False, failure_error=None, entry=None)

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

    # Backtest the wallet under rising per-position caps (5/10/15/20), the
    # same way the slippage sweep backtests it under rising friction. Each
    # level replays the wallet with the cap that actually binds and
    # inherits the gated-level rejection semantics. A failure here is
    # recorded, never allowed to reject a wallet whose headline verdict
    # already succeeded — the cap backtest is extra analysis on top.
    cap_sweep = []
    try:
        cap_sweep = _assign_cap_sweep_tiers(run_cap_sensitivity_sweep(
            wallet=wallet,
            profile=profile,
            cap_levels=cap_levels,
            fetcher=fetcher,
            cache_dir=cache_dir,
        ))
    except Exception as e:
        cap_sweep = [{"error": str(e)}]

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
        "cap_sweep": cap_sweep,
    })
    return Verdict(endpoint_failure=False, failure_error=None, entry=entry)

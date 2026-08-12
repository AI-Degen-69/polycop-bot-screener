#!/usr/bin/env python3
import json
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import DATA_DIR, PHASE1_FILE, PHASE2_FILE, SCANNED_WALLETS_FILE

from execution.copy_execution_profile import CURRENT_PROFILE
from pipeline.first_party_adapter import first_party_activity, to_engine_metrics
from screener.score_wallets import (
    GEM_SITE_SCORE_MAX,
    TIER_A_MIN,
    TIER_S_MIN,
    calculate_bankroll_optimized_score,
    calculate_edge_retention,
)
from screener.activity import summarize_buckets

def _round_or_none(value, digits=2):
    """A figure rounded for the record, or None when it was never measured.

    `round(None, 2)` raises, so the record writer needs the same
    absent-stays-absent discipline the engine uses (ADR 0007): a figure the
    source could not measure is published as null, not as a rounded zero.
    """
    return None if value is None else round(value, digits)


def run_phase2_filter(profile=CURRENT_PROFILE, in_file=None, out_file=None,
                      record_file=None):
    """
    Phase 2: scores the wallets Phase 1 discovered, from the scanner's
    first-party measurements, into app/data/phase2_verified_targets.json.

    Phase 1 supplies candidate addresses and nothing else; every figure the
    100-point audit reads is derived from the wallet's own Polymarket fills
    (ADR 0012). An address the scanner has not measured yet is reported as
    pending, not rejected - the absence of a measurement is not evidence about
    a wallet, and rejecting on it would quietly turn scan coverage into a
    verdict.

    Triage is only valid for one Copy Execution Profile, so the profile is stated once
    here and passed down rather than restated as literals per call site.

    The three paths default to the cached datasets and are overridable so the
    whole phase can be exercised against a fixture, which is the only way to
    catch a parameter that scores well because nothing ever measured it.
    """
    in_file = in_file or os.path.join(DATA_DIR, PHASE1_FILE)
    out_file = out_file or os.path.join(DATA_DIR, PHASE2_FILE)
    record_file = record_file or os.path.join(DATA_DIR, SCANNED_WALLETS_FILE)

    if not os.path.exists(in_file):
        print(f"Error: Phase 1 file {in_file} not found. Run phase1_scrape_leaderboard.py first.")
        return None

    with open(in_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = {}
    if os.path.exists(record_file):
        with open(record_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            records = {
                str(key).lower(): value
                for key, value in loaded.items() if isinstance(value, dict)
            }
    else:
        print(f"Warning: no scanner record at {record_file} - nothing can be scored yet.")

    raw_profiles = data.get("profiles", [])
    print(f"=== PHASE 2: SCORING {len(raw_profiles)} DISCOVERED ADDRESSES ===")

    verified_targets = []
    rejected_count = 0
    pending_count = 0
    stale_profile_count = 0
    s_tier = []
    a_tier = []
    gems = []

    for idx, p in enumerate(raw_profiles, start=1):
        addr = p.get("address") or p.get("wallet") or p.get("user")
        if not addr:
            continue

        record = records.get(str(addr).lower())
        if record is None:
            # Never measured. Pending is not a rejection: this wallet has not
            # been judged at all, and counting it as a reject would report scan
            # coverage as a verdict about the trader.
            pending_count += 1
            continue
        if record.get("profile_fingerprint") != profile.fingerprint:
            # Measured under execution settings that no longer exist, so its
            # copy replay answers a question about a different bot. Held for
            # re-measurement rather than scored under a label it never ran with.
            stale_profile_count += 1
            continue

        # Measured before scoring, not after. Each of these is None when the
        # source data will not support it, and the engine scores None as nothing,
        # so an unmeasured wallet ranks below a measured poor one.
        meas = to_engine_metrics(record, profile.slippage_pct)
        raw_metrics = meas["raw_metrics"]
        sim_summary = meas["sim_summary"]
        green_rate = meas["green_rate"]
        observed_days = meas["observed_days"]
        drawdown_depth = meas["drawdown_depth"]
        edge_to_friction = meas["edge_to_friction"]

        audit_res = calculate_bankroll_optimized_score(raw_metrics, profile=profile)

        if audit_res["rejection_reasons"]:
            rejected_count += 1
            continue

        score = audit_res["final_score"]
        # "Rated highly" is defined by the recalibrated tier bands (ADR 0005):
        # a wallet the screen grades A-Tier or better while the site rates it
        # poorly. The old constant 80.0 is gone so the gem definition cannot
        # silently diverge from the tier floors.
        # The aggregator's opinion is the only thing Phase 1 still carries from
        # it, kept for exactly one purpose: a Hidden Gem is defined by the two
        # opinions disagreeing, so one of them has to be theirs. It reaches no
        # gate and no scored parameter.
        site_score = p.get("aggregator_opinion")
        # An unmeasured site score cannot disagree with the screen, and Hidden Gem
        # is defined as that disagreement.
        is_gem = site_score is not None and site_score < GEM_SITE_SCORE_MAX and score >= TIER_A_MIN
        raw_name = p.get("name") or p.get("username")
        name_str = str(raw_name) if raw_name else f"PolyCop_Trader ({addr[:6]}...{addr[-4:]})"

        target_entry = {
            "address": addr,
            "name": name_str,
            "polycop_leaderboard_index": idx,
            "final_score": score,
            "grade": audit_res["grade"],
            "is_hidden_gem": is_gem,
            "simulation_summary": sim_summary,
            "metrics": {
                "aggregator_opinion": site_score,
                "actual_pnl": _round_or_none(raw_metrics["actual_pnl"]),
                "copy_pnl": _round_or_none(raw_metrics["copy_pnl"]),
                "days_win_rate": _round_or_none(green_rate),
                "observed_days": observed_days,
                "drawdown_depth": _round_or_none(drawdown_depth, 4),
                "edge_to_friction": _round_or_none(edge_to_friction, 4),
                "hedged_pct": _round_or_none(raw_metrics["hedged_pct"]),
                "pl_ratio": _round_or_none(raw_metrics["pl_ratio"]),
                "pnl_vol_ratio": _round_or_none(raw_metrics["pnl_vol_ratio"]),
                "avg_invest": _round_or_none(raw_metrics["avg_invest"]),
                "markets": raw_metrics["markets"],
                "r20_pnl": _round_or_none(raw_metrics["r20_pnl"]),
                "r20_slip": _round_or_none(raw_metrics["r20_slip"]),
                # How much of this wallet's history the measurement covers, so
                # a reader can see the scope a figure was measured over rather
                # than comparing four months against six hours.
                "coverage_days": record.get("coverage_days"),
                "history_truncated": record.get("history_truncated"),
                # The share of this wallet's fills at 3c/97c extremes. It is
                # ADR 0012's headline evidence in one number: the aggregator's
                # top-ranked wallet bought at a median 0.999, where the most a
                # fill can gain is 0.1%. Displayed, never gated - a wallet can
                # have an innocent reason to trade a near-certainty.
                "extreme_price_share": record.get("extreme_price_share"),
            },
            "annotations": meas["annotations"],
            "activity": first_party_activity(record),
            "breakdown": audit_res["breakdown"],
            "breakdown_labels": audit_res["breakdown_labels"],
            "radar_labels": audit_res["radar_labels"],
            "breakdown_points": audit_res["breakdown_points"],
            "bankroll_analysis": audit_res["bankroll_analysis"]
        }


        verified_targets.append(target_entry)
        if score >= TIER_S_MIN:
            s_tier.append(target_entry)
        elif score >= TIER_A_MIN:
            a_tier.append(target_entry)
        if is_gem:
            gems.append(target_entry)

    # Sort descending by final score
    verified_targets.sort(key=lambda x: x["final_score"], reverse=True)

    summary_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        # A score is valid only for one Copy Execution Profile, so the file states
        # which one produced it rather than leaving a later reader to guess.
        "copy_execution_profile": dict(profile.as_dict(), fingerprint=profile.fingerprint),
        "total_scraped_profiles": len(raw_profiles),
        "rejected_disqualified_count": rejected_count,
        # Reported apart from the rejects, because these wallets were not
        # judged. Folding them in would overstate how much the screen has
        # actually decided.
        "pending_measurement_count": pending_count,
        "stale_profile_count": stale_profile_count,
        "total_verified_targets": len(verified_targets),
        "s_tier_count": len(s_tier),
        "a_tier_count": len(a_tier),
        "hidden_gems_count": len(gems),
        "activity_buckets": summarize_buckets([t["activity"] for t in verified_targets]),
        "verified_targets": verified_targets
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    print(f"\n=== PHASE 2 COMPLETE ===")
    print(f"Total Discovered Addresses: {len(raw_profiles)}")
    print(f"Pending First-Party Measurement: {pending_count}")
    print(f"Measured Under An Older Profile: {stale_profile_count}")
    print(f"Disqualified Rejects: {rejected_count}")
    print(f"Verified PASS Targets: {len(verified_targets)}")
    print(f"  |-- S-Tier (>= {TIER_S_MIN:.0f} Pts): {len(s_tier)}")
    print(f"  |-- A-Tier ({TIER_A_MIN:.0f}-{TIER_S_MIN - 1:.0f} Pts): {len(a_tier)}")
    print(f"  +-- Hidden Gems: {len(gems)}")
    print(f"Activity buckets: {summary_data['activity_buckets']}")
    print(f"Saved verified feed to: {out_file}")
    return out_file

if __name__ == "__main__":
    run_phase2_filter()

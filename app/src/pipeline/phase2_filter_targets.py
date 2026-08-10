#!/usr/bin/env python3
import json
import time
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# SCRIPT_DIR is app/src/pipeline -> APP_DIR is app/
APP_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SRC_DIR = os.path.join(APP_DIR, "src")
DATA_DIR = os.path.join(APP_DIR, "data")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from execution.copy_execution_profile import CURRENT_PROFILE
from pipeline.leaderboard_adapter import to_engine_metrics
from screener.score_wallets import (
    GEM_SITE_SCORE_MAX,
    TIER_A_MIN,
    TIER_S_MIN,
    calculate_bankroll_optimized_score,
    calculate_edge_retention,
)
from screener.activity import compute_activity, parse_timestamp, summarize_buckets

def run_phase2_filter(profile=CURRENT_PROFILE, in_file=None, out_file=None):
    """
    Phase 2: Takes raw scraped profiles from app/data/phase1_scraped_wallets.json,
    runs the 100-Point Audit Engine (score_wallets.py), and outputs app/data/phase2_verified_targets.json.

    Triage is only valid for one Copy Execution Profile, so the profile is stated once
    here and passed down rather than restated as literals per call site.

    The two paths default to the cached dataset and are overridable so the whole
    phase can be exercised against a fixture, which is the only way to catch a
    parameter that scores well because nothing ever measured it.
    """
    in_file = in_file or os.path.join(DATA_DIR, "phase1_scraped_wallets.json")
    out_file = out_file or os.path.join(DATA_DIR, "phase2_verified_targets.json")

    if not os.path.exists(in_file):
        print(f"Error: Phase 1 file {in_file} not found. Run phase1_scrape_leaderboard.py first.")
        return None

    with open(in_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_profiles = data.get("profiles", [])
    print(f"=== PHASE 2: FILTERING & SCORING {len(raw_profiles)} PROFILES ===")

    # Age recency against the scrape instant, not against read time, so a
    # cached dataset never claims a trader went quiet while it sat on disk.
    raw_ts = data.get("timestamp")
    scrape_now = parse_timestamp(raw_ts)
    if raw_ts and scrape_now is None:
        raise ValueError(f"Unparseable timestamp in Phase 1 scraped data: '{raw_ts}'")

    verified_targets = []
    rejected_count = 0
    s_tier = []
    a_tier = []
    gems = []

    for idx, p in enumerate(raw_profiles, start=1):
        addr = p.get("address") or p.get("wallet") or p.get("user")
        if not addr:
            continue

        # Measured before scoring, not after. Each of these is None when the
        # source data will not support it, and the engine scores None as nothing,
        # so an unmeasured wallet ranks below a measured poor one.
        meas = to_engine_metrics(p, profile.slippage_pct)
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
        is_gem = raw_metrics["polycop_site_score"] < GEM_SITE_SCORE_MAX and score >= TIER_A_MIN
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
                "polycop_site_score": raw_metrics["polycop_site_score"],
                "actual_pnl": round(raw_metrics["actual_pnl"], 2),
                "copy_pnl": round(raw_metrics["copy_pnl"], 2),
                "days_win_rate": round(green_rate, 2) if green_rate is not None else None,
                "observed_days": observed_days,
                "drawdown_depth": round(drawdown_depth, 4) if drawdown_depth is not None else None,
                "edge_to_friction": round(edge_to_friction, 4) if edge_to_friction is not None else None,
                "hedged_pct": round(raw_metrics["hedged_pct"], 2),
                "r20_win_rate": round(raw_metrics["r20_win_rate"], 2),
                "pl_ratio": round(raw_metrics["pl_ratio"], 2),
                "pnl_vol_ratio": round(raw_metrics["pnl_vol_ratio"], 2),
                "avg_invest": round(raw_metrics["avg_invest"], 2),
                "markets": raw_metrics["markets"],
                "r20_pnl": round(raw_metrics["r20_pnl"], 2),
                "r20_slip": round(raw_metrics["r20_slip"], 2) if raw_metrics["r20_slip"] is not None else None,
                "buy_price": round(raw_metrics["buy_price"], 4)
            },
            "activity": compute_activity(p, now=scrape_now),
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
    print(f"Total Scraped Profiles Evaluated: {len(raw_profiles)}")
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

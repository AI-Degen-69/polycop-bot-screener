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

from screener.score_wallets import calculate_bankroll_optimized_score
from screener.activity import compute_activity, parse_timestamp, summarize_buckets

def run_phase2_filter():
    """
    Phase 2: Takes raw scraped profiles from app/data/phase1_scraped_wallets.json,
    runs the 100-Point Audit Engine (score_wallets.py), and outputs app/data/phase2_verified_targets.json.
    """
    in_file = os.path.join(DATA_DIR, "phase1_scraped_wallets.json")
    out_file = os.path.join(DATA_DIR, "phase2_verified_targets.json")

    if not os.path.exists(in_file):
        print(f"Error: Phase 1 file {in_file} not found. Run phase1_scrape_leaderboard.py first.")
        return None

    with open(in_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_profiles = data.get("profiles", [])
    print(f"=== PHASE 2: FILTERING & SCORING {len(raw_profiles)} PROFILES ===")

    # Age recency against the scrape instant, not against read time, so a
    # cached dataset never claims a trader went quiet while it sat on disk.
    scrape_now = parse_timestamp(data.get("timestamp"))

    verified_targets = []
    rejected_count = 0
    s_tier = []
    a_tier = []
    gems = []

    for idx, p in enumerate(raw_profiles, start=1):
        addr = p.get("address") or p.get("wallet") or p.get("user")
        if not addr:
            continue

        raw_metrics = {
            "actual_pnl": float(p.get("actual_pnl", p.get("pnl", 0.0))),
            "copy_pnl": float(p.get("copy_backtest_pnl", p.get("copy_pnl", -1.0))),
            "slippage": float(p.get("slippage", 0.0)),
            "hedged_pct": float(p.get("hedged_pct", p.get("hedged_percentage", 0.0))),
            "pl_ratio": float(p.get("avg_profit_loss_ratio", p.get("pl_ratio", 0.0))),
            "days_win_rate": float(p.get("daily_green_rate", p.get("win_rate", p.get("days_win_rate", 0.0)))),
            "r20_win_rate": float(p.get("r20_wr", p.get("recent_20_win_rate", p.get("r20_win_rate", 0.0)))),
            "r20_pnl": float(p.get("r20_pnl", p.get("recent_20_pnl", 0.0))),
            "r20_slip": float(p.get("r20_slip", p.get("recent_20_slippage", 0.0))),
            "pnl_vol_ratio": float(p.get("roi", p.get("pnl_to_volume_ratio", p.get("pnl_vol_ratio", 0.0)))),
            "avg_invest": float(p.get("avg_invest", 0.0)),
            "markets": int(p.get("markets_traded", p.get("markets", 0))),
            "polycop_site_score": float(p.get("polycop_site_score", p.get("score", 0.0))),
            "buy_price": float(p.get("buy_price", p.get("avg_buy_price", 0.0)))
        }

        audit_res = calculate_bankroll_optimized_score(raw_metrics, user_capital=100.0)

        if audit_res["rejection_reasons"]:
            rejected_count += 1
            continue

        score = audit_res["final_score"]
        is_gem = raw_metrics["polycop_site_score"] < 75 and score >= 80.0
        raw_name = p.get("name") or p.get("username")
        name_str = str(raw_name) if raw_name else f"PolyCop_Trader ({addr[:6]}...{addr[-4:]})"

        target_entry = {
            "address": addr,
            "name": name_str,
            "polycop_leaderboard_index": idx,
            "final_score": score,
            "grade": audit_res["grade"],
            "is_hidden_gem": is_gem,
            "metrics": {
                "polycop_site_score": raw_metrics["polycop_site_score"],
                "actual_pnl": round(raw_metrics["actual_pnl"], 2),
                "copy_pnl": round(raw_metrics["copy_pnl"], 2),
                "days_win_rate": round(raw_metrics["days_win_rate"], 2),
                "hedged_pct": round(raw_metrics["hedged_pct"], 2),
                "r20_win_rate": round(raw_metrics["r20_win_rate"], 2),
                "pl_ratio": round(raw_metrics["pl_ratio"], 2),
                "pnl_vol_ratio": round(raw_metrics["pnl_vol_ratio"], 2),
                "avg_invest": round(raw_metrics["avg_invest"], 2),
                "markets": raw_metrics["markets"],
                "r20_pnl": round(raw_metrics["r20_pnl"], 2),
                "r20_slip": round(raw_metrics["r20_slip"], 2),
                "buy_price": round(raw_metrics["buy_price"], 4)
            },
            "activity": compute_activity(p, now=scrape_now),
            "breakdown": audit_res["breakdown"],
            "bankroll_analysis": audit_res["bankroll_analysis"]
        }

        verified_targets.append(target_entry)
        if score >= 90.0:
            s_tier.append(target_entry)
        elif score >= 80.0:
            a_tier.append(target_entry)
        if is_gem:
            gems.append(target_entry)

    # Sort descending by final score
    verified_targets.sort(key=lambda x: x["final_score"], reverse=True)

    summary_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
    print(f"  |-- S-Tier (>= 90 Pts): {len(s_tier)}")
    print(f"  |-- A-Tier (80-89 Pts): {len(a_tier)}")
    print(f"  +-- Hidden Gems: {len(gems)}")
    print(f"Activity buckets: {summary_data['activity_buckets']}")
    print(f"Saved verified feed to: {out_file}")
    return out_file

if __name__ == "__main__":
    run_phase2_filter()

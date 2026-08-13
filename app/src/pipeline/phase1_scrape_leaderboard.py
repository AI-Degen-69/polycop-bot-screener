#!/usr/bin/env python3
import urllib.request
import json
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import DATA_DIR, PHASE1_FILE

# The aggregator's own score, kept under a name that says whose opinion it is.
# It reaches no gate and no scored parameter; its only consumer is the Hidden
# Gem comparison, which is defined by the two opinions disagreeing.
AGGREGATOR_OPINION_KEY = "aggregator_opinion"


def _keep_address_only(profile, aggregator_score):
    """One discovered candidate, stripped to what this project will trust.

    The ADR 0012 boundary, in code. The leaderboard returns a full profile of
    precomputed metrics - `actual_pnl`, `copy_backtest_pnl`, `hedged_pct`,
    `r20_wr`, `daily_stats_json` and their siblings - and this project measured
    that ranking to be anti-correlated with copyability: its 100/100 wallet buys
    at a median price of 0.999 for a maximum gain of 0.1% per fill.

    So the address survives and the judgments do not. Dropping them here rather
    than ignoring them downstream is what makes the rule checkable: a field that
    is never written cannot be read back by accident three refactors later.
    """
    address = profile.get("address") or profile.get("wallet") or profile.get("user")
    if not address:
        return None
    name = profile.get("name") or profile.get("username") or profile.get("pseudonym")
    kept = {"address": address}
    if name:
        kept["name"] = name
    if aggregator_score is not None:
        kept[AGGREGATOR_OPINION_KEY] = aggregator_score
    return kept


def fetch_and_scrape_leaderboard(min_score=None):
    """
    Phase 1: Paginate through all pages of PolyCop leaderboard API and scrape raw profiles.

    No site-score pre-filter by default. The screen exists because the site's own
    score optimises for something other than copyability, and a Hidden Gem is by
    definition a wallet the two disagree about — discarding low-scoring wallets
    here would make those unfindable. The engine keeps its own sanity floor.

    `min_score` remains available for a deliberately narrowed scrape; leaving it
    unset keeps every profile.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    out_file = os.path.join(DATA_DIR, PHASE1_FILE)
    
    scope = "every profile" if min_score is None else f"PolyCop Score > {min_score}"
    print(f"=== PHASE 1: SCRAPING POLYCOP LEADERBOARD ({scope}) ===")
    
    page = 1
    page_size = 100
    all_profiles = []
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    while True:
        url = f"https://polycop.fun/api/leaderboard?page={page}&page_size={page_size}&full=1"
        print(f"Fetching leaderboard page {page}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status != 200:
                    print(f"Failed to fetch page {page}. Status: {response.status}")
                    break
                data = json.loads(response.read().decode('utf-8'))
                
                profiles = data.get("data", [])
                if not profiles:
                    print(f"No profiles found on page {page}. Ending pagination.")
                    break
                
                for p in profiles:
                    polycop_score = float(p.get("score", p.get("polycop_score", 0.0)))
                    if min_score is not None and polycop_score <= min_score:
                        continue
                    kept = _keep_address_only(p, polycop_score)
                    if kept:
                        all_profiles.append(kept)

                print(f"Page {page}: Fetched {len(profiles)} profiles. Total kept ({scope}): {len(all_profiles)}")
                
                meta = data.get("meta", {})
                total_pages = meta.get("total_pages")
                if total_pages and page >= total_pages:
                    print(f"Reached last page ({total_pages}). Ending pagination.")
                    break
                
                page += 1
                time.sleep(0.1)
                
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break

    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_scraped_profiles": len(all_profiles),
        "min_score_filter": min_score,
        "profiles": all_profiles
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"\n=== PHASE 1 COMPLETE ===")
    print(f"Total Scraped Profiles ({scope}): {len(all_profiles)}")
    print(f"Saved raw scraped dataset to: {out_file}")
    return out_file

if __name__ == "__main__":
    fetch_and_scrape_leaderboard()

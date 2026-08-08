#!/usr/bin/env python3
import urllib.request
import json
import time
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# SCRIPT_DIR is app/src/pipeline -> APP_DIR is app/
APP_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
DATA_DIR = os.path.join(APP_DIR, "data")

def fetch_and_scrape_leaderboard(min_score=60.0):
    """
    Phase 1: Paginate through all pages of PolyCop leaderboard API and scrape raw profiles.
    Filters for raw profiles with PolyCop Site Score > 60.0. Saves to app/data/phase1_scraped_wallets.json.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    out_file = os.path.join(DATA_DIR, "phase1_scraped_wallets.json")
    
    print(f"=== PHASE 1: SCRAPING POLYCOP LEADERBOARD (PolyCop Score > {min_score}) ===")
    
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
                
                # Filter for profiles where PolyCop site score > min_score
                for p in profiles:
                    polycop_score = float(p.get("score", p.get("polycop_score", 0.0)))
                    if polycop_score > min_score:
                        p["polycop_site_score"] = polycop_score
                        all_profiles.append(p)

                print(f"Page {page}: Fetched {len(profiles)} profiles. Total profiles with score > {min_score}: {len(all_profiles)}")
                
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
    print(f"Total Scraped Profiles (Score > {min_score}): {len(all_profiles)}")
    print(f"Saved raw scraped dataset to: {out_file}")
    return out_file

if __name__ == "__main__":
    fetch_and_scrape_leaderboard(60.0)

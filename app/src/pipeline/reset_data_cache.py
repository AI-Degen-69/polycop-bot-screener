#!/usr/bin/env python3
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# SCRIPT_DIR is app/src/pipeline -> APP_DIR is app/
APP_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
DATA_DIR = os.path.join(APP_DIR, "data")

FILES_TO_REMOVE = [
    os.path.join(DATA_DIR, "phase1_scraped_wallets.json"),
    os.path.join(DATA_DIR, "phase2_verified_targets.json")
]

def reset_data_cache():
    removed = []
    for filepath in FILES_TO_REMOVE:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                removed.append(os.path.basename(filepath))
            except Exception as e:
                print(f"Error removing {filepath}: {e}")
    
    if removed:
        print(f"=== DATA CACHE RESET COMPLETE ===")
        print(f"Successfully deleted cached dataset files: {', '.join(removed)}")
    else:
        print("=== NO CACHED DATASETS FOUND ===")
        print("Workspace data cache is already clean.")

if __name__ == "__main__":
    reset_data_cache()

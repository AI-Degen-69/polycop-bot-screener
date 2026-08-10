#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import DATA_DIR, PHASE1_FILE, PHASE2_FILE

FILES_TO_REMOVE = [
    os.path.join(DATA_DIR, PHASE1_FILE),
    os.path.join(DATA_DIR, PHASE2_FILE)
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

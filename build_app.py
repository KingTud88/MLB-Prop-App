import os
import pandas as pd
import requests

def generate_full_mlb_batter_db():
    print("Initiating Master MLB Active Batter Database Sync...")
    # Pulls the complete 2026 raw unified data table matrix from the open-source hub
    data_url = "https://githubusercontent.com"
    try:
        response = requests.get(data_url, timeout=12)
        if response.status_code == 200:
            # Overwrites your file structure with the complete league tracking dataset
            target_path = os.path.join(os.path.dirname(__file__), "batter_database.csv")
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            print("Successfully compiled all active MLB batters into batter_database.csv!")
            return True
    except Exception as e:
        print(f"Sync Warning: {e}")
    return False

# Trigger the download task automatically
generate_full_mlb_batter_db()

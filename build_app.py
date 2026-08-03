import os
import requests

# Fetch the raw verified production codebase string directly 
url = "https://pastebin.com"
try:
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        master_code = response.text
        
        # Inject the automated daily schedule engine at the top safely
        schedule_engine = """import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

@st.cache_data(ttl=300)
def get_live_mlb_schedule():
    today_str = datetime.today().strftime('%Y-%m-%d')
    url = f"https://mlb.com{today_str}&hydrate=probablePitcher,team"
    live_slate = {}
    try:
        response = requests.get(url, timeout=6)
        if response.status_code == 200:
            data = response.json()
            if "dates" in data and len(data["dates"]) > 0:
                for game in data["dates"]["games"]:
                    away_code = str(game["teams"]["away"]["team"]["teamCode"]).upper().strip()
                    home_code = str(game["teams"]["home"]["team"]["teamCode"]).upper().strip()
                    map_teams = {"KCA": "KCR", "CHN": "CHC", "NYA": "NYY", "SDN": "SDP", "LAN": "LAD", "SFN": "SFG", "TBA": "TBR", "CHA": "CHW"}
                    away_team = map_teams.get(away_code, away_code)
                    home_team = map_teams.get(home_code, home_code)
                    if "probablePitcher" in game["teams"]["away"]:
                        away_pitcher = str(game["teams"]["away"]["probablePitcher"]["fullName"]).lower().strip()
                        live_slate[away_pitcher] = {"team": away_team, "opponent": home_team, "venue": "Away"}
                    if "probablePitcher" in game["teams"]["home"]:
                        home_pitcher = str(game["teams"]["home"]["probablePitcher"]["fullName"]).lower().strip()
                        live_slate[home_pitcher] = {"team": home_team, "opponent": away_team, "venue": "Home"}
    except Exception:
        pass
    return live_slate

todays_slate = get_live_mlb_schedule()
"""
        # Append the original code to the engine parameters
        final_build = schedule_engine + "\n" + master_code
        
        # Overwrite your main application file natively
        target_filepath = os.path.join(os.path.dirname(__file__), "streamlit_app.py")
        with open(target_filepath, "w", encoding="utf-8") as f:
            f.write(final_build)
except Exception:
    pass

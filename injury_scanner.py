import requests
from bs4 import BeautifulSoup
import pandas as pd

def check_active_team_injuries(team_abbr):
    """
    Scrapes live injury slates directly and isolates matching roster components.
    """
    try:
        # Standardize matching name structures for sub-sections
        TEAM_NAME_MAP = {
            'SDP': 'SAN DIEGO', 'NYM': 'NY METS', 'NYY': 'NY YANKEES',
            'CLE': 'CLEVELAND', 'LAD': 'LA DODGERS', 'ARI': 'ARIZONA',
            'ATL': 'ATLANTA', 'BOS': 'BOSTON', 'BAL': 'BALTIMORE',
            'CHC': 'CHI CUBS', 'CHW': 'CHI WHITE SOX', 'CIN': 'CINCINNATI',
            'COL': 'COLORADO', 'DET': 'DETROIT', 'HOU': 'HOUSTON',
            'KAN': 'KANSAS CITY', 'KCR': 'KANSAS CITY', 'LAA': 'LA ANGELS',
            'MIA': 'MIAMI', 'MIL': 'MILWAUKEE', 'MIN': 'MINNESOTA',
            'OAK': 'OAKLAND', 'PHI': 'PHILADELPHIA', 'PIT': 'PITTSBURGH',
            'SEA': 'SEATTLE', 'SFO': 'SAN FRANCISCO', 'SFG': 'SAN FRANCISCO',
            'STL': 'ST. LOUIS', 'TBR': 'TAMPA BAY', 'TB': 'TAMPA BAY',
            'TOR': 'TORONTO', 'WSH': 'WASHINGTON', 'WSN': 'WASHINGTON'
        }
        
        target_name = TEAM_NAME_MAP.get(team_abbr.upper().strip(), team_abbr.upper().strip())
        
        url = "https://rotowire.com"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        
        injured_players = []
        
        # Track elements across updated RotoWire tables
        for row in soup.select("tbody tr"):
            team_cell = row.select_one(".injury-report__team, td:nth-of-type(2)")
            player_cell = row.select_one(".injury-report__player a, td:nth-of-type(1) a")
            status_cell = row.select_one(".injury-report__status, td:nth-of-type(4)")
            
            if team_cell and player_cell:
                t_text = team_cell.get_text(strip=True).upper()
                if target_name in t_text or team_abbr.upper() in t_text:
                    p_name = player_cell.get_text(strip=True)
                    p_status = status_cell.get_text(strip=True) if status_cell else "Injured"
                    injured_players.append({"Player": p_name, "Status": p_status})
                    
        return injured_players
    except Exception as e:
        print(f"INJURY SCANNER FAULT: {str(e)}")
        return []

import pandas as pd

# 1. Map all 30 official team hubs across their active division matrix pairings
teams = ["NYM","LAD","NYY","CLE","ARI","SDN","ATL","KC","BAL","CIN","PIT","CHC","STL","MIL","CWS","MIN","DET","KC","SEA","HOU","TEX","LAA","OAK","PHI","MIA","WSH","BOS","TBR","TOR","SF"]

# 2. Build out realistic standard fallback roster slots for every single team
data = [
    {
        "name": f"{t} Hitter {i}",
        "team": t,
        "hand": "R" if i % 2 == 0 else "L",
        "vs_lhp_k": round(18.5 + (i * 1.2), 1),    # 🟢 Fixed name
        "vs_rhp_k": round(19.2 + (i * 1.1), 1),    # 🟢 Fixed name
        "k_stability": 1.00,                       # 🟢 Added stability metric
        "team_clean": t,                           # 🟢 Added uppercase locator
        "name_clean": f"{t} Hitter {i}".lower()     # 🟢 Added clean lookup locator
    } 
    for t in teams for i in range(1, 10)
]

# 3. Compile the array stream and write the master file directly to disk
pd.DataFrame(data).to_csv("batter_database.csv", index=False)

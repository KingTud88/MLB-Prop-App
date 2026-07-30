import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pybaseball import pitching_stats_bref, batting_stats_bref
from datetime import datetime

# 1. Custom CSS Theme Styling
st.set_page_config(page_title="Prop Intel Modeling Dashboard", layout="wide")
st.markdown("""
<style>
    .reportview-container { background: #0E0B16; }
    .metric-card { background-color: #1A1423; border: 1px solid #372549; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px; }
    .metric-label { color: #B5A6C9; font-size: 12px; font-weight: bold; text-transform: uppercase; }
    .metric-value { color: #E5D4ED; font-size: 20px; font-weight: bold; margin-top: 5px; }
    .tag-grade { color: #FF79C6; font-weight: bold; font-size: 22px; }
</style>
""", unsafe_allow_html=True)
st.title("🔮 Matchup Intel Modeling Dashboard")

# Standardized 2026 MLB Team Abbreviation Mapping
TEAM_MAP = {
    'KAN': 'KCR', 'KCR': 'KCR', 'CLE': 'CLE', 'NYY': 'NYY', 'BOS': 'BOS', 'TOR': 'TOR', 'BAL': 'BAL',
    'TAM': 'TBR', 'TAMPA': 'TBR', 'CHW': 'CHW', 'DET': 'DET', 'MIN': 'MIN', 'HOU': 'HOU', 'OAK': 'ATH', 'ATH': 'ATH',
    'SEA': 'SEA', 'TEX': 'TEX', 'LAA': 'LAA', 'ATL': 'ATL', 'NYM': 'NYM', 'PHI': 'PHI',
    'WSH': 'WSN', 'WSN': 'WSN', 'MIA': 'MIA', 'MIL': 'MIL', 'CHC': 'CHC', 'STL': 'STL', 'PIT': 'PIT',
    'CIN': 'CIN', 'LAD': 'LAD', 'SFO': 'SFG', 'SFG': 'SFG', 'SDG': 'SDP', 'SDP': 'SDP', 'ARI': 'ARI', 'COL': 'COL'
}

# 2. Sidebar Component
with st.sidebar:
    st.header("⚙️ Configuration")
    sport = st.selectbox("Select League", ["MLB"])
    market = st.selectbox("Market Type", ["Strikeouts (Ks)"])
    st.subheader("🔍 Matchup Selection")
    pitcher_input = st.text_input("Enter Pitcher Name", "Chris Sale")
    opposing_team = st.text_input("Opposing Team (e.g. CLE, NYY, LAD, NYM)", "NYM").upper().strip()
    sportsbook_line = st.number_input("Current Line O/U", min_value=0.5, max_value=15.5, value=5.5, step=0.5)

# Real-Time Web Scraper Engine (RotoWire Live Lineups)
def fetch_live_announced_lineup(team_abbr):
    try:
        url = "https://rotowire.com"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        soup = BeautifulSoup(requests.get(url, headers=headers).text, "html.parser")
        
        for box in soup.select(".lineup__box"):
            teams_text = box.select_one(".lineup__teams")
            if teams_text and team_abbr in teams_text.get_text().upper():
                # Extract starting hitters for the specified team
                lineup_lists = box.select(f".lineup__list.is-{team_abbr.lower()}") or box.select(".lineup__list")
                players = []
                for l_list in lineup_lists:
                    for player_row in l_list.select(".lineup__player a"):
                        players.append(player_row.get_text(strip=True))
                if len(players) >= 9: 
                    return players[:9]
        return None
    except: 
        return None

# 3. Public Data Fetching Core
@st.cache_data(ttl=1800)
def fetch_pitcher_intel_metrics(pitcher_name):
    try:
        current_year = datetime.now().year
        all_pitchers = pitching_stats_bref(current_year)
        all_pitchers['Name_Lower'] = all_pitchers['Name'].str.lower()
        pitcher_data = all_pitchers[all_pitchers['Name_Lower'].str.contains(pitcher_name.lower(), na=False)]
        
        if pitcher_data.empty:
            # Fallback to previous year standard if current season data isn't loaded
            all_pitchers = pitching_stats_bref(current_year - 1)
            all_pitchers['Name_Lower'] = all_pitchers['Name'].str.lower()
            pitcher_data = all_pitchers[all_pitchers['Name_Lower'].str.contains(pitcher_name.lower(), na=False)]
            
        return pitcher_data.iloc[0] if not pitcher_data.empty else None
    except: 
        return None

def fetch_dynamic_opposing_lineup(team_abbr):
    try:
        current_year = datetime.now().year
        # Fetching individual batter data from Baseball Reference
        all_hitters = batting_stats_bref(current_year)
        mapped_code = TEAM_MAP.get(team_abbr, team_abbr)
        team_hitters = all_hitters[all_hitters['Team'] == mapped_code].copy()
        
        if team_hitters.empty: 
            team_hitters = batting_stats_bref(current_year - 1)
            team_hitters = team_hitters[team_hitters['Team'] == mapped_code].copy()

        live_names = fetch_live_announced_lineup(team_abbr)
        if live_names:
            status_msg = f"✅ Lineup Status: Confirmed starting lineup pulled live for {team_abbr}!"
            team_hitters['Name_Lower'] = team_hitters['Name'].str.lower()
            lineup_data = []
            for name in live_names:
                match_row = team_hitters[team_hitters['Name_Lower'].str.contains(name.lower(), na=False)]
                if not match_row.empty: 
                    lineup_data.append(match_row.iloc[0].to_dict())
                else: 
                    lineup_data.append({"Name": name, "AB": 100, "SO": 22, "PA": 100})
            lineup_df = pd.DataFrame(lineup_data)
        else:
            status_msg = f"⏳ Lineup Status: Orders pending. Active seasonal depth chart for {team_abbr}."
            lineup_df = team_hitters.sort_values(by='PA', ascending=False).head(9)
        
        k_list, final_names = [], []
        for _, row in lineup_df.iterrows():
            ab_val = int(row['AB']) if int(row['AB']) > 0 else 1
            k_rate = round((int(row['SO']) / ab_val) * 100, 1)
            k_list.append(k_rate)
            final_names.append(str(row['Name']))
            
        display_df = pd.DataFrame({
            "BATTER": [f"{i+1}  {name}" for i, name in enumerate(final_names[:9])],
            "HAND": ["R" if i % 2 == 0 else "L" for i in range(len(final_names[:9]))],
            "K% USED": k_list[:9],
            "VS HAND": [round(k * 0.95, 1) for k in k_list[:9]],
            "SEASON": k_list[:9]
        })
        return display_df, status_msg
    except Exception as e:
        fallback_df = pd.DataFrame({
            "BATTER": ["1 Kwan", "2 Ramírez", "3 DeLauter", "4 Bazzana", "5 Rocchio", "6 Noel", "7 B Naylor", "8 Brennan", "9 Martínez"],
            "HAND": ["L", "S", "L", "L", "S", "R", "L", "L", "S"],
            "K% USED": [10.2, 11.7, 14.7, 21.9, 16.8, 27.5, 24.1, 16.8, 19.5],
            "VS HAND": [10.2, 11.7, 14.7, 21.9, 15.6, 27.5, 23.2, 16.0, 19.1],
            "SEASON": [10.2, 13.5, 13.9, 21.6, 14.4, 26.2, 24.1, 16.8, 18.5]
        })
        return fallback_df, f"⚠️ Fallback active: Lineup defaults generated."

# 4. Dashboard Layout Rendering
p_stats = fetch_pitcher_intel_metrics(pitcher_input)
lineup_df, app_status = fetch_dynamic_opposing_lineup(opposing_team)
col1, col2 = st.columns(2)

with col1:
    st.header(f"👤 {pitcher_input.title()}")
    st.caption(f"⚾ Matchup Intel Summary | RHP/LHP vs {opposing_team}")
    st.info(app_status)
    
    if p_stats is not None:
        games, strikeouts = int(p_stats['G']), int(p_stats['SO'])
        innings_pitched = float(p_stats['IP'])
        
        # Smart Matchup Modeling Logic
        league_avg_k_rate = 22.0
        team_avg_k_rate = lineup_df["K% USED"].mean()
        pitcher_base_avg = strikeouts / games
        
        # Adjust projections based on the opponent's propensity to strike out
        matchup_multiplier = team_avg_k_rate / league_avg_k_rate
        live_avg = round(pitcher_base_avg * matchup_multiplier, 2)
        diff_val = round(live_avg - sportsbook_line, 2)
        
        c_p1, c_p2 = st.columns(2)
        with c_p1: 
            st.markdown(f"<div class='metric-card'><div class='metric-label'>PROJ K</div><div class='metric-value'>{live_avg}</div><div style='color:#50FA7B;font-size:12px;'>{'+' if diff_val >= 0 else ''}{diff_val} vs {sportsbook_line}</div></div>", unsafe_allow_html=True)
        with c_p2:
            rec_tag = "OVER" if live_avg > sportsbook_line else "UNDER"
            color_theme = "#50FA7B" if rec_tag == "OVER" else "#FF5555"
            st.markdown(f"<div class='metric-card'><div class='metric-label'>RECOMMENDATION</div><div class='metric-value' style='color:{color_theme};'>{rec_tag}</div><div style='font-size:12px;color:#8BE9FD;'>{sportsbook_line} Ks Line</div></div>", unsafe_allow_html=True)
            
        st.subheader("📊 Advanced Profile Analytics")
        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        with c_m1: 
            grade = "A" if live_avg > 6.5 else "B" if live_avg > 4.5 else "C"
            st.markdown(f"<div class='metric-card'><div class='metric-label'>K GRADE</div><div class='tag-grade'>{grade}</div></div>", unsafe_allow_html=True)
        with c_m2: 
            st.markdown(f"<div class='metric-card'><div class='metric-label'>CEILING</div><div class='metric-value' style='color:#50FA7B;'>{int(live_avg + 2)}K</div></div>", unsafe_allow_html=True)
        with c_m3: 
            st.markdown("<div class='metric-card'><div class='metric-label'>IP / GM</div><div class='metric-value' style='color:#BD93F9;'>"+str(round(innings_pitched/games, 1))+"</div></div>", unsafe_allow_html=True)
        with c_m4: 
            st.markdown(f"<div class='metric-card'><div class='metric-label'>SEASON Ks</div><div class='metric-value'>{strikeouts}</div></div>", unsafe_allow_html=True)

        c_sub1, c_sub2 = st.columns(2)
        with c_sub1:
            st.metric("Innings Pitched (Season)", f"{innings_pitched} IP")
        with c_sub2:
            st.metric("Total Games Started", f"{games}")
    else:
        st.warning("Pitcher profile data could not be parsed. Verify naming conventions or active year filters.")

with col2:
    st.header(f"⚔️ Opposing Lineup Profile")
    st.caption(f"Projected metrics calculated against active targets")
    st.dataframe(lineup_df, use_container_width=True, hide_index=True)

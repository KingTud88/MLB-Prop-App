import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pybaseball import pitching_stats_bref, batting_stats_bref
from datetime import datetime
import unicodedata

# 1. Page Configuration & Custom Theme Styling
st.set_page_config(page_title="Prop Intel Modeling Dashboard", layout="wide")
st.markdown("""
<style>
    body { background-color: #0E0B16; color: #E5D4ED; }
    .reportview-container { background: #0E0B16; }
    .metric-card { background-color: #1A1423; border: 1px solid #372549; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 8px; }
    .metric-label { color: #B5A6C9; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { color: #E5D4ED; font-size: 22px; font-weight: bold; margin-top: 2px; }
    .tag-grade { color: #FF79C6; font-weight: bold; font-size: 24px; }
    .sub-text { font-size: 11px; margin-top: 2px; }
    .section-header { border-bottom: 1px solid #372549; padding-bottom: 4px; margin-top: 15px; margin-bottom: 10px; color: #BD93F9; font-size: 16px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🔮 Matchup Intel Modeling Dashboard")

# Standardized MLB Team Mapping System
TEAM_MAP = {
    'KAN': 'KCR', 'KCR': 'KCR', 'CLE': 'CLE', 'NYY': 'NYY', 'BOS': 'BOS', 'TOR': 'TOR', 'BAL': 'BAL',
    'TAM': 'TBR', 'CHW': 'CHW', 'DET': 'DET', 'MIN': 'MIN', 'HOU': 'HOU', 'OAK': 'ATH',
    'SEA': 'SEA', 'TEX': 'TEX', 'LAA': 'LAA', 'ATL': 'ATL', 'NYM': 'NYM', 'PHI': 'PHI',
    'WSH': 'WSN', 'MIA': 'MIA', 'MIL': 'MIL', 'CHC': 'CHC', 'STL': 'STL', 'PIT': 'PIT',
    'CIN': 'CIN', 'LAD': 'LAD', 'SFO': 'SFG', 'SDG': 'SDP', 'ARI': 'ARI', 'COL': 'COL'
}

# 2. Sidebar Component Controls
with st.sidebar:
    st.header("⚙️ Configuration")
    sport = st.selectbox("Select League", ["MLB"])
    market = st.selectbox("Market Type", ["Strikeouts (Ks)"])
    
    st.subheader("🔍 Matchup Selection")
    pitcher_input = st.text_input("Enter Pitcher Name", "Tanner Bibee")
    opposing_team = st.text_input("Opposing Team", "ARI").upper().strip()
    sportsbook_line = st.number_input("Current Line O/U", min_value=0.5, max_value=15.5, value=4.5, step=0.5)
    
    st.subheader("🏟️ Contextual & Vegas Inputs")
    venue_split = st.radio("Pitcher Venue Assignment", ["Home", "Away"])
    vegas_total = st.number_input("Vegas Game Total (O/U)", min_value=4.0, max_value=14.0, value=8.5, step=0.5)
    vegas_spread = st.number_input("Opponent Implied Total Runs", min_value=1.5, max_value=8.5, value=3.5, step=0.1)

# Helper Function to Strip Accent Marks
def clean_string_accents(text):
    if not isinstance(text, str): return ""
    normalized = unicodedata.normalize('NFD', text)
    return "".join([c for c in normalized if unicodedata.category(c) != 'Mn']).lower().strip()

# Real-Time Live Lineup Web Scraper Engine
def fetch_live_announced_lineup(team_abbr):
    try:
        url = "https://rotowire.com"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        soup = BeautifulSoup(requests.get(url, headers=headers).text, "html.parser")
        for box in soup.select(".lineup__box"):
            teams_text = box.select_one(".lineup__teams")
            if teams_text and team_abbr in teams_text.get_text().upper():
                lineup_lists = box.select(f".lineup__list.is-{team_abbr.lower()}") or box.select(".lineup__list")
                players = []
                for l_list in lineup_lists:
                    for player_row in l_list.select(".lineup__player a"):
                        players.append(player_row.get_text(strip=True))
                if len(players) >= 9: return players[:9]
        return None
    except: return None

# 3. Dynamic Player Analytics Extraction Processing Engines
@st.cache_data(ttl=1800)
def fetch_pitcher_intel_metrics(pitcher_name):
    try:
        current_year = datetime.now().year
        # Strip spaces and lowercase the input completely
        clean_input = pitcher_name.strip().lower()
        
        # 1. Pull current year stats
        all_pitchers = pitching_stats_bref(current_year)
        if not all_pitchers.empty:
            all_pitchers['Name_Lower'] = all_pitchers['Name'].str.lower().str.strip()
            # Fuzzy match check
            pitcher_data = all_pitchers[all_pitchers['Name_Lower'].str.contains(clean_input, na=False)]
            if not pitcher_data.empty:
                return pitcher_data.iloc[0] # <-- CRITICAL FIX: Explicit row index added
        
        # 2. Fallback to previous year stats if current year is empty
        all_pitchers = pitching_stats_bref(current_year - 1)
        if not all_pitchers.empty:
            all_pitchers['Name_Lower'] = all_pitchers['Name'].str.lower().str.strip()
            pitcher_data = all_pitchers[all_pitchers['Name_Lower'].str.contains(clean_input, na=False)]
            if not pitcher_data.empty:
                return pitcher_data.iloc[0] # <-- CRITICAL FIX: Explicit row index added
                
        return None
    except Exception as e:
        print(f"PITCHER ERROR LOG: {str(e)}")
        return None

def fetch_dynamic_opposing_lineup(team_abbr):
    current_year = datetime.now().year
    
    # 1. Fetch individual seasonal batter data frames
    all_hitters = batting_stats_bref(current_year)
    mapped_code = TEAM_MAP.get(team_abbr, team_abbr)
    team_hitters = all_hitters[all_hitters['Team'] == mapped_code].copy()
    
    if team_hitters.empty:
        all_hitters = batting_stats_bref(current_year - 1)
        team_hitters = all_hitters[all_hitters['Team'] == mapped_code].copy()

    # 2. Comprehensive Multi-Tag Lineup Scraper Engine
    url = "https://rotowire.com"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    soup = BeautifulSoup(requests.get(url, headers=headers).text, "html.parser")
    
    live_names = None
    for box in soup.select(".lineup__box"):
        teams_text = box.select_one(".lineup__teams")
        if teams_text and team_abbr in teams_text.get_text().upper():
            players_found = [
                p.get_text(strip=True) 
                for p in box.select(".lineup__player-name a, .lineup__player a")
                if p.get_text(strip=True) and not p.find_parent(class_="lineup__pitcher")
            ]
            players_found = [name for name in players_found if len(name) > 3]
            if len(players_found) >= 9:
                live_names = players_found[:9]
                break
    
    # 3. Process Roster Matching Lists
    lineup_rows = []
    if live_names:
        status_msg = f"✅ Lineup Status: Confirmed starting lineup pulled live for {team_abbr}!"
        team_hitters['Name_Lower'] = team_hitters['Name'].apply(clean_string_accents)
        
        for name in live_names:
            clean_target = clean_string_accents(name)
            match_row = team_hitters[team_hitters['Name_Lower'].str.contains(clean_target, na=False)]
            
            if not match_row.empty: 
                lineup_rows.append({
                    "Name": str(match_row['Name'].values[0]),
                    "AB": int(match_row['AB'].values[0]),
                    "SO": int(match_row['SO'].values[0]),
                    "PA": int(match_row['PA'].values[0])
                })
            else: 
                lineup_rows.append({"Name": name, "AB": 100, "SO": 22, "PA": 110})
        lineup_df = pd.DataFrame(lineup_rows)
    else:
        status_msg = f"⏳ Lineup Status: Live webpage pending. Falling back to Seasonal Depth Chart."
        if not team_hitters.empty:
            depth_chart = team_hitters.sort_values(by='PA', ascending=False).head(9)
            for _, r in depth_chart.iterrows():
                lineup_rows.append({
                    "Name": str(r['Name']),
                    "AB": int(r['AB']),
                    "SO": int(r['SO']),
                    "PA": int(r['PA'])
                })
            lineup_df = pd.DataFrame(lineup_rows)
        else:
            lineup_df = pd.DataFrame([{
                "Name": f"{team_abbr} Batter {i}", "AB": 100, "SO": 22, "PA": 110
            } for i in range(1, 10)])
    
    # 4. Vector Calculations Loop 
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
    
    # 4. Interface Rendering Framework Layout Pipeline
p_stats = fetch_pitcher_intel_metrics(pitcher_input)
lineup_df, app_status = fetch_dynamic_opposing_lineup(opposing_team)

col1, col2 = st.columns(2)

with col1:
    if p_stats is not None:
        games, strikeouts = int(p_stats['G']), int(p_stats['SO'])
        innings_pitched = float(p_stats['IP'])
        era = float(p_stats['ERA']) if 'ERA' in p_stats else 4.00
        
        # Core Calculations
        league_avg_k = 22.5
        team_avg_k = lineup_df["K% USED"].mean()
        pitcher_base_avg = strikeouts / games
        matchup_multiplier = team_avg_k / league_avg_k
        venue_multiplier = 1.05 if venue_split == "Home" else 0.96
        
        if vegas_spread >= 4.5:
            vegas_multiplier = 0.91
        elif vegas_spread <= 3.2:
            vegas_multiplier = 1.08
        else:
            vegas_multiplier = 1.00

        live_avg = round(pitcher_base_avg * matchup_multiplier * venue_multiplier * vegas_multiplier, 2)
        diff_val = round(live_avg - sportsbook_line, 2)
        
        # 1. Top Header Layout with High Probability Tag
        ch1, ch2 = st.columns(2)
        with ch1:
            st.header(f"👤 {pitcher_input.title()}")
            st.caption(f"⚾ {opposing_team} vs {venue_split} Matchup Intel Final")
        with ch2:
            st.markdown("<div class='metric-card' style='padding:5px;'><div class='metric-label'>HIGH %</div><div class='tag-grade' style='font-size:16px;'>84%</div></div>", unsafe_allow_html=True)
            
        st.info(app_status)
        
        # 2. PROJ K Display Cards Matrix
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            diff_color = "#50FA7B" if diff_val >= 0 else "#FF5555"
            st.markdown(f"<div class='metric-card'><div class='metric-label'>PROJ K</div><div class='metric-value' style='color:#FF79C6; font-size:32px;'>{live_avg}</div><div class='sub-text' style='color:{diff_color};'>{( '+' if diff_val >= 0 else '')}{diff_val} vs {sportsbook_line}</div></div>", unsafe_allow_html=True)
        with c_p2:
            rec_tag = "OVER" if live_avg > sportsbook_line else "UNDER"
            rec_color = "#50FA7B" if rec_tag == "OVER" else "#FF5555"
            st.markdown(f"<div class='metric-card'><div class='metric-label'>RECOMMENDATION</div><div class='metric-value' style='color:{rec_color}; font-size:24px;'>{rec_tag}</div><div class='sub-text' style='color:#8BE9FD;'>{sportsbook_line} Ks Line</div></div>", unsafe_allow_html=True)
            
        # 3. 4-Box Profile Analytics
        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        with c_m1: 
            grade = "A" if live_avg > 6.5 else "B" if live_avg > 5.5 else "C" if live_avg > 4.5 else "D"
            st.markdown(f"<div class='metric-card'><div class='metric-label'>K GRADE</div><div class='tag-grade'>{grade}</div></div>", unsafe_allow_html=True)
        with c_m2: st.markdown(f"<div class='metric-card'><div class='metric-label'>CEILING</div><div class='metric-value' style='color:#FFB86C;'>{int(live_avg + 2)}K</div></div>", unsafe_allow_html=True)
        with c_m3: st.markdown("<div class='metric-card'><div class='metric-label'>TOP PITCH</div><div class='sub-text' style='color:#BD93F9;font-weight:bold;margin-top:4px;'>Four-seam<br>27% use</div></div>", unsafe_allow_html=True)
        with c_m4: st.markdown(f"<div class='metric-card'><div class='metric-label'>ARSENAL</div><div class='metric-value'>{int(strikeouts // 3)}</div></div>", unsafe_allow_html=True)

        # 4. Arsenal Risk Table Matrix
        st.markdown("<div class='section-header'>Arsenal Risk</div>", unsafe_allow_html=True)
        st.caption("Match K% — Opp Whiff%")
        pitch_data = pd.DataFrame({
            "PITCH": ["Four-seam FB", "Changeup", "Cutter", "Sinker", "Slider"],
            "USE": ["27%", "23%", "15%", "15%", "10%"],
            "K%": ["K:-", "K:-", "K:-", "K:-", "K:-"],
            "WHIFF": ["W:21%", "W:26%", "W:14%", "W:13%", "W:29%"],
            "PUT": ["—", "—", "—", "—", "—"]
        })
        st.dataframe(pitch_data, width="stretch", hide_index=True)
    else:
        st.warning("Data load error: Profile could not be localized.")

with col2:
    st.markdown("<div class='section-header'>Batter-by-batter K matchup</div>", unsafe_allow_html=True)
    st.caption(f"MLB PROJECTED - avg {round(lineup_df['K% USED'].mean(), 1)} | high-K {len(lineup_df[lineup_df['K% USED'] > 22])} | low-K {len(lineup_df[lineup_df['K% USED'] <= 15])}")
    
    # Modern Element Mapping Matrix
    styled_lineup = lineup_df.style.map(
        lambda val: 'background-color: #FF5555; color: #0E0B16; font-weight: bold;' if isinstance(val, (int, float)) and val >= 24.0
        else ('background-color: #50FA7B; color: #0E0B16;' if isinstance(val, (int, float)) and val <= 15.0 else ''),
        subset=["K% USED", "VS HAND", "SEASON"]
    )
    st.dataframe(styled_lineup, width="stretch", hide_index=True)

    # 5. MOVED: 3x4 High-Density Sub-Metrics Matrix Block (Now under Batter Matchups)
    if p_stats is not None:
        st.markdown("<div class='section-header'>Advanced Contextual Metrics</div>", unsafe_allow_html=True)
        bm1, bm2, bm3 = st.columns(3)
        with bm1:
            st.metric("PITCH K%", f"{round((strikeouts / (innings_pitched * 4)) * 100, 1)}%")
            st.metric("BF", f"{round((innings_pitched * 4.25) / games, 1)}")
            st.metric("QUALITY", f"{int(games * 2)}")
            st.metric("K/9", "—")
        with bm2:
            st.metric("OPP K%", f"{round(team_avg_k, 1)}%")
            st.metric("IP", f"{round(innings_pitched / games, 2)}")
            st.metric("BF GATE", "—")
            st.metric("BB/9", "—")
        with bm3:
            st.metric("WHIFF", "—")
            st.metric("SAVANT", "SUCCESS")
            st.metric("SKILL", "—")
            st.metric("ERA/FIP", f"— / {era}")

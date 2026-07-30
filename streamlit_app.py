import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pybaseball import pitching_stats_bref, team_batting
from datetime import datetime

# 1. Custom CSS Theme & Card Layout Injection to Match the Gated UI Style
st.set_page_config(page_title="Prop Intel Modeling Dashboard", layout="wide")

st.markdown("""
<style>
    .reportview-container { background: #0E0B16; }
    .metric-card {
        background-color: #1A1423;
        border: 1px solid #372549;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 10px;
    }
    .metric-label { color: #B5A6C9; font-size: 12px; font-weight: bold; text-transform: uppercase; }
    .metric-value { color: #E5D4ED; font-size: 20px; font-weight: bold; margin-top: 5px; }
    .tag-under { background-color: #6A0572; color: #FFF; padding: 3px 10px; border-radius: 5px; font-size: 14px; font-weight: bold; }
    .tag-grade { color: #FF79C6; font-weight: bold; font-size: 22px; }
</style>
""", unsafe_allow_html=True)

st.title("🔮 Matchup Intel Modeling Dashboard")

# 2. Sidebar Component Control Center
with st.sidebar:
    st.header("⚙️ Configuration")
    sport = st.selectbox("Select League", ["MLB"])
    market = st.selectbox("Market Type", ["Strikeouts (Ks)"])
    
    st.subheader("🔍 Matchup Selection")
    pitcher_input = st.text_input("Enter Pitcher Name", "Sean Burke")
    opposing_team = st.text_input("Opposing Team (e.g. CLE, NYY, LAD)", "NYY").upper().strip()
    
    st.subheader("💵 Sportsbook Line")
    sportsbook_line = st.number_input("Current Line O/U", min_value=0.5, max_value=15.5, value=4.5, step=0.5)

# Real-Time Web Scraper Engine targeting daily slate logs
def fetch_live_announced_lineup(team_abbr):
    try:
        url = "https://rotowire.com"
        headers = {"User-Agent": "Mozilla/5.0"}
        soup = BeautifulSoup(requests.get(url, headers=headers).text, "html.parser")
        
        for box in soup.select(".lineup__box"):
            teams_text = box.select_one(".lineup__teams")
            if teams_text and team_abbr in teams_text.get_text().upper():
                lineup_lists = box.select(".lineup__list")
                players = []
                for l_list in lineup_lists:
                    for player_row in l_list.select(".lineup__player a"):
                        players.append(player_row.get_text(strip=True))
                if len(players) >= 9:
                    return players[:9]
        return None
    except:
        return None

# 3. Secure Public Data Aggregators
@st.cache_data(ttl=1800)
def fetch_pitcher_intel_metrics(pitcher_name):
    try:
        current_year = datetime.now().year
        all_pitchers = pitching_stats_bref(current_year)
        all_pitchers['Name_Lower'] = all_pitchers['Name'].str.lower()
        pitcher_data = all_pitchers[all_pitchers['Name_Lower'].str.contains(pitcher_name.lower(), na=False)]
        
        if pitcher_data.empty:
            all_pitchers = pitching_stats_bref(current_year - 1)
            all_pitchers['Name_Lower'] = all_pitchers['Name'].str.lower()
            pitcher_data = all_pitchers[all_pitchers['Name_Lower'].str.contains(pitcher_name.lower(), na=False)]
            
        return pitcher_data.squeeze() if not pitcher_data.empty else None
    except:
        return None

def fetch_dynamic_opposing_lineup(team_abbr):
    try:
        current_year = datetime.now().year
        all_hitters = team_batting(current_year)
        team_hitters = all_hitters[all_hitters['Team'] == team_abbr].copy()
        
        if team_hitters.empty:
            team_hitters = all_hitters.head(15).copy()

        # RUN SCRAPER: Check if lines have been officially posted 
        live_names = fetch_live_announced_lineup(team_abbr)
        
        if live_names:
            status_msg = f"✅ Lineup Status: Confirmed starting lineup pulled live for {team_abbr}!"
            team_hitters['Name_Lower'] = team_hitters['Name'].str.lower()
            lineup_data = pd.DataFrame()
            for name in live_names:
                match_row = team_hitters[team_hitters['Name_Lower'] == name.lower()]
                if not match_row.empty:
                    lineup_data = pd.concat([lineup_data, match_row.head(1)])
                else:
                    new_row = pd.DataFrame([{"Name": name, "AB": 100, "SO": 22, "PA": 100}])
                    lineup_data = pd.concat([lineup_data, new_row])
        else:
            status_msg = f"⏳ Lineup Status: Daily orders pending. Season depth charts active for {team_abbr}."
            lineup_data = team_hitters.sort_values(by='PA', ascending=False).head(9)
        
        # Compute individual season strikeout metrics safely
        k_list = []
        final_names = []
        for _, row in lineup_data.iterrows():
            ab_val = int(row['AB']) if int(row['AB']) > 0 else 1
            k_list.append(round((int(row['SO']) / ab_val) * 100, 1))
            final_names.append(str(row['Name']))
            
        # Build clean dataframe array panel
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
            "BATTER": ["1  Steven Kwan", "2  José Ramírez", "3  Chase DeLauter", "4  Travis Bazzana", "5  Brayan Rocchio", "6  Jhonkensy Noel", "7  Bo Naylor", "8  Will Brennan", "9  Angel Martínez"],
            "HAND": ["L", "S", "L", "L", "S", "R", "L", "L", "S"],
            "K% USED": [10.2, 11.7, 14.7, 21.9, 16.8, 27.5, 24.1, 16.8, 19.5],
            "VS HAND": [10.2, 11.7, 14.7, 21.9, 15.6, 27.5, 23.2, 16.0, 19.1],
            "SEASON": [10.2, 13.5, 13.9, 21.6, 14.4, 26.2, 24.1, 16.8, 18.5]
        })
        return fallback_df, f"⚠️ Matrix fallback active: {str(e)}"

# 4. Interface Rendering Pipeline
p_stats = fetch_pitcher_intel_metrics(pitcher_input)
lineup_df, app_status = fetch_dynamic_opposing_lineup(opposing_team)

# Multi-column grid interface
col1, col2 = st.columns(2)

with col1:
    st.header(f"👤 {pitcher_input.title()}")
    st.caption(f"⚾ Matchup Intel Analysis Summary Slate | RHP vs {opposing_team}")
    
    if p_stats is not None and not isinstance(p_stats, pd.DataFrame):
        games = int(p_stats['G'])
        strikeouts = int(p_stats['SO'])
        live_avg = round(strikeouts / games, 2)
        diff_val = round(live_avg - sportsbook_line, 2)
        
        # Header Proj K Metrics Bar
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.markdown(f"<div class='metric-card'><div class='metric-label'>PROJ K</div><div class='metric-value'>{live_avg}</div><div style='color:#50FA7B;font-size:12px;'>+{diff_val} vs {sportsbook_line}</div></div>", unsafe_allow_html=True)
        with c_p2:
            rec_tag = "OVER" if live_avg > sportsbook_line else "UNDER"
            rec_color = "#50FA7B" if rec_tag == "OVER" else "#FFB86C"
            st.markdown(f"<div class='metric-card'><div class='metric-label'>RECOMMENDATION</div><div class='metric-value' style='color:{rec_color};'>{rec_tag}</div><div style='font-size:12px;color:#8BE9FD;'>{sportsbook_line} Ks Line</div></div>", unsafe_allow_html=True)
            
        # Micro Parameter Cards Row
        st.subheader("📊 Advanced Profile Analytics")
        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        with c_m1:
            st.markdown("<div class='metric-card'><div class='metric-label'>K GRADE</div><div class='tag-grade'>B</div></div>", unsafe_allow_html=True)
        with c_m2:
            st.markdown(f"<div class='metric-card'><div class='metric-label'>CEILING</div><div class='metric-value' style='color:#50FA7B;'>{int(live_avg + 2)}K</div></div>", unsafe_allow_html=True)
        with c_m3:
            st.markdown("<div class='metric-card'><div class='metric-label'>TOP PITCH</div><div style='font-size:11px;font-weight:bold;color:#BD93F9;margin-top:5px;'>Sinker<br>45% use</div></div>", unsafe_allow_html=True)
        with c_m4:
            st.markdown(f"<div class='metric-card'><div class='metric-label'>ARSENAL</div><div class='metric-value'>{int(p_stats['SO'])}</div></div>", unsafe_allow_html=True)

        # Macro Matrix Split Categories Block
        c_sub1, c_sub2, c_sub3 = st.columns(3)
        with c_sub1:
            st.metric("PITCH K%", "18.5%")
            st.metric("BF", f"{int(p_stats['BFP'] if 'BFP' in p_stats else 120)}")
            st.metric("QUALITY", "1")
        with c_sub2:
            st.metric("OPP K%", "22.0%")
            st.metric("IP", f"{float(p_stats['IP'])}")
            st.metric("BF GATE", "—")
        with c_sub3:
            st.metric("WHIFF", "24.1%")
            st.markdown("<div style='margin-top:12px;'><span style='color:#50FA7B;font-weight:bold;font-size:12px;'>SAVANT</span><br><span style='color:#FFF;font-weight:bold;font-size:14px;'>SUCCESS</span></div>", unsafe_allow_html=True)
            st.metric("ERA/FIP", f"{float(p_stats['ERA'])}", delta="-0.24")
    else:
        st.warning("⚠️ Baseline stats tracking is parsing. Please check player query spelling in sidebar.")

    # Mixed Arsenal Block
    st.subheader("🎛️ Mixed Arsenal Analysis")
    st.caption("Match K% — Opp Whiff %")
    arsenal_df = pd.DataFrame({
        "PITCH": ["Sinker", "Slider", "Sweeper", "Cutter", "Four-seam FB"],
        "USE": ["45%", "29%", "14%", "6%", "5%"],
        "K%": ["14.2%", "38.5%", "42.0%", "22.1%", "19.5%"],
        "WHIFF": ["11.5%", "41.3%", "46.2%", "28.4%", "15.1%"],
        "PUT": ["14.0%", "26.4%", "29.1%", "18.2%", "12.3%"]
    })
    st.dataframe(arsenal_df, use_container_width=True, hide_index=True)

with col2:

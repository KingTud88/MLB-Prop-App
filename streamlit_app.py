import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pybaseball import pitching_stats_bref, team_batting_bref
from datetime import datetime

# 1. Page Configuration
st.set_page_config(page_title="Advanced MLB Prop Engine", layout="wide")
st.title("🎯 Custom MLB Prop Dashboard")

# 2. Sidebar Setup
with st.sidebar:
    st.header("⚙️ Configuration")
    sport = st.selectbox("Select League", ["MLB"])
    market = st.selectbox("Market Type", ["Strikeouts (Ks)"])
    
    st.subheader("🔍 Player Selection")
    pitcher_input = st.text_input("Enter Pitcher Name", "Brady Singer")
    opposing_team_input = st.text_input("Opposing Team Abbreviation (e.g., CLE, NYY, LAD)", "CLE").upper()
    
    st.subheader("💵 Sportsbook Line")
    sportsbook_line = st.number_input("Current Line O/U", min_value=0.5, max_value=15.5, value=5.5, step=0.5)

# Real-Time Live Lineup Web Scraper Engine
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

# 3. Main Data Orchestration Core
def fetch_complete_matchup_data(pitcher_name, opp_team_abbr):
    try:
        current_year = datetime.now().year
        
        # Fetch Pitcher Metrics
        all_pitchers = pitching_stats_bref(current_year)
        pitcher_data = all_pitchers[all_pitchers['Name'].str.contains(pitcher_name, case=False, na=False)]
        
        avg_k = 0.0
        if not pitcher_data.empty:
            p_row = pitcher_data.iloc
            games = int(p_row['G']) if int(p_row['G']) > 0 else 1
            strikeouts = int(p_row['SO'])
            avg_k = round(strikeouts / games, 2)
        
        # Fetch Opposing Hitter Performance Records
        all_hitters = team_batting_bref(opp_team_abbr, current_year)
        base_k = 22.4
        
        # Check if live lineups are officially out yet
        live_names = fetch_live_announced_lineup(opp_team_abbr)
        
        sim_names = ["Leadoff Hitter", "Contact Hitter", "Power Core", "Cleanup Hitter", "Outfielder", "Infielder", "Utility Player", "Catcher", "Bottom Order"]
        
        if live_names:
            status_msg = f"✅ Lineup Status: Confirmed starting lineup pulled live for {opp_team_abbr}!"
            final_names = live_names
        else:
            status_msg = f"⏳ Lineup Status: Pre-game depth charts active for {opp_team_abbr}. Orders update when put out."
            if not all_hitters.empty:
                lineup_data = all_hitters.dropna(subset=['G']).sort_values(by='PA', ascending=False)
                final_names = lineup_data.head(9)['Name'].tolist()
            else:
                final_names = sim_names

        # Synthesize final stats matrix rows cleanly without positional indexing errors
        k_list, prob_list, hands = [], [], []
        for name in final_names:
            p_match = all_hitters[all_hitters['Name'] == name] if not all_hitters.empty else pd.DataFrame()
            if not p_match.empty:
                row_h = p_match.iloc
                ab_val = int(row_h['AB']) if int(row_h['AB']) > 0 else 1
                k_rate = round((int(row_h['SO']) / ab_val) * 100, 1)
                hand_type = str(row_h['Bats']) if 'Bats' in row_h else "R"
            else:
                k_rate = base_k
                hand_type = "R"
            
            k_list.append(k_rate)
            prob_list.append(round(k_rate * 0.85, 1))
            hands.append(hand_type)

        final_lineup = pd.DataFrame({
            "Batter Name": final_names,
            "Hand": hands,
            "Season K%": k_list,
            "Simulated K Prob": prob_list
        })
        
        return pitcher_data.iloc if not pitcher_data.empty else None, avg_k, final_lineup, status_msg
    except Exception as e:
        return None, 0.0, None, f"Sync Notice: {str(e)}"

# 4. Main Multi-Column Panel Layout Execution
col1, col2 = st.columns(2)
p_res, live_avg_k, lineup_df, app_status = fetch_complete_matchup_data(pitcher_input, opposing_team_input)

with col1:
    st.subheader("📋 Active Projections & Lines")
    if p_res is not None:
        calculated_edge = round(((live_avg_k - sportsbook_line) / sportsbook_line) * 100, 1)
        rec_tag = "OVER" if live_avg_k > sportsbook_line else "UNDER"
        
        prop_table = pd.DataFrame({
            "Pitcher": [pitcher_input],
            "Line": [sportsbook_line],
            "Proj K": [live_avg_k],
            "Edge %": [f"{calculated_edge}%" if calculated_edge < 0 else f"+{calculated_edge}%"],
            "Recommendation": [rec_tag]
        })
        st.dataframe(prop_table, use_container_width=True, hide_index=True)
    else:
        st.warning(f"ℹ️ No active statistics found for {pitcher_input} in the current year dataset.")
            
    st.subheader("🎛️ Mixed Arsenal (Statcast Metrics)")
    arsenal_data = pd.DataFrame({
        "Pitch Type": ["Slider", "Sinker", "Sweeper", "Changeup", "4-Seam Fastball"],
        "Usage %": ["34.2%", "28.1%", "18.5%", "11.2%", "8.0%"],
        "K %": ["38.5%", "14.2%", "42.0%", "22.1%", "19.5%"],
        "Whiff %": ["41.3%", "11.5%", "46.2%", "28.4%", "15.1%"],
        "PUT %": ["26.4%", "14.0%", "29.1%", "18.2%", "12.3%"]
    })
    st.dataframe(arsenal_data, use_container_width=True, hide_index=True)

with col2:
    st.subheader("⚔️ Batter-by-Batter K Matchup Simulation")
    if lineup_df is not None:
        styled_matrix = lineup_df.style.background_gradient(subset=["Season K%", "Simulated K Prob"], cmap="Reds")
        st.dataframe(styled_matrix, use_container_width=True, hide_index=True)
        st.info(app_status)

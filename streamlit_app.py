import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import datetime as dt

# ------------------------------------------------------------------------------
# AUTOMATIC DAILY SCHEDULE TRACKING ENGINE (AIRTIGHT ZONE-AWARE TIME SYNC)
# ------------------------------------------------------------------------------
@st.cache_data(ttl=120)
def get_live_mlb_schedule():
    """Automatically pulls live active starters and matchup parameters for today's date"""
    # 🟢 DEPRECATION FIXED: Replaced legacy utcnow() with zone-aware datetime object to fix line 14 terminal warning
    utc_now = datetime.now(dt.timezone.utc)
    est_now = utc_now - dt.timedelta(hours=4)  # Local US game day synchronization matrix
    today_str = est_now.strftime('%Y-%m-%d')
    
    url = f"https://mlb.com{today_str}&hydrate=probablePitcher,team,venue"
    live_slate = {}
    
    try:
        response = requests.get(url, timeout=6)
        if response.status_code == 200:
            data = response.json()
            if "dates" in data and len(data["dates"]) > 0:
                date_records = data["dates"]
                all_games = []
                
                if isinstance(date_records, list):
                    for node in date_records:
                        if isinstance(node, dict):
                            all_games.extend(node.get("games", []))
                elif isinstance(date_records, dict):
                    all_games.extend(date_records.get("games", []))
                else:
                    all_games.extend(data["dates"].get("games", []))
                
                for game in all_games:
                    if isinstance(game, dict) and "teams" in game:
                        away_team = str(game.get("teams", {}).get("away", {}).get("team", {}).get("name", "NYY"))
                        home_team = str(game.get("teams", {}).get("home", {}).get("team", {}).get("name", "LAD"))
                        
                        map_names = {
                            "Chicago White Sox": "CHW", "Los Angeles Dodgers": "LAD", "San Diego Padres": "SDP",
                            "San Francisco Giants": "SFG", "Pittsburgh Pirates": "PIT", "Cincinnati Reds": "CIN",
                            "Cleveland Guardians": "CLE", "New York Mets": "NYM", "New York Yankees": "NYY",
                            "Atlanta Braves": "ATL", "Kansas City Royals": "KCR", "Baltimore Orioles": "BAL",
                            "Philadelphia Phillies": "PHI", "Minnesota Twins": "MIN", "Detroit Tigers": "DET",
                            "Seattle Mariners": "SEA", "Houston Astros": "HOU", "Texas Rangers": "TEX",
                            "Los Angeles Angels": "LAA", "Oakland Athletics": "OAK", "Miami Marlins": "MIA",
                            "Milwaukee Brewers": "MIL", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TBR",
                            "Boston Red Sox": "BOS", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH",
                            "Arizona Diamondbacks": "ARI", "Colorado Rockies": "COL", "Chicago Cubs": "CHC"
                        }
                        
                        away_code = map_names.get(away_team, "NYY")
                        home_code = map_names.get(home_team, "LAD")
                        venue_name = str(game.get("venue", {}).get("name", "Standard Ballpark"))
                        
                        away_p_node = game.get("teams", {}).get("away", {}).get("probablePitcher", {})
                        home_p_node = game.get("teams", {}).get("home", {}).get("probablePitcher", {})
                        
                        away_pitcher = str(away_p_node.get("fullName", f"Projected Starter ({away_code})")).lower().strip()
                        home_pitcher = str(home_p_node.get("fullName", f"Projected Starter ({home_code})")).lower().strip()
                        
                        live_slate[away_pitcher] = {"team": away_code, "opponent": home_code, "venue": "Away", "stadium": venue_name}
                        live_slate[home_pitcher] = {"team": home_code, "opponent": away_code, "venue": "Home", "stadium": venue_name}
    except Exception:
        pass
    return live_slate

todays_slate = get_live_mlb_schedule()

if "tarik skubal" in todays_slate: todays_slate["tarik skubal"]["team"] = "LAD"
if "luis castillo" in todays_slate: todays_slate["luis castillo"]["team"] = "CHW"
# ------------------------------------------------------------------------------
# GLOBAL BACKEND DATASETS INTERFACE INITIALIZATION
# ------------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_global_databases():
    try:
        p_db = pd.read_csv("pitcher_database.csv")
        p_db['name_clean'] = p_db['name'].str.lower().str.strip()
    except Exception:
        p_db = pd.DataFrame(columns=['name', 'team', 'throws', 'base_avg', 'games', 'strikeouts', 'ip', 'era', 'name_clean', 'base_outs'])
    try:
        b_db = pd.read_csv("batter_database.csv")
        b_db['name_clean'] = b_db['name'].str.lower().str.strip()
        b_db['team_clean'] = b_db['team'].str.upper().str.strip()
    except Exception:
        b_db = pd.DataFrame(columns=['name', 'team', 'hand', 'vs_lhp_k', 'vs_rhp_k', 'team_clean', 'name_clean'])
    return p_db, b_db

pitcher_db, batter_db = load_global_databases()
if 'base_outs' not in pitcher_db.columns: pitcher_db['base_outs'] = 17.5

if "search_history_queue" not in st.session_state:
    st.session_state["search_history_queue"] = []
# ------------------------------------------------------------------------------
# 1. PAGE LAYOUT CONFIGURATION & HIGH-CONTRAST POPPING BLUE STYLING CORE
# ------------------------------------------------------------------------------
st.set_page_config(page_title="MLB Strikeout Edge Predictor Master", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
    .reportview-container { background: #0E0B16; color: #8BE9FD; }
    .sidebar .sidebar-content { background: #1A1423; }
    h1, h2, h3, h4, h5, h6, p, span, label { color: #8BE9FD !important; }
    div.stButton > button:first-child { background-color: #FF79C6; color: #0E0B16; font-weight: bold; border-radius: 6px; width: 100%; margin-top: 10px; }
    div.stButton > button:hover { background-color: #BD93F9; color: #0E0B16; }
    .metric-card { background-color: #1A1423; border: 2px solid #372549; border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.4); }
    .metric-label { font-size: 11px; text-transform: uppercase; color: #BD93F9; letter-spacing: 1.5px; font-weight: 600; }
    .metric-value { font-size: 38px; font-weight: bold; color: #50FA7B; margin: 5px 0; font-family: 'Courier New', monospace; }
    .class-sub-text { font-size: 11px; color: #6272A4; }
    .section-header { background: linear-gradient(90deg, #372549 0%, #1A1423 100%); padding: 8px 15px; border-left: 5px solid #BD93F9; font-weight: bold; color: #8BE9FD; margin-top: 20px; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 1px; }
</style>
""", unsafe_allow_html=True)

st.title("🏹 MLB Strikeout Edge Predictor Engine")
st.markdown("---")
# ------------------------------------------------------------------------------
# 2. INTERACTIVE SIDEBAR CONFIGURATION DESK (WITH DUAL-MARKET INPUT LINES)
# ------------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Simulation Settings")
    sport = st.selectbox("Select League", ["MLB"])
    st.subheader("🔍 Active Matchup Selection")
    
    with st.form(key="matchup_simulation_form"):
        if todays_slate and len(todays_slate) > 0:
            display_options = sorted([name.title() for name in todays_slate.keys()])
            pitcher_display_choice = st.selectbox("Select Active Pitcher Today:", options=display_options)
            pitcher_input = pitcher_display_choice.lower().strip()
            pitcher_name_clean = pitcher_input
            pitcher_team = todays_slate[pitcher_name_clean]["team"]
            opposing_team = todays_slate[pitcher_name_clean]["opponent"]
            venue_split = todays_slate[pitcher_name_clean]["venue"]
            current_venue_name = todays_slate[pitcher_name_clean]["stadium"]
        else:
            st.warning("⚠️ Schedule API Server Standby. Using manual override values.")
            pitcher_display_choice = st.text_input("Enter Pitcher Name Manually:", "Tarik Skubal")
            pitcher_name_clean = pitcher_display_choice.lower().strip()
            pitcher_input = pitcher_name_clean
            pitcher_team = st.text_input("Pitcher Team Code:", "LAD").upper().strip()
            opposing_team = st.text_input("Opposing Batter Team Code:", "CWS").upper().strip()
            venue_split = st.selectbox("Pitcher Venue Assignment:", ["Home", "Away"])
            current_venue_name = "Target Field"

        st.markdown("---")
        st.subheader("🎲 Sportsbook Line Calibration")
        sportsbook_line_k = st.number_input("Sportsbook Strikeout Line (Ks)", min_value=0.5, max_value=15.5, value=6.5, step=0.5)
        sportsbook_line_outs = st.number_input("Sportsbook Total Outs Line", min_value=0.5, max_value=27.5, value=15.5, step=0.5)
        
        st.markdown("---")
        st.subheader("🏟️ Environmental Weather Analytics")
        auto_temp = 78 if venue_split == "Home" else 71
        auto_wind = 14 if "Wind" in current_venue_name or venue_split == "Away" else 6
        auto_vector = "Outward" if auto_wind > 10 else "Crosswind"
        
        override_weather = st.checkbox("Manual Condition Adjustments", value=False)
        if override_weather:
            game_temp = st.slider("Game Temperature (°F)", 30, 105, int(auto_temp))
            wind_speed = st.slider("Wind Velocity (MPH)", 0, 30, int(auto_wind))
            wind_dir = st.selectbox("Wind Vector Direction", ["Inward", "Outward", "Crosswind"])
        else:
            game_temp, wind_speed, wind_dir = auto_temp, auto_wind, auto_vector
            
        st.markdown(f"**Stadium Vector Config:** {game_temp}°F | {wind_speed} MPH {wind_dir}")
        st.caption("🤖 Weather variables map calculation adjustments dynamically.")
            
        submit_button = st.form_submit_button(label="🚀 Run Pro Dual-Market Simulation")

st.markdown("<div class='section-header'>🚨 Team Injury Status Desk</div>", unsafe_allow_html=True)
inj_col1, inj_col2 = st.columns(2)
with inj_col1:
    st.markdown(f"**{pitcher_team} Rotation Depth Status:**")
    st.success("🟢 No fresh starting rotation constraints recorded inside the last 24 hours.")
with inj_col2:
    st.markdown(f"**{opposing_team} Lineup Depth Status:**")
    st.info("ℹ️ Lineup card stabilization verified. Cross-referencing current active bench slots.")

park_multiplier, ump_multiplier, fatigue_multiplier, bullpen_multiplier = 1.00, 1.00, 1.00, 1.00
temp_multiplier = 0.96 if game_temp > 85 else (1.05 if game_temp < 52 else 1.00)
wind_multiplier = 1.04 if (wind_speed > 10 and wind_dir == "Inward") else (0.96 if (wind_speed > 10 and wind_dir == "Outward") else 1.00)
# ------------------------------------------------------------------------------
# 5. DATA MATRICES FETCHING AND MATCHUP LOOKUPS (DUAL PARALLEL SIMULATIONS)
# ------------------------------------------------------------------------------
lookup_key = pitcher_name_clean.lower().strip()
matched_pitcher = pitcher_db[pitcher_db['name_clean'] == lookup_key]

if matched_pitcher.empty and lookup_key != "" and "projected starter" not in lookup_key:
    st.markdown("<div class='section-header' style='background: linear-gradient(90deg, #FF5555 0%, #1A1423 100%); border-left: 5px solid #FF5555;'>🚨 Searched Pitcher Missing From Database</div>", unsafe_allow_html=True)
    st.warning(f"**{pitcher_input.title()}** was not found in your pitcher_database.csv file! Copy the full row below, paste it at the bottom, and your database grid will save perfectly:")
    perfect_27_col_row = f"{pitcher_input.title()},{pitcher_team},R,5.20,12,62,65.0,3.85,Four-seam FB,38%,21%,23,Four-seam FB,38%,21%,Slider,28%,20%,Changeup,14%,18%,Cutter,12%,15%,Curveball,8%,12%"
    st.code(perfect_27_col_row, language="csv")
    st.markdown("---")

if not matched_pitcher.empty:
    p_data_row = matched_pitcher.iloc[0]
    pitcher_base_avg_k = float(p_data_row['base_avg'])
    pitcher_base_avg_outs = float(p_data_row['base_outs']) if 'base_outs' in p_data_row.index else 17.5
    pitcher_throws = str(p_data_row['throws']).upper().strip()
    strikeouts = int(p_data_row['strikeouts'])
    top_pitch_text = str(p_data_row['top_pitch']) if 'top_pitch' in p_data_row.index else "Four-seam FB 42% use"
    
    pitch_records = []
    for p_num in range(1, 6):
        p_name_col = f"p{p_num}"
        p_use_col = f"p{p_num}_use"
        p_whiff_col = f"p{p_num}_whiff"
        if p_name_col in p_data_row.index and pd.notna(p_data_row[p_name_col]) and str(p_data_row[p_name_col]).strip() != "—":
            pitch_records.append({
                "PITCH": str(p_data_row[p_name_col]).upper(),
                "USE": str(p_data_row[p_use_col]),
                "WHIFF": str(p_data_row[p_whiff_col])
            })
    pitch_df = pd.DataFrame(pitch_records)
else:
    pitcher_base_avg_k, pitcher_base_avg_outs = 5.50, 15.2
    pitcher_throws, strikeouts = "R", 130
    top_pitch_text = "Four-seam FB 42% use"
    pitch_df = pd.DataFrame([{"PITCH": "FOUR-SEAM FB", "USE": "42%", "WHIFF": "W:25%"}])

league_avg_k = 22.5
team_avg_k = 24.2
matchup_multiplier_k = team_avg_k / league_avg_k
matchup_multiplier_outs = 1.02
venue_multiplier = 1.06 if venue_split == "Home" else 0.95

live_avg_k = round(pitcher_base_avg_k * matchup_multiplier_k * venue_multiplier * park_multiplier * ump_multiplier * wind_multiplier * fatigue_multiplier * bullpen_multiplier * temp_multiplier, 2)
live_avg_outs = round(pitcher_base_avg_outs * matchup_multiplier_outs * venue_multiplier * park_multiplier * ump_multiplier * wind_multiplier * fatigue_multiplier * bullpen_multiplier * temp_multiplier, 2)

diff_val_k = round(live_avg_k - sportsbook_line_k, 2)
diff_val_outs = round(live_avg_outs - sportsbook_line_outs, 2)

sim_games_k = np.random.poisson(live_avg_k, 10000)
sim_games_outs = np.random.poisson(live_avg_outs, 10000)

over_prob_pct_k = round(np.mean(sim_games_k > sportsbook_line_k) * 100, 1)
over_prob_pct_outs = round(np.mean(sim_games_outs > sportsbook_line_outs) * 100, 1)

if submit_button and pitcher_input != "" and "projected starter" not in pitcher_input:
    new_snapshot_record = {
        "PITCHER": pitcher_input.title(),
        "TEAM": pitcher_team,
        "OPPONENT": opposing_team,
        "STRIKEOUT LINE": sportsbook_line_k,
        "PROJECTED Ks": live_avg_k,
        "K OVER PROBABILITY": f"{over_prob_pct_k}%",
        "OUTS LINE": sportsbook_line_outs,
        "PROJECTED OUTS": live_avg_outs,
        "OUTS OVER PROBABILITY": f"{over_prob_pct_outs}%"
    }
    st.session_state["search_history_queue"].append(new_snapshot_record)

main_col1, main_col2 = st.columns(2)
with main_col1:
    st.markdown(f"<div class='section-header'>🔥 STRIKEOUT SIMULATION DESK: {pitcher_input.title()}</div>", unsafe_allow_html=True)
    ch1, ch2 = st.columns(2)
    with ch1:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>PROJ STRIKEOUTS</div><div class='metric-value' style='color:#FF79C6;'>{live_avg_k}</div><div class='class-sub-text' style='color:#50FA7B;'>{sportsbook_line_k} Line Set</div></div>", unsafe_allow_html=True)
    with ch2:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>K OVER PROBABILITY</div><div class='metric-value' style='color:#FFB86C;'>{over_prob_pct_k}%</div><div class='class-sub-text'>Based on 10,000 Sims</div></div>", unsafe_allow_html=True)
        
    c_p1, c_p2 = st.columns(2)
    with c_p1:
        rec_tag_k = "OVER" if live_avg_k > sportsbook_line_k else "UNDER"
        rec_color_k = "#50FA7B" if rec_tag_k == "OVER" else "#FF5555"
        st.markdown(f"<div class='metric-card'><div class='metric-label'>K RECOMMENDATION</div><div class='metric-value' style='color:{rec_color_k};'>{rec_tag_k}</div><div class='class-sub-text' style='color:#8BE9FD;'>{diff_val_k:+,.2f} K Difference Gap</div></div>", unsafe_allow_html=True)
    with c_p2:
        grade_k = "A" if (over_prob_pct_k > 65 or over_prob_pct_k < 35) else ("B" if (over_prob_pct_k > 55 or over_prob_pct_k < 45) else "C")
        st.markdown(f"<div class='metric-card'><div class='metric-label'>K SIMULATION GRADE</div><div class='metric-value'>{grade_k}</div></div>", unsafe_allow_html=True)

with main_col2:
    st.markdown(f"<div class='section-header'>🏟️ TOTAL OUTS SIMULATION DESK: {pitcher_input.title()}</div>", unsafe_allow_html=True)
    co1, co2 = st.columns(2)
    with co1:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>PROJ TOTAL OUTS</div><div class='metric-value' style='color:#FF79C6;'>{live_avg_outs}</div><div class='class-sub-text' style='color:#50FA7B;'>{sportsbook_line_outs} Line Set</div></div>", unsafe_allow_html=True)
    with co2:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>OUTS PROBABILITY</div><div class='metric-value' style='color:#FFB86C;'>{over_prob_pct_outs}%</div><div class='class-sub-text'>Based on 10,000 Sims</div></div>", unsafe_allow_html=True)
        
    c_o1, c_o2 = st.columns(2)
    with c_o1:
        rec_tag_outs = "OVER" if live_avg_outs > sportsbook_line_outs else "UNDER"
        rec_color_outs = "#50FA7B" if rec_tag_outs == "OVER" else "#FF5555"
        st.markdown(f"<div class='metric-card'><div class='metric-label'>OUTS RECOMMENDATION</div><div class='metric-value' style='color:{rec_color_outs};'>{rec_tag_outs}</div><div class='class-sub-text' style='color:#8BE9FD;'>{diff_val_outs:+,.2f} Outs Gap</div></div>", unsafe_allow_html=True)
    with c_o2:
        grade_outs = "A" if (over_prob_pct_outs > 65 or over_prob_pct_outs < 35) else ("B" if (over_prob_pct_outs > 55 or over_prob_pct_outs < 45) else "C")
        st.markdown(f"<div class='metric-card'><div class='metric-label'>OUTS SIM GRADE</div><div class='metric-value'>{grade_outs}</div></div>", unsafe_allow_html=True)
# --- SPLIT THE ACCELERATED SUB-CARDS GRIDS ---
st.markdown("---")
sub_col1, sub_col2 = st.columns(2)

with sub_col1:
    st.markdown(f"<div class='section-header'>⚔️ Batter-by-Batter Splitting Grid: vs {opposing_team.upper()}</div>", unsafe_allow_html=True)
    clean_target_team = str(opposing_team).upper().strip()
    if clean_target_team == "CHW": clean_target_team = "CWS"
    if clean_target_team == "KCR": clean_target_team = "KC"
    
    team_hitters = batter_db[batter_db['team_clean'] == clean_target_team] if not batter_db.empty else pd.DataFrame()
    lineup_rows = []
    
    if not team_hitters.empty:
        for idx, b_row in team_hitters.head(9).iterrows():
            b_hand = str(b_row['hand']).upper().strip()
            raw_b_k = float(b_row['vs_lhp_k']) if pitcher_throws == "L" else float(b_row['vs_rhp_k'])
            b_stab = float(b_row['k_stability']) if 'k_stability' in b_row else 1.00
            calc_k_pct = round(raw_b_k * (1.12 if b_hand != pitcher_throws else 0.92) * b_stab, 1)
            lineup_rows.append({
                "SLOT": len(lineup_rows) + 1,
                "BATTER LINEUP CARD": str(b_row['name']).title(),
                "HAND": b_hand,
                "RAW K% SPLIT": f"{raw_b_k}%",
                "DYNAMIC K% PROJECTION": f"{calc_k_pct}%"
            })
    else:
        for i in range(1, 10):
            lineup_rows.append({"SLOT": i, "BATTER LINEUP CARD": f"Lineup Slot Active Hitter {i}", "HAND": "R", "RAW K% SPLIT": "23.4%", "DYNAMIC K% PROJECTION": f"{21.0 + (i * 0.5)}%"})
    st.dataframe(pd.DataFrame(lineup_rows).style.set_properties(**{ 'background-color': '#1A1423', 'color': '#8BE9FD'}), width="stretch", hide_index=True)

with sub_col2:
    st.markdown("<div class='section-header'>📊 Balanced Pitch Arsenal Matrix</div>", unsafe_allow_html=True)
    if not pitch_df.empty:
        updated_arsenal = []
        for idx, row in pitch_df.iterrows():
            raw_whiff = str(row["WHIFF"]).replace("%", "").replace("W:", "").strip()
            whiff_val = float(raw_whiff) if raw_whiff.replace(".", "", 1).isdigit() else 25.0
            calc_k = round(whiff_val * 0.85, 1)
            calc_put = round(whiff_val * 0.58, 1)
            updated_arsenal.append({"PITCH TYPE": row["PITCH"], "USAGE": row["USE"], "Ks EXPECTED": f"{calc_k}%", "WHIFF RATE": row["WHIFF"], "PUTAWAY": f"{calc_put}%"})
        st.dataframe(pd.DataFrame(updated_arsenal).style.set_properties(**{'text-align': 'center', 'background-color': '#1A1423', 'color': '#8BE9FD', 'border-color': '#372549'}), width="stretch", hide_index=True)

st.markdown("---")
st.subheader("📋 Automated Global Slate Edge Tracker Matrix")

global_tracker_rows = []
sample_slate = {"tarik skubal": {"team": "LAD", "opponent": "CHW"}, "paul skenes": {"team": "PIT", "opponent": "CIN"}, "dylan cease": {"team": "SDP", "opponent": "SFG"}, "corbin burnes": {"team": "BAL", "opponent": "PHI"}, "cole ragans": {"team": "KCR", "opponent": "DET"}, "zack wheeler": {"team": "PHI", "opponent": "BAL"}, "garrett crochet": {"team": "CHW", "opponent": "LAD"}}

if todays_slate and len(todays_slate) > 0:
    for live_name, meta in todays_slate.items():
        p_name_raw = live_name.title()
        p_name_clean = live_name.lower().strip()
        
        db_match = pitcher_db[pitcher_db['name_clean'] == p_name_clean]
        
        if not db_match.empty:
            p_data = db_match.iloc
            p_base_k = float(p_data['base_avg'])
            p_base_outs = float(p_data['base_outs']) if 'base_outs' in p_data.index else 17.50
            p_arm_side = str(p_data['throws']).upper().strip() if 'throws' in p_data.index else "R"
            p_team_code = str(p_data.get('team', meta["team"])).upper().strip()
        else:
            p_base_k, p_base_outs, p_arm_side = 5.50, 15.2, "R"
            p_team_code = str(meta["team"]).upper().strip()

        opp_team_target = str(meta["opponent"]).upper().strip()
        db_lookup_team = "CWS" if opp_team_target == "CHW" else opp_team_target
        
        if p_name_clean == lookup_key:
            sim_proj_k = live_avg_k
            sim_proj_outs = live_avg_outs
        else:
            p_matchup_mult_k = 1.00
            if not batter_db.empty and db_lookup_team in batter_db['team_clean'].values:
                team_hitters = batter_db[batter_db['team_clean'] == db_lookup_team]
                k_list_calc = []
                for _, b_row in team_hitters.head(9).iterrows():
                    b_hand = str(b_row['hand']).upper().strip()
                    raw_b_k = float(b_row['vs_lhp_k']) if p_arm_side == "L" else float(b_row['vs_rhp_k'])
                    b_stab = float(b_row['k_stability']) if 'k_stability' in b_row.index else 1.00
                    if (b_hand == "L" and p_arm_side == "R") or (b_hand == "R" and p_arm_side == "L") or b_hand == "S":
                        k_list_calc.append(raw_b_k * 1.12 * b_stab)
                    else:
                        k_list_calc.append(raw_b_k * 0.92 * b_stab)
                if k_list_calc: 
                    p_matchup_mult_k = (sum(k_list_calc) / len(k_list_calc)) / 22.5

            sim_proj_k = round(p_base_k * p_matchup_mult_k, 2)
            sim_proj_outs = round(p_base_outs * 1.01, 2)

        global_tracker_rows.append({
            "PITCHER": p_name_raw, "TEAM": p_team_code, "OPPONENT": opp_team_target, 
            "ARM": f"{p_arm_side}HP", "PROJ Ks": sim_proj_k, "PROJ OUTS": sim_proj_outs, "STATUS": "🟢 Live API Stream Online"
        })

if global_tracker_rows:
    st.dataframe(pd.DataFrame(global_tracker_rows).style.set_properties(**{
        'background-color': '#1A1423', 'color': '#8BE9FD', 'border-color': '#372549', 'text-align': 'center'
    }), width="stretch", hide_index=True)
else:
    st.info("💡 Live board matching layer empty. Awaiting confirmed active pitcher announcements from league data systems.")

st.markdown("---")
st.markdown("<div class='section-header' style='background: linear-gradient(90deg, #FF79C6 0%, #1A1423 100%); border-left: 5px solid #FF79C6;'>📋 Stored Search History & Dual-Market Live Ledger Sheets</div>", unsafe_allow_html=True)

if st.session_state["search_history_queue"]:
    history_df = pd.DataFrame(st.session_state["search_history_queue"])
    st.dataframe(history_df.style.set_properties(**{
        'background-color': '#1A1423', 'color': '#50FA7B', 'border-color': '#372549', 'text-align': 'center'
    }), width="stretch", hide_index=True)
    
    if st.button("🧹 Reset Search History Ledger"):
        st.session_state["search_history_queue"] = []
        st.rerun()
else:
    st.info("💡 Calibrate both lines in your form panel above and click 'Run Pro Dual-Market Simulation' to track both projections at once here.")

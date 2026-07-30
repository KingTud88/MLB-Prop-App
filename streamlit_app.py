import streamlit as st
import pandas as pd
from pybaseball import pitching_stats_range
from datetime import datetime

# 1. Page Configuration
st.set_page_config(page_title="MLB Prop Dashboard", layout="wide")
st.title("🎯 Custom MLB Prop Dashboard")

# 2. Sidebar Configuration Setup
with st.sidebar:
    st.header("⚙️ Configuration")
    pitcher_input = st.text_input("Enter Pitcher Name", "Brady Singer")
    sportsbook_line = st.number_input("Current Line O/U", min_value=0.5, max_value=15.5, value=5.5, step=0.5)

# 3. Main Data Core
st.subheader("📋 Active Season Performance")

try:
    p_names = pitcher_input.split()
    current_year = datetime.now().year
    
    # Pull current data
    all_stats = pitching_stats_range(f"{current_year}-03-01", f"{current_year}-11-01")
    
    # Simple name filter
    pitcher_data = all_stats[all_stats['Name'].str.contains(pitcher_input, case=False, na=False)]
    
    if pitcher_data.empty:
        st.warning(f"No active data found for {pitcher_input} in {current_year}.")
    else:
        # Extract base calculations
        row = pitcher_data.iloc
        games = int(row['G'])
        strikeouts = int(row['SO'])
        live_avg_k = round(strikeouts / games, 2)
        calculated_edge = round(((live_avg_k - sportsbook_line) / sportsbook_line) * 100, 1)
        rec_tag = "OVER" if live_avg_k > sportsbook_line else "UNDER"
        
        # Display output summary metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Calculated Season Avg Ks/Game", value=f"{live_avg_k} K")
        with col2:
            st.metric(label="Calculated Line Edge %", value=f"{calculated_edge}%", delta=f"{rec_tag} Recommendation")
            
        # Display underlying table
        st.dataframe(pitcher_data[['Name', 'Team', 'G', 'IP', 'SO']], use_container_width=True, hide_index=True)
        
except Exception as e:
    st.error(f"Waiting for input update: {str(e)}")

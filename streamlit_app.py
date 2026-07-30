import streamlit as st
import pandas as pd

# 1. Setup the visual layout (Dark theme & title)
st.set_page_config(page_title="Prop Analytics Dashboard", layout="wide")
st.title("🎯 Custom MLB Prop Dashboard")

# 2. Create the sidebar navigation (Exactly like your screenshot)
with st.sidebar:
    st.header("⚙️ Configuration")
    sport = st.selectbox("Select League", ["MLB", "NBA", "NFL"])
    market = st.selectbox("Market Type", ["Strikeouts (Ks)", "Total Bases", "Hits Allowed"])
    st.slider("Model Weight: Pitcher Stats", 0, 100, 60)
    st.slider("Model Weight: Batter Matchup", 0, 100, 40)

# 3. Create the Main Layout Columns
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📋 Active Projections")
    # Mock data to replicate his interface layout
    prop_data = {
        "Pitcher": ["Brady Singer", "Shane Drohan", "Paul Skenes"],
        "Line": [5.5, 4.5, 6.5],
        "Proj K": [4.82, 3.33, 7.15],
        "Edge %": ["-12.3%", "-26.0%", "+10.0%"],
        "Recommendation": ["UNDER", "UNDER", "OVER"]
    }
    df = pd.DataFrame(prop_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

with col2:
    st.subheader("⚔️ Batter-by-Batter Matchup Simulation")
    
    # Replicating his specific batter matchup matrix table
    batter_data = {
        "Order":,
        "Batter Name": ["Steven Kwan", "José Ramírez", "Josh Naylor", "Andrés Giménez"],
        "Hand": ["L", "S", "L", "L"],
        "Season K%": ["9.2%", "11.5%", "18.1%", "20.4%"],
        "Simulated K Prob": ["4.1%", "6.3%", "14.2%", "17.9%"]
    }
    df_batters = pd.DataFrame(batter_data)
    st.table(df_batters)
    
    st.success("🤖 Savant Trend: Opposing lineup has an overall K rate 4.2% below league average.")

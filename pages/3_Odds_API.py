from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Odds API", page_icon="💰", layout="wide")
st.title("💰 Odds API")
st.info("The Odds API has been merged into the Projection page. You can now see the 3+ through 10+ strikeout ladder and live sportsbook lines without leaving StrikeOut King.")
if st.button("Open Projection", type="primary"):
    st.switch_page("streamlit_app.py")

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
TRACKER_PATH = APP_DIR / "data" / "bet_log.csv"

st.set_page_config(page_title="Bet Tracker", page_icon="📊", layout="wide")

st.title("📊 Bet Tracker")
st.caption("Saved manual sportsbook analyses. Confidence remains provisional until historical calibration is available.")

if not TRACKER_PATH.exists():
    st.info("No saved bets yet. Analyze a sportsbook line in PitchLab Pro and click Save to bet tracker.")
    st.stop()

tracker = pd.read_csv(TRACKER_PATH)
if tracker.empty:
    st.info("The tracker file exists, but it has no saved bets yet.")
    st.stop()

tracker["model_probability"] = pd.to_numeric(tracker.get("model_probability"), errors="coerce")
tracker["implied_probability"] = pd.to_numeric(tracker.get("implied_probability"), errors="coerce")
tracker["edge"] = pd.to_numeric(tracker.get("edge"), errors="coerce")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Tracked bets", len(tracker))
c2.metric("Average model probability", f"{tracker['model_probability'].mean():.1%}")
c3.metric("Average edge", f"{tracker['edge'].mean():+.1%}")
c4.metric("Positive-edge bets", f"{(tracker['edge'] > 0).sum()} / {len(tracker)}")

st.subheader("Saved bets")
show = tracker.copy()
if "entered_at_utc" in show:
    show = show.sort_values("entered_at_utc", ascending=False)

columns = [
    "player", "game_date", "side", "line", "american_odds",
    "projection", "model_probability", "implied_probability", "edge",
    "confidence", "actual_strikeouts",
]
columns = [c for c in columns if c in show.columns]
st.dataframe(
    show[columns].style.format({
        "model_probability": "{:.1%}",
        "implied_probability": "{:.1%}",
        "edge": "{:+.1%}",
        "projection": "{:.2f}",
    }),
    hide_index=True,
    use_container_width=True,
)

st.download_button(
    "Download bet tracker CSV",
    tracker.to_csv(index=False),
    file_name="bet_tracker.csv",
    mime="text/csv",
)

st.info("Next upgrade: result entry and automatic win/loss, ROI, and confidence-bucket performance once we have enough tracked plays.")

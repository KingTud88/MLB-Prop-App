from __future__ import annotations

import requests
import pandas as pd
import streamlit as st
from training.github_bet_store import load_bets

MLB_API = "https://statsapi.mlb.com/api/v1"

st.set_page_config(page_title="Bet Tracker", page_icon="📊", layout="wide")
st.title("📊 Bet Tracker")
st.caption("Persistent bets with live strikeout progress from MLB game data.")

@st.cache_data(ttl=30, show_spinner=False)
def live_strikeouts(game_pk: int, pitcher_id: int) -> tuple[float | None, str]:
    try:
        response = requests.get(f"{MLB_API}/game/{int(game_pk)}/feed/live", timeout=10)
        response.raise_for_status()
        data = response.json()
        status = data.get("gameData", {}).get("status", {}).get("abstractGameState") or data.get("gameData", {}).get("status", {}).get("detailedState") or "Unknown"
        players = {}
        for side in ("away", "home"):
            players.update(data.get("liveData", {}).get("boxscore", {}).get("teams", {}).get(side, {}).get("players", {}))
        player = players.get(f"ID{int(pitcher_id)}")
        if not player:
            return None, status
        ks = player.get("stats", {}).get("pitching", {}).get("strikeOuts")
        return (float(ks) if ks is not None else 0.0), status
    except Exception as exc:
        return None, f"Live lookup unavailable: {exc}"

try:
    records = load_bets()
except Exception as exc:
    st.error(f"Could not load the persistent bet tracker: {exc}")
    st.stop()

tracker = pd.DataFrame(records)
if tracker.empty:
    st.info("No saved bets yet. Analyze a sportsbook line in StrikeOut King 9000 and click Save to bet tracker.")
    st.stop()

for col in ["model_probability", "implied_probability", "edge", "line", "projection", "actual_strikeouts", "game_pk", "pitcher_id"]:
    if col in tracker:
        tracker[col] = pd.to_numeric(tracker[col], errors="coerce")

c1,c2,c3,c4=st.columns(4)
c1.metric("Tracked bets",len(tracker))
c2.metric("Average model probability",f"{tracker['model_probability'].mean():.1%}")
c3.metric("Average edge",f"{tracker['edge'].mean():+.1%}")
c4.metric("Positive-edge bets",f"{(tracker['edge']>0).sum()} / {len(tracker)}")

st.subheader("Live bet progress")
st.caption("The bar uses the exact MLB game and pitcher saved with the bet. Refresh during the game for the latest strikeout count.")
if st.button("🔄 Refresh live results", type="primary"):
    live_strikeouts.clear()
    st.rerun()

for idx,row in tracker.sort_values("entered_at_utc",ascending=False).iterrows():
    player=str(row.get("player","Unknown")); side=str(row.get("side","Over")).title(); line=float(row.get("line",0)); game_pk=row.get("game_pk"); pitcher_id=row.get("pitcher_id"); actual=None; status="Saved"
    if pd.notna(game_pk) and pd.notna(pitcher_id):
        actual,status=live_strikeouts(int(game_pk),int(pitcher_id))
    current=float(actual) if actual is not None else 0.0
    progress=min(max(current/max(line,0.5),0.0),1.0)
    st.markdown(f"### {player} — {side} {line:g}")
    st.progress(progress,text=f"{int(current)} Ks / {line:g} line")
    if actual is None:
        st.caption(f"{status}. Live progress will appear once MLB has game data for this pitcher.")
    elif status == "Final":
        won=(current > line) if side == "Over" else (current < line)
        st.write(f"Final: **{int(current)} Ks** · **{'WIN' if won else 'LOSS'}**")
    else:
        ahead=(current > line) if side == "Over" else (current < line)
        st.write(f"Live: **{int(current)} Ks** · {status} · {'Currently ahead' if ahead else 'Currently behind'}")
    st.divider()

st.subheader("Saved bets")
show=tracker.sort_values("entered_at_utc",ascending=False).copy() if "entered_at_utc" in tracker else tracker.copy()
columns=["player","game_date","side","line","american_odds","projection","model_probability","implied_probability","edge","confidence","actual_strikeouts"]
columns=[c for c in columns if c in show.columns]
st.dataframe(show[columns].style.format({"model_probability":"{:.1%}","implied_probability":"{:.1%}","edge":"{:+.1%}","projection":"{:.2f}"}),hide_index=True,use_container_width=True)
st.download_button("Download bet tracker CSV",tracker.to_csv(index=False),file_name="bet_tracker.csv",mime="text/csv")
st.info("Confidence remains provisional until historical sportsbook lines are available for calibration.")

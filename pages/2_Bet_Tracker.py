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
def live_strikeouts(player_name: str, game_date: str, game_pk: int | None = None, pitcher_id: int | None = None) -> tuple[float | None, str]:
    try:
        target = player_name.strip().lower()
        candidates = []

        # First use the saved game if it exists and is valid.
        if game_pk and pitcher_id:
            candidates.append((int(game_pk), int(pitcher_id)))

        # Always resolve the saved pitcher/date through MLB's schedule as a fallback.
        schedule = requests.get(
            f"{MLB_API}/schedule",
            params={"sportId": 1, "date": game_date, "hydrate": "probablePitcher,team"},
            timeout=10,
        )
        schedule.raise_for_status()
        for block in schedule.json().get("dates", []):
            for game in block.get("games", []):
                for side in ("away", "home"):
                    pitcher = game.get("teams", {}).get(side, {}).get("probablePitcher", {}) or {}
                    name = pitcher.get("fullName", "").strip().lower()
                    if name == target and game.get("gamePk"):
                        pair = (int(game["gamePk"]), int(pitcher.get("id", 0) or 0))
                        if pair not in candidates:
                            candidates.append(pair)

        if not candidates:
            return None, "No MLB game found for this pitcher on the saved date."

        # Prefer a candidate whose live feed is available.
        last_status = "Scheduled"
        for candidate_game_pk, candidate_pitcher_id in candidates:
            response = requests.get(f"{MLB_API}/game/{candidate_game_pk}/feed/live", timeout=10)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            data = response.json()
            status = data.get("gameData", {}).get("status", {}).get("abstractGameState") or data.get("gameData", {}).get("status", {}).get("detailedState") or "Unknown"
            last_status = status
            players = {}
            for side in ("away", "home"):
                players.update(data.get("liveData", {}).get("boxscore", {}).get("teams", {}).get(side, {}).get("players", {}))
            player = players.get(f"ID{candidate_pitcher_id}") if candidate_pitcher_id else None
            if not player:
                for value in players.values():
                    if value.get("person", {}).get("fullName", "").strip().lower() == target:
                        player = value
                        break
            if not player:
                continue
            stats = player.get("stats", {}).get("pitching", {})
            ks = stats.get("strikeOuts")
            if ks is not None:
                return float(ks), status

        return None, f"Game found, but MLB has not posted pitching stats yet ({last_status})."
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
st.caption("The bar resolves the saved pitcher and game through MLB. Refresh during the game for the latest strikeout count.")
if st.button("🔄 Refresh live results", type="primary"):
    live_strikeouts.clear()
    st.rerun()

for idx,row in tracker.sort_values("entered_at_utc",ascending=False).iterrows():
    player=str(row.get("player","Unknown")); side=str(row.get("side","Over")).title(); line=float(row.get("line",0)); game_pk=row.get("game_pk"); pitcher_id=row.get("pitcher_id"); game_date=str(row.get("game_date", ""))[:10]
    game_pk_value=int(game_pk) if pd.notna(game_pk) else None
    pitcher_id_value=int(pitcher_id) if pd.notna(pitcher_id) else None
    actual,status=live_strikeouts(player,game_date,game_pk_value,pitcher_id_value)
    current=float(actual) if actual is not None else 0.0
    progress=min(max(current/max(line,0.5),0.0),1.0)
    st.markdown(f"### {player} — {side} {line:g}")
    st.progress(progress,text=f"{int(current)} Ks / {line:g} line")
    if actual is None:
        st.caption(f"{status}")
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

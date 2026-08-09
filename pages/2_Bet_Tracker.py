from __future__ import annotations

from datetime import date
import requests

import pandas as pd
import streamlit as st

from training.github_bet_store import load_bets

MLB_API = "https://statsapi.mlb.com/api/v1"

st.set_page_config(page_title="Bet Tracker", page_icon="📊", layout="wide")

st.title("📊 Bet Tracker")
st.caption("Saved manual sportsbook analyses with live strikeout progress when MLB game data is available.")

try:
    records = load_bets()
except Exception as exc:
    st.error(f"Could not load the persistent bet tracker: {exc}")
    st.stop()

tracker = pd.DataFrame(records)
if tracker.empty:
    st.info("No saved bets yet. Analyze a sportsbook line in StrikeOut King 9000 and click Save to bet tracker.")
    st.stop()

for col in ["model_probability", "implied_probability", "edge", "line", "projection", "actual_strikeouts"]:
    if col in tracker:
        tracker[col] = pd.to_numeric(tracker[col], errors="coerce")


def fetch_live_strikeouts(player_name: str, game_date: str) -> tuple[float | None, str]:
    try:
        games_resp = requests.get(
            f"{MLB_API}/schedule",
            params={"sportId": 1, "date": game_date, "hydrate": "game(content(summary))"},
            timeout=8,
        )
        games_resp.raise_for_status()
        dates = games_resp.json().get("dates", [])
        if not dates:
            return None, "No MLB games found for this date."

        target = player_name.strip().lower()
        for game in dates[0].get("games", []):
            status = game.get("status", {}).get("abstractGameState", "")
            if status not in {"Preview", "Live", "Final"}:
                continue
            game_pk = game.get("gamePk")
            if not game_pk:
                continue
            feed = requests.get(f"{MLB_API}/game/{game_pk}/feed/live", timeout=8)
            feed.raise_for_status()
            data = feed.json()
            teams = data.get("liveData", {}).get("boxscore", {}).get("teams", {})
            for team_key in ("away", "home"):
                pitchers = teams.get(team_key, {}).get("players", {})
                for player in pitchers.values():
                    person = player.get("person", {})
                    if person.get("fullName", "").strip().lower() == target:
                        stats = player.get("stats", {}).get("pitching", {})
                        ks = stats.get("strikeOuts")
                        if ks is not None:
                            return float(ks), status
        return None, "Game not found or pitcher has not appeared yet."
    except Exception as exc:
        return None, f"Live lookup unavailable: {exc}"


c1, c2, c3, c4 = st.columns(4)
c1.metric("Tracked bets", len(tracker))
c2.metric("Average model probability", f"{tracker['model_probability'].mean():.1%}")
c3.metric("Average edge", f"{tracker['edge'].mean():+.1%}")
c4.metric("Positive-edge bets", f"{(tracker['edge'] > 0).sum()} / {len(tracker)}")

st.subheader("Live bet progress")
st.caption("Refresh while the game is live. The bar tracks actual strikeouts against your sportsbook line.")
if st.button("🔄 Refresh live results", type="primary"):
    st.rerun()

for idx, row in tracker.sort_values("entered_at_utc", ascending=False).iterrows():
    player = str(row.get("player", "Unknown"))
    side = str(row.get("side", "Over")).title()
    line = float(row.get("line", 0))
    game_date = str(row.get("game_date", ""))[:10]
    actual = row.get("actual_strikeouts")

    if pd.isna(actual):
        actual, status = fetch_live_strikeouts(player, game_date)
    else:
        status = "Saved"

    if actual is not None:
        tracker.loc[idx, "actual_strikeouts"] = actual

    progress_target = max(line, 0.5)
    progress = min(max((float(actual) if actual is not None else 0.0) / progress_target, 0.0), 1.0)
    hit = actual is not None and ((side == "Over" and actual > line) or (side == "Under" and actual < line))

    st.markdown(f"**{player} — {side} {line:g}**")
    st.progress(progress, text=f"{int(actual) if actual is not None else 0} Ks / {line:g} line")
    if actual is not None:
        if status == "Final":
            result = "WIN" if hit else "LOSS"
            st.write(f"Final: **{int(actual)} Ks** · **{result}**")
        else:
            st.write(f"Live: **{int(actual)} Ks** · {status}")
    else:
        st.caption(status)
    st.divider()

st.subheader("Saved bets")
show = tracker.sort_values("entered_at_utc", ascending=False).copy() if "entered_at_utc" in tracker else tracker.copy()
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

st.info("Confidence remains provisional until historical sportsbook lines are available for calibration.")

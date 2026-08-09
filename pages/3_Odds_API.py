from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from training.odds_api import (
    OddsAPIError,
    flatten_pitcher_strikeouts,
    get_api_key,
    get_event_pitcher_strikeouts,
    get_events,
    usage_summary,
)

st.set_page_config(page_title="Odds API", page_icon="💰", layout="wide")
st.title("💰 Odds API")
st.caption("Current MLB pitcher strikeout markets from The Odds API. This feed is optional and never changes the baseball projection itself.")

api_key = get_api_key(st.secrets)
if not api_key:
    st.warning("Odds API is not connected yet.")
    st.markdown("Add your key as a Streamlit secret named `ODDS_API_KEY` (or as an environment variable with that name). Never paste the key into GitHub code.")
    st.stop()

selected_date = st.date_input("Game date", value=date.today())
region = st.selectbox("Bookmaker region", ["us", "us2"], index=0)

if "odds_events" not in st.session_state or st.session_state.get("odds_events_date") != selected_date:
    try:
        events, event_headers = get_events(api_key, selected_date)
        st.session_state["odds_events"] = events
        st.session_state["odds_events_date"] = selected_date
        st.session_state["odds_event_headers"] = event_headers
    except OddsAPIError as exc:
        st.error(str(exc))
        st.stop()

events = st.session_state["odds_events"]
if not events:
    st.info("No Odds API MLB events were returned for this date.")
    st.stop()

options = {
    e["id"]: f"{e.get('away_team', '?')} @ {e.get('home_team', '?')} · {e.get('commence_time', '')}"
    for e in events
}
selected_event_id = st.selectbox("MLB game", list(options), format_func=lambda key: options[key])

if st.button("Fetch pitcher strikeout odds", type="primary"):
    try:
        event, headers = get_event_pitcher_strikeouts(api_key, selected_event_id, region)
        st.session_state["selected_odds_event"] = event
        st.session_state["selected_odds_headers"] = headers
    except OddsAPIError as exc:
        st.error(str(exc))
        st.stop()

event = st.session_state.get("selected_odds_event")
if not event:
    st.info("Choose a game and fetch its pitcher strikeout market. The events lookup itself does not use monthly credits.")
    st.stop()

usage = usage_summary(st.session_state.get("selected_odds_headers", {}))
u1, u2, u3 = st.columns(3)
u1.metric("Credits remaining", usage["remaining"])
u2.metric("Credits used", usage["used"])
u3.metric("Last request cost", usage["last_cost"])

rows = flatten_pitcher_strikeouts(event)
if not rows:
    st.warning("The selected game currently has no pitcher strikeout market from the returned bookmakers. Try again closer to game time or choose another game.")
    st.stop()

frame = pd.DataFrame(rows)
st.subheader("Pitcher strikeout markets")
st.dataframe(
    frame[["bookmaker", "player", "side", "line", "american_odds", "last_update"]],
    hide_index=True,
    use_container_width=True,
)

players = sorted(frame["player"].dropna().unique().tolist())
if players:
    player = st.selectbox("Pitcher to use in StrikeOut King", players)
    player_rows = frame[frame["player"] == player].copy()
    player_rows["label"] = player_rows.apply(
        lambda r: f"{r['bookmaker']} · {r['side']} {r['line']} @ {int(r['american_odds']):+d}", axis=1
    )
    choice = st.selectbox("Sportsbook line", player_rows.index, format_func=lambda i: player_rows.loc[i, "label"])
    selected = player_rows.loc[choice]
    if st.button("Use this line in StrikeOut King", type="primary"):
        # Keep the selected Odds API pitcher and market in Streamlit session state
        # so the main StrikeOut King page can automatically load the same pitcher.
        st.session_state["manual_side"] = str(selected["side"])
        st.session_state["manual_line"] = float(selected["line"])
        st.session_state["manual_odds"] = int(selected["american_odds"])
        st.session_state["odds_selected_pitcher"] = str(selected["player"])
        st.session_state["odds_selected_date"] = selected_date.isoformat()
        st.session_state["odds_selected_event_id"] = str(selected_event_id)
        st.success(
            f"Loaded {selected['player']} — {selected['side']} {selected['line']} at {int(selected['american_odds']):+d}. "
            "Go back to StrikeOut King 9000 and click Analyze line. The pitcher and sportsbook line will now carry over."
        )

st.caption("The Odds API currently lists MLB pitcher strikeouts as `pitcher_strikeouts`. Player props are queried one event at a time, so we deliberately avoid polling the entire slate to conserve the 500-credit free allowance.")

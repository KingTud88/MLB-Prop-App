from pathlib import Path

path = Path("pages/6_Top_Plays.py")
text = path.read_text(encoding="utf-8")

old = '''st.markdown("#### Add a Top Play to Bet Tracker")
quick_stake = st.number_input("Quick-add stake", min_value=0.0, value=1.0, step=0.5, key="top_plays_quick_stake")
button_cols = st.columns(len(plays))
for button_idx, (_, play_row) in enumerate(plays.iterrows()):
    snapshot = find_snapshot(history, play_row)
    snapshot_dict = snapshot.to_dict() if snapshot is not None else None
    projection_value = projection_for_market(snapshot_dict, play_row.get("Market")) if snapshot_dict else None
    with button_cols[button_idx]:
        st.caption(f"#{int(play_row['Rank'])} {play_row['Pitcher']} · {play_row['Side']} {float(play_row['Line']):g}")
        if st.button("➕ Add as bet", key=f"add_top_play_{int(play_row['Rank'])}", use_container_width=True):
            try:
                game_pk = numeric(play_row.get("Game PK"))
                pitcher_id = numeric(play_row.get("Pitcher ID"))
                record = make_bet_record(
                    player=str(play_row["Pitcher"]),
                    market=play_row["Market"],
                    game_date=str(snapshot.get("game_date", today) if snapshot is not None else today),
                    line=float(play_row["Line"]),
                    side=str(play_row["Side"]),
                    american_odds=float(play_row["Odds"]),
                    stake=float(quick_stake),
                    book=str(play_row.get("Book", "")),
                    projection=projection_value,
                    model_probability=float(play_row["Model Probability"]),
                    implied_probability=float(play_row["No-Vig Implied"]),
                    edge=float(play_row["Edge"]),
                    confidence=(snapshot.get("confidence", "") if snapshot is not None else ""),
                    game_pk=None if game_pk is None else int(game_pk),
                    pitcher_id=None if pitcher_id is None else int(pitcher_id),
                )
                append_bet(BET_LOG, record, st.secrets)
                st.success("Added")
            except Exception as exc:
                st.error(f"Could not add bet: {exc}")

try:
    selected_rows = list(event.selection.rows)
except Exception:
    selected_rows = list((event.get("selection", {}) or {}).get("rows", [])) if isinstance(event, dict) else []

if selected_rows:
    idx = int(selected_rows[0])
    if 0 <= idx < len(plays):
        play = plays.iloc[idx]
        snapshot = find_snapshot(history, play)
        if snapshot is not None:
            render_projection_rationale(play, snapshot, history)
        else:
            st.warning("The frozen projection snapshot for this ranked leg could not be matched in the history log.")
'''

new = '''st.markdown("#### Top Play actions")
st.caption("Quick-add stake is the amount recorded in Bet Tracker for P/L and ROI. It does not place a sportsbook wager and it does not affect the projection model.")
quick_stake = st.number_input("Quick-add stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_quick_stake")
button_cols = st.columns(len(plays))
for button_idx, (_, play_row) in enumerate(plays.iterrows()):
    snapshot = find_snapshot(history, play_row)
    snapshot_dict = snapshot.to_dict() if snapshot is not None else None
    projection_value = projection_for_market(snapshot_dict, play_row.get("Market")) if snapshot_dict else None
    with button_cols[button_idx]:
        rank = int(play_row["Rank"])
        st.caption(f"#{rank} {play_row['Pitcher']} · {play_row['Side']} {float(play_row['Line']):g}")
        if st.button("🔎 View details", key=f"view_top_play_{rank}", use_container_width=True):
            st.session_state["top_play_detail_rank"] = rank
        if st.button("➕ Add as bet", key=f"add_top_play_{rank}", use_container_width=True):
            try:
                game_pk = numeric(play_row.get("Game PK"))
                pitcher_id = numeric(play_row.get("Pitcher ID"))
                record = make_bet_record(
                    player=str(play_row["Pitcher"]),
                    market=play_row["Market"],
                    game_date=str(snapshot.get("game_date", today) if snapshot is not None else today),
                    line=float(play_row["Line"]),
                    side=str(play_row["Side"]),
                    american_odds=float(play_row["Odds"]),
                    stake=float(quick_stake),
                    book=str(play_row.get("Book", "")),
                    projection=projection_value,
                    model_probability=float(play_row["Model Probability"]),
                    implied_probability=float(play_row["No-Vig Implied"]),
                    edge=float(play_row["Edge"]),
                    confidence=(snapshot.get("confidence", "") if snapshot is not None else ""),
                    game_pk=None if game_pk is None else int(game_pk),
                    pitcher_id=None if pitcher_id is None else int(pitcher_id),
                )
                append_bet(BET_LOG, record, st.secrets)
                st.success("Added to Bet Tracker")
            except Exception as exc:
                st.error(f"Could not add bet: {exc}")

selected_rank = st.session_state.get("top_play_detail_rank")
try:
    selected_rows = list(event.selection.rows)
except Exception:
    selected_rows = list((event.get("selection", {}) or {}).get("rows", [])) if isinstance(event, dict) else []
if selected_rows:
    idx = int(selected_rows[0])
    if 0 <= idx < len(plays):
        selected_rank = int(plays.iloc[idx]["Rank"])
        st.session_state["top_play_detail_rank"] = selected_rank

if selected_rank is not None:
    matched = plays.loc[pd.to_numeric(plays["Rank"], errors="coerce").eq(float(selected_rank))]
    if not matched.empty:
        play = matched.iloc[0]
        snapshot = find_snapshot(history, play)
        if snapshot is not None:
            render_projection_rationale(play, snapshot, history)
        else:
            st.warning("The frozen projection snapshot for this ranked leg could not be matched in the history log.")
'''

if old not in text:
    raise SystemExit("Top Plays action block anchor not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

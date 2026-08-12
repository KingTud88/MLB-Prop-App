from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


page = Path("pages/4_Projection_History.py")
text = page.read_text(encoding="utf-8")

old = '''archive_formats = {}
for col in ["projection", "hits_projection", "outs_projection", "k_target_margin", "k_error", "hits_error", "outs_error"]:
    if col in archive_view.columns:
        archive_formats[col] = "{:+.2f}" if col.endswith("_error") else "{:+.0f}" if col == "k_target_margin" else "{:.2f}"
for col in ["actual_strikeouts", "actual_hits_allowed", "actual_outs", "k_range_low", "k_range_high", "hits_range_low", "hits_range_high", "outs_range_low", "outs_range_high", "starter_history_games", "starter_history_mlb_games", "starter_history_observation_games"]:
    if col in archive_view.columns:
        archive_formats[col] = "{:.0f}"
archive_styled = archive_view.style.format(archive_formats, na_rep="—")
projected_cols = [c for c in ["projection", "hits_projection", "outs_projection"] if c in archive_view.columns]
actual_cols = [c for c in ["actual_strikeouts", "actual_hits_allowed", "actual_outs"] if c in archive_view.columns]
if projected_cols:
    archive_styled = archive_styled.map(lambda _: "color:#22c55e;font-weight:800;", subset=projected_cols)
if actual_cols:
    archive_styled = archive_styled.map(lambda _: "color:#facc15;font-weight:800;", subset=actual_cols)
target_cols = [c for c in ["k_bettable_target"] if c in archive_view.columns]
if target_cols:
    archive_styled = archive_styled.map(lambda _: "color:#38bdf8;font-weight:800;", subset=target_cols)

st.caption("Archive scan order: matchup → projected K → bettable whole-K target → actual Ks → WIN/MISS → exact-model and 80% range diagnostics. Empty None/null/NaN columns are hidden automatically.")
st.dataframe(
    archive_styled,
    hide_index=True,
    width="stretch",
    column_config={
        "game_date": st.column_config.TextColumn("Game Date"),
        "player": st.column_config.TextColumn("Pitcher"),
        "team": st.column_config.TextColumn("Team"),
        "opponent": st.column_config.TextColumn("Opp"),
        "starter_history_games": st.column_config.NumberColumn("Starts Used", format="%.0f"),
        "starter_history_source": st.column_config.TextColumn("History Source"),
        "starter_history_mlb_games": st.column_config.NumberColumn("MLB Starts", format="%.0f"),
        "starter_history_observation_games": st.column_config.NumberColumn("Observed Starts", format="%.0f"),
        "projection": st.column_config.NumberColumn("Projected K", format="%.2f"),
        "k_range_low": st.column_config.NumberColumn("80% K Low", format="%.0f"),
        "k_range_high": st.column_config.NumberColumn("80% K High", format="%.0f"),
        "actual_strikeouts": st.column_config.NumberColumn("Actual Ks", format="%.0f"),
        "k_bettable_target": st.column_config.TextColumn("K Target"),
        "k_bettable_result": st.column_config.TextColumn("K Result"),
        "k_target_margin": st.column_config.NumberColumn("Vs Target", format="%+.0f"),
        "k_range_result": st.column_config.TextColumn("80% Range Result"),
        "k_error": st.column_config.NumberColumn("Vs Projection", format="%+.2f"),
        "hits_projection": st.column_config.NumberColumn("Projected Hits", format="%.2f"),
        "hits_range_low": st.column_config.NumberColumn("80% H Low", format="%.0f"),
        "hits_range_high": st.column_config.NumberColumn("80% H High", format="%.0f"),
        "actual_hits_allowed": st.column_config.NumberColumn("Actual Hits", format="%.0f"),
        "hits_result": st.column_config.TextColumn("Hits Result"),
        "hits_error": st.column_config.NumberColumn("Hits Error", format="%+.2f"),
        "outs_projection": st.column_config.NumberColumn("Projected Outs", format="%.2f"),
        "outs_range_low": st.column_config.NumberColumn("80% Outs Low", format="%.0f"),
        "outs_range_high": st.column_config.NumberColumn("80% Outs High", format="%.0f"),
        "actual_outs": st.column_config.NumberColumn("Actual Outs", format="%.0f"),
        "outs_result": st.column_config.TextColumn("Outs Result"),
        "outs_error": st.column_config.NumberColumn("Outs Error", format="%+.2f"),
        "history_semantics": st.column_config.TextColumn("History Model"),
    },
)
'''

new = '''archive_formats = {}
for col in ["projection", "hits_projection", "outs_projection", "k_target_margin", "k_error", "hits_error", "outs_error"]:
    if col in archive_view.columns:
        archive_formats[col] = "{:+.2f}" if col.endswith("_error") else "{:+.0f}" if col == "k_target_margin" else "{:.2f}"
for col in ["actual_strikeouts", "actual_hits_allowed", "actual_outs", "k_range_low", "k_range_high", "hits_range_low", "hits_range_high", "outs_range_low", "outs_range_high", "starter_history_games", "starter_history_mlb_games", "starter_history_observation_games"]:
    if col in archive_view.columns:
        archive_formats[col] = "{:.0f}"

archive_column_config = {
    "player": st.column_config.TextColumn("Pitcher"),
    "team": st.column_config.TextColumn("Team"),
    "opponent": st.column_config.TextColumn("Opp"),
    "starter_history_games": st.column_config.NumberColumn("Starts Used", format="%.0f"),
    "starter_history_source": st.column_config.TextColumn("History Source"),
    "starter_history_mlb_games": st.column_config.NumberColumn("MLB Starts", format="%.0f"),
    "starter_history_observation_games": st.column_config.NumberColumn("Observed Starts", format="%.0f"),
    "projection": st.column_config.NumberColumn("Projected K", format="%.2f"),
    "k_range_low": st.column_config.NumberColumn("80% K Low", format="%.0f"),
    "k_range_high": st.column_config.NumberColumn("80% K High", format="%.0f"),
    "actual_strikeouts": st.column_config.NumberColumn("Actual Ks", format="%.0f"),
    "k_bettable_target": st.column_config.TextColumn("K Target"),
    "k_bettable_result": st.column_config.TextColumn("K Result"),
    "k_target_margin": st.column_config.NumberColumn("Vs Target", format="%+.0f"),
    "k_range_result": st.column_config.TextColumn("80% Range Result"),
    "k_error": st.column_config.NumberColumn("Vs Projection", format="%+.2f"),
    "hits_projection": st.column_config.NumberColumn("Projected Hits", format="%.2f"),
    "hits_range_low": st.column_config.NumberColumn("80% H Low", format="%.0f"),
    "hits_range_high": st.column_config.NumberColumn("80% H High", format="%.0f"),
    "actual_hits_allowed": st.column_config.NumberColumn("Actual Hits", format="%.0f"),
    "hits_result": st.column_config.TextColumn("Hits Result"),
    "hits_error": st.column_config.NumberColumn("Hits Error", format="%+.2f"),
    "outs_projection": st.column_config.NumberColumn("Projected Outs", format="%.2f"),
    "outs_range_low": st.column_config.NumberColumn("80% Outs Low", format="%.0f"),
    "outs_range_high": st.column_config.NumberColumn("80% Outs High", format="%.0f"),
    "actual_outs": st.column_config.NumberColumn("Actual Outs", format="%.0f"),
    "outs_result": st.column_config.TextColumn("Outs Result"),
    "outs_error": st.column_config.NumberColumn("Outs Error", format="%+.2f"),
    "history_semantics": st.column_config.TextColumn("History Model"),
}


def style_archive_group(group: pd.DataFrame):
    styled = group.style.format({col: fmt for col, fmt in archive_formats.items() if col in group.columns}, na_rep="—")
    projected_cols = [c for c in ["projection", "hits_projection", "outs_projection"] if c in group.columns]
    actual_cols = [c for c in ["actual_strikeouts", "actual_hits_allowed", "actual_outs"] if c in group.columns]
    target_cols = [c for c in ["k_bettable_target"] if c in group.columns]
    if projected_cols:
        styled = styled.map(lambda _: "color:#22c55e;font-weight:800;", subset=projected_cols)
    if actual_cols:
        styled = styled.map(lambda _: "color:#facc15;font-weight:800;", subset=actual_cols)
    if target_cols:
        styled = styled.map(lambda _: "color:#38bdf8;font-weight:800;", subset=target_cols)
    return styled


st.caption("Click a date to open that slate. Inside each date: pitcher/matchup → projected K → bettable K target → actual Ks → WIN/MISS → exact-model and 80% range diagnostics. Empty None/null/NaN columns are hidden automatically.")
archive_view["_archive_date"] = pd.to_datetime(archive_view.get("game_date"), errors="coerce")
archive_view = archive_view.sort_values(["_archive_date", "player"], ascending=[False, True], na_position="last")
archive_dates = archive_view["_archive_date"].dt.date.drop_duplicates().tolist()
for archive_date in archive_dates:
    date_mask = archive_view["_archive_date"].dt.date.eq(archive_date)
    date_group = archive_view.loc[date_mask].copy()
    date_group = date_group.drop(columns=["game_date", "_archive_date"], errors="ignore")
    date_label = pd.Timestamp(archive_date).strftime("%B %-d, %Y")
    pitcher_count = len(date_group)
    with st.expander(f"📅 {date_label} · {pitcher_count} pitcher{'s' if pitcher_count != 1 else ''}", expanded=False):
        st.dataframe(
            style_archive_group(date_group),
            hide_index=True,
            width="stretch",
            column_config={key: value for key, value in archive_column_config.items() if key in date_group.columns},
        )

undated_group = archive_view.loc[archive_view["_archive_date"].isna()].copy()
if not undated_group.empty:
    undated_group = undated_group.drop(columns=["game_date", "_archive_date"], errors="ignore")
    with st.expander(f"📅 Unknown date · {len(undated_group)} pitcher{'s' if len(undated_group) != 1 else ''}", expanded=False):
        st.dataframe(
            style_archive_group(undated_group),
            hide_index=True,
            width="stretch",
            column_config={key: value for key, value in archive_column_config.items() if key in undated_group.columns},
        )
'''

text = replace_once(text, old, new, "flat archive table")
page.write_text(text, encoding="utf-8")

contract = Path("tests/test_projection_history_learning_dashboard.py")
test = contract.read_text(encoding="utf-8")
addition = '''\n\ndef test_projection_archive_groups_rows_into_clickable_dates():\n    text = _page_text()\n    assert 'with st.expander(f"📅 {date_label}' in text\n    assert 'archive_view["_archive_date"]' in text\n    assert 'date_group = date_group.drop(columns=["game_date", "_archive_date"]' in text\n    assert "Click a date to open that slate" in text\n    assert 'expanded=False' in text\n'''
if "test_projection_archive_groups_rows_into_clickable_dates" not in test:
    test += addition
contract.write_text(test, encoding="utf-8")

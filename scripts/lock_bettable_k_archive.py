from pathlib import Path

# One-shot patch helper. Retriggered after the UI contract landed on main.


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


page = Path("pages/4_Projection_History.py")
text = page.read_text(encoding="utf-8")

text = replace_once(
    text,
    "from engine.projection_crushers import crusher_report, directional_k_result\n",
    "from engine.projection_crushers import bettable_k_label, bettable_k_result, bettable_k_target, crusher_report\n",
    "crusher import",
)

section_start = text.index('st.subheader("🔥 K Projection Wins & Crushers")')
section_end = text.index('st.divider()\nst.subheader("🧠 Current model learning status")', section_start)
new_section = '''st.subheader("🔥 Bettable K Wins & Crushers")
st.caption(
    "Archive K grading uses the highest whole-K ladder milestone fully supported by the frozen projection: floor(Projected K), within our 3+–12+ ladder. "
    "Example: 5.07 projects to a 5+ target, so 5 actual Ks = ✅ WIN. Exact projection error and 80% range coverage remain separate model diagnostics."
)
_bettable_ready = df["projection"].notna() & df["actual_strikeouts"].notna()
_bettable = df.loc[_bettable_ready].copy()
_bettable["K Target Value"] = pd.to_numeric(_bettable["projection"], errors="coerce").map(bettable_k_target)
_bettable = _bettable.loc[_bettable["K Target Value"].notna()].copy()
if _bettable.empty:
    st.info("Bettable K wins will appear as supported 3+–12+ frozen projections resolve.")
else:
    _bettable["K Target"] = _bettable["projection"].map(bettable_k_label)
    _bettable["K vs Target"] = pd.to_numeric(_bettable["actual_strikeouts"], errors="coerce") - pd.to_numeric(_bettable["K Target Value"], errors="coerce")
    _bettable["K Result"] = _bettable.apply(lambda r: bettable_k_result(r.get("projection"), r.get("actual_strikeouts")), axis=1)
    _wins = int(_bettable["K Result"].eq("✅ WIN").sum())
    _win_rate = float(_wins / len(_bettable)) if len(_bettable) else float("nan")
    _crushers = crusher_report(df)
    _crusher_count = int(_crushers["Crusher Status"].eq("🔥 CRUSHER").sum()) if not _crushers.empty else 0
    kw1, kw2, kw3, kw4 = st.columns(4)
    kw1.metric("Resolved ladder calls", len(_bettable))
    kw2.metric("Ladder wins", _wins)
    kw3.metric("Ladder win rate", f"{_win_rate:.1%}")
    kw4.metric("Consistent crushers", _crusher_count)

    high_calls = _bettable.loc[_bettable.get("confidence", pd.Series(index=_bettable.index, dtype=str)).astype(str).str.upper().eq("HIGH")].copy()
    if not high_calls.empty:
        st.markdown("#### High-confidence ladder calls")
        high_calls = high_calls.sort_values(["game_date", "captured_at_utc"], ascending=[False, False]).head(30)
        high_view = high_calls[["player", "projection", "K Target", "actual_strikeouts", "K vs Target", "K Result"]].copy()
        high_view = high_view.rename(columns={"player":"Pitcher", "projection":"Projection", "actual_strikeouts":"Actual"})
        high_styled = high_view.style.format({"Projection":"{:.2f}", "Actual":"{:.0f}", "K vs Target":"{:+.0f}"}, na_rep="—")
        high_styled = high_styled.map(lambda _: "color:#22c55e;font-weight:800;", subset=["Projection"])
        high_styled = high_styled.map(lambda _: "color:#38bdf8;font-weight:800;", subset=["K Target"])
        high_styled = high_styled.map(lambda _: "color:#facc15;font-weight:800;", subset=["Actual"])
        st.dataframe(high_styled, hide_index=True, width="stretch")

    st.markdown("#### Projection Crushers")
    if _crushers.empty:
        st.info("Crusher tracking will populate as current starter-only K ladder calls resolve.")
    else:
        crusher_view = _crushers.copy()
        for col in ["Win Rate", "Recent 5 Win Rate"]:
            crusher_view[col] = crusher_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")
        for col in ["Avg K Above Target", "Avg Win Margin", "Total K Above Target"]:
            crusher_view[col] = crusher_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.2f}")
        st.dataframe(crusher_view, hide_index=True, width="stretch")
        st.caption("🔥 CRUSHER requires at least 3 resolved current-model ladder calls, a win rate of at least 66.7%, and average actual Ks more than 0.5 above the bettable target. This board is descriptive tracking only.")

'''
text = text[:section_start] + new_section + text[section_end:]

old_grade = '''display["k_directional_result"] = display.apply(lambda r: directional_k_result(r.get("projection"), r.get("actual_strikeouts")), axis=1)
display["k_range_result"] = display.apply(lambda r: range_result(r, "actual_strikeouts", "k_range_low", "k_range_high"), axis=1)
'''
new_grade = '''display["k_bettable_target_value"] = display["projection"].map(bettable_k_target)
display["k_bettable_target"] = display["projection"].map(bettable_k_label)
display["k_target_margin"] = display.apply(
    lambda r: r["actual_strikeouts"] - r["k_bettable_target_value"] if pd.notna(r.get("actual_strikeouts")) and pd.notna(r.get("k_bettable_target_value")) else None,
    axis=1,
)
display["k_bettable_result"] = display.apply(lambda r: bettable_k_result(r.get("projection"), r.get("actual_strikeouts")), axis=1)
display["k_range_result"] = display.apply(lambda r: range_result(r, "actual_strikeouts", "k_range_low", "k_range_high"), axis=1)
'''
text = replace_once(text, old_grade, new_grade, "archive K grade")

old_columns = '''display_columns = [
    "game_date", "player", "team", "opponent",
    "projection", "actual_strikeouts", "k_directional_result", "k_error", "k_range_low", "k_range_high", "k_range_result",
    "hits_projection", "actual_hits_allowed", "hits_error", "hits_range_low", "hits_range_high", "hits_result",
    "outs_projection", "actual_outs", "outs_error", "outs_range_low", "outs_range_high", "outs_result",
    "confidence", "data_quality", "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games",
    "status", "history_semantics",
]
'''
new_columns = '''display_columns = [
    "game_date", "player", "team", "opponent",
    "projection", "k_bettable_target", "actual_strikeouts", "k_bettable_result", "k_target_margin", "k_error", "k_range_low", "k_range_high", "k_range_result",
    "hits_projection", "actual_hits_allowed", "hits_error", "hits_range_low", "hits_range_high", "hits_result",
    "outs_projection", "actual_outs", "outs_error", "outs_range_low", "outs_range_high", "outs_result",
    "confidence", "data_quality", "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games",
    "status", "history_semantics",
]
'''
text = replace_once(text, old_columns, new_columns, "archive columns")

old_empty = '''archive_view = display[display_columns].copy()
# Remove dead archive columns instead of rendering blank visual tracks/cells.
archive_populated = []
for col in archive_view.columns:
    series = archive_view[col]
    populated = series.notna()
    if series.dtype == object:
        populated = populated & series.astype(str).str.strip().ne("") & series.astype(str).str.lower().ne("nan")
    if bool(populated.any()):
        archive_populated.append(col)
archive_view = archive_view[archive_populated]
'''
new_empty = '''archive_view = display[display_columns].copy()
# Normalize placeholder strings, then remove genuinely dead archive columns.
for col in archive_view.columns:
    if archive_view[col].dtype == object:
        cleaned = archive_view[col].astype(str).str.strip()
        empty_token = cleaned.str.lower().isin({"", "nan", "none", "null", "nat", "<na>"})
        archive_view.loc[empty_token, col] = pd.NA
archive_populated = [col for col in archive_view.columns if bool(archive_view[col].notna().any())]
archive_view = archive_view[archive_populated]
'''
text = replace_once(text, old_empty, new_empty, "empty archive normalization")

text = text.replace(
    'for col in ["projection", "hits_projection", "outs_projection", "k_error", "hits_error", "outs_error"]:',
    'for col in ["projection", "hits_projection", "outs_projection", "k_target_margin", "k_error", "hits_error", "outs_error"]:',
    1,
)
text = text.replace(
    'archive_formats[col] = "{:+.2f}" if col.endswith("_error") else "{:.2f}"',
    'archive_formats[col] = "{:+.2f}" if col.endswith("_error") else "{:+.0f}" if col == "k_target_margin" else "{:.2f}"',
    1,
)

old_style = '''if actual_cols:
    archive_styled = archive_styled.map(lambda _: "color:#facc15;font-weight:800;", subset=actual_cols)

st.caption("Archive scan order: matchup → projected vs actual → directional result/margin → 80% range context → supporting audit fields. Completely empty columns are hidden automatically.")
'''
new_style = '''if actual_cols:
    archive_styled = archive_styled.map(lambda _: "color:#facc15;font-weight:800;", subset=actual_cols)
target_cols = [c for c in ["k_bettable_target"] if c in archive_view.columns]
if target_cols:
    archive_styled = archive_styled.map(lambda _: "color:#38bdf8;font-weight:800;", subset=target_cols)

st.caption("Archive scan order: matchup → projected K → bettable whole-K target → actual Ks → WIN/MISS → exact-model and 80% range diagnostics. Empty None/null/NaN columns are hidden automatically.")
'''
text = replace_once(text, old_style, new_style, "archive style/caption")

text = replace_once(
    text,
    '        "k_directional_result": st.column_config.TextColumn("Directional K Result"),\n        "k_range_result": st.column_config.TextColumn("80% Range Result"),\n        "k_error": st.column_config.NumberColumn("K Error", format="%+.2f"),\n',
    '        "k_bettable_target": st.column_config.TextColumn("K Target"),\n        "k_bettable_result": st.column_config.TextColumn("K Result"),\n        "k_target_margin": st.column_config.NumberColumn("Vs Target", format="%+.0f"),\n        "k_range_result": st.column_config.TextColumn("80% Range Result"),\n        "k_error": st.column_config.NumberColumn("Vs Projection", format="%+.2f"),\n',
    "archive column config",
)

page.write_text(text, encoding="utf-8")

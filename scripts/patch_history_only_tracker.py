from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor not found: {label}")
    return text.replace(old, new, 1)


path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''    LOG_PATH,\n    PROBABILITY_SEMANTICS,\n''',
    '''    LOG_PATH,\n    PROBABILITY_SEMANTICS,\n    load_observation_log,\n    resolve_observation_log,\n''',
    "observation imports",
)

anchor = '''def save_log(frame: pd.DataFrame) -> None:\n'''
helper = '''def history_only_for_day(day: str) -> pd.DataFrame:\n    """Return persistent history-only starter observations for one slate date."""\n    frame = load_observation_log()\n    if frame.empty or "game_date" not in frame.columns:\n        return pd.DataFrame()\n    rows = frame.loc[frame["game_date"].astype(str).eq(str(day))].copy()\n    if rows.empty:\n        return rows\n    actual_cols = [\n        "actual_strikeouts", "actual_hits_allowed", "actual_outs",\n        "actual_batters_faced", "actual_pitches",\n    ]\n    for col in actual_cols + ["history_games_available_at_capture"]:\n        if col in rows.columns:\n            rows[col] = pd.to_numeric(rows[col], errors="coerce")\n    available = [col for col in actual_cols if col in rows.columns]\n    resolved = rows[available].notna().all(axis=1) if available else pd.Series(False, index=rows.index)\n    rows["observation_status"] = np.where(resolved, "RESOLVED", "PENDING")\n    return rows.sort_values(["observation_status", "game_time", "player"], ascending=[True, True, True]).reset_index(drop=True)\n\n\n'''
if anchor not in text:
    raise SystemExit("history helper anchor missing")
text = text.replace(anchor, helper + anchor, 1)

text = replace_once(
    text,
    '''            "player", "weather_icon", "weather_delay_risk", "weather_precip_probability", "lineup_source", "lineup_batters", "lineup_projection_delta", "team", "opponent", "projection", "k_range_low", "k_range_high",\n''',
    '''            "player", "starter_history_games", "weather_icon", "weather_delay_risk", "weather_precip_probability", "lineup_source", "lineup_batters", "lineup_projection_delta", "team", "opponent", "projection", "k_range_low", "k_range_high",\n''',
    "starts used display column",
)
text = replace_once(
    text,
    '''                "player": "Pitcher",\n                "weather_delay_risk": "Weather Risk",\n''',
    '''                "player": "Pitcher",\n                "starter_history_games": "Starts Used",\n                "weather_delay_risk": "Weather Risk",\n''',
    "starts used display rename",
)

history_anchor = '''st.divider()\nst.subheader("Resolve completed games")\n'''
history_ui = '''st.divider()\nst.subheader("📚 Persistent history-only starter tracker")\nst.caption(\n    "These rows live in starter_observation_log.csv, separate from projection_log.csv. "\n    "They are real starter observations collected specifically for pitchers who could not yet receive a legitimate projection."\n)\nhistory_rows = history_only_for_day(slate_date.isoformat())\nif history_rows.empty:\n    st.info("No history-only starter observations are recorded for this slate date.")\nelse:\n    resolved_count = int(history_rows["observation_status"].eq("RESOLVED").sum())\n    pending_count = int(history_rows["observation_status"].eq("PENDING").sum())\n    h1, h2, h3 = st.columns(3)\n    h1.metric("History-only starts", len(history_rows))\n    h2.metric("Pending results", pending_count)\n    h3.metric("Resolved into history", resolved_count)\n\n    history_display_cols = [\n        "player", "team", "opponent", "reason", "history_games_available_at_capture",\n        "observation_status", "actual_strikeouts", "actual_hits_allowed", "actual_outs",\n        "actual_batters_faced", "actual_pitches", "resolved_at_utc",\n    ]\n    history_display_cols = [col for col in history_display_cols if col in history_rows.columns]\n    history_display = history_rows[history_display_cols].copy().rename(columns={\n        "player": "Pitcher",\n        "team": "Team",\n        "opponent": "Opp",\n        "reason": "Tracking Reason",\n        "history_games_available_at_capture": "Starts Available",\n        "observation_status": "Status",\n        "actual_strikeouts": "Actual K",\n        "actual_hits_allowed": "Actual Hits Allowed",\n        "actual_outs": "Actual Outs",\n        "actual_batters_faced": "Actual BF",\n        "actual_pitches": "Actual Pitches",\n        "resolved_at_utc": "Resolved At",\n    })\n    st.dataframe(history_display, hide_index=True, use_container_width=True)\n    st.caption(\n        "When a row resolves, its full starter line becomes eligible fallback history for that pitcher on a future start. "\n        "It never becomes a fake historical projection or calibration row."\n    )\n\nst.divider()\nst.subheader("Resolve completed games")\n'''
text = replace_once(text, history_anchor, history_ui, "persistent history-only UI")

old_resolve = '''if st.button("Resolve completed projection outcomes"):\n    frame = load_log()\n    updated = 0\n    if not frame.empty:\n        with st.spinner("Checking MLB results and attaching actual strikeouts + hits allowed + outs..."):\n            for idx in frame.index:\n                actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])\n                changed = False\n                if pd.notna(actual_k) and pd.isna(frame.loc[idx].get("actual_strikeouts")):\n                    frame.at[idx, "actual_strikeouts"] = actual_k\n                    changed = True\n                if pd.notna(actual_hits) and pd.isna(frame.loc[idx].get("actual_hits_allowed")):\n                    frame.at[idx, "actual_hits_allowed"] = actual_hits\n                    changed = True\n                if pd.notna(actual_outs) and pd.isna(frame.loc[idx].get("actual_outs")):\n                    frame.at[idx, "actual_outs"] = actual_outs\n                    changed = True\n                if changed:\n                    frame.at[idx, "resolved_at_utc"] = resolved\n                    updated += 1\n            save_log(frame)\n    if updated:\n        st.success(f"Resolved {updated} new projection outcome(s).")\n    else:\n        st.info("No new completed outcomes were available.")\n'''
new_resolve = '''if st.button("Resolve completed projection outcomes"):\n    frame = load_log()\n    updated = 0\n    observation_updates = 0\n    with st.spinner("Checking MLB results for projected and history-only starters..."):\n        if not frame.empty:\n            for idx in frame.index:\n                actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])\n                changed = False\n                if pd.notna(actual_k) and pd.isna(frame.loc[idx].get("actual_strikeouts")):\n                    frame.at[idx, "actual_strikeouts"] = actual_k\n                    changed = True\n                if pd.notna(actual_hits) and pd.isna(frame.loc[idx].get("actual_hits_allowed")):\n                    frame.at[idx, "actual_hits_allowed"] = actual_hits\n                    changed = True\n                if pd.notna(actual_outs) and pd.isna(frame.loc[idx].get("actual_outs")):\n                    frame.at[idx, "actual_outs"] = actual_outs\n                    changed = True\n                if changed:\n                    frame.at[idx, "resolved_at_utc"] = resolved\n                    updated += 1\n            save_log(frame)\n        observation_updates = resolve_observation_log()\n    if updated or observation_updates:\n        st.success(\n            f"Resolved {updated} new projection outcome(s) and {observation_updates} history-only starter observation(s)."\n        )\n    else:\n        st.info("No new completed projected or history-only starter outcomes were available.")\n'''
text = replace_once(text, old_resolve, new_resolve, "combined resolver")
path.write_text(text, encoding="utf-8")


path = Path("tests/test_daily_history_ui.py")
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_daily_page_has_persistent_history_only_tracker_and_starts_used():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert "load_observation_log" in source\n    assert "resolve_observation_log" in source\n    assert "history_only_for_day" in source\n    assert "📚 Persistent history-only starter tracker" in source\n    assert "Resolved into history" in source\n    assert '"starter_history_games": "Starts Used"' in source\n    assert 'observation_updates = resolve_observation_log()' in source\n    assert "It never becomes a fake historical projection or calibration row." in source\n'''
path.write_text(text, encoding="utf-8")

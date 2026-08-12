from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor not found: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Daily runner: label MLB vs self-collected starter rows and freeze provenance.
# ---------------------------------------------------------------------------
path = Path("automation/daily_projection_runner.py")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''                "outs": parse_ip(s.get("inningsPitched", "0.0")) * 3,\n                "games_started": int(float(s.get("gamesStarted", 0) or 0)),\n''',
    '''                "outs": parse_ip(s.get("inningsPitched", "0.0")) * 3,\n                "games_started": int(float(s.get("gamesStarted", 0) or 0)),\n                "history_source": "MLB",\n''',
    "MLB history source label",
)

text = replace_once(
    text,
    '''        "outs": data["actual_outs"].to_numpy(float),\n        "games_started": np.ones(len(data), dtype=int),\n''',
    '''        "outs": data["actual_outs"].to_numpy(float),\n        "games_started": np.ones(len(data), dtype=int),\n        "history_source": np.full(len(data), "OBSERVATION", dtype=object),\n''',
    "observation history source label",
)

anchor = '''def supplement_with_observations(log: pd.DataFrame, pitcher_id: int) -> pd.DataFrame:\n'''
helper = '''def starter_history_provenance(log: pd.DataFrame) -> dict[str, object]:\n    """Summarize the actual starter rows used by source without changing the model input."""\n    if log.empty:\n        return {"source": "NONE", "mlb_games": 0, "observation_games": 0}\n    if "history_source" in log.columns:\n        source = log["history_source"].fillna("MLB").astype(str).str.upper()\n    else:\n        source = pd.Series("MLB", index=log.index, dtype=str)\n    mlb_games = int(source.eq("MLB").sum())\n    observation_games = int(source.eq("OBSERVATION").sum())\n    if observation_games and mlb_games:\n        label = "MLB_PLUS_OBSERVATIONS"\n    elif observation_games:\n        label = "OBSERVATIONS_ONLY"\n    else:\n        label = "MLB_ONLY"\n    return {"source": label, "mlb_games": mlb_games, "observation_games": observation_games}\n\n\n'''
if anchor not in text:
    raise SystemExit("provenance helper anchor missing")
text = text.replace(anchor, helper + anchor, 1)

text = replace_once(
    text,
    '''    log = combine_starter_history(current_log, prior_log)\n    log = supplement_with_observations(log, row["pitcher_id"])\n    if log.empty:\n''',
    '''    log = combine_starter_history(current_log, prior_log)\n    log = supplement_with_observations(log, row["pitcher_id"])\n    history_provenance = starter_history_provenance(log)\n    if log.empty:\n''',
    "project provenance capture",
)

text = replace_once(
    text,
    '''        "history_semantics": HISTORY_SEMANTICS, "starter_history_games": int(len(log)),\n''',
    '''        "history_semantics": HISTORY_SEMANTICS, "starter_history_games": int(len(log)),\n        "starter_history_source": str(history_provenance["source"]),\n        "starter_history_mlb_games": int(history_provenance["mlb_games"]),\n        "starter_history_observation_games": int(history_provenance["observation_games"]),\n''',
    "snapshot provenance fields",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Daily page: surface provenance in the slate and rationale.
# ---------------------------------------------------------------------------
path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''    if "starter_history_games" not in frame.columns:\n        frame["starter_history_games"] = np.nan\n''',
    '''    if "starter_history_games" not in frame.columns:\n        frame["starter_history_games"] = np.nan\n    if "starter_history_source" not in frame.columns:\n        frame["starter_history_source"] = ""\n    if "starter_history_mlb_games" not in frame.columns:\n        frame["starter_history_mlb_games"] = np.nan\n    if "starter_history_observation_games" not in frame.columns:\n        frame["starter_history_observation_games"] = np.nan\n''',
    "daily save provenance schema",
)

text = replace_once(
    text,
    '''        "Starter appearances used": int(_num(row, "starter_history_games") or 0),\n''',
    '''        "Starter appearances used": int(_num(row, "starter_history_games") or 0),\n        "History source": row.get("starter_history_source", "—"),\n        "MLB starts used": int(_num(row, "starter_history_mlb_games") or 0),\n        "Observed starts used": int(_num(row, "starter_history_observation_games") or 0),\n''',
    "daily rationale provenance",
)

text = replace_once(
    text,
    '''            "player", "starter_history_games", "weather_icon", "weather_delay_risk", "weather_precip_probability", "lineup_source", "lineup_batters", "lineup_projection_delta", "team", "opponent", "projection", "k_range_low", "k_range_high",\n''',
    '''            "player", "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games", "weather_icon", "weather_delay_risk", "weather_precip_probability", "lineup_source", "lineup_batters", "lineup_projection_delta", "team", "opponent", "projection", "k_range_low", "k_range_high",\n''',
    "daily display provenance columns",
)

text = replace_once(
    text,
    '''                "starter_history_games": "Starts Used",\n                "weather_delay_risk": "Weather Risk",\n''',
    '''                "starter_history_games": "Starts Used",\n                "starter_history_source": "History Source",\n                "starter_history_mlb_games": "MLB Starts",\n                "starter_history_observation_games": "Observed Starts",\n                "weather_delay_risk": "Weather Risk",\n''',
    "daily display provenance labels",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Projection History archive: keep provenance visible after the slate passes.
# ---------------------------------------------------------------------------
path = Path("pages/4_Projection_History.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    "game_date", "player", "team", "opponent", "starter_history_games",\n''',
    '''    "game_date", "player", "team", "opponent", "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games",\n''',
    "history archive provenance columns",
)
text = replace_once(
    text,
    '''        "starter_history_games": st.column_config.NumberColumn("Starts Used", format="%.0f"),\n''',
    '''        "starter_history_games": st.column_config.NumberColumn("Starts Used", format="%.0f"),\n        "starter_history_source": st.column_config.TextColumn("History Source"),\n        "starter_history_mlb_games": st.column_config.NumberColumn("MLB Starts", format="%.0f"),\n        "starter_history_observation_games": st.column_config.NumberColumn("Observed Starts", format="%.0f"),\n''',
    "history archive provenance config",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Regression coverage.
# ---------------------------------------------------------------------------
path = Path("tests/test_starter_observations.py")
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_starter_history_provenance_distinguishes_mlb_and_observation_rows():\n    log = pd.DataFrame([\n        {"date": pd.Timestamp("2026-08-01"), "history_source": "MLB"},\n        {"date": pd.Timestamp("2026-08-07"), "history_source": "OBSERVATION"},\n        {"date": pd.Timestamp("2026-08-12"), "history_source": "OBSERVATION"},\n    ])\n    info = runner.starter_history_provenance(log)\n    assert info["source"] == "MLB_PLUS_OBSERVATIONS"\n    assert info["mlb_games"] == 1\n    assert info["observation_games"] == 2\n\n\ndef test_observation_history_rows_are_labeled_for_provenance(tmp_path, monkeypatch):\n    path = tmp_path / "starter_observation_log.csv"\n    monkeypatch.setattr(runner, "OBS_LOG_PATH", path)\n    runner.record_history_only(_row())\n    frame = runner.load_observation_log()\n    frame.loc[0, "actual_strikeouts"] = 6\n    frame.loc[0, "actual_hits_allowed"] = 4\n    frame.loc[0, "actual_outs"] = 17\n    frame.loc[0, "actual_batters_faced"] = 23\n    frame.loc[0, "actual_pitches"] = 91\n    runner.save_observation_log(frame)\n    history = runner.observation_history(987)\n    assert history.loc[0, "history_source"] == "OBSERVATION"\n'''
path.write_text(text, encoding="utf-8")

path = Path("tests/test_daily_history_ui.py")
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_daily_page_surfaces_starter_history_provenance():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert '"starter_history_source": "History Source"' in source\n    assert '"starter_history_mlb_games": "MLB Starts"' in source\n    assert '"starter_history_observation_games": "Observed Starts"' in source\n    assert '"Observed starts used"' in source\n'''
path.write_text(text, encoding="utf-8")

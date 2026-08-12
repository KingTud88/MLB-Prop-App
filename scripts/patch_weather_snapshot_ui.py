from pathlib import Path

RUNNER=Path("automation/daily_projection_runner.py")
DAILY=Path("pages/5_Daily_Projection_Run.py")
TOP=Path("pages/6_Top_Plays.py")
MODEL=Path("engine/model_top_plays.py")
TEST=Path("tests/test_weather_snapshot_ui.py")

runner=RUNNER.read_text(encoding="utf-8")
repls=[
('import math\nfrom datetime import datetime, timedelta, timezone\n','import math\nfrom functools import lru_cache\nfrom datetime import datetime, timedelta, timezone\n'),
('from engine.starter_history import HISTORY_SEMANTICS, TARGET_STARTER_HISTORY, combine_starter_history, starter_only\n','from engine.starter_history import HISTORY_SEMANTICS, TARGET_STARTER_HISTORY, combine_starter_history, starter_only\nfrom engine.weather_risk import WeatherDelayRisk, fetch_weather_delay_risk\n'),
('def pitcher_hand(pitcher_id: int) -> str:\n','''@lru_cache(maxsize=64)\ndef venue_coordinates(venue_id: int) -> tuple[float, float] | None:\n    if not venue_id:\n        return None\n    try:\n        data = get_json(f"venues/{int(venue_id)}", {})\n        venues = data.get("venues") or []\n        coords = ((venues[0].get("location") or {}).get("defaultCoordinates") or {}) if venues else {}\n        lat, lon = coords.get("latitude"), coords.get("longitude")\n        return (float(lat), float(lon)) if lat is not None and lon is not None else None\n    except (requests.RequestException, ValueError, TypeError, IndexError):\n        return None\n\n\n@lru_cache(maxsize=128)\ndef game_weather(venue_id: int, game_time: str) -> WeatherDelayRisk:\n    coords = venue_coordinates(int(venue_id or 0))\n    if not coords:\n        return WeatherDelayRisk("UNKNOWN", "", None, None, None, "Venue coordinates unavailable for weather risk.", False)\n    return fetch_weather_delay_risk(coords[0], coords[1], str(game_time or ""))\n\n\ndef weather_snapshot_fields(venue_id: int, game_time: str) -> dict[str, object]:\n    risk = game_weather(int(venue_id or 0), str(game_time or ""))\n    return {\n        "weather_delay_risk": risk.level,\n        "weather_icon": risk.icon,\n        "weather_precip_probability": np.nan if risk.precip_probability is None else risk.precip_probability,\n        "weather_precip_mm": np.nan if risk.precipitation_mm is None else risk.precipitation_mm,\n        "weather_summary": risk.summary,\n    }\n\n\ndef pitcher_hand(pitcher_id: int) -> str:\n'''),
('            teams = game.get("teams", {})\n            for side, other in (("away", "home"), ("home", "away")):\n','            teams = game.get("teams", {})\n            venue_node = game.get("venue", {}) or {}\n            for side, other in (("away", "home"), ("home", "away")):\n'),
('                    "venue": game.get("venue", {}).get("name", "Unknown"),\n','                    "venue_id": int(venue_node.get("id", 0) or 0),\n                    "venue": venue_node.get("name", "Unknown"),\n'),
('    raw_sim = result.metadata.get("raw_simulation_probabilities", result.simulation_probabilities)\n','    weather = weather_snapshot_fields(int(row.get("venue_id", 0) or 0), str(row.get("game_time", "")))\n    raw_sim = result.metadata.get("raw_simulation_probabilities", result.simulation_probabilities)\n'),
('        "player": row["player"], "team": row["team"], "opponent": row["opponent"], "venue": row["venue"],\n','        "player": row["player"], "team": row["team"], "opponent": row["opponent"], "venue_id": row.get("venue_id", 0), "venue": row["venue"],\n'),
('        "weather_factor": 1.0, "rest_factor": 1.0,\n','        "weather_factor": 1.0, "rest_factor": 1.0,\n        **weather,\n'),
('def fill_missing_pregame_paths(frame: pd.DataFrame) -> int:\n','''def attach_pregame_weather(frame: pd.DataFrame, announced: list[dict]) -> int:\n    if frame.empty or not announced:\n        return 0\n    now = datetime.now(timezone.utc)\n    lookup = {(int(r["game_pk"]), int(r["pitcher_id"])): r for r in announced}\n    updated = 0\n    for idx in frame.index:\n        row = frame.loc[idx]\n        if not row_is_pregame(row, now):\n            continue\n        existing = str(row.get("weather_delay_risk", "") or "").upper()\n        if existing in {"NONE", "LOW", "ELEVATED", "HIGH"}:\n            continue\n        try:\n            key = (int(row["game_pk"]), int(row["pitcher_id"]))\n        except Exception:\n            continue\n        scheduled = lookup.get(key)\n        if not scheduled:\n            continue\n        fields = weather_snapshot_fields(int(scheduled.get("venue_id", 0) or 0), str(scheduled.get("game_time", "")))\n        frame.at[idx, "venue_id"] = int(scheduled.get("venue_id", 0) or 0)\n        for key_name, value in fields.items():\n            frame.at[idx, key_name] = value\n        updated += 1\n    return updated\n\n\ndef fill_missing_pregame_paths(frame: pd.DataFrame) -> int:\n'''),
('                "venue": row.get("venue", "Unknown"),\n','                "venue_id": int(row["venue_id"]) if pd.notna(row.get("venue_id")) else 0,\n                "venue": row.get("venue", "Unknown"),\n'),
('    rows = schedule(today.isoformat())\n    existing = set()\n','    rows = schedule(today.isoformat())\n    weather_refreshes = attach_pregame_weather(frame, rows)\n    existing = set()\n'),
('        f"projection log rows={len(frame)} new={len(new_rows)} pregame_path_refreshes={refreshed} "\n','        f"projection log rows={len(frame)} new={len(new_rows)} pregame_path_refreshes={refreshed} weather_refreshes={weather_refreshes} "\n'),
]
for old,new in repls:
    if old not in runner: raise SystemExit(f"runner anchor not found: {old[:160]}")
    runner=runner.replace(old,new,1)
RUNNER.write_text(runner,encoding="utf-8")

daily=DAILY.read_text(encoding="utf-8")
repls=[
('    fill_missing_pregame_paths,\n','    fill_missing_pregame_paths,\n    attach_pregame_weather,\n'),
('    refreshed = fill_missing_pregame_paths(frame)\n    save_log(frame)\n','    refreshed = fill_missing_pregame_paths(frame)\n    weather_refreshed = attach_pregame_weather(frame, announced)\n    save_log(frame)\n'),
('    return slate, len(new_rows), skipped + refreshed, history_only, errors\n','    return slate, len(new_rows), skipped + refreshed + weather_refreshed, history_only, errors\n'),
('            "player", "team", "opponent", "projection", "k_range_low", "k_range_high",\n','            "player", "weather_icon", "weather_delay_risk", "weather_precip_probability", "team", "opponent", "projection", "k_range_low", "k_range_high",\n'),
('        display = slate[display_cols].copy().rename(\n','        display = slate[display_cols].copy()\n        if "weather_icon" in display.columns:\n            display["player"] = display.apply(lambda r: f"{r.get(\'player\', \'Unknown\')} {str(r.get(\'weather_icon\', \'\') or \'\')}".strip(), axis=1)\n            display = display.drop(columns=["weather_icon"])\n        display = display.rename(\n'),
('                "team": "Team",\n','                "weather_delay_risk": "Weather Risk",\n                "weather_precip_probability": "Rain %",\n                "team": "Team",\n'),
]
for old,new in repls:
    if old not in daily: raise SystemExit(f"daily anchor not found: {old[:160]}")
    daily=daily.replace(old,new,1)
DAILY.write_text(daily,encoding="utf-8")

model=MODEL.read_text(encoding="utf-8")
old='        "Captured At UTC": row.get("captured_at_utc", ""),\n'
new='''        "Captured At UTC": row.get("captured_at_utc", ""),\n        "Weather Icon": row.get("weather_icon", ""),\n        "Weather Risk": row.get("weather_delay_risk", ""),\n        "Weather Summary": row.get("weather_summary", ""),\n        "Rain Probability": row.get("weather_precip_probability", None),\n'''
if old not in model: raise SystemExit("model weather metadata anchor not found")
MODEL.write_text(model.replace(old,new,1),encoding="utf-8")

top=TOP.read_text(encoding="utf-8")
repls=[
('view = plays[["Rank", "Status", "Pitcher", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Starter History", "Book", "Odds"]].copy()\n','view = plays[["Rank", "Status", "Pitcher", "Weather Icon", "Weather Risk", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Starter History", "Book", "Odds"]].copy()\nview["Pitcher"] = view.apply(lambda r: f"{r[\'Pitcher\']} {str(r.get(\'Weather Icon\', \'\') or \'\')}".strip(), axis=1)\nview = view.drop(columns=["Weather Icon"])\n'),
('        st.caption(f"#{rank} {play_row[\'Pitcher\']} · {play_row[\'Side\']} {float(play_row[\'Line\']):g}")\n','        weather_icon = str(play_row.get("Weather Icon", "") or "")\n        st.caption(f"#{rank} {play_row[\'Pitcher\']} {weather_icon} · {play_row[\'Side\']} {float(play_row[\'Line\']):g}".replace("  ·", " ·"))\n'),
('        f"#{int(leg[\'Rank\'])} {leg[\'Pitcher\']} · {leg[\'Market\']} · {leg[\'Side\']} {float(leg[\'Line\']):g} · "\n','        f"#{int(leg[\'Rank\'])} {leg[\'Pitcher\']} {str(leg.get(\'Weather Icon\', \'\') or \'\')} · {leg[\'Market\']} · {leg[\'Side\']} {float(leg[\'Line\']):g} · "\n'),
('    st.caption(f"{play.get(\'Team\', \'\')} vs {play.get(\'Opponent\', \'\')} · {play[\'Market\']} · {play[\'Side\']} {float(play[\'Line\']):g} · {live_text}")\n','    st.caption(f"{play.get(\'Team\', \'\')} vs {play.get(\'Opponent\', \'\')} · {play[\'Market\']} · {play[\'Side\']} {float(play[\'Line\']):g} · {live_text}")\n    weather_level = str(play.get("Weather Risk", "") or "").upper()\n    weather_summary = str(play.get("Weather Summary", "") or "").strip()\n    if weather_level in {"HIGH", "ELEVATED"} and weather_summary:\n        st.warning(f"{str(play.get(\'Weather Icon\', \'\') or \'🌩️\')} {weather_summary}. Weather is informational and does not affect Top 5 ranking.")\n'),
]
for old,new in repls:
    if old not in top: raise SystemExit(f"top anchor not found: {old[:180]}")
    top=top.replace(old,new,1)
TOP.write_text(top,encoding="utf-8")

TEST.write_text('''from pathlib import Path\n\n\ndef test_daily_runner_captures_weather_without_model_factor_change():\n    text=Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")\n    assert "weather_snapshot_fields" in text\n    assert "attach_pregame_weather" in text\n    assert '"weather_delay_risk"' in text\n    assert '"weather_icon"' in text\n    assert '"weather_factor": 1.0' in text\n\n\ndef test_daily_and_top_plays_surface_weather_icons():\n    daily=Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    top=Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")\n    assert '"Weather Risk"' in daily\n    assert 'weather_icon' in daily\n    assert '"Weather Icon"' in top\n    assert "Weather is informational and does not affect Top 5 ranking" in top\n\n\ndef test_model_board_only_carries_weather_metadata():\n    text=Path("engine/model_top_plays.py").read_text(encoding="utf-8")\n    assert '"Weather Icon": row.get("weather_icon", "")' in text\n    assert 'sort_values(["Model Probability", "Data Quality"]' in text\n\n\ndef test_changed_pages_compile():\n    for path in ["automation/daily_projection_runner.py","pages/5_Daily_Projection_Run.py","pages/6_Top_Plays.py","engine/model_top_plays.py"]:\n        compile(Path(path).read_text(encoding="utf-8"),path,"exec")\n''',encoding="utf-8")

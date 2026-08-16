from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"{label} anchor missing")
    return text.replace(old, new, 1)


# 1) Daily Projection Run: expose active sportsbook lines directly in the
# frozen Starter Slate table. This is presentation only; projections stay frozen.
p = Path("pages/5_Daily_Projection_Run.py")
s = p.read_text()

old_cols = '''        display_cols = [
            "player", "team", "opponent", "projection", "k_range_low", "k_range_high", "sim_5p", "math_5p",
            "hits_projection", "hits_range_low", "hits_range_high", "hits_sim_over_5_5", "hits_math_over_5_5",
            "outs_projection", "outs_range_low", "outs_range_high", "outs_sim_over_15_5", "outs_math_over_15_5",
            "confidence", "data_quality", "opponent_k_pct",'''
new_cols = '''        display_cols = [
            "player", "team", "opponent",
            "active_strikeout_line", "active_strikeout_line_source", "projection", "k_range_low", "k_range_high", "sim_5p", "math_5p",
            "active_outs_line", "active_outs_line_source", "outs_projection", "outs_range_low", "outs_range_high", "outs_sim_over_15_5", "outs_math_over_15_5",
            "active_hits_allowed_line", "active_hits_allowed_line_source", "hits_projection", "hits_range_low", "hits_range_high", "hits_sim_over_5_5", "hits_math_over_5_5",
            "confidence", "data_quality", "opponent_k_pct",'''
s = replace_once(s, old_cols, new_cols, "starter slate columns")

rename_anchor = '''                "projection": "Projection K",
                "hits_projection": "Projection Hits",
                "outs_projection": "Projection Outs",'''
rename_new = '''                "active_strikeout_line": "K Line",
                "active_strikeout_line_source": "K Source",
                "projection": "Projection K",
                "active_outs_line": "Outs Line",
                "active_outs_line_source": "Outs Source",
                "outs_projection": "Projection Outs",
                "active_hits_allowed_line": "Hits Line",
                "active_hits_allowed_line_source": "Hits Source",
                "hits_projection": "Projection Hits",'''
s = replace_once(s, rename_anchor, rename_new, "starter slate rename")

format_anchor = '''        for col in projection_highlight_cols:
            formatters[col] = "{:.2f}"
        for col in probability_cols:'''
format_new = '''        for col in projection_highlight_cols:
            formatters[col] = "{:.2f}"
        for col in ("K Line", "Outs Line", "Hits Line"):
            if col in display.columns:
                formatters[col] = "{:.1f}"
        for col in probability_cols:'''
s = replace_once(s, format_anchor, format_new, "starter slate line formatting")

caption_old = '''            "How to read: Projection = expected average outcome · 80% Range = one central simulated interval (10th–90th percentile), not an 80% chance at each endpoint · "
            "SIM/MATH = the probability from each independent model path. Click a pitcher row for the full breakdown. Headline projections are green."'''
caption_new = '''            "How to read: Line = active sportsbook execution line attached after projection capture · Projection = frozen expected average outcome · 80% Range = one central simulated interval (10th–90th percentile), not an 80% chance at each endpoint · "
            "SIM/MATH = the probability from each independent model path. MANUAL/PAID API source labels show exactly where each line came from. Adding or changing a line never changes the frozen projection. Click a pitcher row for the full breakdown. Headline projections are green."'''
s = replace_once(s, caption_old, caption_new, "starter slate caption")
p.write_text(s)


# 2) Weather: the schedule is already hydrated with venue data. Preserve its
# coordinates and pass them directly into the weather lookup. Also explicitly
# hydrate location on the venue endpoint as a fallback.
p = Path("automation/daily_projection_runner.py")
s = p.read_text()

venue_lookup_old = '''        data = get_json(f"venues/{int(venue_id)}", {})
        venues = data.get("venues") or []'''
venue_lookup_new = '''        data = get_json(f"venues/{int(venue_id)}", {"hydrate": "location"})
        venues = data.get("venues") or []'''
s = replace_once(s, venue_lookup_old, venue_lookup_new, "venue location hydration")

weather_func_old = '''@lru_cache(maxsize=128)
def game_weather(venue_id: int, game_time: str) -> WeatherDelayRisk:
    coords = venue_coordinates(int(venue_id or 0))
    if not coords:
        return WeatherDelayRisk("UNKNOWN", "", None, None, None, "Venue coordinates unavailable for weather risk.", False)
    return fetch_weather_delay_risk(coords[0], coords[1], str(game_time or ""))


def weather_snapshot_fields(venue_id: int, game_time: str) -> dict[str, object]:
    risk = game_weather(int(venue_id or 0), str(game_time or ""))'''
weather_func_new = '''@lru_cache(maxsize=128)
def game_weather(
    venue_id: int,
    game_time: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> WeatherDelayRisk:
    coords = None
    try:
        if latitude is not None and longitude is not None and pd.notna(latitude) and pd.notna(longitude):
            coords = (float(latitude), float(longitude))
    except (TypeError, ValueError):
        coords = None
    if not coords:
        coords = venue_coordinates(int(venue_id or 0))
    if not coords:
        return WeatherDelayRisk("UNKNOWN", "", None, None, None, "Venue coordinates unavailable for weather risk.", False)
    return fetch_weather_delay_risk(coords[0], coords[1], str(game_time or ""))


def weather_snapshot_fields(
    venue_id: int,
    game_time: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, object]:
    risk = game_weather(int(venue_id or 0), str(game_time or ""), latitude, longitude)'''
s = replace_once(s, weather_func_old, weather_func_new, "weather coordinate pass-through")

schedule_anchor = '''            teams = game.get("teams", {})
            venue_node = game.get("venue", {}) or {}
            for side, other in (("away", "home"), ("home", "away")):'''
schedule_new = '''            teams = game.get("teams", {})
            venue_node = game.get("venue", {}) or {}
            venue_location = venue_node.get("location", {}) or {}
            venue_coords = venue_location.get("defaultCoordinates", {}) or {}
            venue_latitude = pd.to_numeric(pd.Series([venue_coords.get("latitude")]), errors="coerce").iloc[0]
            venue_longitude = pd.to_numeric(pd.Series([venue_coords.get("longitude")]), errors="coerce").iloc[0]
            venue_latitude = None if pd.isna(venue_latitude) else float(venue_latitude)
            venue_longitude = None if pd.isna(venue_longitude) else float(venue_longitude)
            for side, other in (("away", "home"), ("home", "away")):'''
s = replace_once(s, schedule_anchor, schedule_new, "schedule venue coordinates")

row_anchor = '''                    "venue_id": int(venue_node.get("id", 0) or 0),
                    "venue": venue_node.get("name", "Unknown"),
                    "game_time": game.get("gameDate", ""),'''
row_new = '''                    "venue_id": int(venue_node.get("id", 0) or 0),
                    "venue": venue_node.get("name", "Unknown"),
                    "venue_latitude": venue_latitude,
                    "venue_longitude": venue_longitude,
                    "game_time": game.get("gameDate", ""),'''
s = replace_once(s, row_anchor, row_new, "schedule row venue coordinates")

project_weather_old = '''    weather = weather_snapshot_fields(int(row.get("venue_id", 0) or 0), str(row.get("game_time", "")))'''
project_weather_new = '''    weather = weather_snapshot_fields(
        int(row.get("venue_id", 0) or 0),
        str(row.get("game_time", "")),
        row.get("venue_latitude"),
        row.get("venue_longitude"),
    )'''
s = replace_once(s, project_weather_old, project_weather_new, "project weather coordinates")

refresh_weather_old = '''        fields = weather_snapshot_fields(int(scheduled.get("venue_id", 0) or 0), str(scheduled.get("game_time", "")))'''
refresh_weather_new = '''        fields = weather_snapshot_fields(
            int(scheduled.get("venue_id", 0) or 0),
            str(scheduled.get("game_time", "")),
            scheduled.get("venue_latitude"),
            scheduled.get("venue_longitude"),
        )'''
s = replace_once(s, refresh_weather_old, refresh_weather_new, "weather refresh coordinates")

p.write_text(s)
print("starter slate line display + weather coordinate fix applied")

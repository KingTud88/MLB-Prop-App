from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"{label} anchor missing")
    return text.replace(old, new, 1)


p = Path("streamlit_app.py")
s = p.read_text(encoding="utf-8")

# Preserve current game coordinates on the live Projection page. Defaults keep
# any other GamePitcher construction backward-compatible.
s = replace_once(
    s,
    '''class GamePitcher:\n    key:str; pitcher_id:int; pitcher_name:str; team:str; opponent:str; side:str; venue_id:int; venue:str; game_pk:int; game_time:str; status:str''',
    '''class GamePitcher:\n    key:str; pitcher_id:int; pitcher_name:str; team:str; opponent:str; side:str; venue_id:int; venue:str; game_pk:int; game_time:str; status:str; venue_latitude:float|None=None; venue_longitude:float|None=None''',
    "GamePitcher venue coordinates",
)

# Ask the schedule endpoint for location data so neutral/special-site games can
# carry their own coordinates instead of depending on a static park table.
s = replace_once(
    s,
    '''try:p=MLBClient().get("schedule",{"sportId":1,"date":day,"hydrate":"probablePitcher,team,venue"})''',
    '''try:p=MLBClient().get("schedule",{"sportId":1,"date":day,"hydrate":"probablePitcher,team,venue(location)"})''',
    "schedule venue location hydrate",
)

s = replace_once(
    s,
    '''            teams=game.get("teams",{}); pk=int(game.get("gamePk",0)); venue_node=game.get("venue",{}) or {}; venue=venue_node.get("name","Unknown"); venue_id=int(venue_node.get("id",0) or 0)''',
    '''            teams=game.get("teams",{}); pk=int(game.get("gamePk",0)); venue_node=game.get("venue",{}) or {}; venue=venue_node.get("name","Unknown"); venue_id=int(venue_node.get("id",0) or 0)\n            venue_location=venue_node.get("location",{}) or {}; venue_coords=venue_location.get("defaultCoordinates",{}) or {}\n            venue_latitude=pd.to_numeric(pd.Series([venue_coords.get("latitude")]),errors="coerce").iloc[0]; venue_longitude=pd.to_numeric(pd.Series([venue_coords.get("longitude")]),errors="coerce").iloc[0]\n            venue_latitude=None if pd.isna(venue_latitude) else float(venue_latitude); venue_longitude=None if pd.isna(venue_longitude) else float(venue_longitude)''',
    "schedule venue coordinate extraction",
)

s = replace_once(
    s,
    '''                rows.append(GamePitcher(f"{pk}:{pit['id']}",int(pit["id"]),pit.get("fullName","Unknown"),team,opponent,side.title(),venue_id,venue,pk,game.get("gameDate",""),game.get("status",{}).get("detailedState","Scheduled")))''',
    '''                rows.append(GamePitcher(f"{pk}:{pit['id']}",int(pit["id"]),pit.get("fullName","Unknown"),team,opponent,side.title(),venue_id,venue,pk,game.get("gameDate",""),game.get("status",{}).get("detailedState","Scheduled"),venue_latitude=venue_latitude,venue_longitude=venue_longitude))''',
    "schedule GamePitcher coordinate pass-through",
)

old_lookup = '''@st.cache_data(ttl=21600,show_spinner=False)\ndef get_venue_coordinates(venue_id):\n    if not venue_id: return None\n    try:\n        payload=MLBClient().get(f"venues/{int(venue_id)}",{})\n        venues=payload.get("venues") or []\n        coords=((venues[0].get("location") or {}).get("defaultCoordinates") or {}) if venues else {}\n        lat=coords.get("latitude"); lon=coords.get("longitude")\n        return (float(lat),float(lon)) if lat is not None and lon is not None else None\n    except Exception:\n        return None\n\n@st.cache_data(ttl=900,show_spinner=False)\ndef get_game_weather(venue_id,game_time):\n    coords=get_venue_coordinates(venue_id)\n    if not coords:\n        return WeatherDelayRisk("UNKNOWN","",None,None,None,"Venue coordinates unavailable for weather risk.",False)\n    return fetch_weather_delay_risk(coords[0],coords[1],game_time)'''

new_lookup = '''@st.cache_data(ttl=21600,show_spinner=False)\ndef get_venue_coordinates(venue_id):\n    if not venue_id: return None\n    target_id=int(venue_id)\n\n    # Primary fallback: ask MLB's venue endpoint explicitly for location data.\n    try:\n        payload=MLBClient().get(f"venues/{target_id}",{"hydrate":"location"})\n        venues=payload.get("venues") or []\n        coords=((venues[0].get("location") or {}).get("defaultCoordinates") or {}) if venues else {}\n        lat=coords.get("latitude"); lon=coords.get("longitude")\n        if lat is not None and lon is not None:\n            return float(lat),float(lon)\n    except Exception:\n        pass\n\n    # Secondary fallback for current MLB home parks: resolve the same venue ID\n    # through the live team directory with hydrated venue location data. This\n    # avoids a stale hard-coded stadium table when parks/names change.\n    try:\n        payload=MLBClient().get("teams",{"sportId":1,"hydrate":"venue(location)"})\n        for team_node in payload.get("teams",[]) or []:\n            venue_node=team_node.get("venue",{}) or {}\n            if int(venue_node.get("id",0) or 0) != target_id:\n                continue\n            coords=((venue_node.get("location") or {}).get("defaultCoordinates") or {})\n            lat=coords.get("latitude"); lon=coords.get("longitude")\n            if lat is not None and lon is not None:\n                return float(lat),float(lon)\n    except Exception:\n        pass\n    return None\n\n@st.cache_data(ttl=900,show_spinner=False)\ndef get_game_weather(venue_id,game_time,latitude=None,longitude=None):\n    coords=None\n    try:\n        if latitude is not None and longitude is not None and pd.notna(latitude) and pd.notna(longitude):\n            coords=(float(latitude),float(longitude))\n    except (TypeError,ValueError):\n        coords=None\n    if not coords:\n        coords=get_venue_coordinates(venue_id)\n    if not coords:\n        return WeatherDelayRisk("UNKNOWN","",None,None,None,"Venue coordinates unavailable for weather risk.",False)\n    return fetch_weather_delay_risk(coords[0],coords[1],game_time)'''

s = replace_once(s, old_lookup, new_lookup, "live Projection weather coordinate resolver")

s = replace_once(
    s,
    '''weather_risk=get_game_weather(game.venue_id,game.game_time)''',
    '''weather_risk=get_game_weather(game.venue_id,game.game_time,game.venue_latitude,game.venue_longitude)''',
    "live weather coordinate call",
)

p.write_text(s, encoding="utf-8")
print("Applied live Projection MLB venue-coordinate resolution v11")

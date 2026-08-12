from pathlib import Path

PAGE = Path("streamlit_app.py")
TEST_WEATHER = Path("tests/test_weather_risk.py")
TEST_PAGE = Path("tests/test_projection_weather_batter_contract.py")
text = PAGE.read_text(encoding="utf-8")

replacements = [
    (
        'from engine.starter_history import TARGET_STARTER_HISTORY, combine_starter_history, starter_only\n',
        'from engine.starter_history import TARGET_STARTER_HISTORY, combine_starter_history, starter_only\nfrom engine.opposing_batters import get_opposing_batters, matchup_summary\nfrom engine.weather_risk import WeatherDelayRisk, fetch_weather_delay_risk\n',
    ),
    (
        'class GamePitcher:\n    key:str; pitcher_id:int; pitcher_name:str; team:str; opponent:str; side:str; venue:str; game_pk:int; game_time:str; status:str\n',
        'class GamePitcher:\n    key:str; pitcher_id:int; pitcher_name:str; team:str; opponent:str; side:str; venue_id:int; venue:str; game_pk:int; game_time:str; status:str\n',
    ),
    (
        '            teams=game.get("teams",{}); pk=int(game.get("gamePk",0)); venue=game.get("venue",{}).get("name","Unknown")\n',
        '            teams=game.get("teams",{}); pk=int(game.get("gamePk",0)); venue_node=game.get("venue",{}) or {}; venue=venue_node.get("name","Unknown"); venue_id=int(venue_node.get("id",0) or 0)\n',
    ),
    (
        '                rows.append(GamePitcher(f"{pk}:{pit[\'id\']}",int(pit["id"]),pit.get("fullName","Unknown"),team,opponent,side.title(),venue,pk,game.get("gameDate",""),game.get("status",{}).get("detailedState","Scheduled")))\n',
        '                rows.append(GamePitcher(f"{pk}:{pit[\'id\']}",int(pit["id"]),pit.get("fullName","Unknown"),team,opponent,side.title(),venue_id,venue,pk,game.get("gameDate",""),game.get("status",{}).get("detailedState","Scheduled")))\n',
    ),
    (
        'def shrink(rate,opp,prior=.224,weight=120): return (rate*opp+prior*weight)/max(opp+weight,1)\n\n',
        '''def shrink(rate,opp,prior=.224,weight=120): return (rate*opp+prior*weight)/max(opp+weight,1)\n\n@st.cache_data(ttl=1800,show_spinner=False)\ndef get_pitcher_hand(pid):\n    try:\n        payload=MLBClient().get(f"people/{int(pid)}",{})\n        people=payload.get("people") or []\n        return str(((people[0].get("pitchingHand") or {}).get("code")) or "").upper() if people else ""\n    except Exception:\n        return ""\n\n@st.cache_data(ttl=21600,show_spinner=False)\ndef get_venue_coordinates(venue_id):\n    if not venue_id: return None\n    try:\n        payload=MLBClient().get(f"venues/{int(venue_id)}",{})\n        venues=payload.get("venues") or []\n        coords=((venues[0].get("location") or {}).get("defaultCoordinates") or {}) if venues else {}\n        lat=coords.get("latitude"); lon=coords.get("longitude")\n        return (float(lat),float(lon)) if lat is not None and lon is not None else None\n    except Exception:\n        return None\n\n@st.cache_data(ttl=900,show_spinner=False)\ndef get_game_weather(venue_id,game_time):\n    coords=get_venue_coordinates(venue_id)\n    if not coords:\n        return WeatherDelayRisk("UNKNOWN","",None,None,None,"Venue coordinates unavailable for weather risk.",False)\n    return fetch_weather_delay_risk(coords[0],coords[1],game_time)\n\n''',
    ),
    (
        'def build_engine_features(log,game):\n',
        'def build_engine_features(log,game,opponent_k_pct=.224,lineup_batters=0):\n',
    ),
    (
        '"opponent_k_pct":.224',
        '"opponent_k_pct":float(np.clip(opponent_k_pct,.08,.45))',
    ),
    (
        '"lineup_batters":0',
        '"lineup_batters":int(lineup_batters)',
    ),
    (
        'def calculate_projection(log,game,simulations):\n',
        'def calculate_projection(log,game,simulations,opponent_k_pct=.224,lineup_batters=0):\n',
    ),
    (
        'features=build_engine_features(log,game); engine=ProjectionEngine',
        'features=build_engine_features(log,game,opponent_k_pct,lineup_batters); engine=ProjectionEngine',
    ),
    (
        'if log.empty: st.error(herr or "Pitcher starter history unavailable."); st.stop()\nproj=calculate_projection(log,game,25000); kdf=ladder(proj,10)\nfeatures_for_hits=build_engine_features(log,game)\n',
        '''if log.empty: st.error(herr or "Pitcher starter history unavailable."); st.stop()\npitcher_hand=get_pitcher_hand(game.pitcher_id)\nopposing_batters=get_opposing_batters(game.opponent,pitcher_hand,selected_date.year)\nopponent_matchup=matchup_summary(opposing_batters)\nweather_risk=get_game_weather(game.venue_id,game.game_time)\nproj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),len(opposing_batters)); kdf=ladder(proj,10)\nfeatures_for_hits=build_engine_features(log,game,float(opponent_matchup["k_rate"]),len(opposing_batters))\n''',
    ),
    (
        'st.markdown(f\'<div class="pitcher-card"><h2>{game.pitcher_name.upper()}</h2><b>{game.team} vs {game.opponent}</b><br><span class="search-note">{game.venue} · {game.side} · {game.status}</span></div>\',unsafe_allow_html=True)\n',
        '''weather_marker=f" {weather_risk.icon}" if weather_risk.icon else ""\nst.markdown(f'<div class="pitcher-card"><h2>{game.pitcher_name.upper()}{weather_marker}</h2><b>{game.team} vs {game.opponent}</b><br><span class="search-note">{game.venue} · {game.side} · {game.status}</span></div>',unsafe_allow_html=True)\nif weather_risk.available and weather_risk.level in {"HIGH","ELEVATED"}:\n    st.warning(f"{weather_risk.icon} {weather_risk.summary}. Weather risk is informational and does not currently modify the projection.")\nelif weather_risk.available and weather_risk.level == "LOW":\n    st.caption(f"{weather_risk.icon} {weather_risk.summary}. Informational only.")\n''',
    ),
    (
        'render_reco(h2,hit_reco)\nst.markdown("#### Add recommendation to Bet Tracker")\n',
        '''render_reco(h2,hit_reco)\n\nst.markdown('<div class="section-head">OPPOSING BATTER BOX</div>',unsafe_allow_html=True)\nst.caption(f"Active {game.opponent} hitters vs a {pitcher_hand or 'unknown-hand'} pitcher. K% is the same pitcher-hand split used by the matchup input; this box is supplemental and safely degrades when MLB split data is incomplete.")\nif opposing_batters.empty:\n    st.info("Opposing batter split data is not available yet. The projection falls back to the protected league opponent-K baseline.")\nelse:\n    b1,b2,b3,b4=st.columns(4)\n    b1.metric("Matchup K%",f"{float(opponent_matchup['k_rate']):.1%}")\n    b2.metric("Split PA",int(opponent_matchup["pa"]))\n    b3.metric("HIGH K hitters",int(opponent_matchup["high"]))\n    b4.metric("ELEVATED K hitters",int(opponent_matchup["elevated"]))\n    batter_display=opposing_batters.copy()\n    batter_display["Risk"]=batter_display["Risk"].map({"HIGH":"🔥 HIGH","ELEVATED":"⚠️ ELEVATED","NORMAL":"NORMAL"}).fillna(batter_display["Risk"])\n    st.dataframe(\n        batter_display[["Batter","Hand","K% vs Pitcher","PA","Risk"]],\n        hide_index=True,\n        width="stretch",\n        column_config={\n            "Batter":st.column_config.TextColumn("Batter"),\n            "Hand":st.column_config.TextColumn("Bats"),\n            "K% vs Pitcher":st.column_config.NumberColumn(f"K% vs {pitcher_hand or 'Pitcher'}",format="%.1f%%"),\n            "PA":st.column_config.NumberColumn("Split PA",format="%.0f"),\n            "Risk":st.column_config.TextColumn("K Risk"),\n        },\n    )\n\nst.markdown("#### Add recommendation to Bet Tracker")\n''',
    ),
]

for old,new in replacements:
    if old not in text:
        raise SystemExit(f"anchor not found:\n{old[:300]}")
    text=text.replace(old,new,1)

PAGE.write_text(text,encoding="utf-8")

TEST_WEATHER.write_text('''from datetime import datetime, timezone\n\nfrom engine.weather_risk import assess_delay_risk\n\n\ndef _hourly(prob=5, precip=0.0, code=0):\n    return {\n        "time":["2026-08-12T22:00","2026-08-12T23:00","2026-08-13T00:00","2026-08-13T01:00","2026-08-13T02:00","2026-08-13T03:00"],\n        "precipitation_probability":[prob]*6,\n        "precipitation":[precip]*6,\n        "weather_code":[code]*6,\n    }\n\n\ndef test_clear_weather_has_no_badge():\n    result=assess_delay_risk(_hourly(),datetime(2026,8,13,0,0,tzinfo=timezone.utc))\n    assert result.level == "NONE"\n    assert result.icon == ""\n\n\ndef test_thunderstorm_is_high_delay_risk():\n    result=assess_delay_risk(_hourly(prob=55,precip=1.0,code=95),datetime(2026,8,13,0,0,tzinfo=timezone.utc))\n    assert result.level == "HIGH"\n    assert result.icon == "⛈️"\n    assert "thunderstorm" in result.summary\n\n\ndef test_moderate_rain_is_elevated_delay_risk():\n    result=assess_delay_risk(_hourly(prob=45,precip=.8,code=61),datetime(2026,8,13,0,0,tzinfo=timezone.utc))\n    assert result.level == "ELEVATED"\n    assert result.icon == "🌩️"\n''',encoding="utf-8")

TEST_PAGE.write_text('''from pathlib import Path\n\n\ndef test_projection_page_has_weather_badge_and_batter_box():\n    text=Path("streamlit_app.py").read_text(encoding="utf-8")\n    assert "get_game_weather(game.venue_id,game.game_time)" in text\n    assert "weather_marker" in text\n    assert "Weather risk is informational and does not currently modify the projection" in text\n    assert "OPPOSING BATTER BOX" in text\n    assert "get_opposing_batters(game.opponent,pitcher_hand,selected_date.year)" in text\n    assert 'float(opponent_matchup["k_rate"])' in text\n    assert "HIGH K hitters" in text\n    assert "ELEVATED K hitters" in text\n\n\ndef test_projection_page_compiles():\n    source=Path("streamlit_app.py").read_text(encoding="utf-8")\n    compile(source,"streamlit_app.py","exec")\n''',encoding="utf-8")

from pathlib import Path


def test_daily_runner_captures_weather_without_model_factor_change():
    text=Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    assert "weather_snapshot_fields" in text
    assert "attach_pregame_weather" in text
    assert '"weather_delay_risk"' in text
    assert '"weather_icon"' in text
    assert '"weather_factor": 1.0' in text


def test_daily_and_top_plays_surface_weather_icons():
    daily=Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    top=Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")
    assert '"weather_delay_risk": "Weather"' in daily
    assert 'weather_icon' in daily
    assert '"Weather Icon"' in top
    assert "Weather is informational and does not affect Top 5 ranking" in top


def test_model_board_only_carries_weather_metadata():
    text=Path("engine/model_top_plays.py").read_text(encoding="utf-8")
    assert '"Weather Icon": weather_icon_for_display' in text
    assert '"Weather Risk": clean_ui_text' in text
    assert '"Weather Summary": clean_ui_text' in text
    assert 'sort_values(["Model Probability", "Data Quality"]' in text
    assert 'sort_values(["Weather' not in text


def test_changed_pages_compile():
    for path in ["automation/daily_projection_runner.py","pages/5_Daily_Projection_Run.py","pages/6_Top_Plays.py","engine/model_top_plays.py"]:
        compile(Path(path).read_text(encoding="utf-8"),path,"exec")

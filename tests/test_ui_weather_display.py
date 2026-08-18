from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from engine.ui_weather import clean_ui_text, saved_weather_risk, weather_icon_for_display
from training.projection_storage import overlay_manual_market_lines


def test_ui_text_and_weather_icons_never_leak_nan() -> None:
    assert clean_ui_text(np.nan) == ""
    assert clean_ui_text(" NaN ") == ""
    assert weather_icon_for_display("NONE", np.nan) == "☀️"
    assert weather_icon_for_display("ROOF", "") == "🏟️"
    assert weather_icon_for_display("HIGH", "") == "⛈️"
    assert weather_icon_for_display("UNKNOWN", np.nan, unknown="") == ""


def test_overlay_cleans_blank_weather_icon_without_touching_player() -> None:
    slate = pd.DataFrame([
        {"game_pk": 824803, "pitcher_id": 607074, "player": "Carlos Rodón", "weather_delay_risk": "NONE", "weather_icon": np.nan}
    ])
    result = overlay_manual_market_lines(slate, pd.DataFrame())
    assert result.loc[0, "player"] == "Carlos Rodón"
    assert result.loc[0, "weather_icon"] == "☀️"


def test_saved_weather_fallback_uses_latest_exact_game_pitcher_only() -> None:
    frame = pd.DataFrame([
        {"game_pk": 1, "pitcher_id": 10, "captured_at_utc": "2026-08-18T04:00:00Z", "weather_delay_risk": "LOW", "weather_icon": "🌧️", "weather_precip_probability": 25, "weather_precip_mm": 0.1, "weather_summary": "older"},
        {"game_pk": 1, "pitcher_id": 10, "captured_at_utc": "2026-08-18T12:00:00Z", "weather_delay_risk": "NONE", "weather_icon": np.nan, "weather_precip_probability": 0, "weather_precip_mm": 0, "weather_summary": "latest"},
        {"game_pk": 2, "pitcher_id": 10, "captured_at_utc": "2026-08-18T13:00:00Z", "weather_delay_risk": "HIGH", "weather_icon": "⛈️", "weather_summary": "wrong game"},
    ])
    risk = saved_weather_risk(frame, 1, 10)
    assert risk is not None
    assert risk.available is True
    assert risk.level == "NONE"
    assert risk.icon == ""
    assert risk.precip_probability == 0.0
    assert risk.summary == "latest"
    assert weather_icon_for_display(risk.level, risk.icon) == "☀️"


def test_page_contracts_use_display_safe_weather_without_model_change() -> None:
    main = Path("streamlit_app.py").read_text(encoding="utf-8")
    daily = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    command = Path("engine/ui_command_center.py").read_text(encoding="utf-8")
    board = Path("engine/model_top_plays.py").read_text(encoding="utf-8")
    runner = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    history = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")

    assert "saved_weather_risk(load_projection_history(),game.game_pk,game.pitcher_id)" in main
    assert "weather_icon=_weather_icon" in main
    assert "str(r.get('weather_icon', '') or '')" not in daily
    assert "weather_symbol = weather_icon_for_display(level, weather_icon)" in command
    assert '"Weather Icon": weather_icon_for_display' in board
    assert '"weather_factor": 1.0' in runner
    assert '"nan", "none", "null", "nat", "<na>"' in history

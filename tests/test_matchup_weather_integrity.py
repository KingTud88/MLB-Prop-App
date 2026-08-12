from pathlib import Path

import pandas as pd

from engine.projection_engine import ProjectionEngine
import automation.daily_projection_runner as runner


def _features(opponent_k):
    return {
        "pitcher_k_pct": .24,
        "opponent_k_pct": opponent_k,
        "expected_bf": 23,
        "bf_sd": 2.5,
        "historical_k_sd": 2.0,
        "historical_games": 20,
        "lineup_batters": 0,
        "arsenal_sample_size": 0,
        "weather_available": 0,
        "umpire_available": 0,
        "handedness_factor": 1.0,
        "arsenal_factor": 1.0,
        "park_factor": 1.0,
        "umpire_factor": 1.0,
        "weather_factor": 1.0,
        "rest_factor": 1.0,
    }


def test_projection_engine_preserves_explicit_matchup_input():
    low = ProjectionEngine(seed=7).project(_features(.15), draws=2000)
    high = ProjectionEngine(seed=7).project(_features(.35), draws=2000)
    assert high.ensemble_mean > low.ensemble_mean


def test_active_roster_batter_box_does_not_claim_confirmed_lineup_quality():
    text = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),0)' in text
    assert 'build_engine_features(log,game,float(opponent_matchup["k_rate"]),0)' in text


def test_pregame_weather_can_change_on_later_refresh(monkeypatch):
    frame = pd.DataFrame([{
        "game_pk": 1, "pitcher_id": 2, "game_time": "2099-08-12T23:00:00Z",
        "venue_id": 10, "weather_delay_risk": "NONE", "weather_icon": "",
        "weather_precip_probability": 5.0, "weather_precip_mm": 0.0, "weather_summary": "Clear",
    }])
    announced = [{"game_pk": 1, "pitcher_id": 2, "game_time": "2099-08-12T23:00:00Z", "venue_id": 10}]
    monkeypatch.setattr(runner, "weather_snapshot_fields", lambda venue_id, game_time: {
        "weather_delay_risk": "HIGH", "weather_icon": "⛈️",
        "weather_precip_probability": 80.0, "weather_precip_mm": 3.0, "weather_summary": "High weather-delay risk",
    })
    updated = runner.attach_pregame_weather(frame, announced)
    assert updated == 1
    assert frame.loc[0, "weather_delay_risk"] == "HIGH"
    assert frame.loc[0, "weather_icon"] == "⛈️"


def test_projection_engine_has_no_caller_frame_matchup_override():
    text = Path("engine/projection_engine.py").read_text(encoding="utf-8")
    assert "inspect.currentframe" not in text
    assert "silently replace an explicit opponent K input" in text

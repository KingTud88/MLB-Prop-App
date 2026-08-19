from pathlib import Path


def test_pitcher_hand_uses_mlb_person_pitch_hand_key():
    app = Path("streamlit_app.py").read_text(encoding="utf-8")
    runner = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    assert 'get("pitchHand")' in app
    assert 'get("pitchHand")' in runner


def test_projection_has_no_direct_paid_odds_error_path():
    app = Path("streamlit_app.py").read_text(encoding="utf-8")
    odds = Path("engine/odds_snapshot.py").read_text(encoding="utf-8")
    assert 'get_event_props' not in app
    assert 'load_pitcher_market_odds' in app
    assert 'load_pitcher_strikeout_odds' not in app
    assert 'type(exc).__name__' in odds


def test_batter_box_reads_bat_side_from_hydrated_person():
    text = Path("engine/opposing_batters.py").read_text(encoding="utf-8")
    assert 'person.get("batSide")' in text
    assert '"Hand": person_bat_side' in text

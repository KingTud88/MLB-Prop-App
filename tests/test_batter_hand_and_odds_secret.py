from pathlib import Path


def test_pitcher_hand_uses_mlb_person_pitch_hand_key():
    app = Path("streamlit_app.py").read_text(encoding="utf-8")
    runner = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    assert 'get("pitchHand")' in app
    assert 'get("pitchHand")' in runner


def test_odds_errors_never_render_raw_exception_url_or_key():
    app = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'safe_odds_error' in app
    assert 'f"Odds API unavailable: {e}"' not in app
    assert 'authentication failed (401)' in app


def test_batter_box_reads_bat_side_from_hydrated_person():
    text = Path("engine/opposing_batters.py").read_text(encoding="utf-8")
    assert 'person.get("batSide")' in text
    assert '"Hand": person_bat_side' in text

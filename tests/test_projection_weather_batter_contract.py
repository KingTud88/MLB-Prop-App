from pathlib import Path


def test_projection_page_has_weather_badge_and_batter_box():
    text=Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "get_game_weather(game.venue_id,game.game_time)" in text
    assert "weather_marker" in text
    assert "Weather risk is informational and does not currently modify the projection" in text
    assert "OPPOSING BATTER BOX" in text
    assert "get_confirmed_lineup(game.game_pk,opponent_team_id)" in text
    assert "lineup_context.player_ids if lineup_context.confirmed else ()" in text
    assert "ACTIVE ROSTER FALLBACK" in text
    assert "CONFIRMED BATTING ORDER" in text
    assert 'float(opponent_matchup["k_rate"])' in text
    assert "HIGH K hitters" in text
    assert "ELEVATED K hitters" in text
    assert '*100.0' in text


def test_projection_page_compiles():
    source=Path("streamlit_app.py").read_text(encoding="utf-8")
    compile(source,"streamlit_app.py","exec")

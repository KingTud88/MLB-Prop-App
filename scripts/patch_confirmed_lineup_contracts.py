from pathlib import Path


path = Path("tests/test_matchup_weather_integrity.py")
text = path.read_text(encoding="utf-8")
old = '''def test_active_roster_batter_box_does_not_claim_confirmed_lineup_quality():
    text = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),0)' in text
    assert 'build_engine_features(log,game,float(opponent_matchup["k_rate"]),0)' in text
'''
new = '''def test_lineup_quality_credit_requires_confirmed_nine_man_order():
    text = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'confirmed_count=lineup_context.batter_count if lineup_context.confirmed else 0' in text
    assert 'calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count)' in text
    assert 'build_engine_features(log,game,float(opponent_matchup["k_rate"]),confirmed_count)' in text
'''
if old not in text:
    raise SystemExit("matchup-weather contract anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")


path = Path("tests/test_projection_weather_batter_contract.py")
text = path.read_text(encoding="utf-8")
old = '    assert "get_opposing_batters(game.opponent,pitcher_hand,selected_date.year)" in text\n'
new = '''    assert "get_confirmed_lineup(game.game_pk,opponent_team_id)" in text
    assert "lineup_context.player_ids if lineup_context.confirmed else ()" in text
    assert "ACTIVE ROSTER FALLBACK" in text
    assert "CONFIRMED BATTING ORDER" in text
'''
if old not in text:
    raise SystemExit("projection batter contract anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

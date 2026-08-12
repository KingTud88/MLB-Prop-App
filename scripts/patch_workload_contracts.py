from pathlib import Path


# Daily projection page now materializes workload actuals in addition to K/Hits/Outs.
path = Path("tests/test_daily_projection_page_contract.py")
text = path.read_text(encoding="utf-8")
old = '    assert \'for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs")\' in source\n'
new = '    assert \'for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches")\' in source\n'
if old not in text:
    raise SystemExit("daily legacy resolution contract anchor missing")
text = text.replace(old, new, 1)
text += '''\n\ndef test_daily_projection_page_tracks_workload_actuals():\n    source = (Path(__file__).resolve().parents[1] / "pages" / "5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert 'actual_batters_faced' in source\n    assert 'actual_pitches' in source\n    assert 'resolve_workload_actuals' in source\n'''
path.write_text(text, encoding="utf-8")


# Confirmed-lineup quality contract now passes the same shared workload context
# into both projection and feature construction.
path = Path("tests/test_matchup_weather_integrity.py")
text = path.read_text(encoding="utf-8")
old = '''    assert 'calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count)' in text\n    assert 'build_engine_features(log,game,float(opponent_matchup["k_rate"]),confirmed_count)' in text\n'''
new = '''    assert 'workload_ctx=build_workload_context(log,game.game_time)' in text\n    assert 'calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count,workload_ctx)' in text\n    assert 'build_engine_features(log,game,float(opponent_matchup["k_rate"]),confirmed_count,workload_ctx)' in text\n'''
if old not in text:
    raise SystemExit("lineup workload contract anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

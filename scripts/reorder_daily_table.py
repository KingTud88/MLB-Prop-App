from pathlib import Path

path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")
old = '''        display_cols = [
            "player", "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games", "workload_version", "expected_pitches", "expected_bf", "expected_outs", "pitches_per_bf", "days_since_last_start", "leash_label", "pitch_trend", "weather_icon", "weather_delay_risk", "weather_precip_probability", "lineup_source", "lineup_batters", "lineup_projection_delta", "team", "opponent", "projection", "k_range_low", "k_range_high",
            "hits_projection", "hits_range_low", "hits_range_high",
            "outs_projection", "outs_range_low", "outs_range_high",
            "confidence", "data_quality", "opponent_k_pct", "sim_5p", "math_5p",
            "hits_sim_over_5_5", "hits_math_over_5_5", "outs_sim_over_15_5", "outs_math_over_15_5", "probability_semantics",
            "actual_strikeouts", "actual_hits_allowed", "actual_outs",
        ]
'''
new = '''        # Keep the primary projection scan tight: pitcher/matchup first, then Ks.
        # Audit/context fields (weather, starter sample, workload) stay available
        # but live farther right so they do not separate the pitcher from Projection K.
        display_cols = [
            "player", "team", "opponent", "projection", "k_range_low", "k_range_high", "sim_5p", "math_5p",
            "hits_projection", "hits_range_low", "hits_range_high", "hits_sim_over_5_5", "hits_math_over_5_5",
            "outs_projection", "outs_range_low", "outs_range_high", "outs_sim_over_15_5", "outs_math_over_15_5",
            "confidence", "data_quality", "opponent_k_pct",
            "lineup_source", "lineup_batters", "lineup_projection_delta",
            "weather_icon", "weather_delay_risk", "weather_precip_probability",
            "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games",
            "workload_version", "expected_pitches", "expected_bf", "expected_outs", "pitches_per_bf", "days_since_last_start", "leash_label", "pitch_trend",
            "probability_semantics", "actual_strikeouts", "actual_hits_allowed", "actual_outs",
        ]
'''
if old not in text:
    raise SystemExit("daily display_cols anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

contract = Path("tests/test_daily_table_order.py")
contract.write_text('''from pathlib import Path\n\n\ndef test_daily_projection_table_keeps_k_projection_near_pitcher():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    block_start = source.index("display_cols = [", source.index("if not slate.empty:"))\n    block_end = source.index("]", block_start)\n    block = source[block_start:block_end]\n    assert block.index('"player"') < block.index('"team"') < block.index('"opponent"') < block.index('"projection"')\n    assert block.index('"projection"') < block.index('"weather_delay_risk"')\n    assert block.index('"projection"') < block.index('"starter_history_games"')\n    assert block.index('"projection"') < block.index('"workload_version"')\n    assert block.index('"sim_5p"') < block.index('"weather_delay_risk"')\n''', encoding="utf-8")

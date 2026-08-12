from pathlib import Path

path = Path("automation/daily_projection_runner.py")
text = path.read_text(encoding="utf-8")
old = '''        for field, value in projected.items():\n            if field not in protected:\n                frame.at[idx, field] = value\n'''
new = '''        for field, value in projected.items():\n            if field not in protected and not field.startswith("team_leash_"):\n                frame.at[idx, field] = value\n'''
if old not in text:
    raise SystemExit("lineup refresh copy anchor missing")
text = text.replace(old, new, 1)

old = '''    refreshed = fill_missing_pregame_paths(frame)\n    lineup_refreshes = refresh_pregame_lineups(frame, rows)\n'''
new = '''    refreshed = fill_missing_pregame_paths(frame)\n    team_leash_refreshes += attach_pregame_team_leash(frame)\n    lineup_refreshes = refresh_pregame_lineups(frame, rows)\n'''
if old not in text:
    raise SystemExit("scheduled refresh order anchor missing")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

Path("tests/test_team_leash_refresh_order.py").write_text('''from pathlib import Path\n\n\ndef test_scheduled_refresh_reapplies_team_context_after_path_backfill():\n    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")\n    main = source[source.index("def main() -> None:"):]\n    fill_pos = main.index("refreshed = fill_missing_pregame_paths(frame)")\n    team_pos = main.index("team_leash_refreshes += attach_pregame_team_leash(frame)", fill_pos)\n    lineup_pos = main.index("lineup_refreshes = refresh_pregame_lineups(frame, rows)", team_pos)\n    assert fill_pos < team_pos < lineup_pos\n\n\ndef test_lineup_refresh_cannot_overwrite_team_leash_audit_fields():\n    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")\n    assert 'field not in protected and not field.startswith("team_leash_")' in source\n''', encoding="utf-8")

from pathlib import Path


def test_scheduled_refresh_reapplies_team_context_after_path_backfill():
    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    main = source[source.index("def main() -> None:"):]
    fill_pos = main.index("refreshed = fill_missing_pregame_paths(frame)")
    team_pos = main.index("team_leash_refreshes += attach_pregame_team_leash(frame)", fill_pos)
    lineup_pos = main.index("lineup_refreshes = refresh_pregame_lineups(frame, rows)", team_pos)
    assert fill_pos < team_pos < lineup_pos


def test_lineup_refresh_cannot_overwrite_team_leash_audit_fields():
    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    assert 'field not in protected and not field.startswith("team_leash_")' in source

from pathlib import Path


def test_bet_tracker_page_compiles_and_keeps_today_slate_autofill():
    path = Path(__file__).resolve().parents[1] / "pages" / "2_Bet_Tracker.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")

    assert "schedule as daily_schedule" in source
    assert "todays_slate(today_text)" in source
    assert 'pick_col.selectbox(' in source
    assert "frozen_snapshot(" in source
    assert "projection_for_market(snapshot, market)" in source
    assert '"game_pk": int(selected_pitcher["game_pk"])' in source
    assert '"pitcher_id": int(selected_pitcher["pitcher_id"])' in source

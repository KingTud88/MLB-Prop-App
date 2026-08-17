from pathlib import Path


def test_daily_runner_logs_and_refreshes_confirmed_lineups():
    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    compile(source, "automation/daily_projection_runner.py", "exec")
    assert "get_confirmed_lineup" in source
    assert '"lineup_source"' in source
    assert '"lineup_hash"' in source
    assert '"lineup_projection_delta"' in source
    assert "refresh_pregame_lineups" in source
    assert "row_is_pregame" in source
    assert 'opponent_hit_rate=float(matchup.get("hit_rate", .235))' in source


def test_projection_page_prefers_confirmed_order_and_shows_contact_profile():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    compile(source, "streamlit_app.py", "exec")
    assert "get_confirmed_lineup(game.game_pk" in source
    assert "CONFIRMED BATTING ORDER" in source
    assert "ACTIVE ROSTER FALLBACK" in source
    assert '"Lineup Spot"' in source
    assert '"H/PA vs Pitcher"' in source
    assert "opponent_hit_rate=float(opponent_matchup.get" in source


def test_history_exposes_lineup_audit():
    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    compile(source, "pages/4_Projection_History.py", "exec")
    assert "Lineup input audit" in source
    assert "Avg K Projection Delta" in source


def test_daily_confirmed_lineup_metric_has_sixth_column():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    summary = source[source.index('slate = st.session_state.get("daily_slate")'):]
    assert 'c1, c2, c3, c4, c5, c6 = st.columns(6)' in summary
    assert 'c6.metric("Confirmed lineups", confirmed_lineups, help=metric_help("daily_confirmed"))' in summary

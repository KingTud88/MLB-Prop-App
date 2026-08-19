from pathlib import Path


def test_top_plays_has_no_paid_odds_runtime():
    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")
    assert 'api_key = None  # Paid Odds API access is intentionally restricted to Daily Projection Run.' in source
    assert 'api_key = secret()' not in source


def test_projection_page_reads_saved_k_odds_without_paid_api_call():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'load_pitcher_strikeout_odds' in source
    assert 'LOAD LIVE ODDS · ≤3 credits' not in source
    assert 'odds_events,odds_err=get_odds_events()' not in source
    assert 'this page never calls the Odds API' in source


def test_daily_projection_page_owns_legacy_paid_k_backup_button_only():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert 'LOAD STRIKEOUT LINES · BACKUP API' in source
    assert 'refresh_strikeout_snapshot' in source
    assert 'Optional fallback only.' in source
    assert 'SportsGameOdds remains the primary automated execution-line source.' in source


def test_paid_snapshot_request_is_strikeouts_only_and_tracks_quota_headers():
    source = Path("engine/odds_snapshot.py").read_text(encoding="utf-8")
    assert '"markets": "pitcher_strikeouts"' in source
    assert 'pitcher_outs' not in source
    assert 'pitcher_hits_allowed' not in source
    assert 'x-requests-remaining' in source
    assert 'x-requests-used' in source
    assert 'x-requests-last' in source


def test_scheduled_projection_automation_never_calls_legacy_odds_api():
    workflow = Path(".github/workflows/daily-projection-resolver.yml").read_text(encoding="utf-8")
    runner = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    resolver = Path("automation/resolve_projection_log.py").read_text(encoding="utf-8")
    for source in (workflow, runner, resolver):
        lowered = source.lower()
        assert "the-odds-api" not in lowered
        assert "odds_api_key" not in lowered
        assert "training.daily_odds" not in lowered

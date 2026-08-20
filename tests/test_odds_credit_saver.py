from pathlib import Path


def test_top_plays_has_no_paid_odds_runtime():
    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")
    assert 'api_key = secret()' not in source
    assert 'api_key = None' not in source
    assert 'api.the-odds-api.com' not in source
    assert 'load_pitcher_market_odds' in source
    assert 'attach_sportsgameodds_prices' in source


def test_projection_page_reads_saved_k_odds_without_paid_api_call():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'load_pitcher_market_odds' in source
    assert 'LOAD LIVE ODDS · ≤3 credits' not in source
    assert 'odds_events,odds_err=get_odds_events()' not in source
    assert 'api.the-odds-api.com' not in source
    assert 'Central SportsGameOdds snapshot' in source
    assert 'scheduled capture distributes one saved slate snapshot to every page' in source
    assert 'fetch_live_pitcher_market_odds' not in source
    assert 'resolve_sgo_api_key' not in source
    assert 'api.the-odds-api.com' not in source


def test_daily_projection_page_has_no_visible_legacy_paid_k_controls():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert 'LOAD STRIKEOUT LINES · BACKUP API' not in source
    assert 'refresh_strikeout_snapshot' not in source
    assert 'Odds API credits remaining' not in source
    assert '📡 Automated sportsbook lines' in source


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
        assert "the_odds_api_key" not in lowered
        assert "training.daily_odds" not in lowered

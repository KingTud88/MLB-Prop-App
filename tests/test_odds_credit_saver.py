from pathlib import Path


def test_top_plays_credit_saver_requires_manual_paid_load_and_main_markets_only():
    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")
    assert 'MAIN_MARKET_KEYS = {' in source
    assert '"Strikeouts": "pitcher_strikeouts"' in source
    assert '"Total Outs": "pitcher_outs"' in source
    assert '"Hits Allowed": "pitcher_hits_allowed"' in source
    assert 'Load / reuse live Top 5 prices' in source
    assert 'estimated_credits = sum(len(markets) for markets in request_plan.values())' in source
    assert 'event_props(api_key, event_id, tuple(sorted(market_keys)))' in source
    assert 'pitcher_strikeouts,pitcher_strikeouts_alternate' not in source
    assert 'Alternate markets are disabled by default.' in source


def test_projection_page_credit_saver_has_no_automatic_paid_prop_call():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'MAIN_PROP_MARKETS="pitcher_strikeouts,pitcher_outs,pitcher_hits_allowed"' in source
    assert 'LOAD LIVE ODDS · ≤3 credits' in source
    assert 'Paid odds are OFF by default.' in source
    assert 'Alternate markets stay off.' in source
    automatic = 'if odds_event_id: odds_payload,prop_err=get_event_props(odds_event_id)'
    assert automatic not in source


def test_paid_odds_calls_cache_for_fifteen_minutes_and_track_quota_headers():
    top = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")
    app = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert '@st.cache_data(ttl=900, show_spinner=False)\ndef event_props' in top
    assert '@st.cache_data(ttl=900,show_spinner=False)\ndef get_event_props' in app
    for source in (top, app):
        assert 'x-requests-remaining' in source
        assert 'x-requests-used' in source
        assert 'x-requests-last' in source


def test_scheduled_projection_automation_never_calls_odds_api():
    workflow = Path(".github/workflows/daily-projection-resolver.yml").read_text(encoding="utf-8")
    runner = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    resolver = Path("automation/resolve_projection_log.py").read_text(encoding="utf-8")
    for source in (workflow, runner, resolver):
        lowered = source.lower()
        assert "the-odds-api" not in lowered
        assert "odds_api_key" not in lowered
        assert "training.daily_odds" not in lowered

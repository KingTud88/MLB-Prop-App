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


def test_main_projection_routes_bet_tracker_to_command_page_before_schedule_work():
    main = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    source = main.read_text(encoding="utf-8")
    route = 'if nav == "Bet Tracker":\n        st.switch_page("pages/2_Bet_Tracker.py")'
    assert route in source
    assert source.index(route) < source.index("schedule,err=get_schedule")


def test_bet_tracker_command_filters_and_sections_are_present():
    path = Path(__file__).resolve().parents[1] / "pages" / "2_Bet_Tracker.py"
    source = path.read_text(encoding="utf-8")
    assert "BET_TRACKER_FILTERS_V1" in source
    for label in (
        'selectbox("Status", ["All", "Open / Live", "Settled", "Invalid"]',
        'selectbox("Ticket type", ["All", "Straight", "Parlay"]',
        'selectbox("Pitcher", ["All"] + pitcher_options',
        'selectbox("Game date", ["All"] + date_options',
        '"OPEN / LIVE STRAIGHTS"',
        '"PARLAY TICKETS"',
        '"SETTLED STRAIGHTS"',
        '"LEGACY INVALID"',
        '"MODEL-ONLY / UNPRICED"',
        '"PRICED TRACKED BET"',
    ):
        assert label in source


def test_bet_tracker_avoids_streamlit_cache_replay_for_data_helpers():
    path = Path(__file__).resolve().parents[1] / "pages" / "2_Bet_Tracker.py"
    source = path.read_text(encoding="utf-8")
    assert "BET_TRACKER_PROCESS_TTL_CACHE_V1" in source
    assert "@st.cache_data(" not in source
    assert "@_local_ttl_cache(15)\ndef live_pitcher_prop(" in source
    assert "@_local_ttl_cache(120)\ndef todays_slate(" in source
    assert "@_local_ttl_cache(30)\ndef frozen_snapshot(" in source
    assert "live_pitcher_prop.clear()" in source

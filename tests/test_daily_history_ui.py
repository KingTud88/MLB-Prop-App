from pathlib import Path


def test_daily_page_separates_history_only_from_errors():
    text = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert "daily_history_only" in text
    assert "History-only tracked" in text
    assert "📚 History-only starters being tracked" in text
    assert "Some announced starters hit real capture errors:" in text
    assert "no usable starter history — final K / hits / outs / BF / pitches will be tracked" in text
    assert 'c5.metric("Errors", len(errors))' in text


def test_daily_page_compiles():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    compile(source, "pages/5_Daily_Projection_Run.py", "exec")


def test_daily_page_has_persistent_history_only_tracker_and_starts_used():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert "load_observation_log" in source
    assert "resolve_observation_log" in source
    assert "history_only_for_day" in source
    assert "📚 Persistent history-only starter tracker" in source
    assert "Resolved into history" in source
    assert '"starter_history_games": "Starts"' in source
    assert 'observation_updates = resolve_observation_log()' in source
    assert "It never becomes a fake historical projection or calibration row." in source


def test_daily_page_surfaces_starter_history_provenance():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert '"starter_history_source": "History"' in source
    assert '"starter_history_mlb_games": "MLB Starts"' in source
    assert '"starter_history_observation_games": "Observed Starts"' in source
    assert '"Observed starts used"' in source

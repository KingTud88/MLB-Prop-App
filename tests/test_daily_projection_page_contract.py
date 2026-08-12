from pathlib import Path


def test_daily_projection_page_materializes_legacy_resolution_columns():
    path = Path(__file__).resolve().parents[1] / "pages" / "5_Daily_Projection_Run.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert 'for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches")' in source
    assert 'frame[col] = np.nan' in source
    assert 'actual_hits.notna().sum()' in source
    assert 'actual_outs.notna().sum()' in source


def test_daily_projection_page_tracks_workload_actuals():
    source = (Path(__file__).resolve().parents[1] / "pages" / "5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert 'actual_batters_faced' in source
    assert 'actual_pitches' in source
    assert 'resolve_workload_actuals' in source

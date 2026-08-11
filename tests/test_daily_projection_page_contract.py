from pathlib import Path


def test_daily_projection_page_materializes_legacy_resolution_columns():
    path = Path(__file__).resolve().parents[1] / "pages" / "5_Daily_Projection_Run.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert 'for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs")' in source
    assert 'frame[col] = np.nan' in source
    assert 'actual_hits.notna().sum()' in source
    assert 'actual_outs.notna().sum()' in source

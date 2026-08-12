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

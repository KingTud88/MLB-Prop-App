from pathlib import Path


def test_daily_table_collapses_ranges_and_formats_probabilities_for_humans():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert '("k_range_low", "k_range_high", "80% K Range")' in source
    assert '("hits_range_low", "hits_range_high", "80% Hits Range")' in source
    assert '("outs_range_low", "outs_range_high", "80% Outs Range")' in source
    assert 'formatters[col] = "{:.1%}"' in source
    assert 'formatters[col] = "{:.2f}"' in source
    assert '80% Range = one central simulated interval' in source
    assert 'not an 80% chance at each endpoint' in source
    assert '"k_range_low": "K 80% Low"' not in source
    assert '"k_range_high": "K 80% High"' not in source


def test_daily_range_text_is_one_interval_not_two_probabilities():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert 'def _range_text(low: object, high: object) -> str:' in source
    assert 'return f"{_endpoint(float(lo))}–{_endpoint(float(hi))}"' in source

def test_projection_highlight_survives_readability_rename():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert '("Projection K", "Projection Hits", "Projection Outs")' in source
    assert 'color: #22c55e; font-weight: 700;' in source

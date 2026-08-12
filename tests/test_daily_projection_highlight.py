from pathlib import Path


def test_daily_headline_projection_numbers_are_green_and_bold():
    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert '("Projection K", "Projection Hits", "Projection Outs")' in source
    assert 'color: #22c55e; font-weight: 700;' in source
    assert 'subset=projection_highlight_cols' in source
    assert 'st.dataframe(\n            styled_display,' in source

from pathlib import Path


def test_opposing_batter_box_precedes_betting_workspace():
    source=Path("streamlit_app.py").read_text(encoding="utf-8")
    summary=source.index('PROJECTION SUMMARY')
    batter=source.index('OPPOSING BATTER BOX')
    betting=source.rindex('render_projection_betting_workspace(')
    footer=source.index('Data status:')
    assert summary < batter < betting < footer

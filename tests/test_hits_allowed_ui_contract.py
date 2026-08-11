from pathlib import Path


def test_main_projection_wires_hits_allowed_market_and_card():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "pitcher_hits_allowed" in source
    assert "pitcher_hits_allowed_alternate" in source
    assert "project_hits_allowed" in source
    assert "PROJECTED HITS ALLOWED" in source
    assert "HITS ALLOWED BET LEAN" in source
    assert 'st.switch_page("pages/6_Top_Plays.py")' in source


def test_projection_history_grades_hits_allowed():
    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    for token in (
        "hits_projection",
        "hits_range_low",
        "hits_range_high",
        "actual_hits_allowed",
        "hits_result",
        "Hits hit rate",
    ):
        assert token in source

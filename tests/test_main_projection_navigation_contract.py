from pathlib import Path


APP = Path("streamlit_app.py")


def test_dedicated_pages_stay_routed_from_main_projection_sidebar() -> None:
    text = APP.read_text(encoding="utf-8")
    assert '"Bet Tracker"' in text
    assert 'st.switch_page("pages/2_Bet_Tracker.py")' in text
    assert 'st.switch_page("pages/4_Projection_History.py")' in text
    assert 'st.switch_page("pages/5_Daily_Projection_Run.py")' in text
    assert 'st.switch_page("pages/6_Top_Plays.py")' in text


def test_dedicated_page_renderers_are_not_duplicated_inline() -> None:
    text = APP.read_text(encoding="utf-8")
    assert 'elif nav=="Bet Tracker":' not in text
    assert 'elif nav=="Projection History":' not in text
    assert 'elif nav=="Daily Projection Run":' not in text


def test_inline_projection_views_remain_available() -> None:
    text = APP.read_text(encoding="utf-8")
    assert 'if nav=="Distribution":' in text
    assert 'elif nav=="Form & Workload":' in text
    assert 'elif nav=="Model Card":' in text

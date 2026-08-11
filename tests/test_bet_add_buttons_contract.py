from pathlib import Path


def test_top_plays_page_compiles_and_has_quick_add_buttons():
    path = Path(__file__).resolve().parents[1] / "pages" / "6_Top_Plays.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert "make_bet_record" in source
    assert "append_bet(BET_LOG, record, st.secrets)" in source
    assert 'st.button("➕ Add as bet"' in source
    assert 'st.number_input("Quick-add stake (units)"' in source


def test_projection_page_has_actionable_quick_add_buttons():
    path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert "render_add_bet_button" in source
    assert '"➕ Add {market_label}"' in source
    assert "best_market_offer" in source
    assert "append_bet(BET_LOG,record,st.secrets)" in source


def test_tracker_page_applies_result_status_styling():
    path = Path(__file__).resolve().parents[1] / "pages" / "2_Bet_Tracker.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert "result_cell_css" in source
    assert 'view.style.map(result_cell_css, subset=["Result"])' in source

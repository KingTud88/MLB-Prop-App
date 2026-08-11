from pathlib import Path


def test_top_plays_page_compiles_and_has_straight_and_parlay_actions():
    path = Path(__file__).resolve().parents[1] / "pages" / "6_Top_Plays.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert "make_bet_record" in source
    assert "make_parlay_record" in source
    assert "append_bet(BET_LOG, record, st.secrets)" in source
    assert 'st.button("➕ Add as bet"' in source
    assert 'st.number_input("Straight-bet stake (units)"' in source
    assert 'st.number_input("Parlay stake (units)"' in source
    assert 'st.multiselect(\n    "Parlay legs (2–5)"' in source
    assert "candidate_pool.empty" not in source[source.index('st.subheader("🎟️ Parlay Builder")'):]
    assert "same sportsbook" not in source[source.index('st.subheader("🎟️ Parlay Builder")'):]
    assert 'Sportsbook used (optional)' not in source
    assert 'Actual parlay American odds (optional)' not in source
    assert 'book=book_note' not in source


def test_top_plays_is_model_first_and_odds_are_optional_overlay():
    path = Path(__file__).resolve().parents[1] / "pages" / "6_Top_Plays.py"
    source = path.read_text(encoding="utf-8")
    assert "build_model_board" in source
    assert 'st.subheader("Today\'s five highest-probability model legs")' in source
    assert "Sportsbook odds and market edge do not decide the Top 5" in source
    assert 'plays["Live Offer"] = False' in source
    assert "if api_key:" in source


def test_projection_page_has_actionable_quick_add_buttons():
    path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert "render_add_bet_button" in source
    assert '"➕ Add {market_label}"' in source
    assert "best_market_offer" in source
    assert "append_bet(BET_LOG,record,st.secrets)" in source


def test_tracker_page_applies_result_status_styling_and_grades_parlays():
    path = Path(__file__).resolve().parents[1] / "pages" / "2_Bet_Tracker.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert "result_cell_css" in source
    assert 'view.style.map(result_cell_css, subset=["Result"])' in source
    assert "parse_parlay_legs" in source
    assert "grade_parlay" in source
    assert 'if bet_type == "Parlay":' in source

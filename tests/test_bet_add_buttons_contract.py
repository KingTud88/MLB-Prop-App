# Top Plays UI contracts, including model-health gating and price independence.
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
    assert '"Sportsbook (recordkeeping only)"' in source
    assert 'book=parlay_book_value' in source
    parlay_block = source[source.index('st.subheader("🎟️ Parlay Builder")'):]
    assert 'candidate_pool' not in parlay_block
    assert 'parlay_book_value' in parlay_block


def test_top_plays_is_model_first_and_odds_are_optional_overlay():
    path = Path(__file__).resolve().parents[1] / "pages" / "6_Top_Plays.py"
    source = path.read_text(encoding="utf-8")
    assert "build_model_board" in source
    assert "require_market_lines=True" in source
    assert "Line integrity: every ranked leg below uses an active sportsbook line" in source
    assert "Sportsbook lines and odds are execution information only" in source
    assert "market_health=health_map" in source
    assert 'plays["Live Offer"] = False' in source
    assert "api_key = None" in source
    assert 'st.subheader("Today\'s five highest-probability model legs")' not in source


def test_projection_page_has_unpriced_straight_and_parlay_actions():
    path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert "render_add_bet_button" in source
    assert 'button("➕ Straight"' in source
    assert 'button("🎟️ Parlay"' in source
    assert 'tradable=side in {"OVER","UNDER"} and not no_line' in source
    assert "disabled=not tradable" in source
    assert "render_projection_parlay_builder" in source
    assert "make_parlay_record" in source
    assert "Projection Page Model Parlay" in source
    assert "append_bet(BET_LOG,record,st.secrets)" in source


def test_projection_bet_leans_require_real_lines_and_manual_editor_is_gone():
    source = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text(encoding="utf-8")
    assert "no_active_line_recommendation" in source
    assert 'side_text=f"{projection_text} PROJ"' in source
    assert "NO ACTIVE LINE" in source
    assert "the app will not manufacture a bet lean" in source
    assert "MANUAL LINE / ODDS" not in source
    assert "manual_market_recommendation" not in source
    assert "get_odds_events" not in source
    assert "get_event_props" not in source



def test_projection_strikeout_ladder_is_clickable_and_actionable():
    source = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text(encoding="utf-8")
    assert 'key=f"projection_k_ladder_{game.key}"' in source
    assert 'selection_mode="single-row"' in source
    assert '"➕ Add selected as straight"' in source
    assert '"🎟️ Add selected to parlay"' in source
    assert 'tracker_line=float(milestone)-0.5' in source
    assert "Fair Odds are model-only and are never saved as a sportsbook price" in source
    ladder_pos = source.index('key=f"projection_k_ladder_{game.key}"')
    builder_pos = source.rindex("render_projection_parlay_builder()")
    assert ladder_pos < builder_pos
    assert "kdf=ladder(proj,12)" in source
    assert "3+ through 12+" in source


def test_projection_parlay_builder_has_no_hard_leg_cap():
    source = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text(encoding="utf-8")
    assert "capped at five legs" not in source
    assert "if len(legs)>=5" not in source
    assert "very high variance" in source
    assert "does not multiply model probabilities" in source
    assert "({len(legs)}/5)" not in source


def test_tracker_page_has_ticket_progress_and_grades_parlays():
    path = Path(__file__).resolve().parents[1] / "pages" / "2_Bet_Tracker.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    assert "parse_parlay_legs" in source
    assert "grade_parlay" in source
    assert 'if bet_type == "Parlay":' in source
    assert "# BET_TRACKER_TICKET_CARDS_V1" in source
    assert "def _ticket_icon" in source
    assert "def _progress_value" in source
    assert "with st.expander(label" in source
    assert 'p1.metric("Current"' in source
    assert 'p2.metric("Target line"' in source
    assert "st.progress(_progress_value(actual, line))" in source
    assert "delete_bet" in source
    assert 'st.expander("🗑️ Delete a saved bet"' in source
    assert '"Confirm deletion of this saved ticket"' in source
    assert '"🗑️ Delete selected bet"' in source


def test_tracker_live_stats_prefer_boxscore_before_date_range_fallback():
    path = Path(__file__).resolve().parents[1] / "pages" / "2_Bet_Tracker.py"
    source = path.read_text(encoding="utf-8")
    start = source.index("def live_pitcher_prop(")
    end = source.index("@st.cache_data(ttl=120", start)
    block = source[start:end]
    live_pos = block.index("stat = _live_pitching_stats(found_game_pk, resolved_id)")
    fallback_pos = block.index("stat = _date_pitching_stats(resolved_id, game_date)")
    assert live_pos < fallback_pos

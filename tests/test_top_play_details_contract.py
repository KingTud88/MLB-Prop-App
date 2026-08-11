from pathlib import Path


def test_top_plays_has_reliable_detail_button_and_stake_explanation():
    path = Path(__file__).resolve().parents[1] / "pages" / "6_Top_Plays.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")

    assert 'st.button("🔎 View details"' in source
    assert 'st.session_state["top_play_detail_rank"] = rank' in source
    assert 'selected_rank = st.session_state.get("top_play_detail_rank")' in source
    assert 'render_projection_rationale(play, snapshot, history)' in source
    assert 'Straight-bet stake (units)' in source
    assert 'Parlay stake (units)' in source
    assert 'It does not place a sportsbook wager' in source

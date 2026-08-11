from engine.bet_tracker import (
    default_line_for_market,
    grade_bet,
    make_bet_record,
    normalize_market,
    profit_for,
    projection_for_market,
    result_cell_css,
)


def test_old_rows_default_to_strikeouts():
    assert normalize_market("") == "Strikeouts"
    assert normalize_market(None) == "Strikeouts"


def test_market_normalization_supports_all_three_props():
    assert normalize_market("pitcher_hits_allowed") == "Hits Allowed"
    assert normalize_market("Total Outs") == "Total Outs"
    assert normalize_market("pitcher_strikeouts") == "Strikeouts"


def test_projection_autofill_uses_matching_frozen_market_projection():
    snapshot = {
        "projection": 6.25,
        "outs_projection": 17.40,
        "hits_projection": 4.85,
    }
    assert projection_for_market(snapshot, "Strikeouts") == 6.25
    assert projection_for_market(snapshot, "Total Outs") == 17.40
    assert projection_for_market(snapshot, "Hits Allowed") == 4.85
    assert projection_for_market({}, "Strikeouts") is None


def test_default_entry_lines_follow_market_family():
    assert default_line_for_market("Strikeouts") == 5.5
    assert default_line_for_market("Total Outs") == 15.5
    assert default_line_for_market("Hits Allowed") == 5.5


def test_final_half_line_grading():
    assert grade_bet("over", 5.5, 6, True).result == "WIN"
    assert grade_bet("over", 5.5, 5, True).result == "LOSS"
    assert grade_bet("under", 5.5, 5, True).result == "WIN"
    assert grade_bet("under", 5.5, 6, True).result == "LOSS"


def test_integer_line_can_push():
    grade = grade_bet("over", 6.0, 6, True)
    assert grade.result == "PUSH"
    assert grade.push is True


def test_profit_math_american_odds():
    win = grade_bet("over", 5.5, 6, True)
    loss = grade_bet("over", 5.5, 5, True)
    assert round(profit_for(10, 150, win), 2) == 15.00
    assert round(profit_for(10, -200, win), 2) == 5.00
    assert profit_for(10, -110, loss) == -10.0


def test_shared_quick_add_record_preserves_bet_metadata():
    record = make_bet_record(
        player="Tanner Bibee",
        market="pitcher_strikeouts",
        game_date="2026-08-11",
        line=4.5,
        side="UNDER",
        american_odds=-115,
        stake=2.0,
        book="FanDuel",
        projection=4.12,
        model_probability=0.58,
        implied_probability=0.535,
        edge=0.045,
        confidence="High",
        game_pk=123,
        pitcher_id=456,
        entered_at_utc="2026-08-11T16:00:00+00:00",
    )
    assert record["market"] == "Strikeouts"
    assert record["side"] == "Under"
    assert record["american_odds"] == -115
    assert record["stake"] == 2.0
    assert record["projection"] == 4.12
    assert record["game_pk"] == 123
    assert record["pitcher_id"] == 456


def test_result_colors_are_green_for_win_and_red_for_loss():
    assert "#49efb0" in result_cell_css("WIN")
    assert "#ff4b4b" in result_cell_css("LOSS")

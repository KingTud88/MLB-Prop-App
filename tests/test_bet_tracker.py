from engine.bet_tracker import (
    combined_parlay_odds,
    default_line_for_market,
    grade_bet,
    grade_parlay,
    make_bet_record,
    make_parlay_record,
    normalize_market,
    parse_parlay_legs,
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
    assert record["bet_type"] == "Straight"
    assert record["market"] == "Strikeouts"
    assert record["side"] == "Under"
    assert record["american_odds"] == -115
    assert record["stake"] == 2.0
    assert record["projection"] == 4.12
    assert record["game_pk"] == 123
    assert record["pitcher_id"] == 456


def test_model_straight_can_be_saved_without_sportsbook_odds():
    record = make_bet_record(
        player="Model Pitcher", market="Strikeouts", game_date="2026-08-12",
        line=4.5, side="Over", american_odds=None, stake=1.0,
        projection=5.2, model_probability=0.61, source="Projection Strikeout Ladder",
    )
    assert record["bet_type"] == "Straight"
    assert record["american_odds"] == ""
    assert record["line"] == 4.5
    assert record["side"] == "Over"
    assert profit_for(1.0, None, grade_bet("Over", 4.5, 5, True)) is None


def test_parlay_combined_odds_and_ticket_record():
    estimated = combined_parlay_odds([-110, -110])
    assert 260 <= estimated <= 265
    legs = [
        {"player":"A","market":"Strikeouts","game_date":"2026-08-11","line":5.5,"side":"Over","american_odds":-110,"game_pk":1,"pitcher_id":11},
        {"player":"B","market":"Total Outs","game_date":"2026-08-11","line":17.5,"side":"Under","american_odds":-110,"game_pk":2,"pitcher_id":22},
    ]
    record = make_parlay_record(legs=legs, stake=1.0, book="FanDuel", american_odds=estimated, game_date="2026-08-11")
    assert record["bet_type"] == "Parlay"
    assert record["player"] == "2-leg parlay"
    parsed = parse_parlay_legs(record["parlay_legs"])
    assert len(parsed) == 2
    assert parsed[1]["market"] == "Total Outs"


def test_model_parlay_can_be_saved_without_sportsbook_or_odds():
    legs = [
        {"player":"A","market":"Strikeouts","game_date":"2026-08-11","line":5.5,"side":"Over","american_odds":None,"game_pk":1,"pitcher_id":11},
        {"player":"B","market":"Total Outs","game_date":"2026-08-11","line":17.5,"side":"Under","american_odds":None,"game_pk":2,"pitcher_id":22},
    ]
    record = make_parlay_record(legs=legs, stake=1.0, game_date="2026-08-11", source="Top Plays Model Parlay")
    assert record["book"] == ""
    assert record["american_odds"] == ""
    parsed = parse_parlay_legs(record["parlay_legs"])
    assert parsed[0]["american_odds"] == ""
    assert record["source"] == "Top Plays Model Parlay"


def test_parlay_grade_requires_every_leg_to_win():
    win = grade_bet("over", 5.5, 6, True)
    loss = grade_bet("under", 17.5, 18, True)
    pending = grade_bet("over", 4.5, None, False)
    assert grade_parlay([win, win]).result == "WIN"
    assert grade_parlay([win, loss]).result == "LOSS"
    assert grade_parlay([win, pending]).result == "PENDING"


def test_result_colors_are_green_for_win_and_red_for_loss():
    assert "#49efb0" in result_cell_css("WIN")
    assert "#ff4b4b" in result_cell_css("LOSS")


def test_model_parlay_supports_eighteen_unpriced_legs():
    legs = [
        {
            "player": f"Pitcher {idx}",
            "market": "Strikeouts",
            "game_date": "2026-08-12",
            "line": 4.5 + (idx % 4),
            "side": "Over",
            "american_odds": None,
            "game_pk": 1000 + idx,
            "pitcher_id": 2000 + idx,
        }
        for idx in range(18)
    ]
    record = make_parlay_record(legs=legs, stake=0.25, game_date="2026-08-12", source="Projection Page Model Parlay")
    assert record["bet_type"] == "Parlay"
    assert record["player"] == "18-leg parlay"
    parsed = parse_parlay_legs(record["parlay_legs"])
    assert len(parsed) == 18
    assert all(leg["american_odds"] == "" for leg in parsed)

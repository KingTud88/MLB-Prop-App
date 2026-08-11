from engine.bet_tracker import grade_bet, normalize_market, profit_for


def test_old_rows_default_to_strikeouts():
    assert normalize_market("") == "Strikeouts"
    assert normalize_market(None) == "Strikeouts"


def test_market_normalization_supports_all_three_props():
    assert normalize_market("pitcher_hits_allowed") == "Hits Allowed"
    assert normalize_market("Total Outs") == "Total Outs"
    assert normalize_market("pitcher_strikeouts") == "Strikeouts"


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

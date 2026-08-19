from engine.card_explainability import (
    active_market_explanation,
    market_decision_explanation,
    matchup_metric_explanation,
    pitcher_projection_explanation,
)
from pathlib import Path


def test_projection_page_uses_compact_card_info_controls():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "apply_card_info_theme()" in source
    assert "card_info_popover(" in source
    assert "matchup_metric_explanation(\"k_rate\"" in source
    assert "matchup_metric_explanation(\"hit_rate\"" in source
    assert "matchup_metric_explanation(\"pa\"" in source
    assert "matchup_metric_explanation(\"high\"" in source
    assert "matchup_metric_explanation(\"elevated\"" in source
    for old in (
        "ⓘ EXPLAIN ACTIVE LINES","ⓘ WHY THIS K PROJECTION?","ⓘ WHY THIS K DECISION?",
        "ⓘ WHY THIS OUTS PROJECTION?","ⓘ WHY THIS OUTS DECISION?","ⓘ WHY THIS HITS PROJECTION?",
        "ⓘ WHY THIS HITS DECISION?","ⓘ WHY THIS WEATHER STATUS?","ⓘ EXPLAIN BATTER MATCHUP",
        "ⓘ EXPLAIN BET ACTIONS","🔎 Why this projection?",
    ):
        assert old not in source


def test_active_market_detail_reports_real_pair_and_prices():
    offers = [
        {"market":"pitcher_strikeouts","name":"Over","point":5.5,"price":-120,"book":"ESPN BET","fetched_at_utc":"2026-08-19T21:00:00+00:00"},
        {"market":"pitcher_strikeouts","name":"Under","point":5.5,"price":-110,"book":"ESPN BET","fetched_at_utc":"2026-08-19T21:00:00+00:00"},
    ]
    exp = active_market_explanation("STRIKEOUTS",5.5,"SPORTSGAMEODDS · ESPN BET",offers,market_names=("pitcher_strikeouts",))
    joined = " | ".join(exp.current)
    assert "5.5" in joined
    assert "ESPN BET" in joined
    assert "-120" in joined
    assert "-110" in joined
    assert "complete real pregame Over/Under pair" in exp.decision


def test_projection_detail_contains_models_workload_and_matchup():
    context = {
        "history_games":25,"expected_pitches":92.5,"expected_bf":23.4,"expected_outs":16.2,
        "lineup_source":"CONFIRMED BATTING ORDER","lineup_batters":9,"split_pa":1800,"pitcher_hand":"R",
        "data_quality":79,"confidence":"High","draws":25000,"pitcher_k_pct":.26,"matchup_k_pct":.245,
        "park_factor":1.03,"sim_mean":5.4,"sim_sd":2.0,"math_mean":5.1,"math_sd":2.1,
        "ensemble_sd":2.05,"sim_weight":.55,
    }
    exp = pitcher_projection_explanation("Strikeouts",5.25,3,8,context)
    text = " | ".join(exp.inputs + exp.current)
    assert "25 starts" in text
    assert "23.4 BF" in text
    assert "CONFIRMED BATTING ORDER" in text
    assert "SIM path" in text
    assert "MATH path" in text
    assert "25,000" in text


def test_matchup_k_detail_describes_exact_confirmed_lineup_formula():
    exp = matchup_metric_explanation(
        "k_rate",{"confirmed":True,"batters":9,"pa":1600,"k_rate":.247,"hit_rate":.231,"high":2,"elevated":3},
        lineup_source="CONFIRMED BATTING ORDER",pitcher_hand="R",
    )
    assert "60-PA prior" in exp.method
    assert "22.4% league K baseline" in exp.method
    assert "24.7%" in " | ".join(exp.current)


def test_decision_detail_exposes_path_probabilities_calibration_and_price_edge():
    reco = {"side":"OVER","line":5.5,"projection_mean":6.2,"model":.61,"edge":.07,"reason":"aligned_positive_edge","active_line_source":"SPORTSGAMEODDS · ESPN BET"}
    exp = market_decision_explanation(reco,"Strikeouts",{"sim_probability":.64,"math_probability":.58,"sim_weight":.5,"math_weight":.5,"over_price":-115,"under_price":-105})
    text = " | ".join(exp.current)
    assert "SIM 64.0%" in text
    assert "MATH 58.0%" in text
    assert "OVER -115" in text
    assert "+7.0%" in text
    assert "positive-edge rule" in exp.decision

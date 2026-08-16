from pathlib import Path


def test_daily_runner_captures_raw_k_path_means_for_future_three_path_research():
    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    assert '"sim_mean_k": result.simulation_mean' in source
    assert '"math_mean_k": result.mathematical_mean' in source
    assert '"sim_sd_k": result.simulation_sd' in source
    assert '"math_sd_k": result.mathematical_sd' in source


def test_model_card_reads_shadow_reports_without_training_in_streamlit():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "ML SHADOW CHALLENGER · REPORT ONLY" in source
    assert "ml_shadow_summary.csv" in source
    assert "ml_shadow_live_candidates.csv" in source
    assert "GradientBoostingRegressor" not in source


def test_no_line_recommendation_card_uses_compact_projection_value_state():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'side_text=f"{projection_text} PROJ"' in source
    assert 'side_text="PROJECTION ONLY"' not in source
    assert 'line_text="NO ACTIVE LINE"' in source

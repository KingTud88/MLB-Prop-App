import pandas as pd

from training.workload_backtest import (
    BIAS_CANDIDATE_VERSION,
    attach_walk_forward_bias_candidate,
    replay_pitcher,
    segment_summary,
    summarize_backtest,
)


def _starts():
    rows = []
    dates = pd.to_datetime([
        "2025-08-01","2025-08-07","2025-08-13","2025-08-19","2025-08-25",
        "2026-03-30","2026-04-05","2026-04-11","2026-04-17","2026-04-23","2026-04-29",
    ])
    for i, date in enumerate(dates):
        rows.append({
            "pitcher_id": 1,
            "date": date,
            "season": int(date.year),
            "pitches": 80 + i * 2,
            "bf": 20 + i * 0.5,
            "outs": 15 + (i % 3),
        })
    return pd.DataFrame(rows)


def _bias_detail() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2026-04-01", periods=32, freq="D")
    for i, date in enumerate(dates):
        rows.append({
            "pitcher_id": i + 1,
            "game_date": date.date().isoformat(),
            "days_since_last_start": 5,
            "leash_label": "NORMAL",
            "actual_pitches": 91.0,
            "workload_pitches": 90.0,
            "rolling5_pitches": 89.0,
            "season_to_date_pitches": 89.5,
            "actual_bf": 24.5,
            "workload_bf": 24.0,
            "rolling5_bf": 23.5,
            "season_to_date_bf": 23.8,
            "actual_outs": 16.4,
            "workload_outs": 16.0,
            "rolling5_outs": 15.6,
            "season_to_date_outs": 15.8,
        })
    # Two games on the same date must receive the same correction based only on
    # earlier dates, regardless of either same-day final result.
    for pitcher_id, actual_pitches in ((1001, 91.0), (1002, 130.0)):
        rows.append({
            "pitcher_id": pitcher_id,
            "game_date": "2026-05-10",
            "days_since_last_start": 5,
            "leash_label": "NORMAL",
            "actual_pitches": actual_pitches,
            "workload_pitches": 90.0,
            "rolling5_pitches": 89.0,
            "season_to_date_pitches": 89.5,
            "actual_bf": 24.5,
            "workload_bf": 24.0,
            "rolling5_bf": 23.5,
            "season_to_date_bf": 23.8,
            "actual_outs": 16.4,
            "workload_outs": 16.0,
            "rolling5_outs": 15.6,
            "season_to_date_outs": 15.8,
        })
    return pd.DataFrame(rows)


def test_replay_pitcher_is_strictly_pregame_and_uses_prior_season_carry():
    detail = replay_pitcher(_starts(), 2026)
    assert not detail.empty
    first = detail.sort_values("game_date").iloc[0]
    assert first["game_date"] == "2026-03-30"
    assert first["prior_starts"] == 5
    assert first["current_season_prior_starts"] == 0
    # The target start itself must never leak into its own workload estimate.
    assert first["workload_pitches"] < first["actual_pitches"]
    assert pd.isna(first["season_to_date_pitches"])


def test_bias_candidate_uses_only_strictly_earlier_dates_and_corrects_underprediction():
    detail = attach_walk_forward_bias_candidate(_bias_detail())
    same_day = detail.loc[detail["game_date"].eq("2026-05-10")].sort_values("pitcher_id")
    assert len(same_day) == 2
    assert same_day["bias_candidate_version"].eq(BIAS_CANDIDATE_VERSION).all()
    assert same_day["bias_prior_n_pitches"].eq(32).all()
    assert same_day["bias_correction_pitches"].nunique() == 1
    assert same_day["bias_correction_pitches"].iloc[0] > 0.0
    assert (same_day["candidate_pitches"] > same_day["workload_pitches"]).all()
    # The 130-pitch same-day outlier cannot alter the other game's correction.
    assert same_day["candidate_pitches"].nunique() == 1


def test_summary_compares_workload_candidate_and_simple_baselines_without_market_data():
    detail = replay_pitcher(_starts(), 2026)
    summary = summarize_backtest(detail)
    assert set(summary["Metric"]) == {"PITCHES", "BF", "OUTS"}
    assert {
        "Workload_MAE", "Rolling5_MAE", "Relative_MAE_vs_Rolling5", "Status",
        "Candidate_MAE", "Relative_MAE_vs_Workload", "Candidate_Status",
    }.issubset(summary.columns)
    assert all(summary["Evaluated_Starts"] > 0)


def test_candidate_summary_detects_helpful_chronological_bias_correction():
    detail = attach_walk_forward_bias_candidate(_bias_detail())
    summary = summarize_backtest(detail)
    pitches = summary.loc[summary["Metric"].eq("PITCHES")].iloc[0]
    assert pitches["Candidate_Adjusted_Starts"] >= 2
    assert pitches["Candidate_Bias"] > pitches["Workload_Bias"]
    assert pitches["Candidate_MAE"] <= pitches["Workload_MAE"]


def test_segment_summary_requires_minimum_sample():
    detail = replay_pitcher(_starts(), 2026)
    assert segment_summary(detail, min_starts=99).empty
    visible = segment_summary(detail, min_starts=1)
    assert not visible.empty
    assert set(visible["Dimension"]).issubset({"rest_segment", "leash_label"})
    assert "Candidate MAE" in visible.columns

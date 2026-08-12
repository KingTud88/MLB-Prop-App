import numpy as np
import pandas as pd

from training.workload_backtest import attach_walk_forward_bias_candidate
from training.workload_leash_backtest import (
    LEASH_CANDIDATE_VERSION,
    LEASH_MIN_OBSERVATIONS,
    attach_walk_forward_leash_candidate,
    leash_segment_report,
    summarize_leash_candidate,
)


def _detail() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2026-04-01", periods=72, freq="D")
    for i, date in enumerate(dates):
        leash = "NORMAL" if i % 2 == 0 else "LONG"
        pitch_residual = 1.2 if leash == "NORMAL" else -0.8
        bf_residual = 0.5 if leash == "NORMAL" else -0.3
        outs_residual = 0.45 if leash == "NORMAL" else -0.25
        rows.append({
            "pitcher_id": i + 1,
            "game_date": date.date().isoformat(),
            "days_since_last_start": 5,
            "leash_label": leash,
            "actual_pitches": 90.0 + pitch_residual,
            "workload_pitches": 90.0,
            "rolling5_pitches": 89.5,
            "season_to_date_pitches": 89.7,
            "actual_bf": 24.0 + bf_residual,
            "workload_bf": 24.0,
            "rolling5_bf": 23.8,
            "season_to_date_bf": 23.9,
            "actual_outs": 16.0 + outs_residual,
            "workload_outs": 16.0,
            "rolling5_outs": 15.8,
            "season_to_date_outs": 15.9,
        })
    # Same-date games with the same leash label must see identical prior pools.
    for pitcher_id, actual in ((9001, 91.2), (9002, 140.0)):
        rows.append({
            "pitcher_id": pitcher_id,
            "game_date": "2026-07-01",
            "days_since_last_start": 5,
            "leash_label": "NORMAL",
            "actual_pitches": actual,
            "workload_pitches": 90.0,
            "rolling5_pitches": 89.5,
            "season_to_date_pitches": 89.7,
            "actual_bf": 24.5,
            "workload_bf": 24.0,
            "rolling5_bf": 23.8,
            "season_to_date_bf": 23.9,
            "actual_outs": 16.45,
            "workload_outs": 16.0,
            "rolling5_outs": 15.8,
            "season_to_date_outs": 15.9,
        })
    return pd.DataFrame(rows)


def _candidate() -> pd.DataFrame:
    global_candidate = attach_walk_forward_bias_candidate(_detail())
    return attach_walk_forward_leash_candidate(global_candidate)


def test_leash_candidate_is_same_day_leakage_safe():
    detail = _candidate()
    same_day = detail.loc[detail["game_date"].eq("2026-07-01")].sort_values("pitcher_id")
    assert len(same_day) == 2
    assert same_day["leash_candidate_version"].eq(LEASH_CANDIDATE_VERSION).all()
    assert same_day["leash_prior_n_pitches"].nunique() == 1
    assert same_day["leash_prior_n_pitches"].iloc[0] >= LEASH_MIN_OBSERVATIONS
    assert same_day["leash_correction_pitches"].nunique() == 1
    assert same_day["leash_candidate_pitches"].nunique() == 1


def test_leash_candidate_shrinks_segment_signal_toward_global():
    detail = _candidate()
    late = detail.loc[detail["game_date"].eq("2026-07-01")].iloc[0]
    global_correction = float(late["bias_correction_pitches"])
    leash_correction = float(late["leash_correction_pitches"])
    # NORMAL residuals are positive and larger than the all-leash global mean.
    assert leash_correction > global_correction
    # Hierarchical shrinkage prevents jumping all the way to the raw +1.2 residual.
    assert leash_correction < 1.2


def test_small_leash_samples_fall_back_to_global_candidate():
    detail = _candidate().sort_values("game_date")
    early = detail.loc[
        (detail["leash_label"].eq("NORMAL"))
        & (detail["leash_prior_n_pitches"] < LEASH_MIN_OBSERVATIONS)
    ]
    assert not early.empty
    assert np.allclose(
        early["leash_candidate_pitches"].astype(float),
        early["candidate_pitches"].astype(float),
        equal_nan=True,
    )


def test_summary_and_segments_compare_v21_to_global_v2():
    detail = _candidate()
    summary = summarize_leash_candidate(detail)
    assert set(summary["Metric"]) == {"PITCHES", "BF", "OUTS"}
    assert {
        "Global_v2_MAE",
        "Leash_v21_MAE",
        "Relative_MAE_vs_Global_v2",
        "Leash_Win_Share_vs_Global_v2",
        "Leash_Status",
    }.issubset(summary.columns)
    segments = leash_segment_report(detail, min_starts=1)
    assert not segments.empty
    assert set(segments["Leash"]) == {"NORMAL", "LONG"}

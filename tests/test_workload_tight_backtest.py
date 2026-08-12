import numpy as np
import pandas as pd

from training.workload_backtest import attach_walk_forward_bias_candidate
from training.workload_leash_backtest import attach_walk_forward_leash_candidate
from training.workload_tight_backtest import (
    TIGHT_CANDIDATE_VERSION,
    attach_tight_only_candidate,
    summarize_tight_candidate,
    tight_segment_report,
)


def _detail() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2026-04-01", periods=90, freq="D")
    for i, date in enumerate(dates):
        if i % 3 == 0:
            leash = "TIGHT"
            pitch_residual, bf_residual, outs_residual = -4.0, -0.8, -0.7
        elif i % 3 == 1:
            leash = "NORMAL"
            pitch_residual, bf_residual, outs_residual = 0.8, 0.2, 0.15
        else:
            leash = "LONG"
            pitch_residual, bf_residual, outs_residual = 2.0, 0.5, 0.4
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
    return pd.DataFrame(rows)


def _candidate() -> pd.DataFrame:
    global_candidate = attach_walk_forward_bias_candidate(_detail())
    leash_candidate = attach_walk_forward_leash_candidate(global_candidate)
    return attach_tight_only_candidate(leash_candidate)


def test_tight_only_candidate_changes_tight_rows_only():
    detail = _candidate()
    assert detail["tight_candidate_version"].eq(TIGHT_CANDIDATE_VERSION).all()
    tight = detail["leash_label"].eq("TIGHT")
    non_tight = ~tight
    assert np.allclose(
        detail.loc[non_tight, "tight_candidate_pitches"].astype(float),
        detail.loc[non_tight, "candidate_pitches"].astype(float),
        equal_nan=True,
    )
    changed_tight = tight & (
        detail["tight_candidate_pitches"].astype(float) - detail["candidate_pitches"].astype(float)
    ).abs().gt(1e-12)
    assert changed_tight.any()


def test_tight_only_summary_compares_against_global_v2():
    summary = summarize_tight_candidate(_candidate())
    assert set(summary["Metric"]) == {"PITCHES", "BF", "OUTS"}
    assert {
        "Global_v2_MAE",
        "Tight_v22_MAE",
        "Relative_MAE_vs_Global_v2",
        "Tight_Win_Share_vs_Global_v2",
        "Tight_Status",
    }.issubset(summary.columns)
    assert (summary["Tight_Adjusted_Starts"] > 0).all()


def test_tight_segment_report_keeps_non_tight_groups_unchanged():
    segments = tight_segment_report(_candidate(), min_starts=1)
    assert not segments.empty
    assert set(segments["Leash"]) == {"TIGHT", "NORMAL", "LONG"}
    non_tight = segments[segments["Leash"].isin(["NORMAL", "LONG"])]
    assert np.allclose(
        non_tight["Tight_v22_MAE"].astype(float),
        non_tight["Global_v2_MAE"].astype(float),
        equal_nan=True,
    )

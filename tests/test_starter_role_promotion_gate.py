from __future__ import annotations

import pandas as pd

from training.starter_role_promotion_gate import evaluate


def _good_summary() -> pd.DataFrame:
    rows = []
    for season in (2025, 2026):
        for role in ("RAMPING", "LOW_RECENT_EXPOSURE"):
            for metric in ("PITCHES", "BF", "OUTS"):
                rows.append({
                    "Season": season,
                    "Role": role,
                    "Metric": metric,
                    "Adjusted_Starts": 40,
                    "Relative_MAE": 0.02,
                    "Win_Share": 0.60,
                    "Baseline_Bias": -2.0,
                    "Candidate_Bias": -1.0,
                })
    return pd.DataFrame(rows)


def test_gate_passes_only_when_every_required_cell_passes() -> None:
    report, passed = evaluate(_good_summary())
    assert passed is True
    assert len(report) == 12
    assert report["Gate_Result"].eq("PASS").all()


def test_gate_fails_on_any_regression() -> None:
    frame = _good_summary()
    mask = (frame["Season"] == 2026) & (frame["Role"] == "RAMPING") & (frame["Metric"] == "OUTS")
    frame.loc[mask, "Relative_MAE"] = -0.01
    report, passed = evaluate(frame)
    assert passed is False
    failed = report.loc[(report["Season"] == 2026) & (report["Role"] == "RAMPING") & (report["Metric"] == "OUTS")].iloc[0]
    assert failed["Gate_Result"] == "FAIL"
    assert "mae" in failed["Reasons"]


def test_gate_rejects_bias_worsening_even_with_mae_gain() -> None:
    frame = _good_summary()
    frame.loc[0, "Candidate_Bias"] = -3.0
    _, passed = evaluate(frame)
    assert passed is False

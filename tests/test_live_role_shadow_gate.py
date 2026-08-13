from __future__ import annotations

import pandas as pd

from training.live_role_shadow_gate import evaluate


def _summary(starts: int = 30) -> pd.DataFrame:
    rows = []
    for role in ("RAMPING", "LOW_RECENT_EXPOSURE"):
        for metric in ("PITCHES", "BF", "OUTS"):
            rows.append({
                "Role": role,
                "Metric": metric,
                "Resolved_Starts": starts,
                "Relative_MAE": 0.02,
                "Baseline_Bias": -2.0,
                "Candidate_Bias": -1.0,
                "Candidate_Win_Share": 0.60,
            })
    return pd.DataFrame(rows)


def test_gate_stays_learning_before_live_sample_threshold() -> None:
    report, overall = evaluate(_summary(starts=29))
    assert overall == "LEARNING"
    assert report["Live_Gate_Status"].eq("LEARNING").all()


def test_gate_passes_only_when_every_live_cell_clears_guardrails() -> None:
    report, overall = evaluate(_summary(starts=30))
    assert overall == "PASS"
    assert report["Live_Gate_Status"].eq("PASS").all()


def test_gate_fails_after_minimum_sample_if_any_cell_regresses() -> None:
    frame = _summary(starts=30)
    mask = (frame["Role"] == "RAMPING") & (frame["Metric"] == "OUTS")
    frame.loc[mask, "Relative_MAE"] = -0.02
    report, overall = evaluate(frame)
    assert overall == "FAIL"
    failed = report.loc[(report["Role"] == "RAMPING") & (report["Metric"] == "OUTS")].iloc[0]
    assert failed["Live_Gate_Status"] == "FAIL"
    assert "mae" in failed["Reasons"]


def test_missing_cells_are_learning_not_pass() -> None:
    report, overall = evaluate(pd.DataFrame())
    assert overall == "LEARNING"
    assert len(report) == 6
    assert report["Resolved_Starts"].eq(0).all()

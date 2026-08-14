from __future__ import annotations

import pandas as pd

from training.calibration_shadow_gate import MILESTONES, evaluate


def _summary(*, oos: int, rel: float = 0.02, base_gap: float = 0.05, cand_gap: float = 0.03, win: float = 0.60) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Milestone": milestone,
            "OOS_Starts": oos,
            "Relative_Brier_Improvement": rel,
            "Baseline_Calibration_Gap": base_gap,
            "Candidate_Calibration_Gap": cand_gap,
            "Candidate_Win_Share": win,
        }
        for milestone in MILESTONES
    ])


def test_gate_stays_learning_without_30_oos_starts() -> None:
    report, overall = evaluate(_summary(oos=29))
    assert overall == "LEARNING"
    assert set(report["Promotion_Gate_Status"]) == {"LEARNING"}
    assert set(report["Reasons"]) == {"oos_sample"}


def test_gate_requires_brier_gap_and_win_share_guardrails() -> None:
    report, overall = evaluate(_summary(oos=30, rel=0.0, base_gap=0.02, cand_gap=0.03, win=0.49))
    assert overall == "FAIL"
    assert set(report["Promotion_Gate_Status"]) == {"FAIL"}
    assert all("brier" in reason and "calibration_gap" in reason and "win_share" in reason for reason in report["Reasons"])


def test_gate_passes_only_when_every_milestone_passes() -> None:
    report, overall = evaluate(_summary(oos=30))
    assert overall == "PASS"
    assert set(report["Promotion_Gate_Status"]) == {"PASS"}


def test_missing_shadow_evidence_never_passes() -> None:
    report, overall = evaluate(pd.DataFrame())
    assert overall == "LEARNING"
    assert len(report) == len(MILESTONES)
    assert set(report["Reasons"]) == {"missing_shadow_cell"}

from __future__ import annotations

import pandas as pd

from engine.role_workload_gate import build_role_workload_decision
from engine.workload_context import build_workload_context


def _starter_log() -> pd.DataFrame:
    # Rising recent exposure => RAMPING under the existing role classifier.
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-07-01", "2026-07-07", "2026-07-13", "2026-07-19", "2026-07-25", "2026-07-31"]),
        "games_started": [1, 1, 1, 1, 1, 1],
        "pitches": [58, 60, 61, 70, 78, 84],
        "bf": [16, 17, 17, 19, 21, 22],
        "outs": [10, 11, 11, 13, 15, 16],
    })


def _role_history() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=40, freq="3D")
    return pd.DataFrame({
        "game_date": dates,
        "starter_role_label": ["RAMPING"] * 40,
        "projected_pitches": [80.0] * 40,
        "actual_pitches": [85.0] * 40,
        "projected_bf": [20.0] * 40,
        "actual_bf": [21.2] * 40,
        "projected_outs": [14.0] * 40,
        "actual_outs": [15.0] * 40,
    })


def test_shadow_computes_candidate_without_changing_effective_workload() -> None:
    log = _starter_log()
    target = pd.Timestamp("2026-08-10")
    base = build_workload_context(log, target)
    decision = build_role_workload_decision(log, base, _role_history(), target, mode="shadow")
    assert decision.role == "RAMPING"
    assert decision.eligible is True
    assert decision.applied is False
    assert decision.effective == base
    assert decision.candidate.expected_pitches > base.expected_pitches


def test_active_mode_applies_only_promoted_candidate() -> None:
    log = _starter_log()
    target = pd.Timestamp("2026-08-10")
    base = build_workload_context(log, target)
    decision = build_role_workload_decision(log, base, _role_history(), target, mode="active")
    assert decision.applied is True
    assert decision.effective == decision.candidate
    assert decision.effective.expected_pitches > base.expected_pitches


def test_future_role_residuals_cannot_change_current_decision() -> None:
    log = _starter_log()
    target = pd.Timestamp("2026-08-10")
    base = build_workload_context(log, target)
    history = _role_history()
    first = build_role_workload_decision(log, base, history, target, mode="shadow")
    future = pd.DataFrame({
        "game_date": [pd.Timestamp("2026-09-01")],
        "starter_role_label": ["RAMPING"],
        "projected_pitches": [80.0], "actual_pitches": [10.0],
        "projected_bf": [20.0], "actual_bf": [3.0],
        "projected_outs": [14.0], "actual_outs": [1.0],
    })
    second = build_role_workload_decision(log, base, pd.concat([history, future], ignore_index=True), target, mode="shadow")
    assert first.correction_pitches == second.correction_pitches
    assert first.correction_bf == second.correction_bf
    assert first.correction_outs == second.correction_outs


def test_established_role_is_behaviorally_unchanged_even_active() -> None:
    log = pd.DataFrame({
        "date": pd.date_range("2026-06-01", periods=8, freq="6D"),
        "games_started": [1] * 8,
        "pitches": [91, 90, 92, 89, 91, 90, 92, 91],
        "bf": [23, 22, 23, 22, 23, 22, 23, 23],
        "outs": [17, 17, 18, 17, 18, 17, 18, 18],
    })
    target = pd.Timestamp("2026-08-10")
    base = build_workload_context(log, target)
    decision = build_role_workload_decision(log, base, _role_history(), target, mode="active")
    assert decision.role == "ESTABLISHED"
    assert decision.applied is False
    assert decision.effective == base

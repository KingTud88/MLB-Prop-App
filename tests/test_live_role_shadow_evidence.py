from __future__ import annotations

import pandas as pd

from training.live_role_shadow_evidence import build_evidence, eligible_shadow_rows


def _frame() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "game_pk": 1,
            "game_date": "2026-08-01",
            "pitcher_id": 11,
            "player": "A",
            "role_workload_version": "starter-role-workload-v1",
            "role_workload_mode": "shadow",
            "starter_role_label": "RAMPING",
            "resolved_at_utc": "2026-08-02T03:00:00Z",
            "expected_pitches": 80.0,
            "role_candidate_expected_pitches": 85.0,
            "actual_pitches": 86.0,
            "expected_bf": 20.0,
            "role_candidate_expected_bf": 21.5,
            "actual_batters_faced": 22.0,
            "expected_outs": 13.0,
            "role_candidate_expected_outs": 14.5,
            "actual_outs": 15.0,
        },
        {
            "game_pk": 2,
            "game_date": "2026-08-02",
            "pitcher_id": 12,
            "player": "B",
            "role_workload_version": "starter-role-workload-v1",
            "role_workload_mode": "shadow",
            "starter_role_label": "LOW_RECENT_EXPOSURE",
            "resolved_at_utc": "2026-08-03T03:00:00Z",
            "expected_pitches": 72.0,
            "role_candidate_expected_pitches": 77.0,
            "actual_pitches": 78.0,
            "expected_bf": 18.0,
            "role_candidate_expected_bf": 19.5,
            "actual_batters_faced": 20.0,
            "expected_outs": 11.0,
            "role_candidate_expected_outs": 12.5,
            "actual_outs": 13.0,
        },
        {
            "game_pk": 3,
            "role_workload_version": "starter-role-workload-v1",
            "role_workload_mode": "shadow",
            "starter_role_label": "RAMPING",
            "resolved_at_utc": "",
        },
        {
            "game_pk": 4,
            "role_workload_version": "old-version",
            "role_workload_mode": "shadow",
            "starter_role_label": "RAMPING",
            "resolved_at_utc": "2026-08-04T03:00:00Z",
        },
        {
            "game_pk": 5,
            "role_workload_version": "starter-role-workload-v1",
            "role_workload_mode": "shadow",
            "starter_role_label": "ESTABLISHED",
            "resolved_at_utc": "2026-08-04T03:00:00Z",
        },
    ])


def test_only_resolved_current_shadow_eligible_roles_are_counted() -> None:
    eligible = eligible_shadow_rows(_frame())
    assert eligible["game_pk"].tolist() == [1, 2]


def test_evidence_compares_baseline_and_candidate_for_all_workload_metrics() -> None:
    detail, summary = build_evidence(_frame())
    assert len(detail) == 6
    assert set(detail["Metric"]) == {"PITCHES", "BF", "OUTS"}
    assert detail["Candidate_Win"].all()
    assert len(summary) == 6
    assert (summary["Relative_MAE"] > 0).all()


def test_legacy_and_unresolved_rows_cannot_affect_score() -> None:
    base_detail, base_summary = build_evidence(_frame())
    noisy = pd.concat([
        _frame(),
        pd.DataFrame([{
            "game_pk": 99,
            "role_workload_version": "starter-role-workload-v1",
            "role_workload_mode": "shadow",
            "starter_role_label": "RAMPING",
            "resolved_at_utc": "",
            "expected_pitches": 1.0,
            "role_candidate_expected_pitches": 999.0,
            "actual_pitches": 50.0,
        }]),
    ], ignore_index=True)
    detail, summary = build_evidence(noisy)
    pd.testing.assert_frame_equal(detail.reset_index(drop=True), base_detail.reset_index(drop=True))
    pd.testing.assert_frame_equal(summary.reset_index(drop=True), base_summary.reset_index(drop=True))

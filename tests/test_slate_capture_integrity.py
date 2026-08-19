from __future__ import annotations

import pandas as pd

from training.slate_capture_integrity import AUDIT_VERSION, _failures, build_audit


DAY = "2026-08-19"
STARTER = {
    "game_pk": 900001,
    "pitcher_id": 700001,
    "player": "Test Starter",
    "team": "AAA",
    "opponent": "BBB",
    "game_time": "2026-08-19T23:10:00Z",
    "status": "Scheduled",
}


def _frame(*, audit_eligible: object | None = None) -> pd.DataFrame:
    row: dict[str, object] = {
        "game_date": DAY,
        "game_pk": STARTER["game_pk"],
        "pitcher_id": STARTER["pitcher_id"],
    }
    if audit_eligible is not None:
        row["audit_eligible"] = audit_eligible
    return pd.DataFrame([row])


def test_projected_starter_requires_all_frozen_research_layers_but_not_score_eligibility() -> None:
    report = build_audit(
        DAY,
        announced=[STARTER],
        projections=_frame(),
        observations=pd.DataFrame(),
        handedness=_frame(),
        pitch_arsenal=_frame(),
        batter_whiff=_frame(),
        pitch_mix_scores=_frame(audit_eligible=False),
    )

    row = report.iloc[0]
    assert row["capture_status"] == "PROJECTED"
    assert row["research_capture_status"] == "COMPLETE"
    assert row["handedness_capture"] == "CAPTURED"
    assert row["pitch_arsenal_capture"] == "CAPTURED"
    assert row["batter_whiff_capture"] == "CAPTURED"
    assert row["pitch_mix_score_capture"] == "CAPTURED"
    assert row["pitch_mix_score_eligibility"] == "INELIGIBLE"
    assert row["missing_research_layers"] == ""
    assert row["audit_version"] == AUDIT_VERSION == "slate-capture-integrity-v2-research-context"
    assert _failures(report).empty


def test_missing_research_layers_fail_even_when_base_projection_exists() -> None:
    report = build_audit(
        DAY,
        announced=[STARTER],
        projections=_frame(),
        observations=pd.DataFrame(),
        handedness=_frame(),
        pitch_arsenal=_frame(),
        batter_whiff=pd.DataFrame(),
        pitch_mix_scores=pd.DataFrame(),
    )

    row = report.iloc[0]
    assert row["capture_status"] == "PROJECTED"
    assert row["research_capture_status"] == "PARTIAL"
    assert row["batter_whiff_capture"] == "MISSING"
    assert row["pitch_mix_score_capture"] == "MISSING"
    assert row["pitch_mix_score_eligibility"] == "MISSING"
    assert row["missing_research_layers"] == "batter_whiff|pitch_mix_score"
    assert len(_failures(report)) == 1


def test_history_only_starter_preserves_existing_research_context_exemption() -> None:
    report = build_audit(
        DAY,
        announced=[STARTER],
        projections=pd.DataFrame(),
        observations=_frame(),
        handedness=pd.DataFrame(),
        pitch_arsenal=pd.DataFrame(),
        batter_whiff=pd.DataFrame(),
        pitch_mix_scores=pd.DataFrame(),
    )

    row = report.iloc[0]
    assert row["capture_status"] == "HISTORY_ONLY"
    assert row["research_capture_status"] == "NOT_REQUIRED"
    assert row["handedness_capture"] == "NOT_REQUIRED"
    assert row["pitch_mix_score_eligibility"] == "NOT_REQUIRED"
    assert _failures(report).empty


def test_uncaptured_announced_starter_still_fails_base_slate_integrity() -> None:
    report = build_audit(
        DAY,
        announced=[STARTER],
        projections=pd.DataFrame(),
        observations=pd.DataFrame(),
        handedness=pd.DataFrame(),
        pitch_arsenal=pd.DataFrame(),
        batter_whiff=pd.DataFrame(),
        pitch_mix_scores=pd.DataFrame(),
    )

    row = report.iloc[0]
    assert row["capture_status"] == "MISSING"
    assert row["research_capture_status"] == "NOT_REQUIRED"
    assert len(_failures(report)) == 1


def test_any_eligible_frozen_score_context_marks_slate_score_eligible_without_rewriting_lineage() -> None:
    scores = pd.concat(
        [
            _frame(audit_eligible=False),
            _frame(audit_eligible=True),
        ],
        ignore_index=True,
    )
    report = build_audit(
        DAY,
        announced=[STARTER],
        projections=_frame(),
        observations=pd.DataFrame(),
        handedness=_frame(),
        pitch_arsenal=_frame(),
        batter_whiff=_frame(),
        pitch_mix_scores=scores,
    )

    row = report.iloc[0]
    assert row["research_capture_status"] == "COMPLETE"
    assert row["pitch_mix_score_eligibility"] == "ELIGIBLE"

from __future__ import annotations

import pandas as pd

from training.research_evidence_transition_digest import (
    DIGEST_COLUMNS,
    NO_AUTO_PROMOTION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_digest_summary,
    build_transition_digest,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Observed_At_UTC": "2026-08-18T13:00:00+00:00",
        "Event_Type": "EVIDENCE_CHANGE",
        "Lane": "Confirmed Lineup",
        "Category": "LINEUP",
        "Previous_Status": "LEARNING",
        "Status": "LEARNING",
        "Evidence_Direction": "relative_mae=+0.50%",
        "Current_Starts": 122,
        "Required_Starts": 30,
        "Starts_Remaining": 0,
        "Current_Days": 6,
        "Required_Days": 10,
        "Days_Remaining": 4,
        "Breadth_Label": "OPPONENTS",
        "Current_Breadth": 30,
        "Required_Breadth": 8,
        "Breadth_Remaining": 0,
        "Secondary_Progress": "authentic_pairs=150",
        "Ready_For_Manual_Review": False,
        "Recommended_Action": "KEEP_LEARNING",
        "Source_Reason": "Need 10 observed days.",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "No_Auto_Promotion": True,
        "Source_Version": "lineup-v1",
        "Change_Summary": "Current_Starts:120->122; Current_Days:5->6; Secondary_Progress:authentic_pairs=148->authentic_pairs=150",
    }
    row.update(overrides)
    return row


def test_baseline_rows_never_surface_as_transitions() -> None:
    history = pd.DataFrame([_row(Event_Type="BASELINE_CAPTURE", Previous_Status="")])
    digest = build_transition_digest(history, "2026-08-18T13:00:00+00:00")
    summary = build_digest_summary(digest, "2026-08-18T13:00:00+00:00").iloc[0]
    assert digest.empty
    assert summary["Digest_Status"] == "NO_CHANGES"
    assert summary["Changed_Lanes"] == 0


def test_exact_refresh_only_prevents_replaying_old_transitions() -> None:
    history = pd.DataFrame([_row(Observed_At_UTC="2026-08-18T12:00:00+00:00")])
    digest = build_transition_digest(history, "2026-08-18T13:00:00+00:00")
    summary = build_digest_summary(digest, "2026-08-18T13:00:00+00:00").iloc[0]
    assert digest.empty
    assert summary["Digest_Status"] == "NO_CHANGES"


def test_digest_classifies_status_progress_readiness_and_action_changes() -> None:
    refresh = "2026-08-18T13:00:00+00:00"
    history = pd.DataFrame([
        _row(),
        _row(
            Lane="Umpire Context",
            Category="CONTEXT",
            Previous_Status="LEARNING",
            Status="READY_FOR_MANUAL_RESEARCH_REVIEW",
            Ready_For_Manual_Review=True,
            Recommended_Action="MANUAL_RESEARCH_REVIEW",
            Change_Summary=(
                "Status:LEARNING->READY_FOR_MANUAL_RESEARCH_REVIEW; "
                "Ready_For_Manual_Review:False->True; "
                "Recommended_Action:KEEP_LEARNING->MANUAL_RESEARCH_REVIEW"
            ),
        ),
    ])
    digest = build_transition_digest(history, refresh)
    assert len(digest) == 2
    lineup = digest.loc[digest["Lane"].eq("Confirmed Lineup")].iloc[0]
    umpire = digest.loc[digest["Lane"].eq("Umpire Context")].iloc[0]
    assert lineup["Progress_Changed"] in (True, 1)
    assert lineup["Status_Changed"] in (False, 0)
    assert umpire["Status_Changed"] in (True, 1)
    assert umpire["Readiness_Changed"] in (True, 1)
    assert umpire["Action_Changed"] in (True, 1)
    summary = build_digest_summary(digest, refresh).iloc[0]
    assert summary["Digest_Status"] == "CHANGES_DETECTED"
    assert summary["Changed_Lanes"] == 2
    assert summary["Status_Change_Lanes"] == 1
    assert summary["Progress_Change_Lanes"] == 1
    assert summary["Readiness_Change_Lanes"] == 1
    assert summary["Review_Ready_Changed_Lanes"] == 1


def test_control_violation_is_loud_without_granting_authority() -> None:
    refresh = "2026-08-18T13:00:00+00:00"
    history = pd.DataFrame([_row(Production_Authority="K_MODEL")])
    digest = build_transition_digest(history, refresh)
    assert digest.iloc[0]["Control_Violation"] in (True, 1)
    summary = build_digest_summary(digest, refresh).iloc[0]
    assert summary["Digest_Status"] == "CONTROL_VIOLATION"
    assert summary["Control_Violation_Lanes"] == 1
    assert summary["Production_Authority"] == "NONE"
    assert summary["No_Auto_Promotion"] in (True, 1)


def test_source_version_change_is_visible_but_not_a_score() -> None:
    refresh = "2026-08-18T13:00:00+00:00"
    history = pd.DataFrame([_row(Change_Summary="Source_Version:v1->v2", Source_Version="v2")])
    digest = build_transition_digest(history, refresh)
    assert digest.iloc[0]["Source_Version_Changed"] in (True, 1)
    assert "Score" not in DIGEST_COLUMNS
    assert "Priority" not in DIGEST_COLUMNS


def test_contract_is_report_only_and_no_auto_promotion() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_AUTO_PROMOTION is True
    assert VERSION == "research-evidence-transition-digest-v1-report-only"

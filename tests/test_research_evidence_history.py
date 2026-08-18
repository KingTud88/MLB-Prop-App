from __future__ import annotations

import pandas as pd

from training.research_evidence_history import (
    NO_AUTO_PROMOTION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    append_history,
    build_history_summary,
    fingerprint_row,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Lane": "Confirmed Lineup",
        "Category": "LINEUP",
        "Status": "LEARNING",
        "Evidence_Direction": "relative_mae=+0.49%; win_share=51.7%",
        "Current_Starts": 120,
        "Required_Starts": 30,
        "Starts_Remaining": 0,
        "Current_Days": 5,
        "Required_Days": 10,
        "Days_Remaining": 5,
        "Breadth_Label": "OPPONENTS",
        "Current_Breadth": 30,
        "Required_Breadth": 8,
        "Breadth_Remaining": 0,
        "Secondary_Progress": "authentic_pairs=148",
        "Ready_For_Manual_Review": False,
        "Recommended_Action": "KEEP_LEARNING",
        "Source_Reason": "Need 10 observed days.",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "No_Auto_Promotion": True,
        "Source_Version": "lineup-v1",
        "Command_Center_Version": "command-center-v1",
    }
    row.update(overrides)
    return row


def test_initial_snapshot_records_one_baseline_per_lane() -> None:
    center = pd.DataFrame([_row(), _row(Lane="Umpire Context", Category="CONTEXT")])
    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")
    assert len(history) == 2
    assert set(history["Event_Type"]) == {"BASELINE_CAPTURE"}
    assert set(history["Change_Summary"]) == {"BASELINE_CAPTURE"}
    assert set(history["Previous_Status"].fillna("")) == {""}
    assert history["Fingerprint"].str.len().eq(64).all()


def test_identical_snapshot_is_not_appended_again() -> None:
    center = pd.DataFrame([_row()])
    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")
    repeated = append_history(center, history, observed_at_utc="2026-08-18T13:00:00+00:00")
    assert len(repeated) == 1
    assert repeated.iloc[0]["Observed_At_UTC"] == "2026-08-18T12:00:00+00:00"


def test_progress_change_appends_evidence_change_and_explains_delta() -> None:
    center = pd.DataFrame([_row()])
    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")
    changed = pd.DataFrame([_row(Current_Days=6, Days_Remaining=4, Source_Reason="Need 4 more observed days.")])
    updated = append_history(changed, history, observed_at_utc="2026-08-19T12:00:00+00:00")
    assert len(updated) == 2
    event = updated.iloc[-1]
    assert event["Event_Type"] == "EVIDENCE_CHANGE"
    assert event["Previous_Status"] == "LEARNING"
    assert "Current_Days:5->6" in event["Change_Summary"]
    assert "Source_Reason:CHANGED" in event["Change_Summary"]


def test_status_transition_is_preserved_without_auto_promotion() -> None:
    center = pd.DataFrame([_row()])
    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")
    changed = pd.DataFrame([_row(Status="PASS", Ready_For_Manual_Review=True, Recommended_Action="MANUAL_REVIEW")])
    updated = append_history(changed, history, observed_at_utc="2026-08-28T12:00:00+00:00")
    event = updated.iloc[-1]
    assert event["Previous_Status"] == "LEARNING"
    assert event["Status"] == "PASS"
    assert bool(event["Ready_For_Manual_Review"]) is True
    assert event["Production_Authority"] == "NONE"
    assert bool(event["No_Auto_Promotion"]) is True
    assert "Status:LEARNING->PASS" in event["Change_Summary"]


def test_command_center_implementation_version_does_not_create_history_noise() -> None:
    first = pd.Series(_row(Command_Center_Version="v1"))
    second = pd.Series(_row(Command_Center_Version="v2"))
    assert fingerprint_row(first) == fingerprint_row(second)


def test_source_version_change_is_a_real_history_event() -> None:
    center = pd.DataFrame([_row()])
    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")
    changed = pd.DataFrame([_row(Source_Version="lineup-v2")])
    updated = append_history(changed, history, observed_at_utc="2026-08-19T12:00:00+00:00")
    assert len(updated) == 2
    assert "Source_Version:lineup-v1->lineup-v2" in updated.iloc[-1]["Change_Summary"]


def test_history_summary_reports_latest_state_and_transition_count() -> None:
    center = pd.DataFrame([_row()])
    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")
    changed = pd.DataFrame([_row(Current_Days=6, Days_Remaining=4)])
    history = append_history(changed, history, observed_at_utc="2026-08-19T12:00:00+00:00")
    summary = build_history_summary(history).iloc[0]
    assert summary["Recorded_Events"] == 2
    assert summary["Transition_Count"] == 1
    assert summary["First_Observed_At_UTC"] == "2026-08-18T12:00:00+00:00"
    assert summary["Last_Changed_At_UTC"] == "2026-08-19T12:00:00+00:00"
    assert summary["Current_Status"] == "LEARNING"
    assert summary["Current_Days"] == 6


def test_empty_history_summary_is_schema_safe() -> None:
    summary = build_history_summary(pd.DataFrame())
    assert summary.empty
    assert "Transition_Count" in summary.columns


def test_history_contract_remains_report_only() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_AUTO_PROMOTION is True
    assert VERSION == "research-evidence-history-v1-report-only"

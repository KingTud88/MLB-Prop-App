from __future__ import annotations

import pandas as pd

from training.catcher_context_validation import MIN_PRIOR_STARTS
from training.catcher_prior_maturity import (
    MATURITY_VERSION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    build_maturity,
    summarize_maturity,
)


def _row(
    *,
    catcher_id: int | None,
    name: str = "Test Catcher",
    date: str = "2026-08-18",
    lineage: str = "PRE_GAME_CAPTURE",
    actual: float | None = 5.0,
    prior: int = 0,
    auditable: bool = False,
) -> dict[str, object]:
    return {
        "Game_Date": date,
        "Game_Time_UTC": f"{date}T23:00:00Z",
        "Catcher_ID": catcher_id,
        "Catcher_Name": name,
        "Lineage": lineage,
        "Actual_Strikeouts": actual,
        "Prior_Catcher_Starts": prior,
        "Candidate_Auditable": auditable,
    }


def test_maturity_uses_locked_validation_threshold() -> None:
    assert MIN_PRIOR_STARTS == 5


def test_five_resolved_without_past_auditable_target_is_next_appearance_ready() -> None:
    frame = pd.DataFrame([
        _row(catcher_id=10, date=f"2026-08-{day:02d}", prior=max(day - 13, 0))
        for day in range(13, 18)
    ])
    result = build_maturity(frame)
    row = result.iloc[0]
    assert row["Resolved_Context_Starts"] == 5
    assert row["Auditable_Targets_To_Date"] == 0
    assert bool(row["Next_Appearance_Prior_Ready"]) is True
    assert row["Maturity_Status"] == "NEXT_APPEARANCE_READY"
    assert row["Starts_To_Min_Prior"] == 0
    assert "no past target becomes auditable retroactively" in row["Reason"]


def test_three_and_four_resolved_are_near_ready() -> None:
    three = build_maturity(pd.DataFrame([_row(catcher_id=11, date=f"2026-08-{d:02d}") for d in (14, 15, 16)]))
    four = build_maturity(pd.DataFrame([_row(catcher_id=12, date=f"2026-08-{d:02d}") for d in (13, 14, 15, 16)]))
    assert three.iloc[0]["Maturity_Status"] == "NEAR_READY_3_4"
    assert three.iloc[0]["Starts_To_Min_Prior"] == 2
    assert four.iloc[0]["Maturity_Status"] == "NEAR_READY_3_4"
    assert four.iloc[0]["Starts_To_Min_Prior"] == 1


def test_existing_auditable_target_takes_authoritative_status() -> None:
    frame = pd.DataFrame([
        _row(catcher_id=13, date="2026-08-12", prior=0),
        _row(catcher_id=13, date="2026-08-13", prior=1),
        _row(catcher_id=13, date="2026-08-14", prior=2),
        _row(catcher_id=13, date="2026-08-15", prior=3),
        _row(catcher_id=13, date="2026-08-16", prior=4),
        _row(catcher_id=13, date="2026-08-17", prior=5, auditable=True),
    ])
    row = build_maturity(frame).iloc[0]
    assert row["Maturity_Status"] == "AUDITABLE_EXISTS"
    assert row["Auditable_Targets_To_Date"] == 1
    assert row["First_Auditable_Target_Date"] == "2026-08-17"
    assert row["Max_Leakage_Safe_Prior_Starts_Seen"] == 5


def test_unresolved_and_missing_catcher_id_do_not_enter_resolved_pool() -> None:
    frame = pd.DataFrame([
        _row(catcher_id=14, date="2026-08-15", actual=4.0),
        _row(catcher_id=14, date="2026-08-16", actual=None),
        _row(catcher_id=None, date="2026-08-17", actual=7.0),
    ])
    result = build_maturity(frame)
    assert len(result) == 1
    assert result.iloc[0]["Resolved_Context_Starts"] == 1
    assert result.iloc[0]["Maturity_Status"] == "BUILDING_0_2"


def test_authentic_and_backfilled_resolved_counts_are_separate() -> None:
    frame = pd.DataFrame([
        _row(catcher_id=15, date="2026-08-14", lineage="POST_START_BACKFILL"),
        _row(catcher_id=15, date="2026-08-15", lineage="POST_START_BACKFILL"),
        _row(catcher_id=15, date="2026-08-16", lineage="PRE_GAME_CAPTURE"),
        _row(catcher_id=15, date="2026-08-17", lineage="PRE_GAME_CAPTURE"),
    ])
    row = build_maturity(frame).iloc[0]
    assert row["Resolved_Context_Starts"] == 4
    assert row["Authentic_Pregame_Resolved_Starts"] == 2
    assert row["Post_Start_Backfill_Resolved_Starts"] == 2


def test_summary_reports_maturity_buckets_without_activation() -> None:
    frame = pd.DataFrame(
        [
            *[_row(catcher_id=20, name="Ready", date=f"2026-08-{d:02d}") for d in (12, 13, 14, 15, 16)],
            *[_row(catcher_id=21, name="Near", date=f"2026-08-{d:02d}") for d in (14, 15, 16, 17)],
            _row(catcher_id=22, name="Building", date="2026-08-17"),
        ]
    )
    maturity = build_maturity(frame)
    summary = summarize_maturity(maturity).iloc[0]
    assert summary["Known_Resolved_Catchers"] == 3
    assert summary["Resolved_Context_Starts"] == 10
    assert summary["Next_Appearance_Ready_No_Auditable_Yet"] == 1
    assert summary["Near_Ready_3_4"] == 1
    assert summary["Building_0_2"] == 1
    assert summary["Current_Auditable_Starts"] == 0
    assert bool(summary["Report_Only"]) is True
    assert summary["Production_Authority"] == "NONE"


def test_report_only_contract_is_frozen() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert MATURITY_VERSION == "catcher-prior-maturity-v1-report-only"

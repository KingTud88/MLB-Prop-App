from __future__ import annotations

from pathlib import Path

import pandas as pd

import training.research_pipeline_freshness_audit as freshness
from training.research_evidence_history import append_history
from training.research_evidence_transition_digest import (
    DIGEST_COLUMNS,
    build_digest_summary,
    build_transition_digest,
)
from training.research_manual_review_packet import (
    PACKET_COLUMNS,
    build_manual_review_packet,
    build_packet_summary,
)
from training.research_manual_review_queue import (
    QUEUE_COLUMNS,
    append_review_queue,
    build_queue_summary,
)


def _center(secondary: str = "sample=1") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Lane": "Synthetic Lane",
                "Category": "TEST",
                "Source_Path": "data/synthetic.csv",
                "Status": "LEARNING",
                "Evidence_Direction": "INCONCLUSIVE",
                "Current_Starts": 1,
                "Required_Starts": 10,
                "Starts_Remaining": 9,
                "Current_Days": 1,
                "Required_Days": 5,
                "Days_Remaining": 4,
                "Breadth_Label": "ITEMS",
                "Current_Breadth": 1,
                "Required_Breadth": 5,
                "Breadth_Remaining": 4,
                "Secondary_Progress": secondary,
                "Ready_For_Manual_Review": False,
                "Recommended_Action": "KEEP_LEARNING",
                "Source_Reason": "synthetic reason",
                "Report_Only": True,
                "Production_Authority": "NONE",
                "No_Auto_Promotion": True,
                "Source_Version": "synthetic-v1",
                "Command_Center_Version": "research-evidence-command-center-v1-report-only",
            }
        ]
    )


def _write_pipeline(root: Path, center: pd.DataFrame, history: pd.DataFrame, refresh: str) -> None:
    center.to_csv(root / "research_evidence_command_center.csv", index=False)
    history.to_csv(root / "research_evidence_history.csv", index=False)

    digest = build_transition_digest(history, refresh)
    digest.to_csv(root / "research_evidence_transition_digest.csv", index=False)
    build_digest_summary(digest, refresh).to_csv(root / "research_evidence_transition_digest_summary.csv", index=False)

    packet = build_manual_review_packet(digest, history, center, refresh)
    packet.to_csv(root / "research_manual_review_packet.csv", index=False)
    build_packet_summary(packet, digest, refresh).to_csv(root / "research_manual_review_packet_summary.csv", index=False)

    queue = append_review_queue(packet, pd.DataFrame(columns=QUEUE_COLUMNS), queued_at_utc=refresh)
    queue.to_csv(root / "research_manual_review_queue.csv", index=False)
    build_queue_summary(queue, refresh).to_csv(root / "research_manual_review_queue_summary.csv", index=False)


def test_exact_recomputation_marks_full_pipeline_current(tmp_path: Path, monkeypatch) -> None:
    center = _center()
    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")
    refresh = "2026-08-18T13:00:00+00:00"
    _write_pipeline(tmp_path, center, history, refresh)
    monkeypatch.setattr(freshness, "build_command_center", lambda _root: center.copy())

    audit = freshness.build_pipeline_freshness_audit(tmp_path)
    summary = freshness.build_freshness_summary(audit).iloc[0]

    assert audit["Freshness_Status"].tolist() == [freshness.CURRENT] * 5
    assert summary["Overall_Status"] == "HEALTHY"
    assert summary["Current_Stages"] == 5


def test_command_center_detects_current_source_mismatch_without_time_thresholds(tmp_path: Path, monkeypatch) -> None:
    expected = _center("sample=2")
    saved = _center("sample=1")
    history = append_history(expected, observed_at_utc="2026-08-18T12:00:00+00:00")
    refresh = "2026-08-18T13:00:00+00:00"
    _write_pipeline(tmp_path, saved, history, refresh)
    monkeypatch.setattr(freshness, "build_command_center", lambda _root: expected.copy())

    audit = freshness.build_pipeline_freshness_audit(tmp_path)
    command = audit.loc[audit["Stage"].eq("COMMAND_CENTER")].iloc[0]
    summary = freshness.build_freshness_summary(audit).iloc[0]

    assert command["Freshness_Status"] == freshness.SOURCE_NEWER
    assert command["Mismatch_Items"] == 1
    assert "Synthetic Lane" in command["Detail"]
    assert summary["Overall_Status"] == "STALE"


def test_history_mismatch_propagates_upstream_stale_to_digest_packet_and_queue(tmp_path: Path, monkeypatch) -> None:
    current = _center("sample=2")
    old = _center("sample=1")
    history = append_history(old, observed_at_utc="2026-08-18T12:00:00+00:00")
    refresh = "2026-08-18T13:00:00+00:00"
    _write_pipeline(tmp_path, current, history, refresh)
    monkeypatch.setattr(freshness, "build_command_center", lambda _root: current.copy())

    audit = freshness.build_pipeline_freshness_audit(tmp_path).set_index("Stage")

    assert audit.loc["COMMAND_CENTER", "Freshness_Status"] == freshness.CURRENT
    assert audit.loc["HISTORY", "Freshness_Status"] == freshness.SOURCE_NEWER
    assert audit.loc["TRANSITION_DIGEST", "Freshness_Status"] == freshness.UPSTREAM_STALE
    assert audit.loc["MANUAL_REVIEW_PACKET", "Freshness_Status"] == freshness.UPSTREAM_STALE
    assert audit.loc["MANUAL_REVIEW_QUEUE", "Freshness_Status"] == freshness.UPSTREAM_STALE


def test_digest_detects_newer_history_transition_than_its_exact_refresh(tmp_path: Path, monkeypatch) -> None:
    old = _center("sample=1")
    current = _center("sample=2")
    history = append_history(old, observed_at_utc="2026-08-18T12:00:00+00:00")
    history = append_history(current, history, observed_at_utc="2026-08-18T14:00:00+00:00")
    refresh = "2026-08-18T13:00:00+00:00"
    _write_pipeline(tmp_path, current, history, refresh)
    monkeypatch.setattr(freshness, "build_command_center", lambda _root: current.copy())

    audit = freshness.build_pipeline_freshness_audit(tmp_path).set_index("Stage")

    assert audit.loc["HISTORY", "Freshness_Status"] == freshness.CURRENT
    assert audit.loc["TRANSITION_DIGEST", "Freshness_Status"] == freshness.SOURCE_NEWER
    assert "after digest refresh" in audit.loc["TRANSITION_DIGEST", "Detail"]


def test_queue_control_violation_is_loud_and_never_authoritative(tmp_path: Path, monkeypatch) -> None:
    center = _center()
    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")
    refresh = "2026-08-18T13:00:00+00:00"
    _write_pipeline(tmp_path, center, history, refresh)
    monkeypatch.setattr(freshness, "build_command_center", lambda _root: center.copy())

    bad = {column: "" for column in QUEUE_COLUMNS}
    bad.update(
        {
            "Review_Case_ID": "bad-case",
            "Review_Status": "PENDING_MANUAL_REVIEW",
            "Lane": "Synthetic Lane",
            "Report_Only": False,
            "Production_Authority": "NONE",
            "No_Auto_Promotion": True,
            "Control_Violation": False,
        }
    )
    queue = pd.DataFrame([bad], columns=QUEUE_COLUMNS)
    queue.to_csv(tmp_path / "research_manual_review_queue.csv", index=False)
    build_queue_summary(queue, refresh).to_csv(tmp_path / "research_manual_review_queue_summary.csv", index=False)

    audit = freshness.build_pipeline_freshness_audit(tmp_path).set_index("Stage")
    summary = freshness.build_freshness_summary(audit.reset_index()).iloc[0]

    assert audit.loc["MANUAL_REVIEW_QUEUE", "Freshness_Status"] == freshness.CONTROL_VIOLATION
    assert summary["Overall_Status"] == freshness.CONTROL_VIOLATION


def test_freshness_contract_is_report_only_and_not_a_ninth_scoreboard_card() -> None:
    assert freshness.REPORT_ONLY is True
    assert freshness.PRODUCTION_AUTHORITY == "NONE"
    assert freshness.NO_AUTO_PROMOTION is True
    assert freshness.LOCKED_PROMOTION_SCOREBOARD_CARDS == 8
    assert freshness.VERSION == "research-pipeline-freshness-v1-report-only"
    assert "Score" not in freshness.SUMMARY_COLUMNS

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

VERSION = "research-manual-review-packet-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True
AUTOMATIC_DECISION_ALLOWED = False

PACKET_COLUMNS = [
    "Refresh_At_UTC",
    "Lane",
    "Category",
    "Review_Trigger",
    "Previous_Status",
    "Status",
    "Previous_Ready_For_Manual_Review",
    "Ready_For_Manual_Review",
    "Previous_Evidence_Direction",
    "Evidence_Direction",
    "Previous_Starts",
    "Current_Starts",
    "Required_Starts",
    "Starts_Remaining",
    "Previous_Days",
    "Current_Days",
    "Required_Days",
    "Days_Remaining",
    "Breadth_Label",
    "Previous_Breadth",
    "Current_Breadth",
    "Required_Breadth",
    "Breadth_Remaining",
    "Previous_Secondary_Progress",
    "Secondary_Progress",
    "Previous_Recommended_Action",
    "Recommended_Action",
    "Source_Path",
    "Source_Version",
    "Source_Reason",
    "Change_Summary",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Human_Review_Required",
    "Control_Violation",
    "Packet_Version",
]

SUMMARY_COLUMNS = [
    "Refresh_At_UTC",
    "Packet_Status",
    "Triggered_Lanes",
    "Status_Transition_Lanes",
    "Readiness_Transition_Lanes",
    "Newly_Review_Ready_Lanes",
    "Control_Violation_Lanes",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Packet_Version",
]


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _clean(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _control_violation(row: pd.Series) -> bool:
    return not (
        _truthy(row.get("Report_Only"))
        and _clean(row.get("Production_Authority")).upper() == "NONE"
        and _truthy(row.get("No_Auto_Promotion"))
    )


def _trigger(row: pd.Series) -> str:
    status = _truthy(row.get("Status_Changed"))
    readiness = _truthy(row.get("Readiness_Changed"))
    if status and readiness:
        return "STATUS_AND_READINESS_TRANSITION"
    if status:
        return "STATUS_TRANSITION"
    if readiness:
        return "READINESS_TRANSITION"
    return ""


def _previous_history_row(history: pd.DataFrame, lane: str, refresh_at_utc: str) -> pd.Series:
    if history is None or history.empty:
        return pd.Series(dtype=object)
    frame = history.reset_index(drop=True).copy()
    lane_mask = frame.get("Lane", pd.Series(index=frame.index, dtype=object)).astype(str).eq(str(lane))
    refresh_mask = frame.get("Observed_At_UTC", pd.Series(index=frame.index, dtype=object)).astype(str).eq(str(refresh_at_utc))
    event_mask = frame.get("Event_Type", pd.Series(index=frame.index, dtype=object)).astype(str).eq("EVIDENCE_CHANGE")
    current_positions = frame.index[lane_mask & refresh_mask & event_mask].tolist()
    if not current_positions:
        return pd.Series(dtype=object)
    current_position = current_positions[-1]
    prior_positions = frame.index[lane_mask & (frame.index < current_position)].tolist()
    if not prior_positions:
        return pd.Series(dtype=object)
    return frame.loc[prior_positions[-1]]


def _center_row(command_center: pd.DataFrame, lane: str) -> pd.Series:
    if command_center is None or command_center.empty:
        return pd.Series(dtype=object)
    lane_values = command_center.get("Lane", pd.Series(index=command_center.index, dtype=object)).astype(str)
    selected = command_center.loc[lane_values.eq(str(lane))]
    return selected.iloc[0] if not selected.empty else pd.Series(dtype=object)


def build_manual_review_packet(
    digest: pd.DataFrame,
    history: pd.DataFrame,
    command_center: pd.DataFrame,
    refresh_at_utc: str,
) -> pd.DataFrame:
    if digest is None or digest.empty or not refresh_at_utc:
        return pd.DataFrame(columns=PACKET_COLUMNS)

    digest_frame = digest.copy()
    refresh_values = digest_frame.get("Refresh_At_UTC", pd.Series(index=digest_frame.index, dtype=object)).astype(str)
    digest_frame = digest_frame.loc[refresh_values.eq(str(refresh_at_utc))]
    if digest_frame.empty:
        return pd.DataFrame(columns=PACKET_COLUMNS)

    rows: list[dict[str, object]] = []
    for _, current in digest_frame.iterrows():
        trigger = _trigger(current)
        if not trigger:
            continue
        lane = _clean(current.get("Lane"))
        previous = _previous_history_row(history, lane, refresh_at_utc)
        center = _center_row(command_center, lane)
        violation = _control_violation(current)
        rows.append({
            "Refresh_At_UTC": refresh_at_utc,
            "Lane": lane,
            "Category": current.get("Category"),
            "Review_Trigger": trigger,
            "Previous_Status": previous.get("Status", current.get("Previous_Status")),
            "Status": current.get("Status"),
            "Previous_Ready_For_Manual_Review": previous.get("Ready_For_Manual_Review"),
            "Ready_For_Manual_Review": current.get("Ready_For_Manual_Review"),
            "Previous_Evidence_Direction": previous.get("Evidence_Direction"),
            "Evidence_Direction": current.get("Evidence_Direction"),
            "Previous_Starts": previous.get("Current_Starts"),
            "Current_Starts": current.get("Current_Starts"),
            "Required_Starts": current.get("Required_Starts"),
            "Starts_Remaining": current.get("Starts_Remaining"),
            "Previous_Days": previous.get("Current_Days"),
            "Current_Days": current.get("Current_Days"),
            "Required_Days": current.get("Required_Days"),
            "Days_Remaining": current.get("Days_Remaining"),
            "Breadth_Label": current.get("Breadth_Label"),
            "Previous_Breadth": previous.get("Current_Breadth"),
            "Current_Breadth": current.get("Current_Breadth"),
            "Required_Breadth": current.get("Required_Breadth"),
            "Breadth_Remaining": current.get("Breadth_Remaining"),
            "Previous_Secondary_Progress": previous.get("Secondary_Progress"),
            "Secondary_Progress": current.get("Secondary_Progress"),
            "Previous_Recommended_Action": previous.get("Recommended_Action"),
            "Recommended_Action": current.get("Recommended_Action"),
            "Source_Path": center.get("Source_Path"),
            "Source_Version": current.get("Source_Version"),
            "Source_Reason": current.get("Source_Reason"),
            "Change_Summary": current.get("Change_Summary"),
            "Report_Only": current.get("Report_Only"),
            "Production_Authority": current.get("Production_Authority"),
            "No_Auto_Promotion": current.get("No_Auto_Promotion"),
            "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
            "Human_Review_Required": True,
            "Control_Violation": violation,
            "Packet_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=PACKET_COLUMNS)


def build_packet_summary(packet: pd.DataFrame, digest: pd.DataFrame, refresh_at_utc: str) -> pd.DataFrame:
    frame = packet.copy() if packet is not None else pd.DataFrame(columns=PACKET_COLUMNS)
    digest_frame = digest.copy() if digest is not None else pd.DataFrame()
    if not digest_frame.empty and "Refresh_At_UTC" in digest_frame.columns:
        digest_frame = digest_frame.loc[digest_frame["Refresh_At_UTC"].astype(str).eq(str(refresh_at_utc))]

    digest_violations = 0
    if not digest_frame.empty and "Control_Violation" in digest_frame.columns:
        digest_violations = int(digest_frame["Control_Violation"].map(_truthy).sum())
    packet_violations = 0
    if not frame.empty and "Control_Violation" in frame.columns:
        packet_violations = int(frame["Control_Violation"].map(_truthy).sum())
    violation_lanes = max(digest_violations, packet_violations)

    if violation_lanes:
        status = "CONTROL_VIOLATION"
    elif frame.empty:
        status = "NO_REVIEW_TRIGGER"
    else:
        status = "MANUAL_REVIEW_PACKET_READY"

    def count_trigger(token: str) -> int:
        if frame.empty or "Review_Trigger" not in frame.columns:
            return 0
        return int(frame["Review_Trigger"].astype(str).str.contains(token, regex=False).sum())

    newly_ready = 0
    if not frame.empty:
        current_ready = frame["Ready_For_Manual_Review"].map(_truthy)
        previous_ready = frame["Previous_Ready_For_Manual_Review"].map(_truthy)
        newly_ready = int((current_ready & ~previous_ready).sum())

    return pd.DataFrame([{
        "Refresh_At_UTC": refresh_at_utc,
        "Packet_Status": status,
        "Triggered_Lanes": int(len(frame)),
        "Status_Transition_Lanes": count_trigger("STATUS"),
        "Readiness_Transition_Lanes": count_trigger("READINESS"),
        "Newly_Review_Ready_Lanes": newly_ready,
        "Control_Violation_Lanes": violation_lanes,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
        "Packet_Version": VERSION,
    }], columns=SUMMARY_COLUMNS)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build gated report-only manual review packets from exact-refresh evidence transitions.")
    parser.add_argument("--digest", default="data/research_evidence_transition_digest.csv")
    parser.add_argument("--history", default="data/research_evidence_history.csv")
    parser.add_argument("--command-center", default="data/research_evidence_command_center.csv")
    parser.add_argument("--refresh-at-utc", default=os.getenv("RESEARCH_REFRESH_AT_UTC"))
    parser.add_argument("--output", default="data/research_manual_review_packet.csv")
    parser.add_argument("--summary-output", default="data/research_manual_review_packet_summary.csv")
    args = parser.parse_args()

    refresh_at = args.refresh_at_utc or datetime.now(timezone.utc).isoformat()
    digest = _read_csv(Path(args.digest))
    history = _read_csv(Path(args.history))
    center = _read_csv(Path(args.command_center))
    packet = build_manual_review_packet(digest, history, center, refresh_at)
    summary = build_packet_summary(packet, digest, refresh_at)

    output = Path(args.output)
    summary_output = Path(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    packet.to_csv(output, index=False)
    summary.to_csv(summary_output, index=False)
    print(packet.to_string(index=False) if not packet.empty else "NO_STATUS_OR_READINESS_REVIEW_TRIGGER_THIS_REFRESH")
    print(summary.to_string(index=False))
    print(
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"no_auto_promotion={NO_AUTO_PROMOTION} automatic_decision_allowed={AUTOMATIC_DECISION_ALLOWED} "
        f"packet_version={VERSION}"
    )


if __name__ == "__main__":
    main()

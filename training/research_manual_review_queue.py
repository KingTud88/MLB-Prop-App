from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

VERSION = "research-manual-review-queue-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True
AUTOMATIC_DECISION_ALLOWED = False
DEFAULT_REVIEW_STATUS = "PENDING_MANUAL_REVIEW"

PACKET_FIELDS = [
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

MANUAL_FIELDS = [
    "Review_Status",
    "Reviewed_At_UTC",
    "Reviewer",
    "Review_Notes",
]

QUEUE_COLUMNS = [
    "Review_Case_ID",
    "Queued_At_UTC",
    *PACKET_FIELDS,
    *MANUAL_FIELDS,
    "Queue_Version",
]

SUMMARY_COLUMNS = [
    "Generated_At_UTC",
    "Queue_Status",
    "Total_Cases",
    "Pending_Cases",
    "Pending_Lanes",
    "Non_Pending_Cases",
    "Control_Violation_Cases",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Queue_Version",
]


def _clean(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _truthy(value: object) -> bool:
    return _clean(value).lower() in {"true", "1", "yes", "y"}


def _case_id(row: pd.Series) -> str:
    payload = "|".join(
        [
            _clean(row.get("Refresh_At_UTC")),
            _clean(row.get("Lane")),
            _clean(row.get("Review_Trigger")),
            _clean(row.get("Change_Summary")),
            _clean(row.get("Source_Version")),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _empty_queue() -> pd.DataFrame:
    return pd.DataFrame(columns=QUEUE_COLUMNS)


def append_review_queue(
    packet: pd.DataFrame,
    existing_queue: pd.DataFrame | None = None,
    queued_at_utc: str | None = None,
) -> pd.DataFrame:
    queue = existing_queue.copy() if existing_queue is not None else _empty_queue()
    for column in QUEUE_COLUMNS:
        if column not in queue.columns:
            queue[column] = None
    queue = queue[QUEUE_COLUMNS]

    if packet is None or packet.empty:
        return queue.reset_index(drop=True)

    queued_at = queued_at_utc or datetime.now(timezone.utc).isoformat()
    existing_ids = set(queue["Review_Case_ID"].astype(str)) if not queue.empty else set()
    appended: list[dict[str, object]] = []

    for _, source in packet.iterrows():
        case_id = _case_id(source)
        if case_id in existing_ids:
            continue

        record: dict[str, object] = {
            "Review_Case_ID": case_id,
            "Queued_At_UTC": queued_at,
            "Review_Status": DEFAULT_REVIEW_STATUS,
            "Reviewed_At_UTC": "",
            "Reviewer": "",
            "Review_Notes": "",
            "Queue_Version": VERSION,
        }
        for field in PACKET_FIELDS:
            record[field] = source.get(field)
        appended.append(record)
        existing_ids.add(case_id)

    if appended:
        queue = pd.concat([queue, pd.DataFrame(appended, columns=QUEUE_COLUMNS)], ignore_index=True)
    return queue[QUEUE_COLUMNS].reset_index(drop=True)


def build_queue_summary(queue: pd.DataFrame, generated_at_utc: str | None = None) -> pd.DataFrame:
    frame = queue.copy() if queue is not None else _empty_queue()
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()

    if frame.empty:
        total = pending = non_pending = violations = pending_lanes = 0
        status = "EMPTY"
    else:
        statuses = frame.get("Review_Status", pd.Series(index=frame.index, dtype=object)).map(_clean)
        pending_mask = statuses.eq(DEFAULT_REVIEW_STATUS)
        violation_mask = frame.get("Control_Violation", pd.Series(index=frame.index, dtype=object)).map(_truthy)
        total = int(len(frame))
        pending = int(pending_mask.sum())
        non_pending = total - pending
        violations = int(violation_mask.sum())
        pending_lanes = int(frame.loc[pending_mask, "Lane"].astype(str).nunique()) if pending else 0
        if violations:
            status = "CONTROL_VIOLATION"
        elif pending:
            status = "PENDING_MANUAL_REVIEW"
        else:
            status = "NO_PENDING_REVIEW"

    return pd.DataFrame(
        [
            {
                "Generated_At_UTC": generated,
                "Queue_Status": status,
                "Total_Cases": total,
                "Pending_Cases": pending,
                "Pending_Lanes": pending_lanes,
                "Non_Pending_Cases": non_pending,
                "Control_Violation_Cases": violations,
                "Report_Only": REPORT_ONLY,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "No_Auto_Promotion": NO_AUTO_PROMOTION,
                "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
                "Queue_Version": VERSION,
            }
        ],
        columns=SUMMARY_COLUMNS,
    )


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append exact-refresh manual review packets to a durable report-only review queue."
    )
    parser.add_argument("--packet", default="data/research_manual_review_packet.csv")
    parser.add_argument("--queue", default="data/research_manual_review_queue.csv")
    parser.add_argument("--summary-output", default="data/research_manual_review_queue_summary.csv")
    parser.add_argument("--queued-at-utc", default=None)
    args = parser.parse_args()

    packet = _read_csv(Path(args.packet))
    queue_path = Path(args.queue)
    existing = _read_csv(queue_path)
    queue = append_review_queue(packet, existing, args.queued_at_utc)
    summary = build_queue_summary(queue, args.queued_at_utc)

    queue_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    queue.to_csv(queue_path, index=False)
    summary.to_csv(summary_path, index=False)

    print(queue.tail(20).to_string(index=False) if not queue.empty else "NO_MANUAL_REVIEW_CASES_QUEUED")
    print(summary.to_string(index=False))
    print(
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"no_auto_promotion={NO_AUTO_PROMOTION} automatic_decision_allowed={AUTOMATIC_DECISION_ALLOWED} "
        f"queue_version={VERSION}"
    )


if __name__ == "__main__":
    main()

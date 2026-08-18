from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

VERSION = "research-evidence-transition-digest-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True

DIGEST_COLUMNS = [
    "Refresh_At_UTC",
    "Lane",
    "Category",
    "Previous_Status",
    "Status",
    "Status_Changed",
    "Evidence_Direction_Changed",
    "Progress_Changed",
    "Readiness_Changed",
    "Action_Changed",
    "Source_Version_Changed",
    "Evidence_Direction",
    "Current_Starts",
    "Required_Starts",
    "Starts_Remaining",
    "Current_Days",
    "Required_Days",
    "Days_Remaining",
    "Breadth_Label",
    "Current_Breadth",
    "Required_Breadth",
    "Breadth_Remaining",
    "Secondary_Progress",
    "Ready_For_Manual_Review",
    "Recommended_Action",
    "Source_Reason",
    "Change_Summary",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Control_Violation",
    "Source_Version",
    "Digest_Version",
]

SUMMARY_COLUMNS = [
    "Refresh_At_UTC",
    "Digest_Status",
    "Changed_Lanes",
    "Status_Change_Lanes",
    "Progress_Change_Lanes",
    "Readiness_Change_Lanes",
    "Action_Change_Lanes",
    "Source_Version_Change_Lanes",
    "Review_Ready_Changed_Lanes",
    "Control_Violation_Lanes",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Digest_Version",
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


def _changed(summary: str, field: str) -> bool:
    return f"{field}:" in summary


def _progress_changed(summary: str) -> bool:
    return any(
        _changed(summary, field)
        for field in ("Current_Starts", "Current_Days", "Current_Breadth", "Secondary_Progress")
    )


def _control_violation(row: pd.Series) -> bool:
    return not (
        _truthy(row.get("Report_Only"))
        and _clean(row.get("Production_Authority")).upper() == "NONE"
        and _truthy(row.get("No_Auto_Promotion"))
    )


def build_transition_digest(
    history: pd.DataFrame,
    refresh_at_utc: str,
) -> pd.DataFrame:
    if history is None or history.empty or not refresh_at_utc:
        return pd.DataFrame(columns=DIGEST_COLUMNS)

    frame = history.copy()
    observed = frame.get("Observed_At_UTC", pd.Series(index=frame.index, dtype=object)).astype(str)
    event_type = frame.get("Event_Type", pd.Series(index=frame.index, dtype=object)).astype(str)
    selected = frame.loc[observed.eq(str(refresh_at_utc)) & event_type.eq("EVIDENCE_CHANGE")].copy()
    if selected.empty:
        return pd.DataFrame(columns=DIGEST_COLUMNS)

    rows: list[dict[str, object]] = []
    for _, row in selected.iterrows():
        summary = _clean(row.get("Change_Summary"))
        violation = _control_violation(row)
        rows.append({
            "Refresh_At_UTC": refresh_at_utc,
            "Lane": row.get("Lane"),
            "Category": row.get("Category"),
            "Previous_Status": row.get("Previous_Status"),
            "Status": row.get("Status"),
            "Status_Changed": _changed(summary, "Status"),
            "Evidence_Direction_Changed": _changed(summary, "Evidence_Direction"),
            "Progress_Changed": _progress_changed(summary),
            "Readiness_Changed": _changed(summary, "Ready_For_Manual_Review"),
            "Action_Changed": _changed(summary, "Recommended_Action"),
            "Source_Version_Changed": _changed(summary, "Source_Version"),
            "Evidence_Direction": row.get("Evidence_Direction"),
            "Current_Starts": row.get("Current_Starts"),
            "Required_Starts": row.get("Required_Starts"),
            "Starts_Remaining": row.get("Starts_Remaining"),
            "Current_Days": row.get("Current_Days"),
            "Required_Days": row.get("Required_Days"),
            "Days_Remaining": row.get("Days_Remaining"),
            "Breadth_Label": row.get("Breadth_Label"),
            "Current_Breadth": row.get("Current_Breadth"),
            "Required_Breadth": row.get("Required_Breadth"),
            "Breadth_Remaining": row.get("Breadth_Remaining"),
            "Secondary_Progress": row.get("Secondary_Progress"),
            "Ready_For_Manual_Review": row.get("Ready_For_Manual_Review"),
            "Recommended_Action": row.get("Recommended_Action"),
            "Source_Reason": row.get("Source_Reason"),
            "Change_Summary": summary,
            "Report_Only": row.get("Report_Only"),
            "Production_Authority": row.get("Production_Authority"),
            "No_Auto_Promotion": row.get("No_Auto_Promotion"),
            "Control_Violation": violation,
            "Source_Version": row.get("Source_Version"),
            "Digest_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=DIGEST_COLUMNS)


def build_digest_summary(digest: pd.DataFrame, refresh_at_utc: str) -> pd.DataFrame:
    frame = digest.copy() if digest is not None else pd.DataFrame(columns=DIGEST_COLUMNS)
    violations = frame.get("Control_Violation", pd.Series(dtype=bool)).map(_truthy) if not frame.empty else pd.Series(dtype=bool)
    if not frame.empty and bool(violations.any()):
        status = "CONTROL_VIOLATION"
    elif frame.empty:
        status = "NO_CHANGES"
    else:
        status = "CHANGES_DETECTED"

    def count_true(column: str) -> int:
        if frame.empty or column not in frame.columns:
            return 0
        return int(frame[column].map(_truthy).sum())

    review_ready = 0
    if not frame.empty and "Ready_For_Manual_Review" in frame.columns:
        review_ready = int(frame["Ready_For_Manual_Review"].map(_truthy).sum())

    return pd.DataFrame([{
        "Refresh_At_UTC": refresh_at_utc,
        "Digest_Status": status,
        "Changed_Lanes": int(len(frame)),
        "Status_Change_Lanes": count_true("Status_Changed"),
        "Progress_Change_Lanes": count_true("Progress_Changed"),
        "Readiness_Change_Lanes": count_true("Readiness_Changed"),
        "Action_Change_Lanes": count_true("Action_Changed"),
        "Source_Version_Change_Lanes": count_true("Source_Version_Changed"),
        "Review_Ready_Changed_Lanes": review_ready,
        "Control_Violation_Lanes": int(violations.sum()) if not violations.empty else 0,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Digest_Version": VERSION,
    }], columns=SUMMARY_COLUMNS)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the exact-refresh report-only research evidence transition digest.")
    parser.add_argument("--history", default="data/research_evidence_history.csv")
    parser.add_argument("--refresh-at-utc", default=os.getenv("RESEARCH_REFRESH_AT_UTC"))
    parser.add_argument("--output", default="data/research_evidence_transition_digest.csv")
    parser.add_argument("--summary-output", default="data/research_evidence_transition_digest_summary.csv")
    args = parser.parse_args()

    refresh_at = args.refresh_at_utc or datetime.now(timezone.utc).isoformat()
    history = _read_csv(Path(args.history))
    digest = build_transition_digest(history, refresh_at)
    summary = build_digest_summary(digest, refresh_at)

    output = Path(args.output)
    summary_output = Path(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    digest.to_csv(output, index=False)
    summary.to_csv(summary_output, index=False)
    print(digest.to_string(index=False) if not digest.empty else "NO_EVIDENCE_CHANGES_THIS_REFRESH")
    print(summary.to_string(index=False))
    print(
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"no_auto_promotion={NO_AUTO_PROMOTION} digest_version={VERSION}"
    )


if __name__ == "__main__":
    main()

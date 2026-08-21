from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

VERSION = "research-evidence-history-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True

TRACKED_FIELDS = [
    "Status",
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
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Source_Version",
]

CHANGE_SUMMARY_FIELDS = [
    "Status",
    "Evidence_Direction",
    "Current_Starts",
    "Current_Days",
    "Current_Breadth",
    "Secondary_Progress",
    "Ready_For_Manual_Review",
    "Recommended_Action",
    "Source_Reason",
    "Source_Version",
]

HISTORY_COLUMNS = [
    "Observed_At_UTC",
    "Event_Type",
    "Lane",
    "Category",
    "Previous_Status",
    *TRACKED_FIELDS,
    "Change_Summary",
    "Fingerprint",
    "History_Version",
]

SUMMARY_COLUMNS = [
    "Lane",
    "Category",
    "First_Observed_At_UTC",
    "Last_Changed_At_UTC",
    "Recorded_Events",
    "Transition_Count",
    "Current_Status",
    "Current_Evidence_Direction",
    "Current_Starts",
    "Current_Days",
    "Current_Breadth",
    "Ready_For_Manual_Review",
    "Recommended_Action",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Source_Version",
    "History_Version",
]


def _missing(value: object) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _normalize(value: object) -> object:
    if _missing(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return int(number) if number.is_integer() else number
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        number = float(text)
        return int(number) if number.is_integer() else number
    except ValueError:
        return text


def _display(value: object) -> str:
    normalized = _normalize(value)
    if normalized is None:
        return "NA"
    if isinstance(normalized, bool):
        return "True" if normalized else "False"
    return str(normalized)


def fingerprint_row(row: pd.Series) -> str:
    payload = {field: _normalize(row.get(field)) for field in TRACKED_FIELDS}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _change_summary(previous: pd.Series | None, current: pd.Series) -> str:
    if previous is None or previous.empty:
        return "BASELINE_CAPTURE"
    changes: list[str] = []
    for field in CHANGE_SUMMARY_FIELDS:
        old = _normalize(previous.get(field))
        new = _normalize(current.get(field))
        if old == new:
            continue
        if field == "Source_Reason":
            changes.append("Source_Reason:CHANGED")
        else:
            changes.append(f"{field}:{_display(old)}->{_display(new)}")
    return "; ".join(changes) if changes else "TRACKED_EVIDENCE_CHANGED"


def _empty_history() -> pd.DataFrame:
    return pd.DataFrame(columns=HISTORY_COLUMNS)


def append_history(
    command_center: pd.DataFrame,
    existing_history: pd.DataFrame | None = None,
    observed_at_utc: str | None = None,
) -> pd.DataFrame:
    center = command_center.copy() if command_center is not None else pd.DataFrame()
    history = existing_history.copy() if existing_history is not None else _empty_history()
    for column in HISTORY_COLUMNS:
        if column not in history.columns:
            history[column] = None
    history = history[HISTORY_COLUMNS]

    if center.empty:
        return history.reset_index(drop=True)

    observed = observed_at_utc or datetime.now(timezone.utc).isoformat()
    appended: list[dict[str, object]] = []

    for _, current in center.iterrows():
        lane = str(current.get("Lane", "")).strip()
        if not lane:
            continue
        prior_rows = history.loc[history["Lane"].astype(str).eq(lane)]
        previous = prior_rows.iloc[-1] if not prior_rows.empty else None
        fingerprint = fingerprint_row(current)
        if previous is not None and str(previous.get("Fingerprint", "")).strip() == fingerprint:
            continue

        event_type = "BASELINE_CAPTURE" if previous is None else "EVIDENCE_CHANGE"
        record: dict[str, object] = {
            "Observed_At_UTC": observed,
            "Event_Type": event_type,
            "Lane": lane,
            "Category": current.get("Category"),
            "Previous_Status": "" if previous is None else previous.get("Status"),
            "Change_Summary": _change_summary(previous, current),
            "Fingerprint": fingerprint,
            "History_Version": VERSION,
        }
        for field in TRACKED_FIELDS:
            record[field] = current.get(field)
        appended.append(record)

    if appended:
        history = pd.concat([history, pd.DataFrame(appended, columns=HISTORY_COLUMNS)], ignore_index=True)
    return history[HISTORY_COLUMNS].reset_index(drop=True)


def build_history_summary(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    rows: list[dict[str, object]] = []
    for lane, group in history.groupby("Lane", sort=False):
        ordered = group.reset_index(drop=True)
        latest = ordered.iloc[-1]
        transitions = ordered["Event_Type"].astype(str).eq("EVIDENCE_CHANGE")
        rows.append({
            "Lane": lane,
            "Category": latest.get("Category"),
            "First_Observed_At_UTC": ordered.iloc[0].get("Observed_At_UTC"),
            "Last_Changed_At_UTC": latest.get("Observed_At_UTC"),
            "Recorded_Events": int(len(ordered)),
            "Transition_Count": int(transitions.sum()),
            "Current_Status": latest.get("Status"),
            "Current_Evidence_Direction": latest.get("Evidence_Direction"),
            "Current_Starts": latest.get("Current_Starts"),
            "Current_Days": latest.get("Current_Days"),
            "Current_Breadth": latest.get("Current_Breadth"),
            "Ready_For_Manual_Review": latest.get("Ready_For_Manual_Review"),
            "Recommended_Action": latest.get("Recommended_Action"),
            "Report_Only": latest.get("Report_Only"),
            "Production_Authority": latest.get("Production_Authority"),
            "No_Auto_Promotion": latest.get("No_Auto_Promotion"),
            "Source_Version": latest.get("Source_Version"),
            "History_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Append change-only report-only research evidence history.")
    parser.add_argument("--command-center", default="data/research_promotion_command_center.csv")
    parser.add_argument("--history", default="data/research_evidence_history.csv")
    parser.add_argument("--summary-output", default="data/research_evidence_history_summary.csv")
    parser.add_argument("--observed-at-utc", default=None)
    args = parser.parse_args()

    center_path = Path(args.command_center)
    history_path = Path(args.history)
    summary_path = Path(args.summary_output)
    center = _read_csv(center_path)
    existing = _read_csv(history_path)
    history = append_history(center, existing, args.observed_at_utc)
    summary = build_history_summary(history)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(history_path, index=False)
    summary.to_csv(summary_path, index=False)
    print(history.tail(24).to_string(index=False))
    print(summary.to_string(index=False))
    print(
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"no_auto_promotion={NO_AUTO_PROMOTION} history_version={VERSION}"
    )


if __name__ == "__main__":
    main()

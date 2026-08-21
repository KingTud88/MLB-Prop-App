from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

VERSION = "research-milestone-watch-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True
AUTOMATIC_DECISION_ALLOWED = False

WATCH_COLUMNS = [
    "Lane",
    "Category",
    "Status",
    "Primary_Gate_State",
    "Blocking_Dimensions",
    "Starts_Remaining",
    "Days_Remaining",
    "Breadth_Label",
    "Breadth_Remaining",
    "Secondary_Progress",
    "Ready_For_Manual_Review",
    "Recommended_Action",
    "Source_Reason",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Source_Version",
    "Watch_Version",
]

SUMMARY_COLUMNS = [
    "Total_Lanes",
    "Manual_Review_Ready_Lanes",
    "Primary_Dimensions_Mature_Lanes",
    "Primary_Dimensions_Blocked_Lanes",
    "Nonstandard_Gate_Lanes",
    "Source_Missing_Lanes",
    "All_Report_Only",
    "All_Production_Authority_None",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Watch_Version",
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


def _number(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _remaining(value: object) -> int | float | None:
    number = _number(value)
    if number is None:
        return None
    number = max(0.0, number)
    return int(number) if number.is_integer() else number


def _source_contract_ok(frame: pd.DataFrame) -> bool:
    if frame is None or frame.empty:
        return False
    report_only = frame.get("Report_Only", pd.Series(False, index=frame.index)).map(_truthy)
    authority = (
        frame.get("Production_Authority", pd.Series("", index=frame.index))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    no_auto = frame.get("No_Auto_Promotion", pd.Series(False, index=frame.index)).map(_truthy)
    return bool(report_only.all() and authority.eq("NONE").all() and no_auto.all())


def _primary_gate_state(row: pd.Series) -> tuple[str, str]:
    if _clean(row.get("Status")).upper() == "SOURCE_MISSING":
        return "SOURCE_MISSING", "SOURCE"

    if _truthy(row.get("Ready_For_Manual_Review")):
        return "MANUAL_REVIEW_READY", ""

    dimensions = [
        ("STARTS", row.get("Required_Starts"), row.get("Starts_Remaining")),
        ("DAYS", row.get("Required_Days"), row.get("Days_Remaining")),
        (_clean(row.get("Breadth_Label")).upper() or "BREADTH", row.get("Required_Breadth"), row.get("Breadth_Remaining")),
    ]
    applicable = [(label, _remaining(remaining)) for label, required, remaining in dimensions if _number(required) is not None]
    if not applicable:
        return "NONSTANDARD_GATE_TRACKED_ELSEWHERE", ""

    blockers = [f"{label}={remaining}" for label, remaining in applicable if remaining is not None and remaining > 0]
    if blockers:
        return "PRIMARY_DIMENSIONS_BLOCKED", "|".join(blockers)

    # This is intentionally not called promotion-ready: source-specific secondary
    # requirements and the source Manual_Review_Ready field remain authoritative.
    return "PRIMARY_DIMENSIONS_MATURE", ""


def build_milestone_watch(command_center: pd.DataFrame) -> pd.DataFrame:
    if command_center is None or command_center.empty:
        return pd.DataFrame(columns=WATCH_COLUMNS)
    if not _source_contract_ok(command_center):
        raise ValueError("Research command center violates the report-only production-authority contract.")

    rows: list[dict[str, object]] = []
    for _, row in command_center.iterrows():
        state, blockers = _primary_gate_state(row)
        rows.append(
            {
                "Lane": row.get("Lane"),
                "Category": row.get("Category"),
                "Status": row.get("Status"),
                "Primary_Gate_State": state,
                "Blocking_Dimensions": blockers,
                "Starts_Remaining": _remaining(row.get("Starts_Remaining")),
                "Days_Remaining": _remaining(row.get("Days_Remaining")),
                "Breadth_Label": row.get("Breadth_Label"),
                "Breadth_Remaining": _remaining(row.get("Breadth_Remaining")),
                "Secondary_Progress": row.get("Secondary_Progress"),
                "Ready_For_Manual_Review": _truthy(row.get("Ready_For_Manual_Review")),
                "Recommended_Action": row.get("Recommended_Action"),
                "Source_Reason": row.get("Source_Reason"),
                "Report_Only": REPORT_ONLY,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "No_Auto_Promotion": NO_AUTO_PROMOTION,
                "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
                "Source_Version": row.get("Source_Version"),
                "Watch_Version": VERSION,
            }
        )
    return pd.DataFrame(rows, columns=WATCH_COLUMNS)


def build_watch_summary(watch: pd.DataFrame) -> pd.DataFrame:
    frame = watch.copy() if watch is not None else pd.DataFrame(columns=WATCH_COLUMNS)
    states = frame.get("Primary_Gate_State", pd.Series(dtype=object)).fillna("").astype(str)
    ready = frame.get("Ready_For_Manual_Review", pd.Series(dtype=object)).map(_truthy) if not frame.empty else pd.Series(dtype=bool)
    report_only = frame.get("Report_Only", pd.Series(dtype=object)).map(_truthy) if not frame.empty else pd.Series(dtype=bool)
    authority = (
        frame.get("Production_Authority", pd.Series(dtype=object)).fillna("").astype(str).str.upper()
        if not frame.empty
        else pd.Series(dtype=object)
    )
    return pd.DataFrame(
        [
            {
                "Total_Lanes": int(len(frame)),
                "Manual_Review_Ready_Lanes": int(ready.sum()) if not ready.empty else 0,
                "Primary_Dimensions_Mature_Lanes": int(states.eq("PRIMARY_DIMENSIONS_MATURE").sum()),
                "Primary_Dimensions_Blocked_Lanes": int(states.eq("PRIMARY_DIMENSIONS_BLOCKED").sum()),
                "Nonstandard_Gate_Lanes": int(states.eq("NONSTANDARD_GATE_TRACKED_ELSEWHERE").sum()),
                "Source_Missing_Lanes": int(states.eq("SOURCE_MISSING").sum()),
                "All_Report_Only": bool(report_only.all()) if not report_only.empty else True,
                "All_Production_Authority_None": bool(authority.eq("NONE").all()) if not authority.empty else True,
                "No_Auto_Promotion": NO_AUTO_PROMOTION,
                "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
                "Watch_Version": VERSION,
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
    parser = argparse.ArgumentParser(description="Build a report-only watch of exact blockers on existing research evidence gates.")
    parser.add_argument("--command-center", default="data/research_promotion_command_center.csv")
    parser.add_argument("--output", default="data/research_milestone_watch.csv")
    parser.add_argument("--summary-output", default="data/research_milestone_watch_summary.csv")
    args = parser.parse_args()

    command_center = _read_csv(Path(args.command_center))
    if command_center.empty:
        raise SystemExit("Research evidence command center is required.")

    watch = build_milestone_watch(command_center)
    summary = build_watch_summary(watch)
    output = Path(args.output)
    summary_output = Path(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    watch.to_csv(output, index=False)
    summary.to_csv(summary_output, index=False)

    print(summary.to_string(index=False))
    print(watch.to_string(index=False))
    print(
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"no_auto_promotion={NO_AUTO_PROMOTION} automatic_decision_allowed={AUTOMATIC_DECISION_ALLOWED}"
    )


if __name__ == "__main__":
    main()

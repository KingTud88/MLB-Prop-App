from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from training.research_evidence_command_center import COLUMNS, build_command_center

VERSION = "research-promotion-command-center-v2-all-lanes"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True
SCOREBOARD_MODE = "ALL_LANES"

SUMMARY_COLUMNS = [
    "Total_Lanes", "Learning_Lanes", "Review_Ready_Lanes", "Failing_Lanes",
    "Source_Missing_Lanes", "All_Report_Only", "All_Production_Authority_None",
    "No_Auto_Promotion", "Scoreboard_Mode", "Command_Center_Version",
]


def _read(data_dir: Path, filename: str) -> pd.DataFrame:
    path = data_dir / filename
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def _clean(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _number(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _integer(value: object) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _remaining(current: int | None, required: int | None) -> int | None:
    if current is None or required is None:
        return None
    return max(0, required - current)


def _pct(value: object, *, signed: bool = False) -> str:
    number = _number(value)
    if number is None:
        return "NA"
    return f"{number:+.2%}" if signed else f"{number:.1%}"


def _base_row(
    *, lane: str, source_path: str, status: str, direction: str,
    current_starts: int | None, required_starts: int | None,
    current_days: int | None, required_days: int | None,
    current_breadth: int | None, required_breadth: int | None,
    breadth_label: str, secondary: str, ready: bool, action: str,
    reason: str, source_version: str,
) -> dict[str, object]:
    return {
        "Lane": lane,
        "Category": "K_RESEARCH",
        "Source_Path": source_path,
        "Status": status or "UNKNOWN",
        "Evidence_Direction": direction,
        "Current_Starts": current_starts,
        "Required_Starts": required_starts,
        "Starts_Remaining": _remaining(current_starts, required_starts),
        "Current_Days": current_days,
        "Required_Days": required_days,
        "Days_Remaining": _remaining(current_days, required_days),
        "Breadth_Label": breadth_label,
        "Current_Breadth": current_breadth,
        "Required_Breadth": required_breadth,
        "Breadth_Remaining": _remaining(current_breadth, required_breadth),
        "Secondary_Progress": secondary,
        "Ready_For_Manual_Review": bool(ready),
        "Recommended_Action": action,
        "Source_Reason": reason,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Source_Version": source_version,
        "Command_Center_Version": VERSION,
    }


def _missing(lane: str, source_path: str) -> dict[str, object]:
    return _base_row(
        lane=lane,
        source_path=source_path,
        status="SOURCE_MISSING",
        direction="",
        current_starts=None,
        required_starts=None,
        current_days=None,
        required_days=None,
        current_breadth=None,
        required_breadth=None,
        breadth_label="PITCHERS",
        secondary="",
        ready=False,
        action="REFRESH_REPORT_ONLY_RESEARCH_SOURCE",
        reason="Report-only research source is missing; no evidence is reconstructed.",
        source_version="",
    )


def _crusher_lane(data_dir: Path) -> dict[str, object]:
    filename = "projection_crusher_shadow_gate.csv"
    source_path = f"data/{filename}"
    frame = _read(data_dir, filename)
    if frame.empty:
        return _missing("Projection Crusher Shadow", source_path)
    row = frame.iloc[0]
    return _base_row(
        lane="Projection Crusher Shadow",
        source_path=source_path,
        status=_clean(row.get("Status")),
        direction=(
            f"beat_projection_rate={_pct(row.get('Beat_Projection_Rate'))}; "
            f"material_crusher_rate={_pct(row.get('Material_Crusher_Rate'))}; "
            f"mean_k_residual={_number(row.get('Mean_K_Residual')) if _number(row.get('Mean_K_Residual')) is not None else 'NA'}"
        ),
        current_starts=_integer(row.get("Resolved_Starts")),
        required_starts=_integer(row.get("Required_Starts")),
        current_days=_integer(row.get("Resolved_Days")),
        required_days=_integer(row.get("Required_Days")),
        current_breadth=_integer(row.get("Distinct_Pitchers")),
        required_breadth=_integer(row.get("Required_Pitchers")),
        breadth_label="PITCHERS",
        secondary=f"cohorts_tracked={_integer(row.get('Cohorts_Tracked')) or 0}; exact_projection_outcome=true",
        ready=_truthy(row.get("Ready_For_Manual_Review")),
        action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")),
        source_version=_clean(row.get("Research_Version")),
    )


def _ladder_lane(data_dir: Path) -> dict[str, object]:
    filename = "k_ladder_reliability_shadow_gate.csv"
    source_path = f"data/{filename}"
    frame = _read(data_dir, filename)
    if frame.empty:
        return _missing("K Ladder Reliability Shadow", source_path)
    row = frame.iloc[0]
    return _base_row(
        lane="K Ladder Reliability Shadow",
        source_path=source_path,
        status=_clean(row.get("Status")),
        direction=(
            f"ladder_win_rate={_pct(row.get('Ladder_Win_Rate'))}; "
            f"avg_target_probability={_pct(row.get('Avg_Target_Probability'))}; "
            f"calibration_gap={_pct(row.get('Calibration_Gap'), signed=True)}; "
            f"brier={_number(row.get('Brier_Score')) if _number(row.get('Brier_Score')) is not None else 'NA'}"
        ),
        current_starts=_integer(row.get("Resolved_Calls")),
        required_starts=_integer(row.get("Required_Calls")),
        current_days=_integer(row.get("Resolved_Days")),
        required_days=_integer(row.get("Required_Days")),
        current_breadth=_integer(row.get("Distinct_Pitchers")),
        required_breadth=_integer(row.get("Required_Pitchers")),
        breadth_label="PITCHERS",
        secondary=(
            f"probability_coverage={_pct(row.get('Probability_Coverage'))}/"
            f"{_pct(row.get('Required_Probability_Coverage'))}; cohorts_tracked={_integer(row.get('Cohorts_Tracked')) or 0}; "
            "sportsbook_execution=false"
        ),
        ready=_truthy(row.get("Ready_For_Manual_Review")),
        action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")),
        source_version=_clean(row.get("Research_Version")),
    )


def build_promotion_command_center(data_dir: Path | str = "data") -> pd.DataFrame:
    root = Path(data_dir)
    base = build_command_center(root).copy()
    extra = pd.DataFrame([_crusher_lane(root), _ladder_lane(root)], columns=COLUMNS)
    extra_names = set(extra["Lane"].astype(str))
    if not base.empty:
        base = base.loc[~base["Lane"].astype(str).isin(extra_names)].copy()
    return pd.concat([base, extra], ignore_index=True)[COLUMNS]


def build_summary(command_center: pd.DataFrame) -> pd.DataFrame:
    frame = command_center.copy() if command_center is not None else pd.DataFrame(columns=COLUMNS)
    statuses = frame.get("Status", pd.Series(dtype=object)).fillna("").astype(str).str.upper()
    ready = frame.get("Ready_For_Manual_Review", pd.Series(dtype=bool)).map(_truthy) if not frame.empty else pd.Series(dtype=bool)
    report_only = frame.get("Report_Only", pd.Series(dtype=bool)).map(_truthy) if not frame.empty else pd.Series(dtype=bool)
    authority = frame.get("Production_Authority", pd.Series(dtype=object)).fillna("").astype(str).str.upper()
    return pd.DataFrame([{
        "Total_Lanes": int(len(frame)),
        "Learning_Lanes": int(statuses.isin({"LEARNING", "INCONCLUSIVE"}).sum()),
        "Review_Ready_Lanes": int(ready.sum()) if not ready.empty else 0,
        "Failing_Lanes": int(statuses.isin({"FAIL", "HURTING", "HURTING_BOTH"}).sum()),
        "Source_Missing_Lanes": int(statuses.eq("SOURCE_MISSING").sum()),
        "All_Report_Only": bool(report_only.all()) if not report_only.empty else True,
        "All_Production_Authority_None": bool(authority.eq("NONE").all()) if not authority.empty else True,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Scoreboard_Mode": SCOREBOARD_MODE,
        "Command_Center_Version": VERSION,
    }], columns=SUMMARY_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the all-lanes report-only research promotion command center.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default="data/research_promotion_command_center.csv")
    parser.add_argument("--summary-output", default="data/research_promotion_command_center_summary.csv")
    args = parser.parse_args()
    center = build_promotion_command_center(args.data_dir)
    summary = build_summary(center)
    output = Path(args.output)
    summary_output = Path(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    center.to_csv(output, index=False)
    summary.to_csv(summary_output, index=False)
    print(center.to_string(index=False))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

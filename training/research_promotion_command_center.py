from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from training.calibration_common_mode_v2 import (
    MIN_DISTINCT_PITCHERS as CAL_V2_MIN_DISTINCT_PITCHERS,
    MIN_EVIDENCE_DAYS as CAL_V2_MIN_EVIDENCE_DAYS,
    MIN_OOS_STARTS as CAL_V2_MIN_OOS_STARTS,
)
from training.input_quality_matched_v2 import (
    MIN_MATCHED_PAIRS as INPUT_QUALITY_MIN_MATCHED_PAIRS,
    PRIMARY_RULE as INPUT_QUALITY_PRIMARY_RULE,
)
from training.research_evidence_command_center import COLUMNS, build_command_center
from training.research_governance_v2 import apply_promotion_governance

VERSION = "research-promotion-command-center-v4-governance-v2"
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
    if isinstance(value, bool):
        return value
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


def _source_contract(row: pd.Series) -> tuple[bool, str]:
    report_only = _truthy(row.get("Report_Only", row.get("Report Only", REPORT_ONLY)))
    authority = _clean(row.get("Production_Authority", row.get("Production Authority", PRODUCTION_AUTHORITY)))
    return report_only, authority or PRODUCTION_AUTHORITY


def _base_row(
    *,
    lane: str,
    category: str,
    source_path: str,
    status: str,
    direction: str = "",
    current_starts: int | None = None,
    required_starts: int | None = None,
    current_days: int | None = None,
    required_days: int | None = None,
    breadth_label: str = "",
    current_breadth: int | None = None,
    required_breadth: int | None = None,
    secondary: str = "",
    ready: bool = False,
    action: str = "",
    reason: str = "",
    report_only: bool = REPORT_ONLY,
    authority: str = PRODUCTION_AUTHORITY,
    source_version: str = "",
) -> dict[str, object]:
    return {
        "Lane": lane,
        "Category": category,
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
        "Report_Only": bool(report_only),
        "Production_Authority": authority or PRODUCTION_AUTHORITY,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Source_Version": source_version,
        "Command_Center_Version": VERSION,
    }


def _missing(lane: str, category: str, source_path: str) -> dict[str, object]:
    return _base_row(
        lane=lane,
        category=category,
        source_path=source_path,
        status="SOURCE_MISSING",
        action="REFRESH_REPORT_ONLY_RESEARCH_SOURCE",
        reason="Authoritative report-only research source is missing; no evidence is reconstructed.",
    )


def _crusher_lane(data_dir: Path) -> dict[str, object]:
    filename = "projection_crusher_shadow_gate.csv"
    source = f"data/{filename}"
    frame = _read(data_dir, filename)
    if frame.empty:
        return _missing("Projection Crusher Shadow", "K_RESEARCH", source)
    row = frame.iloc[0]
    report_only, authority = _source_contract(row)
    return _base_row(
        lane="Projection Crusher Shadow", category="K_RESEARCH", source_path=source,
        status=_clean(row.get("Status")),
        direction=(
            f"beat_projection_rate={_pct(row.get('Beat_Projection_Rate'))}; "
            f"material_crusher_rate={_pct(row.get('Material_Crusher_Rate'))}; "
            f"mean_k_residual={_number(row.get('Mean_K_Residual')) if _number(row.get('Mean_K_Residual')) is not None else 'NA'}"
        ),
        current_starts=_integer(row.get("Resolved_Starts")), required_starts=_integer(row.get("Required_Starts")),
        current_days=_integer(row.get("Resolved_Days")), required_days=_integer(row.get("Required_Days")),
        breadth_label="PITCHERS", current_breadth=_integer(row.get("Distinct_Pitchers")), required_breadth=_integer(row.get("Required_Pitchers")),
        secondary=f"cohorts_tracked={_integer(row.get('Cohorts_Tracked')) or 0}; exact_projection_outcome=true",
        ready=_truthy(row.get("Ready_For_Manual_Review")), action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")), report_only=report_only, authority=authority,
        source_version=_clean(row.get("Research_Version")),
    )


def _underperformer_lane(data_dir: Path) -> dict[str, object]:
    filename = "projection_underperformer_shadow_gate.csv"
    source = f"data/{filename}"
    frame = _read(data_dir, filename)
    if frame.empty:
        return _missing("Projection Underperformer Shadow", "K_RESEARCH", source)
    row = frame.iloc[0]
    report_only, authority = _source_contract(row)
    return _base_row(
        lane="Projection Underperformer Shadow", category="K_RESEARCH", source_path=source,
        status=_clean(row.get("Status")),
        direction=(
            f"below_projection_rate={_pct(row.get('Below_Projection_Rate'))}; "
            f"material_underperform_rate={_pct(row.get('Material_Underperform_Rate'))}; "
            f"mean_k_residual={_number(row.get('Mean_K_Residual')) if _number(row.get('Mean_K_Residual')) is not None else 'NA'}"
        ),
        current_starts=_integer(row.get("Resolved_Starts")), required_starts=_integer(row.get("Required_Starts")),
        current_days=_integer(row.get("Resolved_Days")), required_days=_integer(row.get("Required_Days")),
        breadth_label="PITCHERS", current_breadth=_integer(row.get("Distinct_Pitchers")), required_breadth=_integer(row.get("Required_Pitchers")),
        secondary=f"cohorts_tracked={_integer(row.get('Cohorts_Tracked')) or 0}; exact_projection_outcome=true; negative_tail=true",
        ready=_truthy(row.get("Ready_For_Manual_Review")), action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")), report_only=report_only, authority=authority,
        source_version=_clean(row.get("Research_Version")),
    )


def _ladder_lane(data_dir: Path) -> dict[str, object]:
    filename = "k_ladder_reliability_shadow_gate.csv"
    source = f"data/{filename}"
    frame = _read(data_dir, filename)
    if frame.empty:
        return _missing("K Ladder Reliability Shadow", "K_RESEARCH", source)
    row = frame.iloc[0]
    report_only, authority = _source_contract(row)
    return _base_row(
        lane="K Ladder Reliability Shadow", category="K_RESEARCH", source_path=source,
        status=_clean(row.get("Status")),
        direction=(
            f"ladder_win_rate={_pct(row.get('Ladder_Win_Rate'))}; "
            f"avg_target_probability={_pct(row.get('Avg_Target_Probability'))}; "
            f"calibration_gap={_pct(row.get('Calibration_Gap'), signed=True)}; "
            f"brier={_number(row.get('Brier_Score')) if _number(row.get('Brier_Score')) is not None else 'NA'}"
        ),
        current_starts=_integer(row.get("Resolved_Calls")), required_starts=_integer(row.get("Required_Calls")),
        current_days=_integer(row.get("Resolved_Days")), required_days=_integer(row.get("Required_Days")),
        breadth_label="PITCHERS", current_breadth=_integer(row.get("Distinct_Pitchers")), required_breadth=_integer(row.get("Required_Pitchers")),
        secondary=(
            f"probability_coverage={_pct(row.get('Probability_Coverage'))}/{_pct(row.get('Required_Probability_Coverage'))}; "
            f"cohorts_tracked={_integer(row.get('Cohorts_Tracked')) or 0}; sportsbook_execution=false"
        ),
        ready=_truthy(row.get("Ready_For_Manual_Review")), action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")), report_only=report_only, authority=authority,
        source_version=_clean(row.get("Research_Version")),
    )


def _input_quality_lane(data_dir: Path, metric: str) -> dict[str, object]:
    filename = "input_quality_matched_v2_summary.csv"
    source = f"data/{filename}"
    frame = _read(data_dir, filename)
    lane = f"Input Quality v2 · {metric.title() if metric != 'STRIKEOUTS' else 'Strikeouts'}"
    if frame.empty:
        return _missing(lane, "INPUT_QUALITY", source)
    rule = frame.get("Rule", pd.Series(index=frame.index, dtype=str)).astype(str)
    metrics = frame.get("Metric", pd.Series(index=frame.index, dtype=str)).astype(str).str.upper()
    selected = frame.loc[rule.eq(INPUT_QUALITY_PRIMARY_RULE.name) & metrics.eq(metric)]
    if selected.empty:
        return _missing(lane, "INPUT_QUALITY", source)
    row = selected.iloc[0]
    status = _clean(row.get("Status"))
    authority = _clean(row.get("Production_Authority")) or PRODUCTION_AUTHORITY
    return _base_row(
        lane=lane, category="INPUT_QUALITY", source_path=source, status=status,
        direction=(
            f"relative_mae_deep_vs_shallow={_pct(row.get('Relative_MAE_Improvement_Deep_vs_Shallow'), signed=True)}; "
            f"shallow_bias={_number(row.get('Shallow_Bias')) if _number(row.get('Shallow_Bias')) is not None else 'NA'}; "
            f"deep_bias={_number(row.get('Deep_Bias')) if _number(row.get('Deep_Bias')) is not None else 'NA'}"
        ),
        current_starts=_integer(row.get("Matched_Pairs")), required_starts=INPUT_QUALITY_MIN_MATCHED_PAIRS,
        breadth_label="MATCHED PAIRS", current_breadth=_integer(row.get("Matched_Pairs")), required_breadth=INPUT_QUALITY_MIN_MATCHED_PAIRS,
        secondary=(
            f"eligible_shallow={_integer(row.get('Eligible_Shallow')) or 0}; eligible_deep={_integer(row.get('Eligible_Deep')) or 0}; "
            f"future_only={_clean(row.get('Future_Only_Start'))}; rule={INPUT_QUALITY_PRIMARY_RULE.name}"
        ),
        ready=False,
        action="PRESERVE_FROZEN_MATCHED_COHORT_AND_LEARN" if status == "LEARNING" else "MANUAL_RESEARCH_REVIEW_ONLY",
        reason="Primary frozen matched-cohort source verdict; same-pitcher sensitivity remains diagnostic and no production behavior is activated.",
        authority=authority, source_version=_clean(row.get("Audit_Version")),
    )


def _calibration_common_mode_lane(data_dir: Path) -> dict[str, object]:
    filename = "calibration_common_mode_v2_summary.csv"
    source = f"data/{filename}"
    frame = _read(data_dir, filename)
    if frame.empty:
        return _missing("Calibration Common-Mode v2", "CALIBRATION", source)
    row = frame.iloc[0]
    status = _clean(row.get("Status"))
    authority = _clean(row.get("Production_Authority")) or PRODUCTION_AUTHORITY
    return _base_row(
        lane="Calibration Common-Mode v2", category="CALIBRATION", source_path=source, status=status,
        direction=(
            f"relative_mae={_pct(row.get('Relative_MAE_Improvement'), signed=True)}; "
            f"win_share={_pct(row.get('Candidate_Win_Share'))}; "
            f"baseline_bias={_number(row.get('Baseline_Bias')) if _number(row.get('Baseline_Bias')) is not None else 'NA'}; "
            f"candidate_bias={_number(row.get('Candidate_Bias')) if _number(row.get('Candidate_Bias')) is not None else 'NA'}"
        ),
        current_starts=_integer(row.get("OOS_Starts")), required_starts=CAL_V2_MIN_OOS_STARTS,
        current_days=_integer(row.get("Evidence_Days")), required_days=CAL_V2_MIN_EVIDENCE_DAYS,
        breadth_label="PITCHERS", current_breadth=_integer(row.get("Distinct_Pitchers")), required_breadth=CAL_V2_MIN_DISTINCT_PITCHERS,
        secondary=f"eligible_future={_integer(row.get('Eligible_Future_Starts')) or 0}; future_only={_clean(row.get('Future_Only_Start'))}",
        ready=status == "HELPING",
        action="MANUAL_RESEARCH_REVIEW_ONLY" if status == "HELPING" else "KEEP_COMMON_MODE_V2_FROZEN_AND_LEARN",
        reason="Frozen future-only post-blend common-mode challenger; source status controls the verdict and automatic activation remains forbidden.",
        authority=authority, source_version=_clean(row.get("Audit_Version")),
    )


def _ml_challenger_lane(data_dir: Path) -> dict[str, object]:
    filename = "ml_shadow_summary.csv"
    source = f"data/{filename}"
    frame = _read(data_dir, filename)
    if frame.empty:
        return _missing("ML Challenger", "ML", source)
    challenger = frame.get("Challenger", pd.Series(index=frame.index, dtype=str)).astype(str)
    primary = frame.loc[challenger.eq("ML_SHADOW")]
    row = (primary if not primary.empty else frame.head(1)).iloc[0]
    report_only, authority = _source_contract(row)
    equal = frame.loc[challenger.eq("SIM_MATH_ML_EQUAL_THIRDS")]
    equal_status = _clean(equal.iloc[0].get("Status")) if not equal.empty else "NA"
    return _base_row(
        lane="ML Challenger", category="ML", source_path=source, status=_clean(row.get("Status")),
        direction=(
            f"relative_mae={_pct(row.get('Relative_MAE_Improvement'), signed=True)}; "
            f"win_share={_pct(row.get('Candidate_Win_Share'))}; "
            f"existing_bias={_number(row.get('Existing_Bias')) if _number(row.get('Existing_Bias')) is not None else 'NA'}; "
            f"candidate_bias={_number(row.get('Candidate_Bias')) if _number(row.get('Candidate_Bias')) is not None else 'NA'}"
        ),
        current_starts=_integer(row.get("OOS_Starts")), breadth_label="OOS STARTS",
        secondary=(
            f"equal_thirds_status={equal_status}; live_projection_use={_clean(row.get('Live_Projection_Use'))}; "
            f"market_features_used={_clean(row.get('Market_Features_Used'))}"
        ),
        ready=False, action="PRESERVE_NEGATIVE_ML_EVIDENCE_NO_PROMOTION",
        reason=_clean(row.get("Reason")) or "Native ML shadow verdict; challenger remains report-only.",
        report_only=report_only, authority=authority, source_version=_clean(row.get("Validation_Version")),
    )


def _workload_v25_lane(data_dir: Path) -> dict[str, object]:
    filename = "workload_promotion_decisions.csv"
    source = f"data/{filename}"
    decisions = _read(data_dir, filename)
    if decisions.empty:
        return _missing("Workload v2.5 Candidates", "WORKLOAD", source)

    work = decisions.copy()
    work["_metric"] = work.get("Metric", pd.Series(index=work.index, dtype=str)).fillna("").astype(str).str.upper()
    metric_order = {"PITCHES": 0, "BF": 1, "OUTS": 2}
    work["_metric_order"] = work["_metric"].map(metric_order).fillna(99)
    work = work.sort_values(["_metric_order", "_metric"]).reset_index(drop=True)

    source_decisions = [_clean(value).upper() for value in work.get("Decision", pd.Series(dtype=str)) if _clean(value)]
    decision_rank = {"PROMOTE": 0, "HOLD": 1, "REJECT": 2}
    unique_decisions = sorted(set(source_decisions), key=lambda value: (decision_rank.get(value, 99), value))
    status = " / ".join(unique_decisions) if unique_decisions else "UNKNOWN"

    signals: list[str] = []
    passing: list[str] = []
    better: list[str] = []
    for _, row in work.iterrows():
        metric = _clean(row.get("Metric")).upper() or "UNKNOWN"
        decision = _clean(row.get("Decision")).upper() or "UNKNOWN"
        version = _clean(row.get("Recommended_Version")) or "NONE"
        signals.append(f"{metric}:{decision} {version} pooled_relative_mae={_pct(row.get('Pooled_Relative_MAE'), signed=True)}")
        passing.append(f"{metric}={_integer(row.get('Passing_Seasons')) or 0}/{_integer(row.get('Required_Seasons')) or 0}")
        better.append(f"{metric}={_integer(row.get('MAE_Better_Seasons')) or 0}")

    report_values = work.get("Report_Only", pd.Series(True, index=work.index)).map(_truthy)
    report_only = bool(report_values.all()) if not report_values.empty else REPORT_ONLY
    authority_values = sorted({_clean(value).upper() for value in work.get("Production_Authority", pd.Series(dtype=str)) if _clean(value)})
    authority = authority_values[0] if len(authority_values) == 1 else " / ".join(authority_values)
    ready = "PROMOTE" in unique_decisions
    source_versions = sorted({_clean(value) for value in work.get("Report_Version", pd.Series(dtype=str)) if _clean(value)})

    return _base_row(
        lane="Workload v2.5 Candidates", category="WORKLOAD", source_path=source, status=status,
        direction="; ".join(signals),
        breadth_label="METRICS", current_breadth=int(len(work)), required_breadth=3,
        secondary="passing_seasons=" + ",".join(passing) + "; mae_better_seasons=" + ",".join(better),
        ready=ready,
        action="MANUAL_RESEARCH_REVIEW_ONLY" if ready else "PRESERVE_WORKLOAD_PROMOTION_DECISIONS_REPORT_ONLY",
        reason=(
            "Authoritative cross-season workload promotion decisions are displayed without regrading; "
            "every metric remains report-only and any PROMOTE decision opens manual review only."
        ),
        report_only=report_only,
        authority=authority or PRODUCTION_AUTHORITY,
        source_version=" / ".join(source_versions),
    )

def build_promotion_command_center(data_dir: Path | str = "data") -> pd.DataFrame:
    root = Path(data_dir)
    base = build_command_center(root).copy()
    extra = pd.DataFrame([
        _crusher_lane(root),
        _underperformer_lane(root),
        _ladder_lane(root),
        _input_quality_lane(root, "STRIKEOUTS"),
        _input_quality_lane(root, "HITS"),
        _input_quality_lane(root, "OUTS"),
        _calibration_common_mode_lane(root),
        _ml_challenger_lane(root),
        _workload_v25_lane(root),
    ], columns=COLUMNS)
    extra_names = set(extra["Lane"].astype(str))
    if not base.empty:
        base = base.loc[~base["Lane"].astype(str).isin(extra_names)].copy()
    rows = base.to_dict("records") + extra.to_dict("records")
    center = pd.DataFrame(rows, columns=COLUMNS)
    return apply_promotion_governance(center, root)


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

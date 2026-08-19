from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

import pandas as pd

VERSION = "research-evidence-command-center-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True
LOCKED_PROMOTION_SCOREBOARD_CARDS = 8

COLUMNS = [
    "Lane",
    "Category",
    "Source_Path",
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
    "Command_Center_Version",
]

SUMMARY_COLUMNS = [
    "Total_Lanes",
    "Learning_Lanes",
    "Review_Ready_Lanes",
    "Failing_Lanes",
    "Source_Missing_Lanes",
    "All_Report_Only",
    "All_Production_Authority_None",
    "No_Auto_Promotion",
    "Locked_Promotion_Scoreboard_Cards",
    "Command_Center_Version",
]


def _clean(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _number(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _integer(value: object) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def _remaining(current: int | None, required: int | None) -> int | None:
    if current is None or required is None:
        return None
    return max(0, required - current)


def _pct(value: object, digits: int = 2) -> str:
    number = _number(value)
    if number is None:
        return "NA"
    return f"{number * 100:+.{digits}f}%"


def _ratio(value: object, digits: int = 1) -> str:
    number = _number(value)
    if number is None:
        return "NA"
    return f"{number * 100:.{digits}f}%"


def _read(data_dir: Path, filename: str) -> pd.DataFrame:
    path = data_dir / filename
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def _first(frame: pd.DataFrame) -> pd.Series:
    return frame.iloc[0] if frame is not None and not frame.empty else pd.Series(dtype=object)


def _source_contract(row: pd.Series) -> tuple[bool, str]:
    report_only = _truthy(row.get("Report_Only", row.get("Report Only", True)))
    authority = _clean(row.get("Production_Authority", row.get("Production Authority", ""))) or PRODUCTION_AUTHORITY
    return report_only, authority


def _base(
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
    report_only: bool = True,
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
    return _base(
        lane=lane,
        category=category,
        source_path=source_path,
        status="SOURCE_MISSING",
        reason="Authoritative evidence source is not present; command center does not reconstruct it.",
        action="RESTORE_OR_REFRESH_EXISTING_EVIDENCE_SOURCE",
    )


def _asymmetric(data_dir: Path) -> dict[str, object]:
    source = "data/opponent_matchup_asymmetric_response_shadow_gate.csv"
    row = _first(_read(data_dir, Path(source).name))
    if row.empty:
        return _missing("Opponent Asymmetric Challenger", "OPPONENT", source)
    report_only, authority = _source_contract(row)
    return _base(
        lane="Opponent Asymmetric Challenger",
        category="OPPONENT",
        source_path=source,
        status=_clean(row.get("Finding")),
        direction=_clean(row.get("Early_Read")),
        current_starts=_integer(row.get("Forward_Starts")),
        required_starts=60,
        current_days=_integer(row.get("Forward_Days")),
        required_days=10,
        breadth_label="OPPONENTS",
        current_breadth=_integer(row.get("Forward_Opponents")),
        required_breadth=15,
        secondary=(
            f"changed={_integer(row.get('Forward_Changed_Starts')) or 0}; "
            f"boost_capped={_integer(row.get('Forward_Boost_Capped_Starts')) or 0}/15; "
            f"weak_reduce_neutralized={_integer(row.get('Forward_Weak_Reduce_Neutralized_Starts')) or 0}/15"
        ),
        ready=_truthy(row.get("Manual_Review_Ready")),
        action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")),
        report_only=report_only,
        authority=authority,
        source_version=_clean(row.get("Validation_Version")),
    )


def _forward_summary_lane(
    data_dir: Path,
    *,
    lane: str,
    source_name: str,
    metric_col: str,
    win_col: str,
    required_starts: int,
    required_days: int,
    required_opponents: int,
) -> dict[str, object]:
    source = f"data/{source_name}"
    frame = _read(data_dir, source_name)
    if frame.empty:
        return _missing(lane, "OPPONENT", source)
    if "Evidence_Lane" in frame.columns:
        selected = frame.loc[frame["Evidence_Lane"].astype(str).eq("FORWARD_OOS")]
        row = _first(selected if not selected.empty else frame.tail(1))
    else:
        row = _first(frame.tail(1))
    report_only, authority = _source_contract(row)
    direction = f"relative_mae={_pct(row.get(metric_col))}; win_share={_ratio(row.get(win_col))}"
    return _base(
        lane=lane,
        category="OPPONENT",
        source_path=source,
        status=_clean(row.get("Evidence_Status")),
        direction=direction,
        current_starts=_integer(row.get("Starts")),
        required_starts=required_starts,
        current_days=_integer(row.get("Observed_Days")),
        required_days=required_days,
        breadth_label="OPPONENTS",
        current_breadth=_integer(row.get("Distinct_Opponents")),
        required_breadth=required_opponents,
        action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")),
        report_only=report_only,
        authority=authority,
        source_version=_clean(row.get("Validation_Version")),
    )


def _confirmed_lineup(data_dir: Path) -> dict[str, object]:
    source = "data/lineup_k_walkforward_gate.csv"
    row = _first(_read(data_dir, Path(source).name))
    if row.empty:
        return _missing("Confirmed Lineup", "LINEUP", source)
    report_only, authority = _source_contract(row)
    return _base(
        lane="Confirmed Lineup",
        category="LINEUP",
        source_path=source,
        status=_clean(row.get("Evidence_Status")),
        direction=(
            f"relative_mae={_pct(row.get('Relative_MAE_Improvement'))}; "
            f"win_share={_ratio(row.get('Confirmed_Win_Share'))}"
        ),
        current_starts=_integer(row.get("OOS_Paired_Starts")),
        required_starts=30,
        current_days=_integer(row.get("Observed_Days")),
        required_days=10,
        breadth_label="OPPONENTS",
        current_breadth=_integer(row.get("Distinct_Opponents")),
        required_breadth=8,
        secondary=f"authentic_pairs={_integer(row.get('Authentic_Pregame_Pairs')) or 0}",
        ready=_truthy(row.get("Manual_Review_Ready")),
        action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")),
        report_only=report_only,
        authority=authority,
        source_version=_clean(row.get("Validation_Version")),
    )


def _lineup_materiality(data_dir: Path) -> dict[str, object]:
    source = "data/lineup_materiality_shadow_gate.csv"
    row = _first(_read(data_dir, Path(source).name))
    if row.empty:
        return _missing("Lineup Materiality Shadow", "LINEUP", source)
    report_only, authority = _source_contract(row)
    return _base(
        lane="Lineup Materiality Shadow",
        category="LINEUP",
        source_path=source,
        status=_clean(row.get("Finding")),
        direction=_clean(row.get("Early_Read")),
        current_starts=_integer(row.get("Forward_Pairs")),
        required_starts=30,
        current_days=_integer(row.get("Forward_Days")),
        required_days=10,
        breadth_label="OPPONENTS",
        current_breadth=_integer(row.get("Forward_Opponents")),
        required_breadth=12,
        secondary=f"immaterial_changed_pairs={_integer(row.get('Forward_Changed_Pairs')) or 0}/20",
        ready=_truthy(row.get("Manual_Review_Ready")),
        action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")),
        report_only=report_only,
        authority=authority,
        source_version=_clean(row.get("Validation_Version")),
    )


def _handedness(data_dir: Path) -> dict[str, object]:
    source = "data/handedness_matchup_audit_gate.csv"
    row = _first(_read(data_dir, Path(source).name))
    if row.empty:
        return _missing("Handedness Matchup Audit", "MATCHUP", source)
    report_only, authority = _source_contract(row)
    return _base(
        lane="Handedness Matchup Audit",
        category="MATCHUP",
        source_path=source,
        status=_clean(row.get("Finding")),
        direction=_clean(row.get("Early_Read")),
        current_starts=_integer(row.get("Auditable_Starts")),
        required_starts=60,
        current_days=_integer(row.get("Observed_Days")),
        required_days=10,
        breadth_label="OPPONENTS",
        current_breadth=_integer(row.get("Distinct_Opponents")),
        required_breadth=15,
        secondary=(
            f"RHP={_integer(row.get('RHP_Starts')) or 0}/35; "
            f"LHP={_integer(row.get('LHP_Starts')) or 0}/15"
        ),
        action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")),
        report_only=report_only,
        authority=authority,
        source_version=_clean(row.get("Validation_Version")),
    )


def _pitch_mix(data_dir: Path) -> dict[str, object]:
    source = "data/pitch_mix_whiff_forward_gate.csv"
    row = _first(_read(data_dir, Path(source).name))
    if row.empty:
        return _missing("Pitch-Mix Whiff Forward", "PITCH_MIX", source)
    report_only, authority = _source_contract(row)
    return _base(
        lane="Pitch-Mix Whiff Forward",
        category="PITCH_MIX",
        source_path=source,
        status=_clean(row.get("Status")),
        direction=_clean(row.get("Primary_Metric")),
        current_starts=_integer(row.get("Resolved_Starts")),
        required_starts=_integer(row.get("Required_Starts")),
        current_days=_integer(row.get("Resolved_Days")),
        required_days=_integer(row.get("Required_Days")),
        breadth_label="OPPONENTS",
        current_breadth=_integer(row.get("Opponents")),
        required_breadth=_integer(row.get("Required_Opponents")),
        ready=_clean(row.get("Status")) == "READY_FOR_MANUAL_RESEARCH_REVIEW",
        action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")),
        report_only=report_only,
        authority=authority,
        source_version=_clean(row.get("Evaluation_Version")),
    )


def _umpire(data_dir: Path) -> dict[str, object]:
    source = "data/umpire_k_live_validation_gate.csv"
    row = _first(_read(data_dir, Path(source).name))
    if row.empty:
        return _missing("Umpire Context", "CONTEXT", source)
    report_only, authority = _source_contract(row)
    return _base(
        lane="Umpire Context",
        category="CONTEXT",
        source_path=source,
        status=_clean(row.get("Evidence_Status")),
        direction=(
            f"relative_mae={_pct(row.get('Relative_MAE_Improvement'))}; "
            f"win_share={_ratio(row.get('Candidate_Win_Share'))}"
        ),
        current_starts=_integer(row.get("OOS_Eligible_Starts")),
        required_starts=30,
        current_days=_integer(row.get("Observed_Days")),
        required_days=10,
        breadth_label="UMPIRES",
        current_breadth=_integer(row.get("Distinct_Umpires")),
        required_breadth=8,
        ready=_truthy(row.get("Manual_Review_Ready")),
        action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")),
        report_only=report_only,
        authority=authority,
        source_version=_clean(row.get("Validation_Version")),
    )


def _umpire_k_up_cap(data_dir: Path) -> dict[str, object]:
    source = "data/umpire_k_up_cap_shadow_summary.csv"
    frame = _read(data_dir, Path(source).name)
    if frame.empty:
        return _missing("Umpire K-UP Cap Shadow", "CONTEXT", source)
    if "Evidence_Lane" in frame.columns:
        selected = frame.loc[frame["Evidence_Lane"].astype(str).eq("FORWARD_OOS")]
        row = _first(selected if not selected.empty else frame.tail(1))
    else:
        row = _first(frame.tail(1))
    report_only, authority = _source_contract(row)
    return _base(
        lane="Umpire K-UP Cap Shadow",
        category="CONTEXT",
        source_path=source,
        status=_clean(row.get("Evidence_Status")),
        direction=(
            f"relative_mae={_pct(row.get('Capped_Relative_MAE_vs_Incumbent'))}; "
            f"win_share={_ratio(row.get('Capped_Win_Share_vs_Incumbent'))}"
        ),
        current_starts=_integer(row.get("Changed_Starts")),
        required_starts=30,
        current_days=_integer(row.get("Observed_Days")),
        required_days=10,
        breadth_label="UMPIRES",
        current_breadth=_integer(row.get("Distinct_Umpires")),
        required_breadth=12,
        secondary=(
            f"eligible_starts={_integer(row.get('Eligible_Starts')) or 0}; "
            f"frozen_max_factor={_number(row.get('Frozen_Max_K_Up_Factor')) if _number(row.get('Frozen_Max_K_Up_Factor')) is not None else 'NA'}"
        ),
        ready=_truthy(row.get("Manual_Review_Ready")),
        action=_clean(row.get("Recommended_Action")),
        reason=_clean(row.get("Reason")),
        report_only=report_only,
        authority=authority,
        source_version=_clean(row.get("Validation_Version")),
    )


def _catcher(data_dir: Path) -> dict[str, object]:
    source = "data/catcher_context_validation_gate.csv"
    row = _first(_read(data_dir, Path(source).name))
    if row.empty:
        return _missing("Catcher Context", "CONTEXT", source)
    report_only, authority = _source_contract(row)
    metric = _number(row.get("Relative_MAE_Improvement"))
    direction = "NO_AUDITABLE_METRIC_YET" if metric is None else f"relative_mae={_pct(metric)}"

    secondary_parts = [f"authentic_pregame_resolved={_integer(row.get('Authentic_Pregame_Resolved')) or 0}"]
    maturity = _first(_read(data_dir, "catcher_prior_maturity_summary.csv"))
    if not maturity.empty:
        maturity_report_only, maturity_authority = _source_contract(maturity)
        if maturity_report_only and maturity_authority.upper() == PRODUCTION_AUTHORITY:
            secondary_parts.extend([
                f"resolved_pool={_integer(maturity.get('Known_Resolved_Catchers')) or 0} catchers/{_integer(maturity.get('Resolved_Context_Starts')) or 0} starts",
                f"next_appearance_ready={_integer(maturity.get('Next_Appearance_Ready_No_Auditable_Yet')) or 0}",
                f"near_ready_3_4={_integer(maturity.get('Near_Ready_3_4')) or 0}",
            ])
        else:
            secondary_parts.append("maturity_context=CONTROL_BLOCKED")

    return _base(
        lane="Catcher Context",
        category="CONTEXT",
        source_path=source,
        status=_clean(row.get("Evidence_Status")),
        direction=direction,
        current_starts=_integer(row.get("Auditable_Starts")),
        required_starts=30,
        current_days=_integer(row.get("Observed_Days")),
        required_days=10,
        breadth_label="CATCHERS",
        current_breadth=_integer(row.get("Distinct_Catchers")),
        required_breadth=8,
        secondary="; ".join(secondary_parts),
        action="KEEP_LEARNING" if not _truthy(row.get("Recommended_Activation")) else "MANUAL_REVIEW_SOURCE_GATE",
        reason=_clean(row.get("Reason")),
        report_only=report_only,
        authority=authority,
        source_version=_clean(row.get("Validation_Version")),
    )


def _calibration(data_dir: Path) -> dict[str, object]:
    source = "data/calibration_shadow_gate.csv"
    frame = _read(data_dir, Path(source).name)
    if frame.empty:
        return _missing("Calibration Shadow", "CALIBRATION", source)
    statuses = frame.get("Promotion_Gate_Status", pd.Series(dtype=object)).fillna("").astype(str)
    fail_count = int(statuses.eq("FAIL").sum())
    pass_count = int(statuses.eq("PASS").sum())
    total = int(len(frame))
    starts = _integer(pd.to_numeric(frame.get("OOS_Starts"), errors="coerce").max()) if "OOS_Starts" in frame else None
    return _base(
        lane="Calibration Shadow",
        category="CALIBRATION",
        source_path=source,
        status="FAIL" if fail_count else ("PASS" if pass_count == total and total else "MIXED"),
        direction=f"milestones_pass={pass_count}/{total}; milestones_fail={fail_count}/{total}",
        current_starts=starts,
        secondary="; ".join(
            f"{_clean(row.get('Milestone'))}:{_clean(row.get('Promotion_Gate_Status'))}"
            for _, row in frame.iterrows()
        ),
        ready=False,
        action="KEEP_CALIBRATION_SHADOW_REPORT_ONLY",
        reason="; ".join(sorted({_clean(value) for value in frame.get("Reasons", pd.Series(dtype=object)) if _clean(value)})),
        report_only=True,
        authority=PRODUCTION_AUTHORITY,
        source_version=_clean(frame.get("Gate_Version", pd.Series(dtype=object)).iloc[0]) if "Gate_Version" in frame else "",
    )


def _starter_role(data_dir: Path) -> dict[str, object]:
    source = "data/live_role_shadow_gate.csv"
    frame = _read(data_dir, Path(source).name)
    if frame.empty:
        return _missing("Starter Role Live Shadow", "WORKLOAD", source)
    status_values = sorted({_clean(value) for value in frame.get("Live_Gate_Status", pd.Series(dtype=object)) if _clean(value)})
    relative = pd.to_numeric(frame.get("Relative_MAE"), errors="coerce") if "Relative_MAE" in frame else pd.Series(dtype=float)
    resolved_by_role = []
    if {"Role", "Resolved_Starts"}.issubset(frame.columns):
        for role, group in frame.groupby("Role"):
            value = pd.to_numeric(group["Resolved_Starts"], errors="coerce").max()
            resolved_by_role.append(f"{role}={int(value) if pd.notna(value) else 0}")
    max_resolved = _integer(pd.to_numeric(frame.get("Resolved_Starts"), errors="coerce").max()) if "Resolved_Starts" in frame else None
    direction = "NO_LIVE_METRIC_YET"
    if relative.notna().any():
        direction = f"relative_mae_range={relative.min():+.4f}..{relative.max():+.4f}"
    return _base(
        lane="Starter Role Live Shadow",
        category="WORKLOAD",
        source_path=source,
        status="/".join(status_values) or "UNKNOWN",
        direction=direction,
        current_starts=max_resolved,
        secondary="; ".join(resolved_by_role),
        ready=False,
        action="KEEP_LIVE_ROLE_SHADOW_REPORT_ONLY",
        reason="; ".join(sorted({_clean(value) for value in frame.get("Reasons", pd.Series(dtype=object)) if _clean(value)})),
        report_only=True,
        authority=PRODUCTION_AUTHORITY,
        source_version=_clean(frame.get("Gate_Version", pd.Series(dtype=object)).iloc[0]) if "Gate_Version" in frame else "",
    )


def _top_plays(data_dir: Path) -> dict[str, object]:
    source = "data/top_plays_accountability_summary.csv"
    frame = _read(data_dir, Path(source).name)
    if frame.empty:
        return _missing("Top Plays Accountability", "EXECUTION", source)
    selected = frame.loc[
        frame.get("Dimension", pd.Series(index=frame.index, dtype=object)).astype(str).eq("OVERALL")
        & frame.get("Segment", pd.Series(index=frame.index, dtype=object)).astype(str).eq("ALL REAL-LINE TOP PLAYS")
    ]
    row = _first(selected if not selected.empty else frame.head(1))
    report_only, authority = _source_contract(row)
    return _base(
        lane="Top Plays Accountability",
        category="EXECUTION",
        source_path=source,
        status=_clean(row.get("Evidence")),
        direction=(
            f"hit_rate={_ratio(row.get('Hit Rate'))}; "
            f"calibration_gap={_pct(row.get('Calibration Gap'))}; "
            f"brier={_number(row.get('Brier Score')) if _number(row.get('Brier Score')) is not None else 'NA'}"
        ),
        current_starts=_integer(row.get("Settled Legs")),
        required_starts=20,
        current_days=_integer(row.get("Observed Days")),
        action="KEEP_TOP_PLAYS_ACCOUNTABILITY_LEARNING",
        reason=_clean(row.get("Reason")),
        report_only=report_only,
        authority=authority,
        source_version=_clean(row.get("Accountability Version")),
    )


ADAPTERS: tuple[Callable[[Path], dict[str, object]], ...] = (
    _asymmetric,
    lambda data_dir: _forward_summary_lane(
        data_dir,
        lane="Opponent BOOST Cap Shadow",
        source_name="opponent_matchup_boost_cap_shadow_summary.csv",
        metric_col="Capped_Relative_MAE_vs_Applied",
        win_col="Capped_Win_Share_vs_Applied",
        required_starts=30,
        required_days=10,
        required_opponents=12,
    ),
    lambda data_dir: _forward_summary_lane(
        data_dir,
        lane="Weak-REDUCE Neutralization Shadow",
        source_name="opponent_matchup_weak_reduce_neutral_shadow_summary.csv",
        metric_col="Neutralized_Relative_MAE_vs_Applied",
        win_col="Neutralized_Win_Share_vs_Applied",
        required_starts=30,
        required_days=10,
        required_opponents=12,
    ),
    _confirmed_lineup,
    _lineup_materiality,
    _handedness,
    _pitch_mix,
    _umpire,
    _umpire_k_up_cap,
    _catcher,
    _calibration,
    _starter_role,
    _top_plays,
)


def build_command_center(data_dir: Path | str = "data") -> pd.DataFrame:
    root = Path(data_dir)
    rows = [adapter(root) for adapter in ADAPTERS]
    return pd.DataFrame(rows, columns=COLUMNS)


def build_summary(command_center: pd.DataFrame) -> pd.DataFrame:
    frame = command_center.copy() if command_center is not None else pd.DataFrame(columns=COLUMNS)
    statuses = frame.get("Status", pd.Series(dtype=object)).fillna("").astype(str)
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
        "Locked_Promotion_Scoreboard_Cards": LOCKED_PROMOTION_SCOREBOARD_CARDS,
        "Command_Center_Version": VERSION,
    }], columns=SUMMARY_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the report-only research evidence command center.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default="data/research_evidence_command_center.csv")
    parser.add_argument("--summary-output", default="data/research_evidence_command_center_summary.csv")
    args = parser.parse_args()

    command_center = build_command_center(args.data_dir)
    summary = build_summary(command_center)
    output = Path(args.output)
    summary_output = Path(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    command_center.to_csv(output, index=False)
    summary.to_csv(summary_output, index=False)
    print(command_center.to_string(index=False))
    print(summary.to_string(index=False))
    print(
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"no_auto_promotion={NO_AUTO_PROMOTION} locked_scoreboard_cards={LOCKED_PROMOTION_SCOREBOARD_CARDS}"
    )


if __name__ == "__main__":
    main()

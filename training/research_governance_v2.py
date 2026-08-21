from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "research-governance-v2-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True
AUTOMATIC_DECISION_ALLOWED = False
GOVERNANCE_EFFECTIVE_DATE = "2026-08-21"
BOOTSTRAP_SAMPLES = 1000
BOOTSTRAP_SEED = 9000

CALIBRATION_MIN_DAYS = 10
CALIBRATION_MIN_PITCHERS = 20
STARTER_ROLE_MIN_DAYS_PER_CELL = 10
STARTER_ROLE_MIN_PITCHERS_PER_CELL = 12
TOP_PLAYS_MIN_DAYS = 5
ML_MIN_DAYS = 10
ML_MIN_PITCHERS = 20
ML_MIN_OPPONENTS = 15

REQUIRED_ROLE_CELLS = tuple(
    (role, metric)
    for role in ("RAMPING", "LOW_RECENT_EXPOSURE")
    for metric in ("PITCHES", "BF", "OUTS")
)

MANIFEST_COLUMNS = [
    "Lane",
    "Category",
    "Research_Family",
    "Sibling_Lanes",
    "Hypothesis_ID",
    "Primary_Endpoint",
    "Source_Path",
    "Source_Version",
    "Source_Fingerprint",
    "Forward_Start_Date",
    "Freeze_At_UTC",
    "Source_Code_SHA",
    "Freeze_Metadata_Status",
    "Governance_Effective_Date",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Governance_Version",
]

UNCERTAINTY_COLUMNS = [
    "Lane",
    "Segment",
    "Metric",
    "Estimate",
    "CI_Low_95",
    "CI_High_95",
    "Observations",
    "Date_Blocks",
    "Method",
    "Report_Only",
    "Production_Authority",
    "Governance_Version",
]

SUMMARY_COLUMNS = [
    "Total_Lanes",
    "Review_Ready_Lanes",
    "Governance_Blocked_Lanes",
    "Control_Blocked_Lanes",
    "Manifest_Lanes",
    "Uncertainty_Rows",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Governance_Version",
]

PRIMARY_ENDPOINTS = {
    "Opponent Asymmetric Challenger": "changed-start relative MAE + win share versus incumbent",
    "Opponent BOOST Cap Shadow": "changed-start relative MAE + win share versus incumbent",
    "Weak-REDUCE Neutralization Shadow": "changed-start relative MAE + win share versus incumbent",
    "Confirmed Lineup": "OOS paired strikeout-projection MAE + win share",
    "Lineup Materiality Shadow": "changed-pair relative MAE versus confirmed-lineup incumbent",
    "Handedness Matchup Audit": "RHP/LHP projection residual consistency",
    "Pitch-Mix Whiff Forward": "frozen whiff-score association with strikeout residual",
    "Umpire Context": "OOS strikeout-projection MAE + win share",
    "Umpire K-UP Cap Shadow": "changed-start relative MAE + win share versus incumbent",
    "Catcher Context": "auditable OOS strikeout-projection MAE",
    "Calibration Shadow": "milestone Brier improvement with calibration-gap and win-share guardrails",
    "Starter Role Live Shadow": "role-by-metric MAE improvement with win-share and bias guardrails",
    "Top Plays Accountability": "settled authentic-line hit rate, calibration, Brier, and Wilson support",
    "Projection Crusher Shadow": "exact frozen-projection positive strikeout residual",
    "Projection Underperformer Shadow": "exact frozen-projection negative strikeout residual",
    "K Ladder Reliability Shadow": "model milestone hit-rate calibration and Brier reliability",
    "Input Quality v2 · Strikeouts": "matched deep-versus-shallow strikeout MAE",
    "Input Quality v2 · Hits": "matched deep-versus-shallow hits MAE",
    "Input Quality v2 · Outs": "matched deep-versus-shallow outs MAE",
    "Calibration Common-Mode v2": "future-only post-blend strikeout MAE + win share + bias",
    "ML Challenger": "walk-forward strikeout MAE + win share + bias versus incumbent",
    "Workload v2.5 Candidates": "cross-season workload MAE + win share + bias promotion gates",
}

FAMILY_BY_LANE = {
    "Opponent Asymmetric Challenger": "OPPONENT_RESPONSE",
    "Opponent BOOST Cap Shadow": "OPPONENT_RESPONSE",
    "Weak-REDUCE Neutralization Shadow": "OPPONENT_RESPONSE",
    "Confirmed Lineup": "LINEUP",
    "Lineup Materiality Shadow": "LINEUP",
    "Handedness Matchup Audit": "HANDEDNESS",
    "Pitch-Mix Whiff Forward": "PITCH_MIX",
    "Umpire Context": "UMPIRE",
    "Umpire K-UP Cap Shadow": "UMPIRE",
    "Catcher Context": "CATCHER",
    "Calibration Shadow": "CALIBRATION",
    "Calibration Common-Mode v2": "CALIBRATION",
    "Starter Role Live Shadow": "STARTER_ROLE",
    "Top Plays Accountability": "TOP_PLAYS",
    "Projection Crusher Shadow": "EXACT_K_RESIDUAL",
    "Projection Underperformer Shadow": "EXACT_K_RESIDUAL",
    "K Ladder Reliability Shadow": "K_LADDER",
    "Input Quality v2 · Strikeouts": "INPUT_QUALITY",
    "Input Quality v2 · Hits": "INPUT_QUALITY",
    "Input Quality v2 · Outs": "INPUT_QUALITY",
    "ML Challenger": "ML",
    "Workload v2.5 Candidates": "WORKLOAD",
}


def _clean(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"true", "1", "yes", "y"}


def _number(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _integer(value: object) -> int | None:
    value = _number(value)
    return None if value is None else int(value)


def _read(data_dir: Path, filename: str) -> pd.DataFrame:
    path = data_dir / filename
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def _distinct(frame: pd.DataFrame, column: str) -> int | None:
    if frame is None or frame.empty or column not in frame.columns:
        return None
    values = frame[column].dropna().astype(str).str.strip()
    values = values.loc[values.ne("") & values.str.lower().ne("nan")]
    return int(values.nunique()) if not values.empty else 0


def _observed_days(frame: pd.DataFrame, column: str = "game_date") -> int | None:
    if frame is None or frame.empty or column not in frame.columns:
        return None
    dates = pd.to_datetime(frame[column], errors="coerce", utc=True).dt.normalize().dropna()
    return int(dates.nunique()) if not dates.empty else 0


def _append_secondary(existing: object, token: str) -> str:
    current = _clean(existing)
    return f"{current}; {token}" if current else token


def _set_progress(
    frame: pd.DataFrame,
    index: object,
    *,
    current_days: int | None = None,
    required_days: int | None = None,
    breadth_label: str | None = None,
    current_breadth: int | None = None,
    required_breadth: int | None = None,
) -> None:
    if required_days is not None:
        frame.at[index, "Required_Days"] = required_days
        frame.at[index, "Current_Days"] = current_days
        frame.at[index, "Days_Remaining"] = (
            None if current_days is None else max(0, required_days - current_days)
        )
    if required_breadth is not None:
        frame.at[index, "Breadth_Label"] = breadth_label or "BREADTH"
        frame.at[index, "Required_Breadth"] = required_breadth
        frame.at[index, "Current_Breadth"] = current_breadth
        frame.at[index, "Breadth_Remaining"] = (
            None if current_breadth is None else max(0, required_breadth - current_breadth)
        )


def _mature(current: int | None, required: int) -> bool:
    return current is not None and current >= required


def _source_review_candidate(lane: str, status: str, existing_ready: bool) -> bool:
    normalized = status.upper().strip()
    if lane == "Calibration Shadow":
        return normalized == "PASS"
    if lane == "Starter Role Live Shadow":
        return normalized == "PASS"
    if lane == "Top Plays Accountability":
        return normalized in {"SUPPORTED", "STRONG EVIDENCE"}
    if lane == "ML Challenger":
        return normalized == "HELPING"
    return existing_ready


def _lane_breadth(lane: str, data_dir: Path, row: pd.Series) -> tuple[bool, str, dict[str, object]]:
    if lane == "Calibration Shadow":
        detail = _read(data_dir, "calibration_shadow_detail.csv")
        days = _observed_days(detail)
        pitchers = _distinct(detail, "pitcher_id")
        mature = _mature(days, CALIBRATION_MIN_DAYS) and _mature(pitchers, CALIBRATION_MIN_PITCHERS)
        return mature, f"governance_v2_days={days if days is not None else 'NA'}/{CALIBRATION_MIN_DAYS}; governance_v2_pitchers={pitchers if pitchers is not None else 'NA'}/{CALIBRATION_MIN_PITCHERS}", {
            "current_days": days,
            "required_days": CALIBRATION_MIN_DAYS,
            "breadth_label": "PITCHERS",
            "current_breadth": pitchers,
            "required_breadth": CALIBRATION_MIN_PITCHERS,
        }

    if lane == "Starter Role Live Shadow":
        detail = _read(data_dir, "live_role_shadow_detail.csv")
        day_counts: list[int] = []
        pitcher_counts: list[int] = []
        complete = True
        for role, metric in REQUIRED_ROLE_CELLS:
            if detail.empty or not {"Role", "Metric"}.issubset(detail.columns):
                complete = False
                continue
            selected = detail.loc[
                detail["Role"].astype(str).eq(role)
                & detail["Metric"].astype(str).str.upper().eq(metric)
            ]
            if selected.empty:
                complete = False
                continue
            days = _observed_days(selected)
            pitchers = _distinct(selected, "pitcher_id")
            if days is None or pitchers is None:
                complete = False
                continue
            day_counts.append(days)
            pitcher_counts.append(pitchers)
        min_days = min(day_counts) if complete and len(day_counts) == len(REQUIRED_ROLE_CELLS) else None
        min_pitchers = min(pitcher_counts) if complete and len(pitcher_counts) == len(REQUIRED_ROLE_CELLS) else None
        mature = _mature(min_days, STARTER_ROLE_MIN_DAYS_PER_CELL) and _mature(min_pitchers, STARTER_ROLE_MIN_PITCHERS_PER_CELL)
        return mature, f"governance_v2_min_cell_days={min_days if min_days is not None else 'NA'}/{STARTER_ROLE_MIN_DAYS_PER_CELL}; governance_v2_min_cell_pitchers={min_pitchers if min_pitchers is not None else 'NA'}/{STARTER_ROLE_MIN_PITCHERS_PER_CELL}", {
            "current_days": min_days,
            "required_days": STARTER_ROLE_MIN_DAYS_PER_CELL,
            "breadth_label": "PITCHERS / CELL",
            "current_breadth": min_pitchers,
            "required_breadth": STARTER_ROLE_MIN_PITCHERS_PER_CELL,
        }

    if lane == "Top Plays Accountability":
        days = _integer(row.get("Current_Days"))
        mature = _mature(days, TOP_PLAYS_MIN_DAYS)
        return mature, f"governance_v2_real_line_days={days if days is not None else 'NA'}/{TOP_PLAYS_MIN_DAYS}", {
            "current_days": days,
            "required_days": TOP_PLAYS_MIN_DAYS,
        }

    if lane == "ML Challenger":
        detail = _read(data_dir, "ml_shadow_detail.csv")
        if not detail.empty:
            eligible = detail.get("OOS_Eligible", pd.Series(False, index=detail.index)).map(_truthy)
            projection = pd.to_numeric(detail.get("ML_Shadow_Projection"), errors="coerce")
            detail = detail.loc[eligible & projection.notna()].copy()
        days = _observed_days(detail)
        pitchers = _distinct(detail, "pitcher_id")
        opponents = _distinct(detail, "opponent")
        mature = (
            _mature(days, ML_MIN_DAYS)
            and _mature(pitchers, ML_MIN_PITCHERS)
            and _mature(opponents, ML_MIN_OPPONENTS)
        )
        return mature, f"governance_v2_days={days if days is not None else 'NA'}/{ML_MIN_DAYS}; governance_v2_pitchers={pitchers if pitchers is not None else 'NA'}/{ML_MIN_PITCHERS}; governance_v2_opponents={opponents if opponents is not None else 'NA'}/{ML_MIN_OPPONENTS}", {
            "current_days": days,
            "required_days": ML_MIN_DAYS,
            "breadth_label": "PITCHERS",
            "current_breadth": pitchers,
            "required_breadth": ML_MIN_PITCHERS,
        }

    return True, "", {}


def apply_promotion_governance(command_center: pd.DataFrame, data_dir: Path | str = "data") -> pd.DataFrame:
    """Apply report-only governance to review readiness without regrading source verdicts."""
    if command_center is None or command_center.empty:
        return pd.DataFrame() if command_center is None else command_center.copy()

    root = Path(data_dir)
    frame = command_center.copy()
    governed_lanes = {"Calibration Shadow", "Starter Role Live Shadow", "Top Plays Accountability", "ML Challenger"}

    for index, row in frame.iterrows():
        lane = _clean(row.get("Lane"))
        status = _clean(row.get("Status"))
        source_ready = _source_review_candidate(lane, status, _truthy(row.get("Ready_For_Manual_Review")))
        breadth_ready, progress, progress_fields = _lane_breadth(lane, root, row)
        if progress_fields:
            _set_progress(frame, index, **progress_fields)
            frame.at[index, "Secondary_Progress"] = _append_secondary(row.get("Secondary_Progress"), progress)

        source_path = _clean(row.get("Source_Path"))
        source_version = _clean(row.get("Source_Version"))
        source_exists = bool(source_path) and (root / Path(source_path).name).exists()
        controls_ok = (
            _truthy(row.get("Report_Only"))
            and _clean(row.get("Production_Authority")).upper() == PRODUCTION_AUTHORITY
            and _truthy(row.get("No_Auto_Promotion"))
            and source_exists
            and bool(source_version)
        )

        ready = bool(source_ready and breadth_ready and controls_ok)
        frame.at[index, "Ready_For_Manual_Review"] = ready

        if source_ready and not controls_ok:
            frame.at[index, "Recommended_Action"] = "RESTORE_RESEARCH_CONTROL_METADATA_BEFORE_MANUAL_REVIEW"
        elif lane in governed_lanes and source_ready and not breadth_ready:
            frame.at[index, "Recommended_Action"] = "COLLECT_GOVERNANCE_V2_BREADTH_BEFORE_MANUAL_REVIEW"
        elif lane in governed_lanes and ready:
            frame.at[index, "Recommended_Action"] = "MANUAL_RESEARCH_REVIEW_ONLY"

    return frame


def _research_family(lane: str, category: str) -> str:
    return FAMILY_BY_LANE.get(lane, category or "UNCLASSIFIED")


def _forward_start(secondary: object) -> str:
    match = re.search(r"future_only=(\d{4}-\d{2}-\d{2})", _clean(secondary))
    return match.group(1) if match else ""


def _hypothesis_id(row: pd.Series) -> str:
    payload = "|".join([
        _clean(row.get("Lane")),
        _clean(row.get("Source_Path")),
        _clean(row.get("Source_Version")),
    ])
    return "hyp-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _source_fingerprint(row: pd.Series, endpoint: str) -> str:
    fields = [
        _clean(row.get("Lane")),
        _clean(row.get("Category")),
        _clean(row.get("Source_Path")),
        _clean(row.get("Source_Version")),
        _clean(row.get("Required_Starts")),
        _clean(row.get("Required_Days")),
        _clean(row.get("Breadth_Label")),
        _clean(row.get("Required_Breadth")),
        endpoint,
    ]
    return hashlib.sha256("|".join(fields).encode("utf-8")).hexdigest()


def build_hypothesis_manifest(command_center: pd.DataFrame) -> pd.DataFrame:
    if command_center is None or command_center.empty:
        return pd.DataFrame(columns=MANIFEST_COLUMNS)
    frame = command_center.copy()
    family_by_lane = {
        _clean(row.get("Lane")): _research_family(_clean(row.get("Lane")), _clean(row.get("Category")))
        for _, row in frame.iterrows()
    }
    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        lane = _clean(row.get("Lane"))
        category = _clean(row.get("Category"))
        family = family_by_lane.get(lane, category or "UNCLASSIFIED")
        siblings = sorted(name for name, other_family in family_by_lane.items() if other_family == family and name != lane)
        source_version = _clean(row.get("Source_Version"))
        endpoint = PRIMARY_ENDPOINTS.get(lane, "source-owned primary research endpoint")
        rows.append({
            "Lane": lane,
            "Category": category,
            "Research_Family": family,
            "Sibling_Lanes": ";".join(siblings),
            "Hypothesis_ID": _hypothesis_id(row),
            "Primary_Endpoint": endpoint,
            "Source_Path": _clean(row.get("Source_Path")),
            "Source_Version": source_version,
            "Source_Fingerprint": _source_fingerprint(row, endpoint),
            "Forward_Start_Date": _forward_start(row.get("Secondary_Progress")),
            "Freeze_At_UTC": "",
            "Source_Code_SHA": "",
            "Freeze_Metadata_Status": "SOURCE_VERSION_PINNED" if source_version else "LEGACY_METADATA_INCOMPLETE",
            "Governance_Effective_Date": GOVERNANCE_EFFECTIVE_DATE,
            "Report_Only": True,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "No_Auto_Promotion": True,
            "Governance_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=MANIFEST_COLUMNS)


def _stable_seed(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return BOOTSTRAP_SEED + (int(digest[:8], 16) % 100_000)


def _date_block_interval(
    frame: pd.DataFrame,
    *,
    date_col: str,
    value_col: str,
    token: str,
) -> tuple[float | None, float | None, float | None, int, int]:
    if frame is None or frame.empty or date_col not in frame.columns or value_col not in frame.columns:
        return None, None, None, 0, 0
    work = frame.copy()
    work["_date"] = pd.to_datetime(work[date_col], errors="coerce", utc=True).dt.normalize()
    work["_value"] = pd.to_numeric(work[value_col], errors="coerce")
    work = work.dropna(subset=["_date", "_value"])
    if work.empty:
        return None, None, None, 0, 0
    estimate = float(work["_value"].mean())
    blocks = [group["_value"].to_numpy(float) for _, group in work.groupby("_date", sort=True)]
    block_count = len(blocks)
    if block_count < 2:
        return estimate, None, None, int(len(work)), block_count
    rng = np.random.default_rng(_stable_seed(token))
    samples = np.empty(BOOTSTRAP_SAMPLES, dtype=float)
    for pos in range(BOOTSTRAP_SAMPLES):
        chosen = rng.integers(0, block_count, size=block_count)
        values = np.concatenate([blocks[index] for index in chosen])
        samples[pos] = float(values.mean())
    low, high = np.quantile(samples, [0.025, 0.975])
    return estimate, float(low), float(high), int(len(work)), block_count


def _uncertainty_row(
    lane: str,
    segment: str,
    metric: str,
    stats: tuple[float | None, float | None, float | None, int, int],
    method: str = "game-date block bootstrap; 1000 deterministic resamples",
) -> dict[str, object]:
    estimate, low, high, observations, blocks = stats
    return {
        "Lane": lane,
        "Segment": segment,
        "Metric": metric,
        "Estimate": estimate,
        "CI_Low_95": low,
        "CI_High_95": high,
        "Observations": observations,
        "Date_Blocks": blocks,
        "Method": method,
        "Report_Only": True,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Governance_Version": VERSION,
    }


def build_uncertainty_report(data_dir: Path | str = "data") -> pd.DataFrame:
    root = Path(data_dir)
    rows: list[dict[str, object]] = []

    calibration = _read(root, "calibration_shadow_detail.csv")
    if not calibration.empty and {"Baseline_Brier", "Candidate_Brier"}.issubset(calibration.columns):
        calibration = calibration.copy()
        calibration["_improvement"] = pd.to_numeric(calibration["Baseline_Brier"], errors="coerce") - pd.to_numeric(calibration["Candidate_Brier"], errors="coerce")
        for milestone, group in calibration.groupby("Milestone", dropna=False):
            token = f"Calibration Shadow|{milestone}|brier"
            rows.append(_uncertainty_row(
                "Calibration Shadow",
                f"Milestone {milestone}",
                "Baseline_Brier_minus_Candidate_Brier",
                _date_block_interval(group, date_col="game_date", value_col="_improvement", token=token),
            ))

    starter = _read(root, "live_role_shadow_detail.csv")
    if not starter.empty and {"Baseline_Error", "Candidate_Error", "Role", "Metric"}.issubset(starter.columns):
        starter = starter.copy()
        starter["_improvement"] = pd.to_numeric(starter["Baseline_Error"], errors="coerce").abs() - pd.to_numeric(starter["Candidate_Error"], errors="coerce").abs()
        for (role, metric), group in starter.groupby(["Role", "Metric"], dropna=False):
            token = f"Starter Role Live Shadow|{role}|{metric}|mae"
            rows.append(_uncertainty_row(
                "Starter Role Live Shadow",
                str(role),
                f"{metric}_Absolute_Error_Improvement",
                _date_block_interval(group, date_col="game_date", value_col="_improvement", token=token),
            ))

    ml = _read(root, "ml_shadow_detail.csv")
    if not ml.empty and {"Existing_Absolute_Error", "ML_Absolute_Error"}.issubset(ml.columns):
        eligible = ml.get("OOS_Eligible", pd.Series(False, index=ml.index)).map(_truthy)
        ml = ml.loc[eligible].copy()
        ml["_improvement"] = pd.to_numeric(ml["Existing_Absolute_Error"], errors="coerce") - pd.to_numeric(ml["ML_Absolute_Error"], errors="coerce")
        rows.append(_uncertainty_row(
            "ML Challenger",
            "ML_SHADOW",
            "Absolute_Error_Improvement",
            _date_block_interval(ml, date_col="game_date", value_col="_improvement", token="ML Challenger|ML_SHADOW|mae"),
        ))

    top = _read(root, "top_plays_postmortem_detail.csv")
    if not top.empty and "Hit" in top.columns:
        hit = pd.to_numeric(top["Hit"], errors="coerce")
        top = top.loc[hit.notna()].copy()
        top["_hit"] = hit.loc[hit.notna()].astype(float)
        date_col = "Postmortem Date" if "Postmortem Date" in top.columns else "game_date"
        rows.append(_uncertainty_row(
            "Top Plays Accountability",
            "ALL REAL-LINE TOP PLAYS",
            "Hit_Rate",
            _date_block_interval(top, date_col=date_col, value_col="_hit", token="Top Plays Accountability|overall|hit-rate"),
        ))

    return pd.DataFrame(rows, columns=UNCERTAINTY_COLUMNS)


def build_governance_summary(
    command_center: pd.DataFrame,
    manifest: pd.DataFrame,
    uncertainty: pd.DataFrame,
) -> pd.DataFrame:
    frame = command_center.copy() if command_center is not None else pd.DataFrame()
    if frame.empty:
        ready = governance_blocked = control_blocked = 0
    else:
        actions = frame.get("Recommended_Action", pd.Series(index=frame.index, dtype=object)).fillna("").astype(str)
        ready = int(frame.get("Ready_For_Manual_Review", pd.Series(False, index=frame.index)).map(_truthy).sum())
        governance_blocked = int(actions.eq("COLLECT_GOVERNANCE_V2_BREADTH_BEFORE_MANUAL_REVIEW").sum())
        control_blocked = int(actions.eq("RESTORE_RESEARCH_CONTROL_METADATA_BEFORE_MANUAL_REVIEW").sum())
    return pd.DataFrame([{
        "Total_Lanes": int(len(frame)),
        "Review_Ready_Lanes": ready,
        "Governance_Blocked_Lanes": governance_blocked,
        "Control_Blocked_Lanes": control_blocked,
        "Manifest_Lanes": int(len(manifest)) if manifest is not None else 0,
        "Uncertainty_Rows": int(len(uncertainty)) if uncertainty is not None else 0,
        "Report_Only": True,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Auto_Promotion": True,
        "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
        "Governance_Version": VERSION,
    }], columns=SUMMARY_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prospective report-only research governance v2 diagnostics.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--command-center", default="data/research_promotion_command_center.csv")
    parser.add_argument("--manifest-output", default="data/research_hypothesis_manifest.csv")
    parser.add_argument("--uncertainty-output", default="data/research_uncertainty_v2.csv")
    parser.add_argument("--summary-output", default="data/research_governance_v2_summary.csv")
    args = parser.parse_args()

    center_path = Path(args.command_center)
    center = pd.read_csv(center_path) if center_path.exists() else pd.DataFrame()
    governed = apply_promotion_governance(center, args.data_dir)
    manifest = build_hypothesis_manifest(governed)
    uncertainty = build_uncertainty_report(args.data_dir)
    summary = build_governance_summary(governed, manifest, uncertainty)

    for path_text, frame in (
        (args.manifest_output, manifest),
        (args.uncertainty_output, uncertainty),
        (args.summary_output, summary),
    ):
        path = Path(path_text)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    print(summary.to_string(index=False))
    print(
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"no_auto_promotion={NO_AUTO_PROMOTION} automatic_decision_allowed={AUTOMATIC_DECISION_ALLOWED} "
        f"governance_version={VERSION}"
    )


if __name__ == "__main__":
    main()

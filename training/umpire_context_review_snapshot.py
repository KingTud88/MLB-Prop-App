from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from training.umpire_k_live_validation import (
    BIAS_TOLERANCE,
    MIN_EVAL_DAYS,
    MIN_EVAL_STARTS,
    MIN_EVAL_UMPIRES,
)

VERSION = "umpire-context-review-snapshot-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True
AUTOMATIC_DECISION_ALLOWED = False

REVIEW_DIMENSIONS = (
    "OVERALL",
    "LINEAGE",
    "OUTCOME LINEAGE",
    "FACTOR DIRECTION",
    "FACTOR DELTA BAND",
    "PRIOR UMPIRE GAMES BAND",
    "QUALITY BAND",
    "STARTER HISTORY BAND",
)

SNAPSHOT_COLUMNS = [
    "Review_Dimension",
    "Dimension",
    "Segment",
    "Rows",
    "Authentic_Pregame_Candidates",
    "OOS_Eligible_Starts",
    "Observed_Days",
    "Distinct_Umpires",
    "Base_MAE",
    "UmpireCandidate_MAE",
    "Relative_MAE_Improvement",
    "Candidate_Win_Share",
    "Candidate_Loss_Share",
    "Base_Bias",
    "UmpireCandidate_Bias",
    "Bias_Absolute_Change",
    "Mean_Absolute_Factor_Delta",
    "Evidence",
    "Reason",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Source_Version",
    "Snapshot_Version",
]

SUMMARY_COLUMNS = [
    "Review_Status",
    "Source_Evidence_Status",
    "Source_Recommended_Action",
    "Minimum_Evaluation_Ready",
    "Source_Manual_Review_Ready",
    "OOS_Eligible_Starts",
    "Required_Starts",
    "Observed_Days",
    "Required_Days",
    "Distinct_Umpires",
    "Required_Umpires",
    "Base_MAE",
    "UmpireCandidate_MAE",
    "Relative_MAE_Improvement",
    "Candidate_Win_Share",
    "Candidate_Loss_Share",
    "Base_Bias",
    "UmpireCandidate_Bias",
    "Bias_Absolute_Change",
    "Bias_Guardrail_Passed",
    "Mean_Absolute_Factor_Delta",
    "Diagnostic_Segments",
    "Reason",
    "Recommended_Action",
    "Human_Review_Required",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Source_Version",
    "Snapshot_Version",
]


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _number(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _integer(value: object) -> int:
    number = _number(value)
    return 0 if number is None else int(number)


def _clean(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


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
    return bool(report_only.all() and authority.eq("NONE").all())


def minimum_evaluation_ready(gate_row: pd.Series) -> bool:
    return bool(
        _integer(gate_row.get("OOS_Eligible_Starts")) >= MIN_EVAL_STARTS
        and _integer(gate_row.get("Observed_Days")) >= MIN_EVAL_DAYS
        and _integer(gate_row.get("Distinct_Umpires")) >= MIN_EVAL_UMPIRES
    )


def _bias_guardrail(base_bias: object, candidate_bias: object) -> bool | None:
    base = _number(base_bias)
    candidate = _number(candidate_bias)
    if base is None or candidate is None:
        return None
    return abs(candidate) <= abs(base) + BIAS_TOLERANCE


def build_review_snapshot(segments: pd.DataFrame) -> pd.DataFrame:
    if segments is None or segments.empty:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)
    if not _source_contract_ok(segments):
        raise ValueError("Umpire-context segment source violates report-only production-authority contract.")

    selected = segments.loc[
        segments.get("Dimension", pd.Series(index=segments.index, dtype=object))
        .astype(str)
        .isin(REVIEW_DIMENSIONS)
    ].copy()

    review_dimension = {
        "OVERALL": "OVERALL",
        "LINEAGE": "LINEAGE_INTEGRITY",
        "OUTCOME LINEAGE": "LINEAGE_INTEGRITY",
        "FACTOR DIRECTION": "FACTOR_DIRECTION",
        "FACTOR DELTA BAND": "FACTOR_MAGNITUDE",
        "PRIOR UMPIRE GAMES BAND": "PRIOR_UMPIRE_SAMPLE",
        "QUALITY BAND": "DATA_QUALITY",
        "STARTER HISTORY BAND": "STARTER_HISTORY",
    }

    rows: list[dict[str, object]] = []
    for _, row in selected.iterrows():
        dimension = _clean(row.get("Dimension"))
        candidate_bias = _number(row.get("UmpireCandidate_Bias"))
        base_bias = _number(row.get("Base_Bias"))
        rows.append({
            "Review_Dimension": review_dimension.get(dimension, dimension),
            "Dimension": dimension,
            "Segment": row.get("Segment"),
            "Rows": row.get("Rows"),
            "Authentic_Pregame_Candidates": row.get("Authentic_Pregame_Candidates"),
            "OOS_Eligible_Starts": row.get("OOS_Eligible_Starts"),
            "Observed_Days": row.get("Observed_Days"),
            "Distinct_Umpires": row.get("Distinct_Umpires"),
            "Base_MAE": row.get("Base_MAE"),
            "UmpireCandidate_MAE": row.get("UmpireCandidate_MAE"),
            "Relative_MAE_Improvement": row.get("Relative_MAE_Improvement"),
            "Candidate_Win_Share": row.get("Candidate_Win_Share"),
            "Candidate_Loss_Share": row.get("Candidate_Loss_Share"),
            "Base_Bias": row.get("Base_Bias"),
            "UmpireCandidate_Bias": row.get("UmpireCandidate_Bias"),
            "Bias_Absolute_Change": (
                abs(candidate_bias) - abs(base_bias)
                if candidate_bias is not None and base_bias is not None
                else None
            ),
            "Mean_Absolute_Factor_Delta": row.get("Mean_Absolute_Factor_Delta"),
            "Evidence": row.get("Evidence"),
            "Reason": row.get("Reason"),
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "No_Auto_Promotion": NO_AUTO_PROMOTION,
            "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
            "Source_Version": row.get("Validation_Version"),
            "Snapshot_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)


def build_review_summary(gate: pd.DataFrame, snapshot: pd.DataFrame) -> pd.DataFrame:
    if gate is None or gate.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    if not _source_contract_ok(gate):
        raise ValueError("Umpire-context gate source violates report-only production-authority contract.")

    row = gate.iloc[0]
    minimum_ready = minimum_evaluation_ready(row)
    source_review_ready = _truthy(row.get("Manual_Review_Ready"))

    if source_review_ready:
        review_status = "PROMOTION_REVIEW_READY"
        action = "MANUAL_PROMOTION_REVIEW_ONLY"
        human_review = True
    elif minimum_ready:
        review_status = "MINIMUM_EVALUATION_REVIEW_REQUIRED"
        action = "REVIEW_FROZEN_UMPIRE_EVIDENCE_NO_AUTOMATIC_PROMOTION"
        human_review = True
    else:
        review_status = "LEARNING"
        action = "COLLECT_UNTIL_MINIMUM_EVALUATION"
        human_review = False

    base_bias = _number(row.get("Base_Bias"))
    candidate_bias = _number(row.get("UmpireCandidate_Bias"))
    bias_change = None if base_bias is None or candidate_bias is None else abs(candidate_bias) - abs(base_bias)

    reason = _clean(row.get("Reason"))
    if minimum_ready and not source_review_ready:
        reason = (
            f"{reason} Minimum evaluation volume is mature, so a human diagnostic review is required; "
            "the frozen source gate remains authoritative and no automatic promotion is allowed."
        )

    return pd.DataFrame([{
        "Review_Status": review_status,
        "Source_Evidence_Status": row.get("Evidence_Status"),
        "Source_Recommended_Action": row.get("Recommended_Action"),
        "Minimum_Evaluation_Ready": minimum_ready,
        "Source_Manual_Review_Ready": source_review_ready,
        "OOS_Eligible_Starts": _integer(row.get("OOS_Eligible_Starts")),
        "Required_Starts": MIN_EVAL_STARTS,
        "Observed_Days": _integer(row.get("Observed_Days")),
        "Required_Days": MIN_EVAL_DAYS,
        "Distinct_Umpires": _integer(row.get("Distinct_Umpires")),
        "Required_Umpires": MIN_EVAL_UMPIRES,
        "Base_MAE": row.get("Base_MAE"),
        "UmpireCandidate_MAE": row.get("UmpireCandidate_MAE"),
        "Relative_MAE_Improvement": row.get("Relative_MAE_Improvement"),
        "Candidate_Win_Share": row.get("Candidate_Win_Share"),
        "Candidate_Loss_Share": row.get("Candidate_Loss_Share"),
        "Base_Bias": row.get("Base_Bias"),
        "UmpireCandidate_Bias": row.get("UmpireCandidate_Bias"),
        "Bias_Absolute_Change": bias_change,
        "Bias_Guardrail_Passed": _bias_guardrail(base_bias, candidate_bias),
        "Mean_Absolute_Factor_Delta": row.get("Mean_Absolute_Factor_Delta"),
        "Diagnostic_Segments": int(len(snapshot)) if snapshot is not None else 0,
        "Reason": reason,
        "Recommended_Action": action,
        "Human_Review_Required": human_review,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
        "Source_Version": row.get("Validation_Version"),
        "Snapshot_Version": VERSION,
    }], columns=SUMMARY_COLUMNS)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a report-only Umpire Context minimum-evaluation and promotion-review snapshot."
    )
    parser.add_argument("--gate", default="data/umpire_k_live_validation_gate.csv")
    parser.add_argument("--segments", default="data/umpire_k_live_validation_segments.csv")
    parser.add_argument("--output", default="data/umpire_context_review_snapshot.csv")
    parser.add_argument("--summary-output", default="data/umpire_context_review_summary.csv")
    args = parser.parse_args()

    gate = _read_csv(Path(args.gate))
    segments = _read_csv(Path(args.segments))
    if gate.empty or segments.empty:
        raise SystemExit("Umpire-context gate and segment artifacts are required.")

    snapshot = build_review_snapshot(segments)
    summary = build_review_summary(gate, snapshot)

    output = Path(args.output)
    summary_output = Path(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    snapshot.to_csv(output, index=False)
    summary.to_csv(summary_output, index=False)

    print(summary.to_string(index=False))
    print(snapshot.to_string(index=False))
    print(
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"no_auto_promotion={NO_AUTO_PROMOTION} automatic_decision_allowed={AUTOMATIC_DECISION_ALLOWED}"
    )


if __name__ == "__main__":
    main()

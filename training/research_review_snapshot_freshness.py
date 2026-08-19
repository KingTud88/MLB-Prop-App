from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

import training.confirmed_lineup_review_snapshot as lineup_review
import training.umpire_context_review_snapshot as umpire_review

VERSION = "research-review-snapshot-freshness-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True
AUTOMATIC_DECISION_ALLOWED = False

CURRENT = "CURRENT"
SOURCE_MISSING = "SOURCE_MISSING"
DERIVED_MISSING = "DERIVED_MISSING"
DERIVED_DRIFT = "DERIVED_DRIFT"
CONTROL_VIOLATION = "CONTROL_VIOLATION"

DETAIL_COLUMNS = [
    "Review_Artifact",
    "Source_Gate",
    "Source_Segments",
    "Snapshot_Path",
    "Summary_Path",
    "Freshness_Status",
    "Snapshot_Rows",
    "Expected_Snapshot_Rows",
    "Mismatch_Items",
    "Detail",
    "Report_Only",
    "Production_Authority",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Freshness_Version",
]

SUMMARY_COLUMNS = [
    "Overall_Status",
    "Review_Artifacts",
    "Current_Artifacts",
    "Stale_Artifacts",
    "Missing_Artifacts",
    "Control_Violation_Artifacts",
    "All_Report_Only",
    "All_Production_Authority_None",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Freshness_Version",
]


@dataclass(frozen=True)
class ReviewSpec:
    name: str
    gate_path: str
    segments_path: str
    snapshot_path: str
    summary_path: str
    snapshot_columns: list[str]
    summary_columns: list[str]
    build_snapshot: Callable[[pd.DataFrame], pd.DataFrame]
    build_summary: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]


SPECS = (
    ReviewSpec(
        name="CONFIRMED_LINEUP_REVIEW",
        gate_path="lineup_k_walkforward_gate.csv",
        segments_path="lineup_k_walkforward_segments.csv",
        snapshot_path="confirmed_lineup_review_snapshot.csv",
        summary_path="confirmed_lineup_review_summary.csv",
        snapshot_columns=lineup_review.SNAPSHOT_COLUMNS,
        summary_columns=lineup_review.SUMMARY_COLUMNS,
        build_snapshot=lineup_review.build_review_snapshot,
        build_summary=lineup_review.build_review_summary,
    ),
    ReviewSpec(
        name="UMPIRE_CONTEXT_REVIEW",
        gate_path="umpire_k_live_validation_gate.csv",
        segments_path="umpire_k_live_validation_segments.csv",
        snapshot_path="umpire_context_review_snapshot.csv",
        summary_path="umpire_context_review_summary.csv",
        snapshot_columns=umpire_review.SNAPSHOT_COLUMNS,
        summary_columns=umpire_review.SUMMARY_COLUMNS,
        build_snapshot=umpire_review.build_review_snapshot,
        build_summary=umpire_review.build_review_summary,
    ),
)


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


def _normalized_number(number: float) -> int | float:
    rounded = round(float(number), 12)
    return int(rounded) if rounded.is_integer() else rounded


def _normalize(value: object) -> object:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _normalized_number(float(value))
    text = _clean(value)
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return _normalized_number(float(text))
    except ValueError:
        return text


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def _frame_signature(
    frame: pd.DataFrame,
    columns: list[str],
    sort_columns: list[str] | None = None,
) -> tuple[tuple[object, ...], ...]:
    if frame is None or frame.empty:
        return tuple()
    working = frame.copy()
    for column in columns:
        if column not in working.columns:
            working[column] = None
    if sort_columns:
        present = [column for column in sort_columns if column in working.columns]
        if present:
            working = working.sort_values(present, kind="stable", na_position="last")
    return tuple(
        tuple(_normalize(row.get(column)) for column in columns)
        for _, row in working[columns].iterrows()
    )


def _contract_violation(frame: pd.DataFrame) -> bool:
    if frame is None or frame.empty:
        return False
    report = frame.get("Report_Only", pd.Series(index=frame.index, dtype=object)).map(_truthy)
    authority = frame.get("Production_Authority", pd.Series(index=frame.index, dtype=object)).map(_clean).str.upper()
    no_auto = frame.get("No_Auto_Promotion", pd.Series(index=frame.index, dtype=object)).map(_truthy)
    automatic = frame.get("Automatic_Decision_Allowed", pd.Series(False, index=frame.index)).map(_truthy)
    return bool((~report | ~authority.eq("NONE") | ~no_auto | automatic).any())


def _detail_row(
    spec: ReviewSpec,
    status: str,
    snapshot_rows: int,
    expected_rows: int,
    mismatches: int,
    detail: str,
) -> dict[str, object]:
    return {
        "Review_Artifact": spec.name,
        "Source_Gate": f"data/{spec.gate_path}",
        "Source_Segments": f"data/{spec.segments_path}",
        "Snapshot_Path": f"data/{spec.snapshot_path}",
        "Summary_Path": f"data/{spec.summary_path}",
        "Freshness_Status": status,
        "Snapshot_Rows": snapshot_rows,
        "Expected_Snapshot_Rows": expected_rows,
        "Mismatch_Items": mismatches,
        "Detail": detail,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
        "Freshness_Version": VERSION,
    }


def _evaluate_spec(root: Path, spec: ReviewSpec) -> dict[str, object]:
    gate = _read_csv(root / spec.gate_path)
    segments = _read_csv(root / spec.segments_path)
    saved_snapshot = _read_csv(root / spec.snapshot_path)
    saved_summary = _read_csv(root / spec.summary_path)

    if gate.empty or segments.empty:
        missing = []
        if gate.empty:
            missing.append(spec.gate_path)
        if segments.empty:
            missing.append(spec.segments_path)
        return _detail_row(
            spec,
            SOURCE_MISSING,
            len(saved_snapshot),
            0,
            len(missing),
            "Required review source artifact(s) missing or unreadable: " + ", ".join(missing),
        )

    if saved_snapshot.empty or saved_summary.empty:
        missing = []
        if saved_snapshot.empty:
            missing.append(spec.snapshot_path)
        if saved_summary.empty:
            missing.append(spec.summary_path)
        return _detail_row(
            spec,
            DERIVED_MISSING,
            len(saved_snapshot),
            0,
            len(missing),
            "Derived review artifact(s) missing or unreadable: " + ", ".join(missing),
        )

    if _contract_violation(saved_snapshot) or _contract_violation(saved_summary):
        return _detail_row(
            spec,
            CONTROL_VIOLATION,
            len(saved_snapshot),
            len(saved_snapshot),
            1,
            "Saved review snapshot or summary violates the report-only/NONE/no-auto-decision contract.",
        )

    try:
        expected_snapshot = spec.build_snapshot(segments)
        expected_summary = spec.build_summary(gate, expected_snapshot)
    except ValueError as exc:
        return _detail_row(
            spec,
            CONTROL_VIOLATION,
            len(saved_snapshot),
            0,
            1,
            f"Authoritative review source violates its frozen source contract: {exc}",
        )

    snapshot_match = _frame_signature(
        saved_snapshot,
        spec.snapshot_columns,
        ["Review_Dimension", "Dimension", "Segment"],
    ) == _frame_signature(
        expected_snapshot,
        spec.snapshot_columns,
        ["Review_Dimension", "Dimension", "Segment"],
    )
    summary_match = _frame_signature(saved_summary, spec.summary_columns) == _frame_signature(
        expected_summary, spec.summary_columns
    )
    mismatches = int(not snapshot_match) + int(not summary_match)

    if mismatches:
        return _detail_row(
            spec,
            DERIVED_DRIFT,
            len(saved_snapshot),
            len(expected_snapshot),
            mismatches,
            "Saved review snapshot/summary does not exactly reproduce from the current frozen gate and segment sources.",
        )

    return _detail_row(
        spec,
        CURRENT,
        len(saved_snapshot),
        len(expected_snapshot),
        0,
        "Saved review snapshot and summary exactly reproduce from the current frozen gate and segment sources.",
    )


def build_review_snapshot_freshness(data_dir: Path | str = "data") -> pd.DataFrame:
    root = Path(data_dir)
    return pd.DataFrame([_evaluate_spec(root, spec) for spec in SPECS], columns=DETAIL_COLUMNS)


def build_freshness_summary(detail: pd.DataFrame) -> pd.DataFrame:
    frame = detail.copy() if detail is not None else pd.DataFrame(columns=DETAIL_COLUMNS)
    statuses = frame.get("Freshness_Status", pd.Series(dtype=object)).fillna("").astype(str)
    current = int(statuses.eq(CURRENT).sum())
    stale = int(statuses.eq(DERIVED_DRIFT).sum())
    missing = int(statuses.isin({SOURCE_MISSING, DERIVED_MISSING}).sum())
    violations = int(statuses.eq(CONTROL_VIOLATION).sum())

    if violations:
        overall = CONTROL_VIOLATION
    elif missing:
        overall = "INCOMPLETE"
    elif stale:
        overall = "STALE"
    else:
        overall = "HEALTHY"

    report = frame.get("Report_Only", pd.Series(dtype=object)).map(_truthy) if not frame.empty else pd.Series(dtype=bool)
    authority = frame.get("Production_Authority", pd.Series(dtype=object)).map(_clean).str.upper() if not frame.empty else pd.Series(dtype=object)

    return pd.DataFrame(
        [{
            "Overall_Status": overall,
            "Review_Artifacts": int(len(frame)),
            "Current_Artifacts": current,
            "Stale_Artifacts": stale,
            "Missing_Artifacts": missing,
            "Control_Violation_Artifacts": violations,
            "All_Report_Only": bool(report.all()) if not report.empty else True,
            "All_Production_Authority_None": bool(authority.eq("NONE").all()) if not authority.empty else True,
            "No_Auto_Promotion": NO_AUTO_PROMOTION,
            "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
            "Freshness_Version": VERSION,
        }],
        columns=SUMMARY_COLUMNS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Certify freshness of report-only human-review diagnostic snapshots by exact recomputation."
    )
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default="data/research_review_snapshot_freshness.csv")
    parser.add_argument("--summary-output", default="data/research_review_snapshot_freshness_summary.csv")
    args = parser.parse_args()

    detail = build_review_snapshot_freshness(args.data_dir)
    summary = build_freshness_summary(detail)
    output = Path(args.output)
    summary_output = Path(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(output, index=False)
    summary.to_csv(summary_output, index=False)

    print(detail.to_string(index=False))
    print(summary.to_string(index=False))
    print(
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"no_auto_promotion={NO_AUTO_PROMOTION} automatic_decision_allowed={AUTOMATIC_DECISION_ALLOWED} "
        f"freshness_version={VERSION}"
    )

    if summary.empty or str(summary.iloc[0]["Overall_Status"]) != "HEALTHY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

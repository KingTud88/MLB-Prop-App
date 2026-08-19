from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from training.research_manual_review_queue import (
    AUTOMATIC_DECISION_ALLOWED,
    DEFAULT_REVIEW_STATUS,
    NO_AUTO_PROMOTION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    build_queue_summary,
)

VERSION = "research-manual-review-decision-v1-manual-only"
ALLOWED_REVIEW_STATUSES = ("CLOSED_BY_HUMAN",)
MANUAL_FIELDS = ("Review_Status", "Reviewed_At_UTC", "Reviewer", "Review_Notes")


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


def _validate_target(row: pd.Series) -> None:
    if _clean(row.get("Review_Status")) != DEFAULT_REVIEW_STATUS:
        raise ValueError("manual review decision requires a pending review case")
    if _truthy(row.get("Control_Violation")):
        raise ValueError("refusing to close a control-violation review case")
    if not _truthy(row.get("Report_Only")):
        raise ValueError("refusing review decision: Report_Only must remain true")
    if _clean(row.get("Production_Authority")).upper() != PRODUCTION_AUTHORITY:
        raise ValueError("refusing review decision: Production_Authority must remain NONE")
    if not _truthy(row.get("No_Auto_Promotion")):
        raise ValueError("refusing review decision: No_Auto_Promotion must remain true")
    if _truthy(row.get("Automatic_Decision_Allowed")):
        raise ValueError("refusing review decision: automatic decisions must remain disabled")


def apply_manual_review_decision(
    queue: pd.DataFrame,
    *,
    case_id: str,
    reviewer: str,
    notes: str,
    reviewed_at_utc: str,
    review_status: str = "CLOSED_BY_HUMAN",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply an explicit human disposition to one pending report-only review case.

    This function only mutates the four manual review fields. It has no model,
    projection, promotion, or production authority.
    """
    case_id = _clean(case_id)
    reviewer = _clean(reviewer)
    notes = _clean(notes)
    reviewed_at_utc = _clean(reviewed_at_utc)
    review_status = _clean(review_status)

    if not case_id:
        raise ValueError("case_id is required")
    if not reviewer:
        raise ValueError("reviewer is required")
    if not notes:
        raise ValueError("review notes are required")
    if not reviewed_at_utc:
        raise ValueError("reviewed_at_utc is required")
    if review_status not in ALLOWED_REVIEW_STATUSES:
        raise ValueError(f"unsupported manual review status: {review_status}")
    if queue is None or queue.empty or "Review_Case_ID" not in queue.columns:
        raise ValueError("manual review queue is empty or missing Review_Case_ID")

    frame = queue.copy()
    matches = frame.index[frame["Review_Case_ID"].astype(str).eq(case_id)].tolist()
    if len(matches) != 1:
        raise ValueError(f"expected exactly one review case for {case_id}; found {len(matches)}")

    target_index = matches[0]
    _validate_target(frame.loc[target_index])

    immutable_columns = [column for column in frame.columns if column not in MANUAL_FIELDS]
    before = frame.loc[target_index, immutable_columns].copy()

    frame.at[target_index, "Review_Status"] = review_status
    frame.at[target_index, "Reviewed_At_UTC"] = reviewed_at_utc
    frame.at[target_index, "Reviewer"] = reviewer
    frame.at[target_index, "Review_Notes"] = notes

    after = frame.loc[target_index, immutable_columns]
    if not before.equals(after):
        raise RuntimeError("manual review decision attempted to mutate immutable review evidence")

    summary = build_queue_summary(frame, reviewed_at_utc)
    return frame, summary


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record one explicit human decision on an existing report-only research review case."
    )
    parser.add_argument("--queue", default="data/research_manual_review_queue.csv")
    parser.add_argument("--summary-output", default="data/research_manual_review_queue_summary.csv")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument("--review-status", default="CLOSED_BY_HUMAN", choices=ALLOWED_REVIEW_STATUSES)
    parser.add_argument("--reviewed-at-utc", default=None)
    args = parser.parse_args()

    reviewed_at = args.reviewed_at_utc or datetime.now(timezone.utc).isoformat()
    queue_path = Path(args.queue)
    queue = _read_csv(queue_path)
    decided, summary = apply_manual_review_decision(
        queue,
        case_id=args.case_id,
        reviewer=args.reviewer,
        notes=args.notes,
        reviewed_at_utc=reviewed_at,
        review_status=args.review_status,
    )

    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    decided.to_csv(queue_path, index=False)
    summary.to_csv(summary_path, index=False)

    row = decided.loc[decided["Review_Case_ID"].astype(str).eq(str(args.case_id))].iloc[0]
    print(
        f"review_case={row['Review_Case_ID']} lane={row.get('Lane')} "
        f"review_status={row['Review_Status']} reviewer={row['Reviewer']}"
    )
    print(summary.to_string(index=False))
    print(
        f"manual_only=true report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"no_auto_promotion={NO_AUTO_PROMOTION} automatic_decision_allowed={AUTOMATIC_DECISION_ALLOWED} "
        f"decision_version={VERSION}"
    )


if __name__ == "__main__":
    main()

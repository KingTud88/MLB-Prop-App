from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS

PROBABILITY_SEMANTICS = "milestone-ceil-v1"
LINEAGE_VERSION = "calibration-lineage-v1"
REQUIRED_BASE_COLUMNS = (
    "game_date",
    "captured_at_utc",
    "probability_semantics",
    "history_semantics",
    "actual_strikeouts",
)


def classify_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Classify projection-log rows for modern calibration eligibility.

    This guard intentionally does not repair or infer legacy lineage. A row is
    eligible only when it explicitly carries the frozen modern semantics, has a
    valid pregame capture timestamp/date, and has a resolved strikeout outcome.
    """
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["calibration_eligible", "calibration_exclusion_reason", "calibration_lineage_version"])

    out = frame.copy()
    for col in REQUIRED_BASE_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    game_date = pd.to_datetime(out["game_date"], errors="coerce", utc=True)
    captured = pd.to_datetime(out["captured_at_utc"], errors="coerce", utc=True)
    actual = pd.to_numeric(out["actual_strikeouts"], errors="coerce")
    probability_semantics = out["probability_semantics"].fillna("").astype(str)
    history_semantics = out["history_semantics"].fillna("").astype(str)

    reasons: list[str] = []
    eligible: list[bool] = []
    for idx in out.index:
        row_reasons: list[str] = []
        if pd.isna(game_date.loc[idx]):
            row_reasons.append("game_date")
        if pd.isna(captured.loc[idx]):
            row_reasons.append("capture_time")
        elif pd.notna(game_date.loc[idx]) and captured.loc[idx] >= game_date.loc[idx] + pd.Timedelta(days=1):
            # We cannot reconstruct first pitch from every legacy row, but a
            # capture on/after the next UTC day is certainly not a trustworthy
            # frozen pregame snapshot for calibration purposes.
            row_reasons.append("late_capture")
        if probability_semantics.loc[idx] != PROBABILITY_SEMANTICS:
            row_reasons.append("probability_semantics")
        if history_semantics.loc[idx] != HISTORY_SEMANTICS:
            row_reasons.append("history_semantics")
        if pd.isna(actual.loc[idx]):
            row_reasons.append("unresolved")
        eligible.append(not row_reasons)
        reasons.append("|".join(row_reasons))

    out["calibration_eligible"] = eligible
    out["calibration_exclusion_reason"] = reasons
    out["calibration_lineage_version"] = LINEAGE_VERSION
    return out


def eligible_rows(frame: pd.DataFrame) -> pd.DataFrame:
    classified = classify_rows(frame)
    if classified.empty:
        return classified
    return classified.loc[classified["calibration_eligible"].fillna(False)].copy()


def audit_summary(classified: pd.DataFrame) -> pd.DataFrame:
    if classified is None or classified.empty:
        return pd.DataFrame([
            {
                "Lineage_Version": LINEAGE_VERSION,
                "Total_Rows": 0,
                "Eligible_Rows": 0,
                "Excluded_Rows": 0,
                "Eligibility_Rate": 0.0,
                "Exclusion_Reason": "NONE",
                "Rows": 0,
            }
        ])

    total = int(len(classified))
    eligible_n = int(classified["calibration_eligible"].fillna(False).sum())
    rows: list[dict[str, object]] = []
    excluded = classified.loc[~classified["calibration_eligible"].fillna(False)]
    reason_counts: dict[str, int] = {}
    for value in excluded["calibration_exclusion_reason"].fillna("").astype(str):
        for reason in filter(None, value.split("|")):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    if not reason_counts:
        reason_counts = {"NONE": 0}
    for reason, count in sorted(reason_counts.items()):
        rows.append({
            "Lineage_Version": LINEAGE_VERSION,
            "Total_Rows": total,
            "Eligible_Rows": eligible_n,
            "Excluded_Rows": total - eligible_n,
            "Eligibility_Rate": float(eligible_n / total) if total else 0.0,
            "Exclusion_Reason": reason,
            "Rows": int(count),
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit projection-log rows eligible for modern calibration.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--audit", type=Path, default=Path("data/calibration_lineage_audit.csv"))
    args = parser.parse_args()

    frame = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    classified = classify_rows(frame)
    summary = audit_summary(classified)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.audit, index=False)
    print(summary.to_string(index=False))
    print(f"eligible={int(classified['calibration_eligible'].sum()) if not classified.empty else 0} total={len(classified)} lineage={LINEAGE_VERSION}")


if __name__ == "__main__":
    main()

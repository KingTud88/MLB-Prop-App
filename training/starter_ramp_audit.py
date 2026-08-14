from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

AUDIT_VERSION = "starter-ramp-coverage-v1-report-only"

# We intentionally audit what is already archived before inventing a model rule.
# These aliases cover the common names used by workload/start-history pipelines.
SIGNALS = {
    "days_rest": ("days_rest", "rest_days", "days_since_last_start"),
    "prior_start_pitches": ("prior_start_pitches", "last_start_pitches", "previous_start_pitches"),
    "recent_pitch_ceiling": ("recent_pitch_ceiling", "pitch_ceiling", "recent_max_pitches"),
    "recent_starts": ("recent_starts", "starts_last_30", "prior_start_count"),
    "opener_flag": ("opener_flag", "is_opener", "bulk_flag", "starter_role"),
    "restriction_flag": ("restriction_flag", "pitch_limit_flag", "ramp_up_flag", "returning_from_il"),
}


def _present(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").notna()
    text = series.fillna("").astype(str).str.strip().str.lower()
    return ~text.isin({"", "nan", "none", "null", "unknown"})


def build_report(frame: pd.DataFrame) -> pd.DataFrame:
    resolved = pd.to_numeric(frame.get("actual_strikeouts", pd.Series(index=frame.index, dtype=float)), errors="coerce").notna()
    rows: list[dict[str, object]] = []
    for signal, aliases in SIGNALS.items():
        found = [c for c in aliases if c in frame.columns]
        present = pd.Series(False, index=frame.index)
        for col in found:
            present |= _present(frame[col])
        n = int((resolved & present).sum())
        rows.append({
            "Signal": signal.upper(),
            "Columns_Found": "|".join(found),
            "Resolved_K_Starts": int(resolved.sum()),
            "Resolved_K_Starts_With_Signal": n,
            "Resolved_Coverage": float(n / resolved.sum()) if resolved.any() else 0.0,
            "Status": "AUDITABLE" if n >= 30 else "COLLECTING",
            "Audit_Version": AUDIT_VERSION,
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only starter ramp/restriction/opener coverage audit")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/starter_ramp_coverage_summary.csv"))
    args = parser.parse_args()
    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("No projection history available")
    report = build_report(history)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()

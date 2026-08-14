from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

AUDIT_VERSION = "environment-coverage-v1-report-only"
ENVIRONMENT_FIELDS = {
    "weather": ("weather_summary", "temperature", "wind_speed", "wind_mph", "humidity"),
    "umpire": ("umpire", "umpire_name", "home_plate_umpire", "umpire_k_factor", "umpire_modifier"),
    "park": ("park_factor", "park_k_factor", "venue", "venue_name"),
}


def _present(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").notna()
    text = series.fillna("").astype(str).str.strip().str.lower()
    return ~text.isin({"", "nan", "none", "null", "unknown"})


def coverage_report(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total = int(len(frame))
    resolved = frame.get("actual_strikeouts", pd.Series(index=frame.index, dtype=float)).notna()
    for group, candidates in ENVIRONMENT_FIELDS.items():
        found = [col for col in candidates if col in frame.columns]
        if found:
            present = pd.Series(False, index=frame.index)
            for col in found:
                present |= _present(frame[col])
        else:
            present = pd.Series(False, index=frame.index)
        rows.append({
            "Environment_Group": group.upper(),
            "Candidate_Columns_Found": "|".join(found),
            "Rows": total,
            "Rows_With_Context": int(present.sum()),
            "Coverage_Rate": float(present.mean()) if total else 0.0,
            "Resolved_K_Rows": int(resolved.sum()),
            "Resolved_K_Rows_With_Context": int((resolved & present).sum()),
            "Resolved_K_Coverage_Rate": float((resolved & present).sum() / resolved.sum()) if resolved.any() else 0.0,
            "Status": "AUDITABLE" if int((resolved & present).sum()) >= 20 else "COLLECTING",
            "Audit_Version": AUDIT_VERSION,
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only weather/umpire/park context coverage audit")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/environment_coverage_summary.csv"))
    args = parser.parse_args()
    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("No projection history available")
    report = coverage_report(history)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()

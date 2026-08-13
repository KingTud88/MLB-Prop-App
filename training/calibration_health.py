from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.calibration_lineage import eligible_rows

REPORT_VERSION = "calibration-health-v2"
MILESTONES = tuple(range(3, 11))
PATHS = ("SIM", "MATH")


def _probability_column(path: str, milestone: int) -> str:
    prefix = str(path).strip().lower()
    if prefix not in {"sim", "math"}:
        raise ValueError(f"Unsupported probability path: {path}")
    return f"{prefix}_{int(milestone)}p"


def build_report(frame: pd.DataFrame) -> pd.DataFrame:
    eligible = eligible_rows(frame)
    columns = [
        "Path", "Milestone", "Equivalent_Over_Line", "Source_Column",
        "Resolved_Starts", "Brier_Score", "Mean_Predicted_Probability",
        "Empirical_Hit_Rate", "Calibration_Gap", "Absolute_Calibration_Gap",
        "Report_Version",
    ]
    if eligible.empty:
        return pd.DataFrame(columns=columns)

    actual = pd.to_numeric(eligible.get("actual_strikeouts"), errors="coerce")
    rows: list[dict[str, object]] = []
    for milestone in MILESTONES:
        outcome = actual.ge(float(milestone)).astype(float)
        for path in PATHS:
            column = _probability_column(path, milestone)
            if column not in eligible.columns:
                continue
            probability = pd.to_numeric(eligible[column], errors="coerce")
            ready = actual.notna() & probability.notna()
            if not ready.any():
                continue
            p = probability[ready].astype(float).clip(0.0, 1.0)
            y = outcome[ready].astype(float)
            mean_p = float(p.mean())
            empirical = float(y.mean())
            gap = float(mean_p - empirical)
            rows.append({
                "Path": path,
                "Milestone": int(milestone),
                "Equivalent_Over_Line": float(milestone) - 0.5,
                "Source_Column": column,
                "Resolved_Starts": int(ready.sum()),
                "Brier_Score": float(np.mean(np.square(p.to_numpy() - y.to_numpy()))),
                "Mean_Predicted_Probability": mean_p,
                "Empirical_Hit_Rate": empirical,
                "Calibration_Gap": gap,
                "Absolute_Calibration_Gap": abs(gap),
                "Report_Version": REPORT_VERSION,
            })
    return pd.DataFrame(rows, columns=columns)


def main() -> None:
    parser = argparse.ArgumentParser(description="Descriptive calibration health from lineage-safe milestone probabilities only.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/calibration_health.csv"))
    args = parser.parse_args()
    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    report = build_report(history)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False) if not report.empty else "No lineage-safe resolved calibration rows yet")
    print(f"calibration_health_rows={len(report)} report={REPORT_VERSION}")


if __name__ == "__main__":
    main()

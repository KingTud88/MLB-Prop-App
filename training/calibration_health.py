from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.calibration_lineage import eligible_rows

REPORT_VERSION = "calibration-health-v1"
MILESTONES = (4.5, 5.5, 6.5, 7.5, 8.5)


def _probability_column(line: float) -> str:
    token = str(line).replace(".", "_")
    return f"sim_over_{token}"


def build_report(frame: pd.DataFrame) -> pd.DataFrame:
    eligible = eligible_rows(frame)
    if eligible.empty:
        return pd.DataFrame(columns=[
            "Line", "Resolved_Starts", "Brier_Score", "Mean_Predicted_Probability",
            "Empirical_Over_Rate", "Calibration_Gap", "Report_Version",
        ])

    actual = pd.to_numeric(eligible.get("actual_strikeouts"), errors="coerce")
    rows: list[dict[str, object]] = []
    for line in MILESTONES:
        column = _probability_column(line)
        if column not in eligible.columns:
            continue
        probability = pd.to_numeric(eligible[column], errors="coerce")
        ready = actual.notna() & probability.notna()
        if not ready.any():
            continue
        p = probability[ready].astype(float).clip(0.0, 1.0)
        y = actual[ready].astype(float).gt(float(line)).astype(float)
        mean_p = float(p.mean())
        empirical = float(y.mean())
        rows.append({
            "Line": float(line),
            "Resolved_Starts": int(ready.sum()),
            "Brier_Score": float(np.mean(np.square(p.to_numpy() - y.to_numpy()))),
            "Mean_Predicted_Probability": mean_p,
            "Empirical_Over_Rate": empirical,
            "Calibration_Gap": float(mean_p - empirical),
            "Report_Version": REPORT_VERSION,
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Descriptive calibration health from lineage-safe projection rows only.")
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

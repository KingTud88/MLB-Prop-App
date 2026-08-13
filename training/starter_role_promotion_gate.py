from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

# Promotion gate is deliberately stricter than the exploratory HELPING label.
# 2024 is treated as burn-in because the walk-forward candidate cannot adjust
# RAMPING until 30 strictly prior role observations exist. Promotion evidence
# must therefore hold in both fully eligible out-of-sample seasons, 2025/2026.
GATE_VERSION = "starter-role-promotion-gate-v1"
REQUIRED_SEASONS = (2025, 2026)
REQUIRED_ROLES = ("RAMPING", "LOW_RECENT_EXPOSURE")
REQUIRED_METRICS = ("PITCHES", "BF", "OUTS")
MIN_ADJUSTED_STARTS = 30
MIN_RELATIVE_MAE = 0.005
MIN_WIN_SHARE = 0.55


def evaluate(summary: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    rows: list[dict[str, object]] = []
    for season in REQUIRED_SEASONS:
        for role in REQUIRED_ROLES:
            for metric in REQUIRED_METRICS:
                match = summary.loc[
                    (pd.to_numeric(summary.get("Season"), errors="coerce") == season)
                    & summary.get("Role", pd.Series(index=summary.index, dtype=str)).astype(str).eq(role)
                    & summary.get("Metric", pd.Series(index=summary.index, dtype=str)).astype(str).eq(metric)
                ]
                reasons: list[str] = []
                if match.empty:
                    passed = False
                    reasons.append("missing_row")
                    adjusted = 0
                    relative = float("nan")
                    win = float("nan")
                    baseline_bias = candidate_bias = float("nan")
                else:
                    row = match.iloc[0]
                    adjusted = int(pd.to_numeric(pd.Series([row.get("Adjusted_Starts")]), errors="coerce").fillna(0).iloc[0])
                    relative = float(pd.to_numeric(pd.Series([row.get("Relative_MAE")]), errors="coerce").iloc[0])
                    win = float(pd.to_numeric(pd.Series([row.get("Win_Share")]), errors="coerce").iloc[0])
                    baseline_bias = float(pd.to_numeric(pd.Series([row.get("Baseline_Bias")]), errors="coerce").iloc[0])
                    candidate_bias = float(pd.to_numeric(pd.Series([row.get("Candidate_Bias")]), errors="coerce").iloc[0])
                    if adjusted < MIN_ADJUSTED_STARTS:
                        reasons.append("sample")
                    if not pd.notna(relative) or relative < MIN_RELATIVE_MAE:
                        reasons.append("mae")
                    if not pd.notna(win) or win < MIN_WIN_SHARE:
                        reasons.append("win_share")
                    if not pd.notna(baseline_bias) or not pd.notna(candidate_bias) or abs(candidate_bias) > abs(baseline_bias):
                        reasons.append("bias")
                    passed = not reasons
                rows.append({
                    "Season": season,
                    "Role": role,
                    "Metric": metric,
                    "Adjusted_Starts": adjusted,
                    "Relative_MAE": relative,
                    "Win_Share": win,
                    "Baseline_Bias": baseline_bias,
                    "Candidate_Bias": candidate_bias,
                    "Gate_Result": "PASS" if passed else "FAIL",
                    "Reasons": "|".join(reasons),
                    "Gate_Version": GATE_VERSION,
                })
    report = pd.DataFrame(rows)
    return report, bool(not report.empty and report["Gate_Result"].eq("PASS").all())


def main() -> None:
    parser = argparse.ArgumentParser(description="Strict promotion gate for starter-role workload candidate.")
    parser.add_argument("--summary", type=Path, default=Path("data/starter_role_candidate_summary.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/starter_role_promotion_gate.csv"))
    args = parser.parse_args()
    if not args.summary.exists():
        raise SystemExit("Starter-role candidate summary is missing")
    summary = pd.read_csv(args.summary)
    report, passed = evaluate(summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))
    print(f"promotion_gate={'PASS' if passed else 'FAIL'} gate={GATE_VERSION}")
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

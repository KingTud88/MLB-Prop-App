from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

GATE_VERSION = "calibration-shadow-gate-v1"
MILESTONES = tuple(range(3, 11))
MIN_OOS_STARTS = 30
MIN_RELATIVE_BRIER = 0.01
MIN_WIN_SHARE = 0.50


def _number(value: object) -> float:
    return float(pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0])


def evaluate(summary: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Evaluate shadow evidence only; this function has no activation authority."""
    rows: list[dict[str, object]] = []
    any_learning = False
    any_fail = False

    for milestone in MILESTONES:
        match = (
            summary.loc[pd.to_numeric(summary.get("Milestone"), errors="coerce").eq(milestone)]
            if summary is not None and not summary.empty and "Milestone" in summary.columns
            else pd.DataFrame()
        )
        reasons: list[str] = []
        if match.empty:
            oos = 0
            rel = base_gap = cand_gap = win = float("nan")
            status = "LEARNING"
            reasons.append("missing_shadow_cell")
            any_learning = True
        else:
            row = match.iloc[0]
            oos = int(pd.to_numeric(pd.Series([row.get("OOS_Starts")]), errors="coerce").fillna(0).iloc[0])
            rel = _number(row.get("Relative_Brier_Improvement"))
            base_gap = _number(row.get("Baseline_Calibration_Gap"))
            cand_gap = _number(row.get("Candidate_Calibration_Gap"))
            win = _number(row.get("Candidate_Win_Share"))

            if oos < MIN_OOS_STARTS:
                status = "LEARNING"
                reasons.append("oos_sample")
                any_learning = True
            else:
                if not pd.notna(rel) or rel < MIN_RELATIVE_BRIER:
                    reasons.append("brier")
                if not pd.notna(base_gap) or not pd.notna(cand_gap) or abs(cand_gap) > abs(base_gap):
                    reasons.append("calibration_gap")
                if not pd.notna(win) or win < MIN_WIN_SHARE:
                    reasons.append("win_share")
                status = "PASS" if not reasons else "FAIL"
                any_fail = any_fail or status == "FAIL"

        rows.append({
            "Milestone": int(milestone),
            "OOS_Starts": oos,
            "Relative_Brier_Improvement": rel,
            "Baseline_Calibration_Gap": base_gap,
            "Candidate_Calibration_Gap": cand_gap,
            "Candidate_Win_Share": win,
            "Promotion_Gate_Status": status,
            "Reasons": "|".join(reasons),
            "Gate_Version": GATE_VERSION,
        })

    report = pd.DataFrame(rows)
    overall = "FAIL" if any_fail else "LEARNING" if any_learning else "PASS"
    return report, overall


def _read_summary(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only promotion gate for strikeout calibration shadow evidence.")
    parser.add_argument("--summary", type=Path, default=Path("data/calibration_shadow_summary.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/calibration_shadow_gate.csv"))
    args = parser.parse_args()

    summary = _read_summary(args.summary)
    report, overall = evaluate(summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))
    print(f"calibration_shadow_gate={overall} gate={GATE_VERSION}")
    print("report_only=true production_activation=false")


if __name__ == "__main__":
    main()

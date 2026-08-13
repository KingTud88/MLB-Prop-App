from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

GATE_VERSION = "live-role-shadow-gate-v1"
REQUIRED_ROLES = ("RAMPING", "LOW_RECENT_EXPOSURE")
REQUIRED_METRICS = ("PITCHES", "BF", "OUTS")
MIN_RESOLVED_STARTS = 30
MIN_RELATIVE_MAE = 0.005
MIN_WIN_SHARE = 0.55


def evaluate(summary: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, object]] = []
    any_learning = False
    any_fail = False
    for role in REQUIRED_ROLES:
        for metric in REQUIRED_METRICS:
            match = summary.loc[
                summary.get("Role", pd.Series(index=summary.index, dtype=str)).astype(str).eq(role)
                & summary.get("Metric", pd.Series(index=summary.index, dtype=str)).astype(str).eq(metric)
            ] if summary is not None and not summary.empty else pd.DataFrame()
            reasons: list[str] = []
            if match.empty:
                status = "LEARNING"
                starts = 0
                rel = win = base_bias = cand_bias = float("nan")
                reasons.append("missing_live_cell")
                any_learning = True
            else:
                row = match.iloc[0]
                starts = int(pd.to_numeric(pd.Series([row.get("Resolved_Starts")]), errors="coerce").fillna(0).iloc[0])
                rel = float(pd.to_numeric(pd.Series([row.get("Relative_MAE")]), errors="coerce").iloc[0])
                win = float(pd.to_numeric(pd.Series([row.get("Candidate_Win_Share")]), errors="coerce").iloc[0])
                base_bias = float(pd.to_numeric(pd.Series([row.get("Baseline_Bias")]), errors="coerce").iloc[0])
                cand_bias = float(pd.to_numeric(pd.Series([row.get("Candidate_Bias")]), errors="coerce").iloc[0])
                if starts < MIN_RESOLVED_STARTS:
                    status = "LEARNING"
                    reasons.append("sample")
                    any_learning = True
                else:
                    if not pd.notna(rel) or rel < MIN_RELATIVE_MAE:
                        reasons.append("mae")
                    if not pd.notna(win) or win < MIN_WIN_SHARE:
                        reasons.append("win_share")
                    if not pd.notna(base_bias) or not pd.notna(cand_bias) or abs(cand_bias) > abs(base_bias):
                        reasons.append("bias")
                    status = "PASS" if not reasons else "FAIL"
                    any_fail = any_fail or status == "FAIL"
            rows.append({
                "Role": role,
                "Metric": metric,
                "Resolved_Starts": starts,
                "Relative_MAE": rel,
                "Candidate_Win_Share": win,
                "Baseline_Bias": base_bias,
                "Candidate_Bias": cand_bias,
                "Live_Gate_Status": status,
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
        # A report-only producer may intentionally emit a newline when there
        # are zero genuinely live resolved rows. Treat that as no evidence,
        # not as a pipeline failure; evaluate() will correctly return LEARNING.
        return pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Activation gate for genuinely live resolved role-shadow evidence.")
    parser.add_argument("--summary", type=Path, default=Path("data/live_role_shadow_summary.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/live_role_shadow_gate.csv"))
    args = parser.parse_args()
    summary = _read_summary(args.summary)
    report, overall = evaluate(summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))
    print(f"live_role_shadow_gate={overall} gate={GATE_VERSION}")


if __name__ == "__main__":
    main()

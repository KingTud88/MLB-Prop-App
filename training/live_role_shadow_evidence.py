from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SHADOW_VERSION = "starter-role-workload-v1"
SHADOW_MODE = "shadow"
METRICS = (
    ("pitches", "expected_pitches", "role_candidate_expected_pitches", "actual_pitches"),
    ("bf", "expected_bf", "role_candidate_expected_bf", "actual_batters_faced"),
    ("outs", "expected_outs", "role_candidate_expected_outs", "actual_outs"),
)
ELIGIBLE_ROLES = {"RAMPING", "LOW_RECENT_EXPOSURE"}


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def eligible_shadow_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.iloc[0:0].copy()
    version = frame.get("role_workload_version", pd.Series("", index=frame.index)).fillna("").astype(str)
    mode = frame.get("role_workload_mode", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
    role = frame.get("starter_role_label", pd.Series("", index=frame.index)).fillna("").astype(str)
    resolved = frame.get("resolved_at_utc", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip().ne("")
    mask = version.eq(SHADOW_VERSION) & mode.eq(SHADOW_MODE) & role.isin(ELIGIBLE_ROLES) & resolved
    return frame.loc[mask].copy()


def build_evidence(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = eligible_shadow_rows(frame)
    detail_rows: list[dict[str, object]] = []
    if work.empty:
        return pd.DataFrame(), pd.DataFrame()

    for idx, row in work.iterrows():
        role = str(row.get("starter_role_label", ""))
        for metric, base_col, cand_col, actual_col in METRICS:
            base = pd.to_numeric(pd.Series([row.get(base_col)]), errors="coerce").iloc[0]
            cand = pd.to_numeric(pd.Series([row.get(cand_col)]), errors="coerce").iloc[0]
            actual = pd.to_numeric(pd.Series([row.get(actual_col)]), errors="coerce").iloc[0]
            if pd.isna(base) or pd.isna(cand) or pd.isna(actual):
                continue
            base_err = float(base - actual)
            cand_err = float(cand - actual)
            detail_rows.append({
                "game_pk": row.get("game_pk"),
                "game_date": row.get("game_date"),
                "pitcher_id": row.get("pitcher_id"),
                "player": row.get("player"),
                "Role": role,
                "Metric": metric.upper(),
                "Baseline": float(base),
                "Candidate": float(cand),
                "Actual": float(actual),
                "Baseline_Error": base_err,
                "Candidate_Error": cand_err,
                "Candidate_Win": abs(cand_err) < abs(base_err),
                "Candidate_Tie": abs(cand_err) == abs(base_err),
                "Role_Workload_Version": SHADOW_VERSION,
            })

    detail = pd.DataFrame(detail_rows)
    if detail.empty:
        return detail, pd.DataFrame()

    summary_rows: list[dict[str, object]] = []
    for (role, metric), group in detail.groupby(["Role", "Metric"], dropna=False):
        base_abs = group["Baseline_Error"].abs()
        cand_abs = group["Candidate_Error"].abs()
        base_mae = float(base_abs.mean())
        cand_mae = float(cand_abs.mean())
        rel = float((base_mae - cand_mae) / base_mae) if base_mae > 0 else float("nan")
        summary_rows.append({
            "Role": role,
            "Metric": metric,
            "Resolved_Starts": int(len(group)),
            "Baseline_MAE": base_mae,
            "Candidate_MAE": cand_mae,
            "Relative_MAE": rel,
            "Baseline_Bias": float(group["Baseline_Error"].mean()),
            "Candidate_Bias": float(group["Candidate_Error"].mean()),
            "Candidate_Win_Share": float(group["Candidate_Win"].mean()),
            "Candidate_Tie_Share": float(group["Candidate_Tie"].mean()),
            "Role_Workload_Version": SHADOW_VERSION,
        })
    return detail, pd.DataFrame(summary_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score resolved live role-workload shadow projections only.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/live_role_shadow_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/live_role_shadow_summary.csv"))
    args = parser.parse_args()

    frame = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    detail, summary = build_evidence(frame)
    for path in (args.detail, args.summary):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    print(f"live_shadow_rows={len(detail)} summary_rows={len(summary)} version={SHADOW_VERSION}")
    if not summary.empty:
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

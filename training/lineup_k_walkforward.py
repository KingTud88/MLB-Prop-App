from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "lineup-k-walkforward-v1-report-only"
MIN_PRIOR_PAIRED = 20
MIN_OOS_PAIRED = 20
MIN_RELATIVE_MAE = 0.01


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(frame[col], errors="coerce") if col in frame.columns else pd.Series(np.nan, index=frame.index)


def _confirmed(frame: pd.DataFrame) -> pd.Series:
    raw = frame.get("lineup_confirmed", pd.Series(False, index=frame.index))
    return raw.fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})


def build_oos_detail(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    work["_date"] = pd.to_datetime(work.get("game_date"), errors="coerce").dt.normalize()
    pre = _num(work, "lineup_preconfirm_projection")
    post = _num(work, "projection")
    actual = _num(work, "actual_strikeouts")
    ready = _confirmed(work) & work["_date"].notna() & pre.notna() & post.notna() & actual.notna()
    work = work.loc[ready].copy()
    if work.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for game_date in sorted(work["_date"].drop_duplicates().tolist()):
        prior = work.loc[work["_date"].lt(game_date)]
        current = work.loc[work["_date"].eq(game_date)]
        prior_n = int(len(prior))
        eligible = prior_n >= MIN_PRIOR_PAIRED
        for idx, row in current.iterrows():
            pre_v = float(row["lineup_preconfirm_projection"])
            post_v = float(row["projection"])
            actual_v = float(row["actual_strikeouts"])
            rows.append({
                "game_date": pd.Timestamp(game_date).date().isoformat(),
                "game_pk": row.get("game_pk"),
                "pitcher_id": row.get("pitcher_id"),
                "player": row.get("player"),
                "Prior_Paired_Starts": prior_n,
                "OOS_Eligible": bool(eligible),
                "Preconfirm_Projection": pre_v,
                "Confirmed_Projection": post_v,
                "Actual_Strikeouts": actual_v,
                "Preconfirm_Absolute_Error": abs(pre_v - actual_v),
                "Confirmed_Absolute_Error": abs(post_v - actual_v),
                "Preconfirm_Error": pre_v - actual_v,
                "Confirmed_Error": post_v - actual_v,
                "Confirmed_Win": abs(post_v - actual_v) < abs(pre_v - actual_v),
                "Confirmed_Loss": abs(post_v - actual_v) > abs(pre_v - actual_v),
                "Validation_Version": VERSION,
            })
    return pd.DataFrame(rows)


def summarize_oos(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty:
        return pd.DataFrame([{
            "Metric": "STRIKEOUTS", "OOS_Paired_Starts": 0, "Status": "LEARNING", "Reason": "no_paired_rows", "Validation_Version": VERSION
        }])
    oos = detail.loc[detail["OOS_Eligible"].fillna(False).astype(bool)].copy()
    n = int(len(oos))
    if not n:
        return pd.DataFrame([{
            "Metric": "STRIKEOUTS", "OOS_Paired_Starts": 0, "Status": "LEARNING", "Reason": "prior_sample", "Validation_Version": VERSION
        }])

    pre_abs = _num(oos, "Preconfirm_Absolute_Error")
    post_abs = _num(oos, "Confirmed_Absolute_Error")
    pre_err = _num(oos, "Preconfirm_Error")
    post_err = _num(oos, "Confirmed_Error")
    pre_mae = float(pre_abs.mean())
    post_mae = float(post_abs.mean())
    rel = float((pre_mae - post_mae) / pre_mae) if pre_mae > 0 else float("nan")
    win = float((post_abs < pre_abs).mean())
    loss = float((post_abs > pre_abs).mean())
    pre_bias = float(pre_err.mean())
    post_bias = float(post_err.mean())

    if n < MIN_OOS_PAIRED:
        status, reason = "LEARNING", "oos_sample"
    elif rel >= MIN_RELATIVE_MAE and win >= 0.50 and abs(post_bias) <= abs(pre_bias):
        status, reason = "HELPING", "passed"
    elif rel <= -MIN_RELATIVE_MAE and loss >= 0.50 and abs(post_bias) >= abs(pre_bias):
        status, reason = "HURTING", "failed"
    else:
        status, reason = "MIXED", "guardrail"

    return pd.DataFrame([{
        "Metric": "STRIKEOUTS",
        "OOS_Paired_Starts": n,
        "Preconfirm_MAE": pre_mae,
        "Confirmed_MAE": post_mae,
        "Relative_MAE_Improvement": rel,
        "Confirmed_Win_Share": win,
        "Confirmed_Loss_Share": loss,
        "Preconfirm_Bias": pre_bias,
        "Confirmed_Bias": post_bias,
        "Status": status,
        "Reason": reason,
        "Validation_Version": VERSION,
    }])


def main() -> None:
    p = argparse.ArgumentParser(description="Chronological report-only lineup-confirmation K validation")
    p.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    p.add_argument("--detail", type=Path, default=Path("data/lineup_k_walkforward_detail.csv"))
    p.add_argument("--summary", type=Path, default=Path("data/lineup_k_walkforward_summary.csv"))
    args = p.parse_args()
    log = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if log.empty:
        raise SystemExit("No projection history available")
    detail = build_oos_detail(log)
    summary = summarize_oos(detail)
    args.detail.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

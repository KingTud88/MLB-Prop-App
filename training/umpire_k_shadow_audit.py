from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from engine.umpire_context import CANDIDATE_VERSION, candidate_from_prior

VERSION = "umpire-k-shadow-v1-report-only"
MIN_ELIGIBLE_STARTS = 30
MIN_RELATIVE_MAE = 0.01


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(frame[col], errors="coerce") if col in frame.columns else pd.Series(np.nan, index=frame.index)


def build_detail(projections: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    if projections is None or projections.empty or observations is None or observations.empty:
        return pd.DataFrame()
    work = projections.copy()
    work["_game_pk"] = _num(work, "game_pk")
    work["_date"] = pd.to_datetime(work.get("game_date"), errors="coerce").dt.normalize()
    base = _num(work, "projection")
    actual = _num(work, "actual_strikeouts")
    ready = work["_game_pk"].notna() & work["_date"].notna() & base.notna() & actual.notna()
    work = work.loc[ready].copy()
    if work.empty:
        return pd.DataFrame()

    obs = observations.copy()
    obs["_game_pk"] = _num(obs, "game_pk")
    umpire_lookup = (
        obs.dropna(subset=["_game_pk", "umpire_id"])
        .drop_duplicates(subset=["_game_pk"], keep="last")
        .set_index("_game_pk")[["umpire_id", "umpire_name"]]
    )

    rows: list[dict[str, object]] = []
    for _, row in work.iterrows():
        game_pk = float(row["_game_pk"])
        if game_pk not in umpire_lookup.index:
            continue
        ump = umpire_lookup.loc[game_pk]
        candidate = candidate_from_prior(observations, int(ump["umpire_id"]), str(row.get("game_date", "")))
        base_projection = float(row["projection"])
        actual_k = float(row["actual_strikeouts"])
        factor = float(candidate["umpire_k_factor_candidate"])
        candidate_projection = base_projection * factor
        eligible = str(candidate["umpire_candidate_status"]) == "AUDITABLE"
        rows.append({
            "game_date": str(row.get("game_date", "")),
            "game_pk": int(game_pk),
            "pitcher_id": row.get("pitcher_id"),
            "player": row.get("player"),
            "umpire_id": int(ump["umpire_id"]),
            "umpire_name": str(ump.get("umpire_name", "")),
            "Prior_Umpire_Games": int(candidate["umpire_prior_games"]),
            "Candidate_Factor": factor,
            "OOS_Eligible": bool(eligible),
            "Base_Projection": base_projection,
            "Candidate_Projection": candidate_projection,
            "Actual_Strikeouts": actual_k,
            "Base_Absolute_Error": abs(base_projection - actual_k),
            "Candidate_Absolute_Error": abs(candidate_projection - actual_k),
            "Base_Error": base_projection - actual_k,
            "Candidate_Error": candidate_projection - actual_k,
            "Candidate_Win": abs(candidate_projection - actual_k) < abs(base_projection - actual_k),
            "Candidate_Loss": abs(candidate_projection - actual_k) > abs(base_projection - actual_k),
            "Candidate_Version": CANDIDATE_VERSION,
            "Validation_Version": VERSION,
            "Availability_Note": "historical_umpire_identity_backfilled_after_fact",
        })
    return pd.DataFrame(rows)


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty:
        return pd.DataFrame([{
            "Metric": "STRIKEOUTS", "Eligible_Starts": 0, "Status": "LEARNING",
            "Reason": "no_joined_rows", "Validation_Version": VERSION,
        }])
    oos = detail.loc[detail["OOS_Eligible"].fillna(False).astype(bool)].copy()
    n = int(len(oos))
    if not n:
        return pd.DataFrame([{
            "Metric": "STRIKEOUTS", "Eligible_Starts": 0, "Status": "LEARNING",
            "Reason": "no_20_prior_game_rows", "Validation_Version": VERSION,
        }])

    base_abs = _num(oos, "Base_Absolute_Error")
    cand_abs = _num(oos, "Candidate_Absolute_Error")
    base_err = _num(oos, "Base_Error")
    cand_err = _num(oos, "Candidate_Error")
    base_mae = float(base_abs.mean())
    cand_mae = float(cand_abs.mean())
    rel = float((base_mae - cand_mae) / base_mae) if base_mae > 0 else float("nan")
    win = float((cand_abs < base_abs).mean())
    loss = float((cand_abs > base_abs).mean())
    base_bias = float(base_err.mean())
    cand_bias = float(cand_err.mean())

    if n < MIN_ELIGIBLE_STARTS:
        status, reason = "LEARNING", "eligible_sample"
    elif rel >= MIN_RELATIVE_MAE and win >= 0.50 and abs(cand_bias) <= abs(base_bias):
        status, reason = "SIGNAL_HELPING", "passed_signal_only"
    elif rel <= -MIN_RELATIVE_MAE and loss >= 0.50 and abs(cand_bias) >= abs(base_bias):
        status, reason = "SIGNAL_HURTING", "failed_signal_only"
    else:
        status, reason = "MIXED", "guardrail"

    return pd.DataFrame([{
        "Metric": "STRIKEOUTS",
        "Eligible_Starts": n,
        "Base_MAE": base_mae,
        "UmpireCandidate_MAE": cand_mae,
        "Relative_MAE_Improvement": rel,
        "Candidate_Win_Share": win,
        "Candidate_Loss_Share": loss,
        "Base_Bias": base_bias,
        "UmpireCandidate_Bias": cand_bias,
        "Mean_Absolute_Factor_Delta": float((pd.to_numeric(oos["Candidate_Factor"], errors="coerce") - 1.0).abs().mean()),
        "Status": status,
        "Reason": reason,
        "Production_Authority": "NONE",
        "Historical_Umpire_Availability": "NOT_PROVEN",
        "Validation_Version": VERSION,
    }])


def main() -> None:
    p = argparse.ArgumentParser(description="Historical signal-only walk-forward audit for umpire K factor")
    p.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    p.add_argument("--umpire-log", type=Path, default=Path("data/umpire_observation_log.csv"))
    p.add_argument("--detail", type=Path, default=Path("data/umpire_k_shadow_detail.csv"))
    p.add_argument("--summary", type=Path, default=Path("data/umpire_k_shadow_summary.csv"))
    args = p.parse_args()
    projections = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    observations = pd.read_csv(args.umpire_log) if args.umpire_log.exists() else pd.DataFrame()
    if projections.empty or observations.empty:
        raise SystemExit("Projection and umpire history are required")
    detail = build_detail(projections, observations)
    summary = summarize(detail)
    args.detail.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

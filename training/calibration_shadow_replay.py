from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from engine.calibration import fit_blend_candidate
from training.calibration_lineage import eligible_rows

REPLAY_VERSION = "calibration-shadow-replay-v1"
MILESTONES = tuple(range(3, 11))
FIT_MIN_OBSERVATIONS = 30
MIN_OOS_STARTS = 30
MIN_RELATIVE_BRIER = 0.01
MIN_WIN_SHARE = 0.50


def _empty_detail() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "game_date", "captured_at_utc", "game_pk", "pitcher_id", "player", "opponent",
        "Milestone", "Actual_Hit",
        "Prior_Eligible_Starts", "Candidate_SIM_Weight", "Candidate_MATH_Weight",
        "Baseline_Probability", "Candidate_Probability", "Baseline_Brier",
        "Candidate_Brier", "Candidate_Won", "Replay_Version",
    ])


def build_walk_forward_detail(frame: pd.DataFrame) -> pd.DataFrame:
    """Score candidate weights using only strictly earlier resolved game dates.

    The current row is never eligible to fit its own weight. Same-day resolved
    outcomes are also excluded from one another by requiring prior game_date to
    be strictly earlier than the current game_date.
    """
    eligible = eligible_rows(frame)
    if eligible.empty:
        return _empty_detail()

    work = eligible.copy()
    work["_game_date"] = pd.to_datetime(work["game_date"], errors="coerce", utc=True).dt.normalize()
    work["_captured"] = pd.to_datetime(work["captured_at_utc"], errors="coerce", utc=True)
    work["_actual"] = pd.to_numeric(work["actual_strikeouts"], errors="coerce")
    work = work.dropna(subset=["_game_date", "_captured", "_actual"]).sort_values(["_game_date", "_captured"])

    rows: list[dict[str, object]] = []
    for idx, current in work.iterrows():
        prior = work.loc[work["_game_date"].lt(current["_game_date"])]
        if prior.empty:
            continue
        for milestone in MILESTONES:
            sim_col = f"sim_{milestone}p"
            math_col = f"math_{milestone}p"
            if sim_col not in work.columns or math_col not in work.columns:
                continue
            sim_now = pd.to_numeric(pd.Series([current.get(sim_col)]), errors="coerce").iloc[0]
            math_now = pd.to_numeric(pd.Series([current.get(math_col)]), errors="coerce").iloc[0]
            if pd.isna(sim_now) or pd.isna(math_now):
                continue

            candidate = fit_blend_candidate(prior, milestone, min_observations=FIT_MIN_OBSERVATIONS)
            if not candidate.calibrated:
                continue

            sim_now = float(np.clip(float(sim_now), 0.001, 0.999))
            math_now = float(np.clip(float(math_now), 0.001, 0.999))
            baseline_p = 0.50 * sim_now + 0.50 * math_now
            candidate_p = candidate.weight_simulation * sim_now + candidate.weight_math * math_now
            actual_hit = float(float(current["_actual"]) >= float(milestone))
            baseline_brier = float((baseline_p - actual_hit) ** 2)
            candidate_brier = float((candidate_p - actual_hit) ** 2)
            rows.append({
                "game_date": str(current.get("game_date", "")),
                "captured_at_utc": str(current.get("captured_at_utc", "")),
                "game_pk": current.get("game_pk"),
                "pitcher_id": current.get("pitcher_id"),
                "player": current.get("player"),
                "opponent": current.get("opponent"),
                "Milestone": int(milestone),
                "Actual_Hit": actual_hit,
                "Prior_Eligible_Starts": int(candidate.observations),
                "Candidate_SIM_Weight": float(candidate.weight_simulation),
                "Candidate_MATH_Weight": float(candidate.weight_math),
                "Baseline_Probability": baseline_p,
                "Candidate_Probability": candidate_p,
                "Baseline_Brier": baseline_brier,
                "Candidate_Brier": candidate_brier,
                "Candidate_Won": bool(candidate_brier < baseline_brier),
                "Replay_Version": REPLAY_VERSION,
            })
    return pd.DataFrame(rows) if rows else _empty_detail()


def summarize_walk_forward(detail: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Milestone", "OOS_Starts", "Baseline_Brier", "Candidate_Brier",
        "Relative_Brier_Improvement", "Baseline_Calibration_Gap",
        "Candidate_Calibration_Gap", "Candidate_Win_Share", "Status",
        "Replay_Version",
    ]
    if detail is None or detail.empty:
        return pd.DataFrame([
            {
                "Milestone": int(m), "OOS_Starts": 0, "Baseline_Brier": np.nan,
                "Candidate_Brier": np.nan, "Relative_Brier_Improvement": np.nan,
                "Baseline_Calibration_Gap": np.nan, "Candidate_Calibration_Gap": np.nan,
                "Candidate_Win_Share": np.nan, "Status": "LEARNING",
                "Replay_Version": REPLAY_VERSION,
            }
            for m in MILESTONES
        ], columns=columns)

    rows: list[dict[str, object]] = []
    for milestone in MILESTONES:
        group = detail.loc[pd.to_numeric(detail["Milestone"], errors="coerce").eq(milestone)].copy()
        if group.empty:
            n = 0
            baseline_brier = candidate_brier = rel = base_gap = cand_gap = win = np.nan
            status = "LEARNING"
        else:
            n = int(len(group))
            baseline_brier = float(pd.to_numeric(group["Baseline_Brier"], errors="coerce").mean())
            candidate_brier = float(pd.to_numeric(group["Candidate_Brier"], errors="coerce").mean())
            rel = float((baseline_brier - candidate_brier) / baseline_brier) if baseline_brier > 0 else np.nan
            actual = pd.to_numeric(group["Actual_Hit"], errors="coerce")
            base_p = pd.to_numeric(group["Baseline_Probability"], errors="coerce")
            cand_p = pd.to_numeric(group["Candidate_Probability"], errors="coerce")
            base_gap = float(base_p.mean() - actual.mean())
            cand_gap = float(cand_p.mean() - actual.mean())
            win = float(group["Candidate_Won"].fillna(False).astype(bool).mean())
            if n < MIN_OOS_STARTS:
                status = "LEARNING"
            elif rel >= MIN_RELATIVE_BRIER and abs(cand_gap) <= abs(base_gap) and win >= MIN_WIN_SHARE:
                status = "HELPING"
            elif rel <= -MIN_RELATIVE_BRIER and abs(cand_gap) >= abs(base_gap) and win <= 0.50:
                status = "HURTING"
            else:
                status = "MIXED"
        rows.append({
            "Milestone": int(milestone),
            "OOS_Starts": n,
            "Baseline_Brier": baseline_brier,
            "Candidate_Brier": candidate_brier,
            "Relative_Brier_Improvement": rel,
            "Baseline_Calibration_Gap": base_gap,
            "Candidate_Calibration_Gap": cand_gap,
            "Candidate_Win_Share": win,
            "Status": status,
            "Replay_Version": REPLAY_VERSION,
        })
    return pd.DataFrame(rows, columns=columns)


def main() -> None:
    parser = argparse.ArgumentParser(description="Leakage-safe walk-forward shadow replay for strikeout calibration weights.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/calibration_shadow_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/calibration_shadow_summary.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    detail = build_walk_forward_detail(history)
    summary = summarize_walk_forward(detail)
    for path in (args.detail, args.summary):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    print(summary.to_string(index=False))
    print(f"shadow_oos_rows={len(detail)} replay={REPLAY_VERSION}")


if __name__ == "__main__":
    main()

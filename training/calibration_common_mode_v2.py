from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS

AUDIT_VERSION = "calibration-common-mode-v2-report-only"
PRODUCTION_AUTHORITY = "NONE"
FUTURE_ONLY_START = pd.Timestamp("2026-08-21", tz="UTC")
MIN_PRIOR_RESOLVED_STARTS = 30
PRIOR_STRENGTH = 30.0
CORRECTION_CAP_K = 0.50
MIN_OOS_STARTS = 30
MIN_EVIDENCE_DAYS = 5
MIN_DISTINCT_PITCHERS = 15
MIN_RELATIVE_MAE = 0.01
MIN_WIN_SHARE = 0.52

DETAIL_COLUMNS = [
    "Audit_Version", "Production_Authority", "Game_PK", "Game_Date",
    "Pitcher_ID", "Pitcher", "Captured_At_UTC", "Game_Time",
    "Prior_Resolved_Starts", "Raw_Prior_Residual_Mean", "Shrinkage",
    "Applied_Correction_K", "Baseline_Projection", "Candidate_Projection",
    "Actual_Strikeouts", "Baseline_Error", "Candidate_Error",
    "Baseline_Absolute_Error", "Candidate_Absolute_Error", "Candidate_Won",
    "Tie", "Candidate_Ready",
]

SUMMARY_COLUMNS = [
    "Audit_Version", "Production_Authority", "Future_Only_Start",
    "Eligible_Future_Starts", "OOS_Starts", "Evidence_Days",
    "Distinct_Pitchers", "Baseline_MAE", "Candidate_MAE",
    "Relative_MAE_Improvement", "Baseline_Bias", "Candidate_Bias",
    "Candidate_Win_Share", "Tie_Rate", "Status",
]


def _unit_key(row: pd.Series) -> str:
    game_pk = str(row.get("game_pk", "")).strip()
    pitcher_id = str(row.get("pitcher_id", "")).strip()
    player = str(row.get("player", "")).strip()
    game_date = row.get("_game_date")
    date_text = "" if pd.isna(game_date) else pd.Timestamp(game_date).date().isoformat()
    game_part = game_pk if game_pk and game_pk.lower() not in {"nan", "none", "<na>"} else date_text
    pitcher_part = pitcher_id if pitcher_id and pitcher_id.lower() not in {"nan", "none", "<na>"} else player
    return f"{game_part}|{pitcher_part}"


def prepare_units(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one lineage-safe latest pregame capture per pitcher-game.

    This intentionally fails closed when first-pitch timing or modern history
    semantics are unavailable. No legacy timing reconstruction is attempted.
    """
    if frame is None or frame.empty:
        return pd.DataFrame()

    work = frame.copy()
    required = (
        "game_pk", "game_date", "game_time", "captured_at_utc", "pitcher_id",
        "player", "projection", "actual_strikeouts", "history_semantics",
    )
    for column in required:
        if column not in work.columns:
            work[column] = pd.NA

    work["_game_date"] = pd.to_datetime(work["game_date"], errors="coerce", utc=True).dt.normalize()
    work["_game_time"] = pd.to_datetime(work["game_time"], errors="coerce", utc=True)
    work["_captured_at"] = pd.to_datetime(work["captured_at_utc"], errors="coerce", utc=True)
    work["_projection"] = pd.to_numeric(work["projection"], errors="coerce")
    work["_actual"] = pd.to_numeric(work["actual_strikeouts"], errors="coerce")

    valid = (
        work["_game_date"].notna()
        & work["_game_time"].notna()
        & work["_captured_at"].notna()
        & work["_projection"].notna()
        & work["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)
        & work["_captured_at"].le(work["_game_time"])
    )
    work = work.loc[valid].copy()
    if work.empty:
        return work

    work["_unit_key"] = work.apply(_unit_key, axis=1)
    work = (
        work.sort_values(["_unit_key", "_captured_at"])
        .drop_duplicates(subset=["_unit_key"], keep="last")
        .sort_values(["_game_date", "_captured_at", "_unit_key"])
        .reset_index(drop=True)
    )
    return work


def fit_prior_correction(prior: pd.DataFrame) -> dict[str, float | int | bool]:
    resolved = prior.loc[prior["_actual"].notna() & prior["_projection"].notna()].copy()
    n = int(len(resolved))
    if n < MIN_PRIOR_RESOLVED_STARTS:
        return {
            "ready": False,
            "n": n,
            "raw_residual_mean": np.nan,
            "shrinkage": np.nan,
            "correction": np.nan,
        }

    residual = resolved["_actual"].astype(float) - resolved["_projection"].astype(float)
    raw = float(residual.mean())
    shrinkage = float(n / (n + PRIOR_STRENGTH))
    correction = float(np.clip(raw * shrinkage, -CORRECTION_CAP_K, CORRECTION_CAP_K))
    return {
        "ready": True,
        "n": n,
        "raw_residual_mean": raw,
        "shrinkage": shrinkage,
        "correction": correction,
    }


def build_detail(frame: pd.DataFrame) -> pd.DataFrame:
    units = prepare_units(frame)
    if units.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    future = units.loc[units["_game_date"].ge(FUTURE_ONLY_START) & units["_actual"].notna()].copy()
    if future.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    rows: list[dict[str, object]] = []
    for _, current in future.iterrows():
        # Strictly earlier game dates prevent a resolved same-day result from
        # influencing another start on that date.
        prior = units.loc[
            units["_game_date"].lt(current["_game_date"])
            & units["_actual"].notna()
        ]
        fit = fit_prior_correction(prior)
        baseline = float(current["_projection"])
        actual = float(current["_actual"])
        ready = bool(fit["ready"])
        correction = float(fit["correction"]) if ready else np.nan
        candidate = max(0.0, baseline + correction) if ready else np.nan
        baseline_error = baseline - actual
        candidate_error = candidate - actual if ready else np.nan
        baseline_abs = abs(baseline_error)
        candidate_abs = abs(candidate_error) if ready else np.nan
        won = bool(candidate_abs < baseline_abs) if ready else False
        tie = bool(np.isclose(candidate_abs, baseline_abs, atol=1e-12)) if ready else False

        rows.append({
            "Audit_Version": AUDIT_VERSION,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Game_PK": current.get("game_pk"),
            "Game_Date": pd.Timestamp(current["_game_date"]).date().isoformat(),
            "Pitcher_ID": current.get("pitcher_id"),
            "Pitcher": current.get("player"),
            "Captured_At_UTC": current["_captured_at"].isoformat(),
            "Game_Time": current["_game_time"].isoformat(),
            "Prior_Resolved_Starts": int(fit["n"]),
            "Raw_Prior_Residual_Mean": fit["raw_residual_mean"],
            "Shrinkage": fit["shrinkage"],
            "Applied_Correction_K": fit["correction"],
            "Baseline_Projection": baseline,
            "Candidate_Projection": candidate,
            "Actual_Strikeouts": actual,
            "Baseline_Error": baseline_error,
            "Candidate_Error": candidate_error,
            "Baseline_Absolute_Error": baseline_abs,
            "Candidate_Absolute_Error": candidate_abs,
            "Candidate_Won": won,
            "Tie": tie,
            "Candidate_Ready": ready,
        })
    return pd.DataFrame(rows, columns=DETAIL_COLUMNS)


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    eligible_future = 0 if detail is None else int(len(detail))
    ready = (
        detail.loc[detail["Candidate_Ready"].fillna(False).astype(bool)].copy()
        if detail is not None and not detail.empty and "Candidate_Ready" in detail.columns
        else pd.DataFrame()
    )

    n = int(len(ready))
    if ready.empty:
        days = 0
        pitchers = 0
        base_mae = cand_mae = rel = base_bias = cand_bias = win_share = tie_rate = np.nan
        status = "LEARNING"
    else:
        days = int(pd.to_datetime(ready["Game_Date"], errors="coerce").dropna().dt.normalize().nunique())
        pitcher_identity = ready["Pitcher_ID"].fillna(ready["Pitcher"]).astype(str)
        pitchers = int(pitcher_identity.nunique())
        base_abs = pd.to_numeric(ready["Baseline_Absolute_Error"], errors="coerce")
        cand_abs = pd.to_numeric(ready["Candidate_Absolute_Error"], errors="coerce")
        base_err = pd.to_numeric(ready["Baseline_Error"], errors="coerce")
        cand_err = pd.to_numeric(ready["Candidate_Error"], errors="coerce")
        base_mae = float(base_abs.mean())
        cand_mae = float(cand_abs.mean())
        rel = float((base_mae - cand_mae) / base_mae) if base_mae > 0 else np.nan
        base_bias = float(base_err.mean())
        cand_bias = float(cand_err.mean())
        ties = ready["Tie"].fillna(False).astype(bool)
        wins = ready["Candidate_Won"].fillna(False).astype(bool)
        non_ties = ~ties
        win_share = float(wins.loc[non_ties].mean()) if non_ties.any() else np.nan
        tie_rate = float(ties.mean())

        mature = n >= MIN_OOS_STARTS and days >= MIN_EVIDENCE_DAYS and pitchers >= MIN_DISTINCT_PITCHERS
        if not mature:
            status = "LEARNING"
        elif (
            pd.notna(rel)
            and rel >= MIN_RELATIVE_MAE
            and abs(cand_bias) <= abs(base_bias)
            and pd.notna(win_share)
            and win_share >= MIN_WIN_SHARE
        ):
            status = "HELPING"
        elif (
            pd.notna(rel)
            and rel <= -MIN_RELATIVE_MAE
            and abs(cand_bias) >= abs(base_bias)
            and pd.notna(win_share)
            and win_share <= (1.0 - MIN_WIN_SHARE)
        ):
            status = "HURTING"
        else:
            status = "MIXED"

    return pd.DataFrame([{
        "Audit_Version": AUDIT_VERSION,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Future_Only_Start": FUTURE_ONLY_START.date().isoformat(),
        "Eligible_Future_Starts": eligible_future,
        "OOS_Starts": n,
        "Evidence_Days": days,
        "Distinct_Pitchers": pitchers,
        "Baseline_MAE": base_mae,
        "Candidate_MAE": cand_mae,
        "Relative_MAE_Improvement": rel,
        "Baseline_Bias": base_bias,
        "Candidate_Bias": cand_bias,
        "Candidate_Win_Share": win_share,
        "Tie_Rate": tie_rate,
        "Status": status,
    }], columns=SUMMARY_COLUMNS)


def preregistration_manifest() -> pd.DataFrame:
    rows = [
        ("audit_version", AUDIT_VERSION),
        ("production_authority", PRODUCTION_AUTHORITY),
        ("future_only_start", FUTURE_ONLY_START.date().isoformat()),
        ("challenger_type", "post-blend additive residual correction"),
        ("baseline", "saved production strikeout projection"),
        ("training_pool", "expanding strictly earlier resolved game dates"),
        ("same_day_training_excluded", True),
        ("unit_of_analysis", "unique pitcher-game start"),
        ("capture_selection", "latest valid capture at or before game_time"),
        ("post_first_pitch_rows_excluded", True),
        ("history_semantics_required", HISTORY_SEMANTICS),
        ("minimum_prior_resolved_starts", MIN_PRIOR_RESOLVED_STARTS),
        ("residual_definition", "actual_strikeouts - projection"),
        ("residual_estimator", "expanding mean"),
        ("shrinkage", "n / (n + 30)"),
        ("correction_cap_k", CORRECTION_CAP_K),
        ("sim_math_reweighting", False),
        ("minimum_oos_starts", MIN_OOS_STARTS),
        ("minimum_evidence_days", MIN_EVIDENCE_DAYS),
        ("minimum_distinct_pitchers", MIN_DISTINCT_PITCHERS),
        ("helping_relative_mae_min", MIN_RELATIVE_MAE),
        ("helping_win_share_min", MIN_WIN_SHARE),
        ("bias_must_not_worsen_for_helping", True),
        ("weather_authority", "INFORMATIONAL_ONLY"),
        ("automatic_activation", False),
    ]
    return pd.DataFrame(rows, columns=["Field", "Frozen_Value"])


def run_audit(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail = build_detail(frame)
    return detail, summarize(detail)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preregistered report-only post-blend strikeout calibration challenger.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/calibration_common_mode_v2_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/calibration_common_mode_v2_summary.csv"))
    parser.add_argument("--preregistration", type=Path, default=Path("data/calibration_common_mode_v2_preregistration.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    detail, summary = run_audit(history)
    manifest = preregistration_manifest()
    for path in (args.detail, args.summary, args.preregistration):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    manifest.to_csv(args.preregistration, index=False)
    print(summary.to_string(index=False))
    print(f"calibration_common_mode_v2_rows={len(detail)} audit={AUDIT_VERSION}")
    print("report_only=true production_authority=NONE automatic_activation=false")


if __name__ == "__main__":
    main()

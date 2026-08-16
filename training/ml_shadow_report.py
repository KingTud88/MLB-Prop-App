from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from engine.starter_history import HISTORY_SEMANTICS

VERSION = "ml-k-shadow-v1-report-only"
MIN_PRIOR_RESOLVED = 40
MIN_OOS_RESOLVED = 30
MIN_FEATURE_OBSERVATIONS = 10
MIN_RELATIVE_MAE = 0.02
RANDOM_STATE = 9000

# Intentionally limited to pregame baseball/context fields already frozen in
# projection_log.csv. No sportsbook lines, prices, odds, results, current
# projection output, or SIM/MATH probabilities are ML inputs.
FEATURE_COLUMNS = (
    "opponent_k_pct",
    "starter_history_games",
    "expected_pitches",
    "expected_bf",
    "expected_outs",
    "workload_bf_sd",
    "workload_outs_sd",
    "workload_pitch_sd",
    "recent_pitches",
    "recent_bf",
    "recent_outs",
    "pitches_per_bf",
    "outs_per_bf",
    "days_since_last_start",
    "workload_rest_multiplier",
    "pitch_trend",
    "bf_trend",
    "outs_trend",
    "leash_index",
    "matchup_pa",
    "matchup_batters",
    "lineup_batters",
    "opponent_hit_rate",
    "team_leash_starts",
    "team_leash_avg_pitches",
    "team_leash_avg_bf",
    "team_leash_avg_outs",
    "team_leash_quick_hook_rate",
    "team_leash_tto_reach_rate",
    "team_leash_90_pitch_rate",
    "umpire_prior_games",
    "umpire_prior_k_rate",
    "umpire_league_prior_k_rate",
    "umpire_k_factor_candidate",
)

BANNED_INPUT_TOKENS = (
    "actual_",
    "resolved_",
    "odds",
    "price",
    "book",
    "market",
    "projection",
    "sim_",
    "math_",
)


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[col], errors="coerce")


def _dates(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame.get("game_date"), errors="coerce").dt.normalize()


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    work["_date"] = _dates(work)
    work["_actual_k"] = _num(work, "actual_strikeouts")
    work["_baseline"] = _num(work, "projection")
    if "history_semantics" in work.columns:
        work = work.loc[work["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)].copy()
    keys = [col for col in ("game_pk", "pitcher_id") if col in work.columns]
    if keys:
        work = work.drop_duplicates(keys, keep="last")
    return work.sort_values(["_date"] + (["player"] if "player" in work.columns else []), na_position="last")


def _feature_columns(prior: pd.DataFrame) -> list[str]:
    chosen: list[str] = []
    for col in FEATURE_COLUMNS:
        if col not in prior.columns:
            continue
        values = _num(prior, col)
        if int(values.notna().sum()) < MIN_FEATURE_OBSERVATIONS:
            continue
        if int(values.nunique(dropna=True)) < 2:
            continue
        chosen.append(col)
    return chosen


def _matrix(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame({col: _num(frame, col) for col in columns}, index=frame.index)


def _model() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            (
                "gbr",
                GradientBoostingRegressor(
                    loss="huber",
                    n_estimators=180,
                    learning_rate=0.03,
                    max_depth=2,
                    min_samples_leaf=8,
                    subsample=0.85,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def _fit_predict(prior: pd.DataFrame, current: pd.DataFrame) -> tuple[np.ndarray | None, list[str]]:
    features = _feature_columns(prior)
    if len(prior) < MIN_PRIOR_RESOLVED or not features or current.empty:
        return None, features
    y = _num(prior, "actual_strikeouts")
    ready = y.notna()
    if int(ready.sum()) < MIN_PRIOR_RESOLVED:
        return None, features
    pipeline = _model()
    pipeline.fit(_matrix(prior.loc[ready], features), y.loc[ready].astype(float))
    prediction = pipeline.predict(_matrix(current, features))
    return np.clip(np.asarray(prediction, dtype=float), 0.0, 15.0), features


def build_oos_detail(frame: pd.DataFrame) -> pd.DataFrame:
    work = _clean_frame(frame)
    if work.empty:
        return pd.DataFrame()
    resolved = work.loc[work["_date"].notna() & work["_actual_k"].notna() & work["_baseline"].notna()].copy()
    if resolved.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for game_date in sorted(resolved["_date"].drop_duplicates().tolist()):
        prior = resolved.loc[resolved["_date"].lt(game_date)].copy()
        current = resolved.loc[resolved["_date"].eq(game_date)].copy()
        predictions, features = _fit_predict(prior, current)
        eligible = predictions is not None
        for pos, (_, row) in enumerate(current.iterrows()):
            baseline = float(row["_baseline"])
            actual = float(row["_actual_k"])
            ml_value = float(predictions[pos]) if predictions is not None else np.nan
            sim_mean = pd.to_numeric(pd.Series([row.get("sim_mean_k")]), errors="coerce").iloc[0]
            math_mean = pd.to_numeric(pd.Series([row.get("math_mean_k")]), errors="coerce").iloc[0]
            three_path = (
                float((float(sim_mean) + float(math_mean) + ml_value) / 3.0)
                if eligible and pd.notna(sim_mean) and pd.notna(math_mean)
                else np.nan
            )
            rows.append(
                {
                    "game_date": pd.Timestamp(game_date).date().isoformat(),
                    "game_pk": row.get("game_pk"),
                    "pitcher_id": row.get("pitcher_id"),
                    "player": row.get("player"),
                    "team": row.get("team"),
                    "opponent": row.get("opponent"),
                    "Prior_Resolved_Starts": int(len(prior)),
                    "Feature_Count": int(len(features)),
                    "OOS_Eligible": bool(eligible),
                    "Existing_Projection": baseline,
                    "ML_Shadow_Projection": ml_value,
                    "SIM_Mean": sim_mean,
                    "MATH_Mean": math_mean,
                    "Three_Path_Candidate": three_path,
                    "Three_Path_Eligible": bool(pd.notna(three_path)),
                    "Actual_Strikeouts": actual,
                    "Existing_Absolute_Error": abs(baseline - actual),
                    "ML_Absolute_Error": abs(ml_value - actual) if pd.notna(ml_value) else np.nan,
                    "Three_Path_Absolute_Error": abs(three_path - actual) if pd.notna(three_path) else np.nan,
                    "Existing_Error": baseline - actual,
                    "ML_Error": ml_value - actual if pd.notna(ml_value) else np.nan,
                    "Three_Path_Error": three_path - actual if pd.notna(three_path) else np.nan,
                    "Report_Only": True,
                    "Validation_Version": VERSION,
                }
            )
    return pd.DataFrame(rows)


def _status(n: int, baseline_mae: float, candidate_mae: float, win_share: float, baseline_bias: float, candidate_bias: float) -> tuple[str, str, float]:
    relative = float((baseline_mae - candidate_mae) / baseline_mae) if baseline_mae > 0 else float("nan")
    if n < MIN_OOS_RESOLVED:
        return "LEARNING", "oos_sample", relative
    if relative >= MIN_RELATIVE_MAE and win_share >= 0.52 and abs(candidate_bias) <= abs(baseline_bias):
        return "HELPING", "passed", relative
    if relative <= -MIN_RELATIVE_MAE and win_share <= 0.48 and abs(candidate_bias) >= abs(baseline_bias):
        return "HURTING", "failed", relative
    return "MIXED", "guardrail", relative


def summarize_oos(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if detail is None or detail.empty:
        return pd.DataFrame(
            [
                {
                    "Challenger": "ML_SHADOW",
                    "OOS_Starts": 0,
                    "Status": "LEARNING",
                    "Reason": "no_resolved_rows",
                    "Report_Only": True,
                    "Live_Projection_Use": False,
                    "Market_Features_Used": False,
                    "Validation_Version": VERSION,
                },
                {
                    "Challenger": "SIM_MATH_ML_EQUAL_THIRDS",
                    "OOS_Starts": 0,
                    "Status": "LEARNING",
                    "Reason": "waiting_for_raw_path_history",
                    "Report_Only": True,
                    "Live_Projection_Use": False,
                    "Market_Features_Used": False,
                    "Validation_Version": VERSION,
                },
            ]
        )

    oos = detail.loc[detail["OOS_Eligible"].fillna(False).astype(bool) & detail["ML_Shadow_Projection"].notna()].copy()
    if oos.empty:
        rows.append(
            {
                "Challenger": "ML_SHADOW",
                "OOS_Starts": 0,
                "Status": "LEARNING",
                "Reason": "prior_sample",
                "Report_Only": True,
                "Live_Projection_Use": False,
                "Market_Features_Used": False,
                "Validation_Version": VERSION,
            }
        )
    else:
        baseline_abs = _num(oos, "Existing_Absolute_Error")
        candidate_abs = _num(oos, "ML_Absolute_Error")
        baseline_err = _num(oos, "Existing_Error")
        candidate_err = _num(oos, "ML_Error")
        n = int(len(oos))
        baseline_mae = float(baseline_abs.mean())
        candidate_mae = float(candidate_abs.mean())
        win_share = float((candidate_abs < baseline_abs).mean())
        baseline_bias = float(baseline_err.mean())
        candidate_bias = float(candidate_err.mean())
        status, reason, relative = _status(n, baseline_mae, candidate_mae, win_share, baseline_bias, candidate_bias)
        rows.append(
            {
                "Challenger": "ML_SHADOW",
                "OOS_Starts": n,
                "Existing_MAE": baseline_mae,
                "Candidate_MAE": candidate_mae,
                "Relative_MAE_Improvement": relative,
                "Candidate_Win_Share": win_share,
                "Existing_Bias": baseline_bias,
                "Candidate_Bias": candidate_bias,
                "Status": status,
                "Reason": reason,
                "Report_Only": True,
                "Live_Projection_Use": False,
                "Market_Features_Used": False,
                "Validation_Version": VERSION,
            }
        )

    three = detail.loc[detail["Three_Path_Eligible"].fillna(False).astype(bool) & detail["Three_Path_Candidate"].notna()].copy()
    if three.empty:
        rows.append(
            {
                "Challenger": "SIM_MATH_ML_EQUAL_THIRDS",
                "OOS_Starts": 0,
                "Status": "LEARNING",
                "Reason": "waiting_for_raw_path_history",
                "Report_Only": True,
                "Live_Projection_Use": False,
                "Market_Features_Used": False,
                "Validation_Version": VERSION,
            }
        )
    else:
        baseline_abs = _num(three, "Existing_Absolute_Error")
        candidate_abs = _num(three, "Three_Path_Absolute_Error")
        baseline_err = _num(three, "Existing_Error")
        candidate_err = _num(three, "Three_Path_Error")
        n = int(len(three))
        baseline_mae = float(baseline_abs.mean())
        candidate_mae = float(candidate_abs.mean())
        win_share = float((candidate_abs < baseline_abs).mean())
        baseline_bias = float(baseline_err.mean())
        candidate_bias = float(candidate_err.mean())
        status, reason, relative = _status(n, baseline_mae, candidate_mae, win_share, baseline_bias, candidate_bias)
        rows.append(
            {
                "Challenger": "SIM_MATH_ML_EQUAL_THIRDS",
                "OOS_Starts": n,
                "Existing_MAE": baseline_mae,
                "Candidate_MAE": candidate_mae,
                "Relative_MAE_Improvement": relative,
                "Candidate_Win_Share": win_share,
                "Existing_Bias": baseline_bias,
                "Candidate_Bias": candidate_bias,
                "Status": status,
                "Reason": reason,
                "Report_Only": True,
                "Live_Projection_Use": False,
                "Market_Features_Used": False,
                "Validation_Version": VERSION,
            }
        )
    return pd.DataFrame(rows)


def build_live_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    work = _clean_frame(frame)
    if work.empty:
        return pd.DataFrame()
    unresolved = work.loc[work["_date"].notna() & work["_actual_k"].isna() & work["_baseline"].notna()].copy()
    resolved = work.loc[work["_date"].notna() & work["_actual_k"].notna()].copy()
    if unresolved.empty or resolved.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for game_date in sorted(unresolved["_date"].drop_duplicates().tolist()):
        current = unresolved.loc[unresolved["_date"].eq(game_date)].copy()
        prior = resolved.loc[resolved["_date"].lt(game_date)].copy()
        predictions, features = _fit_predict(prior, current)
        if predictions is None:
            continue
        for pos, (_, row) in enumerate(current.iterrows()):
            ml_value = float(predictions[pos])
            sim_mean = pd.to_numeric(pd.Series([row.get("sim_mean_k")]), errors="coerce").iloc[0]
            math_mean = pd.to_numeric(pd.Series([row.get("math_mean_k")]), errors="coerce").iloc[0]
            three_path = (
                float((float(sim_mean) + float(math_mean) + ml_value) / 3.0)
                if pd.notna(sim_mean) and pd.notna(math_mean)
                else np.nan
            )
            rows.append(
                {
                    "game_date": pd.Timestamp(game_date).date().isoformat(),
                    "game_pk": row.get("game_pk"),
                    "pitcher_id": row.get("pitcher_id"),
                    "player": row.get("player"),
                    "team": row.get("team"),
                    "opponent": row.get("opponent"),
                    "Training_Resolved_Starts": int(len(prior)),
                    "Feature_Count": int(len(features)),
                    "Existing_Projection": float(row["_baseline"]),
                    "ML_Shadow_Projection": ml_value,
                    "SIM_Mean": sim_mean,
                    "MATH_Mean": math_mean,
                    "Three_Path_Candidate": three_path,
                    "Report_Only": True,
                    "Validation_Version": VERSION,
                }
            )
    return pd.DataFrame(rows)


def feature_manifest() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Feature": list(FEATURE_COLUMNS),
            "Pregame_Only": True,
            "Market_Data": False,
            "Outcome_Data": False,
            "Version": VERSION,
        }
    )


def validate_feature_contract() -> None:
    lowered = [feature.lower() for feature in FEATURE_COLUMNS]
    for feature in lowered:
        if any(token in feature for token in BANNED_INPUT_TOKENS):
            raise ValueError(f"Banned ML shadow feature: {feature}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Leakage-safe gradient-boosted K shadow/report challenger")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/ml_shadow_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/ml_shadow_summary.csv"))
    parser.add_argument("--live", type=Path, default=Path("data/ml_shadow_live_candidates.csv"))
    parser.add_argument("--features", type=Path, default=Path("data/ml_shadow_feature_manifest.csv"))
    args = parser.parse_args()

    validate_feature_contract()
    frame = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if frame.empty:
        raise SystemExit("No projection history available")
    detail = build_oos_detail(frame)
    summary = summarize_oos(detail)
    live = build_live_candidates(frame)
    manifest = feature_manifest()

    for path in (args.detail, args.summary, args.live, args.features):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    live.to_csv(args.live, index=False)
    manifest.to_csv(args.features, index=False)
    print(summary.to_string(index=False))
    print(f"live_shadow_candidates={len(live)} report_only=true")


if __name__ == "__main__":
    main()

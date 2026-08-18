from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "pitch-mix-whiff-forward-eval-v1-preregistered-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_PROJECTION_ADJUSTMENT = True
PREREGISTERED_GAME_DATE = "2026-08-18"
PRIMARY_METRIC = "SPEARMAN_SCORE_DELTA_VS_K_RESIDUAL"
MIN_RESOLVED_STARTS = 60
MIN_RESOLVED_DAYS = 10
MIN_OPPONENTS = 15

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "lineup_source", "lineup_hash", "score_version", "formula_id",
    "pitch_mix_whiff_score", "baseline_whiff_rate", "pitch_mix_whiff_delta",
    "weighted_arsenal_usage_coverage", "score_batters", "projection",
    "projection_captured_at_utc", "actual_strikeouts", "resolved_at_utc",
    "k_residual", "abs_k_residual", "evaluation_version", "report_only",
    "production_authority", "no_projection_adjustment",
]
SUMMARY_COLUMNS = [
    "Resolved_Starts", "Resolved_Days", "Opponents", "Mean_Score_Delta",
    "Median_Score_Delta", "Mean_K_Residual", "MAE_K_Residual",
    "Spearman_ScoreDelta_KResidual", "Pearson_ScoreDelta_KResidual",
    "Bottom_Quartile_Mean_Residual", "Top_Quartile_Mean_Residual",
    "TopMinusBottom_Residual", "Positive_Delta_Starts", "Positive_Delta_Mean_Residual",
    "NonPositive_Delta_Starts", "NonPositive_Delta_Mean_Residual",
    "Primary_Metric", "Preregistered_Game_Date", "Report_Only",
    "Production_Authority", "No_Projection_Adjustment", "Evaluation_Version",
]
GATE_COLUMNS = [
    "Status", "Resolved_Starts", "Required_Starts", "Resolved_Days", "Required_Days",
    "Opponents", "Required_Opponents", "Primary_Metric", "Reason",
    "Recommended_Action", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "Evaluation_Version",
]


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _clean(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _num(value: object) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return np.nan if pd.isna(parsed) else float(parsed)


def _utc(value: object) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce", utc=True)


def _corr(x: pd.Series, y: pd.Series) -> float:
    pair = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if len(pair) < 2 or pair["x"].nunique() < 2 or pair["y"].nunique() < 2:
        return np.nan
    return float(np.corrcoef(pair["x"], pair["y"])[0, 1])


def _spearman(x: pd.Series, y: pd.Series) -> float:
    pair = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if len(pair) < 2:
        return np.nan
    return _corr(pair["x"].rank(method="average"), pair["y"].rank(method="average"))


def _score_rows(scores: pd.DataFrame | None) -> pd.DataFrame:
    scores = scores.copy() if scores is not None else pd.DataFrame()
    if scores.empty:
        return scores
    if "audit_eligible" in scores.columns:
        scores = scores.loc[scores["audit_eligible"].map(_truthy)].copy()
    if "no_projection_adjustment" in scores.columns:
        scores = scores.loc[scores["no_projection_adjustment"].map(_truthy)].copy()
    dates = pd.to_datetime(scores.get("game_date"), errors="coerce")
    cutoff = pd.Timestamp(PREREGISTERED_GAME_DATE)
    scores = scores.loc[dates.notna() & dates.ge(cutoff)].copy()
    return scores


def _matching_projection(score: pd.Series, projections: pd.DataFrame) -> pd.Series | None:
    if projections.empty:
        return None
    game_pk = _num(score.get("game_pk"))
    pitcher_id = _num(score.get("pitcher_id"))
    if not np.isfinite(game_pk) or not np.isfinite(pitcher_id):
        return None

    game_col = pd.to_numeric(projections.get("game_pk"), errors="coerce")
    pitcher_col = pd.to_numeric(projections.get("pitcher_id"), errors="coerce")
    matches = projections.loc[game_col.eq(int(game_pk)) & pitcher_col.eq(int(pitcher_id))].copy()
    if matches.empty:
        return None

    source = _clean(score.get("lineup_source")) or "ACTIVE_ROSTER"
    if "lineup_source" in matches.columns:
        source_mask = matches["lineup_source"].fillna("ACTIVE_ROSTER").astype(str).str.strip().replace("", "ACTIVE_ROSTER").eq(source)
        matches = matches.loc[source_mask].copy()
    if matches.empty:
        return None

    lineup_hash = _clean(score.get("lineup_hash"))
    if "lineup_hash" in matches.columns:
        hash_text = matches["lineup_hash"].fillna("").astype(str).str.strip().replace("nan", "")
        matches = matches.loc[hash_text.eq(lineup_hash)].copy()
    if matches.empty:
        return None

    score_capture = _utc(score.get("whiff_context_captured_at_utc"))
    if "captured_at_utc" in matches.columns and not pd.isna(score_capture):
        captured = pd.to_datetime(matches["captured_at_utc"], errors="coerce", utc=True)
        eligible_time = captured.notna() & captured.le(score_capture)
        matches = matches.loc[eligible_time].copy()
        if matches.empty:
            return None
        matches = matches.assign(_captured=captured.loc[matches.index]).sort_values("_captured")
    elif "captured_at_utc" in matches.columns:
        matches = matches.assign(_captured=pd.to_datetime(matches["captured_at_utc"], errors="coerce", utc=True)).sort_values("_captured")

    row = matches.iloc[-1].copy()
    if not np.isfinite(_num(row.get("projection"))) or not np.isfinite(_num(row.get("actual_strikeouts"))):
        return None
    return row


def build_detail(scores: pd.DataFrame, projections: pd.DataFrame) -> pd.DataFrame:
    scores = _score_rows(scores)
    projections = projections.copy() if projections is not None else pd.DataFrame()
    rows: list[dict[str, object]] = []
    for _, score in scores.iterrows():
        projection_row = _matching_projection(score, projections)
        if projection_row is None:
            continue
        projection = _num(projection_row.get("projection"))
        actual = _num(projection_row.get("actual_strikeouts"))
        residual = actual - projection
        rows.append({
            "game_date": _clean(score.get("game_date")),
            "game_pk": int(_num(score.get("game_pk"))),
            "pitcher_id": int(_num(score.get("pitcher_id"))),
            "player": _clean(score.get("player")),
            "team": _clean(score.get("team")),
            "opponent": _clean(score.get("opponent")),
            "lineup_source": _clean(score.get("lineup_source")) or "ACTIVE_ROSTER",
            "lineup_hash": _clean(score.get("lineup_hash")),
            "score_version": _clean(score.get("score_version")),
            "formula_id": _clean(score.get("formula_id")),
            "pitch_mix_whiff_score": _num(score.get("pitch_mix_whiff_score")),
            "baseline_whiff_rate": _num(score.get("baseline_whiff_rate")),
            "pitch_mix_whiff_delta": _num(score.get("pitch_mix_whiff_delta")),
            "weighted_arsenal_usage_coverage": _num(score.get("weighted_arsenal_usage_coverage")),
            "score_batters": _num(score.get("score_batters")),
            "projection": projection,
            "projection_captured_at_utc": _clean(projection_row.get("captured_at_utc")),
            "actual_strikeouts": actual,
            "resolved_at_utc": _clean(projection_row.get("resolved_at_utc")),
            "k_residual": residual,
            "abs_k_residual": abs(residual),
            "evaluation_version": VERSION,
            "report_only": REPORT_ONLY,
            "production_authority": PRODUCTION_AUTHORITY,
            "no_projection_adjustment": NO_PROJECTION_ADJUSTMENT,
        })
    return pd.DataFrame(rows, columns=DETAIL_COLUMNS)


def build_summary(detail: pd.DataFrame) -> pd.DataFrame:
    detail = detail.copy() if detail is not None else pd.DataFrame(columns=DETAIL_COLUMNS)
    n = int(len(detail))
    days = int(pd.Series(detail.get("game_date", dtype=object)).dropna().astype(str).nunique()) if n else 0
    opponents = int(pd.Series(detail.get("opponent", dtype=object)).dropna().astype(str).nunique()) if n else 0
    delta = pd.to_numeric(detail.get("pitch_mix_whiff_delta"), errors="coerce") if n else pd.Series(dtype=float)
    residual = pd.to_numeric(detail.get("k_residual"), errors="coerce") if n else pd.Series(dtype=float)
    abs_residual = pd.to_numeric(detail.get("abs_k_residual"), errors="coerce") if n else pd.Series(dtype=float)

    bottom_mean = top_mean = np.nan
    if n >= 4 and delta.notna().sum() >= 4:
        ranked = detail.loc[delta.notna() & residual.notna()].copy()
        if len(ranked) >= 4:
            ranked = ranked.sort_values("pitch_mix_whiff_delta")
            quartile_n = max(1, len(ranked) // 4)
            bottom_mean = float(pd.to_numeric(ranked.head(quartile_n)["k_residual"], errors="coerce").mean())
            top_mean = float(pd.to_numeric(ranked.tail(quartile_n)["k_residual"], errors="coerce").mean())

    positive = detail.loc[delta.gt(0)] if n else detail
    nonpositive = detail.loc[delta.le(0)] if n else detail
    return pd.DataFrame([{
        "Resolved_Starts": n,
        "Resolved_Days": days,
        "Opponents": opponents,
        "Mean_Score_Delta": float(delta.mean()) if delta.notna().any() else np.nan,
        "Median_Score_Delta": float(delta.median()) if delta.notna().any() else np.nan,
        "Mean_K_Residual": float(residual.mean()) if residual.notna().any() else np.nan,
        "MAE_K_Residual": float(abs_residual.mean()) if abs_residual.notna().any() else np.nan,
        "Spearman_ScoreDelta_KResidual": _spearman(delta, residual),
        "Pearson_ScoreDelta_KResidual": _corr(delta, residual),
        "Bottom_Quartile_Mean_Residual": bottom_mean,
        "Top_Quartile_Mean_Residual": top_mean,
        "TopMinusBottom_Residual": top_mean - bottom_mean if np.isfinite(top_mean) and np.isfinite(bottom_mean) else np.nan,
        "Positive_Delta_Starts": int(len(positive)),
        "Positive_Delta_Mean_Residual": float(pd.to_numeric(positive.get("k_residual"), errors="coerce").mean()) if len(positive) else np.nan,
        "NonPositive_Delta_Starts": int(len(nonpositive)),
        "NonPositive_Delta_Mean_Residual": float(pd.to_numeric(nonpositive.get("k_residual"), errors="coerce").mean()) if len(nonpositive) else np.nan,
        "Primary_Metric": PRIMARY_METRIC,
        "Preregistered_Game_Date": PREREGISTERED_GAME_DATE,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
        "Evaluation_Version": VERSION,
    }], columns=SUMMARY_COLUMNS)


def build_gate(summary: pd.DataFrame) -> pd.DataFrame:
    row = summary.iloc[0] if summary is not None and not summary.empty else pd.Series(dtype=object)
    starts = int(_num(row.get("Resolved_Starts"))) if np.isfinite(_num(row.get("Resolved_Starts"))) else 0
    days = int(_num(row.get("Resolved_Days"))) if np.isfinite(_num(row.get("Resolved_Days"))) else 0
    opponents = int(_num(row.get("Opponents"))) if np.isfinite(_num(row.get("Opponents"))) else 0
    ready = starts >= MIN_RESOLVED_STARTS and days >= MIN_RESOLVED_DAYS and opponents >= MIN_OPPONENTS
    if ready:
        status = "READY_FOR_MANUAL_RESEARCH_REVIEW"
        reason = "Preregistered forward sample-readiness requirements are satisfied; interpret association metrics manually."
        action = "REVIEW_ASSOCIATION_ONLY_DO_NOT_MAP_TO_PROJECTION_WITHOUT_NEW_EXPLICIT_RESEARCH"
    else:
        status = "LEARNING"
        reason = (
            f"Need {MIN_RESOLVED_STARTS} resolved starts / {MIN_RESOLVED_DAYS} days / {MIN_OPPONENTS} opponents; "
            f"currently {starts} / {days} / {opponents}."
        )
        action = "COLLECT_FORWARD_OUTCOMES_WITH_FROZEN_SCORE_AND_EVALUATION_PROTOCOL"
    return pd.DataFrame([{
        "Status": status,
        "Resolved_Starts": starts,
        "Required_Starts": MIN_RESOLVED_STARTS,
        "Resolved_Days": days,
        "Required_Days": MIN_RESOLVED_DAYS,
        "Opponents": opponents,
        "Required_Opponents": MIN_OPPONENTS,
        "Primary_Metric": PRIMARY_METRIC,
        "Reason": reason,
        "Recommended_Action": action,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
        "Evaluation_Version": VERSION,
    }], columns=GATE_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate preregistered pitch-mix Whiff score against forward K residuals.")
    parser.add_argument("--score-log", default="data/pitch_mix_whiff_score_log.csv")
    parser.add_argument("--projection-log", default="data/projection_log.csv")
    parser.add_argument("--detail-output", default="data/pitch_mix_whiff_forward_detail.csv")
    parser.add_argument("--summary-output", default="data/pitch_mix_whiff_forward_summary.csv")
    parser.add_argument("--gate-output", default="data/pitch_mix_whiff_forward_gate.csv")
    args = parser.parse_args()

    scores = pd.read_csv(args.score_log) if Path(args.score_log).exists() else pd.DataFrame()
    projections = pd.read_csv(args.projection_log) if Path(args.projection_log).exists() else pd.DataFrame()
    detail = build_detail(scores, projections)
    summary = build_summary(detail)
    gate = build_gate(summary)
    for path, frame in (
        (Path(args.detail_output), detail),
        (Path(args.summary_output), summary),
        (Path(args.gate_output), gate),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    print(gate.to_string(index=False))
    print(f"primary_metric={PRIMARY_METRIC} report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()

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
    """Select one latest frozen score context per start before applying audit eligibility."""
    scores = scores.copy() if scores is not None else pd.DataFrame()
    if scores.empty:
        return scores
    if "no_projection_adjustment" in scores.columns:
        scores = scores.loc[scores["no_projection_adjustment"].map(_truthy)].copy()
    dates = pd.to_datetime(scores.get("game_date"), errors="coerce")
    cutoff = pd.Timestamp(PREREGISTERED_GAME_DATE)
    scores = scores.loc[dates.notna() & dates.ge(cutoff)].copy()
    if scores.empty:
        return scores

    scores["_game_pk"] = pd.to_numeric(scores.get("game_pk"), errors="coerce")
    scores["_pitcher_id"] = pd.to_numeric(scores.get("pitcher_id"), errors="coerce")
    scores["_score_capture"] = pd.to_datetime(scores.get("whiff_context_captured_at_utc"), errors="coerce", utc=True)
    scores["_row_order"] = np.arange(len(scores))
    scores = scores.loc[
        scores["_game_pk"].notna() & scores["_pitcher_id"].notna() & scores["_score_capture"].notna()
    ].copy()
    if scores.empty:
        return scores
    scores = scores.sort_values(["_game_pk", "_pitcher_id", "_score_capture", "_row_order"])
    scores = scores.drop_duplicates(subset=["_game_pk", "_pitcher_id"], keep="last")
    if "audit_eligible" in scores.columns:
        scores = scores.loc[scores["audit_eligible"].map(_truthy)].copy()
    return scores.drop(columns=["_game_pk", "_pitcher_id", "_score_capture", "_row_order"], errors="ignore")


def _game_pitcher_matches(frame: pd.DataFrame, game_pk: int, pitcher_id: int) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    game_col = pd.to_numeric(frame.get("game_pk"), errors="coerce")
    pitcher_col = pd.to_numeric(frame.get("pitcher_id"), errors="coerce")
    return frame.loc[game_col.eq(int(game_pk)) & pitcher_col.eq(int(pitcher_id))].copy()


def _matching_preconfirm_projection(
    score: pd.Series,
    projections: pd.DataFrame,
    whiff_context: pd.DataFrame | None,
) -> pd.Series | None:
    """Recover a frozen active-roster projection only from preserved preconfirm lineage."""
    source = _clean(score.get("lineup_source")) or "ACTIVE_ROSTER"
    lineup_hash = _clean(score.get("lineup_hash"))
    if source != "ACTIVE_ROSTER" or lineup_hash:
        return None

    game_pk = _num(score.get("game_pk"))
    pitcher_id = _num(score.get("pitcher_id"))
    score_capture = _utc(score.get("whiff_context_captured_at_utc"))
    if not np.isfinite(game_pk) or not np.isfinite(pitcher_id) or pd.isna(score_capture):
        return None

    contexts = _game_pitcher_matches(
        whiff_context.copy() if whiff_context is not None else pd.DataFrame(),
        int(game_pk),
        int(pitcher_id),
    )
    if contexts.empty:
        return None
    context_source = contexts.get("lineup_source", pd.Series("ACTIVE_ROSTER", index=contexts.index)).fillna("ACTIVE_ROSTER").astype(str).str.strip().replace("", "ACTIVE_ROSTER")
    context_hash = contexts.get("lineup_hash", pd.Series("", index=contexts.index)).fillna("").astype(str).str.strip().replace("nan", "")
    context_capture = pd.to_datetime(contexts.get("whiff_context_captured_at_utc"), errors="coerce", utc=True)
    eligible = contexts.get("audit_eligible", pd.Series(False, index=contexts.index)).map(_truthy)
    contexts = contexts.loc[
        context_source.eq("ACTIVE_ROSTER")
        & context_hash.eq("")
        & context_capture.eq(score_capture)
        & eligible
    ].copy()
    if contexts.empty:
        return None

    frozen_projection_capture = _utc(contexts.iloc[-1].get("projection_captured_at_utc"))
    if pd.isna(frozen_projection_capture) or frozen_projection_capture > score_capture:
        return None

    matches = _game_pitcher_matches(projections, int(game_pk), int(pitcher_id))
    if matches.empty:
        return None
    if "lineup_source" in matches.columns:
        current_source = matches["lineup_source"].fillna("").astype(str).str.strip()
        matches = matches.loc[current_source.eq("CONFIRMED_LINEUP")].copy()
    if matches.empty:
        return None

    matches["_preconfirm"] = pd.to_numeric(matches.get("lineup_preconfirm_projection"), errors="coerce")
    matches["_actual"] = pd.to_numeric(matches.get("actual_strikeouts"), errors="coerce")
    matches = matches.loc[matches["_preconfirm"].notna() & matches["_actual"].notna()].copy()
    if matches.empty:
        return None
    if "captured_at_utc" in matches.columns:
        matches["_current_capture"] = pd.to_datetime(matches["captured_at_utc"], errors="coerce", utc=True)
        matches = matches.sort_values("_current_capture")

    row = matches.iloc[-1].copy()
    row["projection"] = float(row["_preconfirm"])
    row["captured_at_utc"] = frozen_projection_capture.isoformat()
    return row


def _matching_projection(
    score: pd.Series,
    projections: pd.DataFrame,
    whiff_context: pd.DataFrame | None = None,
) -> pd.Series | None:
    if projections.empty:
        return None
    game_pk = _num(score.get("game_pk"))
    pitcher_id = _num(score.get("pitcher_id"))
    if not np.isfinite(game_pk) or not np.isfinite(pitcher_id):
        return None

    matches = _game_pitcher_matches(projections, int(game_pk), int(pitcher_id))
    if matches.empty:
        return None

    source = _clean(score.get("lineup_source")) or "ACTIVE_ROSTER"
    if "lineup_source" in matches.columns:
        source_mask = matches["lineup_source"].fillna("ACTIVE_ROSTER").astype(str).str.strip().replace("", "ACTIVE_ROSTER").eq(source)
        matches = matches.loc[source_mask].copy()
    if not matches.empty:
        lineup_hash = _clean(score.get("lineup_hash"))
        if "lineup_hash" in matches.columns:
            hash_text = matches["lineup_hash"].fillna("").astype(str).str.strip().replace("nan", "")
            matches = matches.loc[hash_text.eq(lineup_hash)].copy()

    score_capture = _utc(score.get("whiff_context_captured_at_utc"))
    if not matches.empty and "captured_at_utc" in matches.columns and not pd.isna(score_capture):
        captured = pd.to_datetime(matches["captured_at_utc"], errors="coerce", utc=True)
        eligible_time = captured.notna() & captured.le(score_capture)
        matches = matches.loc[eligible_time].copy()
        if not matches.empty:
            matches = matches.assign(_captured=captured.loc[matches.index]).sort_values("_captured")
    elif not matches.empty and "captured_at_utc" in matches.columns:
        matches = matches.assign(_captured=pd.to_datetime(matches["captured_at_utc"], errors="coerce", utc=True)).sort_values("_captured")

    if not matches.empty:
        row = matches.iloc[-1].copy()
        if np.isfinite(_num(row.get("projection"))) and np.isfinite(_num(row.get("actual_strikeouts"))):
            return row

    return _matching_preconfirm_projection(score, projections, whiff_context)


def build_detail(
    scores: pd.DataFrame,
    projections: pd.DataFrame,
    whiff_context: pd.DataFrame | None = None,
) -> pd.DataFrame:
    scores = _score_rows(scores)
    projections = projections.copy() if projections is not None else pd.DataFrame()
    whiff_context = whiff_context.copy() if whiff_context is not None else pd.DataFrame()
    rows: list[dict[str, object]] = []
    for _, score in scores.iterrows():
        projection_row = _matching_projection(score, projections, whiff_context)
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
    game_dates = detail["game_date"] if "game_date" in detail.columns else pd.Series(dtype=object)
    opponent_values = detail["opponent"] if "opponent" in detail.columns else pd.Series(dtype=object)
    days = int(game_dates.dropna().astype(str).nunique()) if n else 0
    opponents = int(opponent_values.dropna().astype(str).nunique()) if n else 0
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
    parser.add_argument("--whiff-context", default="data/batter_pitch_whiff_context_log.csv")
    parser.add_argument("--detail-output", default="data/pitch_mix_whiff_forward_detail.csv")
    parser.add_argument("--summary-output", default="data/pitch_mix_whiff_forward_summary.csv")
    parser.add_argument("--gate-output", default="data/pitch_mix_whiff_forward_gate.csv")
    args = parser.parse_args()

    scores = pd.read_csv(args.score_log) if Path(args.score_log).exists() else pd.DataFrame()
    projections = pd.read_csv(args.projection_log) if Path(args.projection_log).exists() else pd.DataFrame()
    whiff_context = pd.read_csv(args.whiff_context) if Path(args.whiff_context).exists() else pd.DataFrame()
    detail = build_detail(scores, projections, whiff_context)
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

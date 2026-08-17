from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "opponent-matchup-v2-analytic-ablation-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
LEAGUE_K_RATE = 0.224
MIN_INFORMATIVE_RATE_DELTA = 0.0025  # 0.25 percentage points
MIN_EVAL_STARTS = 60
MIN_EVAL_DAYS = 10
MIN_EVAL_OPPONENTS = 15
STRONG_STARTS = 150
STRONG_DAYS = 25
STRONG_OPPONENTS = 25
MIN_RELATIVE_MAE = 0.005
STRONG_RELATIVE_MAE = 0.010
MIN_WIN_SHARE = 0.52
STRONG_WIN_SHARE = 0.55
BIAS_TOLERANCE = 0.05

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "Captured_At_UTC", "Game_Time_UTC", "Resolved_At_UTC", "Lineage",
    "Opponent_K_Rate", "Opponent_K_Delta_PP", "Matchup_PA", "Matchup_Batters",
    "Lineup_State", "Data_Quality", "Quality_Band", "Matchup_Environment",
    "Applied_Projection", "Neutral_Opponent_Projection", "Matchup_Adjustment_K",
    "Adjustment_Direction", "Adjustment_Magnitude_Band", "Informative_Adjustment",
    "Actual_Strikeouts", "Applied_Absolute_Error", "Neutral_Absolute_Error",
    "Applied_Error", "Neutral_Error", "Applied_Win", "Neutral_Win", "Tie",
    "Auditable", "Report_Only", "Production_Authority", "Validation_Version",
]

SUMMARY_COLUMNS = [
    "Metric", "Resolved_Rows", "Authentic_Pregame_Resolved", "Auditable_Starts",
    "Observed_Days", "Distinct_Opponents", "Applied_MAE", "Neutral_MAE",
    "Relative_MAE_Improvement", "Applied_Win_Share", "Neutral_Win_Share", "Tie_Share",
    "Applied_Bias", "Neutral_Bias", "Mean_Absolute_Adjustment_K",
    "Evidence_Status", "Reason", "Recommended_Action", "Report_Only",
    "Production_Authority", "Validation_Version",
]

SEGMENT_COLUMNS = [
    "Dimension", "Segment", "Rows", "Authentic_Pregame_Resolved", "Auditable_Starts",
    "Observed_Days", "Distinct_Opponents", "Applied_MAE", "Neutral_MAE",
    "Relative_MAE_Improvement", "Applied_Win_Share", "Neutral_Win_Share", "Tie_Share",
    "Applied_Bias", "Neutral_Bias", "Mean_Absolute_Adjustment_K",
    "Evidence", "Reason", "Report_Only", "Production_Authority", "Validation_Version",
]

GATE_COLUMNS = [
    "Evidence_Status", "Auditable_Starts", "Observed_Days", "Distinct_Opponents",
    "Applied_MAE", "Neutral_MAE", "Relative_MAE_Improvement", "Applied_Win_Share",
    "Neutral_Win_Share", "Tie_Share", "Applied_Bias", "Neutral_Bias",
    "Mean_Absolute_Adjustment_K", "Reason", "Recommended_Action",
    "Manual_Review_Ready", "Report_Only", "Production_Authority", "Validation_Version",
]


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[col], errors="coerce")


def _utc(frame: pd.DataFrame, col: str) -> pd.Series:
    raw = frame.get(col, pd.Series(pd.NaT, index=frame.index))
    return pd.to_datetime(raw, errors="coerce", utc=True)


def _bool(frame: pd.DataFrame, col: str) -> pd.Series:
    raw = frame.get(col, pd.Series(False, index=frame.index))
    return raw.fillna(False).astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _normalize_k_rate(values: pd.Series) -> pd.Series:
    out = pd.to_numeric(values, errors="coerce").astype(float)
    out = out.where(out <= 1.0, out / 100.0)
    return out.where(out.between(0.05, 0.45))


def neutral_opponent_projection(projection: float, opponent_k_rate: float) -> float:
    """Analytically remove the frozen opponent K-rate multiplier from a K mean.

    Both production K paths use sqrt(pitcher_k_rate * opponent_k_rate), so replacing
    the saved opponent rate with the league baseline scales the mean by
    sqrt(LEAGUE_K_RATE / opponent_k_rate). No final outcome is used.
    """
    projection = float(projection)
    opponent_k_rate = float(opponent_k_rate)
    if not np.isfinite(projection) or not np.isfinite(opponent_k_rate) or opponent_k_rate <= 0:
        return float("nan")
    return float(projection * math.sqrt(LEAGUE_K_RATE / opponent_k_rate))


def _quality_band(value: object) -> str:
    x = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(x):
        return "UNKNOWN"
    x = float(x)
    if x < 60:
        return "<60"
    if x < 70:
        return "60–69"
    if x < 80:
        return "70–79"
    if x < 90:
        return "80–89"
    return "90+"


def _environment(delta_pp: float) -> str:
    if not np.isfinite(delta_pp):
        return "UNKNOWN"
    if delta_pp <= -1.5:
        return "SUPPRESSIVE ≤-1.5pp"
    if delta_pp < -0.5:
        return "SLIGHT SUPPRESSIVE"
    if delta_pp <= 0.5:
        return "NEUTRAL ±0.5pp"
    if delta_pp < 1.5:
        return "SLIGHT FAVORABLE"
    return "FAVORABLE ≥+1.5pp"


def _direction(delta_k: float) -> str:
    if not np.isfinite(delta_k):
        return "UNKNOWN"
    if delta_k > 0.03:
        return "BOOST"
    if delta_k < -0.03:
        return "REDUCE"
    return "NEUTRAL"


def _magnitude(delta_k: float) -> str:
    if not np.isfinite(delta_k):
        return "UNKNOWN"
    x = abs(delta_k)
    if x < 0.10:
        return "<0.10 K"
    if x < 0.25:
        return "0.10–0.24 K"
    if x < 0.50:
        return "0.25–0.49 K"
    return "0.50+ K"


def build_detail(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    work = frame.copy()
    captured = _utc(work, "captured_at_utc")
    game_time = _utc(work, "game_time")
    resolved = _utc(work, "resolved_at_utc")
    projection = _num(work, "projection")
    actual = _num(work, "actual_strikeouts")
    rate = _normalize_k_rate(_num(work, "opponent_k_pct"))
    matchup_pa = _num(work, "matchup_pa")
    matchup_batters = _num(work, "matchup_batters")
    quality = _num(work, "data_quality")
    lineup_confirmed = _bool(work, "lineup_confirmed")

    rows: list[dict[str, object]] = []
    for pos, (_, row) in enumerate(work.iterrows()):
        cap = captured.iloc[pos]
        first_pitch = game_time.iloc[pos]
        done = resolved.iloc[pos]
        proj = projection.iloc[pos]
        outcome = actual.iloc[pos]
        opp_rate = rate.iloc[pos]

        if pd.isna(cap) or pd.isna(first_pitch):
            lineage = "TIMESTAMP_UNKNOWN"
        elif cap >= first_pitch:
            lineage = "POST_START_CAPTURE"
        elif pd.isna(done) or pd.isna(outcome):
            lineage = "UNRESOLVED"
        elif done <= first_pitch:
            lineage = "INVALID_RESOLUTION_TIME"
        else:
            lineage = "PRE_GAME_RESOLVED"

        neutral = neutral_opponent_projection(proj, opp_rate) if pd.notna(proj) and pd.notna(opp_rate) else np.nan
        adjustment = float(proj - neutral) if pd.notna(proj) and np.isfinite(neutral) else np.nan
        delta_pp = float((opp_rate - LEAGUE_K_RATE) * 100.0) if pd.notna(opp_rate) else np.nan
        informative = bool(pd.notna(opp_rate) and abs(float(opp_rate) - LEAGUE_K_RATE) >= MIN_INFORMATIVE_RATE_DELTA)
        authentic = bool(lineage == "PRE_GAME_RESOLVED" and pd.notna(proj) and pd.notna(outcome) and pd.notna(opp_rate))
        auditable = bool(authentic and informative and np.isfinite(neutral))

        if auditable:
            applied_error = float(proj - outcome)
            neutral_error = float(neutral - outcome)
            applied_abs = abs(applied_error)
            neutral_abs = abs(neutral_error)
            applied_win = bool(applied_abs < neutral_abs - 1e-12)
            neutral_win = bool(neutral_abs < applied_abs - 1e-12)
            tie = bool(not applied_win and not neutral_win)
        else:
            applied_error = neutral_error = applied_abs = neutral_abs = np.nan
            applied_win = neutral_win = tie = False

        rows.append({
            "game_date": str(row.get("game_date", "")),
            "game_pk": row.get("game_pk"),
            "pitcher_id": row.get("pitcher_id"),
            "player": row.get("player"),
            "team": row.get("team"),
            "opponent": row.get("opponent"),
            "Captured_At_UTC": cap,
            "Game_Time_UTC": first_pitch,
            "Resolved_At_UTC": done,
            "Lineage": lineage,
            "Opponent_K_Rate": opp_rate,
            "Opponent_K_Delta_PP": delta_pp,
            "Matchup_PA": matchup_pa.iloc[pos],
            "Matchup_Batters": matchup_batters.iloc[pos],
            "Lineup_State": "CONFIRMED" if bool(lineup_confirmed.iloc[pos]) else "PROJECTED/ROSTER",
            "Data_Quality": quality.iloc[pos],
            "Quality_Band": _quality_band(quality.iloc[pos]),
            "Matchup_Environment": _environment(delta_pp),
            "Applied_Projection": proj,
            "Neutral_Opponent_Projection": neutral,
            "Matchup_Adjustment_K": adjustment,
            "Adjustment_Direction": _direction(adjustment),
            "Adjustment_Magnitude_Band": _magnitude(adjustment),
            "Informative_Adjustment": informative,
            "Actual_Strikeouts": outcome,
            "Applied_Absolute_Error": applied_abs,
            "Neutral_Absolute_Error": neutral_abs,
            "Applied_Error": applied_error,
            "Neutral_Error": neutral_error,
            "Applied_Win": applied_win,
            "Neutral_Win": neutral_win,
            "Tie": tie,
            "Auditable": auditable,
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Validation_Version": VERSION,
        })

    return pd.DataFrame(rows, columns=DETAIL_COLUMNS)


def _metrics(group: pd.DataFrame) -> dict[str, object]:
    if group is None or group.empty:
        auditable = pd.DataFrame(columns=DETAIL_COLUMNS)
        authentic_n = 0
    else:
        authentic_n = int(group["Lineage"].eq("PRE_GAME_RESOLVED").sum())
        auditable = group.loc[group["Auditable"].fillna(False).astype(bool)].copy()
    n = int(len(auditable))
    days = int(auditable["game_date"].replace("", np.nan).dropna().astype(str).nunique()) if n else 0
    opponents = int(auditable["opponent"].replace("", np.nan).dropna().astype(str).nunique()) if n else 0
    if n:
        applied_mae = float(_num(auditable, "Applied_Absolute_Error").mean())
        neutral_mae = float(_num(auditable, "Neutral_Absolute_Error").mean())
        rel = float((neutral_mae - applied_mae) / neutral_mae) if neutral_mae > 0 else np.nan
        app_win = float(auditable["Applied_Win"].fillna(False).astype(bool).mean())
        neutral_win = float(auditable["Neutral_Win"].fillna(False).astype(bool).mean())
        tie = float(auditable["Tie"].fillna(False).astype(bool).mean())
        app_bias = float(_num(auditable, "Applied_Error").mean())
        neutral_bias = float(_num(auditable, "Neutral_Error").mean())
        adjustment = float(_num(auditable, "Matchup_Adjustment_K").abs().mean())
    else:
        applied_mae = neutral_mae = rel = app_win = neutral_win = tie = app_bias = neutral_bias = adjustment = np.nan
    return {
        "Rows": int(0 if group is None else len(group)),
        "Authentic_Pregame_Resolved": authentic_n,
        "Auditable_Starts": n,
        "Observed_Days": days,
        "Distinct_Opponents": opponents,
        "Applied_MAE": applied_mae,
        "Neutral_MAE": neutral_mae,
        "Relative_MAE_Improvement": rel,
        "Applied_Win_Share": app_win,
        "Neutral_Win_Share": neutral_win,
        "Tie_Share": tie,
        "Applied_Bias": app_bias,
        "Neutral_Bias": neutral_bias,
        "Mean_Absolute_Adjustment_K": adjustment,
    }


def _status(metrics: dict[str, object]) -> tuple[str, str, str, bool]:
    n = int(metrics["Auditable_Starts"])
    days = int(metrics["Observed_Days"])
    opponents = int(metrics["Distinct_Opponents"])
    rel = metrics["Relative_MAE_Improvement"]
    win = metrics["Applied_Win_Share"]
    app_bias = metrics["Applied_Bias"]
    neutral_bias = metrics["Neutral_Bias"]

    if n < MIN_EVAL_STARTS or days < MIN_EVAL_DAYS or opponents < MIN_EVAL_OPPONENTS:
        return (
            "LEARNING",
            f"Need at least {MIN_EVAL_STARTS} informative starts, {MIN_EVAL_DAYS} observed days, and {MIN_EVAL_OPPONENTS} opponents; have {n}, {days}, and {opponents}.",
            "KEEP_CURRENT_AND_LEARN",
            False,
        )

    bias_ok = bool(
        pd.notna(app_bias)
        and pd.notna(neutral_bias)
        and abs(float(app_bias)) <= abs(float(neutral_bias)) + BIAS_TOLERANCE
    )
    if pd.isna(rel) or pd.isna(win) or float(rel) < 0.0 or float(win) < 0.50 or not bias_ok:
        return (
            "CAUTION",
            "Enough authentic matchup volume exists, but the applied opponent adjustment does not clear MAE, head-to-head, or bias guardrails versus a neutral-opponent counterfactual.",
            "MANUAL_REVIEW_DO_NOT_RETUNE_AUTOMATICALLY",
            False,
        )

    strong = bool(
        n >= STRONG_STARTS
        and days >= STRONG_DAYS
        and opponents >= STRONG_OPPONENTS
        and float(rel) >= STRONG_RELATIVE_MAE
        and float(win) >= STRONG_WIN_SHARE
        and bias_ok
    )
    if strong:
        return (
            "STRONG EVIDENCE",
            "Large, time-diverse sample shows the frozen opponent adjustment beats the neutral-opponent ablation on MAE, head-to-head wins, and bias guardrails.",
            "MANUAL_REVIEW_READY",
            True,
        )

    if float(rel) >= MIN_RELATIVE_MAE and float(win) >= MIN_WIN_SHARE and bias_ok:
        return (
            "SUPPORTED",
            "Authentic matchup sample clears the minimum MAE, head-to-head win-share, and bias guardrails versus the neutral-opponent ablation.",
            "KEEP_CURRENT_MATCHUP",
            False,
        )

    return (
        "CAUTION",
        "The sample is large enough to evaluate, but the opponent adjustment does not clear every support threshold.",
        "KEEP_CURRENT_PENDING_MANUAL_REVIEW",
        False,
    )


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    metrics = _metrics(detail)
    status, reason, action, _ = _status(metrics)
    row = {
        "Metric": "STRIKEOUTS",
        "Resolved_Rows": int(detail["Actual_Strikeouts"].notna().sum()) if detail is not None and not detail.empty else 0,
        **{k: v for k, v in metrics.items() if k != "Rows"},
        "Evidence_Status": status,
        "Reason": reason,
        "Recommended_Action": action,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VERSION,
    }
    return pd.DataFrame([row], columns=SUMMARY_COLUMNS)


def build_segments(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty:
        return pd.DataFrame(columns=SEGMENT_COLUMNS)
    rows: list[dict[str, object]] = []

    def add(dimension: str, segment: str, group: pd.DataFrame) -> None:
        metrics = _metrics(group)
        status, reason, _, _ = _status(metrics)
        rows.append({
            "Dimension": dimension,
            "Segment": segment,
            **metrics,
            "Evidence": status,
            "Reason": reason,
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Validation_Version": VERSION,
        })

    add("OVERALL", "ALL MATCHUP ROWS", detail)
    for dimension, column in (
        ("LINEAGE", "Lineage"),
        ("MATCHUP ENVIRONMENT", "Matchup_Environment"),
        ("ADJUSTMENT DIRECTION", "Adjustment_Direction"),
        ("ADJUSTMENT MAGNITUDE", "Adjustment_Magnitude_Band"),
        ("LINEUP STATE", "Lineup_State"),
        ("QUALITY BAND", "Quality_Band"),
    ):
        values = detail[column].fillna("UNKNOWN").astype(str)
        for segment in sorted(values.unique()):
            add(dimension, segment, detail.loc[values.eq(segment)].copy())
    return pd.DataFrame(rows, columns=SEGMENT_COLUMNS)


def evaluate_gate(detail: pd.DataFrame) -> pd.DataFrame:
    metrics = _metrics(detail)
    status, reason, action, review_ready = _status(metrics)
    row = {
        "Evidence_Status": status,
        **{k: v for k, v in metrics.items() if k not in {"Rows", "Authentic_Pregame_Resolved"}},
        "Reason": reason,
        "Recommended_Action": action,
        "Manual_Review_Ready": review_ready,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VERSION,
    }
    return pd.DataFrame([row], columns=GATE_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only opponent K matchup analytic-ablation validation")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/opponent_matchup_validation_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/opponent_matchup_validation_summary.csv"))
    parser.add_argument("--segments", type=Path, default=Path("data/opponent_matchup_validation_segments.csv"))
    parser.add_argument("--gate", type=Path, default=Path("data/opponent_matchup_validation_gate.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("No projection history available")
    detail = build_detail(history)
    summary = summarize(detail)
    segments = build_segments(detail)
    gate = evaluate_gate(detail)
    for path in (args.detail, args.summary, args.segments, args.gate):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    segments.to_csv(args.segments, index=False)
    gate.to_csv(args.gate, index=False)
    print(summary.to_string(index=False))
    print(gate.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()

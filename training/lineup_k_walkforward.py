from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "lineup-k-walkforward-v2-lineage-safe-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
LINEUP_CONFIRMED = "CONFIRMED_LINEUP"

MIN_PRIOR_PAIRED = 20
MIN_EVAL_STARTS = 30
MIN_EVAL_DAYS = 10
MIN_EVAL_OPPONENTS = 8
STRONG_STARTS = 75
STRONG_DAYS = 20
STRONG_OPPONENTS = 15
MIN_RELATIVE_MAE = 0.005
STRONG_RELATIVE_MAE = 0.01
MIN_WIN_SHARE = 0.52
STRONG_WIN_SHARE = 0.55
BIAS_TOLERANCE = 0.05

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "Lineup_Source", "Lineup_Confirmed", "Lineup_Batters", "Lineup_Hash",
    "Lineup_Captured_At_UTC", "Game_Time_UTC", "Resolved_At_UTC",
    "Lineage", "Outcome_Lineage", "Authentic_Pregame_Pair",
    "Prior_Paired_Starts", "OOS_Eligible",
    "Preconfirm_Projection", "Confirmed_Projection", "Projection_Delta",
    "Opponent_K_Delta", "Projection_Delta_Direction", "Projection_Delta_Band",
    "Data_Quality", "Quality_Band", "Starter_History_Games", "Starter_History_Band",
    "Actual_Strikeouts", "Preconfirm_Absolute_Error", "Confirmed_Absolute_Error",
    "Preconfirm_Error", "Confirmed_Error", "Confirmed_Win", "Confirmed_Loss",
    "Report_Only", "Production_Authority", "Validation_Version",
]

SUMMARY_COLUMNS = [
    "Metric", "Paired_Starts", "Authentic_Pregame_Pairs", "OOS_Paired_Starts",
    "Observed_Days", "Distinct_Opponents", "Preconfirm_MAE", "Confirmed_MAE",
    "Relative_MAE_Improvement", "Confirmed_Win_Share", "Confirmed_Loss_Share",
    "Preconfirm_Bias", "Confirmed_Bias", "Mean_Absolute_Projection_Delta",
    "Status", "Reason", "Report_Only", "Production_Authority", "Validation_Version",
]

SEGMENT_COLUMNS = [
    "Dimension", "Segment", "Rows", "Authentic_Pregame_Pairs", "OOS_Paired_Starts",
    "Observed_Days", "Distinct_Opponents", "Preconfirm_MAE", "Confirmed_MAE",
    "Relative_MAE_Improvement", "Confirmed_Win_Share", "Confirmed_Loss_Share",
    "Preconfirm_Bias", "Confirmed_Bias", "Mean_Absolute_Projection_Delta",
    "Evidence", "Reason", "Report_Only", "Production_Authority", "Validation_Version",
]

GATE_COLUMNS = [
    "Evidence_Status", "Paired_Starts", "Authentic_Pregame_Pairs", "OOS_Paired_Starts",
    "Observed_Days", "Distinct_Opponents", "Preconfirm_MAE", "Confirmed_MAE",
    "Relative_MAE_Improvement", "Confirmed_Win_Share", "Confirmed_Loss_Share",
    "Preconfirm_Bias", "Confirmed_Bias", "Mean_Absolute_Projection_Delta",
    "Reason", "Manual_Review_Ready", "Recommended_Action",
    "Report_Only", "Production_Authority", "Validation_Version",
]


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[col], errors="coerce")


def _truthy_series(frame: pd.DataFrame, col: str) -> pd.Series:
    raw = frame.get(col, pd.Series(False, index=frame.index))
    return raw.fillna(False).astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _utc_series(frame: pd.DataFrame, col: str) -> pd.Series:
    raw = frame.get(col, pd.Series(pd.NaT, index=frame.index))
    return pd.to_datetime(raw, errors="coerce", utc=True)


def _quality_band(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    value_f = float(number)
    if value_f < 60:
        return "<60"
    if value_f < 70:
        return "60–69"
    if value_f < 80:
        return "70–79"
    if value_f < 90:
        return "80–89"
    return "90+"


def _history_band(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    value_f = float(number)
    if value_f < 3:
        return "0–2"
    if value_f < 6:
        return "3–5"
    if value_f < 10:
        return "6–9"
    return "10+"


def _delta_direction(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    if float(number) > 0.01:
        return "UP"
    if float(number) < -0.01:
        return "DOWN"
    return "NEUTRAL"


def _delta_band(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    magnitude = abs(float(number))
    if magnitude < 0.05:
        return "<0.05 K"
    if magnitude < 0.15:
        return "0.05–0.14 K"
    if magnitude < 0.30:
        return "0.15–0.29 K"
    return "0.30+ K"


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    work = frame.copy()
    work["_game_time"] = _utc_series(work, "game_time")
    work["_lineup_capture"] = _utc_series(work, "lineup_captured_at_utc")
    work["_resolved"] = _utc_series(work, "resolved_at_utc")
    work["_pre"] = _num(work, "lineup_preconfirm_projection")
    work["_post"] = _num(work, "projection")
    work["_actual"] = _num(work, "actual_strikeouts")
    work["_lineup_batters"] = _num(work, "lineup_batters")
    work["_data_quality"] = _num(work, "data_quality")
    work["_starter_history"] = _num(work, "starter_history_games")
    work["_opp_k_delta"] = _num(work, "lineup_opponent_k_delta")
    work["_confirmed"] = _truthy_series(work, "lineup_confirmed")
    work["_source"] = work.get("lineup_source", pd.Series("", index=work.index)).fillna("").astype(str)
    work["_hash"] = work.get("lineup_hash", pd.Series("", index=work.index)).fillna("").astype(str).str.strip()

    lineage: list[str] = []
    outcome_lineage: list[str] = []
    authentic_pair: list[bool] = []

    for idx in work.index:
        confirmed = bool(work.at[idx, "_confirmed"])
        source = str(work.at[idx, "_source"])
        batters = work.at[idx, "_lineup_batters"]
        fingerprint = str(work.at[idx, "_hash"])
        capture = work.at[idx, "_lineup_capture"]
        game_time = work.at[idx, "_game_time"]
        resolved = work.at[idx, "_resolved"]

        if not confirmed:
            line = "UNCONFIRMED"
        elif source != LINEUP_CONFIRMED:
            line = "SOURCE_MISMATCH"
        elif pd.isna(batters) or int(batters) < 9:
            line = "INCOMPLETE_LINEUP"
        elif not fingerprint:
            line = "MISSING_FINGERPRINT"
        elif pd.isna(capture) or pd.isna(game_time):
            line = "TIMESTAMP_UNKNOWN"
        elif capture >= game_time:
            line = "POST_START_CAPTURE"
        else:
            line = "PRE_GAME_CAPTURE"

        if pd.isna(resolved):
            outcome = "UNRESOLVED"
        elif pd.isna(game_time):
            outcome = "GAME_TIME_UNKNOWN"
        elif resolved <= game_time:
            outcome = "INVALID_RESOLUTION_TIME"
        else:
            outcome = "RESOLVED_AFTER_START"

        paired = bool(
            line == "PRE_GAME_CAPTURE"
            and outcome == "RESOLVED_AFTER_START"
            and pd.notna(work.at[idx, "_pre"])
            and pd.notna(work.at[idx, "_post"])
            and pd.notna(work.at[idx, "_actual"])
        )
        lineage.append(line)
        outcome_lineage.append(outcome)
        authentic_pair.append(paired)

    work["_lineage"] = lineage
    work["_outcome_lineage"] = outcome_lineage
    work["_authentic_pair"] = authentic_pair
    return work


def build_oos_detail(frame: pd.DataFrame) -> pd.DataFrame:
    work = _prepare(frame)
    if work.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    rows: list[dict[str, object]] = []
    for _, row in work.iterrows():
        target_capture = row["_lineup_capture"]
        target_game_time = row["_game_time"]
        prior_n = 0
        if bool(row["_authentic_pair"]) and pd.notna(target_capture) and pd.notna(target_game_time):
            prior_mask = (
                work["_authentic_pair"].fillna(False).astype(bool)
                & work["_game_time"].notna()
                & work["_game_time"].lt(target_game_time)
                & work["_resolved"].notna()
                & work["_resolved"].le(target_capture)
            )
            prior_n = int(prior_mask.sum())

        pre = row["_pre"]
        post = row["_post"]
        actual = row["_actual"]
        paired = bool(row["_authentic_pair"])
        oos = bool(paired and prior_n >= MIN_PRIOR_PAIRED)
        projection_delta = float(post - pre) if pd.notna(pre) and pd.notna(post) else np.nan
        pre_err = float(pre - actual) if paired else np.nan
        post_err = float(post - actual) if paired else np.nan

        rows.append({
            "game_date": str(row.get("game_date", "")),
            "game_pk": row.get("game_pk"),
            "pitcher_id": row.get("pitcher_id"),
            "player": row.get("player"),
            "team": row.get("team"),
            "opponent": row.get("opponent"),
            "Lineup_Source": str(row.get("lineup_source", "")),
            "Lineup_Confirmed": bool(row["_confirmed"]),
            "Lineup_Batters": row["_lineup_batters"],
            "Lineup_Hash": str(row.get("lineup_hash", "") or ""),
            "Lineup_Captured_At_UTC": row["_lineup_capture"],
            "Game_Time_UTC": row["_game_time"],
            "Resolved_At_UTC": row["_resolved"],
            "Lineage": row["_lineage"],
            "Outcome_Lineage": row["_outcome_lineage"],
            "Authentic_Pregame_Pair": paired,
            "Prior_Paired_Starts": prior_n,
            "OOS_Eligible": oos,
            "Preconfirm_Projection": pre,
            "Confirmed_Projection": post,
            "Projection_Delta": projection_delta,
            "Opponent_K_Delta": row["_opp_k_delta"],
            "Projection_Delta_Direction": _delta_direction(projection_delta),
            "Projection_Delta_Band": _delta_band(projection_delta),
            "Data_Quality": row["_data_quality"],
            "Quality_Band": _quality_band(row["_data_quality"]),
            "Starter_History_Games": row["_starter_history"],
            "Starter_History_Band": _history_band(row["_starter_history"]),
            "Actual_Strikeouts": actual,
            "Preconfirm_Absolute_Error": abs(pre_err) if paired else np.nan,
            "Confirmed_Absolute_Error": abs(post_err) if paired else np.nan,
            "Preconfirm_Error": pre_err,
            "Confirmed_Error": post_err,
            "Confirmed_Win": bool(abs(post_err) < abs(pre_err)) if paired else False,
            "Confirmed_Loss": bool(abs(post_err) > abs(pre_err)) if paired else False,
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Validation_Version": VERSION,
        })

    return pd.DataFrame(rows, columns=DETAIL_COLUMNS)


def _evidence_status(
    n: int,
    days: int,
    opponents: int,
    rel: float,
    win: float,
    pre_bias: float,
    post_bias: float,
) -> tuple[str, str]:
    if n < MIN_EVAL_STARTS or days < MIN_EVAL_DAYS or opponents < MIN_EVAL_OPPONENTS:
        return (
            "LEARNING",
            f"Need at least {MIN_EVAL_STARTS} OOS pairs, {MIN_EVAL_DAYS} observed days, "
            f"and {MIN_EVAL_OPPONENTS} opponents; have {n}, {days}, and {opponents}.",
        )

    bias_ok = (
        pd.notna(pre_bias)
        and pd.notna(post_bias)
        and abs(float(post_bias)) <= abs(float(pre_bias)) + BIAS_TOLERANCE
    )
    if (
        not pd.notna(rel)
        or float(rel) < 0.0
        or not pd.notna(win)
        or float(win) < 0.50
        or not bias_ok
    ):
        return (
            "CAUTION",
            "Enough authentic walk-forward volume exists, but confirmed-lineup updates "
            "do not clear the MAE, win-share, or bias guardrails.",
        )

    strong = (
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
            "Large, time-diverse authentic sample clears MAE, win-share, and bias guardrails.",
        )

    supported = (
        float(rel) >= MIN_RELATIVE_MAE
        and float(win) >= MIN_WIN_SHARE
        and bias_ok
    )
    if supported:
        return (
            "SUPPORTED",
            "Authentic walk-forward sample clears the minimum MAE, win-share, and bias guardrails.",
        )

    return (
        "CAUTION",
        "Sample is large enough to evaluate, but the confirmed-lineup signal does not clear every support guardrail.",
    )


def _metrics(group: pd.DataFrame) -> dict[str, object]:
    if group is None or group.empty:
        return {
            "Rows": 0,
            "Authentic_Pregame_Pairs": 0,
            "OOS_Paired_Starts": 0,
            "Observed_Days": 0,
            "Distinct_Opponents": 0,
            "Preconfirm_MAE": np.nan,
            "Confirmed_MAE": np.nan,
            "Relative_MAE_Improvement": np.nan,
            "Confirmed_Win_Share": np.nan,
            "Confirmed_Loss_Share": np.nan,
            "Preconfirm_Bias": np.nan,
            "Confirmed_Bias": np.nan,
            "Mean_Absolute_Projection_Delta": np.nan,
        }

    authentic = group.loc[
        group.get("Authentic_Pregame_Pair", pd.Series(False, index=group.index)).fillna(False).astype(bool)
    ].copy()
    oos = group.loc[
        group.get("OOS_Eligible", pd.Series(False, index=group.index)).fillna(False).astype(bool)
    ].copy()
    n = int(len(oos))
    days = int(oos.get("game_date", pd.Series(dtype=object)).dropna().astype(str).nunique()) if n else 0
    opponents = int(oos.get("opponent", pd.Series(dtype=object)).replace("", np.nan).dropna().astype(str).nunique()) if n else 0

    if n:
        pre_abs = _num(oos, "Preconfirm_Absolute_Error")
        post_abs = _num(oos, "Confirmed_Absolute_Error")
        pre_err = _num(oos, "Preconfirm_Error")
        post_err = _num(oos, "Confirmed_Error")
        pre_mae = float(pre_abs.mean())
        post_mae = float(post_abs.mean())
        rel = float((pre_mae - post_mae) / pre_mae) if pre_mae > 0 else np.nan
        win = float(oos["Confirmed_Win"].fillna(False).astype(bool).mean())
        loss = float(oos["Confirmed_Loss"].fillna(False).astype(bool).mean())
        pre_bias = float(pre_err.mean())
        post_bias = float(post_err.mean())
        delta = float(_num(oos, "Projection_Delta").abs().mean())
    else:
        pre_mae = post_mae = rel = win = loss = pre_bias = post_bias = delta = np.nan

    return {
        "Rows": int(len(group)),
        "Authentic_Pregame_Pairs": int(len(authentic)),
        "OOS_Paired_Starts": n,
        "Observed_Days": days,
        "Distinct_Opponents": opponents,
        "Preconfirm_MAE": pre_mae,
        "Confirmed_MAE": post_mae,
        "Relative_MAE_Improvement": rel,
        "Confirmed_Win_Share": win,
        "Confirmed_Loss_Share": loss,
        "Preconfirm_Bias": pre_bias,
        "Confirmed_Bias": post_bias,
        "Mean_Absolute_Projection_Delta": delta,
    }


def summarize_oos(detail: pd.DataFrame) -> pd.DataFrame:
    metrics = _metrics(detail)
    status, reason = _evidence_status(
        int(metrics["OOS_Paired_Starts"]),
        int(metrics["Observed_Days"]),
        int(metrics["Distinct_Opponents"]),
        float(metrics["Relative_MAE_Improvement"]),
        float(metrics["Confirmed_Win_Share"]),
        float(metrics["Preconfirm_Bias"]),
        float(metrics["Confirmed_Bias"]),
    )
    paired_mask = (
        _num(detail, "Preconfirm_Projection").notna()
        & _num(detail, "Confirmed_Projection").notna()
        & _num(detail, "Actual_Strikeouts").notna()
    ) if detail is not None and not detail.empty else pd.Series(dtype=bool)
    row = {
        "Metric": "STRIKEOUTS",
        "Paired_Starts": int(paired_mask.sum()),
        **{key: value for key, value in metrics.items() if key != "Rows"},
        "Status": status,
        "Reason": reason,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VERSION,
    }
    return pd.DataFrame([row], columns=SUMMARY_COLUMNS)


def build_segment_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty:
        return pd.DataFrame(columns=SEGMENT_COLUMNS)

    rows: list[dict[str, object]] = []

    def add(dimension: str, segment: str, group: pd.DataFrame) -> None:
        metrics = _metrics(group)
        status, reason = _evidence_status(
            int(metrics["OOS_Paired_Starts"]),
            int(metrics["Observed_Days"]),
            int(metrics["Distinct_Opponents"]),
            float(metrics["Relative_MAE_Improvement"]),
            float(metrics["Confirmed_Win_Share"]),
            float(metrics["Preconfirm_Bias"]),
            float(metrics["Confirmed_Bias"]),
        )
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

    add("OVERALL", "ALL CONFIRMED LINEUP PAIRS", detail)

    for dimension, column in (
        ("LINEAGE", "Lineage"),
        ("OUTCOME LINEAGE", "Outcome_Lineage"),
        ("PROJECTION DELTA DIRECTION", "Projection_Delta_Direction"),
        ("PROJECTION DELTA BAND", "Projection_Delta_Band"),
        ("QUALITY BAND", "Quality_Band"),
        ("STARTER HISTORY BAND", "Starter_History_Band"),
    ):
        values = detail.get(column, pd.Series(dtype=object)).fillna("UNKNOWN").astype(str)
        for segment in sorted(values.unique().tolist()):
            add(dimension, segment, detail.loc[values.eq(segment)].copy())

    return pd.DataFrame(rows, columns=SEGMENT_COLUMNS)


def evaluate_gate(detail: pd.DataFrame) -> pd.DataFrame:
    summary = summarize_oos(detail).iloc[0]
    status = str(summary["Status"])
    if status == "STRONG EVIDENCE":
        action = "MANUAL_REVIEW_READY"
        review_ready = True
    elif status == "SUPPORTED":
        action = "KEEP_AND_MONITOR"
        review_ready = False
    elif status == "CAUTION":
        action = "MANUAL_REVIEW"
        review_ready = False
    else:
        action = "KEEP_LEARNING"
        review_ready = False

    row = {
        "Evidence_Status": status,
        "Paired_Starts": int(summary["Paired_Starts"]),
        "Authentic_Pregame_Pairs": int(summary["Authentic_Pregame_Pairs"]),
        "OOS_Paired_Starts": int(summary["OOS_Paired_Starts"]),
        "Observed_Days": int(summary["Observed_Days"]),
        "Distinct_Opponents": int(summary["Distinct_Opponents"]),
        "Preconfirm_MAE": summary["Preconfirm_MAE"],
        "Confirmed_MAE": summary["Confirmed_MAE"],
        "Relative_MAE_Improvement": summary["Relative_MAE_Improvement"],
        "Confirmed_Win_Share": summary["Confirmed_Win_Share"],
        "Confirmed_Loss_Share": summary["Confirmed_Loss_Share"],
        "Preconfirm_Bias": summary["Preconfirm_Bias"],
        "Confirmed_Bias": summary["Confirmed_Bias"],
        "Mean_Absolute_Projection_Delta": summary["Mean_Absolute_Projection_Delta"],
        "Reason": summary["Reason"],
        "Manual_Review_Ready": review_ready,
        "Recommended_Action": action,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VERSION,
    }
    return pd.DataFrame([row], columns=GATE_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lineage-safe chronological report-only lineup-confirmation K validation"
    )
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/lineup_k_walkforward_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/lineup_k_walkforward_summary.csv"))
    parser.add_argument("--segments", type=Path, default=Path("data/lineup_k_walkforward_segments.csv"))
    parser.add_argument("--gate", type=Path, default=Path("data/lineup_k_walkforward_gate.csv"))
    args = parser.parse_args()

    log = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if log.empty:
        raise SystemExit("No projection history available")

    detail = build_oos_detail(log)
    summary = summarize_oos(detail)
    segments = build_segment_summary(detail)
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

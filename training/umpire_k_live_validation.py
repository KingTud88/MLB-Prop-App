from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "umpire-k-live-validation-v1-lineage-safe-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
EXPECTED_SOURCE = "MLB_LIVE_FEED_PREGAME"
EXPECTED_STATUS = "AUDITABLE"

MIN_EVAL_STARTS = 30
MIN_EVAL_DAYS = 10
MIN_EVAL_UMPIRES = 8
STRONG_STARTS = 75
STRONG_DAYS = 20
STRONG_UMPIRES = 15
MIN_RELATIVE_MAE = 0.005
STRONG_RELATIVE_MAE = 0.01
MIN_WIN_SHARE = 0.52
STRONG_WIN_SHARE = 0.55
BIAS_TOLERANCE = 0.05

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "umpire_id", "umpire_name", "Umpire_Source", "Umpire_Captured_At_UTC",
    "Game_Time_UTC", "Resolved_At_UTC", "Lineage", "Outcome_Lineage",
    "Authentic_Pregame_Candidate", "OOS_Eligible", "Prior_Umpire_Games",
    "Prior_Umpire_BF", "Candidate_Status", "Candidate_Version",
    "Candidate_Factor", "Factor_Delta", "Factor_Direction", "Factor_Delta_Band",
    "Prior_Umpire_Games_Band", "Data_Quality", "Quality_Band",
    "Starter_History_Games", "Starter_History_Band", "Base_Projection",
    "Candidate_Projection", "Actual_Strikeouts", "Base_Absolute_Error",
    "Candidate_Absolute_Error", "Base_Error", "Candidate_Error",
    "Candidate_Win", "Candidate_Loss", "Report_Only", "Production_Authority",
    "Validation_Version",
]

SUMMARY_COLUMNS = [
    "Metric", "Captured_Candidates", "Authentic_Pregame_Candidates",
    "OOS_Eligible_Starts", "Observed_Days", "Distinct_Umpires", "Base_MAE",
    "UmpireCandidate_MAE", "Relative_MAE_Improvement", "Candidate_Win_Share",
    "Candidate_Loss_Share", "Base_Bias", "UmpireCandidate_Bias",
    "Mean_Absolute_Factor_Delta", "Status", "Reason", "Report_Only",
    "Production_Authority", "Validation_Version",
]

SEGMENT_COLUMNS = [
    "Dimension", "Segment", "Rows", "Authentic_Pregame_Candidates",
    "OOS_Eligible_Starts", "Observed_Days", "Distinct_Umpires", "Base_MAE",
    "UmpireCandidate_MAE", "Relative_MAE_Improvement", "Candidate_Win_Share",
    "Candidate_Loss_Share", "Base_Bias", "UmpireCandidate_Bias",
    "Mean_Absolute_Factor_Delta", "Evidence", "Reason", "Report_Only",
    "Production_Authority", "Validation_Version",
]

GATE_COLUMNS = [
    "Evidence_Status", "Captured_Candidates", "Authentic_Pregame_Candidates",
    "OOS_Eligible_Starts", "Observed_Days", "Distinct_Umpires", "Base_MAE",
    "UmpireCandidate_MAE", "Relative_MAE_Improvement", "Candidate_Win_Share",
    "Candidate_Loss_Share", "Base_Bias", "UmpireCandidate_Bias",
    "Mean_Absolute_Factor_Delta", "Reason", "Manual_Review_Ready",
    "Recommended_Action", "Report_Only", "Production_Authority",
    "Validation_Version",
]


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[col], errors="coerce")


def _utc(frame: pd.DataFrame, col: str) -> pd.Series:
    raw = frame.get(col, pd.Series(pd.NaT, index=frame.index))
    return pd.to_datetime(raw, errors="coerce", utc=True)


def _quality_band(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number): return "UNKNOWN"
    value_f = float(number)
    if value_f < 60: return "<60"
    if value_f < 70: return "60-69"
    if value_f < 80: return "70-79"
    if value_f < 90: return "80-89"
    return "90+"


def _history_band(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number): return "UNKNOWN"
    value_f = float(number)
    if value_f < 3: return "0-2"
    if value_f < 6: return "3-5"
    if value_f < 10: return "6-9"
    return "10+"


def _prior_games_band(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number): return "UNKNOWN"
    value_i = int(number)
    if value_i < 20: return "<20"
    if value_i < 30: return "20-29"
    if value_i < 40: return "30-39"
    return "40+"


def _factor_direction(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number): return "UNKNOWN"
    delta = float(number) - 1.0
    if delta > 0.001: return "K UP"
    if delta < -0.001: return "K DOWN"
    return "NEUTRAL"


def _factor_band(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number): return "UNKNOWN"
    magnitude = abs(float(number) - 1.0)
    if magnitude < 0.01: return "<1%"
    if magnitude < 0.02: return "1-1.9%"
    if magnitude < 0.04: return "2-3.9%"
    return "4%+"


def build_detail(projections: pd.DataFrame) -> pd.DataFrame:
    if projections is None or projections.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    work = projections.copy()
    work["_game_time"] = _utc(work, "game_time")
    work["_capture"] = _utc(work, "umpire_captured_at_utc")
    work["_resolved"] = _utc(work, "resolved_at_utc")
    work["_base"] = _num(work, "projection")
    work["_actual"] = _num(work, "actual_strikeouts")
    work["_factor"] = _num(work, "umpire_k_factor_candidate")
    work["_prior_games"] = _num(work, "umpire_prior_games")
    work["_prior_bf"] = _num(work, "umpire_prior_bf")
    work["_umpire_id"] = _num(work, "umpire_id")
    work["_data_quality"] = _num(work, "data_quality")
    work["_starter_history"] = _num(work, "starter_history_games")
    work["_source"] = work.get("umpire_source", pd.Series("", index=work.index)).fillna("").astype(str)
    work["_status"] = work.get("umpire_candidate_status", pd.Series("", index=work.index)).fillna("").astype(str)
    work["_version"] = work.get("umpire_candidate_version", pd.Series("", index=work.index)).fillna("").astype(str)
    work["_umpire_name"] = work.get("umpire_name", pd.Series("", index=work.index)).fillna("").astype(str).str.strip()

    rows: list[dict[str, object]] = []
    for _, row in work.iterrows():
        capture, game_time, resolved = row["_capture"], row["_game_time"], row["_resolved"]
        base, actual, factor = row["_base"], row["_actual"], row["_factor"]
        prior_games, umpire_id = row["_prior_games"], row["_umpire_id"]
        source, status, umpire_name = str(row["_source"]), str(row["_status"]), str(row["_umpire_name"])

        if pd.isna(umpire_id) or not umpire_name:
            lineage = "NO_UMPIRE_CAPTURE"
        elif source != EXPECTED_SOURCE:
            lineage = "SOURCE_MISMATCH"
        elif pd.isna(capture) or pd.isna(game_time):
            lineage = "TIMESTAMP_UNKNOWN"
        elif capture >= game_time:
            lineage = "POST_START_CAPTURE"
        else:
            lineage = "PRE_GAME_CAPTURE"

        if pd.isna(resolved):
            outcome_lineage = "UNRESOLVED"
        elif pd.isna(game_time):
            outcome_lineage = "GAME_TIME_UNKNOWN"
        elif resolved <= game_time:
            outcome_lineage = "INVALID_RESOLUTION_TIME"
        else:
            outcome_lineage = "RESOLVED_AFTER_START"

        authentic = bool(
            lineage == "PRE_GAME_CAPTURE"
            and outcome_lineage == "RESOLVED_AFTER_START"
            and status == EXPECTED_STATUS
            and pd.notna(prior_games) and int(prior_games) >= 20
            and pd.notna(base) and pd.notna(actual) and pd.notna(factor)
            and 0.94 <= float(factor) <= 1.06
        )
        candidate_projection = float(base) * float(factor) if authentic else np.nan
        base_error = float(base - actual) if authentic else np.nan
        candidate_error = float(candidate_projection - actual) if authentic else np.nan
        factor_delta = float(factor - 1.0) if pd.notna(factor) else np.nan

        rows.append({
            "game_date": str(row.get("game_date", "")), "game_pk": row.get("game_pk"),
            "pitcher_id": row.get("pitcher_id"), "player": row.get("player"),
            "team": row.get("team"), "opponent": row.get("opponent"),
            "umpire_id": umpire_id, "umpire_name": umpire_name, "Umpire_Source": source,
            "Umpire_Captured_At_UTC": capture, "Game_Time_UTC": game_time,
            "Resolved_At_UTC": resolved, "Lineage": lineage, "Outcome_Lineage": outcome_lineage,
            "Authentic_Pregame_Candidate": authentic, "OOS_Eligible": authentic,
            "Prior_Umpire_Games": prior_games, "Prior_Umpire_BF": row["_prior_bf"],
            "Candidate_Status": status, "Candidate_Version": str(row["_version"]),
            "Candidate_Factor": factor, "Factor_Delta": factor_delta,
            "Factor_Direction": _factor_direction(factor), "Factor_Delta_Band": _factor_band(factor),
            "Prior_Umpire_Games_Band": _prior_games_band(prior_games),
            "Data_Quality": row["_data_quality"], "Quality_Band": _quality_band(row["_data_quality"]),
            "Starter_History_Games": row["_starter_history"],
            "Starter_History_Band": _history_band(row["_starter_history"]),
            "Base_Projection": base, "Candidate_Projection": candidate_projection,
            "Actual_Strikeouts": actual,
            "Base_Absolute_Error": abs(base_error) if authentic else np.nan,
            "Candidate_Absolute_Error": abs(candidate_error) if authentic else np.nan,
            "Base_Error": base_error, "Candidate_Error": candidate_error,
            "Candidate_Win": bool(abs(candidate_error) < abs(base_error)) if authentic else False,
            "Candidate_Loss": bool(abs(candidate_error) > abs(base_error)) if authentic else False,
            "Report_Only": REPORT_ONLY, "Production_Authority": PRODUCTION_AUTHORITY,
            "Validation_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=DETAIL_COLUMNS)


def _metrics(group: pd.DataFrame) -> dict[str, object]:
    empty = {
        "Rows": 0, "Authentic_Pregame_Candidates": 0, "OOS_Eligible_Starts": 0,
        "Observed_Days": 0, "Distinct_Umpires": 0, "Base_MAE": np.nan,
        "UmpireCandidate_MAE": np.nan, "Relative_MAE_Improvement": np.nan,
        "Candidate_Win_Share": np.nan, "Candidate_Loss_Share": np.nan,
        "Base_Bias": np.nan, "UmpireCandidate_Bias": np.nan,
        "Mean_Absolute_Factor_Delta": np.nan,
    }
    if group is None or group.empty: return empty

    authentic = group.loc[group["Authentic_Pregame_Candidate"].fillna(False).astype(bool)].copy()
    oos = group.loc[group["OOS_Eligible"].fillna(False).astype(bool)].copy()
    n = int(len(oos))
    days = int(oos["game_date"].replace("", np.nan).dropna().astype(str).nunique()) if n else 0
    umpires = int(_num(oos, "umpire_id").dropna().astype(int).nunique()) if n else 0

    if n:
        base_abs, cand_abs = _num(oos, "Base_Absolute_Error"), _num(oos, "Candidate_Absolute_Error")
        base_err, cand_err = _num(oos, "Base_Error"), _num(oos, "Candidate_Error")
        base_mae, cand_mae = float(base_abs.mean()), float(cand_abs.mean())
        rel = float((base_mae - cand_mae) / base_mae) if base_mae > 0 else np.nan
        win = float(oos["Candidate_Win"].fillna(False).astype(bool).mean())
        loss = float(oos["Candidate_Loss"].fillna(False).astype(bool).mean())
        base_bias, cand_bias = float(base_err.mean()), float(cand_err.mean())
        factor_delta = float(_num(oos, "Candidate_Factor").sub(1.0).abs().mean())
    else:
        base_mae = cand_mae = rel = win = loss = base_bias = cand_bias = factor_delta = np.nan

    return {
        "Rows": int(len(group)), "Authentic_Pregame_Candidates": int(len(authentic)),
        "OOS_Eligible_Starts": n, "Observed_Days": days, "Distinct_Umpires": umpires,
        "Base_MAE": base_mae, "UmpireCandidate_MAE": cand_mae,
        "Relative_MAE_Improvement": rel, "Candidate_Win_Share": win,
        "Candidate_Loss_Share": loss, "Base_Bias": base_bias,
        "UmpireCandidate_Bias": cand_bias, "Mean_Absolute_Factor_Delta": factor_delta,
    }


def _evidence_status(n: int, days: int, umpires: int, rel: float, win: float, base_bias: float, cand_bias: float) -> tuple[str, str]:
    if n < MIN_EVAL_STARTS or days < MIN_EVAL_DAYS or umpires < MIN_EVAL_UMPIRES:
        return "LEARNING", f"Need at least {MIN_EVAL_STARTS} authentic OOS starts, {MIN_EVAL_DAYS} observed days, and {MIN_EVAL_UMPIRES} umpires; have {n}, {days}, and {umpires}."
    bias_ok = pd.notna(base_bias) and pd.notna(cand_bias) and abs(float(cand_bias)) <= abs(float(base_bias)) + BIAS_TOLERANCE
    if not pd.notna(rel) or float(rel) < 0.0 or not pd.notna(win) or float(win) < 0.50 or not bias_ok:
        return "CAUTION", "Enough authentic live-lineage volume exists, but the frozen umpire candidate does not clear the MAE, win-share, or bias guardrails."
    if n >= STRONG_STARTS and days >= STRONG_DAYS and umpires >= STRONG_UMPIRES and float(rel) >= STRONG_RELATIVE_MAE and float(win) >= STRONG_WIN_SHARE and bias_ok:
        return "STRONG EVIDENCE", "Large, time-diverse live pregame sample clears MAE, win-share, bias, and umpire-diversity guardrails."
    if float(rel) >= MIN_RELATIVE_MAE and float(win) >= MIN_WIN_SHARE and bias_ok:
        return "SUPPORTED", "Authentic live pregame sample clears the minimum MAE, win-share, and bias guardrails."
    return "CAUTION", "Sample is large enough to evaluate, but the umpire signal does not clear every support guardrail."


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    metrics = _metrics(detail)
    status, reason = _evidence_status(int(metrics["OOS_Eligible_Starts"]), int(metrics["Observed_Days"]), int(metrics["Distinct_Umpires"]), float(metrics["Relative_MAE_Improvement"]), float(metrics["Candidate_Win_Share"]), float(metrics["Base_Bias"]), float(metrics["UmpireCandidate_Bias"]))
    captured = 0 if detail is None or detail.empty else int((_num(detail, "umpire_id").notna() & detail["Umpire_Captured_At_UTC"].notna()).sum())
    row = {"Metric": "STRIKEOUTS", "Captured_Candidates": captured, **{k: v for k, v in metrics.items() if k != "Rows"}, "Status": status, "Reason": reason, "Report_Only": REPORT_ONLY, "Production_Authority": PRODUCTION_AUTHORITY, "Validation_Version": VERSION}
    return pd.DataFrame([row], columns=SUMMARY_COLUMNS)


def build_segment_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty: return pd.DataFrame(columns=SEGMENT_COLUMNS)
    rows: list[dict[str, object]] = []
    def add(dimension: str, segment: str, group: pd.DataFrame) -> None:
        metrics = _metrics(group)
        status, reason = _evidence_status(int(metrics["OOS_Eligible_Starts"]), int(metrics["Observed_Days"]), int(metrics["Distinct_Umpires"]), float(metrics["Relative_MAE_Improvement"]), float(metrics["Candidate_Win_Share"]), float(metrics["Base_Bias"]), float(metrics["UmpireCandidate_Bias"]))
        rows.append({"Dimension": dimension, "Segment": segment, **metrics, "Evidence": status, "Reason": reason, "Report_Only": REPORT_ONLY, "Production_Authority": PRODUCTION_AUTHORITY, "Validation_Version": VERSION})
    add("OVERALL", "ALL LIVE UMPIRE CANDIDATES", detail)
    for dimension, column in (("LINEAGE", "Lineage"), ("OUTCOME LINEAGE", "Outcome_Lineage"), ("FACTOR DIRECTION", "Factor_Direction"), ("FACTOR DELTA BAND", "Factor_Delta_Band"), ("PRIOR UMPIRE GAMES BAND", "Prior_Umpire_Games_Band"), ("QUALITY BAND", "Quality_Band"), ("STARTER HISTORY BAND", "Starter_History_Band")):
        values = detail[column].fillna("UNKNOWN").astype(str)
        for segment in sorted(values.unique().tolist()): add(dimension, segment, detail.loc[values.eq(segment)].copy())
    return pd.DataFrame(rows, columns=SEGMENT_COLUMNS)


def evaluate_gate(detail: pd.DataFrame) -> pd.DataFrame:
    summary = summarize(detail).iloc[0]
    status = str(summary["Status"])
    if status == "STRONG EVIDENCE": action, review_ready = "MANUAL_REVIEW_READY", True
    elif status == "SUPPORTED": action, review_ready = "KEEP_AND_MONITOR", False
    elif status == "CAUTION": action, review_ready = "MANUAL_REVIEW", False
    else: action, review_ready = "KEEP_LEARNING", False
    row = {
        "Evidence_Status": status, "Captured_Candidates": int(summary["Captured_Candidates"]),
        "Authentic_Pregame_Candidates": int(summary["Authentic_Pregame_Candidates"]),
        "OOS_Eligible_Starts": int(summary["OOS_Eligible_Starts"]), "Observed_Days": int(summary["Observed_Days"]),
        "Distinct_Umpires": int(summary["Distinct_Umpires"]), "Base_MAE": summary["Base_MAE"],
        "UmpireCandidate_MAE": summary["UmpireCandidate_MAE"], "Relative_MAE_Improvement": summary["Relative_MAE_Improvement"],
        "Candidate_Win_Share": summary["Candidate_Win_Share"], "Candidate_Loss_Share": summary["Candidate_Loss_Share"],
        "Base_Bias": summary["Base_Bias"], "UmpireCandidate_Bias": summary["UmpireCandidate_Bias"],
        "Mean_Absolute_Factor_Delta": summary["Mean_Absolute_Factor_Delta"], "Reason": summary["Reason"],
        "Manual_Review_Ready": review_ready, "Recommended_Action": action, "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY, "Validation_Version": VERSION,
    }
    return pd.DataFrame([row], columns=GATE_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lineage-safe report-only live pregame umpire K validation")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/umpire_k_live_validation_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/umpire_k_live_validation_summary.csv"))
    parser.add_argument("--segments", type=Path, default=Path("data/umpire_k_live_validation_segments.csv"))
    parser.add_argument("--gate", type=Path, default=Path("data/umpire_k_live_validation_gate.csv"))
    args = parser.parse_args()
    log = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if log.empty: raise SystemExit("Projection history is required")
    detail, summary = build_detail(log), None
    summary = summarize(detail)
    segments, gate = build_segment_summary(detail), evaluate_gate(detail)
    for path in (args.detail, args.summary, args.segments, args.gate): path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False); summary.to_csv(args.summary, index=False)
    segments.to_csv(args.segments, index=False); gate.to_csv(args.gate, index=False)
    print(summary.to_string(index=False)); print(gate.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()

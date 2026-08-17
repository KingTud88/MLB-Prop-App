from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VALIDATION_VERSION = "catcher-context-walkforward-v1"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
MIN_PRIOR_STARTS = 5
SHRINK_PRIOR_STARTS = 10.0
MAX_FACTOR_DELTA = 0.05
MIN_EVAL_STARTS = 30
MIN_EVAL_CATCHERS = 8
MIN_EVAL_DAYS = 10
STRONG_STARTS = 75
STRONG_CATCHERS = 15
STRONG_DAYS = 20

DETAIL_COLUMNS = [
    "Game_Date", "Game_PK", "Pitcher_ID", "Player", "Team",
    "Catcher_ID", "Catcher_Name", "Catcher_Source", "Catcher_Captured_At_UTC",
    "Game_Time_UTC", "Lineage", "Baseline_Captured_At_UTC",
    "Baseline_Projection", "Actual_Strikeouts", "Resolved_At_UTC",
    "Data_Quality", "Quality_Band", "Starter_History_Games", "Starter_History_Band",
    "Prior_Catcher_Starts", "Prior_Backfilled_Starts", "Prior_Mean_Projection",
    "Prior_Mean_K_Residual", "Prior_Mean_K_Per_BF", "Prior_Sample_Band",
    "Shadow_Catcher_Factor", "Signal_Direction", "Candidate_Projection",
    "OOS_Eligible", "Candidate_Auditable", "Baseline_Error", "Candidate_Error",
    "Candidate_Win", "Candidate_Loss", "Signal_Aligned",
    "Production_Catcher_Factor", "Candidate_Authority", "Report_Only",
    "Production_Authority", "Validation_Version",
]

SUMMARY_COLUMNS = [
    "Dimension", "Segment", "Rows", "Resolved_Rows", "Authentic_Pregame_Rows",
    "Auditable_Starts", "Distinct_Catchers", "Observed_Days", "Avg_Prior_Starts",
    "Base_MAE", "Candidate_MAE", "Relative_MAE_Improvement", "Candidate_Win_Share",
    "Candidate_Loss_Share", "Base_Bias", "Candidate_Bias", "Signal_Alignment",
    "Mean_Absolute_Factor_Delta", "Evidence", "Reason", "Report_Only",
    "Production_Authority", "Validation_Version",
]

GATE_COLUMNS = [
    "Evidence_Status", "Authentic_Pregame_Resolved", "Auditable_Starts",
    "Distinct_Catchers", "Observed_Days", "Base_MAE", "Candidate_MAE",
    "Relative_MAE_Improvement", "Candidate_Win_Share", "Candidate_Loss_Share",
    "Base_Bias", "Candidate_Bias", "Signal_Alignment", "Mean_Absolute_Factor_Delta",
    "Reason", "Recommended_Activation", "Report_Only", "Production_Authority",
    "Validation_Version",
]


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _utc(value: object) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce", utc=True)


def _quality_band(value: object) -> str:
    number = _num(value)
    if number is None:
        return "UNKNOWN"
    if number < 60:
        return "<60"
    if number < 70:
        return "60–69"
    if number < 80:
        return "70–79"
    if number < 90:
        return "80–89"
    return "90+"


def _history_band(value: object) -> str:
    number = _num(value)
    if number is None:
        return "UNKNOWN"
    if number < 3:
        return "0–2"
    if number < 6:
        return "3–5"
    if number < 10:
        return "6–9"
    return "10+"


def _prior_band(n: int) -> str:
    if n < 3:
        return "0–2"
    if n < 5:
        return "3–4"
    if n < 10:
        return "5–9"
    return "10+"


def _lineage(confirmed: bool, captured: pd.Timestamp, game_time: pd.Timestamp) -> str:
    if not confirmed:
        return "UNCONFIRMED"
    if pd.isna(captured) or pd.isna(game_time):
        return "UNKNOWN"
    return "PRE_GAME_CAPTURE" if captured < game_time else "POST_START_BACKFILL"


def _signal_direction(factor: float) -> str:
    if factor > 1.002:
        return "POSITIVE"
    if factor < 0.998:
        return "NEGATIVE"
    return "NEUTRAL"


def _projection_records(projections: pd.DataFrame) -> dict[tuple[int, int], pd.DataFrame]:
    if projections is None or projections.empty:
        return {}
    work = projections.copy()
    work["_game_pk"] = pd.to_numeric(work.get("game_pk"), errors="coerce")
    work["_pitcher_id"] = pd.to_numeric(work.get("pitcher_id"), errors="coerce")
    work["_captured"] = pd.to_datetime(work.get("captured_at_utc"), errors="coerce", utc=True)
    work["_game_time"] = pd.to_datetime(work.get("game_time"), errors="coerce", utc=True)
    work["_resolved"] = pd.to_datetime(work.get("resolved_at_utc"), errors="coerce", utc=True)
    work["_projection"] = pd.to_numeric(work.get("projection"), errors="coerce")
    work["_actual_k"] = pd.to_numeric(work.get("actual_strikeouts"), errors="coerce")
    work = work.dropna(subset=["_game_pk", "_pitcher_id"])
    records: dict[tuple[int, int], pd.DataFrame] = {}
    for (game_pk, pitcher_id), group in work.groupby(["_game_pk", "_pitcher_id"], sort=False):
        records[(int(game_pk), int(pitcher_id))] = group.sort_values("_captured", na_position="last").copy()
    return records


def _select_projection(group: pd.DataFrame, catcher_capture: pd.Timestamp) -> dict[str, object]:
    if group is None or group.empty:
        return {}
    game_times = group["_game_time"].dropna()
    game_time = game_times.iloc[0] if not game_times.empty else pd.NaT
    cutoff = catcher_capture if pd.notna(catcher_capture) else game_time
    candidates = group.loc[group["_projection"].notna() & group["_captured"].notna()].copy()
    if pd.notna(game_time):
        candidates = candidates.loc[candidates["_captured"] < game_time]
    if pd.notna(cutoff):
        candidates = candidates.loc[candidates["_captured"] <= cutoff]
    baseline = candidates.sort_values("_captured").iloc[-1] if not candidates.empty else None

    outcomes = group.loc[group["_actual_k"].notna()].copy()
    if not outcomes.empty:
        outcomes = outcomes.sort_values("_resolved", na_position="last")
        outcome = outcomes.iloc[0]
        actual_k = float(outcome["_actual_k"])
        resolved = outcome["_resolved"]
        actual_bf = _num(outcome.get("actual_batters_faced"))
    else:
        actual_k = None
        resolved = pd.NaT
        actual_bf = None

    if baseline is None:
        return {
            "game_time": game_time,
            "actual_k": actual_k,
            "resolved": resolved,
            "actual_bf": actual_bf,
        }
    return {
        "game_time": game_time,
        "baseline_captured": baseline["_captured"],
        "projection": float(baseline["_projection"]),
        "actual_k": actual_k,
        "resolved": resolved,
        "actual_bf": actual_bf,
        "data_quality": _num(baseline.get("data_quality")),
        "starter_history_games": _num(baseline.get("starter_history_games")),
    }


def _shadow_factor(prior: pd.DataFrame) -> float:
    n = int(len(prior))
    if n < MIN_PRIOR_STARTS:
        return 1.0
    projection = pd.to_numeric(prior["Baseline_Projection"], errors="coerce")
    residual = pd.to_numeric(prior["Actual_Strikeouts"], errors="coerce") - projection
    valid = projection.notna() & residual.notna()
    if int(valid.sum()) < MIN_PRIOR_STARTS:
        return 1.0
    mean_projection = float(projection.loc[valid].mean())
    if abs(mean_projection) < 1e-9:
        return 1.0
    raw_rate = float(residual.loc[valid].mean() / mean_projection)
    shrink = float(valid.sum()) / (float(valid.sum()) + SHRINK_PRIOR_STARTS)
    delta = float(np.clip(raw_rate * shrink, -MAX_FACTOR_DELTA, MAX_FACTOR_DELTA))
    return float(1.0 + delta)


def build_detail(projections: pd.DataFrame, catcher_log: pd.DataFrame) -> pd.DataFrame:
    if catcher_log is None or catcher_log.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    projection_groups = _projection_records(projections)
    records: list[dict[str, object]] = []

    for _, catcher_row in catcher_log.iterrows():
        game_pk = _num(catcher_row.get("game_pk"))
        pitcher_id = _num(catcher_row.get("pitcher_id"))
        if game_pk is None or pitcher_id is None:
            continue
        key = (int(game_pk), int(pitcher_id))
        group = projection_groups.get(key)
        catcher_capture = _utc(catcher_row.get("catcher_captured_at_utc"))
        selected = _select_projection(group, catcher_capture) if group is not None else {}
        game_time = selected.get("game_time", pd.NaT)
        confirmed = _truthy(catcher_row.get("catcher_confirmed"))
        catcher_id = _num(catcher_row.get("catcher_id"))
        lineage = _lineage(confirmed and catcher_id is not None, catcher_capture, game_time)
        baseline = _num(selected.get("projection"))
        actual_k = _num(selected.get("actual_k"))
        production_factor = _num(catcher_row.get("catcher_factor"))
        records.append({
            "Game_Date": str(catcher_row.get("game_date", "")),
            "Game_PK": int(game_pk),
            "Pitcher_ID": int(pitcher_id),
            "Player": str(catcher_row.get("player", "")),
            "Team": str(catcher_row.get("team", "")),
            "Catcher_ID": int(catcher_id) if catcher_id is not None else np.nan,
            "Catcher_Name": str(catcher_row.get("catcher_name", "")),
            "Catcher_Source": str(catcher_row.get("catcher_source", "")),
            "Catcher_Captured_At_UTC": catcher_capture,
            "Game_Time_UTC": game_time,
            "Lineage": lineage,
            "Baseline_Captured_At_UTC": selected.get("baseline_captured", pd.NaT),
            "Baseline_Projection": baseline,
            "Actual_Strikeouts": actual_k,
            "Resolved_At_UTC": selected.get("resolved", pd.NaT),
            "Actual_Batters_Faced": _num(selected.get("actual_bf")),
            "Data_Quality": _num(selected.get("data_quality")),
            "Quality_Band": _quality_band(selected.get("data_quality")),
            "Starter_History_Games": _num(selected.get("starter_history_games")),
            "Starter_History_Band": _history_band(selected.get("starter_history_games")),
            "Production_Catcher_Factor": 1.0 if production_factor is None else production_factor,
            "Candidate_Authority": str(catcher_row.get("candidate_authority", "REPORT_ONLY") or "REPORT_ONLY"),
        })

    work = pd.DataFrame(records)
    if work.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    output: list[dict[str, object]] = []
    for _, target in work.iterrows():
        target_capture = target["Catcher_Captured_At_UTC"]
        catcher_id = _num(target["Catcher_ID"])
        prior = pd.DataFrame()
        if catcher_id is not None and pd.notna(target_capture):
            prior_mask = (
                pd.to_numeric(work["Catcher_ID"], errors="coerce").eq(catcher_id)
                & work["Game_Time_UTC"].notna()
                & work["Game_Time_UTC"].lt(target["Game_Time_UTC"])
                & work["Catcher_Captured_At_UTC"].notna()
                & work["Catcher_Captured_At_UTC"].le(target_capture)
                & work["Resolved_At_UTC"].notna()
                & work["Resolved_At_UTC"].le(target_capture)
                & pd.to_numeric(work["Baseline_Projection"], errors="coerce").notna()
                & pd.to_numeric(work["Actual_Strikeouts"], errors="coerce").notna()
            )
            prior = work.loc[prior_mask].copy()

        prior_n = int(len(prior))
        factor = _shadow_factor(prior)
        base = _num(target["Baseline_Projection"])
        actual = _num(target["Actual_Strikeouts"])
        candidate = float(base * factor) if base is not None else None
        oos = bool(target["Lineage"] == "PRE_GAME_CAPTURE" and base is not None and actual is not None)
        auditable = bool(oos and prior_n >= MIN_PRIOR_STARTS)
        base_err = float(base - actual) if oos else np.nan
        cand_err = float(candidate - actual) if auditable and candidate is not None else np.nan
        direction = _signal_direction(factor)
        residual = float(actual - base) if oos else np.nan
        if auditable and direction == "POSITIVE":
            aligned: object = bool(residual > 0)
        elif auditable and direction == "NEGATIVE":
            aligned = bool(residual < 0)
        elif auditable and direction == "NEUTRAL":
            aligned = np.nan
        else:
            aligned = np.nan

        prior_projection = pd.to_numeric(prior.get("Baseline_Projection"), errors="coerce") if not prior.empty else pd.Series(dtype=float)
        prior_actual = pd.to_numeric(prior.get("Actual_Strikeouts"), errors="coerce") if not prior.empty else pd.Series(dtype=float)
        prior_bf = pd.to_numeric(prior.get("Actual_Batters_Faced"), errors="coerce") if not prior.empty else pd.Series(dtype=float)
        prior_resid = prior_actual - prior_projection
        k_per_bf = (prior_actual / prior_bf).replace([np.inf, -np.inf], np.nan)
        row = target.to_dict()
        row.update({
            "Prior_Catcher_Starts": prior_n,
            "Prior_Backfilled_Starts": int(prior["Lineage"].eq("POST_START_BACKFILL").sum()) if not prior.empty else 0,
            "Prior_Mean_Projection": float(prior_projection.mean()) if not prior_projection.empty else np.nan,
            "Prior_Mean_K_Residual": float(prior_resid.mean()) if not prior_resid.empty else np.nan,
            "Prior_Mean_K_Per_BF": float(k_per_bf.mean()) if not k_per_bf.empty else np.nan,
            "Prior_Sample_Band": _prior_band(prior_n),
            "Shadow_Catcher_Factor": factor,
            "Signal_Direction": direction,
            "Candidate_Projection": candidate,
            "OOS_Eligible": oos,
            "Candidate_Auditable": auditable,
            "Baseline_Error": base_err,
            "Candidate_Error": cand_err,
            "Candidate_Win": bool(abs(cand_err) < abs(base_err)) if auditable else False,
            "Candidate_Loss": bool(abs(cand_err) > abs(base_err)) if auditable else False,
            "Signal_Aligned": aligned,
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Validation_Version": VALIDATION_VERSION,
        })
        output.append(row)

    detail = pd.DataFrame(output)
    for column in DETAIL_COLUMNS:
        if column not in detail.columns:
            detail[column] = np.nan
    return detail[DETAIL_COLUMNS].copy()


def _evidence_status(n: int, catchers: int, days: int, rel: float, win: float, base_bias: float, cand_bias: float, alignment: float) -> tuple[str, str]:
    if n < MIN_EVAL_STARTS or catchers < MIN_EVAL_CATCHERS or days < MIN_EVAL_DAYS:
        return "LEARNING", f"Need at least {MIN_EVAL_STARTS} auditable starts, {MIN_EVAL_CATCHERS} catchers, and {MIN_EVAL_DAYS} days; have {n}, {catchers}, and {days}."
    bias_ok = pd.notna(base_bias) and pd.notna(cand_bias) and abs(cand_bias) <= abs(base_bias) + 0.05
    if rel <= -0.005 or win < 0.48 or not bias_ok:
        return "CAUTION", "Enough authentic walk-forward volume exists, but the shadow catcher signal worsens MAE, win share, or bias guardrails."
    strong = n >= STRONG_STARTS and catchers >= STRONG_CATCHERS and days >= STRONG_DAYS and rel >= 0.01 and win >= 0.55 and bias_ok and (pd.isna(alignment) or alignment >= 0.55)
    if strong:
        return "STRONG EVIDENCE", "Large authentic walk-forward sample with stable MAE, win-share, bias, and signal-direction support."
    supported = rel >= 0.005 and win >= 0.52 and bias_ok and (pd.isna(alignment) or alignment >= 0.50)
    if supported:
        return "SUPPORTED", "Authentic walk-forward catcher signal clears the minimum improvement and stability guardrails."
    return "CAUTION", "Sample is large enough to evaluate, but the catcher signal does not clear every support guardrail."


def _summary_row(group: pd.DataFrame, dimension: str, segment: str) -> dict[str, object]:
    rows = int(len(group))
    resolved = group.loc[pd.to_numeric(group.get("Actual_Strikeouts"), errors="coerce").notna()].copy()
    authentic = resolved.loc[resolved.get("Lineage", pd.Series(index=resolved.index, dtype=str)).eq("PRE_GAME_CAPTURE")].copy()
    audit = group.loc[group.get("Candidate_Auditable", pd.Series(False, index=group.index)).fillna(False).astype(bool)].copy()
    n = int(len(audit))
    catchers = int(pd.to_numeric(audit.get("Catcher_ID"), errors="coerce").dropna().nunique()) if n else 0
    days = int(audit.get("Game_Date", pd.Series(dtype=object)).dropna().astype(str).nunique()) if n else 0
    if n:
        base_err = pd.to_numeric(audit["Baseline_Error"], errors="coerce")
        cand_err = pd.to_numeric(audit["Candidate_Error"], errors="coerce")
        base_mae = float(base_err.abs().mean())
        cand_mae = float(cand_err.abs().mean())
        rel = float((base_mae - cand_mae) / base_mae) if base_mae > 0 else float("nan")
        win = float(audit["Candidate_Win"].fillna(False).astype(bool).mean())
        loss = float(audit["Candidate_Loss"].fillna(False).astype(bool).mean())
        base_bias = float(base_err.mean())
        cand_bias = float(cand_err.mean())
        alignment_values = audit["Signal_Aligned"].dropna()
        alignment = float(alignment_values.astype(bool).mean()) if not alignment_values.empty else float("nan")
        factor_delta = float((pd.to_numeric(audit["Shadow_Catcher_Factor"], errors="coerce") - 1.0).abs().mean())
        avg_prior = float(pd.to_numeric(audit["Prior_Catcher_Starts"], errors="coerce").mean())
    else:
        base_mae = cand_mae = rel = win = loss = base_bias = cand_bias = alignment = factor_delta = avg_prior = float("nan")
    evidence, reason = _evidence_status(n, catchers, days, rel, win, base_bias, cand_bias, alignment)
    return {
        "Dimension": dimension,
        "Segment": segment,
        "Rows": rows,
        "Resolved_Rows": int(len(resolved)),
        "Authentic_Pregame_Rows": int(len(authentic)),
        "Auditable_Starts": n,
        "Distinct_Catchers": catchers,
        "Observed_Days": days,
        "Avg_Prior_Starts": avg_prior,
        "Base_MAE": base_mae,
        "Candidate_MAE": cand_mae,
        "Relative_MAE_Improvement": rel,
        "Candidate_Win_Share": win,
        "Candidate_Loss_Share": loss,
        "Base_Bias": base_bias,
        "Candidate_Bias": cand_bias,
        "Signal_Alignment": alignment,
        "Mean_Absolute_Factor_Delta": factor_delta,
        "Evidence": evidence,
        "Reason": reason,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VALIDATION_VERSION,
    }


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    rows = [_summary_row(detail, "OVERALL", "ALL CATCHER CONTEXT")]
    specs = (
        ("LINEAGE", "Lineage"),
        ("PRIOR SAMPLE BAND", "Prior_Sample_Band"),
        ("SIGNAL DIRECTION", "Signal_Direction"),
        ("QUALITY BAND", "Quality_Band"),
        ("STARTER HISTORY BAND", "Starter_History_Band"),
    )
    for dimension, column in specs:
        if column not in detail.columns:
            continue
        values = detail[column].fillna("UNKNOWN").astype(str)
        for segment in sorted(values.unique()):
            rows.append(_summary_row(detail.loc[values.eq(segment)], dimension, segment))
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def evaluate_gate(detail: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    if detail is None or detail.empty:
        row = {
            "Evidence_Status": "LEARNING", "Authentic_Pregame_Resolved": 0, "Auditable_Starts": 0,
            "Distinct_Catchers": 0, "Observed_Days": 0, "Reason": "No catcher validation rows are available.",
            "Recommended_Activation": False, "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY, "Validation_Version": VALIDATION_VERSION,
        }
        return pd.DataFrame([row], columns=GATE_COLUMNS), "LEARNING"

    authentic = detail.loc[
        detail.get("Lineage", pd.Series(index=detail.index, dtype=str)).eq("PRE_GAME_CAPTURE")
        & pd.to_numeric(detail.get("Actual_Strikeouts"), errors="coerce").notna()
    ].copy()
    audit = detail.loc[detail.get("Candidate_Auditable", pd.Series(False, index=detail.index)).fillna(False).astype(bool)].copy()
    n = int(len(audit))
    catchers = int(pd.to_numeric(audit.get("Catcher_ID"), errors="coerce").dropna().nunique()) if n else 0
    days = int(audit.get("Game_Date", pd.Series(dtype=object)).dropna().astype(str).nunique()) if n else 0
    if n:
        base_err = pd.to_numeric(audit["Baseline_Error"], errors="coerce")
        cand_err = pd.to_numeric(audit["Candidate_Error"], errors="coerce")
        base_mae = float(base_err.abs().mean())
        cand_mae = float(cand_err.abs().mean())
        rel = float((base_mae - cand_mae) / base_mae) if base_mae > 0 else float("nan")
        win = float(audit["Candidate_Win"].fillna(False).astype(bool).mean())
        loss = float(audit["Candidate_Loss"].fillna(False).astype(bool).mean())
        base_bias = float(base_err.mean())
        cand_bias = float(cand_err.mean())
        alignment_values = audit["Signal_Aligned"].dropna()
        alignment = float(alignment_values.astype(bool).mean()) if not alignment_values.empty else float("nan")
        factor_delta = float((pd.to_numeric(audit["Shadow_Catcher_Factor"], errors="coerce") - 1.0).abs().mean())
    else:
        base_mae = cand_mae = rel = win = loss = base_bias = cand_bias = alignment = factor_delta = float("nan")
    status, reason = _evidence_status(n, catchers, days, rel, win, base_bias, cand_bias, alignment)
    row = {
        "Evidence_Status": status,
        "Authentic_Pregame_Resolved": int(len(authentic)),
        "Auditable_Starts": n,
        "Distinct_Catchers": catchers,
        "Observed_Days": days,
        "Base_MAE": base_mae,
        "Candidate_MAE": cand_mae,
        "Relative_MAE_Improvement": rel,
        "Candidate_Win_Share": win,
        "Candidate_Loss_Share": loss,
        "Base_Bias": base_bias,
        "Candidate_Bias": cand_bias,
        "Signal_Alignment": alignment,
        "Mean_Absolute_Factor_Delta": factor_delta,
        "Reason": reason,
        "Recommended_Activation": False,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VALIDATION_VERSION,
    }
    return pd.DataFrame([row], columns=GATE_COLUMNS), status


def main() -> None:
    parser = argparse.ArgumentParser(description="Chronological report-only validation of catcher context for strikeout projections.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--catcher-log", type=Path, default=Path("data/catcher_context_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/catcher_context_validation_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/catcher_context_validation_summary.csv"))
    parser.add_argument("--gate", type=Path, default=Path("data/catcher_context_validation_gate.csv"))
    args = parser.parse_args()

    projections = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    catcher_log = pd.read_csv(args.catcher_log) if args.catcher_log.exists() else pd.DataFrame()
    if projections.empty:
        raise SystemExit("Projection history is required")
    detail = build_detail(projections, catcher_log)
    summary = summarize(detail)
    gate, overall = evaluate_gate(detail)
    for path, frame in ((args.detail, detail), (args.summary, summary), (args.gate, gate)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    print(gate.to_string(index=False))
    print(f"catcher_context_evidence={overall} version={VALIDATION_VERSION}")
    print("report_only=true production_authority=NONE catcher_factor_activation=false")


if __name__ == "__main__":
    main()

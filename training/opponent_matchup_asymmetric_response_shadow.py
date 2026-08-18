from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "opponent-matchup-asymmetric-response-shadow-v1"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

FROZEN_BOOST_CAP_K = 0.10
WEAK_REDUCE_DELTA_MIN_PP = -1.00
WEAK_REDUCE_DELTA_MAX_PP = -0.25
DERIVATION_CUTOFF_DATE = "2026-08-17"

MIN_OOS_STARTS = 60
MIN_OOS_DAYS = 10
MIN_OOS_OPPONENTS = 15
MIN_COMPONENT_STARTS = 15
MIN_SUPPORT_RELATIVE_MAE = 0.005
MIN_SUPPORT_WIN_SHARE = 0.52
BIAS_WORSEN_TOLERANCE = 0.05

CHANGED_ACTIONS = ("BOOST_CAPPED", "WEAK_REDUCE_NEUTRALIZED")

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "Opponent_K_Rate", "Opponent_K_Delta_PP", "Matchup_PA", "Lineup_State",
    "Data_Quality", "Quality_Band", "Neutral_Opponent_Projection",
    "Applied_Projection", "Matchup_Adjustment_K", "Adjustment_Direction",
    "Actual_Strikeouts", "Candidate_Action", "Candidate_Adjustment_K",
    "Candidate_Changed", "Candidate_Projection", "Applied_Absolute_Error",
    "Candidate_Absolute_Error", "Neutral_Absolute_Error", "Applied_Error",
    "Candidate_Error", "Neutral_Error", "Candidate_Win_vs_Applied",
    "Applied_Win_vs_Candidate", "Candidate_Applied_Tie", "Evidence_Lane",
    "Counts_For_Promotion", "Frozen_Boost_Cap_K", "Weak_Reduce_Delta_Min_PP",
    "Weak_Reduce_Delta_Max_PP", "Derivation_Cutoff_Date", "Report_Only",
    "Production_Authority", "Validation_Version",
]

SUMMARY_COLUMNS = [
    "Evidence_Lane", "Evidence_Status", "Starts", "Observed_Days",
    "Distinct_Opponents", "Changed_Starts", "Boost_Capped_Starts",
    "Weak_Reduce_Neutralized_Starts", "Applied_MAE", "Candidate_MAE",
    "Neutral_MAE", "Candidate_Relative_MAE_vs_Applied",
    "Candidate_Relative_MAE_vs_Neutral", "Changed_Applied_MAE",
    "Changed_Candidate_MAE", "Changed_Relative_MAE_vs_Applied",
    "Changed_Win_Share_vs_Applied", "Applied_Win_Share_vs_Candidate",
    "Changed_Tie_Share", "Applied_Bias", "Candidate_Bias", "Neutral_Bias",
    "Candidate_Bias_Abs_Change_vs_Applied", "Mean_Applied_Adjustment_K",
    "Mean_Candidate_Adjustment_K", "Frozen_Boost_Cap_K",
    "Weak_Reduce_Delta_Min_PP", "Weak_Reduce_Delta_Max_PP",
    "Derivation_Cutoff_Date", "Reason", "Recommended_Action", "Report_Only",
    "Production_Authority", "Validation_Version",
]

SEGMENT_COLUMNS = [
    "Evidence_Lane", "Candidate_Action", "Starts", "Observed_Days",
    "Distinct_Opponents", "Applied_MAE", "Candidate_MAE",
    "Relative_MAE_vs_Applied", "Candidate_Win_Share_vs_Applied",
    "Applied_Win_Share_vs_Candidate", "Tie_Share", "Applied_Bias",
    "Candidate_Bias", "Bias_Abs_Change", "Mean_Applied_Adjustment_K",
    "Mean_Candidate_Adjustment_K", "Stress_Read", "Report_Only",
    "Production_Authority", "Validation_Version",
]

GATE_COLUMNS = [
    "Finding", "Early_Read", "Forward_Starts", "Forward_Days",
    "Forward_Opponents", "Forward_Changed_Starts", "Forward_Boost_Capped_Starts",
    "Forward_Weak_Reduce_Neutralized_Starts", "Changed_Relative_MAE_vs_Applied",
    "Changed_Win_Share_vs_Applied", "Candidate_Bias_Abs_Change_vs_Applied",
    "Boost_Component_Read", "Weak_Reduce_Component_Read", "Reason",
    "Recommended_Action", "Manual_Review_Ready", "Report_Only",
    "Production_Authority", "Validation_Version",
]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _bool(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    raw = frame[column]
    if pd.api.types.is_bool_dtype(raw):
        return raw.fillna(False).astype(bool)
    return raw.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _candidate_action(adjustment: float, delta_pp: float) -> tuple[str, float]:
    if not np.isfinite(adjustment) or not np.isfinite(delta_pp):
        return "INVALID", np.nan
    if adjustment > FROZEN_BOOST_CAP_K:
        return "BOOST_CAPPED", FROZEN_BOOST_CAP_K
    if adjustment > 0.0:
        return "BOOST_UNCHANGED", adjustment
    if adjustment < 0.0 and WEAK_REDUCE_DELTA_MIN_PP < delta_pp <= WEAK_REDUCE_DELTA_MAX_PP:
        return "WEAK_REDUCE_NEUTRALIZED", 0.0
    if adjustment < 0.0:
        return "STRONG_REDUCE_UNCHANGED", adjustment
    return "NEUTRAL_UNCHANGED", adjustment


def build_detail(validation_detail: pd.DataFrame) -> pd.DataFrame:
    if validation_detail is None or validation_detail.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    out = validation_detail.copy()
    adjustment = _num(out, "Matchup_Adjustment_K")
    delta_pp = _num(out, "Opponent_K_Delta_PP")
    neutral = _num(out, "Neutral_Opponent_Projection")
    applied = _num(out, "Applied_Projection")
    actual = _num(out, "Actual_Strikeouts")
    valid = (
        _bool(out, "Auditable")
        & _bool(out, "Informative_Adjustment")
        & adjustment.notna()
        & delta_pp.notna()
        & neutral.notna()
        & applied.notna()
        & actual.notna()
    )
    out = out.loc[valid].copy()
    adjustment = adjustment.loc[valid]
    delta_pp = delta_pp.loc[valid]
    neutral = neutral.loc[valid]
    applied = applied.loc[valid]
    actual = actual.loc[valid]

    actions: list[str] = []
    candidate_adjustments: list[float] = []
    for adj, delta in zip(adjustment.to_numpy(dtype=float), delta_pp.to_numpy(dtype=float)):
        action, candidate_adj = _candidate_action(float(adj), float(delta))
        actions.append(action)
        candidate_adjustments.append(candidate_adj)

    candidate_adjustment = pd.Series(candidate_adjustments, index=out.index, dtype=float)
    candidate = neutral + candidate_adjustment
    applied_abs = (applied - actual).abs()
    candidate_abs = (candidate - actual).abs()
    neutral_abs = (neutral - actual).abs()

    out["Candidate_Action"] = actions
    out["Candidate_Adjustment_K"] = candidate_adjustment
    out["Candidate_Changed"] = ~np.isclose(candidate_adjustment, adjustment)
    out["Candidate_Projection"] = candidate
    out["Applied_Absolute_Error"] = applied_abs
    out["Candidate_Absolute_Error"] = candidate_abs
    out["Neutral_Absolute_Error"] = neutral_abs
    out["Applied_Error"] = applied - actual
    out["Candidate_Error"] = candidate - actual
    out["Neutral_Error"] = neutral - actual
    out["Candidate_Win_vs_Applied"] = candidate_abs.lt(applied_abs)
    out["Applied_Win_vs_Candidate"] = applied_abs.lt(candidate_abs)
    out["Candidate_Applied_Tie"] = np.isclose(candidate_abs, applied_abs)

    dates = pd.to_datetime(out.get("game_date"), errors="coerce")
    oos = dates.gt(pd.Timestamp(DERIVATION_CUTOFF_DATE))
    out["Evidence_Lane"] = np.where(oos, "FORWARD_OOS", "DERIVATION_BACKTEST")
    out["Counts_For_Promotion"] = oos
    out["Frozen_Boost_Cap_K"] = FROZEN_BOOST_CAP_K
    out["Weak_Reduce_Delta_Min_PP"] = WEAK_REDUCE_DELTA_MIN_PP
    out["Weak_Reduce_Delta_Max_PP"] = WEAK_REDUCE_DELTA_MAX_PP
    out["Derivation_Cutoff_Date"] = DERIVATION_CUTOFF_DATE
    out["Report_Only"] = REPORT_ONLY
    out["Production_Authority"] = PRODUCTION_AUTHORITY
    out["Validation_Version"] = VERSION

    for column in DETAIL_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    return out[DETAIL_COLUMNS].reset_index(drop=True)


def _safe_rel(base: float, candidate: float) -> float:
    if not np.isfinite(base) or base <= 0 or not np.isfinite(candidate):
        return np.nan
    return float((base - candidate) / base)


def _metrics(group: pd.DataFrame) -> dict[str, object]:
    if group is None or group.empty:
        return {
            "Starts": 0, "Observed_Days": 0, "Distinct_Opponents": 0,
            "Changed_Starts": 0, "Boost_Capped_Starts": 0,
            "Weak_Reduce_Neutralized_Starts": 0, "Applied_MAE": np.nan,
            "Candidate_MAE": np.nan, "Neutral_MAE": np.nan,
            "Candidate_Relative_MAE_vs_Applied": np.nan,
            "Candidate_Relative_MAE_vs_Neutral": np.nan,
            "Changed_Applied_MAE": np.nan, "Changed_Candidate_MAE": np.nan,
            "Changed_Relative_MAE_vs_Applied": np.nan,
            "Changed_Win_Share_vs_Applied": np.nan,
            "Applied_Win_Share_vs_Candidate": np.nan, "Changed_Tie_Share": np.nan,
            "Applied_Bias": np.nan, "Candidate_Bias": np.nan, "Neutral_Bias": np.nan,
            "Candidate_Bias_Abs_Change_vs_Applied": np.nan,
            "Mean_Applied_Adjustment_K": np.nan, "Mean_Candidate_Adjustment_K": np.nan,
        }

    changed = group.loc[group["Candidate_Changed"].fillna(False).astype(bool)].copy()
    applied_mae = float(_num(group, "Applied_Absolute_Error").mean())
    candidate_mae = float(_num(group, "Candidate_Absolute_Error").mean())
    neutral_mae = float(_num(group, "Neutral_Absolute_Error").mean())
    applied_bias = float(_num(group, "Applied_Error").mean())
    candidate_bias = float(_num(group, "Candidate_Error").mean())
    neutral_bias = float(_num(group, "Neutral_Error").mean())

    if changed.empty:
        changed_applied_mae = changed_candidate_mae = np.nan
        changed_rel = candidate_wins = applied_wins = ties = np.nan
    else:
        changed_applied_mae = float(_num(changed, "Applied_Absolute_Error").mean())
        changed_candidate_mae = float(_num(changed, "Candidate_Absolute_Error").mean())
        changed_rel = _safe_rel(changed_applied_mae, changed_candidate_mae)
        candidate_wins = float(changed["Candidate_Win_vs_Applied"].astype(bool).mean())
        applied_wins = float(changed["Applied_Win_vs_Candidate"].astype(bool).mean())
        ties = float(changed["Candidate_Applied_Tie"].astype(bool).mean())

    return {
        "Starts": int(len(group)),
        "Observed_Days": int(group["game_date"].dropna().astype(str).nunique()),
        "Distinct_Opponents": int(group["opponent"].dropna().astype(str).nunique()),
        "Changed_Starts": int(len(changed)),
        "Boost_Capped_Starts": int(group["Candidate_Action"].eq("BOOST_CAPPED").sum()),
        "Weak_Reduce_Neutralized_Starts": int(group["Candidate_Action"].eq("WEAK_REDUCE_NEUTRALIZED").sum()),
        "Applied_MAE": applied_mae,
        "Candidate_MAE": candidate_mae,
        "Neutral_MAE": neutral_mae,
        "Candidate_Relative_MAE_vs_Applied": _safe_rel(applied_mae, candidate_mae),
        "Candidate_Relative_MAE_vs_Neutral": _safe_rel(neutral_mae, candidate_mae),
        "Changed_Applied_MAE": changed_applied_mae,
        "Changed_Candidate_MAE": changed_candidate_mae,
        "Changed_Relative_MAE_vs_Applied": changed_rel,
        "Changed_Win_Share_vs_Applied": candidate_wins,
        "Applied_Win_Share_vs_Candidate": applied_wins,
        "Changed_Tie_Share": ties,
        "Applied_Bias": applied_bias,
        "Candidate_Bias": candidate_bias,
        "Neutral_Bias": neutral_bias,
        "Candidate_Bias_Abs_Change_vs_Applied": float(abs(candidate_bias) - abs(applied_bias)),
        "Mean_Applied_Adjustment_K": float(_num(group, "Matchup_Adjustment_K").mean()),
        "Mean_Candidate_Adjustment_K": float(_num(group, "Candidate_Adjustment_K").mean()),
    }


def _segment_metrics(group: pd.DataFrame) -> dict[str, object]:
    if group.empty:
        return {}
    applied_mae = float(_num(group, "Applied_Absolute_Error").mean())
    candidate_mae = float(_num(group, "Candidate_Absolute_Error").mean())
    applied_bias = float(_num(group, "Applied_Error").mean())
    candidate_bias = float(_num(group, "Candidate_Error").mean())
    return {
        "Starts": int(len(group)),
        "Observed_Days": int(group["game_date"].dropna().astype(str).nunique()),
        "Distinct_Opponents": int(group["opponent"].dropna().astype(str).nunique()),
        "Applied_MAE": applied_mae,
        "Candidate_MAE": candidate_mae,
        "Relative_MAE_vs_Applied": _safe_rel(applied_mae, candidate_mae),
        "Candidate_Win_Share_vs_Applied": float(group["Candidate_Win_vs_Applied"].astype(bool).mean()),
        "Applied_Win_Share_vs_Candidate": float(group["Applied_Win_vs_Candidate"].astype(bool).mean()),
        "Tie_Share": float(group["Candidate_Applied_Tie"].astype(bool).mean()),
        "Applied_Bias": applied_bias,
        "Candidate_Bias": candidate_bias,
        "Bias_Abs_Change": float(abs(candidate_bias) - abs(applied_bias)),
        "Mean_Applied_Adjustment_K": float(_num(group, "Matchup_Adjustment_K").mean()),
        "Mean_Candidate_Adjustment_K": float(_num(group, "Candidate_Adjustment_K").mean()),
    }


def _stress_read(metrics: dict[str, object], changed_action: bool) -> str:
    n = int(metrics.get("Starts", 0))
    if n < 8:
        return "SMALL_SAMPLE"
    if not changed_action:
        return "UNCHANGED_CONTROL"
    rel = metrics.get("Relative_MAE_vs_Applied")
    wins = metrics.get("Candidate_Win_Share_vs_Applied")
    if pd.notna(rel) and pd.notna(wins):
        if float(rel) > 0.0 and float(wins) >= 0.50:
            return "HELPING"
        if float(rel) < 0.0 and float(wins) < 0.50:
            return "HURTING"
    return "MIXED"


def build_segments(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for lane in ("DERIVATION_BACKTEST", "FORWARD_OOS"):
        lane_frame = detail.loc[detail["Evidence_Lane"].eq(lane)] if not detail.empty else pd.DataFrame()
        for action in (
            "BOOST_CAPPED", "BOOST_UNCHANGED", "WEAK_REDUCE_NEUTRALIZED",
            "STRONG_REDUCE_UNCHANGED",
        ):
            group = lane_frame.loc[lane_frame["Candidate_Action"].eq(action)].copy() if not lane_frame.empty else pd.DataFrame()
            if group.empty:
                continue
            metrics = _segment_metrics(group)
            rows.append({
                "Evidence_Lane": lane,
                "Candidate_Action": action,
                **metrics,
                "Stress_Read": _stress_read(metrics, action in CHANGED_ACTIONS),
                "Report_Only": REPORT_ONLY,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "Validation_Version": VERSION,
            })
    return pd.DataFrame(rows, columns=SEGMENT_COLUMNS)


def _component_read(segments: pd.DataFrame, action: str, lane: str = "FORWARD_OOS") -> tuple[str, int, float, float]:
    row = segments.loc[(segments["Evidence_Lane"].eq(lane)) & (segments["Candidate_Action"].eq(action))]
    if row.empty:
        return "LEARNING", 0, np.nan, np.nan
    rec = row.iloc[0]
    n = int(rec["Starts"])
    rel = float(rec["Relative_MAE_vs_Applied"]) if pd.notna(rec["Relative_MAE_vs_Applied"]) else np.nan
    wins = float(rec["Candidate_Win_Share_vs_Applied"]) if pd.notna(rec["Candidate_Win_Share_vs_Applied"]) else np.nan
    if n < MIN_COMPONENT_STARTS:
        return "LEARNING", n, rel, wins
    if np.isfinite(rel) and np.isfinite(wins):
        if rel >= 0.0 and wins >= 0.50:
            return "PASS_NO_HARM", n, rel, wins
        if rel < 0.0 and wins < 0.50:
            return "HURTING", n, rel, wins
    return "MIXED", n, rel, wins


def _summary_status(lane: str, metrics: dict[str, object]) -> tuple[str, str, str]:
    if lane == "DERIVATION_BACKTEST":
        return (
            "DESCRIPTIVE_ONLY",
            "These rows predate the frozen composite challenger and cannot validate it.",
            "FREEZE_COMPOSITE_AND_COLLECT_FORWARD_EVIDENCE",
        )
    return (
        "LEARNING",
        "Forward evidence is evaluated by the composite gate, including both changed components.",
        "KEEP_COMPOSITE_FROZEN_AND_LEARN",
    )


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for lane in ("DERIVATION_BACKTEST", "FORWARD_OOS"):
        group = detail.loc[detail["Evidence_Lane"].eq(lane)].copy() if not detail.empty else pd.DataFrame()
        metrics = _metrics(group)
        status, reason, action = _summary_status(lane, metrics)
        rows.append({
            "Evidence_Lane": lane, "Evidence_Status": status, **metrics,
            "Frozen_Boost_Cap_K": FROZEN_BOOST_CAP_K,
            "Weak_Reduce_Delta_Min_PP": WEAK_REDUCE_DELTA_MIN_PP,
            "Weak_Reduce_Delta_Max_PP": WEAK_REDUCE_DELTA_MAX_PP,
            "Derivation_Cutoff_Date": DERIVATION_CUTOFF_DATE,
            "Reason": reason, "Recommended_Action": action,
            "Report_Only": REPORT_ONLY, "Production_Authority": PRODUCTION_AUTHORITY,
            "Validation_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def build_gate(summary: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    forward = summary.loc[summary["Evidence_Lane"].eq("FORWARD_OOS")]
    derivation = summary.loc[summary["Evidence_Lane"].eq("DERIVATION_BACKTEST")]
    if forward.empty:
        fwd = {column: np.nan for column in SUMMARY_COLUMNS}
        fwd.update({"Starts": 0, "Observed_Days": 0, "Distinct_Opponents": 0, "Changed_Starts": 0,
                    "Boost_Capped_Starts": 0, "Weak_Reduce_Neutralized_Starts": 0})
    else:
        fwd = forward.iloc[0].to_dict()

    boost_read, boost_n, _, _ = _component_read(segments, "BOOST_CAPPED")
    weak_read, weak_n, _, _ = _component_read(segments, "WEAK_REDUCE_NEUTRALIZED")

    n = int(fwd.get("Starts") or 0)
    days = int(fwd.get("Observed_Days") or 0)
    opponents = int(fwd.get("Distinct_Opponents") or 0)
    changed = int(fwd.get("Changed_Starts") or 0)
    rel = fwd.get("Changed_Relative_MAE_vs_Applied")
    wins = fwd.get("Changed_Win_Share_vs_Applied")
    bias_change = fwd.get("Candidate_Bias_Abs_Change_vs_Applied")

    derivation_early = "INCONCLUSIVE"
    if not derivation.empty:
        d = derivation.iloc[0]
        drel = d.get("Changed_Relative_MAE_vs_Applied")
        dwins = d.get("Changed_Win_Share_vs_Applied")
        if pd.notna(drel) and pd.notna(dwins):
            if float(drel) > 0.0 and float(dwins) >= 0.50:
                derivation_early = "LEAN_SUPPORTED"
            elif float(drel) < 0.0 and float(dwins) < 0.50:
                derivation_early = "LEAN_HURTING"
            else:
                derivation_early = "MIXED"

    size_ready = n >= MIN_OOS_STARTS and days >= MIN_OOS_DAYS and opponents >= MIN_OOS_OPPONENTS
    components_ready = boost_n >= MIN_COMPONENT_STARTS and weak_n >= MIN_COMPONENT_STARTS
    manual_ready = False

    if not size_ready or not components_ready:
        finding = "INCONCLUSIVE"
        reason = (
            f"Need {MIN_OOS_STARTS} forward informative starts, {MIN_OOS_DAYS} days, {MIN_OOS_OPPONENTS} opponents, "
            f"and {MIN_COMPONENT_STARTS} starts in each changed component; have {n}, {days}, {opponents}, "
            f"BOOST_CAPPED={boost_n}, WEAK_REDUCE_NEUTRALIZED={weak_n}."
        )
        action = "KEEP_COMPOSITE_FROZEN_AND_LEARN"
    elif boost_read == "HURTING" or weak_read == "HURTING":
        finding = "HURTING_COMPONENT"
        reason = "At least one frozen changed component is hurting on forward evidence; aggregate results cannot override it."
        action = "REJECT_COMPOSITE_KEEP_PRODUCTION_UNCHANGED"
    elif pd.notna(rel) and pd.notna(wins) and pd.notna(bias_change) and (
        float(rel) >= MIN_SUPPORT_RELATIVE_MAE
        and float(wins) >= MIN_SUPPORT_WIN_SHARE
        and float(bias_change) <= BIAS_WORSEN_TOLERANCE
        and boost_read == "PASS_NO_HARM"
        and weak_read == "PASS_NO_HARM"
    ):
        finding = "SUPPORTED"
        reason = "Composite clears changed-start MAE, head-to-head, bias, diversity, and both component no-harm guardrails."
        action = "MANUAL_PROMOTION_REVIEW_ONLY"
        manual_ready = True
    elif pd.notna(rel) and pd.notna(wins) and float(rel) < 0.0 and float(wins) < 0.50:
        finding = "HURTING"
        reason = "Composite worsens changed-start forward MAE and loses head-to-head versus the live applied response."
        action = "REJECT_COMPOSITE_KEEP_PRODUCTION_UNCHANGED"
    else:
        finding = "MIXED"
        reason = "Forward sample clears size/component gates but does not clearly support or reject the composite."
        action = "KEEP_PRODUCTION_UNCHANGED_PENDING_MANUAL_REVIEW"

    row = {
        "Finding": finding,
        "Early_Read": derivation_early,
        "Forward_Starts": n,
        "Forward_Days": days,
        "Forward_Opponents": opponents,
        "Forward_Changed_Starts": changed,
        "Forward_Boost_Capped_Starts": int(fwd.get("Boost_Capped_Starts") or 0),
        "Forward_Weak_Reduce_Neutralized_Starts": int(fwd.get("Weak_Reduce_Neutralized_Starts") or 0),
        "Changed_Relative_MAE_vs_Applied": rel,
        "Changed_Win_Share_vs_Applied": wins,
        "Candidate_Bias_Abs_Change_vs_Applied": bias_change,
        "Boost_Component_Read": boost_read,
        "Weak_Reduce_Component_Read": weak_read,
        "Reason": reason,
        "Recommended_Action": action,
        "Manual_Review_Ready": manual_ready,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VERSION,
    }
    return pd.DataFrame([row], columns=GATE_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only frozen asymmetric opponent-response challenger")
    parser.add_argument("--source", type=Path, default=Path("data/opponent_matchup_validation_detail.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/opponent_matchup_asymmetric_response_shadow_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/opponent_matchup_asymmetric_response_shadow_summary.csv"))
    parser.add_argument("--segments", type=Path, default=Path("data/opponent_matchup_asymmetric_response_shadow_segments.csv"))
    parser.add_argument("--gate", type=Path, default=Path("data/opponent_matchup_asymmetric_response_shadow_gate.csv"))
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"Missing source detail: {args.source}")

    detail = build_detail(pd.read_csv(args.source))
    summary = summarize(detail)
    segments = build_segments(detail)
    gate = build_gate(summary, segments)

    args.detail.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    segments.to_csv(args.segments, index=False)
    gate.to_csv(args.gate, index=False)

    print(gate.to_string(index=False))
    print(
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"boost_cap_k={FROZEN_BOOST_CAP_K} weak_reduce_delta=({WEAK_REDUCE_DELTA_MIN_PP}, {WEAK_REDUCE_DELTA_MAX_PP}]"
    )


if __name__ == "__main__":
    main()

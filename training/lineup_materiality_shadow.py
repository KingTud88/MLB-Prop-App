from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "lineup-materiality-shadow-v1"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
FROZEN_MATERIALITY_K = 0.15
DERIVATION_CUTOFF_DATE = "2026-08-17"
MIN_OOS_PAIRS = 30
MIN_OOS_DAYS = 10
MIN_OOS_OPPONENTS = 12
MIN_CHANGED_PAIRS = 20
MIN_SUPPORT_RELATIVE_MAE = 0.005
MIN_SUPPORT_WIN_SHARE = 0.52
BIAS_WORSEN_TOLERANCE = 0.05

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "Lineup_Source", "Lineup_Captured_At_UTC", "Game_Time_UTC", "Lineage",
    "Authentic_Pregame_Pair", "OOS_Eligible", "Preconfirm_Projection",
    "Confirmed_Projection", "Projection_Delta", "Actual_Strikeouts",
    "Materiality_Action", "Materiality_Projection", "Materiality_Changed",
    "Preconfirm_Absolute_Error", "Confirmed_Absolute_Error",
    "Materiality_Absolute_Error", "Preconfirm_Error", "Confirmed_Error",
    "Materiality_Error", "Materiality_Win_vs_Confirmed",
    "Confirmed_Win_vs_Materiality", "Materiality_Confirmed_Tie", "Evidence_Lane",
    "Counts_For_Promotion", "Frozen_Materiality_K", "Derivation_Cutoff_Date",
    "Report_Only", "Production_Authority", "Validation_Version",
]
SUMMARY_COLUMNS = [
    "Evidence_Lane", "Evidence_Status", "Pairs", "Observed_Days",
    "Distinct_Opponents", "Changed_Pairs", "Applied_Confirmed_Pairs",
    "Reverted_To_Preconfirm_Pairs", "Preconfirm_MAE", "Confirmed_MAE",
    "Materiality_MAE", "Materiality_Relative_MAE_vs_Confirmed",
    "Materiality_Relative_MAE_vs_Preconfirm", "Changed_Confirmed_MAE",
    "Changed_Materiality_MAE", "Changed_Relative_MAE_vs_Confirmed",
    "Changed_Win_Share_vs_Confirmed", "Confirmed_Win_Share_vs_Materiality",
    "Changed_Tie_Share", "Confirmed_Bias", "Materiality_Bias",
    "Materiality_Bias_Abs_Change_vs_Confirmed", "Mean_Absolute_Projection_Delta",
    "Frozen_Materiality_K", "Derivation_Cutoff_Date", "Reason",
    "Recommended_Action", "Report_Only", "Production_Authority",
    "Validation_Version",
]
GATE_COLUMNS = [
    "Finding", "Early_Read", "Forward_Pairs", "Forward_Days",
    "Forward_Opponents", "Forward_Changed_Pairs",
    "Changed_Relative_MAE_vs_Confirmed", "Changed_Win_Share_vs_Confirmed",
    "Materiality_Relative_MAE_vs_Preconfirm",
    "Materiality_Bias_Abs_Change_vs_Confirmed", "Reason", "Recommended_Action",
    "Manual_Review_Ready", "Report_Only", "Production_Authority",
    "Validation_Version",
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


def _safe_rel(base: float, candidate: float) -> float:
    if not np.isfinite(base) or base <= 0 or not np.isfinite(candidate):
        return np.nan
    return float((base - candidate) / base)


def build_detail(lineup_detail: pd.DataFrame) -> pd.DataFrame:
    if lineup_detail is None or lineup_detail.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    frame = lineup_detail.copy()
    pre = _num(frame, "Preconfirm_Projection")
    confirmed = _num(frame, "Confirmed_Projection")
    delta = _num(frame, "Projection_Delta")
    actual = _num(frame, "Actual_Strikeouts")
    valid = (
        _bool(frame, "Authentic_Pregame_Pair")
        & _bool(frame, "OOS_Eligible")
        & pre.notna() & confirmed.notna() & delta.notna() & actual.notna()
    )
    frame = frame.loc[valid].copy()
    pre = pre.loc[valid]
    confirmed = confirmed.loc[valid]
    delta = delta.loc[valid]
    actual = actual.loc[valid]

    material = delta.abs().ge(FROZEN_MATERIALITY_K)
    candidate = pre.copy()
    candidate.loc[material] = confirmed.loc[material]
    action = pd.Series(
        np.where(material, "APPLY_CONFIRMED_MATERIAL", "REVERT_IMMATERIAL_TO_PRECONFIRM"),
        index=frame.index,
        dtype=object,
    )
    changed = ~material

    pre_abs = (pre - actual).abs()
    confirmed_abs = (confirmed - actual).abs()
    candidate_abs = (candidate - actual).abs()

    frame["Materiality_Action"] = action
    frame["Materiality_Projection"] = candidate
    frame["Materiality_Changed"] = changed
    frame["Preconfirm_Absolute_Error"] = pre_abs
    frame["Confirmed_Absolute_Error"] = confirmed_abs
    frame["Materiality_Absolute_Error"] = candidate_abs
    frame["Preconfirm_Error"] = pre - actual
    frame["Confirmed_Error"] = confirmed - actual
    frame["Materiality_Error"] = candidate - actual
    frame["Materiality_Win_vs_Confirmed"] = candidate_abs.lt(confirmed_abs)
    frame["Confirmed_Win_vs_Materiality"] = confirmed_abs.lt(candidate_abs)
    frame["Materiality_Confirmed_Tie"] = np.isclose(candidate_abs, confirmed_abs)

    dates = pd.to_datetime(frame.get("game_date"), errors="coerce")
    oos = dates.gt(pd.Timestamp(DERIVATION_CUTOFF_DATE))
    frame["Evidence_Lane"] = np.where(oos, "FORWARD_OOS", "DERIVATION_BACKTEST")
    frame["Counts_For_Promotion"] = oos
    frame["Frozen_Materiality_K"] = FROZEN_MATERIALITY_K
    frame["Derivation_Cutoff_Date"] = DERIVATION_CUTOFF_DATE
    frame["Report_Only"] = REPORT_ONLY
    frame["Production_Authority"] = PRODUCTION_AUTHORITY
    frame["Validation_Version"] = VERSION
    for column in DETAIL_COLUMNS:
        if column not in frame.columns:
            frame[column] = np.nan
    return frame[DETAIL_COLUMNS].reset_index(drop=True)


def _metrics(group: pd.DataFrame) -> dict[str, object]:
    if group is None or group.empty:
        return {
            "Pairs": 0, "Observed_Days": 0, "Distinct_Opponents": 0,
            "Changed_Pairs": 0, "Applied_Confirmed_Pairs": 0,
            "Reverted_To_Preconfirm_Pairs": 0, "Preconfirm_MAE": np.nan,
            "Confirmed_MAE": np.nan, "Materiality_MAE": np.nan,
            "Materiality_Relative_MAE_vs_Confirmed": np.nan,
            "Materiality_Relative_MAE_vs_Preconfirm": np.nan,
            "Changed_Confirmed_MAE": np.nan, "Changed_Materiality_MAE": np.nan,
            "Changed_Relative_MAE_vs_Confirmed": np.nan,
            "Changed_Win_Share_vs_Confirmed": np.nan,
            "Confirmed_Win_Share_vs_Materiality": np.nan, "Changed_Tie_Share": np.nan,
            "Confirmed_Bias": np.nan, "Materiality_Bias": np.nan,
            "Materiality_Bias_Abs_Change_vs_Confirmed": np.nan,
            "Mean_Absolute_Projection_Delta": np.nan,
        }

    changed = group.loc[group["Materiality_Changed"].fillna(False).astype(bool)].copy()
    pre_mae = float(_num(group, "Preconfirm_Absolute_Error").mean())
    confirmed_mae = float(_num(group, "Confirmed_Absolute_Error").mean())
    material_mae = float(_num(group, "Materiality_Absolute_Error").mean())
    confirmed_bias = float(_num(group, "Confirmed_Error").mean())
    material_bias = float(_num(group, "Materiality_Error").mean())

    changed_confirmed = changed_material = changed_rel = wins = losses = ties = np.nan
    if not changed.empty:
        changed_confirmed = float(_num(changed, "Confirmed_Absolute_Error").mean())
        changed_material = float(_num(changed, "Materiality_Absolute_Error").mean())
        changed_rel = _safe_rel(changed_confirmed, changed_material)
        wins = float(changed["Materiality_Win_vs_Confirmed"].astype(bool).mean())
        losses = float(changed["Confirmed_Win_vs_Materiality"].astype(bool).mean())
        ties = float(changed["Materiality_Confirmed_Tie"].astype(bool).mean())

    return {
        "Pairs": int(len(group)),
        "Observed_Days": int(group["game_date"].dropna().astype(str).nunique()),
        "Distinct_Opponents": int(group["opponent"].dropna().astype(str).nunique()),
        "Changed_Pairs": int(len(changed)),
        "Applied_Confirmed_Pairs": int(group["Materiality_Action"].eq("APPLY_CONFIRMED_MATERIAL").sum()),
        "Reverted_To_Preconfirm_Pairs": int(group["Materiality_Action"].eq("REVERT_IMMATERIAL_TO_PRECONFIRM").sum()),
        "Preconfirm_MAE": pre_mae,
        "Confirmed_MAE": confirmed_mae,
        "Materiality_MAE": material_mae,
        "Materiality_Relative_MAE_vs_Confirmed": _safe_rel(confirmed_mae, material_mae),
        "Materiality_Relative_MAE_vs_Preconfirm": _safe_rel(pre_mae, material_mae),
        "Changed_Confirmed_MAE": changed_confirmed,
        "Changed_Materiality_MAE": changed_material,
        "Changed_Relative_MAE_vs_Confirmed": changed_rel,
        "Changed_Win_Share_vs_Confirmed": wins,
        "Confirmed_Win_Share_vs_Materiality": losses,
        "Changed_Tie_Share": ties,
        "Confirmed_Bias": confirmed_bias,
        "Materiality_Bias": material_bias,
        "Materiality_Bias_Abs_Change_vs_Confirmed": float(abs(material_bias) - abs(confirmed_bias)),
        "Mean_Absolute_Projection_Delta": float(_num(group, "Projection_Delta").abs().mean()),
    }


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for lane in ("DERIVATION_BACKTEST", "FORWARD_OOS"):
        group = detail.loc[detail["Evidence_Lane"].eq(lane)].copy() if not detail.empty else pd.DataFrame()
        metrics = _metrics(group)
        if lane == "DERIVATION_BACKTEST":
            status = "DESCRIPTIVE_ONLY"
            reason = "These rows motivated the frozen 0.15 K materiality hypothesis and cannot validate it."
            action = "FREEZE_MATERIALITY_THRESHOLD_AND_COLLECT_FORWARD_EVIDENCE"
        else:
            status = "LEARNING"
            reason = "Forward evidence is evaluated by the materiality promotion gate."
            action = "KEEP_MATERIALITY_THRESHOLD_FROZEN_AND_LEARN"
        rows.append({
            "Evidence_Lane": lane, "Evidence_Status": status, **metrics,
            "Frozen_Materiality_K": FROZEN_MATERIALITY_K,
            "Derivation_Cutoff_Date": DERIVATION_CUTOFF_DATE,
            "Reason": reason, "Recommended_Action": action, "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY, "Validation_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def build_gate(summary: pd.DataFrame) -> pd.DataFrame:
    forward = summary.loc[summary["Evidence_Lane"].eq("FORWARD_OOS")].iloc[0]
    derivation = summary.loc[summary["Evidence_Lane"].eq("DERIVATION_BACKTEST")].iloc[0]
    drel = derivation["Changed_Relative_MAE_vs_Confirmed"]
    dwins = derivation["Changed_Win_Share_vs_Confirmed"]
    early = "INCONCLUSIVE"
    if pd.notna(drel) and pd.notna(dwins):
        if float(drel) > 0.0 and float(dwins) >= 0.50:
            early = "LEAN_SUPPORTED"
        elif float(drel) < 0.0 and float(dwins) < 0.50:
            early = "LEAN_HURTING"
        else:
            early = "MIXED"

    pairs = int(forward["Pairs"])
    days = int(forward["Observed_Days"])
    opponents = int(forward["Distinct_Opponents"])
    changed = int(forward["Changed_Pairs"])
    rel = forward["Changed_Relative_MAE_vs_Confirmed"]
    wins = forward["Changed_Win_Share_vs_Confirmed"]
    vs_pre = forward["Materiality_Relative_MAE_vs_Preconfirm"]
    bias_change = forward["Materiality_Bias_Abs_Change_vs_Confirmed"]
    ready = pairs >= MIN_OOS_PAIRS and days >= MIN_OOS_DAYS and opponents >= MIN_OOS_OPPONENTS and changed >= MIN_CHANGED_PAIRS
    manual_ready = False

    if not ready:
        finding = "INCONCLUSIVE"
        reason = (
            f"Need {MIN_OOS_PAIRS} forward pairs, {MIN_OOS_DAYS} days, {MIN_OOS_OPPONENTS} opponents, "
            f"and {MIN_CHANGED_PAIRS} immaterial changed pairs; have {pairs}, {days}, {opponents}, and {changed}."
        )
        action = "KEEP_MATERIALITY_THRESHOLD_FROZEN_AND_LEARN"
    elif (
        pd.notna(rel) and pd.notna(wins) and pd.notna(vs_pre) and pd.notna(bias_change)
        and float(rel) >= MIN_SUPPORT_RELATIVE_MAE
        and float(wins) >= MIN_SUPPORT_WIN_SHARE
        and float(vs_pre) >= 0.0
        and float(bias_change) <= BIAS_WORSEN_TOLERANCE
    ):
        finding = "SUPPORTED"
        reason = "Frozen materiality threshold clears changed-pair MAE/win-share, preserves value versus pre-confirm, and passes bias guardrail."
        action = "MANUAL_LINEUP_CANDIDATE_REVIEW_ONLY"
        manual_ready = True
    elif pd.notna(rel) and pd.notna(wins) and float(rel) < 0.0 and float(wins) < 0.50:
        finding = "HURTING"
        reason = "Frozen materiality threshold worsens forward changed-pair MAE and loses head-to-head versus full confirmed-lineup candidate."
        action = "REJECT_THRESHOLD_KEEP_LINEUP_CANDIDATE_UNCHANGED"
    else:
        finding = "MIXED"
        reason = "Forward sample clears size/diversity gates but does not clearly support or reject the materiality threshold."
        action = "KEEP_LINEUP_CANDIDATE_UNCHANGED_PENDING_MANUAL_REVIEW"

    return pd.DataFrame([{
        "Finding": finding, "Early_Read": early, "Forward_Pairs": pairs,
        "Forward_Days": days, "Forward_Opponents": opponents,
        "Forward_Changed_Pairs": changed, "Changed_Relative_MAE_vs_Confirmed": rel,
        "Changed_Win_Share_vs_Confirmed": wins,
        "Materiality_Relative_MAE_vs_Preconfirm": vs_pre,
        "Materiality_Bias_Abs_Change_vs_Confirmed": bias_change,
        "Reason": reason, "Recommended_Action": action,
        "Manual_Review_Ready": manual_ready, "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY, "Validation_Version": VERSION,
    }], columns=GATE_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only frozen confirmed-lineup materiality shadow")
    parser.add_argument("--source", type=Path, default=Path("data/lineup_k_walkforward_detail.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/lineup_materiality_shadow_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/lineup_materiality_shadow_summary.csv"))
    parser.add_argument("--gate", type=Path, default=Path("data/lineup_materiality_shadow_gate.csv"))
    args = parser.parse_args()
    if not args.source.exists():
        raise SystemExit(f"Missing source detail: {args.source}")
    detail = build_detail(pd.read_csv(args.source))
    summary = summarize(detail)
    gate = build_gate(summary)
    args.detail.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    gate.to_csv(args.gate, index=False)
    print(gate.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} materiality_k={FROZEN_MATERIALITY_K}")


if __name__ == "__main__":
    main()

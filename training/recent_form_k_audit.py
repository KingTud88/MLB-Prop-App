from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "recent-form-k-v1-report-only"
MIN_BUCKET_STARTS = 30
MIN_SIGNAL_SPREAD = 0.015


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[col], errors="coerce")


def build_detail(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    prior_k9 = _num(work, "feature_payload.prior_k_per_9")
    recent3_k9 = _num(work, "feature_payload.recent3_k_per_9")
    recent5_k9 = _num(work, "feature_payload.recent5_k_per_9")
    prior_k_rate = _num(work, "feature_payload.prior_k_rate")
    actual_k = _num(work, "actual_strikeouts")
    actual_bf = _num(work, "actual_batters_faced")
    prior_games = _num(work, "feature_payload.prior_games")

    ready = (
        prior_k9.gt(0)
        & recent3_k9.gt(0)
        & recent5_k9.gt(0)
        & prior_k_rate.gt(0)
        & actual_k.notna()
        & actual_bf.gt(0)
        & prior_games.ge(5)
    )
    work = work.loc[ready].copy()
    if work.empty:
        return pd.DataFrame()

    prior_k9 = prior_k9.loc[ready].astype(float)
    recent3_k9 = recent3_k9.loc[ready].astype(float)
    recent5_k9 = recent5_k9.loc[ready].astype(float)
    prior_k_rate = prior_k_rate.loc[ready].astype(float)
    actual_k = actual_k.loc[ready].astype(float)
    actual_bf = actual_bf.loc[ready].astype(float)

    # Average two short-horizon views so one extreme 3-start run does not
    # dominate. This is descriptive only and never changes production.
    recent_blend_k9 = 0.4 * recent3_k9 + 0.6 * recent5_k9
    divergence = recent_blend_k9 / prior_k9 - 1.0
    actual_k_rate = actual_k / actual_bf
    residual_vs_prior = actual_k_rate - prior_k_rate

    work["Prior_K9"] = prior_k9
    work["Recent3_K9"] = recent3_k9
    work["Recent5_K9"] = recent5_k9
    work["RecentBlend_K9"] = recent_blend_k9
    work["Recent_vs_Prior_Divergence"] = divergence
    work["Prior_K_Rate"] = prior_k_rate
    work["Actual_K_Rate"] = actual_k_rate
    work["Actual_K_Rate_Residual_vs_Prior"] = residual_vs_prior
    work["Validation_Version"] = VERSION
    return work


def summarize(detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if detail is None or detail.empty:
        summary = pd.DataFrame([{
            "Metric": "STRIKEOUTS",
            "Evaluated_Starts": 0,
            "Powered_Buckets": 0,
            "Status": "LEARNING",
            "Reason": "no_rows",
            "Production_Authority": "NONE",
            "Validation_Version": VERSION,
        }])
        return summary, pd.DataFrame()

    work = detail.copy()
    divergence = _num(work, "Recent_vs_Prior_Divergence")
    residual = _num(work, "Actual_K_Rate_Residual_vs_Prior")
    ready = divergence.notna() & residual.notna()
    work = work.loc[ready].copy()
    divergence = divergence.loc[ready]
    residual = residual.loc[ready]

    if len(work) < 3:
        summary = pd.DataFrame([{
            "Metric": "STRIKEOUTS", "Evaluated_Starts": int(len(work)), "Powered_Buckets": 0,
            "Status": "LEARNING", "Reason": "sample", "Production_Authority": "NONE",
            "Validation_Version": VERSION,
        }])
        return summary, pd.DataFrame()

    try:
        work["Form_Bucket"] = pd.qcut(divergence, 3, labels=["COLD", "NEUTRAL", "HOT"], duplicates="drop")
    except ValueError:
        work["Form_Bucket"] = "UNAVAILABLE"

    rows: list[dict[str, object]] = []
    for label, group in work.groupby("Form_Bucket", observed=True):
        div = _num(group, "Recent_vs_Prior_Divergence")
        res = _num(group, "Actual_K_Rate_Residual_vs_Prior")
        rows.append({
            "Form_Bucket": str(label),
            "Starts": int(len(group)),
            "Mean_Recent_vs_Prior_Divergence": float(div.mean()),
            "Mean_K_Rate_Residual_vs_Prior": float(res.mean()),
            "Median_K_Rate_Residual_vs_Prior": float(res.median()),
            "Residual_MAE": float(res.abs().mean()),
            "Validation_Version": VERSION,
        })
    buckets = pd.DataFrame(rows)
    powered = buckets.loc[buckets["Starts"].ge(MIN_BUCKET_STARTS)].copy() if not buckets.empty else pd.DataFrame()

    status, reason = "LEARNING", "bucket_sample"
    spread = np.nan
    corr = float(divergence.rank().corr(residual.rank())) if len(work) >= 3 else np.nan
    by_name = {str(r["Form_Bucket"]): r for _, r in powered.iterrows()}
    if {"COLD", "HOT"}.issubset(by_name):
        cold = float(by_name["COLD"]["Mean_K_Rate_Residual_vs_Prior"])
        hot = float(by_name["HOT"]["Mean_K_Rate_Residual_vs_Prior"])
        spread = hot - cold
        if cold < 0 < hot and spread >= MIN_SIGNAL_SPREAD and np.isfinite(corr) and corr > 0:
            status, reason = "SIGNAL", "directional_spread"
        elif spread <= -MIN_SIGNAL_SPREAD and np.isfinite(corr) and corr < 0:
            status, reason = "ANTI_SIGNAL", "reversed"
        else:
            status, reason = "MIXED", "guardrail"

    summary = pd.DataFrame([{
        "Metric": "STRIKEOUTS",
        "Evaluated_Starts": int(len(work)),
        "Powered_Buckets": int(len(powered)),
        "Spearman_Form_vs_Next_K_Rate_Residual": corr,
        "HOT_minus_COLD_Residual_Spread": spread,
        "Status": status,
        "Reason": reason,
        "Production_Authority": "NONE",
        "Validation_Version": VERSION,
    }])
    return summary, buckets


def main() -> None:
    p = argparse.ArgumentParser(description="Report-only recent-form K divergence audit")
    p.add_argument("--snapshots", type=Path, default=Path("data/historical_snapshots.csv"))
    p.add_argument("--detail", type=Path, default=Path("data/recent_form_k_detail.csv"))
    p.add_argument("--buckets", type=Path, default=Path("data/recent_form_k_buckets.csv"))
    p.add_argument("--summary", type=Path, default=Path("data/recent_form_k_summary.csv"))
    args = p.parse_args()
    frame = pd.read_csv(args.snapshots) if args.snapshots.exists() else pd.DataFrame()
    if frame.empty:
        raise SystemExit("No historical snapshots available")
    detail = build_detail(frame)
    summary, buckets = summarize(detail)
    for path in (args.detail, args.buckets, args.summary):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    buckets.to_csv(args.buckets, index=False)
    summary.to_csv(args.summary, index=False)
    print(summary.to_string(index=False))
    if not buckets.empty:
        print(buckets.to_string(index=False))


if __name__ == "__main__":
    main()

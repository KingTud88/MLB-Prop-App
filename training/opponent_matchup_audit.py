from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

AUDIT_VERSION = "opponent-matchup-v1-report-only"
MIN_BUCKET_STARTS = 20

SPECS = {
    "STRIKEOUTS": {
        "feature": "opponent_k_pct",
        "projection": "projection",
        "actual": "actual_strikeouts",
    },
    "HITS": {
        "feature": "opponent_hit_rate",
        "projection": "hits_projection",
        "actual": "actual_hits_allowed",
    },
}


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[col], errors="coerce")


def _tercile_labels(values: pd.Series) -> pd.Series:
    """Bucket only on the captured feature distribution, never on outcomes."""
    ranked = values.rank(method="average", pct=True)
    return pd.cut(
        ranked,
        bins=[0.0, 1 / 3, 2 / 3, 1.0],
        labels=["LOW", "MID", "HIGH"],
        include_lowest=True,
    )


def bucket_report(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for metric, spec in SPECS.items():
        feature = _num(frame, spec["feature"])
        projection = _num(frame, spec["projection"])
        actual = _num(frame, spec["actual"])
        ready = feature.notna() & projection.notna() & actual.notna()
        if not ready.any():
            continue
        work = pd.DataFrame(
            {
                "feature": feature[ready].astype(float),
                "projection": projection[ready].astype(float),
                "actual": actual[ready].astype(float),
            }
        )
        work["bucket"] = _tercile_labels(work["feature"])
        work["error"] = work["projection"] - work["actual"]
        for bucket, group in work.groupby("bucket", observed=False):
            if group.empty:
                continue
            n = int(len(group))
            rows.append(
                {
                    "Metric": metric,
                    "Feature": spec["feature"],
                    "Bucket": str(bucket),
                    "Resolved_Starts": n,
                    "Feature_Mean": float(group["feature"].mean()),
                    "Projection_MAE": float(group["error"].abs().mean()),
                    "Projection_Bias": float(group["error"].mean()),
                    "Powered": bool(n >= MIN_BUCKET_STARTS),
                    "Audit_Version": AUDIT_VERSION,
                }
            )
    return pd.DataFrame(rows)


def summary_report(bucket_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if bucket_frame is None or bucket_frame.empty:
        return pd.DataFrame()
    order = {"LOW": 0, "MID": 1, "HIGH": 2}
    for metric, group in bucket_frame.groupby("Metric"):
        powered = group[group["Powered"].astype(bool)].copy()
        powered["_order"] = powered["Bucket"].map(order)
        powered = powered.sort_values("_order")
        if len(powered) < 3:
            rows.append(
                {
                    "Metric": metric,
                    "Powered_Buckets": int(len(powered)),
                    "Low_Bias": float("nan"),
                    "Mid_Bias": float("nan"),
                    "High_Bias": float("nan"),
                    "Bias_Spread_High_minus_Low": float("nan"),
                    "Monotonic_Bias": False,
                    "Status": "LEARNING",
                    "Audit_Version": AUDIT_VERSION,
                }
            )
            continue
        bias_map = dict(zip(powered["Bucket"], powered["Projection_Bias"]))
        low = float(bias_map.get("LOW", np.nan))
        mid = float(bias_map.get("MID", np.nan))
        high = float(bias_map.get("HIGH", np.nan))
        monotonic = bool((low <= mid <= high) or (low >= mid >= high))
        spread = float(high - low)
        # Descriptive status only. We do not call a candidate from this first pass.
        status = "PATTERN" if monotonic and abs(spread) >= 0.25 else "MIXED"
        rows.append(
            {
                "Metric": metric,
                "Powered_Buckets": 3,
                "Low_Bias": low,
                "Mid_Bias": mid,
                "High_Bias": high,
                "Bias_Spread_High_minus_Low": spread,
                "Monotonic_Bias": monotonic,
                "Status": status,
                "Audit_Version": AUDIT_VERSION,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only opponent matchup residual audit")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--buckets", type=Path, default=Path("data/opponent_matchup_buckets.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/opponent_matchup_summary.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("No projection history available")
    buckets = bucket_report(history)
    summary = summary_report(buckets)
    if buckets.empty:
        raise SystemExit("No resolved matchup rows available")
    args.buckets.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    buckets.to_csv(args.buckets, index=False)
    summary.to_csv(args.summary, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

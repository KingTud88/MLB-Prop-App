from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

AUDIT_VERSION = "environment-effect-v1-report-only"
MIN_STARTS = 20


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(frame[col], errors="coerce") if col in frame.columns else pd.Series(np.nan, index=frame.index)


def _k_ready(frame: pd.DataFrame) -> pd.Series:
    return _num(frame, "projection").notna() & _num(frame, "actual_strikeouts").notna()


def _err(frame: pd.DataFrame) -> pd.Series:
    return _num(frame, "projection") - _num(frame, "actual_strikeouts")


def _row(group: str, bucket: str, frame: pd.DataFrame) -> dict[str, object]:
    ready = _k_ready(frame)
    e = _err(frame)[ready].astype(float)
    return {
        "Environment_Group": group,
        "Bucket": bucket,
        "Resolved_K_Starts": int(ready.sum()),
        "MAE": float(e.abs().mean()) if len(e) else float("nan"),
        "Bias": float(e.mean()) if len(e) else float("nan"),
        "Status": "POWERED" if int(ready.sum()) >= MIN_STARTS else "LEARNING",
        "Audit_Version": AUDIT_VERSION,
    }


def environment_effect_report(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    # Weather coverage effect: context present vs absent. Descriptive only;
    # this does not claim causality because weather availability may be era-linked.
    weather = frame.get("weather_summary", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip()
    rows.append(_row("WEATHER", "CONTEXT_PRESENT", frame.loc[weather.ne("")]))
    rows.append(_row("WEATHER", "CONTEXT_ABSENT", frame.loc[weather.eq("")]))

    # Umpire factor must actually vary before it can be considered informative.
    ump = _num(frame, "umpire_k_factor")
    ready_ump = _k_ready(frame) & ump.notna()
    unique_ump = int(ump[ready_ump].nunique())
    if unique_ump >= 3:
        try:
            buckets = pd.qcut(ump[ready_ump], q=3, labels=["LOW", "MID", "HIGH"], duplicates="drop")
            tmp = frame.loc[ready_ump].copy()
            tmp["_bucket"] = buckets.astype(str)
            for bucket, group in tmp.groupby("_bucket"):
                rows.append(_row("UMPIRE", str(bucket), group))
        except ValueError:
            rows.append({"Environment_Group":"UMPIRE","Bucket":"NO_VARIATION","Resolved_K_Starts":int(ready_ump.sum()),"MAE":float("nan"),"Bias":float("nan"),"Status":"NO_VARIATION","Audit_Version":AUDIT_VERSION})
    else:
        rows.append({"Environment_Group":"UMPIRE","Bucket":"NO_VARIATION","Resolved_K_Starts":int(ready_ump.sum()),"MAE":float("nan"),"Bias":float("nan"),"Status":"NO_VARIATION","Audit_Version":AUDIT_VERSION})

    # Venue effect: only individually evaluate parks with at least MIN_STARTS
    # resolved K starts so tiny samples cannot look meaningful.
    venue = frame.get("venue", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip()
    tmp = frame.loc[_k_ready(frame) & venue.ne("")].copy()
    if not tmp.empty:
        tmp["_venue"] = venue.loc[tmp.index]
        counts = tmp["_venue"].value_counts()
        powered = counts[counts >= MIN_STARTS].index.tolist()
        if powered:
            for name in powered:
                rows.append(_row("PARK", str(name), tmp.loc[tmp["_venue"].eq(name)]))
        else:
            rows.append({"Environment_Group":"PARK","Bucket":"NO_POWERED_VENUES","Resolved_K_Starts":int(len(tmp)),"MAE":float("nan"),"Bias":float("nan"),"Status":"LEARNING","Audit_Version":AUDIT_VERSION})

    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser(description="Report-only weather/umpire/park K residual audit")
    p.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    p.add_argument("--output", type=Path, default=Path("data/environment_effect_summary.csv"))
    args = p.parse_args()
    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("No projection history available")
    report = environment_effect_report(history)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()

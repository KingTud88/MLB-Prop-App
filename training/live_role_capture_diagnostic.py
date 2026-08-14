from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DIAGNOSTIC_VERSION = "live-role-capture-diagnostic-v1"


def _text(frame: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="object")
    return frame[column].fillna(default).astype(str).str.strip()


def build_diagnostic(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()

    role = _text(frame, "starter_role_label", "MISSING").replace("", "MISSING")
    version = _text(frame, "role_workload_version", "MISSING").replace("", "MISSING")
    mode = _text(frame, "role_workload_mode", "MISSING").replace("", "MISSING")
    reason = _text(frame, "role_workload_reason", "MISSING").replace("", "MISSING")
    captured = pd.to_datetime(frame.get("captured_at_utc"), errors="coerce", utc=True)
    resolved = _text(frame, "resolved_at_utc").ne("")
    eligible = _text(frame, "role_workload_eligible").str.lower().isin({"true", "1", "yes"})

    work = pd.DataFrame({
        "Role": role,
        "Version": version,
        "Mode": mode,
        "Reason": reason,
        "Captured_Date": captured.dt.strftime("%Y-%m-%d").fillna("UNKNOWN"),
        "Resolved": resolved,
        "Eligible": eligible,
    })

    rows: list[dict[str, object]] = []
    for (r, v, m, why), group in work.groupby(["Role", "Version", "Mode", "Reason"], dropna=False):
        rows.append({
            "Role": r,
            "Version": v,
            "Mode": m,
            "Reason": why,
            "Rows": int(len(group)),
            "Resolved_Rows": int(group["Resolved"].sum()),
            "Eligible_Rows": int(group["Eligible"].sum()),
            "First_Captured_Date": str(group["Captured_Date"].min()),
            "Last_Captured_Date": str(group["Captured_Date"].max()),
            "Diagnostic_Version": DIAGNOSTIC_VERSION,
        })

    return pd.DataFrame(rows).sort_values(["Rows", "Role"], ascending=[False, True]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose persisted live starter-role shadow coverage.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/live_role_capture_diagnostic.csv"))
    args = parser.parse_args()

    frame = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if frame.empty:
        raise SystemExit("Projection log is empty")
    report = build_diagnostic(frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()

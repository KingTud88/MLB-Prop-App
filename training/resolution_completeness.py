from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "projection_log.csv"
AUDIT_VERSION = "resolution-completeness-v1"
REQUIRED_ACTUALS = ("actual_strikeouts", "actual_pitches", "actual_batters_faced", "actual_outs")
DEFAULT_GRACE_HOURS = 18.0


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def build_detail(frame: pd.DataFrame, now: pd.Timestamp, grace_hours: float) -> pd.DataFrame:
    if frame.empty or not {"game_pk", "pitcher_id", "game_time"}.issubset(frame.columns):
        return pd.DataFrame()

    work = frame.copy()
    work["game_pk"] = pd.to_numeric(work["game_pk"], errors="coerce")
    work["pitcher_id"] = pd.to_numeric(work["pitcher_id"], errors="coerce")
    work["game_time_dt"] = pd.to_datetime(work["game_time"], errors="coerce", utc=True)
    if "captured_at_utc" in work.columns:
        work["captured_dt"] = pd.to_datetime(work["captured_at_utc"], errors="coerce", utc=True)
    else:
        work["captured_dt"] = pd.NaT

    for col in REQUIRED_ACTUALS:
        if col not in work.columns:
            work[col] = pd.NA
        work[col] = pd.to_numeric(work[col], errors="coerce")

    ready = work["game_pk"].notna() & work["pitcher_id"].notna() & work["game_time_dt"].notna()
    work = work.loc[ready].copy()
    if work.empty:
        return pd.DataFrame()

    # A starter may be captured more than once as the slate refreshes. Resolution
    # authority is game+pitcher, so collapse to one row and prefer any available
    # resolved actuals across duplicate snapshots.
    rows: list[dict[str, object]] = []
    for (game_pk, pitcher_id), group in work.groupby(["game_pk", "pitcher_id"], sort=False):
        group = group.sort_values("captured_dt", na_position="last")
        first = group.iloc[0]
        record: dict[str, object] = {
            "game_pk": int(game_pk),
            "pitcher_id": int(pitcher_id),
            "game_date": str(first.get("game_date", "")),
            "player": first.get("player", "Unknown"),
            "team": first.get("team", "UNK"),
            "opponent": first.get("opponent", "UNK"),
            "game_time": first.get("game_time", ""),
        }
        missing: list[str] = []
        for col in REQUIRED_ACTUALS:
            values = pd.to_numeric(group[col], errors="coerce").dropna()
            value = float(values.iloc[-1]) if not values.empty else pd.NA
            record[col] = value
            if pd.isna(value):
                missing.append(col)

        game_time = pd.to_datetime(first["game_time_dt"], utc=True)
        age_hours = float((now - game_time).total_seconds() / 3600.0)
        if not missing:
            status = "RESOLVED"
        elif age_hours >= float(grace_hours):
            status = "STUCK"
        elif age_hours >= 0:
            status = "AWAITING_RESOLUTION"
        else:
            status = "UPCOMING"
        record.update({
            "age_hours": age_hours,
            "resolution_status": status,
            "missing_actuals": "|".join(missing),
            "audit_version": AUDIT_VERSION,
        })
        rows.append(record)
    return pd.DataFrame(rows)


def build_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame([{
            "Total_Archived_Starters": 0,
            "Resolved": 0,
            "Awaiting_Resolution": 0,
            "Upcoming": 0,
            "Stuck": 0,
            "Resolution_Rate_Eligible": 0.0,
            "Audit_Version": AUDIT_VERSION,
        }])
    counts = detail["resolution_status"].value_counts().to_dict()
    eligible = detail["resolution_status"].isin(["RESOLVED", "STUCK"])
    eligible_n = int(eligible.sum())
    resolved_n = int(detail["resolution_status"].eq("RESOLVED").sum())
    return pd.DataFrame([{
        "Total_Archived_Starters": int(len(detail)),
        "Resolved": resolved_n,
        "Awaiting_Resolution": int(counts.get("AWAITING_RESOLUTION", 0)),
        "Upcoming": int(counts.get("UPCOMING", 0)),
        "Stuck": int(counts.get("STUCK", 0)),
        "Resolution_Rate_Eligible": float(resolved_n / eligible_n) if eligible_n else 1.0,
        "Audit_Version": AUDIT_VERSION,
    }])


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit durable projection resolution completeness")
    parser.add_argument("--projection-log", type=Path, default=LOG_PATH)
    parser.add_argument("--detail", type=Path, default=ROOT / "data" / "resolution_completeness_detail.csv")
    parser.add_argument("--summary", type=Path, default=ROOT / "data" / "resolution_completeness_summary.csv")
    parser.add_argument("--grace-hours", type=float, default=DEFAULT_GRACE_HOURS)
    parser.add_argument("--fail-on-stuck", action="store_true")
    args = parser.parse_args()

    frame = _load(args.projection_log)
    now = pd.Timestamp(datetime.now(timezone.utc))
    detail = build_detail(frame, now=now, grace_hours=float(args.grace_hours))
    summary = build_summary(detail)
    for path in (args.detail, args.summary):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    print(summary.to_string(index=False))

    stuck = detail.loc[detail.get("resolution_status", pd.Series(dtype=str)).eq("STUCK")]
    if not stuck.empty:
        print("stuck archived starters:")
        print(stuck[["game_date", "player", "team", "opponent", "game_pk", "missing_actuals", "age_hours"]].to_string(index=False))
        if args.fail_on_stuck:
            raise SystemExit(2)


if __name__ == "__main__":
    main()

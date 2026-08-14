from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from automation.daily_projection_runner import schedule

ROOT = Path(__file__).resolve().parents[1]
PROJECTION_LOG = ROOT / "data" / "projection_log.csv"
OBSERVATION_LOG = ROOT / "data" / "starter_observation_log.csv"
EASTERN = ZoneInfo("America/New_York")
AUDIT_VERSION = "slate-capture-integrity-v1"


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _keys(frame: pd.DataFrame, day: str) -> set[tuple[int, int]]:
    if frame.empty or not {"game_pk", "pitcher_id"}.issubset(frame.columns):
        return set()
    work = frame.copy()
    if "game_date" in work.columns:
        work = work.loc[work["game_date"].astype(str).eq(str(day))].copy()
    game_pk = pd.to_numeric(work["game_pk"], errors="coerce")
    pitcher_id = pd.to_numeric(work["pitcher_id"], errors="coerce")
    ready = game_pk.notna() & pitcher_id.notna()
    return {(int(g), int(p)) for g, p in zip(game_pk[ready], pitcher_id[ready])}


def build_audit(day: str) -> pd.DataFrame:
    announced = schedule(day)
    projections = _load(PROJECTION_LOG)
    observations = _load(OBSERVATION_LOG)
    projected_keys = _keys(projections, day)
    observed_keys = _keys(observations, day)

    rows: list[dict[str, object]] = []
    for starter in announced:
        key = (int(starter.get("game_pk", 0) or 0), int(starter.get("pitcher_id", 0) or 0))
        if key in projected_keys:
            status = "PROJECTED"
        elif key in observed_keys:
            status = "HISTORY_ONLY"
        else:
            status = "MISSING"
        rows.append({
            "game_date": day,
            "game_pk": key[0],
            "pitcher_id": key[1],
            "player": starter.get("player", "Unknown"),
            "team": starter.get("team", "UNK"),
            "opponent": starter.get("opponent", "UNK"),
            "game_time": starter.get("game_time", ""),
            "schedule_status": starter.get("status", ""),
            "capture_status": status,
            "audit_version": AUDIT_VERSION,
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only audit of announced starter capture coverage")
    parser.add_argument("--date", default=datetime.now(EASTERN).date().isoformat())
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "slate_capture_integrity.csv")
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args()

    report = build_audit(str(args.date))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)

    if report.empty:
        print(f"date={args.date} announced=0")
        return
    counts = report["capture_status"].value_counts().to_dict()
    missing = report.loc[report["capture_status"].eq("MISSING")]
    print(report.to_string(index=False))
    print(f"date={args.date} announced={len(report)} counts={counts}")
    if not missing.empty:
        print("missing starters:")
        print(missing[["player", "team", "opponent", "game_pk", "pitcher_id"]].to_string(index=False))
        if args.fail_on_missing:
            raise SystemExit(2)


if __name__ == "__main__":
    main()

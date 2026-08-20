from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from engine.sportsgameodds import (
    HISTORY_PATH,
    PROJECTION_LOG_PATH,
    SNAPSHOT_PATH,
    STATUS_PATH,
    apply_selected_lines_to_projection_log,
    fetch_slate_offers,
    persist_capture,
    resolve_api_key,
)

EASTERN = ZoneInfo("America/New_York")


def status_covers_slate(slate_date: str, status_path: Path = STATUS_PATH) -> bool:
    """Return True only when the durable central SGO status already covers this slate."""
    if not status_path.exists():
        return False
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return False
    return str(payload.get("slate_date") or "").strip() == str(slate_date).strip()


def run_capture(
    slate_date: str,
    *,
    api_key: str,
    projection_log_path: Path = PROJECTION_LOG_PATH,
    snapshot_path: Path = SNAPSHOT_PATH,
    history_path: Path = HISTORY_PATH,
    status_path: Path = STATUS_PATH,
    session=None,
) -> dict[str, object]:
    offers, metadata, error = fetch_slate_offers(api_key, slate_date, session=session)
    if error:
        raise RuntimeError(error)

    selected = persist_capture(
        offers,
        metadata,
        snapshot_path=snapshot_path,
        history_path=history_path,
        status_path=status_path,
    )
    applied = 0
    if projection_log_path.exists():
        try:
            projection_log = pd.read_csv(projection_log_path)
        except Exception as exc:
            raise RuntimeError(f"Could not read projection log: {type(exc).__name__}.") from exc
        updated, applied = apply_selected_lines_to_projection_log(projection_log, selected, slate_date)
        if not updated.empty:
            updated.to_csv(projection_log_path, index=False)

    result = dict(metadata)
    result.update({
        "selected_pair_count": int(len(selected) // 2),
        "projection_lines_applied": int(applied),
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture authentic MLB pitcher prop lines from SportsGameOdds")
    parser.add_argument("--slate-date", default=datetime.now(EASTERN).date().isoformat())
    parser.add_argument("--projection-log", type=Path, default=PROJECTION_LOG_PATH)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--history", type=Path, default=HISTORY_PATH)
    parser.add_argument("--status", type=Path, default=STATUS_PATH)
    parser.add_argument(
        "--skip-if-current-slate",
        action="store_true",
        help="Exit without an API call when the durable central status already covers the target slate.",
    )
    args = parser.parse_args()

    slate_date = str(args.slate_date)
    if args.skip_if_current_slate and status_covers_slate(slate_date, args.status):
        print(f"SportsGameOdds capture skipped: centralized snapshot already covers {slate_date}.")
        return

    api_key = resolve_api_key()
    if not api_key:
        raise SystemExit("SPORTSGAMEODDS_API_KEY is not configured for this runner.")
    result = run_capture(
        slate_date,
        api_key=api_key,
        projection_log_path=args.projection_log,
        snapshot_path=args.snapshot,
        history_path=args.history,
        status_path=args.status,
    )
    print(
        "SportsGameOdds capture complete: "
        f"events={result.get('event_count', 0)} "
        f"offers={result.get('offer_count', 0)} "
        f"selected_pairs={result.get('selected_pair_count', 0)} "
        f"projection_lines_applied={result.get('projection_lines_applied', 0)}"
    )
    notice = str(result.get("notice") or "").strip()
    if notice:
        print(f"Provider notice: {notice}")


if __name__ == "__main__":
    main()

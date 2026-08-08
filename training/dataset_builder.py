from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .snapshot_schema import PregameSnapshot, snapshots_to_frame, validate_training_frame


SNAPSHOT_COLUMNS = [
    "game_id",
    "game_date",
    "pitcher_id",
    "pitcher_name",
    "opponent_team",
    "captured_at_utc",
    "snapshot_version",
    "snapshot_hash",
    "actual_strikeouts",
    "actual_batters_faced",
]


def build_training_frame(snapshots: Iterable[PregameSnapshot]) -> pd.DataFrame:
    """Flatten archived snapshots and require resolved outcomes."""
    frame = snapshots_to_frame(list(snapshots))
    if frame.empty:
        return frame
    validate_training_frame(frame)
    frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
    frame["captured_at_utc"] = pd.to_datetime(frame["captured_at_utc"], errors="coerce", utc=True)
    frame = frame.sort_values(["game_date", "captured_at_utc", "game_id"]).reset_index(drop=True)
    return frame


def save_snapshot_dataset(frame: pd.DataFrame, path: str | Path) -> None:
    """Persist a resolved dataset as parquet when available, otherwise CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)


def load_snapshot_dataset(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    validate_training_frame(frame)
    return frame

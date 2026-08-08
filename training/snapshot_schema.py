from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

import pandas as pd


SNAPSHOT_VERSION = "1.0.0"


@dataclass(frozen=True)
class PregameSnapshot:
    """Immutable record of information available immediately before a game."""

    game_id: str
    game_date: str
    pitcher_id: str
    pitcher_name: str
    opponent_team: str
    captured_at_utc: str
    feature_payload: dict[str, Any]
    source_versions: dict[str, str]
    actual_strikeouts: int | None = None
    actual_batters_faced: int | None = None

    @property
    def snapshot_version(self) -> str:
        return SNAPSHOT_VERSION

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["snapshot_version"] = SNAPSHOT_VERSION
        record["snapshot_hash"] = snapshot_hash(record)
        return record


def snapshot_hash(record: Mapping[str, Any]) -> str:
    """Stable hash used to detect accidental mutation of archived snapshots."""
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def make_snapshot(
    *,
    game_id: str,
    game_date: str | datetime,
    pitcher_id: str,
    pitcher_name: str,
    opponent_team: str,
    features: Mapping[str, Any],
    source_versions: Mapping[str, str] | None = None,
    actual_strikeouts: int | None = None,
    actual_batters_faced: int | None = None,
) -> PregameSnapshot:
    """Create a snapshot with an explicit UTC capture timestamp.

    Outcomes are optional so the same schema can represent a live pregame
    record and its later resolved historical version. Training code should
    require a non-null outcome and must never add postgame features.
    """
    if isinstance(game_date, datetime):
        date_value = game_date.date().isoformat()
    else:
        date_value = str(game_date)

    return PregameSnapshot(
        game_id=str(game_id),
        game_date=date_value,
        pitcher_id=str(pitcher_id),
        pitcher_name=str(pitcher_name),
        opponent_team=str(opponent_team),
        captured_at_utc=datetime.now(timezone.utc).isoformat(),
        feature_payload=dict(features),
        source_versions=dict(source_versions or {}),
        actual_strikeouts=actual_strikeouts,
        actual_batters_faced=actual_batters_faced,
    )


def snapshots_to_frame(snapshots: list[PregameSnapshot]) -> pd.DataFrame:
    rows = [snapshot.to_record() for snapshot in snapshots]
    return pd.json_normalize(rows) if rows else pd.DataFrame()


def validate_training_frame(frame: pd.DataFrame) -> None:
    """Fail closed if required snapshot/outcome fields are missing."""
    required = {"game_id", "game_date", "pitcher_id", "captured_at_utc", "actual_strikeouts"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Training frame missing required fields: {sorted(missing)}")
    if frame["actual_strikeouts"].isna().any():
        raise ValueError("Training data contains unresolved games")
    if (pd.to_numeric(frame["actual_strikeouts"], errors="coerce") < 0).any():
        raise ValueError("Strikeout outcomes cannot be negative")

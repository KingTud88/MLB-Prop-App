from __future__ import annotations

import pandas as pd

HISTORY_SEMANTICS = "starter-only-v1"
MIN_STARTS_FOR_TOP_PLAY = 3
TARGET_STARTER_HISTORY = 12
MAX_STARTER_HISTORY = 35


def starter_only(frame: pd.DataFrame) -> pd.DataFrame:
    """Return only appearances explicitly identified by MLB as starts.

    The caller must populate a ``games_started`` column from each game-log split's
    ``gamesStarted`` stat. Missing starter identity is treated as unusable rather
    than guessing from innings pitched or batters faced.
    """
    if frame.empty or "games_started" not in frame.columns:
        return frame.iloc[0:0].copy()
    started = pd.to_numeric(frame["games_started"], errors="coerce").fillna(0)
    out = frame.loc[started.ge(1)].copy()
    if "date" in out.columns:
        out = out.sort_values("date")
    return out.reset_index(drop=True)


def combine_starter_history(
    current: pd.DataFrame,
    prior: pd.DataFrame | None = None,
    *,
    limit: int = MAX_STARTER_HISTORY,
) -> pd.DataFrame:
    """Combine current/prior starter-only logs while preserving chronological order."""
    pieces = [starter_only(current)]
    if prior is not None and not prior.empty:
        pieces.insert(0, starter_only(prior))
    pieces = [piece for piece in pieces if not piece.empty]
    if not pieces:
        columns = list(current.columns) if not current.empty else (list(prior.columns) if prior is not None else [])
        return pd.DataFrame(columns=columns)
    combined = pd.concat(pieces, ignore_index=True)
    if "date" in combined.columns:
        combined = combined.sort_values("date")
        # A duplicated split can occasionally appear across API refreshes; date plus
        # opponent is sufficient for this single-pitcher regular-season game log.
        subset = [c for c in ("date", "opponent") if c in combined.columns]
        if subset:
            combined = combined.drop_duplicates(subset=subset, keep="last")
    return combined.tail(int(limit)).reset_index(drop=True)


def has_minimum_starts(frame: pd.DataFrame, minimum: int = MIN_STARTS_FOR_TOP_PLAY) -> bool:
    return int(len(starter_only(frame))) >= int(minimum)

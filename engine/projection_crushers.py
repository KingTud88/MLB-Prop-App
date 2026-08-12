from __future__ import annotations

import numpy as np
import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS


def directional_k_result(projection: object, actual_strikeouts: object) -> str:
    """Grade the user's directional K rule: actual Ks above projection = WIN."""
    projected = pd.to_numeric(pd.Series([projection]), errors="coerce").iloc[0]
    actual = pd.to_numeric(pd.Series([actual_strikeouts]), errors="coerce").iloc[0]
    if pd.isna(projected) or pd.isna(actual):
        return "PENDING"
    return "✅ WIN" if float(actual) > float(projected) else "❌ MISS"


def _current_win_streak(group: pd.DataFrame) -> int:
    ordered = group.sort_values(["_game_date", "_captured"], ascending=[False, False])
    streak = 0
    for margin in ordered["_margin"].tolist():
        if float(margin) > 0.0:
            streak += 1
        else:
            break
    return streak


def crusher_report(history: pd.DataFrame) -> pd.DataFrame:
    """Summarize pitchers who repeatedly finish above the frozen K projection.

    This is a descriptive decision/evaluation view only. It does not feed the
    baseball forecast, calibration, or Top Plays ranking.
    """
    columns = [
        "Pitcher", "Resolved Starts", "Projection Wins", "Win Rate",
        "Avg K Margin", "Avg Win Margin", "Total K Above Projection",
        "2+ K Crushes", "Recent 5 Win Rate", "Current Win Streak", "Crusher Status",
    ]
    if history is None or history.empty:
        return pd.DataFrame(columns=columns)

    frame = history.copy()
    if "history_semantics" in frame.columns:
        current = frame["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)
        if current.any():
            frame = frame.loc[current].copy()

    frame["_projection"] = pd.to_numeric(frame.get("projection"), errors="coerce")
    frame["_actual"] = pd.to_numeric(frame.get("actual_strikeouts"), errors="coerce")
    frame = frame.loc[frame["_projection"].notna() & frame["_actual"].notna()].copy()
    if frame.empty:
        return pd.DataFrame(columns=columns)

    frame["_margin"] = frame["_actual"] - frame["_projection"]
    frame["_win"] = frame["_margin"] > 0.0
    frame["_game_date"] = pd.to_datetime(frame.get("game_date"), errors="coerce")
    frame["_captured"] = pd.to_datetime(frame.get("captured_at_utc"), errors="coerce", utc=True)

    if "pitcher_id" in frame.columns:
        ids = frame["pitcher_id"].astype(str)
        frame["_pitcher_key"] = np.where(ids.notna() & ids.ne("") & ids.ne("nan"), ids, frame.get("player", "Unknown").astype(str))
    else:
        frame["_pitcher_key"] = frame.get("player", pd.Series("Unknown", index=frame.index)).astype(str)

    rows: list[dict[str, object]] = []
    for _, group in frame.groupby("_pitcher_key", dropna=False):
        ordered = group.sort_values(["_game_date", "_captured"])
        starts = int(len(ordered))
        wins = int(ordered["_win"].sum())
        win_rate = float(wins / starts) if starts else np.nan
        margins = ordered["_margin"].astype(float)
        win_margins = margins[margins > 0.0]
        recent = ordered.tail(5)
        recent_rate = float(recent["_win"].mean()) if not recent.empty else np.nan
        avg_margin = float(margins.mean())
        if starts < 3:
            status = "LEARNING"
        elif win_rate >= (2.0 / 3.0) and avg_margin > 0.5:
            status = "🔥 CRUSHER"
        elif win_rate >= 0.55 and avg_margin > 0.0:
            status = "✅ ABOVE PROJECTION"
        else:
            status = "MIXED"
        rows.append({
            "Pitcher": str(ordered.get("player", pd.Series(["Unknown"])).iloc[-1]),
            "Resolved Starts": starts,
            "Projection Wins": wins,
            "Win Rate": win_rate,
            "Avg K Margin": avg_margin,
            "Avg Win Margin": float(win_margins.mean()) if not win_margins.empty else np.nan,
            "Total K Above Projection": float(margins.clip(lower=0.0).sum()),
            "2+ K Crushes": int((margins >= 2.0).sum()),
            "Recent 5 Win Rate": recent_rate,
            "Current Win Streak": _current_win_streak(ordered),
            "Crusher Status": status,
        })

    report = pd.DataFrame(rows, columns=columns)
    status_rank = {"🔥 CRUSHER": 0, "✅ ABOVE PROJECTION": 1, "LEARNING": 2, "MIXED": 3}
    report["_status_rank"] = report["Crusher Status"].map(status_rank).fillna(9)
    report = report.sort_values(
        ["_status_rank", "Projection Wins", "Win Rate", "Avg K Margin", "Resolved Starts"],
        ascending=[True, False, False, False, False],
    ).drop(columns=["_status_rank"]).reset_index(drop=True)
    return report

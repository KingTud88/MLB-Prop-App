from __future__ import annotations

import math

import numpy as np
import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS

MIN_K_MILESTONE = 3
MAX_K_MILESTONE = 12


def _numeric(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def bettable_k_target(projection: object) -> int | None:
    """Convert a frozen K mean to the highest supported whole-K ladder target.

    A 5.07 projection supports 5+, not 6+. Targets below the app's 3+ ladder
    are intentionally treated as NO CALL. Means above 12 still map to the
    highest currently supported ladder milestone, 12+.
    """
    projected = _numeric(projection)
    if projected is None or projected < float(MIN_K_MILESTONE):
        return None
    return int(min(math.floor(projected), MAX_K_MILESTONE))


def bettable_k_label(projection: object) -> str:
    target = bettable_k_target(projection)
    return "—" if target is None else f"{target}+"


def bettable_k_result(projection: object, actual_strikeouts: object) -> str:
    """Grade the model-derived whole-K milestone supported by the frozen projection.

    This is model-ladder research, not sportsbook execution grading.
    """
    target = bettable_k_target(projection)
    actual = _numeric(actual_strikeouts)
    if target is None:
        return "NO CALL"
    if actual is None:
        return "PENDING"
    return "✅ WIN" if actual >= float(target) else "❌ MISS"


def directional_k_result(projection: object, actual_strikeouts: object) -> str:
    """Grade whether actual strikeouts finished above the exact frozen projection."""
    projected = _numeric(projection)
    actual = _numeric(actual_strikeouts)
    if projected is None or actual is None:
        return "PENDING"
    return "✅ WIN" if actual > projected else "❌ MISS"


def _current_streak(group: pd.DataFrame, flag_col: str) -> int:
    ordered = group.sort_values(["_game_date", "_captured"], ascending=[False, False])
    streak = 0
    for flagged in ordered[flag_col].tolist():
        if bool(flagged):
            streak += 1
        else:
            break
    return streak


def _resolved_exact_projection_frame(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame()
    frame = history.copy()
    if "history_semantics" in frame.columns:
        current = frame["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)
        if current.any():
            frame = frame.loc[current].copy()

    frame["_projection"] = pd.to_numeric(frame.get("projection"), errors="coerce")
    frame["_actual"] = pd.to_numeric(frame.get("actual_strikeouts"), errors="coerce")
    frame = frame.loc[frame["_projection"].notna() & frame["_actual"].notna()].copy()
    if frame.empty:
        return frame

    frame["_margin"] = frame["_actual"] - frame["_projection"]
    frame["_win"] = frame["_margin"].gt(0.0)
    frame["_under"] = frame["_margin"].lt(0.0)
    frame["_game_date"] = pd.to_datetime(frame.get("game_date"), errors="coerce")
    frame["_captured"] = pd.to_datetime(frame.get("captured_at_utc"), errors="coerce", utc=True)

    if "pitcher_id" in frame.columns:
        ids = frame["pitcher_id"].astype(str)
        player_names = frame.get("player", pd.Series("Unknown", index=frame.index)).astype(str)
        frame["_pitcher_key"] = np.where(ids.notna() & ids.ne("") & ids.ne("nan"), ids, player_names)
    else:
        frame["_pitcher_key"] = frame.get("player", pd.Series("Unknown", index=frame.index)).astype(str)
    return frame


def crusher_report(history: pd.DataFrame) -> pd.DataFrame:
    """Summarize pitchers who repeatedly finish above the exact frozen K projection.

    This is descriptive research only. It does not feed the baseball forecast,
    calibration, sportsbook execution, or Top Plays ranking.
    """
    columns = [
        "Pitcher", "Resolved Starts", "Projection Wins", "Win Rate",
        "Avg K vs Projection", "Avg Win Margin", "Total K Above Projection",
        "2+ K Crushes", "Recent 5 Win Rate", "Current Win Streak", "Crusher Status",
        # Transitional aliases keep older Projection History renderers safe while
        # the UI moves from ladder-target Crusher semantics back to exact projection.
        "Ladder Wins", "Avg K Above Target", "Total K Above Target",
    ]
    frame = _resolved_exact_projection_frame(history)
    if frame.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for _, group in frame.groupby("_pitcher_key", dropna=False):
        ordered = group.sort_values(["_game_date", "_captured"])
        starts = int(len(ordered))
        wins = int(ordered["_win"].sum())
        win_rate = float(wins / starts) if starts else np.nan
        margins = ordered["_margin"].astype(float)
        win_margins = margins[ordered["_win"]]
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
        total_above = float(margins.clip(lower=0.0).sum())
        rows.append({
            "Pitcher": str(ordered.get("player", pd.Series(["Unknown"])).iloc[-1]),
            "Resolved Starts": starts,
            "Projection Wins": wins,
            "Win Rate": win_rate,
            "Avg K vs Projection": avg_margin,
            "Avg Win Margin": float(win_margins.mean()) if not win_margins.empty else np.nan,
            "Total K Above Projection": total_above,
            "2+ K Crushes": int((margins >= 2.0).sum()),
            "Recent 5 Win Rate": recent_rate,
            "Current Win Streak": _current_streak(ordered, "_win"),
            "Crusher Status": status,
            "Ladder Wins": wins,
            "Avg K Above Target": avg_margin,
            "Total K Above Target": total_above,
        })

    report = pd.DataFrame(rows, columns=columns)
    status_rank = {"🔥 CRUSHER": 0, "✅ ABOVE PROJECTION": 1, "LEARNING": 2, "MIXED": 3}
    report["_status_rank"] = report["Crusher Status"].map(status_rank).fillna(9)
    report = report.sort_values(
        ["_status_rank", "Projection Wins", "Win Rate", "Avg K vs Projection", "Resolved Starts"],
        ascending=[True, False, False, False, False],
    ).drop(columns=["_status_rank"]).reset_index(drop=True)
    return report


def underperformer_report(history: pd.DataFrame) -> pd.DataFrame:
    """Summarize pitchers who repeatedly finish below the exact frozen K projection.

    This is the symmetric negative-residual companion to ``crusher_report`` and
    remains descriptive research only. It cannot change the live projection,
    calibration, sportsbook execution, or Top Plays ranking.
    """
    columns = [
        "Pitcher", "Resolved Starts", "Below Projection Starts", "Below Projection Rate",
        "Avg K vs Projection", "Median K vs Projection", "Avg Under Margin",
        "Total K Below Projection", "2+ K Under Events", "Recent 5 Below Rate",
        "Current Below Streak", "Underperformer Status",
    ]
    frame = _resolved_exact_projection_frame(history)
    if frame.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for _, group in frame.groupby("_pitcher_key", dropna=False):
        ordered = group.sort_values(["_game_date", "_captured"])
        starts = int(len(ordered))
        below = int(ordered["_under"].sum())
        below_rate = float(below / starts) if starts else np.nan
        margins = ordered["_margin"].astype(float)
        under_margins = margins[ordered["_under"]]
        recent = ordered.tail(5)
        recent_rate = float(recent["_under"].mean()) if not recent.empty else np.nan
        avg_margin = float(margins.mean())
        if starts < 3:
            status = "LEARNING"
        elif below_rate >= (2.0 / 3.0) and avg_margin < -0.5:
            status = "UNDERPERFORMER"
        elif below_rate >= 0.55 and avg_margin < 0.0:
            status = "BELOW PROJECTION"
        else:
            status = "MIXED"
        rows.append({
            "Pitcher": str(ordered.get("player", pd.Series(["Unknown"])).iloc[-1]),
            "Resolved Starts": starts,
            "Below Projection Starts": below,
            "Below Projection Rate": below_rate,
            "Avg K vs Projection": avg_margin,
            "Median K vs Projection": float(margins.median()),
            "Avg Under Margin": float(under_margins.mean()) if not under_margins.empty else np.nan,
            "Total K Below Projection": float((-margins.clip(upper=0.0)).sum()),
            "2+ K Under Events": int((margins <= -2.0).sum()),
            "Recent 5 Below Rate": recent_rate,
            "Current Below Streak": _current_streak(ordered, "_under"),
            "Underperformer Status": status,
        })

    report = pd.DataFrame(rows, columns=columns)
    status_rank = {"UNDERPERFORMER": 0, "BELOW PROJECTION": 1, "LEARNING": 2, "MIXED": 3}
    report["_status_rank"] = report["Underperformer Status"].map(status_rank).fillna(9)
    report = report.sort_values(
        ["_status_rank", "Below Projection Starts", "Below Projection Rate", "Avg K vs Projection", "Resolved Starts"],
        ascending=[True, False, False, True, False],
    ).drop(columns=["_status_rank"]).reset_index(drop=True)
    return report

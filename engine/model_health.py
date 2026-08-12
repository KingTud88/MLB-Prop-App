from __future__ import annotations

import numpy as np
import pandas as pd

from engine.model_top_plays import MARKETS, build_model_board
from engine.starter_history import HISTORY_SEMANTICS

MIN_HEALTH_OBSERVATIONS = 30
RECENT_HEALTH_WINDOW = 20

ACTUAL_COLUMNS = {
    "Strikeouts": "actual_strikeouts",
    "Hits Allowed": "actual_hits_allowed",
    "Total Outs": "actual_outs",
}


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _current_rows(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty or "history_semantics" not in history.columns or "game_date" not in history.columns:
        return history.iloc[0:0].copy()
    frame = history.loc[history["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)].copy()
    frame["_game_date"] = pd.to_datetime(frame["game_date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["_game_date"])
    sort_cols = ["_game_date"]
    if "captured_at_utc" in frame.columns:
        sort_cols.append("captured_at_utc")
    return frame.sort_values(sort_cols).reset_index(drop=True)


def _snapshot_for_play(slate: pd.DataFrame, play: pd.Series) -> pd.Series | None:
    if slate.empty:
        return None
    game_pk = _num(play.get("Game PK"))
    pitcher_id = _num(play.get("Pitcher ID"))
    if game_pk is not None and pitcher_id is not None and {"game_pk", "pitcher_id"}.issubset(slate.columns):
        game_col = pd.to_numeric(slate["game_pk"], errors="coerce")
        pitcher_col = pd.to_numeric(slate["pitcher_id"], errors="coerce")
        match = slate.loc[game_col.eq(game_pk) & pitcher_col.eq(pitcher_id)]
        if not match.empty:
            return match.iloc[-1]
    if "player" in slate.columns:
        match = slate.loc[slate["player"].astype(str).eq(str(play.get("Pitcher", "")))]
        if not match.empty:
            return match.iloc[-1]
    return None


def grade_play(play: pd.Series | dict[str, object], snapshot: pd.Series | dict[str, object]) -> tuple[float | None, bool | None]:
    market = str(play.get("Market", ""))
    actual_col = ACTUAL_COLUMNS.get(market)
    if actual_col is None:
        return None, None
    actual = _num(snapshot.get(actual_col))
    line = _num(play.get("Line"))
    if actual is None or line is None:
        return actual, None
    side = str(play.get("Side", "")).upper()
    if side == "OVER":
        return actual, bool(actual > line)
    if side == "UNDER":
        return actual, bool(actual < line)
    return actual, None


def walk_forward_top5(history: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    """Replay each historical model Top 5 using only rows from earlier game dates.

    Same-day outcomes are never available to calibration. Each slate is built from
    its frozen pregame snapshot while SIM/MATH calibration can only see prior dates.
    Sportsbook data is not used anywhere in this replay.
    """
    current = _current_rows(history)
    if current.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for day in current["_game_date"].drop_duplicates().sort_values():
        slate = current.loc[current["_game_date"].eq(day)].drop(columns=["_game_date"], errors="ignore")
        training = current.loc[current["_game_date"].lt(day)].drop(columns=["_game_date"], errors="ignore")
        board = build_model_board(slate, training, limit=limit)
        if board.empty:
            continue
        resolved_training = 0
        for actual_col in ACTUAL_COLUMNS.values():
            if actual_col in training.columns:
                resolved_training = max(resolved_training, int(pd.to_numeric(training[actual_col], errors="coerce").notna().sum()))
        for _, play in board.iterrows():
            snapshot = _snapshot_for_play(slate, play)
            if snapshot is None:
                continue
            actual, hit = grade_play(play, snapshot)
            row = play.to_dict()
            row.update({
                "Walk Forward Date": pd.Timestamp(day).date().isoformat(),
                "Training Rows": int(len(training)),
                "Training Resolved": int(resolved_training),
                "Actual": actual,
                "Hit": hit,
            })
            rows.append(row)
    return pd.DataFrame(rows)


def health_from_walk_forward(
    walk_forward: pd.DataFrame,
    *,
    min_observations: int = MIN_HEALTH_OBSERVATIONS,
    recent_window: int = RECENT_HEALTH_WINDOW,
) -> pd.DataFrame:
    columns = [
        "Market", "Settled Top 5 Legs", "Status", "Eligible", "Hit Rate",
        "Avg Model Probability", "Calibration Gap", "Brier Score",
        "Recent Legs", "Recent Hit Rate", "Recent Avg Probability", "Recent Calibration Gap", "Reason",
    ]
    rows: list[dict[str, object]] = []
    for market in (*MARKETS, "ALL TOP 5"):
        if walk_forward.empty:
            data = pd.DataFrame()
        else:
            data = walk_forward.copy()
            if market != "ALL TOP 5":
                data = data.loc[data.get("Market", pd.Series(index=data.index, dtype=str)).astype(str).eq(market)]
            data = data.loc[data.get("Hit", pd.Series(index=data.index, dtype=object)).notna()].copy()
            if not data.empty:
                data["Model Probability"] = pd.to_numeric(data["Model Probability"], errors="coerce")
                data = data.dropna(subset=["Model Probability"])
        n = int(len(data))
        if n:
            y = data["Hit"].astype(float).to_numpy()
            p = np.clip(data["Model Probability"].to_numpy(float), 0.0, 1.0)
            hit_rate = float(y.mean())
            avg_p = float(p.mean())
            gap = float(abs(hit_rate - avg_p))
            brier = float(np.mean((p - y) ** 2))
            recent = data.tail(int(recent_window))
            recent_y = recent["Hit"].astype(float).to_numpy()
            recent_p = np.clip(pd.to_numeric(recent["Model Probability"], errors="coerce").to_numpy(float), 0.0, 1.0)
            recent_hit = float(recent_y.mean())
            recent_avg = float(recent_p.mean())
            recent_gap = float(abs(recent_hit - recent_avg))
        else:
            hit_rate = avg_p = gap = brier = None
            recent = pd.DataFrame()
            recent_hit = recent_avg = recent_gap = None

        if n < int(min_observations):
            status = "LEARNING"
            eligible = True
            reason = f"Need {int(min_observations)} settled walk-forward Top 5 legs; {n} available."
        elif gap is not None and brier is not None and recent_gap is not None and gap <= 0.08 and brier <= 0.24 and recent_gap <= 0.10:
            status = "HEALTHY"
            eligible = True
            reason = "Walk-forward probability calibration and Brier score are inside the healthy guardrails."
        elif gap is not None and brier is not None and recent_gap is not None and gap <= 0.12 and brier <= 0.27 and recent_gap <= 0.15:
            status = "WATCH"
            eligible = True
            reason = "Performance is usable but outside the tighter healthy guardrails."
        else:
            status = "BLOCKED"
            eligible = False
            reason = "Enough walk-forward evidence exists and probability performance is outside safety guardrails."

        rows.append({
            "Market": market,
            "Settled Top 5 Legs": n,
            "Status": status,
            "Eligible": eligible,
            "Hit Rate": hit_rate,
            "Avg Model Probability": avg_p,
            "Calibration Gap": gap,
            "Brier Score": brier,
            "Recent Legs": int(len(recent)),
            "Recent Hit Rate": recent_hit,
            "Recent Avg Probability": recent_avg,
            "Recent Calibration Gap": recent_gap,
            "Reason": reason,
        })
    return pd.DataFrame(rows, columns=columns)


def market_health_report(history: pd.DataFrame, *, min_observations: int = MIN_HEALTH_OBSERVATIONS) -> pd.DataFrame:
    return health_from_walk_forward(walk_forward_top5(history), min_observations=min_observations)


def market_health_map(report: pd.DataFrame) -> dict[str, str]:
    if report.empty:
        return {market: "LEARNING" for market in MARKETS}
    return {
        market: str(report.loc[report["Market"].eq(market), "Status"].iloc[0])
        if report["Market"].eq(market).any() else "LEARNING"
        for market in MARKETS
    }


def reliability_table(walk_forward: pd.DataFrame, market: str | None = None) -> pd.DataFrame:
    if walk_forward.empty:
        return pd.DataFrame(columns=["Probability Band", "Legs", "Avg Model Probability", "Observed Hit Rate", "Calibration Gap"])
    data = walk_forward.loc[walk_forward.get("Hit", pd.Series(index=walk_forward.index, dtype=object)).notna()].copy()
    if market and market != "ALL TOP 5":
        data = data.loc[data["Market"].astype(str).eq(str(market))]
    data["Model Probability"] = pd.to_numeric(data.get("Model Probability"), errors="coerce")
    data = data.dropna(subset=["Model Probability"])
    if data.empty:
        return pd.DataFrame(columns=["Probability Band", "Legs", "Avg Model Probability", "Observed Hit Rate", "Calibration Gap"])
    edges = [0.0, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90, 1.000001]
    labels = ["<50%", "50–54%", "55–59%", "60–64%", "65–69%", "70–74%", "75–79%", "80–89%", "90%+"]
    data["Probability Band"] = pd.cut(data["Model Probability"], bins=edges, labels=labels, right=False, include_lowest=True)
    rows = []
    for band, group in data.groupby("Probability Band", observed=True):
        p = float(group["Model Probability"].mean())
        hit = float(group["Hit"].astype(float).mean())
        rows.append({
            "Probability Band": str(band),
            "Legs": int(len(group)),
            "Avg Model Probability": p,
            "Observed Hit Rate": hit,
            "Calibration Gap": abs(p - hit),
        })
    return pd.DataFrame(rows)


def daily_top5_summary(walk_forward: pd.DataFrame) -> pd.DataFrame:
    if walk_forward.empty:
        return pd.DataFrame(columns=["Date", "Settled Legs", "Hits", "Hit Rate", "Avg Model Probability", "Brier Score", "5/5 Sweep"])
    data = walk_forward.loc[walk_forward.get("Hit", pd.Series(index=walk_forward.index, dtype=object)).notna()].copy()
    if data.empty:
        return pd.DataFrame(columns=["Date", "Settled Legs", "Hits", "Hit Rate", "Avg Model Probability", "Brier Score", "5/5 Sweep"])
    rows = []
    for day, group in data.groupby("Walk Forward Date", sort=True):
        y = group["Hit"].astype(float).to_numpy()
        p = np.clip(pd.to_numeric(group["Model Probability"], errors="coerce").to_numpy(float), 0.0, 1.0)
        n = int(len(group))
        hits = int(y.sum())
        rows.append({
            "Date": str(day),
            "Settled Legs": n,
            "Hits": hits,
            "Hit Rate": float(y.mean()),
            "Avg Model Probability": float(p.mean()),
            "Brier Score": float(np.mean((p - y) ** 2)),
            "5/5 Sweep": bool(n == 5 and hits == 5),
        })
    return pd.DataFrame(rows)

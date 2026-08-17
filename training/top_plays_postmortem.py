from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from engine.decision_learning import probability_band, quality_band
from engine.model_health import grade_play, health_from_walk_forward, market_health_map, walk_forward_top5
from engine.model_top_plays import (
    MARKET_HITS,
    MARKET_LINE_COLUMNS,
    MARKET_LINE_SOURCE_COLUMNS,
    MARKET_OUTS,
    MARKET_STRIKEOUTS,
    MARKETS,
    build_model_board,
)
from engine.starter_history import HISTORY_SEMANTICS

POSTMORTEM_VERSION = "top-plays-postmortem-v1"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
FORBIDDEN_LINE_SOURCE_MARKERS = ("MODEL GRID", "DIAGNOSTIC", "DEFAULT", "PLACEHOLDER", "SYNTHETIC")
MANUAL_COLUMNS = {
    MARKET_STRIKEOUTS: "manual_strikeout_line",
    MARKET_OUTS: "manual_outs_line",
    MARKET_HITS: "manual_hits_allowed_line",
}
ACTUAL_COLUMNS = {
    MARKET_STRIKEOUTS: "actual_strikeouts",
    MARKET_OUTS: "actual_outs",
    MARKET_HITS: "actual_hits_allowed",
}


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _missing_scalar(value: object) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _key(value: object) -> str:
    if _missing_scalar(value):
        return ""
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def _safe_line_source(value: object) -> str:
    if _missing_scalar(value):
        return ""
    source = str(value).strip()
    upper = source.upper()
    if not source or any(marker in upper for marker in FORBIDDEN_LINE_SOURCE_MARKERS):
        return ""
    return source


def overlay_persisted_active_lines(history: pd.DataFrame, archive: pd.DataFrame) -> pd.DataFrame:
    """Overlay only explicitly persisted real execution lines onto frozen history.

    Manual lines are authoritative when present. Otherwise an archived active line
    is accepted only when it has a nonblank source that is not a model-grid,
    diagnostic, default, placeholder, or synthetic source. This deliberately
    leaves older unobserved markets blank instead of reconstructing them.
    """
    result = history.copy()
    for market in MARKETS:
        result[MARKET_LINE_COLUMNS[market]] = pd.NA
        result[MARKET_LINE_SOURCE_COLUMNS[market]] = ""
    if result.empty or archive is None or archive.empty:
        return result
    if not {"game_pk", "pitcher_id"}.issubset(result.columns) or not {"game_pk", "pitcher_id"}.issubset(archive.columns):
        return result

    saved = archive.copy()
    saved["_game"] = saved["game_pk"].map(_key)
    saved["_pitcher"] = saved["pitcher_id"].map(_key)
    sort_cols = [col for col in ("archive_committed_at_utc", "captured_at_utc") if col in saved.columns]
    if sort_cols:
        saved = saved.sort_values(sort_cols, kind="stable")
    lookup = saved.drop_duplicates(["_game", "_pitcher"], keep="last").set_index(["_game", "_pitcher"])

    for idx, row in result.iterrows():
        key = (_key(row.get("game_pk")), _key(row.get("pitcher_id")))
        if key not in lookup.index:
            continue
        archived = lookup.loc[key]
        if isinstance(archived, pd.DataFrame):
            archived = archived.iloc[-1]
        for market in MARKETS:
            line_col = MARKET_LINE_COLUMNS[market]
            source_col = MARKET_LINE_SOURCE_COLUMNS[market]
            manual = _num(archived.get(MANUAL_COLUMNS[market]))
            if manual is not None:
                result.at[idx, line_col] = manual
                result.at[idx, source_col] = "MANUAL"
                continue
            active = _num(archived.get(line_col))
            source = _safe_line_source(archived.get(source_col))
            if active is not None and source:
                result.at[idx, line_col] = active
                result.at[idx, source_col] = source
    return result


def _current_history(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty or "game_date" not in history.columns:
        return pd.DataFrame()
    frame = history.copy()
    if "history_semantics" in frame.columns:
        frame = frame.loc[frame["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)].copy()
    frame["_date"] = pd.to_datetime(frame["game_date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["_date"])
    sort_cols = ["_date"] + (["captured_at_utc"] if "captured_at_utc" in frame.columns else [])
    return frame.sort_values(sort_cols, kind="stable").reset_index(drop=True)


def _snapshot_for_play(slate: pd.DataFrame, play: pd.Series) -> pd.Series | None:
    game = _num(play.get("Game PK"))
    pitcher = _num(play.get("Pitcher ID"))
    if game is not None and pitcher is not None and {"game_pk", "pitcher_id"}.issubset(slate.columns):
        games = pd.to_numeric(slate["game_pk"], errors="coerce")
        pitchers = pd.to_numeric(slate["pitcher_id"], errors="coerce")
        match = slate.loc[games.eq(game) & pitchers.eq(pitcher)]
        if not match.empty:
            return match.iloc[-1]
    player = str(play.get("Pitcher", ""))
    if player and "player" in slate.columns:
        match = slate.loc[slate["player"].astype(str).eq(player)]
        if not match.empty:
            return match.iloc[-1]
    return None


def _lineup_state(snapshot: pd.Series) -> str:
    confirmed = snapshot.get("lineup_confirmed")
    if isinstance(confirmed, (bool, np.bool_)):
        return "CONFIRMED" if bool(confirmed) else "PROJECTED"
    if not _missing_scalar(confirmed):
        text = str(confirmed).strip().lower()
        if text in {"true", "1", "yes"}:
            return "CONFIRMED"
        if text in {"false", "0", "no"}:
            return "PROJECTED"
    source_value = snapshot.get("lineup_source", "")
    source = "" if _missing_scalar(source_value) else str(source_value).strip().upper()
    return source or "UNKNOWN"


def _weather_state(snapshot: pd.Series) -> str:
    value = snapshot.get("weather_delay_risk", "")
    if _missing_scalar(value):
        return "UNKNOWN"
    text = str(value).strip().upper()
    return text or "UNKNOWN"


def _outcome_margin(side: str, actual: float | None, line: float | None) -> float | None:
    if actual is None or line is None:
        return None
    if str(side).upper() == "OVER":
        return float(actual - line)
    if str(side).upper() == "UNDER":
        return float(line - actual)
    return None


def replay_real_line_top5(history: pd.DataFrame, archive: pd.DataFrame, *, limit: int = 5) -> pd.DataFrame:
    """Replay historical Top Plays only where a real active line was persisted.

    Calibration and market-health evidence are rebuilt from strictly earlier game
    dates. The market line itself comes only from durable pregame archive fields.
    Sportsbook odds/prices and realized results never affect ranking.
    """
    current = _current_history(history)
    if current.empty:
        return pd.DataFrame()
    overlaid = overlay_persisted_active_lines(current.drop(columns=["_date"], errors="ignore"), archive)
    overlaid["_date"] = current["_date"].to_numpy()

    rows: list[dict[str, object]] = []
    for day in overlaid["_date"].drop_duplicates().sort_values():
        slate = overlaid.loc[overlaid["_date"].eq(day)].drop(columns=["_date"], errors="ignore")
        training = current.loc[current["_date"].lt(day)].drop(columns=["_date"], errors="ignore")
        historical_health = market_health_map(health_from_walk_forward(walk_forward_top5(training)))
        board = build_model_board(
            slate,
            training,
            limit=limit,
            market_health=historical_health,
            require_market_lines=True,
        )
        if board.empty:
            continue
        for _, play in board.iterrows():
            snapshot = _snapshot_for_play(slate, play)
            if snapshot is None:
                continue
            actual, hit = grade_play(play, snapshot)
            line = _num(play.get("Line"))
            projection = _num(play.get("Projection"))
            probability = _num(play.get("Model Probability"))
            quality = _num(play.get("Data Quality"))
            row = play.to_dict()
            row.update(
                {
                    "Postmortem Date": pd.Timestamp(day).date().isoformat(),
                    "Actual": actual,
                    "Hit": hit,
                    "Resolved": hit is not None,
                    "Projection Margin": None if projection is None or line is None else abs(projection - line),
                    "Outcome Margin": _outcome_margin(str(play.get("Side", "")), actual, line),
                    "Probability Band": probability_band(probability),
                    "Quality Band": quality_band(quality),
                    "Lineup State": _lineup_state(snapshot),
                    "Lineup Source": str(snapshot.get("lineup_source", "") or "").strip() or "UNKNOWN",
                    "Weather Risk": _weather_state(snapshot),
                    "Training Rows": int(len(training)),
                    "Historical Market Health": str(historical_health.get(str(play.get("Market", "")), "LEARNING")),
                    "Report Only": REPORT_ONLY,
                    "Production Authority": PRODUCTION_AUTHORITY,
                    "Postmortem Version": POSTMORTEM_VERSION,
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def line_coverage_report(history: pd.DataFrame, archive: pd.DataFrame) -> pd.DataFrame:
    current = _current_history(history)
    if current.empty:
        return pd.DataFrame()
    overlaid = overlay_persisted_active_lines(current.drop(columns=["_date"], errors="ignore"), archive)
    overlaid["_date"] = current["_date"].to_numpy()
    rows: list[dict[str, object]] = []
    for day, group in overlaid.groupby("_date", sort=True):
        counts = {}
        any_line = pd.Series(False, index=group.index)
        for market in MARKETS:
            observed = pd.to_numeric(group[MARKET_LINE_COLUMNS[market]], errors="coerce").notna()
            sourced = group[MARKET_LINE_SOURCE_COLUMNS[market]].astype(str).str.strip().ne("")
            valid = observed & sourced
            counts[market] = int(valid.sum())
            any_line = any_line | valid
        resolved = pd.Series(False, index=group.index)
        for col in ACTUAL_COLUMNS.values():
            if col in group.columns:
                resolved = resolved | pd.to_numeric(group[col], errors="coerce").notna()
        rows.append(
            {
                "Date": pd.Timestamp(day).date().isoformat(),
                "Frozen Pitcher Rows": int(len(group)),
                "Rows With Any Persisted Real Line": int(any_line.sum()),
                "Strikeout Lines": counts[MARKET_STRIKEOUTS],
                "Outs Lines": counts[MARKET_OUTS],
                "Hits Lines": counts[MARKET_HITS],
                "Resolved Pitcher Rows": int(resolved.sum()),
                "Postmortem Version": POSTMORTEM_VERSION,
            }
        )
    return pd.DataFrame(rows)


def _segment_summary(data: pd.DataFrame, dimension: str, segment: str) -> dict[str, object]:
    settled = data.loc[data.get("Hit", pd.Series(index=data.index, dtype=object)).notna()].copy()
    n = int(len(settled))
    if n:
        y = settled["Hit"].astype(float).to_numpy()
        p = pd.to_numeric(settled["Model Probability"], errors="coerce").to_numpy(float)
        p = np.clip(p, 0.0, 1.0)
        hit_rate = float(y.mean())
        avg_p = float(p.mean())
        gap = abs(hit_rate - avg_p)
        brier = float(np.mean((p - y) ** 2))
        hits = int(y.sum())
        proj_margin = pd.to_numeric(settled.get("Projection Margin"), errors="coerce").mean()
        outcome_margin = pd.to_numeric(settled.get("Outcome Margin"), errors="coerce").mean()
    else:
        hits = 0
        hit_rate = avg_p = gap = brier = proj_margin = outcome_margin = float("nan")
    return {
        "Dimension": dimension,
        "Segment": segment,
        "Settled Legs": n,
        "Hits": hits,
        "Hit Rate": hit_rate,
        "Avg Model Probability": avg_p,
        "Calibration Gap": gap,
        "Brier Score": brier,
        "Avg Projection Margin": proj_margin,
        "Avg Outcome Margin": outcome_margin,
        "Report Only": REPORT_ONLY,
        "Production Authority": PRODUCTION_AUTHORITY,
        "Postmortem Version": POSTMORTEM_VERSION,
    }


def build_segment_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty:
        return pd.DataFrame()
    rows = [_segment_summary(detail, "OVERALL", "ALL REAL-LINE TOP PLAYS")]
    specs = (
        ("RANK", "Rank"),
        ("MARKET", "Market"),
        ("SIDE", "Side"),
        ("STATUS", "Status"),
        ("PROBABILITY BAND", "Probability Band"),
        ("QUALITY BAND", "Quality Band"),
        ("LINE SOURCE", "Line Source"),
        ("LINEUP STATE", "Lineup State"),
        ("WEATHER RISK", "Weather Risk"),
        ("MARKET HEALTH", "Historical Market Health"),
    )
    for dimension, column in specs:
        if column not in detail.columns:
            continue
        values = detail[column].fillna("UNKNOWN").astype(str)
        for segment in sorted(values.unique()):
            rows.append(_segment_summary(detail.loc[values.eq(segment)], dimension, segment))
    out = pd.DataFrame(rows)
    overall = out.loc[out["Dimension"].eq("OVERALL"), "Hit Rate"]
    overall_rate = float(overall.iloc[0]) if not overall.empty and pd.notna(overall.iloc[0]) else float("nan")
    out["Lift vs Overall"] = pd.to_numeric(out["Hit Rate"], errors="coerce") - overall_rate
    return out


def build_daily_combo_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for day, group in detail.groupby("Postmortem Date", sort=True):
        settled = group.loc[group.get("Hit", pd.Series(index=group.index, dtype=object)).notna()].copy()
        settled["Rank"] = pd.to_numeric(settled.get("Rank"), errors="coerce")
        settled = settled.dropna(subset=["Rank"]).sort_values("Rank")
        ranks = {int(row["Rank"]): bool(row["Hit"]) for _, row in settled.iterrows()}

        def combo(n: int) -> object:
            needed = set(range(1, n + 1))
            if not needed.issubset(ranks):
                return pd.NA
            return bool(all(ranks[r] for r in needed))

        rows.append(
            {
                "Date": str(day),
                "Settled Legs": int(len(settled)),
                "Hits": int(settled["Hit"].astype(bool).sum()) if not settled.empty else 0,
                "Hit Rate": float(settled["Hit"].astype(float).mean()) if not settled.empty else float("nan"),
                "Top 2 All Hit": combo(2),
                "Top 3 All Hit": combo(3),
                "Top 5 All Hit": combo(5),
                "Report Only": REPORT_ONLY,
                "Production Authority": PRODUCTION_AUTHORITY,
                "Postmortem Version": POSTMORTEM_VERSION,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-line chronological Top Plays postmortem.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--archive", type=Path, default=Path("data/projection_archive.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/top_plays_postmortem_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/top_plays_postmortem_summary.csv"))
    parser.add_argument("--daily", type=Path, default=Path("data/top_plays_postmortem_daily.csv"))
    parser.add_argument("--coverage", type=Path, default=Path("data/top_plays_postmortem_coverage.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    archive = pd.read_csv(args.archive) if args.archive.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("Projection log is missing or empty")

    detail = replay_real_line_top5(history, archive)
    summary = build_segment_summary(detail)
    daily = build_daily_combo_summary(detail)
    coverage = line_coverage_report(history, archive)
    for path, frame in ((args.detail, detail), (args.summary, summary), (args.daily, daily), (args.coverage, coverage)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    observed_days = int(coverage.loc[coverage["Rows With Any Persisted Real Line"].gt(0), "Date"].nunique()) if not coverage.empty else 0
    settled = int(detail.get("Hit", pd.Series(dtype=object)).notna().sum()) if not detail.empty else 0
    print(f"real_line_days={observed_days} postmortem_rows={len(detail)} settled_legs={settled}")
    if not summary.empty:
        print(summary.head(20).to_string(index=False))
    print(f"version={POSTMORTEM_VERSION} production_authority={PRODUCTION_AUTHORITY} report_only={REPORT_ONLY}")


if __name__ == "__main__":
    main()

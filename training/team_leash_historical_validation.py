from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests

from engine.team_leash import (
    MAX_LEAGUE_STARTS,
    MAX_TEAM_STARTS,
    MIN_TEAM_STARTS,
    MIN_VALIDATION_STARTS,
    TEAM_LEASH_ROLE,
    TEAM_LEASH_VERSION,
    _candidate_multiplier,
    _weighted,
)
from engine.workload_context import WORKLOAD_VERSION, build_workload_context
from training.workload_backtest import MLB_API, MIN_PRIOR_STARTS, _numeric, _parse_outs, tracked_pitcher_ids

VALIDATION_VERSION = "team-leash-historical-v1"
PRODUCTION_AUTHORITY = "NONE"
REPORT_ONLY = True
REQUIRED_SEASONS = (2024, 2025, 2026)
FETCH_SEASONS = (2023, 2024, 2025, 2026)
METRICS = ("PITCHES", "BF", "OUTS")
PROMOTE_MIN_RELATIVE_MAE = 0.005
PROMOTE_MIN_WIN_SHARE = 0.55


def fetch_pitcher_starts_with_team(
    pitcher_id: int,
    seasons: Iterable[int] = FETCH_SEASONS,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Fetch regular-season starter workloads while preserving the pitcher's team.

    This is baseball-only research plumbing. It uses MLB game logs and never
    consumes sportsbook prices, saved bets, recommendations, or Odds API credits.
    """
    client = session or requests.Session()
    rows: list[dict[str, object]] = []
    for season in seasons:
        response = client.get(
            f"{MLB_API}/people/{int(pitcher_id)}/stats",
            params={"stats": "gameLog", "group": "pitching", "season": int(season), "gameType": "R"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        for block in payload.get("stats", []) or []:
            for split in block.get("splits", []) or []:
                stat = split.get("stat", {}) or {}
                if int(float(stat.get("gamesStarted", 0) or 0)) <= 0:
                    continue
                team = split.get("team", {}) or {}
                team_id = pd.to_numeric(pd.Series([team.get("id")]), errors="coerce").iloc[0]
                team_key = str(int(team_id)) if pd.notna(team_id) else str(team.get("abbreviation") or team.get("name") or "").strip().upper()
                rows.append(
                    {
                        "pitcher_id": int(pitcher_id),
                        "game_pk": pd.to_numeric(pd.Series([split.get("gamePk")]), errors="coerce").iloc[0],
                        "date": pd.to_datetime(split.get("date"), errors="coerce"),
                        "season": int(season),
                        "team": team_key,
                        "pitches": _numeric(stat.get("numberOfPitches")),
                        "bf": _numeric(stat.get("battersFaced")),
                        "outs": _parse_outs(stat.get("inningsPitched", "")),
                    }
                )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.dropna(subset=["date"])
    frame = frame.loc[frame["team"].astype(str).str.len().gt(0)].copy()
    frame = frame.sort_values(["date", "game_pk"], kind="stable")
    # game_pk is preferred for doubleheader safety; fall back to pitcher/date.
    with_pk = frame.loc[pd.to_numeric(frame.get("game_pk"), errors="coerce").notna()].drop_duplicates(
        ["pitcher_id", "game_pk"], keep="last"
    )
    without_pk = frame.loc[pd.to_numeric(frame.get("game_pk"), errors="coerce").isna()].drop_duplicates(
        ["pitcher_id", "date"], keep="last"
    )
    return pd.concat([with_pk, without_pk], ignore_index=True).sort_values(["date", "game_pk"], kind="stable").reset_index(drop=True)


def fetch_historical_start_pool(
    projection_log: pd.DataFrame,
    seasons: Iterable[int] = FETCH_SEASONS,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    ids = tracked_pitcher_ids(projection_log)
    if not ids:
        return pd.DataFrame()
    client = session or requests.Session()
    pieces: list[pd.DataFrame] = []
    for pitcher_id in ids:
        try:
            piece = fetch_pitcher_starts_with_team(int(pitcher_id), seasons, client)
        except requests.RequestException:
            continue
        if not piece.empty:
            pieces.append(piece)
    if not pieces:
        return pd.DataFrame()
    return pd.concat(pieces, ignore_index=True).sort_values(["date", "game_pk"], kind="stable").reset_index(drop=True)


def _team_candidate_context(prior_season: pd.DataFrame, team: str) -> dict[str, object]:
    league_rows = prior_season.tail(MAX_LEAGUE_STARTS).copy()
    team_rows = prior_season.loc[prior_season["team"].astype(str).eq(str(team))].tail(MAX_TEAM_STARTS).copy()
    starts = int(len(team_rows))
    if league_rows.empty:
        league_pitch, league_bf, league_outs = 88.0, 22.0, 16.0
    else:
        league_pitch = float(pd.to_numeric(league_rows["pitches"], errors="coerce").mean())
        league_bf = float(pd.to_numeric(league_rows["bf"], errors="coerce").mean())
        league_outs = float(pd.to_numeric(league_rows["outs"], errors="coerce").mean())
        if not np.isfinite(league_pitch):
            league_pitch = 88.0
        if not np.isfinite(league_bf):
            league_bf = 22.0
        if not np.isfinite(league_outs):
            league_outs = 16.0

    team_pitch = _weighted(team_rows.get("pitches", pd.Series(dtype=float)), 12.0, league_pitch)
    team_bf = _weighted(team_rows.get("bf", pd.Series(dtype=float)), 12.0, league_bf)
    team_outs = _weighted(team_rows.get("outs", pd.Series(dtype=float)), 12.0, league_outs)
    pitch_mult = _candidate_multiplier(team_pitch, league_pitch, starts)
    bf_mult = _candidate_multiplier(team_bf, league_bf, starts)
    outs_mult = _candidate_multiplier(team_outs, league_outs, starts)
    status = "TRACKING" if starts >= MIN_TEAM_STARTS else "LEARNING"
    if status == "LEARNING":
        label = "LEARNING"
    elif pitch_mult <= 0.992 and outs_mult <= 0.992:
        label = "TIGHTER"
    elif pitch_mult >= 1.008 and outs_mult >= 1.008:
        label = "LONGER"
    else:
        label = "NEUTRAL"
    return {
        "team_starts": starts,
        "league_starts": int(len(league_rows)),
        "pitch_multiplier": float(pitch_mult),
        "bf_multiplier": float(bf_mult),
        "outs_multiplier": float(outs_mult),
        "label": label,
        "status": status,
    }


def replay_team_leash(start_pool: pd.DataFrame, target_season: int) -> pd.DataFrame:
    """Chronologically replay workload-v1 plus the existing team-leash candidate."""
    if start_pool is None or start_pool.empty:
        return pd.DataFrame()
    data = start_pool.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for col in ("pitches", "bf", "outs"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=["date", "pitches", "bf", "outs"])
    data = data.sort_values(["date", "game_pk"], kind="stable").reset_index(drop=True)
    targets = data.loc[data["season"].eq(int(target_season))].copy()
    rows: list[dict[str, object]] = []

    for _, target in targets.iterrows():
        target_date = pd.Timestamp(target["date"])
        pitcher_prior = data.loc[
            data["pitcher_id"].eq(int(target["pitcher_id"])) & data["date"].lt(target_date),
            ["date", "pitches", "bf", "outs"],
        ].copy()
        if len(pitcher_prior) < MIN_PRIOR_STARTS:
            continue
        season_prior = data.loc[
            data["season"].eq(int(target_season)) & data["date"].lt(target_date)
        ].copy()
        team_ctx = _team_candidate_context(season_prior, str(target["team"]))
        if team_ctx["status"] != "TRACKING":
            continue

        workload = build_workload_context(pitcher_prior, target_date)
        row: dict[str, object] = {
            "Season": int(target_season),
            "Game_Date": target_date.date().isoformat(),
            "Pitcher_ID": int(target["pitcher_id"]),
            "Team": str(target["team"]),
            "Team_Starts": int(team_ctx["team_starts"]),
            "League_Starts": int(team_ctx["league_starts"]),
            "Team_Leash_Label": str(team_ctx["label"]),
            "Team_Leash_Version": TEAM_LEASH_VERSION,
            "Team_Leash_Role": TEAM_LEASH_ROLE,
            "Workload_Version": WORKLOAD_VERSION,
            "Validation_Version": VALIDATION_VERSION,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Report_Only": REPORT_ONLY,
        }
        for metric, baseline, mult in (
            ("PITCHES", workload.expected_pitches, team_ctx["pitch_multiplier"]),
            ("BF", workload.expected_bf, team_ctx["bf_multiplier"]),
            ("OUTS", workload.expected_outs, team_ctx["outs_multiplier"]),
        ):
            actual_key = {"PITCHES": "pitches", "BF": "bf", "OUTS": "outs"}[metric]
            actual = float(target[actual_key])
            candidate = float(baseline) * float(mult)
            row[f"Actual_{metric}"] = actual
            row[f"Baseline_{metric}"] = float(baseline)
            row[f"Candidate_{metric}"] = candidate
            row[f"Multiplier_{metric}"] = float(mult)
        rows.append(row)
    return pd.DataFrame(rows)


def _summary_row(group: pd.DataFrame, *, season: int | str, metric: str, label: str) -> dict[str, object]:
    actual = pd.to_numeric(group.get(f"Actual_{metric}"), errors="coerce")
    baseline = pd.to_numeric(group.get(f"Baseline_{metric}"), errors="coerce")
    candidate = pd.to_numeric(group.get(f"Candidate_{metric}"), errors="coerce")
    ready = actual.notna() & baseline.notna() & candidate.notna()
    actual = actual[ready].astype(float)
    baseline = baseline[ready].astype(float)
    candidate = candidate[ready].astype(float)
    n = int(len(actual))
    if n:
        base_err = baseline - actual
        cand_err = candidate - actual
        base_abs = base_err.abs()
        cand_abs = cand_err.abs()
        base_mae = float(base_abs.mean())
        cand_mae = float(cand_abs.mean())
        relative = float((base_mae - cand_mae) / base_mae) if base_mae > 0 else float("nan")
        improved_share = float((cand_abs < base_abs).mean())
        base_bias = float(base_err.mean())
        cand_bias = float(cand_err.mean())
    else:
        base_mae = cand_mae = relative = improved_share = base_bias = cand_bias = float("nan")

    is_overall = label == "ALL"
    sample_gate = n >= MIN_VALIDATION_STARTS
    mae_gate = bool(np.isfinite(relative) and relative >= PROMOTE_MIN_RELATIVE_MAE)
    win_gate = bool(np.isfinite(improved_share) and improved_share >= PROMOTE_MIN_WIN_SHARE)
    bias_gate = bool(np.isfinite(base_bias) and np.isfinite(cand_bias) and abs(cand_bias) <= abs(base_bias) + 1e-12)
    reasons: list[str] = []
    if not sample_gate:
        reasons.append("sample")
    if not mae_gate:
        reasons.append("mae")
    if not win_gate:
        reasons.append("win_share")
    if not bias_gate:
        reasons.append("bias")
    gate = "PASS" if is_overall and not reasons else "FAIL" if is_overall else "CONTEXT_ONLY"

    return {
        "Season": season,
        "Metric": metric,
        "Leash_Label": label,
        "Evaluated_Starts": n,
        "Baseline_MAE": base_mae,
        "Candidate_MAE": cand_mae,
        "Relative_MAE_Improvement": relative,
        "Candidate_Win_Share": improved_share,
        "Baseline_Bias": base_bias,
        "Candidate_Bias": cand_bias,
        "Sample_Gate": sample_gate,
        "MAE_Gate": mae_gate,
        "Win_Gate": win_gate,
        "Bias_Gate": bias_gate,
        "Promotion_Cell": gate,
        "Reasons": "|".join(reasons),
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Report_Only": REPORT_ONLY,
        "Validation_Version": VALIDATION_VERSION,
    }


def build_summary(detail: pd.DataFrame, seasons: tuple[int, ...] = REQUIRED_SEASONS) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for season in seasons:
        season_rows = detail.loc[pd.to_numeric(detail.get("Season"), errors="coerce").eq(int(season))].copy()
        for metric in METRICS:
            rows.append(_summary_row(season_rows, season=int(season), metric=metric, label="ALL"))
            for label in ("TIGHTER", "NEUTRAL", "LONGER"):
                rows.append(
                    _summary_row(
                        season_rows.loc[season_rows.get("Team_Leash_Label", pd.Series(index=season_rows.index, dtype=str)).astype(str).eq(label)],
                        season=int(season),
                        metric=metric,
                        label=label,
                    )
                )
    for metric in METRICS:
        rows.append(_summary_row(detail, season="POOLED", metric=metric, label="ALL"))
        for label in ("TIGHTER", "NEUTRAL", "LONGER"):
            rows.append(
                _summary_row(
                    detail.loc[detail.get("Team_Leash_Label", pd.Series(index=detail.index, dtype=str)).astype(str).eq(label)],
                    season="POOLED",
                    metric=metric,
                    label=label,
                )
            )
    return pd.DataFrame(rows)


def build_decisions(summary: pd.DataFrame, seasons: tuple[int, ...] = REQUIRED_SEASONS) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for metric in METRICS:
        cells = summary.loc[
            summary["Metric"].astype(str).eq(metric)
            & summary["Leash_Label"].astype(str).eq("ALL")
            & pd.to_numeric(summary["Season"], errors="coerce").isin(seasons)
        ].copy()
        passed = int(cells["Promotion_Cell"].astype(str).eq("PASS").sum())
        all_pass = len(cells) == len(seasons) and passed == len(seasons)
        pooled = summary.loc[
            summary["Metric"].astype(str).eq(metric)
            & summary["Leash_Label"].astype(str).eq("ALL")
            & summary["Season"].astype(str).eq("POOLED")
        ]
        pooled_row = pooled.iloc[0] if not pooled.empty else pd.Series(dtype=object)
        failures: list[str] = []
        for _, cell in cells.sort_values("Season").iterrows():
            if str(cell.get("Promotion_Cell")) != "PASS":
                failures.append(f"{cell['Season']}:{cell.get('Reasons') or 'gate'}")
        decision = "EARNED_REVIEW" if all_pass else "HOLD"
        rows.append(
            {
                "Metric": metric,
                "Decision": decision,
                "Passing_Seasons": passed,
                "Required_Seasons": len(seasons),
                "Pooled_Evaluated_Starts": int(pd.to_numeric(pd.Series([pooled_row.get("Evaluated_Starts")]), errors="coerce").fillna(0).iloc[0]),
                "Pooled_Baseline_MAE": pd.to_numeric(pd.Series([pooled_row.get("Baseline_MAE")]), errors="coerce").iloc[0],
                "Pooled_Candidate_MAE": pd.to_numeric(pd.Series([pooled_row.get("Candidate_MAE")]), errors="coerce").iloc[0],
                "Pooled_Relative_MAE_Improvement": pd.to_numeric(pd.Series([pooled_row.get("Relative_MAE_Improvement")]), errors="coerce").iloc[0],
                "Pooled_Candidate_Win_Share": pd.to_numeric(pd.Series([pooled_row.get("Candidate_Win_Share")]), errors="coerce").iloc[0],
                "Reasons": ";".join(failures),
                "Production_Authority": PRODUCTION_AUTHORITY,
                "Report_Only": REPORT_ONLY,
                "Validation_Version": VALIDATION_VERSION,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Historical chronological validation of team-level starter leash context.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/team_leash_historical_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/team_leash_historical_summary.csv"))
    parser.add_argument("--decisions", type=Path, default=Path("data/team_leash_historical_decisions.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("Projection log is missing or empty")
    start_pool = fetch_historical_start_pool(history)
    if start_pool.empty:
        raise SystemExit("No historical starter workload pool could be fetched")
    detail = pd.concat(
        [replay_team_leash(start_pool, season) for season in REQUIRED_SEASONS],
        ignore_index=True,
    )
    summary = build_summary(detail)
    decisions = build_decisions(summary)
    for path in (args.detail, args.summary, args.decisions):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    decisions.to_csv(args.decisions, index=False)
    print(decisions.to_string(index=False))
    print(f"validation={VALIDATION_VERSION} role={TEAM_LEASH_ROLE} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()

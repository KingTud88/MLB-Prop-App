from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS

TEAM_LEASH_VERSION = "team-leash-v1"
TEAM_LEASH_ROLE = "CONTEXT_ONLY"
MIN_TEAM_STARTS = 12
TEAM_PRIOR_STARTS = 20.0
MAX_TEAM_STARTS = 60
MAX_LEAGUE_STARTS = 300
MIN_VALIDATION_STARTS = 20


@dataclass(frozen=True)
class TeamLeashContext:
    version: str
    role: str
    team: str
    starts_used: int
    league_starts: int
    team_avg_pitches: float
    team_avg_bf: float
    team_avg_outs: float
    league_avg_pitches: float
    league_avg_bf: float
    league_avg_outs: float
    quick_hook_rate: float
    tto_reach_rate: float
    pitch_90_rate: float
    pitch_multiplier_candidate: float
    bf_multiplier_candidate: float
    outs_multiplier_candidate: float
    label: str
    status: str

    def snapshot_fields(self) -> dict[str, object]:
        return {
            "team_leash_version": self.version,
            "team_leash_role": self.role,
            "team_leash_team": self.team,
            "team_leash_starts": self.starts_used,
            "team_leash_league_starts": self.league_starts,
            "team_leash_avg_pitches": self.team_avg_pitches,
            "team_leash_avg_bf": self.team_avg_bf,
            "team_leash_avg_outs": self.team_avg_outs,
            "team_leash_league_avg_pitches": self.league_avg_pitches,
            "team_leash_league_avg_bf": self.league_avg_bf,
            "team_leash_league_avg_outs": self.league_avg_outs,
            "team_leash_quick_hook_rate": self.quick_hook_rate,
            "team_leash_tto_reach_rate": self.tto_reach_rate,
            "team_leash_90_pitch_rate": self.pitch_90_rate,
            "team_leash_pitch_multiplier_candidate": self.pitch_multiplier_candidate,
            "team_leash_bf_multiplier_candidate": self.bf_multiplier_candidate,
            "team_leash_outs_multiplier_candidate": self.outs_multiplier_candidate,
            "team_leash_label": self.label,
            "team_leash_status": self.status,
        }


def _weighted(values: pd.Series, half_life: float, fallback: float) -> float:
    x = pd.to_numeric(values, errors="coerce").dropna().to_numpy(float)
    if not len(x):
        return float(fallback)
    ages = np.arange(len(x) - 1, -1, -1)
    weights = 0.5 ** (ages / float(half_life))
    return float(np.average(x, weights=weights))


def _resolved_rows(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    columns = ["game_pk", "pitcher_id", "game_date", "team", "actual_pitches", "actual_batters_faced", "actual_outs", "source"]
    if frame is None or frame.empty:
        return pd.DataFrame(columns=columns)
    data = frame.copy()
    if "history_semantics" in data.columns:
        data = data.loc[data["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)].copy()
    for col in ("game_pk", "pitcher_id", "game_date", "team", "actual_pitches", "actual_batters_faced", "actual_outs"):
        if col not in data.columns:
            data[col] = np.nan if col.startswith("actual_") or col in {"game_pk", "pitcher_id"} else ""
    data["_date"] = pd.to_datetime(data["game_date"], errors="coerce", utc=True)
    for col in ("actual_pitches", "actual_batters_faced", "actual_outs"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=["_date", "actual_pitches", "actual_batters_faced", "actual_outs"])
    data = data.loc[data["team"].astype(str).str.len().gt(0)].copy()
    data["source"] = source
    return data[["game_pk", "pitcher_id", "game_date", "team", "actual_pitches", "actual_batters_faced", "actual_outs", "source", "_date"]]


def resolved_starter_workloads(projections: pd.DataFrame, observations: pd.DataFrame | None = None) -> pd.DataFrame:
    """Combine resolved projected and history-only starter workloads.

    The function reads baseball outcome fields only. Sportsbook prices, bets, and
    recommendation fields are deliberately irrelevant to this context layer.
    """
    projected = _resolved_rows(projections, "PROJECTION")
    observed = _resolved_rows(observations if observations is not None else pd.DataFrame(), "OBSERVATION")
    if projected.empty:
        combined = observed.copy()
    elif observed.empty:
        combined = projected.copy()
    else:
        combined = pd.concat([projected, observed], ignore_index=True)
    if combined.empty:
        return combined
    combined["game_pk"] = pd.to_numeric(combined["game_pk"], errors="coerce")
    combined["pitcher_id"] = pd.to_numeric(combined["pitcher_id"], errors="coerce")
    combined = combined.sort_values(["_date", "source"], kind="stable")
    dedupe = combined["game_pk"].notna() & combined["pitcher_id"].notna()
    if dedupe.any():
        with_keys = combined.loc[dedupe].drop_duplicates(["game_pk", "pitcher_id"], keep="first")
        without_keys = combined.loc[~dedupe]
        combined = pd.concat([with_keys, without_keys], ignore_index=True)
    return combined.sort_values("_date", kind="stable").reset_index(drop=True)


def _candidate_multiplier(team_value: float, league_value: float, starts: int) -> float:
    if starts < MIN_TEAM_STARTS or league_value <= 0:
        return 1.0
    shrink = float(starts) / (float(starts) + TEAM_PRIOR_STARTS)
    raw_delta = float(team_value / league_value - 1.0)
    # Team usage is confounded by pitcher quality, so only half of the shrunken
    # organization-level difference is even considered as a future candidate.
    candidate = 1.0 + 0.50 * shrink * raw_delta
    return float(np.clip(candidate, 0.97, 1.03))


def build_team_leash_context(
    projections: pd.DataFrame,
    observations: pd.DataFrame | None,
    team: str,
    game_date: object,
) -> TeamLeashContext:
    """Build a strictly prior-date organization-level starter usage context.

    Only resolved starts with game_date strictly before the target date are used,
    so same-day and future outcomes cannot leak into a pregame context. The current
    implementation is descriptive/candidate-only and does not alter projections.
    """
    team = str(team or "UNK").upper()
    history = resolved_starter_workloads(projections, observations)
    target = pd.to_datetime(game_date, errors="coerce", utc=True)
    if pd.notna(target):
        target_day = pd.Timestamp(target).date()
        target_year = target_day.year
        history = history.loc[history["_date"].dt.date < target_day].copy()
        history = history.loc[history["_date"].dt.year.eq(target_year)].copy()
    if history.empty:
        league_avg_pitches, league_avg_bf, league_avg_outs = 88.0, 22.0, 16.0
        team_rows = history
        league_rows = history
    else:
        league_rows = history.tail(MAX_LEAGUE_STARTS).copy()
        team_rows = history.loc[history["team"].astype(str).str.upper().eq(team)].tail(MAX_TEAM_STARTS).copy()
        league_avg_pitches = float(pd.to_numeric(league_rows["actual_pitches"], errors="coerce").mean())
        league_avg_bf = float(pd.to_numeric(league_rows["actual_batters_faced"], errors="coerce").mean())
        league_avg_outs = float(pd.to_numeric(league_rows["actual_outs"], errors="coerce").mean())
        if not np.isfinite(league_avg_pitches): league_avg_pitches = 88.0
        if not np.isfinite(league_avg_bf): league_avg_bf = 22.0
        if not np.isfinite(league_avg_outs): league_avg_outs = 16.0

    starts = int(len(team_rows))
    team_avg_pitches = _weighted(team_rows.get("actual_pitches", pd.Series(dtype=float)), 12.0, league_avg_pitches)
    team_avg_bf = _weighted(team_rows.get("actual_batters_faced", pd.Series(dtype=float)), 12.0, league_avg_bf)
    team_avg_outs = _weighted(team_rows.get("actual_outs", pd.Series(dtype=float)), 12.0, league_avg_outs)

    if starts:
        pitches = pd.to_numeric(team_rows["actual_pitches"], errors="coerce")
        bf = pd.to_numeric(team_rows["actual_batters_faced"], errors="coerce")
        outs = pd.to_numeric(team_rows["actual_outs"], errors="coerce")
        quick_hook_rate = float((outs < 15).mean())
        # 19th batter begins a third trip through a nine-hitter batting order.
        tto_reach_rate = float((bf >= 19).mean())
        pitch_90_rate = float((pitches >= 90).mean())
    else:
        quick_hook_rate = tto_reach_rate = pitch_90_rate = 0.0

    pitch_multiplier = _candidate_multiplier(team_avg_pitches, league_avg_pitches, starts)
    bf_multiplier = _candidate_multiplier(team_avg_bf, league_avg_bf, starts)
    outs_multiplier = _candidate_multiplier(team_avg_outs, league_avg_outs, starts)
    status = "TRACKING" if starts >= MIN_TEAM_STARTS else "LEARNING"
    if status == "LEARNING":
        label = "LEARNING"
    elif pitch_multiplier <= 0.992 and outs_multiplier <= 0.992:
        label = "TIGHTER"
    elif pitch_multiplier >= 1.008 and outs_multiplier >= 1.008:
        label = "LONGER"
    else:
        label = "NEUTRAL"

    return TeamLeashContext(
        version=TEAM_LEASH_VERSION,
        role=TEAM_LEASH_ROLE,
        team=team,
        starts_used=starts,
        league_starts=int(len(league_rows)),
        team_avg_pitches=float(team_avg_pitches),
        team_avg_bf=float(team_avg_bf),
        team_avg_outs=float(team_avg_outs),
        league_avg_pitches=float(league_avg_pitches),
        league_avg_bf=float(league_avg_bf),
        league_avg_outs=float(league_avg_outs),
        quick_hook_rate=quick_hook_rate,
        tto_reach_rate=tto_reach_rate,
        pitch_90_rate=pitch_90_rate,
        pitch_multiplier_candidate=pitch_multiplier,
        bf_multiplier_candidate=bf_multiplier,
        outs_multiplier_candidate=outs_multiplier,
        label=label,
        status=status,
    )


def candidate_workload_fields(context: TeamLeashContext, expected_pitches: float, expected_bf: float, expected_outs: float) -> dict[str, object]:
    """Return counterfactual candidate exposure without changing the live model."""
    pitch_candidate = float(expected_pitches) * float(context.pitch_multiplier_candidate)
    bf_candidate = float(expected_bf) * float(context.bf_multiplier_candidate)
    outs_candidate = float(expected_outs) * float(context.outs_multiplier_candidate)
    return {
        "team_leash_candidate_expected_pitches": pitch_candidate,
        "team_leash_candidate_expected_bf": bf_candidate,
        "team_leash_candidate_expected_outs": outs_candidate,
        "team_leash_candidate_pitch_delta": pitch_candidate - float(expected_pitches),
        "team_leash_candidate_bf_delta": bf_candidate - float(expected_bf),
        "team_leash_candidate_outs_delta": outs_candidate - float(expected_outs),
    }


def _validation_status(n: int, relative_improvement: float | None, improved_share: float | None) -> tuple[str, str]:
    if n < MIN_VALIDATION_STARTS:
        return "LEARNING", f"Need {MIN_VALIDATION_STARTS} leakage-safe evaluated starts; {n} available."
    rel = 0.0 if relative_improvement is None else float(relative_improvement)
    share = 0.5 if improved_share is None else float(improved_share)
    if rel >= 0.05 and share >= 0.55:
        return "HELPING", "Candidate MAE is at least 5% better and most evaluated starts improved."
    if rel <= -0.05 and share <= 0.45:
        return "HURTING", "Candidate MAE is at least 5% worse and fewer than half of evaluated starts improved."
    return "MIXED", "Enough evidence exists, but the candidate workload adjustment is not consistently better or worse."


def team_leash_walk_forward_report(projections: pd.DataFrame, observations: pd.DataFrame | None = None) -> pd.DataFrame:
    """Backtest the candidate workload adjustment with strict prior-date team data.

    The forecast itself remains untouched. Each row's candidate is reconstructed
    using only team/league outcomes from earlier dates and compared with the frozen
    workload-v1 baseline against the same final workload result.
    """
    columns = [
        "Signal", "Target", "Evaluated Starts", "Baseline MAE", "Candidate MAE",
        "MAE Improvement", "Relative MAE Improvement", "Improved Starts", "Improved Share",
        "Baseline Bias", "Candidate Bias", "Status", "Reason", "Validation Version",
    ]
    if projections is None or projections.empty:
        return pd.DataFrame(columns=columns)
    frame = projections.copy()
    if "history_semantics" in frame.columns:
        frame = frame.loc[frame["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)].copy()
    if "workload_version" in frame.columns:
        frame = frame.loc[frame["workload_version"].astype(str).eq("workload-v1")].copy()
    if frame.empty or "game_date" not in frame.columns or "team" not in frame.columns:
        return pd.DataFrame(columns=columns)
    frame["_date"] = pd.to_datetime(frame["game_date"], errors="coerce", utc=True)
    frame = frame.dropna(subset=["_date"]).sort_values(["_date", "game_pk"], kind="stable")

    specs = (
        ("Pitches", "expected_pitches", "actual_pitches", "pitch_multiplier_candidate"),
        ("Batters Faced", "expected_bf", "actual_batters_faced", "bf_multiplier_candidate"),
        ("Outs", "expected_outs", "actual_outs", "outs_multiplier_candidate"),
    )
    records: dict[str, list[tuple[float, float, float]]] = {name: [] for name, *_ in specs}
    for _, row in frame.iterrows():
        context = build_team_leash_context(projections, observations, str(row.get("team", "")), row.get("game_date"))
        if context.status != "TRACKING":
            continue
        for target_name, baseline_col, actual_col, multiplier_attr in specs:
            baseline = pd.to_numeric(pd.Series([row.get(baseline_col)]), errors="coerce").iloc[0]
            actual = pd.to_numeric(pd.Series([row.get(actual_col)]), errors="coerce").iloc[0]
            if pd.isna(baseline) or pd.isna(actual):
                continue
            candidate = float(baseline) * float(getattr(context, multiplier_attr))
            records[target_name].append((float(baseline), candidate, float(actual)))

    rows: list[dict[str, object]] = []
    for target_name, *_ in specs:
        values = records[target_name]
        n = len(values)
        if n:
            arr = np.asarray(values, dtype=float)
            baseline_error = arr[:, 2] - arr[:, 0]
            candidate_error = arr[:, 2] - arr[:, 1]
            baseline_abs = np.abs(baseline_error)
            candidate_abs = np.abs(candidate_error)
            baseline_mae = float(baseline_abs.mean())
            candidate_mae = float(candidate_abs.mean())
            improvement = baseline_mae - candidate_mae
            relative = None if baseline_mae <= 1e-12 else float(improvement / baseline_mae)
            improved = int((candidate_abs < baseline_abs).sum())
            share = float(improved / n)
            baseline_bias = float(baseline_error.mean())
            candidate_bias = float(candidate_error.mean())
        else:
            baseline_mae = candidate_mae = improvement = relative = share = baseline_bias = candidate_bias = None
            improved = 0
        status, reason = _validation_status(n, relative, share)
        rows.append({
            "Signal": "Team leash candidate",
            "Target": target_name,
            "Evaluated Starts": n,
            "Baseline MAE": baseline_mae,
            "Candidate MAE": candidate_mae,
            "MAE Improvement": improvement,
            "Relative MAE Improvement": relative,
            "Improved Starts": improved,
            "Improved Share": share,
            "Baseline Bias": baseline_bias,
            "Candidate Bias": candidate_bias,
            "Status": status,
            "Reason": reason,
            "Validation Version": TEAM_LEASH_VERSION,
        })
    return pd.DataFrame(rows, columns=columns)


def snapshot_dict(context: TeamLeashContext | Mapping[str, object]) -> dict[str, object]:
    return context.snapshot_fields() if isinstance(context, TeamLeashContext) else dict(context)

from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.role_workload_gate import build_role_workload_decision
from engine.starter_role import build_starter_role_context
from engine.workload_context import build_workload_context

RUNTIME_STATE_PATH = Path("data/starter_role_runtime_state.csv")
DAILY_ROLE_SHADOW_VERSION = "daily-role-shadow-v1"


def normalize_daily_starter_log(log: pd.DataFrame) -> pd.DataFrame:
    """Map the automated runner schema into the production workload contract."""
    if log is None or log.empty:
        return pd.DataFrame(columns=["date", "games_started", "pitches", "bf", "outs"])
    work = log.copy()
    if "bf" not in work.columns:
        work["bf"] = pd.to_numeric(work.get("batters_faced"), errors="coerce")
    for col in ("games_started", "pitches", "bf", "outs"):
        if col not in work.columns:
            work[col] = 0
        work[col] = pd.to_numeric(work[col], errors="coerce")
    if "date" not in work.columns:
        work["date"] = pd.NaT
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    return work[["date", "games_started", "pitches", "bf", "outs"]].copy()


def load_runtime_state(path: Path = RUNTIME_STATE_PATH) -> pd.DataFrame:
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def attach_daily_role_shadow(
    record: dict[str, object],
    starter_log: pd.DataFrame,
    game_date: object,
    role_history: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Append role-workload shadow diagnostics without changing projections."""
    out = dict(record)
    normalized = normalize_daily_starter_log(starter_log)
    base = build_workload_context(normalized, game_date)
    role_context = build_starter_role_context(normalized, game_date)
    history = role_history if role_history is not None else load_runtime_state()
    decision = build_role_workload_decision(
        normalized,
        base,
        history,
        game_date=game_date,
        mode="shadow",
    )
    out["daily_role_shadow_version"] = DAILY_ROLE_SHADOW_VERSION
    out.update(decision.snapshot_fields())

    # Persist the raw pregame classifier evidence separately from the workload
    # decision. These fields are observational only and cannot alter projections.
    out.update(role_context.snapshot_fields())
    out["role_shadow_classifier_label"] = role_context.label
    out["role_shadow_classifier_confidence"] = role_context.confidence
    out["role_shadow_classifier_starts_used"] = role_context.starts_used
    out["role_shadow_classifier_recent_pitches"] = role_context.recent_pitches
    out["role_shadow_classifier_prior_pitches"] = role_context.prior_pitches
    out["role_shadow_classifier_recent_bf"] = role_context.recent_bf
    out["role_shadow_classifier_prior_bf"] = role_context.prior_bf
    out["role_shadow_classifier_recent_outs"] = role_context.recent_outs
    out["role_shadow_classifier_prior_outs"] = role_context.prior_outs
    out["role_shadow_classifier_low_exposure_share"] = role_context.low_exposure_share
    out["role_shadow_classifier_ramp_ratio"] = role_context.ramp_ratio
    out["role_shadow_classifier_reason"] = role_context.reason

    out["role_shadow_base_expected_pitches"] = base.expected_pitches
    out["role_shadow_base_expected_bf"] = base.expected_bf
    out["role_shadow_base_expected_outs"] = base.expected_outs
    return out

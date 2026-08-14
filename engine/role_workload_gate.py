from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

import numpy as np
import pandas as pd

from engine.starter_role import ROLE_RAMPING, ROLE_RESTRICTED, build_starter_role_context
from engine.workload_context import WorkloadContext

ROLE_WORKLOAD_VERSION = "starter-role-workload-v1"
ELIGIBLE_ROLES = {ROLE_RAMPING, ROLE_RESTRICTED}
MIN_OBSERVATIONS = 30
WINDOW = 180
PRIOR_STRENGTH = 60.0
CAPS = {"pitches": 5.0, "bf": 1.5, "outs": 1.5}


@dataclass(frozen=True)
class RoleWorkloadDecision:
    version: str
    mode: str
    role: str
    eligible: bool
    applied: bool
    reason: str
    prior_n_pitches: int
    prior_n_bf: int
    prior_n_outs: int
    correction_pitches: float
    correction_bf: float
    correction_outs: float
    base: WorkloadContext
    candidate: WorkloadContext
    effective: WorkloadContext

    def snapshot_fields(self) -> dict[str, object]:
        return {
            "role_workload_version": self.version,
            "role_workload_mode": self.mode,
            "starter_role_label": "LOW_RECENT_EXPOSURE" if self.role == ROLE_RESTRICTED else self.role,
            "role_workload_eligible": self.eligible,
            "role_workload_applied": self.applied,
            "role_workload_reason": self.reason,
            "role_prior_n_pitches": self.prior_n_pitches,
            "role_prior_n_bf": self.prior_n_bf,
            "role_prior_n_outs": self.prior_n_outs,
            "role_correction_pitches": self.correction_pitches,
            "role_correction_bf": self.correction_bf,
            "role_correction_outs": self.correction_outs,
            "role_candidate_expected_pitches": self.candidate.expected_pitches,
            "role_candidate_expected_bf": self.candidate.expected_bf,
            "role_candidate_expected_outs": self.candidate.expected_outs,
        }


def _num(series: object, index: pd.Index) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    return pd.Series(np.nan, index=index, dtype=float)


def _correction(history: pd.DataFrame, role: str, metric: str, game_date: object | None) -> tuple[int, float]:
    if history is None or history.empty:
        return 0, 0.0
    work = history.copy()
    # Runtime history is stored as date-only strings while live MLB game times are
    # UTC timestamps. Normalize both sides to UTC before comparing so an eligible
    # RAMPING/RESTRICTED starter cannot be dropped by a naive/aware datetime error.
    dates = pd.to_datetime(work.get("game_date"), errors="coerce", utc=True)
    target = pd.to_datetime(game_date, errors="coerce", utc=True)
    mask = work.get("starter_role_label", pd.Series("", index=work.index)).astype(str).eq(str(role))
    if pd.notna(target):
        mask &= dates.dt.normalize().lt(pd.Timestamp(target).normalize())
    prior = work.loc[mask].copy()
    actual = _num(prior.get(f"actual_{metric}"), prior.index)
    baseline = _num(prior.get(f"projected_{metric}"), prior.index)
    residual = (actual - baseline).dropna().tail(WINDOW)
    n = int(len(residual))
    if n < MIN_OBSERVATIONS:
        return n, 0.0
    shrink = float(n / (n + PRIOR_STRENGTH))
    value = float(np.clip(float(residual.mean()) * shrink, -CAPS[metric], CAPS[metric]))
    return n, value


def build_role_workload_decision(
    starter_log: pd.DataFrame,
    base: WorkloadContext,
    role_history: pd.DataFrame | None,
    game_date: object | None = None,
    mode: str = "shadow",
) -> RoleWorkloadDecision:
    """Reproduce the promoted role correction behind an explicit safety gate.

    mode='shadow' computes the candidate but returns workload-v1 as effective.
    mode='active' applies the candidate. Any other value is treated as off.
    """
    normalized_mode = str(mode or "shadow").strip().lower()
    if normalized_mode not in {"off", "shadow", "active"}:
        normalized_mode = "shadow"
    role_ctx = build_starter_role_context(starter_log, game_date)
    role = role_ctx.label
    eligible = role in ELIGIBLE_ROLES
    if not eligible or normalized_mode == "off":
        reason = "role_not_eligible" if not eligible else "gate_off"
        return RoleWorkloadDecision(
            ROLE_WORKLOAD_VERSION, normalized_mode, role, eligible, False, reason,
            0, 0, 0, 0.0, 0.0, 0.0, base, base, base,
        )

    npitch, cp = _correction(role_history if role_history is not None else pd.DataFrame(), role, "pitches", game_date)
    nbf, cb = _correction(role_history if role_history is not None else pd.DataFrame(), role, "bf", game_date)
    nouts, co = _correction(role_history if role_history is not None else pd.DataFrame(), role, "outs", game_date)
    ready = min(npitch, nbf, nouts) >= MIN_OBSERVATIONS
    if not ready:
        return RoleWorkloadDecision(
            ROLE_WORKLOAD_VERSION, normalized_mode, role, True, False, "insufficient_prior_role_residuals",
            npitch, nbf, nouts, cp, cb, co, base, base, base,
        )

    candidate = replace(
        base,
        expected_pitches=float(np.clip(base.expected_pitches + cp, 60.0, 112.0)),
        expected_bf=float(np.clip(base.expected_bf + cb, 10.0, 35.0)),
        expected_outs=float(np.clip(base.expected_outs + co, 6.0, 24.0)),
    )
    applied = normalized_mode == "active"
    effective = candidate if applied else base
    return RoleWorkloadDecision(
        ROLE_WORKLOAD_VERSION, normalized_mode, role, True, applied,
        "active_promoted_candidate" if applied else "shadow_only",
        npitch, nbf, nouts, cp, cb, co, base, candidate, effective,
    )

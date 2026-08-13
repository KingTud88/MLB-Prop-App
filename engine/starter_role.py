from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

STARTER_ROLE_VERSION = "starter-role-v1"
ROLE_ESTABLISHED = "ESTABLISHED"
ROLE_RAMPING = "RAMPING"
ROLE_RESTRICTED = "RESTRICTED"
ROLE_OPENER_LIKE = "OPENER_LIKE"
ROLE_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class StarterRoleContext:
    version: str
    label: str
    confidence: str
    starts_used: int
    recent_pitches: float | None
    prior_pitches: float | None
    recent_bf: float | None
    prior_bf: float | None
    recent_outs: float | None
    prior_outs: float | None
    low_exposure_share: float
    ramp_ratio: float | None
    reason: str

    def snapshot_fields(self) -> dict[str, object]:
        return {
            "starter_role_version": self.version,
            "starter_role_label": self.label,
            "starter_role_confidence": self.confidence,
            "starter_role_starts_used": self.starts_used,
            "starter_role_recent_pitches": self.recent_pitches,
            "starter_role_prior_pitches": self.prior_pitches,
            "starter_role_recent_bf": self.recent_bf,
            "starter_role_prior_bf": self.prior_bf,
            "starter_role_recent_outs": self.recent_outs,
            "starter_role_prior_outs": self.prior_outs,
            "starter_role_low_exposure_share": self.low_exposure_share,
            "starter_role_ramp_ratio": self.ramp_ratio,
            "starter_role_reason": self.reason,
        }


def _pregame_starts(log: pd.DataFrame, game_date: object | None) -> pd.DataFrame:
    if log is None or log.empty:
        return pd.DataFrame()
    work = log.copy()
    if "games_started" in work.columns:
        gs = pd.to_numeric(work["games_started"], errors="coerce").fillna(0)
        work = work.loc[gs.ge(1)].copy()
    # If starter identity is unavailable, do not guess from workload shape.
    else:
        return work.iloc[0:0].copy()

    if "date" not in work.columns:
        work["date"] = pd.NaT
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    target = pd.to_datetime(game_date, errors="coerce", utc=True) if game_date is not None else pd.NaT
    if pd.notna(target):
        target_day = pd.Timestamp(target).date()
        dated = work["date"].notna()
        work = work.loc[~dated | (work["date"].dt.date < target_day)].copy()
    if work["date"].notna().any():
        work = work.sort_values("date", na_position="first")
    for col in ("pitches", "bf", "outs"):
        if col not in work.columns:
            work[col] = np.nan
        work[col] = pd.to_numeric(work[col], errors="coerce")
    return work.tail(12).reset_index(drop=True)


def _mean(frame: pd.DataFrame, col: str) -> float | None:
    values = pd.to_numeric(frame.get(col), errors="coerce").dropna()
    return float(values.mean()) if not values.empty else None


def build_starter_role_context(log: pd.DataFrame, game_date: object | None = None) -> StarterRoleContext:
    """Classify pregame starter exposure shape without changing projections.

    This is context-only v1. It uses MLB starter-only history strictly before the
    target date. Labels are deliberately conservative and are not a claim about
    announced injury restrictions or team intent.
    """
    starts = _pregame_starts(log, game_date)
    n = int(len(starts))
    if n < 2:
        return StarterRoleContext(
            STARTER_ROLE_VERSION, ROLE_UNKNOWN, "LOW", n,
            _mean(starts, "pitches"), None, _mean(starts, "bf"), None,
            _mean(starts, "outs"), None, 0.0, None,
            "Fewer than two prior MLB starts; no role inference.",
        )

    recent = starts.tail(min(3, n))
    prior = starts.iloc[:-len(recent)].tail(5)
    recent_p = _mean(recent, "pitches")
    prior_p = _mean(prior, "pitches")
    recent_bf = _mean(recent, "bf")
    prior_bf = _mean(prior, "bf")
    recent_outs = _mean(recent, "outs")
    prior_outs = _mean(prior, "outs")

    pitches = pd.to_numeric(starts["pitches"], errors="coerce")
    bf = pd.to_numeric(starts["bf"], errors="coerce")
    outs = pd.to_numeric(starts["outs"], errors="coerce")
    low = ((pitches.le(55)) | (bf.le(14)) | (outs.le(9))).fillna(False)
    low_share = float(low.mean()) if n else 0.0
    ramp_ratio = None
    if recent_p is not None and prior_p is not None and prior_p > 0:
        ramp_ratio = float(recent_p / prior_p)

    # Repeated very short starts are opener-like workload behavior. We avoid
    # asserting true opener intent because that requires reliable role metadata.
    last3 = starts.tail(min(3, n))
    last3_low = ((pd.to_numeric(last3["pitches"], errors="coerce").le(55)) |
                 (pd.to_numeric(last3["bf"], errors="coerce").le(14)) |
                 (pd.to_numeric(last3["outs"], errors="coerce").le(9))).fillna(False)
    if n >= 3 and int(last3_low.sum()) >= 2 and low_share >= 0.50:
        label, confidence = ROLE_OPENER_LIKE, "HIGH" if n >= 5 else "MEDIUM"
        reason = "Repeated prior starts ended at very low pitch/BF/out exposure."
    elif recent_p is not None and recent_p < 70 and (recent_outs is None or recent_outs < 14):
        label, confidence = ROLE_RESTRICTED, "MEDIUM" if n >= 3 else "LOW"
        reason = "Recent starter-only workload remains materially below a normal full-start shape."
    elif ramp_ratio is not None and prior_p >= 55 and ramp_ratio >= 1.15 and recent_p < 90:
        label, confidence = ROLE_RAMPING, "MEDIUM" if n >= 5 else "LOW"
        reason = "Recent pitch exposure is rising materially versus earlier prior starts but remains below full workload."
    else:
        label, confidence = ROLE_ESTABLISHED, "HIGH" if n >= 5 else "MEDIUM"
        reason = "Prior starter-only workload does not meet conservative ramp/restriction/opener-like rules."

    return StarterRoleContext(
        STARTER_ROLE_VERSION, label, confidence, n,
        recent_p, prior_p, recent_bf, prior_bf, recent_outs, prior_outs,
        low_share, ramp_ratio, reason,
    )

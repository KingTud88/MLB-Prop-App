from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CalibrationResult:
    weight_simulation: float
    weight_math: float
    observations: int
    brier_score: float | None
    calibrated: bool
    reason: str


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((np.clip(p, 0.0, 1.0) - y) ** 2))


def calibrate_blend(
    frame: pd.DataFrame,
    line: int,
    min_observations: int = 30,
    grid_step: float = 0.02,
) -> CalibrationResult:
    """Choose the simulation/math blend from resolved pregame projections only.

    Calibration is deliberately chronological-safe at the caller: only rows
    whose actual result is already known should be supplied.  With too little
    history the production blend stays at 50/50 rather than overfitting noise.
    """
    sim_col = f"sim_{line}p"
    math_col = f"math_{line}p"
    actual_col = "actual_strikeouts"
    if not {sim_col, math_col, actual_col}.issubset(frame.columns):
        return CalibrationResult(0.50, 0.50, 0, None, False, "Calibration fields are not populated yet.")

    data = frame[[sim_col, math_col, actual_col]].copy()
    data = data.dropna()
    if len(data) < min_observations:
        return CalibrationResult(0.50, 0.50, len(data), None, False, f"Need {min_observations} resolved observations; only {len(data)} are available.")

    y = (pd.to_numeric(data[actual_col], errors="coerce") >= int(line)).astype(float).to_numpy()
    sim = np.clip(pd.to_numeric(data[sim_col], errors="coerce").to_numpy(float), 0.001, 0.999)
    math = np.clip(pd.to_numeric(data[math_col], errors="coerce").to_numpy(float), 0.001, 0.999)
    good = np.isfinite(y) & np.isfinite(sim) & np.isfinite(math)
    y, sim, math = y[good], sim[good], math[good]
    if len(y) < min_observations:
        return CalibrationResult(0.50, 0.50, len(y), None, False, "Not enough valid resolved observations.")

    weights = np.arange(0.0, 1.0 + grid_step / 2.0, grid_step)
    scores = []
    for w in weights:
        p = w * sim + (1.0 - w) * math
        scores.append(_brier(y, p))
    best_idx = int(np.argmin(scores))
    raw_w = float(weights[best_idx])

    # Shrink learned weights toward 50/50 until the sample is large enough to
    # support a stable production decision.
    shrink = min(1.0, (len(y) - min_observations) / max(min_observations * 3.0, 1.0))
    final_w = 0.50 + shrink * (raw_w - 0.50)
    final_score = _brier(y, final_w * sim + (1.0 - final_w) * math)
    return CalibrationResult(final_w, 1.0 - final_w, len(y), final_score, True, "Weight learned from resolved historical projections.")


def calibration_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Return compact resolved-sample diagnostics for the Model Card."""
    if frame.empty or "actual_strikeouts" not in frame.columns:
        return pd.DataFrame(columns=["Metric", "Value"])
    data = frame.copy()
    actual = pd.to_numeric(data["actual_strikeouts"], errors="coerce")
    projected = pd.to_numeric(data.get("projection"), errors="coerce")
    mask = actual.notna() & projected.notna()
    if not mask.any():
        return pd.DataFrame([
            {"Metric": "Resolved projections", "Value": 0},
            {"Metric": "Status", "Value": "Waiting for completed games to resolve"},
        ])
    err = projected[mask] - actual[mask]
    return pd.DataFrame([
        {"Metric": "Resolved projections", "Value": int(mask.sum())},
        {"Metric": "MAE (strikeouts)", "Value": round(float(err.abs().mean()), 3)},
        {"Metric": "Mean bias", "Value": round(float(err.mean()), 3)},
        {"Metric": "RMSE (strikeouts)", "Value": round(float(np.sqrt(np.mean(err.to_numpy() ** 2))), 3)},
    ])

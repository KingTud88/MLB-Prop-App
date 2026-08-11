from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS


@dataclass(frozen=True)
class OutsCalibrationResult:
    weight_simulation: float
    weight_math: float
    observations: int
    brier_score: float | None
    calibrated: bool
    reason: str


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((np.clip(p, 0.0, 1.0) - y) ** 2))


def _key(line: float) -> str:
    return str(float(line)).replace(".", "_")


def _eligible_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "history_semantics" not in frame.columns:
        return frame.iloc[0:0].copy()
    return frame.loc[frame["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)].copy()


def calibrate_outs_blend(
    frame: pd.DataFrame,
    line: float,
    min_observations: int = 30,
    grid_step: float = 0.02,
) -> OutsCalibrationResult:
    frame = _eligible_rows(frame)
    key = _key(line)
    sim_col = f"outs_sim_over_{key}"
    math_col = f"outs_math_over_{key}"
    actual_col = "actual_outs"
    if frame.empty or not {sim_col, math_col, actual_col}.issubset(frame.columns):
        return OutsCalibrationResult(0.50, 0.50, 0, None, False, "Starter-only outs calibration fields are not populated yet.")

    data = frame[[sim_col, math_col, actual_col]].copy().dropna()
    sim = pd.to_numeric(data[sim_col], errors="coerce")
    math = pd.to_numeric(data[math_col], errors="coerce")
    actual = pd.to_numeric(data[actual_col], errors="coerce")
    good = sim.notna() & math.notna() & actual.notna()
    sim = sim.loc[good].to_numpy(float)
    math = math.loc[good].to_numpy(float)
    actual = actual.loc[good].to_numpy(float)
    n = len(actual)
    if n < min_observations:
        return OutsCalibrationResult(0.50, 0.50, n, None, False, f"Need {min_observations} starter-only resolved outs observations; only {n} are available.")

    cutoff = int(np.floor(float(line)) + 1)
    y = (actual >= cutoff).astype(float)
    sim = np.clip(sim, 0.001, 0.999)
    math = np.clip(math, 0.001, 0.999)
    weights = np.arange(0.0, 1.0 + grid_step / 2.0, grid_step)
    scores = [_brier(y, w * sim + (1.0 - w) * math) for w in weights]
    raw_w = float(weights[int(np.argmin(scores))])
    shrink = min(1.0, (n - min_observations) / max(min_observations * 3.0, 1.0))
    final_w = 0.50 + shrink * (raw_w - 0.50)
    final_score = _brier(y, final_w * sim + (1.0 - final_w) * math)
    return OutsCalibrationResult(final_w, 1.0 - final_w, n, final_score, True, "Weight learned from starter-only resolved frozen total-outs projections.")


def outs_calibration_report(
    frame: pd.DataFrame,
    lines: tuple[float, ...] = (13.5, 14.5, 15.5, 16.5, 17.5, 18.5),
    min_observations: int = 30,
) -> pd.DataFrame:
    frame = _eligible_rows(frame)
    rows: list[dict[str, object]] = []
    for line in lines:
        key = _key(line)
        sim_col = f"outs_sim_over_{key}"
        math_col = f"outs_math_over_{key}"
        cols = {sim_col, math_col, "actual_outs"}
        if frame.empty or not cols.issubset(frame.columns):
            rows.append({"Line": line, "Observations": 0, "Status": "Waiting", "Simulation Weight": 0.50, "Math Weight": 0.50, "Calibrated Brier": None})
            continue
        data = frame[[sim_col, math_col, "actual_outs"]].dropna()
        cal = calibrate_outs_blend(frame, line, min_observations=min_observations)
        rows.append({
            "Line": line,
            "Observations": len(data),
            "Status": "Calibrated" if cal.calibrated else "50/50 baseline",
            "Simulation Weight": round(cal.weight_simulation, 3),
            "Math Weight": round(cal.weight_math, 3),
            "Calibrated Brier": None if cal.brier_score is None else round(cal.brier_score, 4),
        })
    return pd.DataFrame(rows)

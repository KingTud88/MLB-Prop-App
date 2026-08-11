from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

CALIBRATION_VERSION = "1.2"
PROBABILITY_SEMANTICS = "milestone-ceil-v1"
__all__ = ["CalibrationResult", "calibrate_blend", "milestone_calibration_report", "calibration_summary"]


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


def _eligible_probability_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Use only rows captured under the current milestone probability definition."""
    if frame.empty or "probability_semantics" not in frame.columns:
        return frame.iloc[0:0].copy()
    mask = frame["probability_semantics"].astype(str).eq(PROBABILITY_SEMANTICS)
    return frame.loc[mask].copy()


def calibrate_blend(
    frame: pd.DataFrame,
    line: int,
    min_observations: int = 30,
    grid_step: float = 0.02,
) -> CalibrationResult:
    """Choose the simulation/math blend from compatible resolved pregame projections only."""
    sim_col = f"sim_{line}p"
    math_col = f"math_{line}p"
    actual_col = "actual_strikeouts"
    frame = _eligible_probability_rows(frame)
    if not {sim_col, math_col, actual_col}.issubset(frame.columns):
        return CalibrationResult(0.50, 0.50, 0, None, False, "Calibration fields are not populated yet.")

    data = frame[[sim_col, math_col, actual_col]].copy().dropna()
    if len(data) < min_observations:
        return CalibrationResult(0.50, 0.50, len(data), None, False, f"Need {min_observations} compatible resolved observations; only {len(data)} are available.")

    y = (pd.to_numeric(data[actual_col], errors="coerce") >= int(line)).astype(float).to_numpy()
    sim = np.clip(pd.to_numeric(data[sim_col], errors="coerce").to_numpy(float), 0.001, 0.999)
    math = np.clip(pd.to_numeric(data[math_col], errors="coerce").to_numpy(float), 0.001, 0.999)
    good = np.isfinite(y) & np.isfinite(sim) & np.isfinite(math)
    y, sim, math = y[good], sim[good], math[good]
    if len(y) < min_observations:
        return CalibrationResult(0.50, 0.50, len(y), None, False, "Not enough valid compatible resolved observations.")

    weights = np.arange(0.0, 1.0 + grid_step / 2.0, grid_step)
    scores = [_brier(y, w * sim + (1.0 - w) * math) for w in weights]
    raw_w = float(weights[int(np.argmin(scores))])
    shrink = min(1.0, (len(y) - min_observations) / max(min_observations * 3.0, 1.0))
    final_w = 0.50 + shrink * (raw_w - 0.50)
    final_score = _brier(y, final_w * sim + (1.0 - final_w) * math)
    return CalibrationResult(final_w, 1.0 - final_w, len(y), final_score, True, "Weight learned from compatible resolved historical projections.")


def milestone_calibration_report(
    frame: pd.DataFrame,
    lines: range = range(3, 11),
    min_observations: int = 30,
) -> pd.DataFrame:
    """Return one auditable calibration row per strikeout milestone."""
    columns = [
        "Line", "Observations", "Status", "Simulation Brier", "Math Brier",
        "Calibrated Brier", "Simulation Weight", "Math Weight", "Actual Hit Rate",
    ]
    frame = _eligible_probability_rows(frame)
    rows: list[dict[str, object]] = []
    for line in lines:
        sim_col = f"sim_{line}p"
        math_col = f"math_{line}p"
        if frame.empty or not {sim_col, math_col, "actual_strikeouts"}.issubset(frame.columns):
            rows.append({"Line": f"{line}+", "Observations": 0, "Status": "Waiting", "Simulation Brier": None, "Math Brier": None, "Calibrated Brier": None, "Simulation Weight": 0.50, "Math Weight": 0.50, "Actual Hit Rate": None})
            continue

        data = frame[[sim_col, math_col, "actual_strikeouts"]].copy().dropna()
        if data.empty:
            rows.append({"Line": f"{line}+", "Observations": 0, "Status": "Waiting", "Simulation Brier": None, "Math Brier": None, "Calibrated Brier": None, "Simulation Weight": 0.50, "Math Weight": 0.50, "Actual Hit Rate": None})
            continue

        actual = pd.to_numeric(data["actual_strikeouts"], errors="coerce")
        sim = pd.to_numeric(data[sim_col], errors="coerce")
        math = pd.to_numeric(data[math_col], errors="coerce")
        valid = actual.notna() & sim.notna() & math.notna()
        actual = actual.loc[valid]
        sim = np.clip(sim.loc[valid].to_numpy(float), 0.001, 0.999)
        math = np.clip(math.loc[valid].to_numpy(float), 0.001, 0.999)
        y = (actual.to_numpy(float) >= line).astype(float)
        n = len(y)
        if n == 0:
            status = "Waiting"
            sim_brier = math_brier = cal_brier = None
            sim_w = 0.50
        else:
            cal = calibrate_blend(frame, line, min_observations=min_observations)
            sim_brier = _brier(y, sim)
            math_brier = _brier(y, math)
            cal_brier = _brier(y, cal.weight_simulation * sim + cal.weight_math * math)
            sim_w = cal.weight_simulation
            status = "Calibrated" if cal.calibrated else "50/50 baseline"

        rows.append({
            "Line": f"{line}+",
            "Observations": n,
            "Status": status,
            "Simulation Brier": None if sim_brier is None else round(sim_brier, 4),
            "Math Brier": None if math_brier is None else round(math_brier, 4),
            "Calibrated Brier": None if cal_brier is None else round(cal_brier, 4),
            "Simulation Weight": round(sim_w, 3),
            "Math Weight": round(1.0 - sim_w, 3),
            "Actual Hit Rate": None if n == 0 else round(float(y.mean()), 4),
        })
    return pd.DataFrame(rows, columns=columns)


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

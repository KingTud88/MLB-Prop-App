from __future__ import annotations

import pandas as pd

from engine.outs_calibration import calibrate_outs_blend


def _frame(n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        actual = 17 if i % 2 == 0 else 14
        rows.append({
            "outs_sim_over_15_5": 0.72 if actual >= 16 else 0.28,
            "outs_math_over_15_5": 0.58 if actual >= 16 else 0.42,
            "actual_outs": actual,
        })
    return pd.DataFrame(rows)


def test_outs_calibration_waits_below_minimum() -> None:
    result = calibrate_outs_blend(_frame(20), 15.5, min_observations=30)
    assert result.calibrated is False
    assert result.observations == 20
    assert result.weight_simulation == 0.50
    assert result.weight_math == 0.50


def test_outs_calibration_learns_after_minimum() -> None:
    result = calibrate_outs_blend(_frame(60), 15.5, min_observations=30)
    assert result.calibrated is True
    assert result.observations == 60
    assert result.brier_score is not None
    assert result.weight_simulation > 0.50


def test_outs_calibration_ignores_legacy_rows_without_paths() -> None:
    current = _frame(30)
    legacy = pd.DataFrame({"actual_outs": [16] * 20})
    frame = pd.concat([current, legacy], ignore_index=True)
    result = calibrate_outs_blend(frame, 15.5, min_observations=30)
    assert result.observations == 30

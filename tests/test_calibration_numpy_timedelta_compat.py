from __future__ import annotations

import warnings

import pandas as pd

from engine.calibration import calibrate_blend
from training.calibration_lineage import classify_rows


def _frame() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "game_date": "2026-08-13",
            "captured_at_utc": "2026-08-13T12:00:00Z",
            "probability_semantics": "milestone-ceil-v1",
            "history_semantics": "starter-only-v1",
            "actual_strikeouts": 5,
            "sim_5p": 0.60,
            "math_5p": 0.55,
        },
        {
            "game_date": "2026-08-13",
            "captured_at_utc": "2026-08-14T00:00:00Z",
            "probability_semantics": "milestone-ceil-v1",
            "history_semantics": "starter-only-v1",
            "actual_strikeouts": 5,
            "sim_5p": 0.60,
            "math_5p": 0.55,
        },
    ])


def test_calibration_cutoff_avoids_numpy_generic_timedelta_deprecation() -> None:
    frame = _frame()
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error",
            message=".*generic.*NumPy timedelta.*",
            category=DeprecationWarning,
        )
        result = calibrate_blend(frame, 5, min_observations=2)
        classified = classify_rows(frame)

    assert result.observations == 1
    assert bool(classified.loc[0, "calibration_eligible"]) is True
    assert bool(classified.loc[1, "calibration_eligible"]) is False
    assert "late_capture" in classified.loc[1, "calibration_exclusion_reason"]

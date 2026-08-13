from __future__ import annotations

import pandas as pd

from engine.calibration import calibrate_blend


def _row(*, captured: str, actual: float = 5.0) -> dict[str, object]:
    return {
        "game_date": "2026-08-13",
        "captured_at_utc": captured,
        "probability_semantics": "milestone-ceil-v1",
        "history_semantics": "starter-only-v1",
        "actual_strikeouts": actual,
        "sim_5p": 0.60,
        "math_5p": 0.55,
    }


def test_production_calibration_rejects_clearly_late_capture() -> None:
    frame = pd.DataFrame([
        _row(captured="2026-08-13T12:00:00Z"),
        _row(captured="2026-08-14T00:00:00Z"),
    ])
    result = calibrate_blend(frame, 5, min_observations=2)
    assert result.observations == 1
    assert result.calibrated is False


def test_production_calibration_rejects_missing_capture_lineage() -> None:
    frame = pd.DataFrame([_row(captured="2026-08-13T12:00:00Z")]).drop(columns=["captured_at_utc"])
    result = calibrate_blend(frame, 5, min_observations=1)
    assert result.observations == 0
    assert result.calibrated is False

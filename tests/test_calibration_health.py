from __future__ import annotations

import math
import pandas as pd

from training.calibration_health import build_report


def _row(*, actual: float, probability: float, probability_semantics: str = "milestone-ceil-v1", history_semantics: str = "starter-only-v1") -> dict[str, object]:
    return {
        "game_date": "2026-08-13",
        "captured_at_utc": "2026-08-13T00:00:00Z",
        "actual_strikeouts": actual,
        "probability_semantics": probability_semantics,
        "history_semantics": history_semantics,
        "sim_over_4_5": probability,
    }


def test_health_uses_only_lineage_eligible_rows() -> None:
    frame = pd.DataFrame([
        _row(actual=6, probability=0.75),
        _row(actual=3, probability=0.25),
        _row(actual=8, probability=0.99, probability_semantics="legacy"),
    ])
    report = build_report(frame)
    row = report.loc[report["Line"] == 4.5].iloc[0]
    assert int(row["Resolved_Starts"]) == 2
    assert math.isclose(float(row["Mean_Predicted_Probability"]), 0.5)
    assert math.isclose(float(row["Empirical_Over_Rate"]), 0.5)
    assert math.isclose(float(row["Calibration_Gap"]), 0.0)


def test_health_is_descriptive_and_skips_missing_probability_columns() -> None:
    frame = pd.DataFrame([_row(actual=5, probability=0.4)])
    report = build_report(frame)
    assert report["Line"].tolist() == [4.5]
    assert float(report.iloc[0]["Brier_Score"]) >= 0.0


def test_health_returns_schema_when_no_rows_are_eligible() -> None:
    frame = pd.DataFrame([_row(actual=5, probability=0.4, history_semantics="legacy")])
    report = build_report(frame)
    assert report.empty
    assert "Brier_Score" in report.columns

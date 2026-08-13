from __future__ import annotations

import math

import pandas as pd

from training.calibration_health import build_report


def _row(
    *,
    actual: float,
    sim_probability: float,
    math_probability: float,
    probability_semantics: str = "milestone-ceil-v1",
    history_semantics: str = "starter-only-v1",
) -> dict[str, object]:
    return {
        "game_date": "2026-08-13",
        "captured_at_utc": "2026-08-13T00:00:00Z",
        "actual_strikeouts": actual,
        "probability_semantics": probability_semantics,
        "history_semantics": history_semantics,
        "sim_5p": sim_probability,
        "math_5p": math_probability,
    }


def test_health_maps_integer_milestone_to_equivalent_half_line() -> None:
    frame = pd.DataFrame([
        _row(actual=6, sim_probability=0.75, math_probability=0.65),
        _row(actual=3, sim_probability=0.25, math_probability=0.35),
        _row(actual=8, sim_probability=0.99, math_probability=0.99, probability_semantics="legacy"),
    ])
    report = build_report(frame)

    sim = report.loc[(report["Path"] == "SIM") & (report["Milestone"] == 5)].iloc[0]
    math_row = report.loc[(report["Path"] == "MATH") & (report["Milestone"] == 5)].iloc[0]
    assert float(sim["Equivalent_Over_Line"]) == 4.5
    assert sim["Source_Column"] == "sim_5p"
    assert math_row["Source_Column"] == "math_5p"
    assert int(sim["Resolved_Starts"]) == 2
    assert math.isclose(float(sim["Mean_Predicted_Probability"]), 0.5)
    assert math.isclose(float(sim["Empirical_Hit_Rate"]), 0.5)
    assert math.isclose(float(sim["Calibration_Gap"]), 0.0)


def test_health_preserves_sim_and_math_as_separate_paths() -> None:
    frame = pd.DataFrame([_row(actual=5, sim_probability=0.4, math_probability=0.6)])
    report = build_report(frame)
    milestone = report.loc[report["Milestone"] == 5].sort_values("Path")
    assert milestone["Path"].tolist() == ["MATH", "SIM"]
    assert set(milestone["Resolved_Starts"].astype(int)) == {1}
    assert all(milestone["Brier_Score"].astype(float).ge(0.0))


def test_health_skips_missing_milestones_without_inventing_probabilities() -> None:
    frame = pd.DataFrame([_row(actual=5, sim_probability=0.4, math_probability=0.6)])
    report = build_report(frame)
    assert sorted(report["Milestone"].unique().tolist()) == [5]


def test_health_returns_schema_when_no_rows_are_eligible() -> None:
    frame = pd.DataFrame([
        _row(actual=5, sim_probability=0.4, math_probability=0.6, history_semantics="legacy")
    ])
    report = build_report(frame)
    assert report.empty
    assert "Brier_Score" in report.columns
    assert "Path" in report.columns

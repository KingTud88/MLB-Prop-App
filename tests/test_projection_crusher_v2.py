from __future__ import annotations

import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS
from training.projection_crusher_v2 import (
    CRUSHER_V2_VERSION,
    PRODUCTION_AUTHORITY,
    _prob,
    build_cohort_summary,
    build_coverage,
    build_detail,
)


def _history() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "game_date": "2026-08-01", "player": "A", "team": "CLE", "opponent": "DET",
            "projection": 5.80, "actual_strikeouts": 7, "confidence": "High", "data_quality": 95,
            "sim_5p": 72.0, "math_5p": 0.68, "opponent_k_pct": 26.0,
            "lineup_confirmed": True, "weather_delay_risk": "NONE", "leash_label": "NORMAL",
            "starter_role_label": "NORMAL", "history_semantics": HISTORY_SEMANTICS,
        },
        {
            "game_date": "2026-08-02", "player": "A", "team": "CLE", "opponent": "DET",
            "projection": 5.10, "actual_strikeouts": 4, "confidence": "High", "data_quality": 90,
            "sim_5p": 55.0, "math_5p": 0.57, "opponent_k_pct": 24.0,
            "lineup_confirmed": False, "weather_delay_risk": "LOW", "leash_label": "TIGHT",
            "starter_role_label": "RAMPING", "history_semantics": HISTORY_SEMANTICS,
        },
        {
            "game_date": "2026-08-03", "player": "B", "team": "BOS", "opponent": "NYY",
            "projection": 4.70, "actual_strikeouts": 6, "confidence": "Medium", "data_quality": 70,
            "sim_4p": 0.61, "math_4p": 63.0, "opponent_k_pct": 21.0,
            "lineup_confirmed": True, "weather_delay_risk": "ELEVATED", "leash_label": "LONG",
            "starter_role_label": "NORMAL", "history_semantics": HISTORY_SEMANTICS,
        },
        {
            "game_date": "2026-08-04", "player": "Old", "team": "BOS", "opponent": "NYY",
            "projection": 6.2, "actual_strikeouts": 10, "confidence": "High", "data_quality": 100,
            "sim_6p": 0.9, "math_6p": 0.9, "history_semantics": "legacy",
        },
    ])


def test_probability_normalizes_percent_and_decimal() -> None:
    assert _prob(72.0) == 0.72
    assert _prob(0.72) == 0.72
    assert _prob(140.0) is None


def test_detail_uses_current_semantics_and_flags_crusher_events() -> None:
    detail = build_detail(_history())
    assert len(detail) == 3
    first = detail.iloc[0]
    assert first["Target_Label"] == "5+"
    assert bool(first["Ladder_Win"])
    assert bool(first["Crusher_Event"])
    assert abs(float(first["Raw_Path_Target_Probability"]) - 0.70) < 1e-12
    assert set(detail["Production_Authority"]) == {PRODUCTION_AUTHORITY}
    assert set(detail["Crusher_Version"]) == {CRUSHER_V2_VERSION}


def test_cohort_summary_is_descriptive_only() -> None:
    detail = pd.concat([build_detail(_history())] * 4, ignore_index=True)
    cohorts = build_cohort_summary(detail)
    assert not cohorts.empty
    assert set(cohorts["Production_Authority"]) == {"NONE"}
    assert cohorts["Report_Only"].astype(bool).all()


def test_coverage_reports_context_availability_without_live_authority() -> None:
    coverage = build_coverage(build_detail(_history()))
    assert int(coverage.iloc[0]["Resolved_Calls"]) == 3
    assert int(coverage.iloc[0]["Crusher_Events"]) == 2
    assert coverage.iloc[0]["Production_Authority"] == "NONE"
    assert bool(coverage.iloc[0]["Report_Only"])

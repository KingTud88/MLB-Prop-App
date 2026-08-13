from __future__ import annotations

import pandas as pd

from training.daily_role_shadow import attach_daily_role_shadow, normalize_daily_starter_log


def _daily_log() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-04-01", "2026-04-07", "2026-04-13", "2026-04-19", "2026-04-25", "2026-05-01"]),
        "games_started": [1, 1, 1, 1, 1, 1],
        "batters_faced": [18, 19, 20, 21, 22, 23],
        "pitches": [68, 72, 76, 82, 86, 90],
        "outs": [12, 12, 13, 14, 15, 16],
        "strikeouts": [4, 5, 5, 6, 6, 7],
    })


def _role_history() -> pd.DataFrame:
    dates = pd.date_range("2025-04-01", periods=40, freq="3D")
    return pd.DataFrame({
        "game_date": dates,
        "starter_role_label": ["RAMPING"] * 40,
        "projected_pitches": [80.0] * 40,
        "actual_pitches": [86.0] * 40,
        "projected_bf": [20.0] * 40,
        "actual_bf": [22.0] * 40,
        "projected_outs": [13.0] * 40,
        "actual_outs": [15.0] * 40,
    })


def test_normalization_maps_batters_faced_without_mutating_input() -> None:
    source = _daily_log()
    before = source.copy(deep=True)
    normalized = normalize_daily_starter_log(source)
    assert "bf" in normalized.columns
    assert normalized["bf"].tolist() == source["batters_faced"].tolist()
    pd.testing.assert_frame_equal(source, before)


def test_shadow_adds_diagnostics_without_changing_existing_projection_fields() -> None:
    record = {"projection": 6.2, "pitch_limit": 92.0, "confidence": "High", "player": "Test Pitcher"}
    result = attach_daily_role_shadow(record, _daily_log(), "2026-05-07", _role_history())
    for key, value in record.items():
        assert result[key] == value
    assert result["role_workload_mode"] == "shadow"
    assert result["role_workload_applied"] is False
    assert result["daily_role_shadow_version"] == "daily-role-shadow-v1"


def test_future_role_history_cannot_change_shadow_candidate() -> None:
    history = _role_history()
    base_record = {"projection": 5.8}
    first = attach_daily_role_shadow(base_record, _daily_log(), "2026-05-07", history)
    future = pd.concat([
        history,
        pd.DataFrame({
            "game_date": ["2026-06-01"],
            "starter_role_label": ["RAMPING"],
            "projected_pitches": [70.0], "actual_pitches": [112.0],
            "projected_bf": [15.0], "actual_bf": [35.0],
            "projected_outs": [8.0], "actual_outs": [24.0],
        }),
    ], ignore_index=True)
    second = attach_daily_role_shadow(base_record, _daily_log(), "2026-05-07", future)
    assert first["role_correction_pitches"] == second["role_correction_pitches"]
    assert first["role_correction_bf"] == second["role_correction_bf"]
    assert first["role_correction_outs"] == second["role_correction_outs"]

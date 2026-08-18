from __future__ import annotations

import pandas as pd

from training.pitch_mix_readiness_audit import (
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_field_audit,
    build_summary,
)


def test_current_style_archive_without_pitch_mix_inputs_is_blocked() -> None:
    projections = pd.DataFrame([{
        "game_pk": 1,
        "pitcher_id": 2,
        "projection": 5.1,
        "lineup_hash": "abc",
        "opponent_k_pct": 0.24,
    }])
    fields = build_field_audit(projections)
    summary = build_summary(projections, pd.DataFrame([{"game_pk": 1}]), fields).iloc[0]
    assert summary["Status"] == "PARTIAL_CAPTURE_SCHEMA"
    assert "PITCHER_PITCH_TYPES" in summary["Missing_Requirements"]
    assert "PITCHER_USAGE" in summary["Missing_Requirements"]
    assert "BATTER_PITCH_K_RATES" in summary["Missing_Requirements"]
    assert "PREGAME_CAPTURE_TIME" in summary["Missing_Requirements"]
    assert summary["Historical_Backfill_Allowed"] in (False, 0)


def test_completely_missing_schema_is_capture_required() -> None:
    projections = pd.DataFrame([{"game_pk": 1, "pitcher_id": 2}])
    fields = build_field_audit(projections)
    summary = build_summary(projections, pd.DataFrame(), fields).iloc[0]
    assert summary["Status"] == "BLOCKED_CAPTURE_REQUIRED"
    assert summary["Satisfied_Requirements"] == 0
    assert summary["Recommended_Action"] == "DESIGN_PREGAME_PITCH_MIX_CAPTURE_BEFORE_MODELING"


def test_complete_frozen_schema_is_ready_for_validation_design() -> None:
    projections = pd.DataFrame([{
        "pitch_mix_pitch_types": "FF|SL|CH",
        "pitch_mix_usage": "0.5|0.3|0.2",
        "pitch_mix_batter_k_rates": "frozen-json",
        "pitch_mix_captured_at_utc": "2026-08-18T12:00:00Z",
        "pitch_mix_lineup_hash": "abc123",
    }])
    fields = build_field_audit(projections)
    summary = build_summary(projections, pd.DataFrame(), fields).iloc[0]
    assert summary["Status"] == "READY_FOR_CAPTURED_VALIDATION"
    assert summary["Satisfied_Requirements"] == summary["Required_Requirements"]
    assert summary["Recommended_Action"] == "OPEN_REPORT_ONLY_PITCH_MIX_VALIDATION_DESIGN"


def test_contract_is_report_only() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert VERSION == "pitch-mix-readiness-v1-report-only"

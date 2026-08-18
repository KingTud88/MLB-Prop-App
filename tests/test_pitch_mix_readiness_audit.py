from __future__ import annotations

import pandas as pd

from training.pitch_mix_readiness_audit import (
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_field_audit,
    build_summary,
)


def projection(lineup_hash: str = "abc123") -> pd.DataFrame:
    return pd.DataFrame([{
        "game_pk": 1,
        "pitcher_id": 2,
        "projection": 5.1,
        "lineup_source": "CONFIRMED_LINEUP",
        "lineup_hash": lineup_hash,
        "opponent_k_pct": 0.24,
    }])


def pitch_context(eligible: bool = True) -> pd.DataFrame:
    return pd.DataFrame([{
        "game_pk": 1,
        "pitcher_id": 2,
        "arsenal_pitch_types": "FF|SL|CH",
        "arsenal_usage": '{"FF":0.5,"SL":0.3,"CH":0.2}',
        "arsenal_captured_at_utc": "2026-08-18T12:00:00Z",
        "audit_eligible": eligible,
    }])


def hand_context(lineup_hash: str = "abc123", eligible: bool = True) -> pd.DataFrame:
    return pd.DataFrame([{
        "game_pk": 1,
        "pitcher_id": 2,
        "lineup_source": "CONFIRMED_LINEUP",
        "lineup_hash": lineup_hash,
        "audit_eligible": eligible,
    }])


def whiff_context(
    lineup_hash: str = "abc123",
    eligible: bool = True,
    source: str = "CONFIRMED_LINEUP",
) -> pd.DataFrame:
    return pd.DataFrame([{
        "game_pk": 1,
        "pitcher_id": 2,
        "lineup_source": source,
        "lineup_hash": lineup_hash,
        "batter_pitch_whiff_rates_json": '{"101":{"FF":0.25}}',
        "whiff_context_captured_at_utc": "2026-08-18T12:05:00Z",
        "metric_definition": "WHIFF_PER_SWING_BY_BATTER_AND_PITCH_TYPE",
        "audit_eligible": eligible,
    }])


def test_current_style_archive_without_pitch_mix_inputs_is_partial() -> None:
    projections = projection()
    fields = build_field_audit(projections)
    summary = build_summary(projections, hand_context(), fields).iloc[0]
    assert summary["Status"] == "PARTIAL_CAPTURE_SCHEMA"
    assert summary["Satisfied_Requirements"] == 1
    assert "PITCHER_PITCH_TYPES" in summary["Missing_Requirements"]
    assert "PITCHER_USAGE" in summary["Missing_Requirements"]
    assert "BATTER_PITCH_WHIFF_RATES" in summary["Missing_Requirements"]
    assert "PREGAME_CAPTURE_TIME" in summary["Missing_Requirements"]
    assert summary["Historical_Backfill_Allowed"] in (False, 0)


def test_completely_missing_schema_is_capture_required() -> None:
    projections = pd.DataFrame([{"game_pk": 1, "pitcher_id": 2}])
    fields = build_field_audit(projections)
    summary = build_summary(projections, pd.DataFrame(), fields).iloc[0]
    assert summary["Status"] == "BLOCKED_CAPTURE_REQUIRED"
    assert summary["Satisfied_Requirements"] == 0
    assert summary["Recommended_Action"] == "COMPLETE_PREGAME_PITCH_MIX_CAPTURE_BEFORE_MODELING"


def test_eligible_pitcher_context_stays_four_of_five_without_whiff_context() -> None:
    projections = projection()
    pitch = pitch_context()
    hand = hand_context()
    fields = build_field_audit(projections, pitch, pd.DataFrame(), hand)
    summary = build_summary(projections, hand, fields, pitch, pd.DataFrame()).iloc[0]
    assert summary["Status"] == "PITCHER_CONTEXT_READY_BATTER_CONTEXT_MISSING"
    assert summary["Satisfied_Requirements"] == 4
    assert summary["Missing_Requirements"] == "BATTER_PITCH_WHIFF_RATES"
    assert summary["Pitch_Arsenal_Rows"] == 1
    assert summary["Pitch_Arsenal_Eligible_Rows"] == 1
    assert summary["Recommended_Action"] == "CAPTURE_BATTER_PITCH_WHIFF_CONTEXT"
    source = fields.set_index("Requirement").loc["PITCHER_USAGE", "Matched_Source"]
    assert source == "pitch_arsenal_context"


def test_ineligible_pitcher_context_does_not_satisfy_capture_requirements() -> None:
    projections = projection()
    pitch = pitch_context(False)
    hand = hand_context()
    fields = build_field_audit(projections, pitch, pd.DataFrame(), hand)
    assert fields.set_index("Requirement").loc["PITCHER_PITCH_TYPES", "Satisfied"] in (False, 0)
    summary = build_summary(projections, hand, fields, pitch, pd.DataFrame()).iloc[0]
    assert summary["Satisfied_Requirements"] == 1
    assert summary["Pitch_Arsenal_Eligible_Rows"] == 0


def test_stale_active_roster_whiff_context_cannot_satisfy_confirmed_lineup() -> None:
    projections = projection("new-confirmed-hash")
    pitch = pitch_context()
    hand = hand_context("new-confirmed-hash")
    stale_whiff = whiff_context("", source="ACTIVE_ROSTER")
    fields = build_field_audit(projections, pitch, stale_whiff, hand)
    summary = build_summary(projections, hand, fields, pitch, stale_whiff).iloc[0]
    assert summary["Satisfied_Requirements"] == 4
    assert summary["Missing_Requirements"] == "BATTER_PITCH_WHIFF_RATES"
    assert summary["Batter_Whiff_Eligible_Rows"] == 1
    assert summary["Batter_Whiff_Current_Lineage_Rows"] == 0


def test_matching_current_lineage_whiff_context_moves_readiness_to_five_of_five() -> None:
    projections = projection()
    pitch = pitch_context()
    hand = hand_context()
    whiff = whiff_context()
    fields = build_field_audit(projections, pitch, whiff, hand)
    summary = build_summary(projections, hand, fields, pitch, whiff).iloc[0]
    assert summary["Status"] == "READY_FOR_REPORT_ONLY_VALIDATION_DESIGN"
    assert summary["Satisfied_Requirements"] == 5
    assert summary["Required_Requirements"] == 5
    assert summary["Missing_Requirements"] == ""
    assert summary["Batter_Whiff_Rows"] == 1
    assert summary["Batter_Whiff_Eligible_Rows"] == 1
    assert summary["Batter_Whiff_Current_Lineage_Rows"] == 1
    assert summary["Recommended_Action"] == "OPEN_REPORT_ONLY_PITCH_MIX_VALIDATION_DESIGN"
    source = fields.set_index("Requirement").loc["BATTER_PITCH_WHIFF_RATES", "Matched_Source"]
    assert source == "batter_pitch_whiff_context"


def test_ineligible_whiff_context_does_not_satisfy_readiness() -> None:
    projections = projection()
    pitch = pitch_context()
    hand = hand_context()
    whiff = whiff_context(eligible=False)
    fields = build_field_audit(projections, pitch, whiff, hand)
    summary = build_summary(projections, hand, fields, pitch, whiff).iloc[0]
    assert summary["Satisfied_Requirements"] == 4
    assert summary["Batter_Whiff_Eligible_Rows"] == 0
    assert summary["Batter_Whiff_Current_Lineage_Rows"] == 0


def test_contract_is_report_only() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert VERSION == "pitch-mix-readiness-v3-report-only"

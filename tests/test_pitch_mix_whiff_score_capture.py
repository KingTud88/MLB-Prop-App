from __future__ import annotations

import json

import pandas as pd
import pytest

from training.pitch_mix_whiff_score_capture import (
    FORMULA_ID,
    NO_PROJECTION_ADJUSTMENT,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_score_frame,
    merge_score_log,
    score_one_context,
)


def arsenal(eligible: bool = True) -> pd.DataFrame:
    return pd.DataFrame([{
        "game_pk": 1,
        "pitcher_id": 2,
        "arsenal_usage": '{"FF":0.6,"SL":0.4}',
        "arsenal_captured_at_utc": "2026-08-18T05:00:00Z",
        "audit_eligible": eligible,
    }])


def hand(lineup_source: str = "CONFIRMED_LINEUP", lineup_hash: str = "abc", eligible: bool = True) -> pd.DataFrame:
    return pd.DataFrame([{
        "game_pk": 1,
        "pitcher_id": 2,
        "lineup_source": lineup_source,
        "lineup_hash": lineup_hash,
        "audit_eligible": eligible,
    }])


def whiff(
    lineup_source: str = "CONFIRMED_LINEUP",
    lineup_hash: str = "abc",
    eligible: bool = True,
    five_batters: bool = True,
) -> pd.DataFrame:
    rates = {
        "101": {"FF": 0.3, "SL": 0.5},
        "102": {"FF": 0.2, "SL": 0.4},
    }
    counts = {
        "101": {"FF": {"swings": 10, "whiffs": 3}, "SL": {"swings": 10, "whiffs": 5}},
        "102": {"FF": {"swings": 20, "whiffs": 4}, "SL": {"swings": 20, "whiffs": 8}},
    }
    if five_batters:
        for batter_id in ("103", "104", "105"):
            rates[batter_id] = {"FF": 0.25, "SL": 0.25}
            counts[batter_id] = {
                "FF": {"swings": 10, "whiffs": 2},
                "SL": {"swings": 10, "whiffs": 3},
            }
    return pd.DataFrame([{
        "game_date": "2026-08-18",
        "game_pk": 1,
        "pitcher_id": 2,
        "player": "Pitcher",
        "team": "AAA",
        "opponent": "BBB",
        "lineup_source": lineup_source,
        "lineup_hash": lineup_hash,
        "whiff_context_captured_at_utc": "2026-08-18T05:05:00Z",
        "batters_requested": len(rates),
        "batter_pitch_whiff_rates_json": json.dumps(rates),
        "batter_pitch_counts_json": json.dumps(counts),
        "audit_eligible": eligible,
    }])


def score_frame(lineup_source: str = "ACTIVE_ROSTER", lineup_hash: str = "", delta: float = 0.01) -> pd.DataFrame:
    row = score_one_context(whiff(lineup_source, lineup_hash).iloc[0], arsenal().iloc[0])
    row["pitch_mix_whiff_delta"] = delta
    return pd.DataFrame([row])


def test_confirmed_lineup_uses_equal_batter_weighting() -> None:
    row = score_one_context(whiff(five_batters=False).iloc[0], arsenal().iloc[0])
    assert row["batter_weighting"] == "EQUAL_CONFIRMED_LINEUP"
    assert row["pitch_mix_whiff_score"] == pytest.approx(0.33)
    assert row["baseline_whiff_rate"] == pytest.approx(0.35)
    assert row["pitch_mix_whiff_delta"] == pytest.approx(-0.02)
    assert row["weighted_arsenal_usage_coverage"] == pytest.approx(1.0)


def test_active_roster_uses_recent_swing_weighting() -> None:
    row = score_one_context(
        whiff("ACTIVE_ROSTER", "", five_batters=False).iloc[0],
        arsenal().iloc[0],
    )
    assert row["batter_weighting"] == "RECENT_SWINGS_ACTIVE_ROSTER"
    assert row["pitch_mix_whiff_score"] == pytest.approx((0.38 * 20 + 0.28 * 40) / 60)
    assert row["baseline_whiff_rate"] == pytest.approx((0.4 * 20 + 0.3 * 40) / 60)
    assert row["pitch_mix_whiff_delta"] == pytest.approx(-0.02)


def test_missing_pitch_types_are_coverage_gated_then_renormalized() -> None:
    whiff_row = whiff(five_batters=False).iloc[0].copy()
    whiff_row["batter_pitch_whiff_rates_json"] = json.dumps({
        "101": {"FF": 0.30},
        "102": {"SL": 0.40},
    })
    row = score_one_context(whiff_row, arsenal().iloc[0])
    payload = json.loads(row["batter_scores_json"])
    assert payload["101"]["arsenal_usage_coverage"] == pytest.approx(0.6)
    assert payload["101"]["pitch_mix_whiff"] == pytest.approx(0.30)
    assert "102" not in payload  # SL alone covers only 40% of the pitcher's arsenal.


def test_stale_lineup_context_is_not_scored() -> None:
    result = build_score_frame(
        whiff("ACTIVE_ROSTER", ""),
        arsenal(),
        hand("CONFIRMED_LINEUP", "new-hash"),
    )
    assert result.empty


def test_ineligible_source_context_is_not_scored() -> None:
    result = build_score_frame(whiff(eligible=False), arsenal(), hand())
    assert result.empty
    result = build_score_frame(whiff(), arsenal(eligible=False), hand())
    assert result.empty


def test_five_batter_minimum_is_capture_quality_only() -> None:
    result = build_score_frame(whiff(five_batters=False), arsenal(), hand())
    assert len(result) == 1
    row = result.iloc[0]
    assert row["score_batters"] == 2
    assert row["audit_eligible"] in (False, 0)
    assert "need at least 5" in row["reason"]


def test_matching_current_context_produces_report_only_score() -> None:
    result = build_score_frame(whiff(), arsenal(), hand())
    assert len(result) == 1
    row = result.iloc[0]
    assert row["audit_eligible"] in (True, 1)
    assert row["score_batters"] == 5
    assert row["formula_id"] == FORMULA_ID
    assert row["production_authority"] == "NONE"
    assert row["no_projection_adjustment"] in (True, 1)


def test_existing_frozen_score_survives_when_current_lineage_changes() -> None:
    existing = score_frame("ACTIVE_ROSTER", "", delta=0.01)
    current = score_frame("CONFIRMED_LINEUP", "new-hash", delta=0.02)
    merged = merge_score_log(existing, current)
    assert len(merged) == 2
    assert merged.iloc[0]["lineup_source"] == "ACTIVE_ROSTER"
    assert merged.iloc[0]["pitch_mix_whiff_delta"] == pytest.approx(0.01)
    assert merged.iloc[1]["lineup_source"] == "CONFIRMED_LINEUP"


def test_same_context_rerun_cannot_overwrite_first_frozen_score() -> None:
    existing = score_frame("ACTIVE_ROSTER", "", delta=0.01)
    rerun = score_frame("ACTIVE_ROSTER", "", delta=0.99)
    merged = merge_score_log(existing, rerun)
    assert len(merged) == 1
    assert merged.iloc[0]["pitch_mix_whiff_delta"] == pytest.approx(0.01)


def test_empty_current_frame_does_not_erase_existing_frozen_scores() -> None:
    existing = score_frame("ACTIVE_ROSTER", "", delta=-0.03)
    merged = merge_score_log(existing, pd.DataFrame())
    assert len(merged) == 1
    assert merged.iloc[0]["pitch_mix_whiff_delta"] == pytest.approx(-0.03)


def test_contract_is_report_only_and_preregistered() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_PROJECTION_ADJUSTMENT is True
    assert VERSION == "pitch-mix-whiff-score-v1-preregistered-report-only"

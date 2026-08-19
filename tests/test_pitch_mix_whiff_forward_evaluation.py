from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from training.pitch_mix_whiff_forward_evaluation import (
    MIN_OPPONENTS,
    MIN_RESOLVED_DAYS,
    MIN_RESOLVED_STARTS,
    NO_PROJECTION_ADJUSTMENT,
    PRIMARY_METRIC,
    PRODUCTION_AUTHORITY,
    PREREGISTERED_GAME_DATE,
    REPORT_ONLY,
    VERSION,
    build_detail,
    build_gate,
    build_summary,
)


def score(
    *,
    game_pk: int = 1,
    pitcher_id: int = 2,
    game_date: str = "2026-08-18",
    source: str = "CONFIRMED_LINEUP",
    lineup_hash: str = "abc",
    delta: float = 0.02,
    eligible: bool = True,
    captured_at: str = "2026-08-18T12:00:00Z",
) -> pd.DataFrame:
    return pd.DataFrame([{
        "game_date": game_date,
        "game_pk": game_pk,
        "pitcher_id": pitcher_id,
        "player": f"Pitcher {pitcher_id}",
        "team": "AAA",
        "opponent": "BBB",
        "lineup_source": source,
        "lineup_hash": lineup_hash,
        "whiff_context_captured_at_utc": captured_at,
        "pitch_mix_whiff_score": 0.27,
        "baseline_whiff_rate": 0.25,
        "pitch_mix_whiff_delta": delta,
        "weighted_arsenal_usage_coverage": 0.80,
        "score_batters": 9,
        "formula_id": "ARSENAL_USAGE_X_BATTER_WHIFF_V1",
        "score_version": "pitch-mix-whiff-score-v1-preregistered-report-only",
        "audit_eligible": eligible,
        "no_projection_adjustment": True,
    }])


def projection_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "game_pk": 1,
            "pitcher_id": 2,
            "lineup_source": "ACTIVE_ROSTER",
            "lineup_hash": "",
            "captured_at_utc": "2026-08-18T10:00:00Z",
            "projection": 4.0,
            "actual_strikeouts": 99,
            "resolved_at_utc": "2026-08-19T04:00:00Z",
        },
        {
            "game_pk": 1,
            "pitcher_id": 2,
            "lineup_source": "CONFIRMED_LINEUP",
            "lineup_hash": "abc",
            "captured_at_utc": "2026-08-18T11:00:00Z",
            "projection": 5.0,
            "actual_strikeouts": 7,
            "resolved_at_utc": "2026-08-19T04:00:00Z",
        },
        {
            "game_pk": 1,
            "pitcher_id": 2,
            "lineup_source": "CONFIRMED_LINEUP",
            "lineup_hash": "abc",
            "captured_at_utc": "2026-08-18T13:00:00Z",
            "projection": 6.0,
            "actual_strikeouts": 7,
            "resolved_at_utc": "2026-08-19T04:00:00Z",
        },
    ])


def mutated_projection_row() -> pd.DataFrame:
    return pd.DataFrame([{
        "game_pk": 1,
        "pitcher_id": 2,
        "lineup_source": "CONFIRMED_LINEUP",
        "lineup_hash": "abc",
        "captured_at_utc": "2026-08-18T13:00:00Z",
        "projection": 5.5,
        "lineup_preconfirm_projection": 4.25,
        "actual_strikeouts": 7,
        "resolved_at_utc": "2026-08-19T04:00:00Z",
    }])


def active_whiff_context(*, eligible: bool = True) -> pd.DataFrame:
    return pd.DataFrame([{
        "game_pk": 1,
        "pitcher_id": 2,
        "lineup_source": "ACTIVE_ROSTER",
        "lineup_hash": "",
        "projection_captured_at_utc": "2026-08-18T10:00:00Z",
        "whiff_context_captured_at_utc": "2026-08-18T12:00:00Z",
        "audit_eligible": eligible,
    }])


def test_exact_lineup_lineage_and_pre_score_projection_are_used() -> None:
    detail = build_detail(score(), projection_rows())
    assert len(detail) == 1
    row = detail.iloc[0]
    assert row["projection"] == 5.0
    assert row["actual_strikeouts"] == 7.0
    assert row["k_residual"] == 2.0
    assert row["projection_captured_at_utc"] == "2026-08-18T11:00:00Z"


def test_stale_or_future_projection_state_is_not_substituted() -> None:
    projections = projection_rows().loc[
        lambda frame: ~(
            frame["lineup_source"].eq("CONFIRMED_LINEUP")
            & frame["captured_at_utc"].eq("2026-08-18T11:00:00Z")
        )
    ]
    detail = build_detail(score(), projections)
    assert detail.empty


def test_active_roster_score_uses_frozen_preconfirm_projection_with_exact_whiff_proof() -> None:
    active_score = score(source="ACTIVE_ROSTER", lineup_hash="")
    detail = build_detail(active_score, mutated_projection_row(), active_whiff_context())
    assert len(detail) == 1
    row = detail.iloc[0]
    assert row["lineup_source"] == "ACTIVE_ROSTER"
    assert row["projection"] == pytest.approx(4.25)
    assert row["projection_captured_at_utc"] == "2026-08-18T10:00:00+00:00"
    assert row["actual_strikeouts"] == 7.0
    assert row["k_residual"] == pytest.approx(2.75)


def test_active_roster_preconfirm_fallback_requires_eligible_exact_whiff_proof() -> None:
    active_score = score(source="ACTIVE_ROSTER", lineup_hash="")
    assert build_detail(active_score, mutated_projection_row()).empty
    assert build_detail(active_score, mutated_projection_row(), active_whiff_context(eligible=False)).empty
    wrong_capture = active_whiff_context()
    wrong_capture.loc[0, "whiff_context_captured_at_utc"] = "2026-08-18T12:01:00Z"
    assert build_detail(active_score, mutated_projection_row(), wrong_capture).empty


def test_confirmed_hash_mismatch_cannot_use_active_roster_preconfirm_fallback() -> None:
    confirmed_score = score(source="CONFIRMED_LINEUP", lineup_hash="different")
    assert build_detail(confirmed_score, mutated_projection_row(), active_whiff_context()).empty


def test_latest_score_context_is_only_context_evaluated_per_start() -> None:
    active = score(source="ACTIVE_ROSTER", lineup_hash="", captured_at="2026-08-18T10:30:00Z", delta=-0.04)
    confirmed = score(source="CONFIRMED_LINEUP", lineup_hash="abc", captured_at="2026-08-18T12:00:00Z", delta=0.03)
    scores = pd.concat([active, confirmed], ignore_index=True)
    detail = build_detail(scores, projection_rows())
    assert len(detail) == 1
    assert detail.iloc[0]["lineup_source"] == "CONFIRMED_LINEUP"
    assert detail.iloc[0]["pitch_mix_whiff_delta"] == pytest.approx(0.03)


def test_later_ineligible_score_context_blocks_stale_eligible_context() -> None:
    active = score(source="ACTIVE_ROSTER", lineup_hash="", captured_at="2026-08-18T10:30:00Z", eligible=True)
    confirmed = score(source="CONFIRMED_LINEUP", lineup_hash="abc", captured_at="2026-08-18T12:00:00Z", eligible=False)
    scores = pd.concat([active, confirmed], ignore_index=True)
    assert build_detail(scores, projection_rows(), active_whiff_context()).empty


def test_only_preregistered_eligible_score_rows_are_evaluated() -> None:
    before = score(game_date="2026-08-17")
    ineligible = score(game_pk=2, pitcher_id=3, eligible=False)
    scores = pd.concat([before, ineligible], ignore_index=True)
    assert build_detail(scores, projection_rows()).empty


def test_unresolved_projection_is_not_evaluated() -> None:
    projections = projection_rows().copy()
    projections.loc[projections["captured_at_utc"].eq("2026-08-18T11:00:00Z"), "actual_strikeouts"] = np.nan
    assert build_detail(score(), projections).empty


def synthetic_detail(n: int = 8) -> pd.DataFrame:
    rows = []
    for idx in range(n):
        delta = -0.04 + idx * 0.01
        residual = -2.0 + idx * 0.5
        rows.append({
            "game_date": f"2026-08-{18 + idx % 4:02d}",
            "opponent": f"OPP{idx % 5}",
            "pitch_mix_whiff_delta": delta,
            "k_residual": residual,
            "abs_k_residual": abs(residual),
        })
    return pd.DataFrame(rows)


def test_primary_metric_is_preregistered_rank_association() -> None:
    summary = build_summary(synthetic_detail()).iloc[0]
    assert summary["Spearman_ScoreDelta_KResidual"] == pytest.approx(1.0)
    assert summary["Pearson_ScoreDelta_KResidual"] == pytest.approx(1.0)
    assert summary["TopMinusBottom_Residual"] > 0
    assert summary["Primary_Metric"] == PRIMARY_METRIC


def test_early_gate_only_says_learning_not_supported_or_hurting() -> None:
    gate = build_gate(build_summary(synthetic_detail())).iloc[0]
    assert gate["Status"] == "LEARNING"
    assert gate["Resolved_Starts"] == 8
    assert "SUPPORTED" not in gate["Status"]
    assert "HURTING" not in gate["Status"]


def test_mature_gate_is_manual_review_only() -> None:
    rows = []
    for idx in range(MIN_RESOLVED_STARTS):
        rows.append({
            "game_date": f"2026-09-{1 + idx % MIN_RESOLVED_DAYS:02d}",
            "opponent": f"OPP{idx % MIN_OPPONENTS}",
            "pitch_mix_whiff_delta": -0.03 + idx * 0.001,
            "k_residual": -1.0 + idx * 0.03,
            "abs_k_residual": abs(-1.0 + idx * 0.03),
        })
    gate = build_gate(build_summary(pd.DataFrame(rows))).iloc[0]
    assert gate["Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert gate["Recommended_Action"] == "REVIEW_ASSOCIATION_ONLY_DO_NOT_MAP_TO_PROJECTION_WITHOUT_NEW_EXPLICIT_RESEARCH"
    assert gate["Production_Authority"] == "NONE"


def test_contract_is_forward_report_only_no_projection_adjustment() -> None:
    assert PREREGISTERED_GAME_DATE == "2026-08-18"
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_PROJECTION_ADJUSTMENT is True
    assert VERSION == "pitch-mix-whiff-forward-eval-v1-preregistered-report-only"

from __future__ import annotations

import pandas as pd

from training.umpire_k_live_validation import (
    EXPECTED_SOURCE,
    build_detail,
    build_segment_summary,
    evaluate_gate,
    summarize,
)


def _row(
    day: int,
    *,
    umpire_id: int = 900,
    source: str = EXPECTED_SOURCE,
    capture_offset_hours: float = -2.0,
    resolved_offset_hours: float = 4.0,
    prior_games: int = 25,
    status: str = "AUDITABLE",
    factor: float = 1.04,
    projection: float = 5.0,
    actual: float = 6.0,
) -> dict[str, object]:
    game_time = pd.Timestamp("2026-06-01T23:00:00Z") + pd.Timedelta(day, unit="D")
    return {
        "game_date": game_time.date().isoformat(),
        "game_pk": 100000 + day,
        "pitcher_id": 200000 + day,
        "player": f"Pitcher {day}",
        "team": "CLE",
        "opponent": f"OPP{day % 20:02d}",
        "game_time": game_time.isoformat(),
        "umpire_id": umpire_id,
        "umpire_name": f"Ump {umpire_id}",
        "umpire_source": source,
        "umpire_captured_at_utc": (game_time + pd.Timedelta(capture_offset_hours, unit="h")).isoformat(),
        "umpire_prior_games": prior_games,
        "umpire_prior_bf": prior_games * 72,
        "umpire_candidate_status": status,
        "umpire_candidate_version": "umpire-k-v1-report-only",
        "umpire_k_factor_candidate": factor,
        "projection": projection,
        "actual_strikeouts": actual,
        "resolved_at_utc": (game_time + pd.Timedelta(resolved_offset_hours, unit="h")).isoformat(),
        "data_quality": 82,
        "starter_history_games": 12,
    }


def test_post_start_capture_cannot_be_authentic() -> None:
    detail = build_detail(pd.DataFrame([_row(0, capture_offset_hours=1.0)]))
    row = detail.iloc[0]
    assert row["Lineage"] == "POST_START_CAPTURE"
    assert bool(row["Authentic_Pregame_Candidate"]) is False
    assert bool(row["OOS_Eligible"]) is False


def test_wrong_source_and_learning_candidate_are_rejected() -> None:
    detail = build_detail(pd.DataFrame([
        _row(0, source="HISTORICAL_BACKFILL"),
        _row(1, status="LEARNING", prior_games=10),
    ]))
    assert detail.iloc[0]["Lineage"] == "SOURCE_MISMATCH"
    assert not detail["Authentic_Pregame_Candidate"].any()


def test_resolution_must_happen_after_first_pitch() -> None:
    detail = build_detail(pd.DataFrame([_row(0, resolved_offset_hours=-1.0)]))
    row = detail.iloc[0]
    assert row["Outcome_Lineage"] == "INVALID_RESOLUTION_TIME"
    assert bool(row["Authentic_Pregame_Candidate"]) is False


def test_small_sample_stays_learning_and_never_has_authority() -> None:
    rows = [_row(i, umpire_id=900 + i % 5) for i in range(12)]
    summary = summarize(build_detail(pd.DataFrame(rows))).iloc[0]
    assert summary["Status"] == "LEARNING"
    assert int(summary["OOS_Eligible_Starts"]) == 12
    assert summary["Production_Authority"] == "NONE"


def test_strong_synthetic_signal_only_becomes_manual_review_ready() -> None:
    rows = []
    for i in range(80):
        rows.append(_row(
            i,
            umpire_id=900 + i % 18,
            factor=1.06,
            projection=5.0,
            actual=6.0,
        ))
    gate = evaluate_gate(build_detail(pd.DataFrame(rows))).iloc[0]
    assert gate["Evidence_Status"] == "STRONG EVIDENCE"
    assert bool(gate["Manual_Review_Ready"]) is True
    assert gate["Recommended_Action"] == "MANUAL_REVIEW_READY"
    assert gate["Production_Authority"] == "NONE"
    assert bool(gate["Report_Only"]) is True


def test_segment_report_exposes_lineage_factor_and_prior_sample_dimensions() -> None:
    detail = build_detail(pd.DataFrame([_row(0), _row(1, factor=.97, actual=4.0)]))
    segments = build_segment_summary(detail)
    dimensions = set(segments["Dimension"])
    assert "LINEAGE" in dimensions
    assert "FACTOR DIRECTION" in dimensions
    assert "FACTOR DELTA BAND" in dimensions
    assert "PRIOR UMPIRE GAMES BAND" in dimensions
    assert set(segments["Production_Authority"]) == {"NONE"}

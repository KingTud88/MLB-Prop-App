from __future__ import annotations

import pandas as pd

from training.lineup_k_walkforward import (
    LINEUP_CONFIRMED,
    MIN_PRIOR_PAIRED,
    build_oos_detail,
    build_segment_summary,
    evaluate_gate,
    summarize_oos,
)


def _row(
    day: int,
    *,
    opponent: str | None = None,
    capture_offset_hours: float = -2.0,
    resolved_offset_hours: float = 4.0,
    source: str = LINEUP_CONFIRMED,
    confirmed: bool = True,
    batters: int = 9,
    fingerprint: str = "abcdef1234567890",
    pre: float = 5.0,
    post: float = 5.5,
    actual: float = 6.0,
) -> dict[str, object]:
    game_time = pd.Timestamp("2026-06-01T23:00:00Z") + pd.Timedelta(day, unit="D")
    return {
        "game_date": game_time.date().isoformat(),
        "game_pk": 100000 + day,
        "pitcher_id": 200000 + day,
        "player": f"Pitcher {day}",
        "team": "CLE",
        "opponent": opponent or f"OPP{day % 20:02d}",
        "game_time": game_time.isoformat(),
        "lineup_source": source,
        "lineup_confirmed": confirmed,
        "lineup_batters": batters,
        "lineup_hash": fingerprint,
        "lineup_captured_at_utc": (game_time + pd.Timedelta(capture_offset_hours, unit="h")).isoformat(),
        "lineup_preconfirm_projection": pre,
        "projection": post,
        "lineup_projection_delta": post - pre,
        "lineup_opponent_k_delta": 0.8,
        "actual_strikeouts": actual,
        "resolved_at_utc": (game_time + pd.Timedelta(resolved_offset_hours, unit="h")).isoformat(),
        "data_quality": 82,
        "starter_history_games": 12,
    }


def test_post_start_lineup_capture_never_becomes_authentic_or_oos() -> None:
    detail = build_oos_detail(pd.DataFrame([_row(0, capture_offset_hours=1.0)]))
    row = detail.iloc[0]
    assert row["Lineage"] == "POST_START_CAPTURE"
    assert bool(row["Authentic_Pregame_Pair"]) is False
    assert bool(row["OOS_Eligible"]) is False


def test_prior_outcomes_must_be_resolved_before_target_lineup_capture() -> None:
    priors = [_row(i, resolved_offset_hours=900.0) for i in range(MIN_PRIOR_PAIRED)]
    target = _row(MIN_PRIOR_PAIRED + 1)
    detail = build_oos_detail(pd.DataFrame(priors + [target]))
    target_row = detail.loc[detail["game_pk"].eq(target["game_pk"])].iloc[0]
    assert int(target_row["Prior_Paired_Starts"]) == 0
    assert bool(target_row["OOS_Eligible"]) is False


def test_future_games_cannot_count_as_prior_evidence() -> None:
    priors = [_row(i) for i in range(MIN_PRIOR_PAIRED)]
    target = _row(MIN_PRIOR_PAIRED + 1)
    future = _row(MIN_PRIOR_PAIRED + 20)
    detail = build_oos_detail(pd.DataFrame(priors + [target, future]))
    target_row = detail.loc[detail["game_pk"].eq(target["game_pk"])].iloc[0]
    assert int(target_row["Prior_Paired_Starts"]) == MIN_PRIOR_PAIRED


def test_lineage_requires_confirmed_source_full_lineup_and_fingerprint() -> None:
    frame = pd.DataFrame([
        _row(0, source="ACTIVE_ROSTER"),
        _row(1, batters=8),
        _row(2, fingerprint=""),
        _row(3, confirmed=False),
    ])
    detail = build_oos_detail(frame)
    assert detail["Lineage"].tolist() == [
        "SOURCE_MISMATCH",
        "INCOMPLETE_LINEUP",
        "MISSING_FINGERPRINT",
        "UNCONFIRMED",
    ]
    assert not detail["Authentic_Pregame_Pair"].any()


def test_small_time_concentrated_sample_stays_learning() -> None:
    warmup = [_row(i) for i in range(MIN_PRIOR_PAIRED)]
    oos = [_row(MIN_PRIOR_PAIRED + i) for i in range(1, 6)]
    summary = summarize_oos(build_oos_detail(pd.DataFrame(warmup + oos))).iloc[0]
    assert summary["Status"] == "LEARNING"
    assert int(summary["OOS_Paired_Starts"]) == 5
    assert summary["Production_Authority"] == "NONE"


def test_strong_synthetic_evidence_is_manual_review_only() -> None:
    warmup = [_row(i, pre=5.0, post=5.5, actual=6.0) for i in range(MIN_PRIOR_PAIRED)]
    oos = [
        _row(
            MIN_PRIOR_PAIRED + i,
            opponent=f"OPP{i % 18:02d}",
            pre=5.0,
            post=5.5,
            actual=6.0,
        )
        for i in range(1, 81)
    ]
    gate = evaluate_gate(build_oos_detail(pd.DataFrame(warmup + oos))).iloc[0]
    assert gate["Evidence_Status"] == "STRONG EVIDENCE"
    assert bool(gate["Manual_Review_Ready"]) is True
    assert gate["Recommended_Action"] == "MANUAL_REVIEW_READY"
    assert gate["Production_Authority"] == "NONE"
    assert bool(gate["Report_Only"]) is True


def test_segment_report_exposes_lineage_and_projection_delta_dimensions() -> None:
    frame = pd.DataFrame([_row(0), _row(1, post=4.5, actual=4.0)])
    segments = build_segment_summary(build_oos_detail(frame))
    dimensions = set(segments["Dimension"])
    assert "LINEAGE" in dimensions
    assert "PROJECTION DELTA DIRECTION" in dimensions
    assert "PROJECTION DELTA BAND" in dimensions
    assert set(segments["Production_Authority"]) == {"NONE"}

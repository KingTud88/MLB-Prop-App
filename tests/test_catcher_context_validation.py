from __future__ import annotations

import pandas as pd

from training.catcher_context_validation import (
    MAX_FACTOR_DELTA,
    PRODUCTION_AUTHORITY,
    build_detail,
    evaluate_gate,
)


def _projection(
    game_pk: int,
    game_date: str,
    game_time: str,
    captured: str,
    actual: float,
    resolved: str,
    *,
    pitcher_id: int | None = None,
    projection: float = 5.0,
) -> dict[str, object]:
    return {
        "game_pk": game_pk,
        "game_date": game_date,
        "game_time": game_time,
        "captured_at_utc": captured,
        "pitcher_id": pitcher_id or (1000 + game_pk),
        "player": f"Pitcher {game_pk}",
        "team": "AAA",
        "projection": projection,
        "actual_strikeouts": actual,
        "resolved_at_utc": resolved,
        "actual_batters_faced": 24,
        "data_quality": 80,
        "starter_history_games": 8,
    }


def _catcher(
    game_pk: int,
    game_date: str,
    captured: str,
    *,
    catcher_id: int = 77,
    pitcher_id: int | None = None,
) -> dict[str, object]:
    return {
        "game_pk": game_pk,
        "game_date": game_date,
        "pitcher_id": pitcher_id or (1000 + game_pk),
        "player": f"Pitcher {game_pk}",
        "team": "AAA",
        "catcher_id": catcher_id,
        "catcher_name": "Test Catcher",
        "catcher_source": "MLB_POSTED_LINEUP",
        "catcher_confirmed": True,
        "catcher_captured_at_utc": captured,
        "catcher_factor": 1.0,
        "candidate_authority": "REPORT_ONLY",
    }


def test_target_requires_pregame_catcher_capture_but_historical_backfill_can_be_prior_if_already_known() -> None:
    projections = pd.DataFrame([
        _projection(1, "2026-08-01", "2026-08-01T20:00:00Z", "2026-08-01T12:00:00Z", 7, "2026-08-01T23:00:00Z"),
        _projection(2, "2026-08-02", "2026-08-02T20:00:00Z", "2026-08-02T12:00:00Z", 6, "2026-08-02T23:00:00Z"),
    ])
    catchers = pd.DataFrame([
        _catcher(1, "2026-08-01", "2026-08-02T10:00:00Z"),
        _catcher(2, "2026-08-02", "2026-08-02T18:00:00Z"),
    ])
    detail = build_detail(projections, catchers).set_index("Game_PK")
    assert detail.loc[1, "Lineage"] == "POST_START_BACKFILL"
    assert bool(detail.loc[1, "OOS_Eligible"]) is False
    assert detail.loc[2, "Lineage"] == "PRE_GAME_CAPTURE"
    assert bool(detail.loc[2, "OOS_Eligible"]) is True
    assert int(detail.loc[2, "Prior_Catcher_Starts"]) == 1
    assert int(detail.loc[2, "Prior_Backfilled_Starts"]) == 1


def test_prior_outcome_must_have_been_resolved_before_target_capture() -> None:
    projections = pd.DataFrame([
        _projection(1, "2026-08-01", "2026-08-01T20:00:00Z", "2026-08-01T12:00:00Z", 7, "2026-08-02T19:00:00Z"),
        _projection(2, "2026-08-02", "2026-08-02T20:00:00Z", "2026-08-02T12:00:00Z", 6, "2026-08-02T23:00:00Z"),
    ])
    catchers = pd.DataFrame([
        _catcher(1, "2026-08-01", "2026-08-02T10:00:00Z"),
        _catcher(2, "2026-08-02", "2026-08-02T18:00:00Z"),
    ])
    detail = build_detail(projections, catchers).set_index("Game_PK")
    assert int(detail.loc[2, "Prior_Catcher_Starts"]) == 0


def test_future_games_never_enter_a_target_catchers_prior_history() -> None:
    projections = pd.DataFrame([
        _projection(1, "2026-08-01", "2026-08-01T20:00:00Z", "2026-08-01T12:00:00Z", 7, "2026-08-01T23:00:00Z"),
        _projection(2, "2026-08-02", "2026-08-02T20:00:00Z", "2026-08-02T12:00:00Z", 6, "2026-08-02T23:00:00Z"),
        _projection(3, "2026-08-03", "2026-08-03T20:00:00Z", "2026-08-03T12:00:00Z", 12, "2026-08-03T23:00:00Z"),
    ])
    catchers = pd.DataFrame([
        _catcher(1, "2026-08-01", "2026-08-01T18:00:00Z"),
        _catcher(2, "2026-08-02", "2026-08-02T18:00:00Z"),
        _catcher(3, "2026-08-03", "2026-08-03T18:00:00Z"),
    ])
    detail = build_detail(projections, catchers).set_index("Game_PK")
    assert int(detail.loc[2, "Prior_Catcher_Starts"]) == 1


def test_shadow_factor_requires_five_prior_starts_is_capped_and_has_no_production_authority() -> None:
    projections = []
    catchers = []
    for day in range(1, 7):
        projections.append(
            _projection(
                day,
                f"2026-08-{day:02d}",
                f"2026-08-{day:02d}T20:00:00Z",
                f"2026-08-{day:02d}T12:00:00Z",
                7 if day < 6 else 6,
                f"2026-08-{day:02d}T23:00:00Z",
            )
        )
        catchers.append(_catcher(day, f"2026-08-{day:02d}", f"2026-08-{day:02d}T18:00:00Z"))
    detail = build_detail(pd.DataFrame(projections), pd.DataFrame(catchers)).set_index("Game_PK")
    target = detail.loc[6]
    assert int(target["Prior_Catcher_Starts"]) == 5
    assert bool(target["Candidate_Auditable"]) is True
    assert 1.0 < float(target["Shadow_Catcher_Factor"]) <= 1.0 + MAX_FACTOR_DELTA
    assert float(target["Production_Catcher_Factor"]) == 1.0
    assert target["Production_Authority"] == PRODUCTION_AUTHORITY == "NONE"
    assert target["Candidate_Authority"] == "REPORT_ONLY"


def _gate_detail(n: int, *, candidate_error: float = 0.5, base_error: float = 1.0) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "Game_Date": f"2026-07-{(i % 25) + 1:02d}",
            "Catcher_ID": 100 + (i % 15),
            "Lineage": "PRE_GAME_CAPTURE",
            "Actual_Strikeouts": 6.0,
            "Candidate_Auditable": True,
            "Baseline_Error": base_error,
            "Candidate_Error": candidate_error,
            "Candidate_Win": abs(candidate_error) < abs(base_error),
            "Candidate_Loss": abs(candidate_error) > abs(base_error),
            "Signal_Aligned": True,
            "Shadow_Catcher_Factor": 1.02,
        })
    return pd.DataFrame(rows)


def test_gate_stays_learning_until_authentic_volume_diversity_and_days_exist() -> None:
    gate, overall = evaluate_gate(_gate_detail(29))
    assert overall == "LEARNING"
    assert gate.iloc[0]["Evidence_Status"] == "LEARNING"
    assert bool(gate.iloc[0]["Recommended_Activation"]) is False
    assert gate.iloc[0]["Production_Authority"] == "NONE"


def test_gate_can_support_signal_without_gaining_activation_authority() -> None:
    gate, overall = evaluate_gate(_gate_detail(30))
    assert overall == "SUPPORTED"
    assert gate.iloc[0]["Evidence_Status"] == "SUPPORTED"
    assert bool(gate.iloc[0]["Recommended_Activation"]) is False
    assert gate.iloc[0]["Production_Authority"] == "NONE"


def test_large_stable_sample_can_reach_strong_evidence_only() -> None:
    gate, overall = evaluate_gate(_gate_detail(75))
    assert overall == "STRONG EVIDENCE"
    assert gate.iloc[0]["Evidence_Status"] == "STRONG EVIDENCE"
    assert bool(gate.iloc[0]["Recommended_Activation"]) is False


def test_large_regressing_sample_is_caution() -> None:
    gate, overall = evaluate_gate(_gate_detail(75, candidate_error=1.4))
    assert overall == "CAUTION"
    assert gate.iloc[0]["Evidence_Status"] == "CAUTION"

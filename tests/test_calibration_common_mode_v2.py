from __future__ import annotations

import numpy as np
import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS
from training.calibration_common_mode_v2 import (
    AUDIT_VERSION,
    CORRECTION_CAP_K,
    FUTURE_ONLY_START,
    MIN_OOS_STARTS,
    MIN_PRIOR_RESOLVED_STARTS,
    PRODUCTION_AUTHORITY,
    build_detail,
    fit_prior_correction,
    prepare_units,
    preregistration_manifest,
    run_audit,
    summarize,
)


def _row(
    game_date: str,
    pitcher_id: int,
    player: str,
    projection: float,
    actual: float | None,
    *,
    game_pk: int | None = None,
    captured_at_utc: str | None = None,
    game_time: str | None = None,
) -> dict[str, object]:
    day = pd.Timestamp(game_date)
    return {
        "game_pk": game_pk if game_pk is not None else 900000 + pitcher_id,
        "game_date": game_date,
        "game_time": game_time or f"{day.date().isoformat()}T23:00:00Z",
        "captured_at_utc": captured_at_utc or f"{day.date().isoformat()}T18:00:00Z",
        "pitcher_id": pitcher_id,
        "player": player,
        "projection": projection,
        "actual_strikeouts": actual,
        "history_semantics": HISTORY_SEMANTICS,
    }


def _prior_rows(n: int = MIN_PRIOR_RESOLVED_STARTS, residual: float = -1.0) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    start = pd.Timestamp("2026-07-01")
    for i in range(n):
        day = start + pd.Timedelta(i, unit="D")
        projection = 6.0
        rows.append(
            _row(
                day.date().isoformat(),
                i + 1,
                f"Prior {i}",
                projection,
                projection + residual,
                game_pk=700000 + i,
            )
        )
    return rows


def test_future_only_boundary_is_august_21() -> None:
    frame = pd.DataFrame(
        _prior_rows()
        + [
            _row("2026-08-20", 100, "Too Early", 6.0, 5.0, game_pk=800100),
            _row("2026-08-21", 101, "Eligible", 6.0, 5.0, game_pk=800101),
        ]
    )
    detail = build_detail(frame)
    assert FUTURE_ONLY_START == pd.Timestamp("2026-08-21", tz="UTC")
    assert detail["Pitcher"].tolist() == ["Eligible"]


def test_latest_valid_pregame_capture_is_unique_unit() -> None:
    frame = pd.DataFrame([
        _row(
            "2026-08-21", 1, "Pitcher", 6.0, 5.0, game_pk=777,
            captured_at_utc="2026-08-21T17:00:00Z", game_time="2026-08-21T23:00:00Z",
        ),
        _row(
            "2026-08-21", 1, "Pitcher", 5.5, 5.0, game_pk=777,
            captured_at_utc="2026-08-21T22:30:00Z", game_time="2026-08-21T23:00:00Z",
        ),
        _row(
            "2026-08-21", 1, "Pitcher", 99.0, 5.0, game_pk=777,
            captured_at_utc="2026-08-21T23:30:00Z", game_time="2026-08-21T23:00:00Z",
        ),
    ])
    prepared = prepare_units(frame)
    assert len(prepared) == 1
    assert float(prepared.iloc[0]["_projection"]) == 5.5
    assert prepared.iloc[0]["_captured_at"] == pd.Timestamp("2026-08-21T22:30:00Z")


def test_prior_fit_is_shrunk_and_hard_capped() -> None:
    prepared = prepare_units(pd.DataFrame(_prior_rows(n=60, residual=-4.0)))
    fit = fit_prior_correction(prepared)
    assert fit["ready"] is True
    assert fit["n"] == 60
    assert np.isclose(float(fit["shrinkage"]), 60.0 / 90.0)
    assert float(fit["correction"]) == -CORRECTION_CAP_K


def test_candidate_waits_for_minimum_prior_sample() -> None:
    frame = pd.DataFrame(
        _prior_rows(n=MIN_PRIOR_RESOLVED_STARTS - 1)
        + [_row("2026-08-21", 200, "Future", 6.0, 5.0, game_pk=820000)]
    )
    detail = build_detail(frame)
    assert len(detail) == 1
    assert bool(detail.iloc[0]["Candidate_Ready"]) is False
    assert pd.isna(detail.iloc[0]["Candidate_Projection"])


def test_same_day_outcome_cannot_train_another_same_day_start() -> None:
    rows = _prior_rows(n=MIN_PRIOR_RESOLVED_STARTS, residual=0.0)
    rows.extend([
        _row("2026-08-21", 301, "Morning Result", 10.0, 0.0, game_pk=830001),
        _row("2026-08-21", 302, "Night Result", 6.0, 6.0, game_pk=830002),
    ])
    detail = build_detail(pd.DataFrame(rows))
    assert len(detail) == 2
    assert set(detail["Prior_Resolved_Starts"].astype(int)) == {MIN_PRIOR_RESOLVED_STARTS}
    assert np.allclose(detail["Applied_Correction_K"].astype(float), 0.0)


def test_target_outcome_does_not_change_its_candidate_projection() -> None:
    base_rows = _prior_rows(n=MIN_PRIOR_RESOLVED_STARTS, residual=-1.0)
    first = pd.DataFrame(base_rows + [_row("2026-08-21", 400, "Target", 6.0, 0.0, game_pk=840000)])
    second = pd.DataFrame(base_rows + [_row("2026-08-21", 400, "Target", 6.0, 20.0, game_pk=840000)])
    candidate_a = float(build_detail(first).iloc[0]["Candidate_Projection"])
    candidate_b = float(build_detail(second).iloc[0]["Candidate_Projection"])
    assert candidate_a == candidate_b


def test_summary_remains_learning_before_maturity() -> None:
    frame = pd.DataFrame(
        _prior_rows(n=MIN_PRIOR_RESOLVED_STARTS, residual=-1.0)
        + [_row("2026-08-21", 500, "One Future", 6.0, 5.0, game_pk=850000)]
    )
    _, summary = run_audit(frame)
    row = summary.iloc[0]
    assert int(row["OOS_Starts"]) == 1
    assert int(row["OOS_Starts"]) < MIN_OOS_STARTS
    assert row["Status"] == "LEARNING"
    assert row["Production_Authority"] == "NONE"


def test_empty_future_window_is_learning_with_no_authority() -> None:
    detail, summary = run_audit(pd.DataFrame(_prior_rows()))
    assert detail.empty
    assert summary.iloc[0]["Status"] == "LEARNING"
    assert int(summary.iloc[0]["OOS_Starts"]) == 0
    assert summary.iloc[0]["Audit_Version"] == AUDIT_VERSION
    assert PRODUCTION_AUTHORITY == "NONE"


def test_preregistration_freezes_distinct_post_blend_contract() -> None:
    manifest = preregistration_manifest().set_index("Field")["Frozen_Value"].astype(str)
    assert manifest["audit_version"] == AUDIT_VERSION
    assert manifest["production_authority"] == "NONE"
    assert manifest["future_only_start"] == "2026-08-21"
    assert manifest["challenger_type"] == "post-blend additive residual correction"
    assert manifest["baseline"] == "saved production strikeout projection"
    assert manifest["same_day_training_excluded"] == "True"
    assert manifest["capture_selection"] == "latest valid capture at or before game_time"
    assert manifest["residual_definition"] == "actual_strikeouts - projection"
    assert manifest["shrinkage"] == "n / (n + 30)"
    assert manifest["correction_cap_k"] == "0.5"
    assert manifest["sim_math_reweighting"] == "False"
    assert manifest["weather_authority"] == "INFORMATIONAL_ONLY"
    assert manifest["automatic_activation"] == "False"

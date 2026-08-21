from __future__ import annotations

import pandas as pd

from training.calibration_shadow_replay import build_walk_forward_detail


def test_calibration_shadow_detail_carries_pregame_identity_for_governance_breadth(monkeypatch) -> None:
    frame = pd.DataFrame([
        {
            "game_date": "2026-08-01", "captured_at_utc": "2026-08-01T12:00:00Z",
            "game_pk": 1, "pitcher_id": 101, "player": "Prior Pitcher", "opponent": "AAA",
            "actual_strikeouts": 5, "sim_5p": 0.55, "math_5p": 0.50,
        },
        {
            "game_date": "2026-08-02", "captured_at_utc": "2026-08-02T12:00:00Z",
            "game_pk": 2, "pitcher_id": 202, "player": "Target Pitcher", "opponent": "BBB",
            "actual_strikeouts": 6, "sim_5p": 0.60, "math_5p": 0.58,
        },
    ])

    class Candidate:
        calibrated = True
        observations = 40
        weight_simulation = 0.6
        weight_math = 0.4

    monkeypatch.setattr("training.calibration_shadow_replay.eligible_rows", lambda data: data.copy())
    monkeypatch.setattr("training.calibration_shadow_replay.fit_blend_candidate", lambda *args, **kwargs: Candidate())

    detail = build_walk_forward_detail(frame)
    target = detail.loc[detail["game_date"].astype(str).str.startswith("2026-08-02")]
    assert not target.empty
    assert set(["pitcher_id", "player", "opponent"]).issubset(detail.columns)
    row = target.iloc[0]
    assert int(row["pitcher_id"]) == 202
    assert row["player"] == "Target Pitcher"
    assert row["opponent"] == "BBB"

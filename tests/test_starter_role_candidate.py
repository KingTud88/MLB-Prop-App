from __future__ import annotations

import pandas as pd

from training.starter_role_candidate import (
    CANDIDATE_VERSION,
    ROLE_ESTABLISHED,
    ROLE_RAMPING,
    ROLE_RESTRICTED,
    attach_role_candidate,
    summarize,
)


def _detail() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2026-04-01", periods=35, freq="D")
    for i, date in enumerate(dates):
        role = ROLE_RAMPING if i < 32 else ROLE_ESTABLISHED
        rows.append({
            "season": 2026,
            "pitcher_id": i + 1,
            "game_date": date.date().isoformat(),
            "starter_role_label": role,
            "actual_pitches": 86.0,
            "projected_pitches": 81.0,
            "actual_bf": 22.0,
            "projected_bf": 20.8,
            "actual_outs": 16.0,
            "projected_outs": 14.8,
        })
    for pid, pitches in ((1001, 86.0), (1002, 130.0)):
        rows.append({
            "season": 2026,
            "pitcher_id": pid,
            "game_date": "2026-05-20",
            "starter_role_label": ROLE_RAMPING,
            "actual_pitches": pitches,
            "projected_pitches": 81.0,
            "actual_bf": 22.0,
            "projected_bf": 20.8,
            "actual_outs": 16.0,
            "projected_outs": 14.8,
        })
    return pd.DataFrame(rows)


def test_role_candidate_uses_only_strictly_earlier_dates() -> None:
    out = attach_role_candidate(_detail())
    same_day = out.loc[out["game_date"].eq("2026-05-20")].sort_values("pitcher_id")
    assert len(same_day) == 2
    assert same_day["role_candidate_version"].eq(CANDIDATE_VERSION).all()
    assert same_day["role_prior_n_pitches"].eq(32).all()
    assert same_day["role_correction_pitches"].nunique() == 1
    assert same_day["role_correction_pitches"].iloc[0] > 0
    assert same_day["role_candidate_pitches"].nunique() == 1


def test_established_starts_are_never_adjusted() -> None:
    out = attach_role_candidate(_detail())
    established = out.loc[out["starter_role_label"].eq(ROLE_ESTABLISHED)]
    assert not established.empty
    assert established["role_correction_pitches"].eq(0).all()
    assert established["role_candidate_pitches"].equals(established["projected_pitches"])


def test_restricted_is_reported_as_low_recent_exposure() -> None:
    frame = _detail().copy()
    frame.loc[frame.index[-1], "starter_role_label"] = ROLE_RESTRICTED
    report = summarize(attach_role_candidate(frame), min_starts=1)
    assert "LOW_RECENT_EXPOSURE" in set(report["Role"])

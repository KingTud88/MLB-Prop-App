from __future__ import annotations

import pandas as pd

from engine.starter_role import (
    ROLE_ESTABLISHED,
    ROLE_OPENER_LIKE,
    ROLE_RAMPING,
    ROLE_RESTRICTED,
    build_starter_role_context,
)


def _log(pitches: list[int], outs: list[int] | None = None) -> pd.DataFrame:
    outs = outs or [16] * len(pitches)
    return pd.DataFrame({
        "date": pd.date_range("2026-04-01", periods=len(pitches), freq="5D"),
        "games_started": [1] * len(pitches),
        "pitches": pitches,
        "bf": [max(10, round(p / 4)) for p in pitches],
        "outs": outs,
    })


def test_established_full_workload() -> None:
    ctx = build_starter_role_context(_log([91, 94, 88, 96, 93, 90]), "2026-06-01")
    assert ctx.label == ROLE_ESTABLISHED
    assert ctx.confidence == "HIGH"


def test_repeated_short_starts_are_opener_like() -> None:
    ctx = build_starter_role_context(_log([45, 49, 52, 48, 50], [6, 7, 8, 7, 8]), "2026-06-01")
    assert ctx.label == ROLE_OPENER_LIKE


def test_recent_low_workload_is_restricted() -> None:
    ctx = build_starter_role_context(_log([92, 90, 88, 66, 64, 68], [17, 16, 17, 12, 12, 13]), "2026-06-01")
    assert ctx.label == ROLE_RESTRICTED


def test_increasing_but_sub_full_workload_is_ramping() -> None:
    ctx = build_starter_role_context(_log([60, 62, 64, 76, 80, 84], [12, 13, 13, 15, 16, 17]), "2026-06-01")
    assert ctx.label == ROLE_RAMPING


def test_same_day_and_future_starts_cannot_change_context() -> None:
    base = _log([70, 76, 82, 86, 88])
    target = pd.Timestamp("2026-04-26")
    before = build_starter_role_context(base, target)
    leaked = pd.concat([
        base,
        pd.DataFrame({
            "date": [target, target + pd.Timedelta(5, unit="D")],
            "games_started": [1, 1],
            "pitches": [110, 115],
            "bf": [30, 31],
            "outs": [24, 24],
        }),
    ], ignore_index=True)
    after = build_starter_role_context(leaked, target)
    assert after == before


def test_relief_appearances_are_excluded() -> None:
    base = _log([90, 92, 94, 91, 93])
    relief = pd.DataFrame({
        "date": [pd.Timestamp("2026-05-01")],
        "games_started": [0],
        "pitches": [12],
        "bf": [3],
        "outs": [3],
    })
    ctx = build_starter_role_context(pd.concat([base, relief], ignore_index=True), "2026-06-01")
    assert ctx.label == ROLE_ESTABLISHED
    assert ctx.starts_used == 5

from __future__ import annotations

import pandas as pd

from training.calibration_shadow_replay import build_walk_forward_detail, summarize_walk_forward


def _row(day: int, *, sim: float, math: float, actual: int) -> dict[str, object]:
    return {
        "game_date": f"2026-07-{day:02d}",
        "captured_at_utc": f"2026-07-{day:02d}T12:00:00Z",
        "probability_semantics": "milestone-ceil-v1",
        "history_semantics": "starter-only-v1",
        "actual_strikeouts": actual,
        "sim_5p": sim,
        "math_5p": math,
    }


def test_walk_forward_requires_strictly_earlier_game_dates() -> None:
    rows = [_row(day, sim=0.70, math=0.30, actual=5 if day % 2 else 4) for day in range(1, 31)]
    # Two rows on the same next date must not train on one another.
    rows.extend([
        {**_row(31, sim=0.65, math=0.35, actual=5), "captured_at_utc": "2026-07-31T10:00:00Z"},
        {**_row(31, sim=0.60, math=0.40, actual=4), "captured_at_utc": "2026-07-31T20:00:00Z"},
    ])
    detail = build_walk_forward_detail(pd.DataFrame(rows))
    five = detail.loc[detail["Milestone"] == 5]
    assert len(five) == 2
    assert set(five["Prior_Eligible_Starts"].astype(int)) == {30}


def test_current_outcome_cannot_change_its_own_candidate_weight() -> None:
    prior = [_row(day, sim=0.80, math=0.20, actual=5) for day in range(1, 31)]
    a = pd.DataFrame(prior + [_row(31, sim=0.70, math=0.30, actual=5)])
    b = pd.DataFrame(prior + [_row(31, sim=0.70, math=0.30, actual=1)])
    da = build_walk_forward_detail(a).loc[lambda x: x["Milestone"] == 5].iloc[0]
    db = build_walk_forward_detail(b).loc[lambda x: x["Milestone"] == 5].iloc[0]
    assert float(da["Candidate_SIM_Weight"]) == float(db["Candidate_SIM_Weight"])
    assert float(da["Candidate_MATH_Weight"]) == float(db["Candidate_MATH_Weight"])


def test_summary_stays_learning_before_out_of_sample_minimum() -> None:
    rows = [_row(day, sim=0.70, math=0.30, actual=5 if day % 2 else 4) for day in range(1, 32)]
    detail = build_walk_forward_detail(pd.DataFrame(rows))
    summary = summarize_walk_forward(detail)
    five = summary.loc[summary["Milestone"] == 5].iloc[0]
    assert int(five["OOS_Starts"]) == 1
    assert five["Status"] == "LEARNING"

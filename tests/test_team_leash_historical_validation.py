from __future__ import annotations

import pandas as pd

from training.team_leash_historical_validation import (
    PRODUCTION_AUTHORITY,
    _summary_row,
    _team_candidate_context,
    build_decisions,
    replay_team_leash,
)


def _pool(days: int = 35) -> pd.DataFrame:
    rows = []
    game_pk = 1
    for i in range(days):
        day = pd.Timestamp("2026-04-01") + pd.Timedelta(i, unit="D")
        for team, pitcher_id, pitches, bf, outs in (
            ("AAA", 1001, 80.0, 20.0, 14.0),
            ("BBB", 2002, 100.0, 24.0, 18.0),
        ):
            rows.append({
                "pitcher_id": pitcher_id,
                "game_pk": game_pk,
                "date": day,
                "season": 2026,
                "team": team,
                "pitches": pitches,
                "bf": bf,
                "outs": outs,
            })
            game_pk += 1
    return pd.DataFrame(rows)


def test_team_candidate_uses_prior_team_history_and_remains_shrunk() -> None:
    prior = _pool(20)
    low = _team_candidate_context(prior, "AAA")
    high = _team_candidate_context(prior, "BBB")
    assert low["status"] == "TRACKING"
    assert high["status"] == "TRACKING"
    assert 0.97 <= low["pitch_multiplier"] < 1.0
    assert 1.0 < high["pitch_multiplier"] <= 1.03


def test_future_outcomes_cannot_change_earlier_replay_candidates() -> None:
    pool = _pool(35)
    before = replay_team_leash(pool, 2026)
    cutoff = pd.Timestamp("2026-04-25")
    changed = pool.copy()
    mask = changed["date"].gt(cutoff)
    changed.loc[mask, ["pitches", "bf", "outs"]] = [120.0, 35.0, 27.0]
    after = replay_team_leash(changed, 2026)
    cols = ["Game_Date", "Pitcher_ID", "Candidate_PITCHES", "Candidate_BF", "Candidate_OUTS"]
    left = before.loc[pd.to_datetime(before["Game_Date"]).le(cutoff), cols].reset_index(drop=True)
    right = after.loc[pd.to_datetime(after["Game_Date"]).le(cutoff), cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)


def test_summary_promotion_cell_requires_mae_win_share_and_bias() -> None:
    frame = pd.DataFrame({
        "Actual_PITCHES": [100.0] * 30,
        "Baseline_PITCHES": [90.0] * 30,
        "Candidate_PITCHES": [96.0] * 30,
    })
    row = _summary_row(frame, season=2026, metric="PITCHES", label="ALL")
    assert row["Promotion_Cell"] == "PASS"
    assert row["MAE_Gate"] is True
    assert row["Win_Gate"] is True
    assert row["Bias_Gate"] is True


def test_metric_decision_requires_every_required_season_and_never_grants_authority() -> None:
    rows = []
    for metric in ("PITCHES", "BF", "OUTS"):
        for season in (2024, 2025, 2026):
            rows.append({
                "Season": season,
                "Metric": metric,
                "Leash_Label": "ALL",
                "Evaluated_Starts": 100,
                "Baseline_MAE": 10.0,
                "Candidate_MAE": 9.0,
                "Relative_MAE_Improvement": 0.10,
                "Candidate_Win_Share": 0.60,
                "Baseline_Bias": -2.0,
                "Candidate_Bias": -1.0,
                "Promotion_Cell": "PASS" if not (metric == "OUTS" and season == 2024) else "FAIL",
                "Reasons": "" if not (metric == "OUTS" and season == 2024) else "bias",
            })
        rows.append({
            "Season": "POOLED",
            "Metric": metric,
            "Leash_Label": "ALL",
            "Evaluated_Starts": 300,
            "Baseline_MAE": 10.0,
            "Candidate_MAE": 9.0,
            "Relative_MAE_Improvement": 0.10,
            "Candidate_Win_Share": 0.60,
            "Baseline_Bias": -2.0,
            "Candidate_Bias": -1.0,
            "Promotion_Cell": "CONTEXT_ONLY",
            "Reasons": "",
        })
    decisions = build_decisions(pd.DataFrame(rows))
    assert decisions.loc[decisions["Metric"].eq("PITCHES"), "Decision"].iloc[0] == "EARNED_REVIEW"
    assert decisions.loc[decisions["Metric"].eq("OUTS"), "Decision"].iloc[0] == "HOLD"
    assert decisions["Production_Authority"].eq(PRODUCTION_AUTHORITY).all()
    assert decisions["Report_Only"].all()

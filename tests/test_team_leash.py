import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS
from engine.team_leash import (
    MIN_TEAM_STARTS,
    build_team_leash_context,
    candidate_workload_fields,
    team_leash_walk_forward_report,
)


def _history(days=50):
    rows = []
    pk = 1000
    for i in range(days):
        day = pd.Timestamp("2026-04-01") + pd.Timedelta(days=i)
        for team, pitches, bf, outs in (("AAA", 80.0, 20.0, 14.0), ("BBB", 100.0, 24.0, 18.0)):
            rows.append({
                "game_pk": pk,
                "pitcher_id": pk + 5000,
                "game_date": day.date().isoformat(),
                "team": team,
                "history_semantics": HISTORY_SEMANTICS,
                "workload_version": "workload-v1",
                "expected_pitches": 90.0,
                "expected_bf": 22.0,
                "expected_outs": 16.0,
                "actual_pitches": pitches,
                "actual_batters_faced": bf,
                "actual_outs": outs,
            })
            pk += 1
    return pd.DataFrame(rows)


def test_small_team_sample_is_neutral_and_context_only():
    frame = _history(MIN_TEAM_STARTS - 1)
    target = (pd.Timestamp("2026-04-01") + pd.Timedelta(days=MIN_TEAM_STARTS)).date().isoformat()
    ctx = build_team_leash_context(frame, pd.DataFrame(), "AAA", target)
    assert ctx.status == "LEARNING"
    assert ctx.role == "CONTEXT_ONLY"
    assert ctx.pitch_multiplier_candidate == 1.0
    assert ctx.bf_multiplier_candidate == 1.0
    assert ctx.outs_multiplier_candidate == 1.0


def test_same_day_and_future_outcomes_cannot_leak_into_context():
    frame = _history(30)
    target = "2026-04-20"
    before = build_team_leash_context(frame, pd.DataFrame(), "AAA", target).snapshot_fields()
    changed = frame.copy()
    changed.loc[pd.to_datetime(changed["game_date"]) >= pd.Timestamp(target), ["actual_pitches", "actual_batters_faced", "actual_outs"]] = [120.0, 35.0, 27.0]
    after = build_team_leash_context(changed, pd.DataFrame(), "AAA", target).snapshot_fields()
    assert before == after


def test_sportsbook_fields_do_not_change_team_leash_context():
    frame = _history(30)
    target = "2026-05-05"
    clean = build_team_leash_context(frame, pd.DataFrame(), "AAA", target).snapshot_fields()
    noisy = frame.copy()
    noisy["Odds"] = -110
    noisy["Book"] = "ExampleBook"
    noisy["Edge"] = 0.99
    altered = build_team_leash_context(noisy, pd.DataFrame(), "AAA", target).snapshot_fields()
    assert clean == altered


def test_candidate_fields_do_not_mutate_baseline_workload():
    frame = _history(30)
    ctx = build_team_leash_context(frame, pd.DataFrame(), "AAA", "2026-05-10")
    baseline = (90.0, 22.0, 16.0)
    fields = candidate_workload_fields(ctx, *baseline)
    assert baseline == (90.0, 22.0, 16.0)
    assert fields["team_leash_candidate_expected_pitches"] < baseline[0]
    assert fields["team_leash_candidate_expected_bf"] < baseline[1]
    assert fields["team_leash_candidate_expected_outs"] < baseline[2]


def test_walk_forward_candidate_detects_helpful_team_usage_signal():
    frame = _history(55)
    report = team_leash_walk_forward_report(frame, pd.DataFrame())
    assert set(report["Target"]) == {"Pitches", "Batters Faced", "Outs"}
    assert (report["Evaluated Starts"] >= 20).all()
    assert (report["Candidate MAE"] < report["Baseline MAE"]).all()
    assert (report["Status"] == "HELPING").all()


def test_walk_forward_report_ignores_sportsbook_columns():
    frame = _history(55)
    clean = team_leash_walk_forward_report(frame, pd.DataFrame())
    noisy = frame.copy()
    noisy["sportsbook_price"] = 12345
    noisy["saved_bet"] = True
    altered = team_leash_walk_forward_report(noisy, pd.DataFrame())
    pd.testing.assert_frame_equal(clean, altered)

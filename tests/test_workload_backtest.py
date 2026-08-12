import pandas as pd

from training.workload_backtest import replay_pitcher, summarize_backtest, segment_summary


def _starts():
    rows = []
    dates = pd.to_datetime([
        "2025-08-01","2025-08-07","2025-08-13","2025-08-19","2025-08-25",
        "2026-03-30","2026-04-05","2026-04-11","2026-04-17","2026-04-23","2026-04-29",
    ])
    for i, date in enumerate(dates):
        rows.append({
            "pitcher_id": 1,
            "date": date,
            "season": int(date.year),
            "pitches": 80 + i * 2,
            "bf": 20 + i * 0.5,
            "outs": 15 + (i % 3),
        })
    return pd.DataFrame(rows)


def test_replay_pitcher_is_strictly_pregame_and_uses_prior_season_carry():
    detail = replay_pitcher(_starts(), 2026)
    assert not detail.empty
    first = detail.sort_values("game_date").iloc[0]
    assert first["game_date"] == "2026-03-30"
    assert first["prior_starts"] == 5
    assert first["current_season_prior_starts"] == 0
    # The target start itself must never leak into its own workload estimate.
    assert first["workload_pitches"] < first["actual_pitches"]
    assert pd.isna(first["season_to_date_pitches"])


def test_summary_compares_workload_to_simple_baselines_without_market_data():
    detail = replay_pitcher(_starts(), 2026)
    summary = summarize_backtest(detail)
    assert set(summary["Metric"]) == {"PITCHES", "BF", "OUTS"}
    assert {"Workload_MAE", "Rolling5_MAE", "Relative_MAE_vs_Rolling5", "Status"}.issubset(summary.columns)
    assert all(summary["Evaluated_Starts"] > 0)


def test_segment_summary_requires_minimum_sample():
    detail = replay_pitcher(_starts(), 2026)
    assert segment_summary(detail, min_starts=99).empty
    visible = segment_summary(detail, min_starts=1)
    assert not visible.empty
    assert set(visible["Dimension"]).issubset({"rest_segment", "leash_label"})

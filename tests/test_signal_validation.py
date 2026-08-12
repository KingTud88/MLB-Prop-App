from __future__ import annotations

import pandas as pd

from engine.signal_validation import (
    attach_signal_profiles,
    context_performance_report,
    paired_signal_report,
)
from engine.starter_history import HISTORY_SEMANTICS


def _paired_history(n: int = 20) -> pd.DataFrame:
    rows = []
    for idx in range(n):
        actual_k = 6.0 + (idx % 2)
        actual_h = 5.0 + (idx % 2)
        actual_o = 17.0 + (idx % 2)
        rows.append({
            "game_pk": 1000 + idx,
            "pitcher_id": 2000 + idx,
            "game_date": f"2026-07-{(idx % 28) + 1:02d}",
            "captured_at_utc": f"2026-07-{(idx % 28) + 1:02d}T10:00:00Z",
            "history_semantics": HISTORY_SEMANTICS,
            "projection": actual_k - 0.2,
            "hits_projection": actual_h + 0.2,
            "outs_projection": actual_o - 0.2,
            "actual_strikeouts": actual_k,
            "actual_hits_allowed": actual_h,
            "actual_outs": actual_o,
            "k_range_low": actual_k - 2,
            "k_range_high": actual_k + 2,
            "hits_range_low": actual_h - 2,
            "hits_range_high": actual_h + 2,
            "outs_range_low": actual_o - 3,
            "outs_range_high": actual_o + 3,
            "workload_preupgrade_projection": actual_k - 1.0,
            "workload_preupgrade_hits_projection": actual_h + 1.0,
            "workload_preupgrade_outs_projection": actual_o - 1.0,
            "workload_version": "workload-v1",
            "lineup_preconfirm_projection": actual_k - 0.8,
            "lineup_preconfirm_hits_projection": actual_h + 0.8,
            "lineup_source": "CONFIRMED_LINEUP",
            "leash_label": "NORMAL",
            "days_since_last_start": 6,
            "starter_history_source": "MLB_ONLY",
            "opponent_k_pct": 26.0,
            "opponent_hit_rate": 23.0,
            "weather_delay_risk": "NONE",
        })
    return pd.DataFrame(rows)


def test_paired_workload_and_lineup_can_earn_helping_status():
    report = paired_signal_report(_paired_history())
    workload_k = report.loc[
        report["Signal"].eq("Workload v1 upgrade") & report["Market"].eq("Strikeouts")
    ].iloc[0]
    lineup_hits = report.loc[
        report["Signal"].eq("Confirmed lineup upgrade") & report["Market"].eq("Hits Allowed")
    ].iloc[0]
    assert workload_k["Resolved Pairs"] == 20
    assert workload_k["Status"] == "HELPING"
    assert workload_k["Post MAE"] < workload_k["Pre MAE"]
    assert lineup_hits["Status"] == "HELPING"


def test_tiny_paired_samples_stay_learning():
    report = paired_signal_report(_paired_history(5))
    assert set(report["Status"]) == {"LEARNING"}


def test_legacy_rows_do_not_count_toward_signal_evidence():
    current = _paired_history(5)
    legacy = _paired_history(30)
    legacy["history_semantics"] = "legacy-mixed-history"
    report = paired_signal_report(pd.concat([current, legacy], ignore_index=True))
    workload_k = report.loc[
        report["Signal"].eq("Workload v1 upgrade") & report["Market"].eq("Strikeouts")
    ].iloc[0]
    assert workload_k["Resolved Pairs"] == 5
    assert workload_k["Status"] == "LEARNING"


def test_sportsbook_columns_cannot_change_signal_report():
    history = _paired_history()
    baseline = paired_signal_report(history)
    with_prices = history.copy()
    with_prices["book"] = "SomeBook"
    with_prices["american_odds"] = -110
    with_prices["edge"] = 0.20
    compared = paired_signal_report(with_prices)
    pd.testing.assert_frame_equal(baseline, compared)


def test_weather_is_explicitly_context_only():
    report = context_performance_report(_paired_history())
    weather = report.loc[report["Context"].eq("Weather Delay Risk")]
    assert not weather.empty
    assert set(weather["Role"]) == {"CONTEXT ONLY"}


def test_attaching_signal_profiles_never_reorders_or_filters_board():
    history = _paired_history()
    plays = pd.DataFrame([
        {"Rank": 1, "Pitcher": "A", "Market": "Strikeouts", "Game PK": 1000, "Pitcher ID": 2000},
        {"Rank": 2, "Pitcher": "B", "Market": "Hits Allowed", "Game PK": 1001, "Pitcher ID": 2001},
    ])
    out = attach_signal_profiles(plays, history)
    assert list(out["Rank"]) == [1, 2]
    assert list(out["Pitcher"]) == ["A", "B"]
    assert len(out) == len(plays)
    assert set(out["Signal Evidence"]) == {"SUPPORTED"}

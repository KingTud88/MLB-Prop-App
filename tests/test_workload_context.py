import pandas as pd

from engine.workload_context import WORKLOAD_VERSION, build_workload_context


def _log(pitches, bf, outs, dates=None):
    n = len(pitches)
    if dates is None:
        dates = pd.date_range("2026-07-01", periods=n, freq="6D")
    return pd.DataFrame({
        "date": pd.to_datetime(dates),
        "pitches": pitches,
        "bf": bf,
        "outs": outs,
    })


def test_workload_context_uses_pitch_efficiency_not_inverse_pitch_count_shortcut():
    efficient = _log([92] * 8, [25] * 8, [18] * 8)
    inefficient = _log([92] * 8, [20] * 8, [15] * 8)
    a = build_workload_context(efficient, "2026-08-25")
    b = build_workload_context(inefficient, "2026-08-25")
    assert a.version == WORKLOAD_VERSION
    assert a.expected_pitches == b.expected_pitches
    assert a.pitches_per_bf < b.pitches_per_bf
    assert a.expected_bf > b.expected_bf
    assert a.expected_outs > b.expected_outs


def test_short_rest_conservatively_reduces_expected_exposure():
    history = _log(
        [94, 95, 96, 97, 98, 99],
        [24, 24, 25, 25, 26, 26],
        [17, 18, 18, 19, 19, 20],
        dates=pd.date_range("2026-07-01", periods=6, freq="6D"),
    )
    last = pd.Timestamp(history["date"].iloc[-1])
    short = build_workload_context(history, last + pd.Timedelta(4, unit="D"))
    normal = build_workload_context(history, last + pd.Timedelta(6, unit="D"))
    assert short.rest_multiplier < 1.0
    assert normal.rest_multiplier == 1.0
    assert short.expected_pitches < normal.expected_pitches
    assert short.expected_bf < normal.expected_bf


def test_target_date_blocks_future_start_leakage():
    base = _log(
        [88, 90, 91, 93, 95, 110],
        [22, 23, 23, 24, 24, 34],
        [15, 16, 16, 17, 17, 24],
        dates=["2026-07-01", "2026-07-07", "2026-07-13", "2026-07-19", "2026-07-25", "2026-08-20"],
    )
    with_future = build_workload_context(base, "2026-08-01")
    without_future = build_workload_context(base.iloc[:-1], "2026-08-01")
    assert with_future.starts_used == without_future.starts_used == 5
    assert with_future.expected_pitches == without_future.expected_pitches
    assert with_future.expected_bf == without_future.expected_bf
    assert with_future.expected_outs == without_future.expected_outs


def test_workload_trend_is_bounded_and_snapshot_fields_are_complete():
    history = _log(
        [70, 72, 74, 100, 105, 110],
        [18, 19, 19, 26, 27, 28],
        [12, 13, 13, 18, 19, 20],
    )
    ctx = build_workload_context(history, "2026-08-25")
    assert -0.30 <= ctx.pitch_trend <= 0.30
    assert 60 <= ctx.expected_pitches <= 112
    assert 10 <= ctx.expected_bf <= 35
    assert 6 <= ctx.expected_outs <= 24
    fields = ctx.snapshot_fields()
    for key in (
        "workload_version", "expected_pitches", "expected_bf", "expected_outs",
        "pitches_per_bf", "days_since_last_start", "pitch_trend", "leash_label",
    ):
        assert key in fields


def test_utc_game_time_works_with_date_only_game_log():
    history = _log(
        [88, 91, 94, 96, 97, 99],
        [22, 23, 24, 24, 25, 25],
        [15, 16, 17, 17, 18, 18],
        dates=["2026-07-01", "2026-07-07", "2026-07-13", "2026-07-19", "2026-07-25", "2026-08-06"],
    )
    ctx = build_workload_context(history, "2026-08-12T23:10:00Z")
    assert ctx.starts_used == 6
    assert ctx.days_since_last_start == 6
    assert 60 <= ctx.expected_pitches <= 112

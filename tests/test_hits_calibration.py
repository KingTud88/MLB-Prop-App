import pandas as pd

from engine.hits_calibration import calibrate_hits_blend, hits_calibration_report
from engine.starter_history import HISTORY_SEMANTICS


def make_rows(n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        hit = 1.0 if i % 2 == 0 else 0.0
        rows.append({
            "hits_sim_over_5_5": 0.80 if hit else 0.20,
            "hits_math_over_5_5": 0.60 if hit else 0.40,
            "actual_hits_allowed": 6 if hit else 4,
            "history_semantics": HISTORY_SEMANTICS,
        })
    return pd.DataFrame(rows)


def test_hits_calibration_waits_for_minimum_sample():
    cal = calibrate_hits_blend(make_rows(10), 5.5, min_observations=30)
    assert not cal.calibrated
    assert cal.observations == 10
    assert cal.weight_simulation == 0.50
    assert cal.weight_math == 0.50


def test_hits_calibration_learns_after_minimum_sample():
    cal = calibrate_hits_blend(make_rows(60), 5.5, min_observations=30)
    assert cal.calibrated
    assert cal.observations == 60
    assert cal.weight_simulation > 0.50
    assert cal.weight_math < 0.50
    assert cal.brier_score is not None


def test_hits_report_excludes_legacy_rows_without_hit_paths():
    frame = pd.concat([make_rows(30), pd.DataFrame([{"actual_hits_allowed": 8}] * 20)], ignore_index=True)
    report = hits_calibration_report(frame, lines=(5.5,), min_observations=30)
    assert int(report.loc[0, "Observations"]) == 30
    assert report.loc[0, "Status"] == "Calibrated"


def test_hits_calibration_excludes_mixed_appearance_history():
    legacy = make_rows(40)
    legacy["history_semantics"] = "legacy-mixed-appearances"
    cal = calibrate_hits_blend(legacy, 5.5, min_observations=30)
    assert cal.observations == 0
    assert not cal.calibrated

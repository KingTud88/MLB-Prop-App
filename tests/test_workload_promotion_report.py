from __future__ import annotations

import pandas as pd

from training.workload_promotion_report import (
    PRODUCTION_AUTHORITY,
    VERSION_ORDER,
    build_decisions,
    season_metric_evidence,
)


def test_season_metric_gate_passes_when_mae_win_share_and_bias_all_improve() -> None:
    frame = pd.DataFrame({
        "actual_pitches": [100.0] * 40,
        "workload_pitches": [90.0] * 40,
        "candidate_pitches": [95.0] * 40,
    })
    row = season_metric_evidence(frame, season=2026, metric="pitches", version="global-v2")
    assert row["Cell_Result"] == "PASS"
    assert row["Changed_Starts"] == 40
    assert row["Relative_MAE_vs_Live"] > 0.0
    assert row["Candidate_Win_Share_vs_Live"] == 1.0
    assert abs(row["Candidate_Bias"]) < abs(row["Live_Bias"])


def test_season_metric_gate_vetoes_mae_gain_when_bias_worsens() -> None:
    rows = []
    for i in range(40):
        if i < 20:
            rows.append({"actual_pitches": 100.0, "workload_pitches": 104.0, "v24_candidate_pitches": 101.0})
        else:
            rows.append({"actual_pitches": 100.0, "workload_pitches": 96.0, "v24_candidate_pitches": 95.0})
    row = season_metric_evidence(pd.DataFrame(rows), season=2026, metric="pitches", version="tight-v2.4")
    assert row["Relative_MAE_vs_Live"] > 0.0
    assert row["Bias_Gate"] is False
    assert row["Cell_Result"] == "FAIL"
    assert "bias" in row["Reasons"]


def _evidence_row(*, season: int, version: str, candidate_mae: float, passed: bool) -> dict[str, object]:
    return {
        "Season": season,
        "Metric": "PITCHES",
        "Version": version,
        "Evaluated_Starts": 100,
        "Changed_Starts": 80,
        "Live_MAE": 10.0,
        "Candidate_MAE": candidate_mae,
        "Relative_MAE_vs_Live": (10.0 - candidate_mae) / 10.0,
        "Candidate_Win_Share_vs_Live": 0.60 if passed else 0.52,
        "Live_Bias": -2.0,
        "Candidate_Bias": -1.0 if passed else -2.5,
        "Sample_Gate": True,
        "MAE_Gate": True,
        "Win_Gate": passed,
        "Bias_Gate": passed,
        "Cell_Result": "PASS" if passed else "FAIL",
        "Reasons": "" if passed else "win_share|bias",
    }


def test_decision_chooses_lowest_mae_candidate_that_passes_every_season() -> None:
    rows = []
    for season in (2024, 2025, 2026):
        for version in VERSION_ORDER:
            if version == "tight-v2.3":
                rows.append(_evidence_row(season=season, version=version, candidate_mae=8.7, passed=True))
            elif version == "global-v2":
                rows.append(_evidence_row(season=season, version=version, candidate_mae=9.0, passed=True))
            elif version == "tight-v2.4":
                rows.append(_evidence_row(season=season, version=version, candidate_mae=8.5, passed=False))
            else:
                rows.append(_evidence_row(season=season, version=version, candidate_mae=9.2, passed=False))
    decisions = build_decisions(pd.DataFrame(rows))
    pitches = decisions.loc[decisions["Metric"].eq("PITCHES")].iloc[0]
    assert pitches["Decision"] == "PROMOTE"
    assert pitches["Recommended_Version"] == "tight-v2.3"
    assert pitches["Production_Authority"] == PRODUCTION_AUTHORITY == "NONE"
    assert bool(pitches["Report_Only"]) is True


def test_decision_holds_best_mae_candidate_when_strict_cells_do_not_all_pass() -> None:
    rows = []
    for season in (2024, 2025, 2026):
        for version in VERSION_ORDER:
            if version == "tight-v2.5":
                rows.append(_evidence_row(season=season, version=version, candidate_mae=9.6, passed=season == 2026))
            else:
                rows.append(_evidence_row(season=season, version=version, candidate_mae=9.8, passed=False))
    decisions = build_decisions(pd.DataFrame(rows))
    pitches = decisions.loc[decisions["Metric"].eq("PITCHES")].iloc[0]
    assert pitches["Decision"] == "HOLD"
    assert pitches["Recommended_Version"] == "tight-v2.5"
    assert pitches["Passing_Seasons"] == 1
    assert "2024:" in pitches["Reasons"]

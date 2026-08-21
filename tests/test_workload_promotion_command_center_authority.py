from pathlib import Path

import pandas as pd

from training.research_promotion_command_center import build_promotion_command_center


def _write(path: Path, name: str, rows: list[dict[str, object]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path / name, index=False)


def _decision(metric: str, version: str, decision: str, relative: float, passing: int, better: int) -> dict[str, object]:
    return {
        "Metric": metric,
        "Recommended_Version": version,
        "Decision": decision,
        "Pooled_Live_MAE": 2.0,
        "Pooled_Candidate_MAE": 2.0 * (1.0 - relative),
        "Pooled_Relative_MAE": relative,
        "Passing_Seasons": passing,
        "Required_Seasons": 3,
        "MAE_Better_Seasons": better,
        "Reasons": "2024:bias",
        "Production_Authority": "NONE",
        "Report_Only": True,
        "Report_Version": "workload-promotion-report-v1",
    }


def test_workload_lane_prefers_authoritative_cross_season_decisions(tmp_path: Path) -> None:
    _write(tmp_path, "workload_promotion_decisions.csv", [
        _decision("PITCHES", "tight-v2.4", "HOLD", 0.0330, 0, 3),
        _decision("BF", "tight-v2.2", "HOLD", 0.0119, 0, 3),
        _decision("OUTS", "tight-v2.2", "HOLD", 0.0080, 0, 2),
    ])
    # Deliberately healthier latest-season evidence must not override the
    # authoritative cross-season promotion decision source.
    _write(tmp_path, "workload_v25_summary.csv", [
        {"Season": 2026, "Metric": metric, "Evaluated_Starts": 2032,
         "Relative_MAE_vs_v23": 0.10, "V25_Adjusted_Starts": 500,
         "V25_Win_Share_vs_v23": 0.70, "V25_Status": "HELPING",
         "Candidate_Version": "misleading-latest-season"}
        for metric in ("PITCHES", "BF", "OUTS")
    ])

    row = build_promotion_command_center(tmp_path).set_index("Lane").loc["Workload v2.5 Candidates"]
    assert row["Source_Path"] == "data/workload_promotion_decisions.csv"
    assert row["Status"] == "HOLD"
    assert int(row["Current_Breadth"]) == 3
    assert int(row["Required_Breadth"]) == 3
    assert "PITCHES:HOLD tight-v2.4" in row["Evidence_Direction"]
    assert "BF:HOLD tight-v2.2" in row["Evidence_Direction"]
    assert "OUTS:HOLD tight-v2.2" in row["Evidence_Direction"]
    assert "passing_seasons=PITCHES=0/3,BF=0/3,OUTS=0/3" in row["Secondary_Progress"]
    assert not bool(row["Ready_For_Manual_Review"])
    assert row["Recommended_Action"] == "PRESERVE_WORKLOAD_PROMOTION_DECISIONS_REPORT_ONLY"
    assert row["Production_Authority"] == "NONE"


def test_workload_source_promote_only_opens_manual_review(tmp_path: Path) -> None:
    _write(tmp_path, "workload_promotion_decisions.csv", [
        _decision("PITCHES", "tight-v2.4", "PROMOTE", 0.04, 3, 3),
        _decision("BF", "tight-v2.2", "HOLD", 0.01, 0, 3),
        _decision("OUTS", "tight-v2.2", "REJECT", -0.01, 0, 1),
    ])

    row = build_promotion_command_center(tmp_path).set_index("Lane").loc["Workload v2.5 Candidates"]
    assert row["Status"] == "PROMOTE / HOLD / REJECT"
    assert bool(row["Ready_For_Manual_Review"])
    assert row["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW_ONLY"
    assert row["Production_Authority"] == "NONE"
    assert bool(row["Report_Only"])
    assert bool(row["No_Auto_Promotion"])

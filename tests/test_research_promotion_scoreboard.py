from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.research_promotion_scoreboard import LANE_ORDER, build_research_promotion_scoreboard


def _write(root: Path, name: str, rows: list[dict[str, object]]) -> None:
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(data / name, index=False)


def _fixture(root: Path) -> None:
    _write(root, "lineup_k_walkforward_gate.csv", [{
        "Evidence_Status": "CAUTION",
        "OOS_Paired_Starts": 44,
        "Observed_Days": 6,
        "Distinct_Opponents": 20,
        "Relative_MAE_Improvement": -0.01,
        "Confirmed_Win_Share": 0.49,
        "Preconfirm_Bias": -0.12,
        "Confirmed_Bias": -0.15,
        "Reason": "native lineup gate reason",
        "Recommended_Action": "MANUAL_REVIEW",
        "Production_Authority": "NONE",
    }])
    _write(root, "umpire_k_live_validation_gate.csv", [{
        "Evidence_Status": "LEARNING",
        "OOS_Eligible_Starts": 12,
        "Observed_Days": 2,
        "Distinct_Umpires": 9,
        "Relative_MAE_Improvement": 0.02,
        "Candidate_Win_Share": 0.60,
        "Mean_Absolute_Factor_Delta": 0.02,
        "Reason": "need days",
        "Recommended_Action": "KEEP_LEARNING",
        "Production_Authority": "NONE",
    }])
    _write(root, "catcher_context_validation_gate.csv", [{
        "Evidence_Status": "LEARNING",
        "Authentic_Pregame_Resolved": 18,
        "Auditable_Starts": 0,
        "Distinct_Catchers": 0,
        "Observed_Days": 0,
        "Reason": "need prior catcher starts",
        "Recommended_Activation": False,
        "Production_Authority": "NONE",
    }])
    _write(root, "live_role_shadow_gate.csv", [
        {"Role": "RAMPING", "Metric": "PITCHES", "Resolved_Starts": 3, "Live_Gate_Status": "LEARNING"},
        {"Role": "RAMPING", "Metric": "BF", "Resolved_Starts": 4, "Live_Gate_Status": "LEARNING"},
        {"Role": "RAMPING", "Metric": "OUTS", "Resolved_Starts": 2, "Live_Gate_Status": "LEARNING"},
    ])
    _write(root, "ml_shadow_summary.csv", [
        {
            "Challenger": "ML_SHADOW", "OOS_Starts": 50, "Relative_MAE_Improvement": -0.10,
            "Candidate_Win_Share": 0.40, "Candidate_Bias": -0.2, "Status": "HURTING", "Reason": "failed",
        },
        {"Challenger": "SIM_MATH_ML_EQUAL_THIRDS", "OOS_Starts": 0, "Status": "LEARNING"},
    ])
    _write(root, "calibration_shadow_gate.csv", [
        {"Milestone": 3, "OOS_Starts": 50, "Relative_Brier_Improvement": -0.01, "Promotion_Gate_Status": "FAIL"},
        {"Milestone": 4, "OOS_Starts": 50, "Relative_Brier_Improvement": 0.005, "Promotion_Gate_Status": "FAIL"},
    ])
    _write(root, "workload_promotion_decisions.csv", [
        {
            "Metric": "PITCHES", "Decision": "HOLD", "Pooled_Relative_MAE": 0.02,
            "Passing_Seasons": 0, "Required_Seasons": 3, "Reasons": "2026:bias",
            "Production_Authority": "NONE",
        },
        {
            "Metric": "BF", "Decision": "HOLD", "Pooled_Relative_MAE": 0.01,
            "Passing_Seasons": 0, "Required_Seasons": 3, "Reasons": "2026:win_share",
            "Production_Authority": "NONE",
        },
    ])
    _write(root, "top_plays_accountability_findings.csv", [{
        "Finding": "OVERALL ACCOUNTABILITY STATE",
        "Status": "LEARNING",
        "Evidence": "5 settled real-line Top Plays across 1 observed real-line slate(s)",
        "Conclusion": "Observed hit rate 60.0% versus average model probability 78.4% (calibration gap 18.4%). Current sample is too small to change ranking or trust labels.",
        "Production Authority": "NONE",
    }])


def test_scoreboard_preserves_native_lane_statuses_and_order(tmp_path: Path) -> None:
    _fixture(tmp_path)
    board = build_research_promotion_scoreboard(tmp_path)
    assert board["Lane"].tolist() == list(LANE_ORDER)
    statuses = dict(zip(board["Lane"], board["Status"]))
    assert statuses["Confirmed Lineup"] == "CAUTION"
    assert statuses["Umpire Context"] == "LEARNING"
    assert statuses["ML Challenger"] == "HURTING"
    assert statuses["Calibration Shadow"] == "FAIL"
    assert statuses["Workload Candidates"] == "HOLD"


def test_scoreboard_never_claims_research_production_authority(tmp_path: Path) -> None:
    _fixture(tmp_path)
    board = build_research_promotion_scoreboard(tmp_path)
    assert set(board["Production Authority"].astype(str)) == {"NONE"}
    assert "native lineup gate reason" in board.loc[board["Lane"].eq("Confirmed Lineup"), "Reason"].iloc[0]


def test_scoreboard_exposes_gate_bottlenecks_without_regrading(tmp_path: Path) -> None:
    _fixture(tmp_path)
    board = build_research_promotion_scoreboard(tmp_path).set_index("Lane")
    assert "days 6/10" in board.loc["Confirmed Lineup", "Gate Progress"]
    assert "days 2/10" in board.loc["Umpire Context", "Gate Progress"]
    assert "starts 0/30" in board.loc["Catcher Context", "Gate Progress"]
    assert "slowest cell 2/30" in board.loc["Starter Role", "Gate Progress"]
    assert "5/20" in board.loc["Top Plays Accountability", "Gate Progress"]


def test_missing_report_becomes_no_data_instead_of_crashing(tmp_path: Path) -> None:
    board = build_research_promotion_scoreboard(tmp_path)
    assert len(board) == len(LANE_ORDER)
    assert set(board["Status"]) == {"NO DATA"}
    assert set(board["Production Authority"]) == {"NONE"}

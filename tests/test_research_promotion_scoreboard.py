from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.research_promotion_scoreboard import (
    PROJECTION_HISTORY_STAGES,
    build_research_promotion_scoreboard,
    projection_history_stage_map_html,
)


def _write(root: Path, name: str, row: dict[str, object]) -> None:
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(data / name, index=False)


def test_scoreboard_has_no_fixed_card_ceiling_and_shows_registered_programs(tmp_path: Path) -> None:
    board = build_research_promotion_scoreboard(tmp_path)
    lanes = set(board["Lane"].astype(str))
    expected = {
        "Pitch-Mix Whiff Forward",
        "Opponent Asymmetric Challenger",
        "Handedness Matchup Audit",
        "Projection Crusher Shadow",
        "Projection Underperformer Shadow",
        "K Ladder Reliability Shadow",
        "Input Quality v2 · Strikeouts",
        "Input Quality v2 · Hits",
        "Input Quality v2 · Outs",
        "Calibration Common-Mode v2",
        "ML Challenger",
        "Workload v2.5 Candidates",
    }
    assert expected.issubset(lanes)
    assert len(board) >= 22
    assert board["Lane"].is_unique
    assert set(board["Production Authority"].astype(str)) == {"NONE"}
    assert "Manual Review Ready" in board.columns


def test_projection_history_stage_map_matches_existing_page_hierarchy() -> None:
    assert PROJECTION_HISTORY_STAGES == (
        "Archive & frozen evidence",
        "Promotion scoreboard",
        "Lane drilldowns",
        "Deep diagnostics",
    )
    html = projection_history_stage_map_html(active_stage=2)
    positions = [html.index(label) for label in PROJECTION_HISTORY_STAGES]
    assert positions == sorted(positions)
    assert html.count("history-stage-active") == 1
    assert '<b>2</b> · Promotion scoreboard' in html
    assert 'history-stage-pill history-stage-active' in html


def test_projection_history_stage_map_is_presentation_only() -> None:
    source = Path("engine/research_promotion_scoreboard.py").read_text(encoding="utf-8")
    assert "Stage 2 of 4 · research command center · report only · all lanes" in source
    assert "lane drilldowns are next; deep diagnostics follow" in source
    assert "Projection History flow" in source
    assert "Auto_Promote" not in projection_history_stage_map_html(active_stage=2)
    assert "Projection_Delta" not in projection_history_stage_map_html(active_stage=2)


def test_scoreboard_preserves_shadow_native_status_gate_and_readiness(tmp_path: Path) -> None:
    _write(tmp_path, "projection_crusher_shadow_gate.csv", {
        "Status": "LEARNING", "Resolved_Starts": 44, "Required_Starts": 60,
        "Resolved_Days": 6, "Required_Days": 10, "Distinct_Pitchers": 18,
        "Required_Pitchers": 20, "Beat_Projection_Rate": 0.59,
        "Material_Crusher_Rate": 0.18, "Mean_K_Residual": 0.21,
        "Cohorts_Tracked": 9, "Ready_For_Manual_Review": False,
        "Recommended_Action": "COLLECT_EXACT_PROJECTION_CRUSHER_EVIDENCE",
        "Reason": "native Crusher gate reason", "Report_Only": True,
        "Production_Authority": "NONE", "Research_Version": "crusher-test",
    })
    _write(tmp_path, "k_ladder_reliability_shadow_gate.csv", {
        "Status": "SOURCE_NATIVE_READY_LABEL", "Resolved_Calls": 70,
        "Required_Calls": 60, "Resolved_Days": 11, "Required_Days": 10,
        "Distinct_Pitchers": 24, "Required_Pitchers": 20,
        "Probability_Coverage": 0.95, "Required_Probability_Coverage": 0.80,
        "Ladder_Win_Rate": 0.63, "Avg_Target_Probability": 0.66,
        "Calibration_Gap": 0.03, "Brier_Score": 0.22, "Cohorts_Tracked": 10,
        "Ready_For_Manual_Review": True, "Recommended_Action": "MANUAL_RESEARCH_REVIEW",
        "Reason": "native ladder gate reason", "Report_Only": True,
        "Production_Authority": "NONE", "Research_Version": "ladder-test",
    })
    board = build_research_promotion_scoreboard(tmp_path).set_index("Lane")
    crusher = board.loc["Projection Crusher Shadow"]
    ladder = board.loc["K Ladder Reliability Shadow"]

    assert crusher["Status"] == "LEARNING"
    assert "starts 44/60" in crusher["Gate Progress"]
    assert "days 6/10" in crusher["Gate Progress"]
    assert "pitchers 18/20" in crusher["Gate Progress"]
    assert not bool(crusher["Manual Review Ready"])
    assert crusher["Reason"] == "native Crusher gate reason"

    # Readiness is carried from the source field rather than inferred from status wording.
    assert ladder["Status"] == "SOURCE_NATIVE_READY_LABEL"
    assert bool(ladder["Manual Review Ready"])
    assert ladder["Recommended Action"] == "MANUAL_RESEARCH_REVIEW"
    assert ladder["Production Authority"] == "NONE"


def test_missing_reports_become_source_missing_without_reconstruction(tmp_path: Path) -> None:
    board = build_research_promotion_scoreboard(tmp_path)
    assert len(board) >= 22
    assert set(board["Status"]) == {"SOURCE_MISSING"}
    assert set(board["Production Authority"].astype(str)) == {"NONE"}
    assert not board["Manual Review Ready"].astype(bool).any()


def test_scoreboard_is_display_only_and_does_not_expose_production_controls(tmp_path: Path) -> None:
    board = build_research_promotion_scoreboard(tmp_path)
    assert "Production Authority" in board.columns
    assert "Recommended Action" in board.columns
    assert not any(column in board.columns for column in ["Apply_Adjustment", "Projection_Delta", "Auto_Promote"])

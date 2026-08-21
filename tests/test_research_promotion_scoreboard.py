from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.research_promotion_scoreboard import build_research_promotion_scoreboard


def _write(root: Path, name: str, row: dict[str, object]) -> None:
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(data / name, index=False)


def test_scoreboard_has_no_fixed_card_ceiling_and_shows_every_registered_lane(tmp_path: Path) -> None:
    board = build_research_promotion_scoreboard(tmp_path)
    lanes = set(board["Lane"].astype(str))

    assert len(board) == 15
    assert "Pitch-Mix Whiff Forward" in lanes
    assert "Opponent Asymmetric Challenger" in lanes
    assert "Handedness Matchup Audit" in lanes
    assert "Projection Crusher Shadow" in lanes
    assert "K Ladder Reliability Shadow" in lanes
    assert set(board["Production Authority"].astype(str)) == {"NONE"}


def test_scoreboard_preserves_new_shadow_native_status_and_gate_progress(tmp_path: Path) -> None:
    _write(tmp_path, "projection_crusher_shadow_gate.csv", {
        "Status": "LEARNING",
        "Resolved_Starts": 44,
        "Required_Starts": 60,
        "Resolved_Days": 6,
        "Required_Days": 10,
        "Distinct_Pitchers": 18,
        "Required_Pitchers": 20,
        "Beat_Projection_Rate": 0.59,
        "Material_Crusher_Rate": 0.18,
        "Mean_K_Residual": 0.21,
        "Cohorts_Tracked": 9,
        "Ready_For_Manual_Review": False,
        "Recommended_Action": "COLLECT_EXACT_PROJECTION_CRUSHER_EVIDENCE",
        "Reason": "native Crusher gate reason",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Research_Version": "crusher-test",
    })
    board = build_research_promotion_scoreboard(tmp_path).set_index("Lane")
    row = board.loc["Projection Crusher Shadow"]

    assert row["Status"] == "LEARNING"
    assert "starts 44/60" in row["Gate Progress"]
    assert "days 6/10" in row["Gate Progress"]
    assert "pitchers 18/20" in row["Gate Progress"]
    assert "beat_projection_rate" in row["Signal"]
    assert row["Recommended Action"] == "COLLECT_EXACT_PROJECTION_CRUSHER_EVIDENCE"
    assert row["Reason"] == "native Crusher gate reason"
    assert row["Production Authority"] == "NONE"


def test_missing_reports_become_source_missing_without_reconstruction(tmp_path: Path) -> None:
    board = build_research_promotion_scoreboard(tmp_path)
    assert len(board) == 15
    assert set(board["Status"]) == {"SOURCE_MISSING"}
    assert set(board["Production Authority"].astype(str)) == {"NONE"}


def test_scoreboard_is_display_only_and_does_not_expose_production_controls(tmp_path: Path) -> None:
    board = build_research_promotion_scoreboard(tmp_path)
    assert "Production Authority" in board.columns
    assert "Recommended Action" in board.columns
    assert not any(column in board.columns for column in ["Apply_Adjustment", "Projection_Delta", "Auto_Promote"])

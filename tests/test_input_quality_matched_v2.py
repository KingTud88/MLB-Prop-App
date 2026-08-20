from __future__ import annotations

import pandas as pd

from training.input_quality_matched_v2 import (
    AUDIT_VERSION,
    FUTURE_ONLY_START,
    PRIMARY_RULE,
    PRODUCTION_AUTHORITY,
    SAME_PITCHER_RULE,
    match_metric,
    preregistration_manifest,
    run_audit,
)


def _row(
    game_date: str,
    pitcher_id: int,
    player: str,
    history: int,
    projection: float,
    actual: float,
    *,
    expected_outs: float = 16.0,
    opponent_k_pct: float = 22.0,
    role: str = "MID",
) -> dict[str, object]:
    return {
        "game_date": game_date,
        "pitcher_id": pitcher_id,
        "player": player,
        "starter_history_games": history,
        "projection": projection,
        "actual_strikeouts": actual,
        "hits_projection": 5.0,
        "actual_hits_allowed": 5.0,
        "outs_projection": 16.0,
        "actual_outs": 16.0,
        "expected_outs": expected_outs,
        "opponent_k_pct": opponent_k_pct,
        "starter_role_label": role,
    }


def test_future_only_cutoff_excludes_pre_preregistered_outcomes() -> None:
    frame = pd.DataFrame([
        _row("2026-08-19", 1, "Old Shallow", 3, 5.0, 5.0),
        _row("2026-08-19", 2, "Old Deep", 8, 5.1, 5.0),
        _row("2026-08-20", 3, "New Shallow", 4, 5.0, 5.0),
        _row("2026-08-20", 4, "New Deep", 5, 5.1, 5.0),
    ])
    pairs = match_metric(frame, "STRIKEOUTS", PRIMARY_RULE)
    assert len(pairs) == 1
    assert pairs.iloc[0]["Shallow_Pitcher"] == "New Shallow"
    assert pairs.iloc[0]["Deep_Pitcher"] == "New Deep"
    assert pd.Timestamp("2026-08-20") == FUTURE_ONLY_START


def test_primary_matching_respects_frozen_pregame_calipers_and_role() -> None:
    frame = pd.DataFrame([
        _row("2026-08-20", 1, "Shallow", 4, 5.0, 4.0, expected_outs=16.0, opponent_k_pct=22.0, role="MID"),
        _row("2026-08-20", 2, "Good Deep", 5, 5.5, 5.0, expected_outs=16.5, opponent_k_pct=23.0, role="MID"),
        _row("2026-08-20", 3, "Projection Too Far", 6, 6.0, 6.0, expected_outs=16.0, opponent_k_pct=22.0, role="MID"),
        _row("2026-08-20", 4, "Workload Too Far", 6, 5.0, 5.0, expected_outs=18.0, opponent_k_pct=22.0, role="MID"),
        _row("2026-08-20", 5, "Opponent Too Far", 6, 5.0, 5.0, expected_outs=16.0, opponent_k_pct=25.0, role="MID"),
        _row("2026-08-20", 6, "Role Mismatch", 6, 5.0, 5.0, expected_outs=16.0, opponent_k_pct=22.0, role="FULL"),
    ])
    pairs = match_metric(frame, "STRIKEOUTS", PRIMARY_RULE)
    assert len(pairs) == 1
    assert pairs.iloc[0]["Deep_Pitcher"] == "Good Deep"
    assert pairs.iloc[0]["Shallow_History"] <= 4
    assert pairs.iloc[0]["Deep_History"] >= 5


def test_matching_is_without_replacement() -> None:
    frame = pd.DataFrame([
        _row("2026-08-20", 1, "Shallow One", 3, 5.0, 5.0),
        _row("2026-08-21", 2, "Shallow Two", 4, 5.1, 5.0),
        _row("2026-08-22", 3, "Only Deep", 5, 5.05, 5.0),
    ])
    pairs = match_metric(frame, "STRIKEOUTS", PRIMARY_RULE)
    assert len(pairs) == 1
    assert pairs["Deep_Pitcher_ID"].nunique() == 1


def test_pair_selection_is_outcome_blind() -> None:
    base = pd.DataFrame([
        _row("2026-08-20", 1, "Shallow A", 3, 5.0, 1.0, expected_outs=16.0, opponent_k_pct=22.0),
        _row("2026-08-21", 2, "Shallow B", 4, 6.0, 10.0, expected_outs=17.0, opponent_k_pct=24.0, role="FULL"),
        _row("2026-08-22", 3, "Deep A", 5, 5.2, 9.0, expected_outs=16.2, opponent_k_pct=22.5),
        _row("2026-08-23", 4, "Deep B", 8, 5.8, 0.0, expected_outs=17.2, opponent_k_pct=23.5, role="FULL"),
    ])
    changed = base.copy()
    changed["actual_strikeouts"] = [99.0, -10.0, 33.0, 44.0]

    first = match_metric(base, "STRIKEOUTS", PRIMARY_RULE)
    second = match_metric(changed, "STRIKEOUTS", PRIMARY_RULE)
    identity = ["Shallow_Pitcher_ID", "Deep_Pitcher_ID"]
    assert first[identity].to_dict("records") == second[identity].to_dict("records")
    assert first["Shallow_Absolute_Error"].tolist() != second["Shallow_Absolute_Error"].tolist()


def test_same_pitcher_sensitivity_rejects_cross_pitcher_pairs() -> None:
    frame = pd.DataFrame([
        _row("2026-08-20", 7, "Same Pitcher", 3, 5.0, 5.0),
        _row("2026-08-27", 7, "Same Pitcher", 6, 5.2, 5.0),
        _row("2026-08-21", 8, "Different Pitcher", 6, 5.0, 5.0),
    ])
    pairs = match_metric(frame, "STRIKEOUTS", SAME_PITCHER_RULE)
    assert len(pairs) == 1
    assert pairs.iloc[0]["Shallow_Pitcher_ID"] == pairs.iloc[0]["Deep_Pitcher_ID"] == "7"


def test_past_only_dataset_stays_learning_and_preserves_authority_boundary() -> None:
    frame = pd.DataFrame([
        _row("2026-08-19", 1, "Past Shallow", 3, 5.0, 5.0),
        _row("2026-08-19", 2, "Past Deep", 7, 5.1, 5.0),
    ])
    pairs, summary = run_audit(frame)
    assert pairs.empty
    assert len(summary) == 6
    assert set(summary["Status"]) == {"LEARNING"}
    assert set(summary["Matched_Pairs"]) == {0}
    assert set(summary["Production_Authority"]) == {"NONE"}
    assert set(summary["Audit_Version"]) == {AUDIT_VERSION}
    assert PRODUCTION_AUTHORITY == "NONE"


def test_preregistration_manifest_freezes_outcome_blind_report_only_contract() -> None:
    manifest = preregistration_manifest().set_index("Field")["Frozen_Value"].astype(str)
    assert manifest["audit_version"] == AUDIT_VERSION
    assert manifest["production_authority"] == "NONE"
    assert manifest["future_only_start"] == "2026-08-20"
    assert manifest["matching_replacement"] == "False"
    assert manifest["pairing_uses_outcomes"] == "False"
    assert manifest["weather_authority"] == "INFORMATIONAL_ONLY"

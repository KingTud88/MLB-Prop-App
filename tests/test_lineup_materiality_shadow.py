from __future__ import annotations

import pandas as pd

from training.lineup_materiality_shadow import (
    DERIVATION_CUTOFF_DATE,
    FROZEN_MATERIALITY_K,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    build_detail,
    build_gate,
    summarize,
)


def _row(date: str, pre: float, confirmed: float, actual: float, opponent: str = "AAA") -> dict:
    return {
        "game_date": date,
        "game_pk": 1,
        "pitcher_id": 10,
        "player": "Pitcher",
        "team": "BBB",
        "opponent": opponent,
        "Lineup_Source": "TEST",
        "Lineup_Captured_At_UTC": "2026-08-18T20:00:00Z",
        "Game_Time_UTC": "2026-08-18T23:00:00Z",
        "Lineage": "PRE_GAME_CAPTURE",
        "Authentic_Pregame_Pair": True,
        "OOS_Eligible": True,
        "Preconfirm_Projection": pre,
        "Confirmed_Projection": confirmed,
        "Projection_Delta": confirmed - pre,
        "Actual_Strikeouts": actual,
    }


def test_materiality_rule_reverts_small_changes_and_keeps_large_changes() -> None:
    detail = build_detail(pd.DataFrame([
        _row("2026-08-16", 5.0, 5.10, 5.0),
        _row("2026-08-16", 5.0, 5.15, 5.0),
        _row("2026-08-16", 5.0, 4.70, 5.0),
    ]))
    assert detail["Materiality_Action"].tolist() == [
        "REVERT_IMMATERIAL_TO_PRECONFIRM",
        "APPLY_CONFIRMED_MATERIAL",
        "APPLY_CONFIRMED_MATERIAL",
    ]
    assert detail["Materiality_Projection"].tolist() == [5.0, 5.15, 4.70]
    assert detail["Materiality_Changed"].tolist() == [True, False, False]
    assert FROZEN_MATERIALITY_K == 0.15


def test_only_authentic_oos_pairs_are_scored() -> None:
    rows = [_row("2026-08-16", 5.0, 5.1, 5.0), _row("2026-08-16", 5.0, 5.2, 5.0)]
    rows[0]["Authentic_Pregame_Pair"] = False
    rows[1]["OOS_Eligible"] = False
    assert build_detail(pd.DataFrame(rows)).empty


def test_august_17_and_earlier_are_derivation_only() -> None:
    detail = build_detail(pd.DataFrame([
        _row(DERIVATION_CUTOFF_DATE, 5.0, 5.1, 5.0),
        _row("2026-08-18", 5.0, 5.1, 5.0, opponent="CCC"),
    ]))
    assert detail["Evidence_Lane"].tolist() == ["DERIVATION_BACKTEST", "FORWARD_OOS"]
    assert detail["Counts_For_Promotion"].tolist() == [False, True]


def test_supported_gate_requires_forward_size_and_changed_pair_value() -> None:
    rows = []
    # 30 immaterial changes hurt the full confirmed candidate; threshold
    # reversion wins while retaining a non-perfect pre-confirm baseline so
    # relative performance versus that baseline is defined.
    for i in range(30):
        day = 18 + (i % 10)
        rows.append(_row(f"2026-08-{day:02d}", 5.0, 5.10, 5.02, opponent=f"OPP{i % 12:02d}"))
    detail = build_detail(pd.DataFrame(rows))
    gate = build_gate(summarize(detail)).iloc[0]
    assert gate["Finding"] == "SUPPORTED"
    assert gate["Forward_Changed_Pairs"] == 30
    assert gate["Manual_Review_Ready"] in (True, 1)
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"


def test_derivation_cannot_promote_threshold() -> None:
    rows = [
        _row("2026-08-16", 5.0, 5.10, 5.0, opponent=f"OPP{i % 12:02d}")
        for i in range(40)
    ]
    detail = build_detail(pd.DataFrame(rows))
    summary = summarize(detail)
    gate = build_gate(summary).iloc[0]
    assert gate["Finding"] == "INCONCLUSIVE"
    assert gate["Forward_Pairs"] == 0
    assert summary.loc[summary["Evidence_Lane"].eq("DERIVATION_BACKTEST"), "Evidence_Status"].iloc[0] == "DESCRIPTIVE_ONLY"

from __future__ import annotations

import pandas as pd

from training.opponent_matchup_asymmetric_response_shadow import (
    DERIVATION_CUTOFF_DATE,
    FROZEN_BOOST_CAP_K,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    WEAK_REDUCE_DELTA_MAX_PP,
    WEAK_REDUCE_DELTA_MIN_PP,
    build_detail,
    build_gate,
    build_segments,
    summarize,
)


def _row(date: str, delta: float, adjustment: float, actual: float = 5.0, neutral: float = 5.0, opponent: str = "AAA") -> dict:
    return {
        "game_date": date,
        "game_pk": 1,
        "pitcher_id": 10,
        "player": "Pitcher",
        "team": "BBB",
        "opponent": opponent,
        "Opponent_K_Rate": 0.22,
        "Opponent_K_Delta_PP": delta,
        "Matchup_PA": 2000,
        "Lineup_State": "CONFIRMED",
        "Data_Quality": 75,
        "Quality_Band": "70–79",
        "Neutral_Opponent_Projection": neutral,
        "Applied_Projection": neutral + adjustment,
        "Matchup_Adjustment_K": adjustment,
        "Adjustment_Direction": "BOOST" if adjustment > 0 else "REDUCE",
        "Informative_Adjustment": True,
        "Actual_Strikeouts": actual,
        "Auditable": True,
    }


def test_piecewise_candidate_rules_are_frozen_and_asymmetric() -> None:
    frame = pd.DataFrame([
        _row("2026-08-16", 1.8, 0.22),
        _row("2026-08-16", 0.7, 0.07),
        _row("2026-08-16", -0.6, -0.07),
        _row("2026-08-16", -1.7, -0.20),
    ])
    detail = build_detail(frame)

    assert detail["Candidate_Action"].tolist() == [
        "BOOST_CAPPED",
        "BOOST_UNCHANGED",
        "WEAK_REDUCE_NEUTRALIZED",
        "STRONG_REDUCE_UNCHANGED",
    ]
    assert detail["Candidate_Adjustment_K"].tolist() == [FROZEN_BOOST_CAP_K, 0.07, 0.0, -0.20]
    assert detail["Candidate_Changed"].tolist() == [True, False, True, False]
    assert WEAK_REDUCE_DELTA_MIN_PP == -1.0
    assert WEAK_REDUCE_DELTA_MAX_PP == -0.25


def test_only_auditable_informative_rows_are_scored() -> None:
    rows = [_row("2026-08-16", 1.5, 0.2), _row("2026-08-16", -0.5, -0.05)]
    rows[0]["Auditable"] = False
    rows[1]["Informative_Adjustment"] = False
    detail = build_detail(pd.DataFrame(rows))
    assert detail.empty


def test_august_17_and_earlier_are_derivation_only() -> None:
    frame = pd.DataFrame([
        _row(DERIVATION_CUTOFF_DATE, 1.8, 0.20),
        _row("2026-08-18", 1.8, 0.20, opponent="CCC"),
    ])
    detail = build_detail(frame)
    assert detail["Evidence_Lane"].tolist() == ["DERIVATION_BACKTEST", "FORWARD_OOS"]
    assert detail["Counts_For_Promotion"].tolist() == [False, True]


def test_gate_requires_both_changed_components_and_forward_diversity() -> None:
    rows = []
    # Overall sample clears 60 starts / 10 days / 15 opponents, but only the
    # BOOST_CAPPED component is present. The composite must remain inconclusive.
    for i in range(60):
        day = 18 + (i % 10)
        rows.append(
            _row(
                f"2026-08-{day:02d}",
                1.8,
                0.22,
                actual=5.0,
                neutral=5.0,
                opponent=f"OPP{i % 15:02d}",
            )
        )
    detail = build_detail(pd.DataFrame(rows))
    summary = summarize(detail)
    segments = build_segments(detail)
    gate = build_gate(summary, segments).iloc[0]

    assert gate["Finding"] == "INCONCLUSIVE"
    assert gate["Forward_Boost_Capped_Starts"] == 60
    assert gate["Forward_Weak_Reduce_Neutralized_Starts"] == 0
    assert gate["Manual_Review_Ready"] in (False, 0)


def test_supported_gate_needs_overall_win_and_no_harm_in_both_components() -> None:
    rows = []
    # 30 capped boosts: applied 5.3 vs actual 5.0, candidate 5.1 -> candidate wins.
    # 30 weak reductions: applied 4.9 vs actual 5.0, candidate 5.0 -> candidate wins.
    for i in range(30):
        day = 18 + (i % 10)
        rows.append(
            _row(
                f"2026-08-{day:02d}", 1.8, 0.30, actual=5.0, neutral=5.0,
                opponent=f"OPP{i % 15:02d}",
            )
        )
        rows.append(
            _row(
                f"2026-08-{day:02d}", -0.6, -0.10, actual=5.0, neutral=5.0,
                opponent=f"OPP{(i + 7) % 15:02d}",
            )
        )

    detail = build_detail(pd.DataFrame(rows))
    summary = summarize(detail)
    segments = build_segments(detail)
    gate = build_gate(summary, segments).iloc[0]

    assert gate["Finding"] == "SUPPORTED"
    assert gate["Boost_Component_Read"] == "PASS_NO_HARM"
    assert gate["Weak_Reduce_Component_Read"] == "PASS_NO_HARM"
    assert gate["Manual_Review_Ready"] in (True, 1)
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"


def test_derivation_rows_never_become_formal_support() -> None:
    rows = []
    for i in range(80):
        rows.append(
            _row(
                "2026-08-16", 1.8 if i % 2 == 0 else -0.6,
                0.30 if i % 2 == 0 else -0.10,
                actual=5.0, neutral=5.0, opponent=f"OPP{i % 20:02d}",
            )
        )
    detail = build_detail(pd.DataFrame(rows))
    summary = summarize(detail)
    segments = build_segments(detail)
    gate = build_gate(summary, segments).iloc[0]

    assert gate["Finding"] == "INCONCLUSIVE"
    assert gate["Forward_Starts"] == 0
    assert summary.loc[summary["Evidence_Lane"].eq("DERIVATION_BACKTEST"), "Evidence_Status"].iloc[0] == "DESCRIPTIVE_ONLY"

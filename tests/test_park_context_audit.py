from __future__ import annotations

import numpy as np
import pandas as pd

from training import park_context_audit as park


def _source_rows() -> list[dict[str, object]]:
    rows = []
    for index in range(25):
        rows.append({
            "venue_name": f"Park {index}",
            "index_hits": 95 + (index % 11),
            "index_so": 95 + ((index * 2) % 11),
            "index_obp": 95 + ((index * 3) % 11),
            "index_bacon": 95 + ((index * 4) % 11),
            "pa": 10_000 + index,
        })
    return rows


def _source_frame() -> pd.DataFrame:
    return park.normalize_statcast_source(
        _source_rows(),
        2025,
        captured_at_utc="2026-08-22T15:00:00+00:00",
    )


def test_preregistration_is_future_only_report_only_and_not_a_promotion_row():
    prereg = park.build_preregistration()

    assert list(prereg["Market"]) == ["K", "H", "OUTS"]
    assert prereg["Preregistered_Game_Date"].eq("2026-08-22").all()
    assert prereg["First_Eligible_Game_Date"].eq("2026-08-23").all()
    assert prereg["Source_Year_Rule"].eq("game_year - 1").all()
    assert prereg["Rolling_Years"].eq(3).all()
    assert prereg["Report_Only"].eq(True).all()
    assert prereg["Production_Authority"].eq("NONE").all()
    assert prereg["No_Projection_Adjustment"].eq(True).all()
    assert prereg["No_Auto_Promotion"].eq(True).all()
    assert prereg["Automatic_Decision_Allowed"].eq(False).all()
    assert prereg["Supporting_Diagnostic_Only"].eq(True).all()
    assert prereg["Promotion_Row_Registered"].eq(False).all()

    outs = prereg.loc[prereg["Market"].eq("OUTS")].iloc[0]
    assert outs["Statcast_Metric"] == "OBP_EXPLORATORY_PROXY"
    assert outs["Expected_Direction"] == "NEGATIVE"
    assert "separate future challenger preregistration" in outs["Selection_Basis"]


def test_statcast_embedded_payload_is_normalized_and_hashed():
    html = f"<script>data = {pd.DataFrame(_source_rows()).to_json(orient='records')};</script>"
    parsed = park.parse_embedded_statcast_data(html)
    source = park.normalize_statcast_source(
        parsed,
        2025,
        captured_at_utc="2026-08-22T15:00:00+00:00",
    )

    assert len(source) == 25
    assert source["Source_Year"].eq(2025).all()
    assert source["Source_Window_Start_Year"].eq(2023).all()
    assert source["Source_Window_End_Year"].eq(2025).all()
    assert source[["H_Factor", "SO_Factor", "OBP_Factor"]].notna().all().all()
    assert source["Source_SHA256"].str.len().eq(64).all()
    assert source["Source_URL"].str.contains("rolling=3", regex=False).all()
    assert park.source_year_for_game_date("2026-08-23") == 2025


def test_forward_detail_excludes_prefreeze_rows_and_uses_saved_source_only():
    source = _source_frame()
    history = pd.DataFrame([
        {
            "game_date": "2026-08-22", "game_pk": 1, "pitcher_id": 1, "player": "A",
            "team": "CLE", "opponent": "BOS", "venue": "Park 0",
            "projection": 5.0, "actual_strikeouts": 6.0,
            "hits_projection": 4.0, "actual_hits_allowed": 5.0,
            "outs_projection": 16.0, "actual_outs": 15.0,
        },
        {
            "game_date": "2026-08-23", "game_pk": 2, "pitcher_id": 2, "player": "B",
            "team": "CLE", "opponent": "BOS", "venue": "Park 1",
            "projection": 5.0, "actual_strikeouts": 6.0,
            "hits_projection": 4.0, "actual_hits_allowed": 5.0,
            "outs_projection": 16.0, "actual_outs": 15.0,
        },
    ])

    detail = park.build_forward_detail(history, source)

    assert len(detail) == 3
    assert set(detail["Game_Date"]) == {"2026-08-23"}
    assert set(detail["Market"]) == {"K", "H", "OUTS"}
    assert detail["Park_Factor"].notna().all()
    assert detail["Source_Year"].eq(2025).all()
    assert detail["Production_Authority"].eq("NONE").all()
    assert detail["No_Projection_Adjustment"].eq(True).all()


def test_mature_direction_is_reported_but_only_manual_review_is_allowed():
    rows = []
    for index in range(60):
        high = index % 2 == 0
        rows.append({
            "Game_Date": f"2026-09-{(index % 15) + 1:02d}",
            "Market": "K",
            "Venue_Normalized": f"park {index % 12}",
            "Park_Factor": 105.0 if high else 95.0,
            "Factor_Bucket": "HIGH" if high else "LOW",
            "Residual": 1.0 if high else -1.0,
        })
    detail = pd.DataFrame(rows)
    for column in park.DETAIL_COLUMNS:
        if column not in detail.columns:
            detail[column] = np.nan

    summary = park.build_summary(detail)
    k = summary.loc[summary["Market"].eq("K")].iloc[0]

    assert k["Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert k["Evidence_Direction"] == "EXPECTED"
    assert bool(k["Ready_For_Manual_Review"])
    assert k["Production_Authority"] == "NONE"
    assert bool(k["No_Auto_Promotion"])
    assert not bool(k["Automatic_Decision_Allowed"])


def test_missing_source_fails_closed_and_aliases_are_deterministic():
    summary = park.build_summary(pd.DataFrame(columns=park.DETAIL_COLUMNS))
    gate = park.build_gate(summary, pd.DataFrame(columns=park.SOURCE_COLUMNS)).iloc[0]

    assert gate["Status"] == "SOURCE_MISSING"
    assert gate["Recommended_Action"] == "CAPTURE_PRIOR_COMPLETED_SEASON_STATCAST_PARK_FACTORS_THEN_COLLECT_FORWARD_EVIDENCE"
    assert gate["Production_Authority"] == "NONE"
    assert not bool(gate["Promotion_Row_Registered"])
    assert park._normalize_venue("UNIQLO Field at Dodger Stadium") == "dodger stadium"
    assert park._normalize_venue("Rate Field") == "guaranteed rate field"
    assert park._normalize_venue("Daikin Park") == "minute maid park"

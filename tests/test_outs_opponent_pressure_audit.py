import pandas as pd

from training.outs_opponent_pressure_audit import build_detail, build_evaluation, build_gate
from training.outs_opponent_pressure_preregistration import build_preregistration


def test_preregistration_is_report_only_future_only_and_not_a_promotion_row():
    prereg = build_preregistration()
    assert set(prereg["Rule_ID"]) == {"OBP_HIGH_335_PLUS", "CONTACT_HIGH_800_PLUS", "OBP335_AND_CONTACT800"}
    assert prereg["First_Eligible_Game_Date"].eq("2026-08-23").all()
    assert prereg["Report_Only"].eq(True).all()
    assert prereg["Production_Authority"].eq("NONE").all()
    assert prereg["No_Projection_Adjustment"].eq(True).all()
    assert prereg["No_Auto_Promotion"].eq(True).all()
    assert prereg["Promotion_Row_Registered"].eq(False).all()


def test_pre_freeze_rows_cannot_grade_forward_evidence():
    projections = pd.DataFrame([
        {"game_date": "2026-08-22", "game_pk": 1, "pitcher_id": 10, "player": "Old", "team": "CLE", "opponent": "NYY", "outs_projection": 17.0, "actual_outs": 12},
        {"game_date": "2026-08-23", "game_pk": 2, "pitcher_id": 20, "player": "New", "team": "CLE", "opponent": "NYY", "outs_projection": 17.0, "actual_outs": 15},
    ])
    context = pd.DataFrame([{
        "game_pk": 2, "pitcher_id": 20, "audit_eligible": True, "lineup_confirmed": True,
        "pressure_captured_at_utc": "2026-08-23T12:00:00Z", "opponent_k_rate": .19,
        "opponent_contact_rate": .81, "opponent_obp": .34, "lineup_source": "CONFIRMED_LINEUP",
        "split_coverage": 1.0, "lineage": "PRE_GAME_CONFIRMED_MATCH",
    }])
    detail, meta = build_detail(projections, context)
    assert len(detail) == 1
    assert int(detail.iloc[0]["Game_PK"]) == 2
    assert float(detail.iloc[0]["Outs_Residual"]) == -2.0
    assert meta["eligible_projection_rows"] == 1
    assert meta["source_coverage"] == 1.0


def test_missing_future_context_blocks_source_coverage():
    projections = pd.DataFrame([{
        "game_date": "2026-08-23", "game_pk": 2, "pitcher_id": 20, "player": "New",
        "team": "CLE", "opponent": "NYY", "outs_projection": 17.0, "actual_outs": 15,
    }])
    detail, meta = build_detail(projections, pd.DataFrame())
    evaluation = build_evaluation(detail, source_coverage=float(meta["source_coverage"]))
    gate = build_gate(detail, evaluation, eligible_projection_rows=1, source_coverage=float(meta["source_coverage"]))
    assert detail.empty
    assert gate.iloc[0]["Status"] == "SOURCE_COVERAGE_BLOCKED"
    assert gate.iloc[0]["Production_Authority"] == "NONE"


def test_frozen_maturity_gates_only_enable_manual_review():
    projection_rows = []
    context_rows = []
    opponents = [f"T{i:02d}" for i in range(15)]
    for i in range(60):
        game_pk = 1000 + i
        pitcher_id = 500 + (i % 20)
        date = pd.Timestamp("2026-08-23") + pd.Timedelta(i % 10, unit="D")
        projection_rows.append({
            "game_date": date.date().isoformat(), "game_pk": game_pk, "pitcher_id": pitcher_id,
            "player": f"P{pitcher_id}", "team": "CLE", "opponent": opponents[i % 15],
            "outs_projection": 18.0, "actual_outs": 16.0,
        })
        context_rows.append({
            "game_pk": game_pk, "pitcher_id": pitcher_id, "audit_eligible": True,
            "lineup_confirmed": i % 2 == 0, "pressure_captured_at_utc": f"{date.date().isoformat()}T12:00:00Z",
            "opponent_k_rate": .19, "opponent_contact_rate": .81, "opponent_obp": .34,
            "lineup_source": "CONFIRMED_LINEUP" if i % 2 == 0 else "ACTIVE_ROSTER",
            "split_coverage": 1.0, "lineage": "PRE_GAME_CONFIRMED_MATCH" if i % 2 == 0 else "PRE_GAME_ACTIVE_ROSTER",
        })
    detail, meta = build_detail(pd.DataFrame(projection_rows), pd.DataFrame(context_rows))
    evaluation = build_evaluation(detail, source_coverage=float(meta["source_coverage"]))
    gate = build_gate(detail, evaluation, eligible_projection_rows=int(meta["eligible_projection_rows"]), source_coverage=float(meta["source_coverage"]))
    assert len(detail) == 60
    assert evaluation["Ready_For_Manual_Review"].eq(True).all()
    assert evaluation["Recommended_Action"].eq("MANUAL_RESEARCH_REVIEW_ONLY").all()
    assert gate.iloc[0]["Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert gate.iloc[0]["Automatic_Decision_Allowed"] == False
    assert gate.iloc[0]["Promotion_Row_Registered"] == False

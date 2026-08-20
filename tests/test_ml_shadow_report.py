from pathlib import Path

import numpy as np
import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS
from training import ml_shadow_report as shadow


def _frame(days: int = 90) -> pd.DataFrame:
    rows = []
    start = pd.Timestamp("2026-04-01")
    for i in range(days):
        date = start + pd.Timedelta(i, unit="D")
        opponent_k = 18.0 + (i % 12) * 0.8
        expected_bf = 18.0 + (i % 9) * 0.9
        actual = max(0.0, round(0.235 * expected_bf + (opponent_k - 22.0) * 0.08 + ((i % 5) - 2) * 0.25))
        baseline = 0.225 * expected_bf + (opponent_k - 22.0) * 0.04
        rows.append(
            {
                "game_pk": 100000 + i,
                "game_date": date.date().isoformat(),
                "pitcher_id": 500000 + (i % 20),
                "player": f"Pitcher {i % 20}",
                "team": "CLE",
                "opponent": "DET",
                "projection": baseline,
                "actual_strikeouts": actual,
                "history_semantics": HISTORY_SEMANTICS,
                "opponent_k_pct": opponent_k,
                "starter_history_games": 12 + (i % 10),
                "expected_pitches": 78 + (i % 20),
                "expected_bf": expected_bf,
                "expected_outs": 13 + (i % 7),
                "recent_pitches": 80 + (i % 18),
                "recent_bf": 20 + (i % 8),
                "recent_outs": 14 + (i % 6),
                "pitches_per_bf": 3.7 + (i % 5) * 0.08,
                "outs_per_bf": 0.62 + (i % 4) * 0.02,
                "days_since_last_start": 4 + (i % 3),
                "workload_rest_multiplier": 0.98 + (i % 4) * 0.01,
                "pitch_trend": ((i % 7) - 3) * 0.01,
                "bf_trend": ((i % 5) - 2) * 0.01,
                "outs_trend": ((i % 6) - 3) * 0.01,
                "leash_index": 0.8 + (i % 7) * 0.05,
                "matchup_pa": 300 + (i % 40),
                "matchup_batters": 9,
                "lineup_batters": 9,
                "opponent_hit_rate": 22.0 + (i % 8) * 0.5,
                "sim_mean_k": baseline - 0.15,
                "math_mean_k": baseline + 0.15,
            }
        )
    return pd.DataFrame(rows)


def test_shadow_feature_contract_excludes_market_outcome_and_existing_model_outputs():
    shadow.validate_feature_contract()
    lowered = " ".join(shadow.FEATURE_COLUMNS).lower()
    assert "actual_" not in lowered
    assert "projection" not in lowered
    assert "odds" not in lowered
    assert "market" not in lowered
    assert "price" not in lowered
    assert "sim_" not in lowered
    assert "math_" not in lowered


def test_walk_forward_predictions_only_start_after_prior_sample_and_use_earlier_dates():
    frame = _frame()
    detail = shadow.build_oos_detail(frame)
    eligible = detail.loc[detail["OOS_Eligible"].astype(bool)].copy()
    assert not eligible.empty
    assert int(eligible["Prior_Resolved_Starts"].min()) >= shadow.MIN_PRIOR_RESOLVED
    first_eligible_date = pd.to_datetime(eligible["game_date"]).min()
    prior_dates = pd.to_datetime(frame["game_date"])
    assert int((prior_dates < first_eligible_date).sum()) >= shadow.MIN_PRIOR_RESOLVED


def test_shadow_and_three_path_are_report_only_and_never_live_inputs():
    summary = shadow.summarize_oos(shadow.build_oos_detail(_frame()))
    assert set(summary["Challenger"]) == {"ML_SHADOW", "SIM_MATH_ML_EQUAL_THIRDS"}
    assert summary["Report_Only"].all()
    assert (~summary["Live_Projection_Use"]).all()
    assert (~summary["Market_Features_Used"]).all()


def test_three_path_candidate_requires_raw_sim_and_math_means():
    frame = _frame()
    detail = shadow.build_oos_detail(frame)
    assert detail.loc[detail["OOS_Eligible"].astype(bool), "Three_Path_Eligible"].any()

    without_raw = frame.drop(columns=["sim_mean_k", "math_mean_k"])
    detail_without = shadow.build_oos_detail(without_raw)
    assert not detail_without["Three_Path_Eligible"].any()
    summary_without = shadow.summarize_oos(detail_without)
    three = summary_without.loc[summary_without["Challenger"].eq("SIM_MATH_ML_EQUAL_THIRDS")].iloc[0]
    assert three["Status"] == "LEARNING"
    assert three["Reason"] == "waiting_for_raw_path_history"


def test_live_shadow_candidates_train_only_on_resolved_prior_dates():
    frame = _frame(70)
    future = frame.iloc[-1].copy()
    future["game_pk"] = 999999
    future["game_date"] = "2026-08-20"
    future["actual_strikeouts"] = np.nan
    future["projection"] = 5.2
    combined = pd.concat([frame, pd.DataFrame([future])], ignore_index=True)
    live = shadow.build_live_candidates(combined)
    row = live.loc[live["game_pk"].astype(str).str.replace(".0", "", regex=False).eq("999999")].iloc[0]
    assert bool(row["Report_Only"]) is True
    assert int(row["Training_Resolved_Starts"]) == len(frame)
    assert pd.notna(row["ML_Shadow_Projection"])


def test_production_app_does_not_import_or_call_ml_trainer():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "GradientBoostingRegressor" not in source
    assert "build_oos_detail(" not in source
    assert "build_live_candidates(" not in source

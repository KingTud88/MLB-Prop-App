from pathlib import Path

import pandas as pd

from training.research_signal_coverage_audit import build_coverage_audit, build_summary


ROOT = Path(__file__).resolve().parents[1]


def test_signal_coverage_audit_is_supporting_report_only_and_covers_all_registered_lanes():
    audit = build_coverage_audit(ROOT)
    command = pd.read_csv(ROOT / "data" / "research_promotion_command_center.csv")

    assert not audit.empty
    assert audit["Report_Only"].eq(True).all()
    assert audit["Production_Authority"].eq("NONE").all()
    assert audit["Supporting_Diagnostic_Only"].eq(True).all()
    assert audit["Promotion_Row_Registered"].eq(False).all()
    assert audit["No_Auto_Promotion"].eq(True).all()
    assert not audit["Research_Statuses"].astype(str).str.contains("SOURCE_MISSING", regex=False).any()

    linked = {
        lane.strip()
        for value in audit["Research_Lanes"].fillna("").astype(str)
        for lane in value.split(";")
        if lane.strip()
    }
    assert set(command["Lane"].astype(str)) <= linked


def test_park_context_is_now_preregistered_supporting_coverage_without_activation():
    audit = build_coverage_audit(ROOT).set_index("Signal_Class")

    park = audit.loc["Park and venue context"]
    assert park["Coverage_State"] == "COVERED_PREREGISTERED_SUPPORTING_DIAGNOSTIC"
    assert park["Gap_Priority"] == "NONE"
    assert park["Production_State"] == "K_PARTIAL_8_VENUES; H_ENGINE_CAPABILITY_NOT_WIRED; OUTS_ABSENT"
    assert park["Recommended_Next_Step"] == "COLLECT_FORWARD_PARK_CONTEXT_EVIDENCE_NO_PRODUCTION_CHANGE"
    assert park["Research_Statuses"] == "N/A"
    assert not bool(park["Promotion_Row_Registered"])

    outs = audit.loc["Opponent contact/on-base pressure for starter outs"]
    assert outs["Coverage_State"] == "HIGH_CONFIDENCE_COVERAGE_GAP"
    assert outs["Gap_Priority"] == "HIGH"
    assert outs["Production_State"] == "ABSENT_DIRECTLY; WORKLOAD_ONLY"
    assert outs["Recommended_Next_Step"] == "PREREGISTER_REPORT_ONLY_OUTS_OPPONENT_PRESSURE_AUDIT"


def test_weather_remains_intentionally_excluded_and_candidate_gaps_do_not_auto_promote():
    audit = build_coverage_audit(ROOT).set_index("Signal_Class")

    weather = audit.loc["Weather"]
    assert weather["Production_State"] == "INFORMATIONAL_ONLY_BY_POLICY"
    assert weather["Coverage_State"] == "INTENTIONALLY_EXCLUDED_FROM_PROJECTION"

    bullpen = audit.loc["Same-day bullpen availability and hook pressure"]
    defense = audit.loc["Team defense and fielding context"]
    assert bullpen["Gap_Priority"] == "MEDIUM"
    assert defense["Gap_Priority"] == "MEDIUM"
    assert not bool(bullpen["Promotion_Row_Registered"])
    assert not bool(defense["Promotion_Row_Registered"])


def test_signal_coverage_summary_counts_current_gap_classes():
    audit = build_coverage_audit(ROOT)
    summary = build_summary(audit).iloc[0]

    assert int(summary["Signal_Classes"]) == 16
    assert int(summary["High_Priority_Gaps"]) == 1
    assert int(summary["Medium_Priority_Candidates"]) == 2
    assert int(summary["Rows_With_Missing_Research_Source"]) == 0
    assert summary["Production_Authority"] == "NONE"
    assert bool(summary["Supporting_Diagnostic_Only"])
    assert not bool(summary["Promotion_Row_Registered"])


def test_checked_in_signal_coverage_artifacts_match_deterministic_recompute():
    expected = build_coverage_audit(ROOT).reset_index(drop=True)
    actual = pd.read_csv(
        ROOT / "data" / "research_signal_coverage_audit.csv",
        keep_default_na=False,
    ).reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False)

    expected_summary = build_summary(expected).reset_index(drop=True)
    actual_summary = pd.read_csv(
        ROOT / "data" / "research_signal_coverage_audit_summary.csv",
        keep_default_na=False,
    ).reset_index(drop=True)
    pd.testing.assert_frame_equal(actual_summary, expected_summary, check_dtype=False)

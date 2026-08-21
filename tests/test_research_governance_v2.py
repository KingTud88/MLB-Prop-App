from __future__ import annotations

from pathlib import Path

import pandas as pd

from training.research_governance_v2 import (
    AUTOMATIC_DECISION_ALLOWED,
    GOVERNANCE_EFFECTIVE_DATE,
    NO_AUTO_PROMOTION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    apply_promotion_governance,
    build_governance_summary,
    build_hypothesis_manifest,
    build_uncertainty_report,
)


def _source(path: Path, name: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"ok": True}]).to_csv(path / name, index=False)


def _row(lane: str, status: str, source_name: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Lane": lane,
        "Category": "TEST",
        "Source_Path": f"data/{source_name}",
        "Status": status,
        "Evidence_Direction": "",
        "Current_Starts": 60,
        "Required_Starts": 30,
        "Starts_Remaining": 0,
        "Current_Days": None,
        "Required_Days": None,
        "Days_Remaining": None,
        "Breadth_Label": "",
        "Current_Breadth": None,
        "Required_Breadth": None,
        "Breadth_Remaining": None,
        "Secondary_Progress": "",
        "Ready_For_Manual_Review": True,
        "Recommended_Action": "MANUAL_RESEARCH_REVIEW",
        "Source_Reason": "source-owned verdict",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "No_Auto_Promotion": True,
        "Source_Version": "frozen-v1",
        "Command_Center_Version": "test",
    }
    row.update(overrides)
    return row


def test_common_contract_fails_closed_without_source_version(tmp_path: Path) -> None:
    _source(tmp_path, "lane.csv")
    center = pd.DataFrame([_row("Generic Lane", "PASS", "lane.csv", Source_Version="")])
    governed = apply_promotion_governance(center, tmp_path).iloc[0]
    assert governed["Status"] == "PASS"
    assert not bool(governed["Ready_For_Manual_Review"])
    assert governed["Recommended_Action"] == "RESTORE_RESEARCH_CONTROL_METADATA_BEFORE_MANUAL_REVIEW"


def test_calibration_requires_days_and_pitcher_breadth_without_regrading_source(tmp_path: Path) -> None:
    _source(tmp_path, "calibration_shadow_gate.csv")
    detail = []
    for day in range(1, 11):
        for pitcher in range(20):
            detail.append({"game_date": f"2026-08-{day:02d}", "pitcher_id": pitcher})
    pd.DataFrame(detail).to_csv(tmp_path / "calibration_shadow_detail.csv", index=False)
    center = pd.DataFrame([_row("Calibration Shadow", "PASS", "calibration_shadow_gate.csv")])
    governed = apply_promotion_governance(center, tmp_path).iloc[0]
    assert governed["Status"] == "PASS"
    assert int(governed["Current_Days"]) == 10
    assert int(governed["Required_Days"]) == 10
    assert int(governed["Current_Breadth"]) == 20
    assert int(governed["Required_Breadth"]) == 20
    assert bool(governed["Ready_For_Manual_Review"])
    assert governed["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW_ONLY"

    pd.DataFrame(detail).loc[lambda x: x["pitcher_id"].lt(19)].to_csv(
        tmp_path / "calibration_shadow_detail.csv", index=False
    )
    blocked = apply_promotion_governance(center, tmp_path).iloc[0]
    assert blocked["Status"] == "PASS"
    assert not bool(blocked["Ready_For_Manual_Review"])
    assert blocked["Recommended_Action"] == "COLLECT_GOVERNANCE_V2_BREADTH_BEFORE_MANUAL_REVIEW"


def test_calibration_legacy_detail_without_pitcher_identity_fails_closed(tmp_path: Path) -> None:
    _source(tmp_path, "calibration_shadow_gate.csv")
    pd.DataFrame({"game_date": [f"2026-08-{day:02d}" for day in range(1, 11)]}).to_csv(
        tmp_path / "calibration_shadow_detail.csv", index=False
    )
    center = pd.DataFrame([_row("Calibration Shadow", "PASS", "calibration_shadow_gate.csv")])
    governed = apply_promotion_governance(center, tmp_path).iloc[0]
    assert governed["Status"] == "PASS"
    assert pd.isna(governed["Current_Breadth"])
    assert not bool(governed["Ready_For_Manual_Review"])


def _starter_detail(days: int, pitchers: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for role in ("RAMPING", "LOW_RECENT_EXPOSURE"):
        for metric in ("PITCHES", "BF", "OUTS"):
            for day in range(1, days + 1):
                for pitcher in range(pitchers):
                    rows.append({
                        "Role": role,
                        "Metric": metric,
                        "game_date": f"2026-08-{day:02d}",
                        "pitcher_id": pitcher,
                    })
    return pd.DataFrame(rows)


def test_starter_role_uses_minimum_breadth_across_every_required_cell(tmp_path: Path) -> None:
    _source(tmp_path, "live_role_shadow_gate.csv")
    _starter_detail(10, 12).to_csv(tmp_path / "live_role_shadow_detail.csv", index=False)
    center = pd.DataFrame([_row("Starter Role Live Shadow", "PASS", "live_role_shadow_gate.csv")])
    ready = apply_promotion_governance(center, tmp_path).iloc[0]
    assert int(ready["Current_Days"]) == 10
    assert int(ready["Current_Breadth"]) == 12
    assert bool(ready["Ready_For_Manual_Review"])

    incomplete = _starter_detail(10, 12)
    incomplete = incomplete.loc[~(
        incomplete["Role"].eq("RAMPING")
        & incomplete["Metric"].eq("BF")
        & incomplete["game_date"].eq("2026-08-10")
    )]
    incomplete.to_csv(tmp_path / "live_role_shadow_detail.csv", index=False)
    blocked = apply_promotion_governance(center, tmp_path).iloc[0]
    assert int(blocked["Current_Days"]) == 9
    assert not bool(blocked["Ready_For_Manual_Review"])


def test_top_plays_support_needs_five_real_line_days_for_manual_review(tmp_path: Path) -> None:
    _source(tmp_path, "top_plays_accountability_summary.csv")
    center = pd.DataFrame([_row(
        "Top Plays Accountability",
        "STRONG EVIDENCE",
        "top_plays_accountability_summary.csv",
        Current_Days=4,
        Required_Days=None,
    )])
    blocked = apply_promotion_governance(center, tmp_path).iloc[0]
    assert blocked["Status"] == "STRONG EVIDENCE"
    assert int(blocked["Required_Days"]) == 5
    assert not bool(blocked["Ready_For_Manual_Review"])

    center.loc[0, "Current_Days"] = 5
    ready = apply_promotion_governance(center, tmp_path).iloc[0]
    assert bool(ready["Ready_For_Manual_Review"])
    assert ready["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW_ONLY"


def test_ml_helping_status_needs_days_pitchers_and_opponents(tmp_path: Path) -> None:
    _source(tmp_path, "ml_shadow_summary.csv")
    rows = []
    for day in range(1, 11):
        for pitcher in range(20):
            rows.append({
                "game_date": f"2026-08-{day:02d}",
                "pitcher_id": pitcher,
                "opponent": f"OPP{pitcher % 15}",
                "OOS_Eligible": True,
                "ML_Shadow_Projection": 5.0,
            })
    pd.DataFrame(rows).to_csv(tmp_path / "ml_shadow_detail.csv", index=False)
    center = pd.DataFrame([_row("ML Challenger", "HELPING", "ml_shadow_summary.csv")])
    ready = apply_promotion_governance(center, tmp_path).iloc[0]
    assert bool(ready["Ready_For_Manual_Review"])
    assert int(ready["Current_Days"]) == 10
    assert int(ready["Current_Breadth"]) == 20
    assert "governance_v2_opponents=15/15" in str(ready["Secondary_Progress"])

    too_narrow = pd.DataFrame(rows)
    too_narrow["opponent"] = "ONE"
    too_narrow.to_csv(tmp_path / "ml_shadow_detail.csv", index=False)
    blocked = apply_promotion_governance(center, tmp_path).iloc[0]
    assert blocked["Status"] == "HELPING"
    assert not bool(blocked["Ready_For_Manual_Review"])


def test_negative_source_verdicts_are_preserved_not_retuned(tmp_path: Path) -> None:
    _source(tmp_path, "ml_shadow_summary.csv")
    center = pd.DataFrame([_row(
        "ML Challenger",
        "MIXED",
        "ml_shadow_summary.csv",
        Evidence_Direction="relative_mae=-11.27%",
        Ready_For_Manual_Review=False,
        Recommended_Action="PRESERVE_NEGATIVE_ML_EVIDENCE_NO_PROMOTION",
    )])
    governed = apply_promotion_governance(center, tmp_path).iloc[0]
    assert governed["Status"] == "MIXED"
    assert governed["Evidence_Direction"] == "relative_mae=-11.27%"
    assert governed["Recommended_Action"] == "PRESERVE_NEGATIVE_ML_EVIDENCE_NO_PROMOTION"
    assert not bool(governed["Ready_For_Manual_Review"])


def test_manifest_is_deterministic_family_aware_and_does_not_invent_freeze_metadata() -> None:
    center = pd.DataFrame([
        _row("Projection Crusher Shadow", "LEARNING", "crusher.csv", Category="K_RESEARCH", Source_Version="crusher-v1"),
        _row("Projection Underperformer Shadow", "LEARNING", "under.csv", Category="K_RESEARCH", Source_Version="under-v1"),
        _row("Calibration Common-Mode v2", "LEARNING", "cal.csv", Category="CALIBRATION", Source_Version="cal-v2", Secondary_Progress="future_only=2026-08-21"),
    ])
    first = build_hypothesis_manifest(center)
    second = build_hypothesis_manifest(center)
    assert first.equals(second)
    assert len(first) == len(center)
    crusher = first.set_index("Lane").loc["Projection Crusher Shadow"]
    assert crusher["Research_Family"] == "EXACT_K_RESIDUAL"
    assert "Projection Underperformer Shadow" in crusher["Sibling_Lanes"]
    assert crusher["Hypothesis_ID"].startswith("hyp-")
    assert crusher["Freeze_At_UTC"] == ""
    assert crusher["Source_Code_SHA"] == ""
    assert crusher["Freeze_Metadata_Status"] == "SOURCE_VERSION_PINNED"
    common = first.set_index("Lane").loc["Calibration Common-Mode v2"]
    assert common["Forward_Start_Date"] == "2026-08-21"
    assert common["Governance_Effective_Date"] == GOVERNANCE_EFFECTIVE_DATE


def test_uncertainty_is_deterministic_date_blocked_and_diagnostic_only(tmp_path: Path) -> None:
    calibration = pd.DataFrame([
        {"game_date": "2026-08-01", "Milestone": 5, "Baseline_Brier": 1.0, "Candidate_Brier": 0.5},
        {"game_date": "2026-08-01", "Milestone": 5, "Baseline_Brier": 0.8, "Candidate_Brier": 0.5},
        {"game_date": "2026-08-02", "Milestone": 5, "Baseline_Brier": 0.6, "Candidate_Brier": 0.5},
        {"game_date": "2026-08-02", "Milestone": 5, "Baseline_Brier": 0.4, "Candidate_Brier": 0.5},
    ])
    calibration.to_csv(tmp_path / "calibration_shadow_detail.csv", index=False)
    first = build_uncertainty_report(tmp_path)
    second = build_uncertainty_report(tmp_path)
    assert first.equals(second)
    row = first.loc[first["Lane"].eq("Calibration Shadow")].iloc[0]
    assert row["Metric"] == "Baseline_Brier_minus_Candidate_Brier"
    assert int(row["Observations"]) == 4
    assert int(row["Date_Blocks"]) == 2
    assert abs(float(row["Estimate"]) - 0.2) < 1e-12
    assert pd.notna(row["CI_Low_95"])
    assert pd.notna(row["CI_High_95"])
    assert bool(row["Report_Only"])
    assert row["Production_Authority"] == "NONE"


def test_governance_constants_and_summary_keep_zero_authority() -> None:
    center = pd.DataFrame([_row("Generic Lane", "LEARNING", "lane.csv", Ready_For_Manual_Review=False)])
    manifest = build_hypothesis_manifest(center)
    uncertainty = pd.DataFrame()
    summary = build_governance_summary(center, manifest, uncertainty).iloc[0]
    assert VERSION == "research-governance-v2-report-only"
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_AUTO_PROMOTION is True
    assert AUTOMATIC_DECISION_ALLOWED is False
    assert bool(summary["Report_Only"])
    assert summary["Production_Authority"] == "NONE"
    assert not bool(summary["Automatic_Decision_Allowed"])

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

VERSION = "research-signal-coverage-audit-v2-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
SUPPORTING_DIAGNOSTIC_ONLY = True
PROMOTION_ROW_REGISTERED = False
NO_AUTO_PROMOTION = True

COLUMNS = [
    "Signal_Class",
    "Markets",
    "Production_State",
    "Research_Lanes",
    "Research_Statuses",
    "Coverage_State",
    "Gap_Priority",
    "Evidence_Basis",
    "Recommended_Next_Step",
    "Report_Only",
    "Production_Authority",
    "Supporting_Diagnostic_Only",
    "Promotion_Row_Registered",
    "No_Auto_Promotion",
    "Audit_Version",
]

SIGNALS = (
    {
        "Signal_Class": "Pitcher baseline skill and recent form",
        "Markets": "K; H; OUTS",
        "Production_State": "ACTIVE_MARKET_SPECIFIC_HISTORY",
        "Research_Lanes": "Calibration Shadow; Projection Crusher Shadow; Projection Underperformer Shadow; K Ladder Reliability Shadow; Input Quality v2 · Strikeouts; Input Quality v2 · Hits; Input Quality v2 · Outs",
        "Coverage_State": "COVERED",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "K uses shrunk recent K/BF history; Hits uses shrunk hits/BF history; Outs uses recency-weighted outs history. Calibration, residual, ladder, and input-quality lanes audit reliability.",
        "Recommended_Next_Step": "KEEP_FROZEN_AND_COLLECT",
    },
    {
        "Signal_Class": "Opponent batter K/H split and confirmed lineup",
        "Markets": "K; H",
        "Production_State": "ACTIVE",
        "Research_Lanes": "Opponent Asymmetric Challenger; Opponent BOOST Cap Shadow; Weak-REDUCE Neutralization Shadow; Confirmed Lineup; Lineup Materiality Shadow; Handedness Matchup Audit",
        "Coverage_State": "COVERED_BUT_IMMATURE",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Pregame opponent summaries use pitcher-hand hitter K and H/PA splits and preserve confirmed nine-man lineups with shrinkage/fallbacks; associated forward lanes remain source-gated.",
        "Recommended_Next_Step": "KEEP_FROZEN_AND_COLLECT",
    },
    {
        "Signal_Class": "Pitch mix, whiff, putaway, usage and velocity",
        "Markets": "K",
        "Production_State": "RESEARCH_ONLY_NEUTRAL_IN_LIVE_K",
        "Research_Lanes": "Pitch-Mix Whiff Forward",
        "Coverage_State": "COVERED_BUT_IMMATURE",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Pregame research features include pitch types, usage entropy, average velocity, whiff, putaway and arsenal K rate; the live K arsenal factor remains neutral until evidence matures.",
        "Recommended_Next_Step": "KEEP_FROZEN_AND_COLLECT",
    },
    {
        "Signal_Class": "Workload, role, rest and leash",
        "Markets": "K; H; OUTS",
        "Production_State": "ACTIVE_SHARED_WORKLOAD",
        "Research_Lanes": "Starter Role Live Shadow; Workload v2.5 Candidates",
        "Coverage_State": "COVERED_BUT_IMMATURE",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Shared workload uses pregame pitches, BF, outs, efficiency, trends, days since last start, conservative short-rest handling and leash; workload promotion decisions remain cross-season authoritative.",
        "Recommended_Next_Step": "PRESERVE_CURRENT_PRODUCTION_AND_COLLECT",
    },
    {
        "Signal_Class": "Umpire strikeout context",
        "Markets": "K",
        "Production_State": "RESEARCH_ONLY_NEUTRAL_IN_LIVE_K",
        "Research_Lanes": "Umpire Context; Umpire K-UP Cap Shadow",
        "Coverage_State": "COVERED_BUT_IMMATURE",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Umpire context has capture/validation and cap-shadow research; the live K umpire factor remains neutral pending source-owned evidence.",
        "Recommended_Next_Step": "KEEP_FROZEN_AND_COLLECT",
    },
    {
        "Signal_Class": "Catcher context",
        "Markets": "K",
        "Production_State": "RESEARCH_ONLY",
        "Research_Lanes": "Catcher Context",
        "Coverage_State": "COVERED_BUT_IMMATURE",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Catcher capture, prior-maturity and forward validation exist; no production activation is authorized.",
        "Recommended_Next_Step": "KEEP_FROZEN_AND_COLLECT",
    },
    {
        "Signal_Class": "Park and venue context",
        "Markets": "K; H; OUTS",
        "Production_State": "K_PARTIAL_8_VENUES; H_ENGINE_CAPABILITY_NOT_WIRED; OUTS_ABSENT",
        "Research_Lanes": "",
        "Coverage_State": "COVERED_PREREGISTERED_SUPPORTING_DIAGNOSTIC",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "A dedicated future-only Park Context Audit is preregistered from 2026-08-23. It freezes prior-completed-season three-year Baseball Savant park factors for SO and H, treats OBP as exploratory-only for Outs, and has no production or promotion-row authority.",
        "Recommended_Next_Step": "COLLECT_FORWARD_PARK_CONTEXT_EVIDENCE_NO_PRODUCTION_CHANGE",
    },
    {
        "Signal_Class": "Opponent contact/on-base pressure for starter outs",
        "Markets": "OUTS",
        "Production_State": "ABSENT_DIRECTLY; WORKLOAD_ONLY",
        "Research_Lanes": "",
        "Coverage_State": "HIGH_CONFIDENCE_COVERAGE_GAP",
        "Gap_Priority": "HIGH",
        "Evidence_Basis": "Outs projection receives recent outs and shared workload targets but no opponent contact/on-base input. Existing opponent promotion research evaluates K adjustments and Actual_Strikeouts rather than total outs.",
        "Recommended_Next_Step": "PREREGISTER_REPORT_ONLY_OUTS_OPPONENT_PRESSURE_AUDIT",
    },
    {
        "Signal_Class": "Same-day bullpen availability and hook pressure",
        "Markets": "K; H; OUTS",
        "Production_State": "INDIRECT_HISTORICAL_LEASH_ONLY",
        "Research_Lanes": "Starter Role Live Shadow; Workload v2.5 Candidates",
        "Coverage_State": "CANDIDATE_GAP",
        "Gap_Priority": "MEDIUM",
        "Evidence_Basis": "Historical team/pitcher leash is represented, but no explicit same-day bullpen availability or bullpen fatigue feature/capture was identified in the current repository audit.",
        "Recommended_Next_Step": "ASSESS_PREGAME_DATA_AVAILABILITY_THEN_PREREGISTER_IF_AUDITABLE",
    },
    {
        "Signal_Class": "Team defense and fielding context",
        "Markets": "H; OUTS",
        "Production_State": "ABSENT_EXPLICITLY",
        "Research_Lanes": "",
        "Coverage_State": "CANDIDATE_GAP",
        "Gap_Priority": "MEDIUM",
        "Evidence_Basis": "No explicit defense/fielding feature or research lane was identified for Hits Allowed or Outs. Treat as a candidate until a leakage-safe pregame metric and incremental hypothesis are specified.",
        "Recommended_Next_Step": "DEFINE_LEAKAGE_SAFE_DEFENSE_HYPOTHESIS_BEFORE_COLLECTION",
    },
    {
        "Signal_Class": "Probability calibration and common-mode error",
        "Markets": "K; H; OUTS",
        "Production_State": "ACTIVE_CALIBRATION_PATHS_AND_REPORTING",
        "Research_Lanes": "Calibration Shadow; Calibration Common-Mode v2; K Ladder Reliability Shadow",
        "Coverage_State": "COVERED_BUT_IMMATURE",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Independent SIM/MATH paths, calibration reporting, common-mode research and K ladder reliability are present; source-owned negative/watch evidence is preserved.",
        "Recommended_Next_Step": "KEEP_FROZEN_AND_COLLECT",
    },
    {
        "Signal_Class": "Input quality and pregame provenance",
        "Markets": "K; H; OUTS",
        "Production_State": "ACTIVE_GUARDRAILS; RESEARCH_MATCHED_COHORTS",
        "Research_Lanes": "Input Quality v2 · Strikeouts; Input Quality v2 · Hits; Input Quality v2 · Outs",
        "Coverage_State": "COVERED_BUT_IMMATURE",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Matched future-only input-quality lanes exist for all three markets, with provenance/freshness controls and no production authority.",
        "Recommended_Next_Step": "KEEP_FROZEN_AND_COLLECT",
    },
    {
        "Signal_Class": "Projection residual tails and milestone reliability",
        "Markets": "K",
        "Production_State": "RESEARCH_ONLY",
        "Research_Lanes": "Projection Crusher Shadow; Projection Underperformer Shadow; K Ladder Reliability Shadow",
        "Coverage_State": "COVERED_REVIEWED",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Exact frozen-projection residual studies and model-milestone reliability are separate, reviewed research lanes; Underperformer has a future-only supporting challenger while Crusher remains HOLD.",
        "Recommended_Next_Step": "PRESERVE_HUMAN_DISPOSITIONS_AND_COLLECT",
    },
    {
        "Signal_Class": "Authentic-line execution accountability",
        "Markets": "K; H; OUTS",
        "Production_State": "EXECUTION_ONLY",
        "Research_Lanes": "Top Plays Accountability",
        "Coverage_State": "COVERED_BUT_IMMATURE",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Top Plays accountability grades authentic observed real-line decisions separately from forecast math; sportsbook data remains execution-only.",
        "Recommended_Next_Step": "KEEP_REAL_LINE_ONLY_AND_COLLECT",
    },
    {
        "Signal_Class": "ML nonlinear challenger",
        "Markets": "K",
        "Production_State": "RESEARCH_ONLY",
        "Research_Lanes": "ML Challenger",
        "Coverage_State": "COVERED_NEGATIVE_OR_MIXED",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Walk-forward ML shadow exists with no live projection use or market features; negative/mixed evidence is preserved and governance breadth gates apply.",
        "Recommended_Next_Step": "PRESERVE_NEGATIVE_ML_EVIDENCE_NO_PROMOTION",
    },
    {
        "Signal_Class": "Weather",
        "Markets": "K; H; OUTS",
        "Production_State": "INFORMATIONAL_ONLY_BY_POLICY",
        "Research_Lanes": "",
        "Coverage_State": "INTENTIONALLY_EXCLUDED_FROM_PROJECTION",
        "Gap_Priority": "NONE",
        "Evidence_Basis": "Weather remains an informational display and live projection factors are neutral by project guardrail.",
        "Recommended_Next_Step": "PRESERVE_INFORMATIONAL_ONLY_POLICY",
    },
)


def _lane_statuses(command_center: pd.DataFrame, lane_text: str) -> str:
    lanes = [lane.strip() for lane in str(lane_text).split(";") if lane.strip()]
    if not lanes:
        return "N/A"
    if command_center.empty or not {"Lane", "Status"}.issubset(command_center.columns):
        return "; ".join(f"{lane}=SOURCE_MISSING" for lane in lanes)
    status_by_lane = {
        str(row["Lane"]).strip(): str(row["Status"]).strip()
        for _, row in command_center.iterrows()
    }
    return "; ".join(f"{lane}={status_by_lane.get(lane, 'SOURCE_MISSING')}" for lane in lanes)


def build_coverage_audit(root: Path) -> pd.DataFrame:
    root = Path(root)
    command_path = root / "data" / "research_promotion_command_center.csv"
    try:
        command_center = pd.read_csv(command_path)
    except Exception:
        command_center = pd.DataFrame()

    rows: list[dict[str, object]] = []
    for signal in SIGNALS:
        row = dict(signal)
        row["Research_Statuses"] = _lane_statuses(command_center, row["Research_Lanes"])
        row["Report_Only"] = REPORT_ONLY
        row["Production_Authority"] = PRODUCTION_AUTHORITY
        row["Supporting_Diagnostic_Only"] = SUPPORTING_DIAGNOSTIC_ONLY
        row["Promotion_Row_Registered"] = PROMOTION_ROW_REGISTERED
        row["No_Auto_Promotion"] = NO_AUTO_PROMOTION
        row["Audit_Version"] = VERSION
        rows.append(row)
    return pd.DataFrame(rows, columns=COLUMNS)


def build_summary(audit: pd.DataFrame) -> pd.DataFrame:
    high = int(audit["Gap_Priority"].eq("HIGH").sum()) if not audit.empty else 0
    medium = int(audit["Gap_Priority"].eq("MEDIUM").sum()) if not audit.empty else 0
    missing_statuses = int(audit["Research_Statuses"].astype(str).str.contains("SOURCE_MISSING", regex=False).sum()) if not audit.empty else 0
    return pd.DataFrame([{
        "Signal_Classes": int(len(audit)),
        "High_Priority_Gaps": high,
        "Medium_Priority_Candidates": medium,
        "Rows_With_Missing_Research_Source": missing_statuses,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Supporting_Diagnostic_Only": SUPPORTING_DIAGNOSTIC_ONLY,
        "Promotion_Row_Registered": PROMOTION_ROW_REGISTERED,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Audit_Version": VERSION,
    }])


def write_outputs(root: Path) -> tuple[Path, Path]:
    root = Path(root)
    audit = build_coverage_audit(root)
    summary = build_summary(audit)
    detail_path = root / "data" / "research_signal_coverage_audit.csv"
    summary_path = root / "data" / "research_signal_coverage_audit_summary.csv"
    audit.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    return detail_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the report-only research signal coverage audit.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    write_outputs(args.root)


if __name__ == "__main__":
    main()

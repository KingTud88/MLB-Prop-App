from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

VERSION = "research-signal-coverage-audit-v3-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
SUPPORTING_DIAGNOSTIC_ONLY = True
PROMOTION_ROW_REGISTERED = False
NO_AUTO_PROMOTION = True

COLUMNS = [
    "Signal_Class", "Markets", "Production_State", "Research_Lanes", "Research_Statuses",
    "Coverage_State", "Gap_Priority", "Evidence_Basis", "Recommended_Next_Step",
    "Report_Only", "Production_Authority", "Supporting_Diagnostic_Only",
    "Promotion_Row_Registered", "No_Auto_Promotion", "Audit_Version",
]


def _s(signal, markets, production, lanes, coverage, priority, basis, next_step):
    return {
        "Signal_Class": signal, "Markets": markets, "Production_State": production,
        "Research_Lanes": lanes, "Coverage_State": coverage, "Gap_Priority": priority,
        "Evidence_Basis": basis, "Recommended_Next_Step": next_step,
    }


SIGNALS = (
    _s("Pitcher baseline skill and recent form", "K; H; OUTS", "ACTIVE_MARKET_SPECIFIC_HISTORY",
       "Calibration Shadow; Projection Crusher Shadow; Projection Underperformer Shadow; K Ladder Reliability Shadow; Input Quality v2 · Strikeouts; Input Quality v2 · Hits; Input Quality v2 · Outs",
       "COVERED", "NONE", "K uses shrunk recent K/BF history; Hits uses shrunk hits/BF history; Outs uses recency-weighted outs history. Calibration, residual, ladder, and input-quality lanes audit reliability.", "KEEP_FROZEN_AND_COLLECT"),
    _s("Opponent batter K/H split and confirmed lineup", "K; H", "ACTIVE",
       "Opponent Asymmetric Challenger; Opponent BOOST Cap Shadow; Weak-REDUCE Neutralization Shadow; Confirmed Lineup; Lineup Materiality Shadow; Handedness Matchup Audit",
       "COVERED_BUT_IMMATURE", "NONE", "Pregame opponent summaries use pitcher-hand hitter K and H/PA splits and preserve confirmed nine-man lineups with shrinkage/fallbacks; associated forward lanes remain source-gated.", "KEEP_FROZEN_AND_COLLECT"),
    _s("Pitch mix, whiff, putaway, usage and velocity", "K", "RESEARCH_ONLY_NEUTRAL_IN_LIVE_K", "Pitch-Mix Whiff Forward",
       "COVERED_BUT_IMMATURE", "NONE", "Pregame research features include pitch types, usage entropy, average velocity, whiff, putaway and arsenal K rate; the live K arsenal factor remains neutral until evidence matures.", "KEEP_FROZEN_AND_COLLECT"),
    _s("Workload, role, rest and leash", "K; H; OUTS", "ACTIVE_SHARED_WORKLOAD", "Starter Role Live Shadow; Workload v2.5 Candidates",
       "COVERED_BUT_IMMATURE", "NONE", "Shared workload uses pregame pitches, BF, outs, efficiency, trends, days since last start, conservative short-rest handling and leash; workload promotion decisions remain cross-season authoritative.", "PRESERVE_CURRENT_PRODUCTION_AND_COLLECT"),
    _s("Umpire strikeout context", "K", "RESEARCH_ONLY_NEUTRAL_IN_LIVE_K", "Umpire Context; Umpire K-UP Cap Shadow",
       "COVERED_BUT_IMMATURE", "NONE", "Umpire context has capture/validation and cap-shadow research; the live K umpire factor remains neutral pending source-owned evidence.", "KEEP_FROZEN_AND_COLLECT"),
    _s("Catcher context", "K", "RESEARCH_ONLY", "Catcher Context", "COVERED_BUT_IMMATURE", "NONE",
       "Catcher capture, prior-maturity and forward validation exist; no production activation is authorized.", "KEEP_FROZEN_AND_COLLECT"),
    _s("Park and venue context", "K; H; OUTS", "K_PARTIAL_8_VENUES; H_ENGINE_CAPABILITY_NOT_WIRED; OUTS_ABSENT", "",
       "COVERED_PREREGISTERED_SUPPORTING_DIAGNOSTIC", "NONE", "A dedicated future-only Park Context Audit is preregistered from 2026-08-23. It freezes prior-completed-season three-year Baseball Savant park factors for SO and H, treats OBP as exploratory-only for Outs, and has no production or promotion-row authority.", "COLLECT_FORWARD_PARK_CONTEXT_EVIDENCE_NO_PRODUCTION_CHANGE"),
    _s("Opponent contact/on-base pressure for starter outs", "OUTS", "PRODUCTION_ABSENT; RESEARCH_ONLY_PREREGISTERED", "",
       "COVERED_PREREGISTERED_SUPPORTING_DIAGNOSTIC", "NONE", "A dedicated future-only Outs Opponent Pressure Audit is preregistered from 2026-08-23. It captures true opponent OBP and contact rate versus pitcher hand before first pitch, validates confirmed-lineup fingerprints when available, and grades only exact frozen Outs residuals. It has no production or promotion-row authority.", "COLLECT_FUTURE_ONLY_OUTS_OPPONENT_PRESSURE_EVIDENCE_NO_PRODUCTION_CHANGE"),
    _s("Same-day bullpen availability and hook pressure", "K; H; OUTS", "INDIRECT_HISTORICAL_LEASH_ONLY", "Starter Role Live Shadow; Workload v2.5 Candidates",
       "CANDIDATE_GAP", "MEDIUM", "Historical team/pitcher leash is represented, but no explicit same-day bullpen availability or bullpen fatigue feature/capture was identified in the current repository audit.", "ASSESS_PREGAME_DATA_AVAILABILITY_THEN_PREREGISTER_IF_AUDITABLE"),
    _s("Team defense and fielding context", "H; OUTS", "ABSENT_EXPLICITLY", "", "CANDIDATE_GAP", "MEDIUM",
       "No explicit defense/fielding feature or research lane was identified for Hits Allowed or Outs. Treat as a candidate until a leakage-safe pregame metric and incremental hypothesis are specified.", "DEFINE_LEAKAGE_SAFE_DEFENSE_HYPOTHESIS_BEFORE_COLLECTION"),
    _s("Probability calibration and common-mode error", "K; H; OUTS", "ACTIVE_CALIBRATION_PATHS_AND_REPORTING", "Calibration Shadow; Calibration Common-Mode v2; K Ladder Reliability Shadow",
       "COVERED_BUT_IMMATURE", "NONE", "Independent SIM/MATH paths, calibration reporting, common-mode research and K ladder reliability are present; source-owned negative/watch evidence is preserved.", "KEEP_FROZEN_AND_COLLECT"),
    _s("Input quality and pregame provenance", "K; H; OUTS", "ACTIVE_GUARDRAILS; RESEARCH_MATCHED_COHORTS", "Input Quality v2 · Strikeouts; Input Quality v2 · Hits; Input Quality v2 · Outs",
       "COVERED_BUT_IMMATURE", "NONE", "Matched future-only input-quality lanes exist for all three markets, with provenance/freshness controls and no production authority.", "KEEP_FROZEN_AND_COLLECT"),
    _s("Projection residual tails and milestone reliability", "K", "RESEARCH_ONLY", "Projection Crusher Shadow; Projection Underperformer Shadow; K Ladder Reliability Shadow",
       "COVERED_REVIEWED", "NONE", "Exact frozen-projection residual studies and model-milestone reliability are separate, reviewed research lanes; Underperformer has a future-only supporting challenger while Crusher remains HOLD.", "PRESERVE_HUMAN_DISPOSITIONS_AND_COLLECT"),
    _s("Authentic-line execution accountability", "K; H; OUTS", "EXECUTION_ONLY", "Top Plays Accountability",
       "COVERED_BUT_IMMATURE", "NONE", "Top Plays accountability grades authentic observed real-line decisions separately from forecast math; sportsbook data remains execution-only.", "KEEP_REAL_LINE_ONLY_AND_COLLECT"),
    _s("ML nonlinear challenger", "K", "RESEARCH_ONLY", "ML Challenger", "COVERED_NEGATIVE_OR_MIXED", "NONE",
       "Walk-forward ML shadow exists with no live projection use or market features; negative/mixed evidence is preserved and governance breadth gates apply.", "PRESERVE_NEGATIVE_ML_EVIDENCE_NO_PROMOTION"),
    _s("Weather", "K; H; OUTS", "INFORMATIONAL_ONLY_BY_POLICY", "", "INTENTIONALLY_EXCLUDED_FROM_PROJECTION", "NONE",
       "Weather remains an informational display and live projection factors are neutral by project guardrail.", "PRESERVE_INFORMATIONAL_ONLY_POLICY"),
)


def _lane_statuses(command_center: pd.DataFrame, lane_text: str) -> str:
    lanes = [lane.strip() for lane in str(lane_text).split(";") if lane.strip()]
    if not lanes:
        return "N/A"
    if command_center.empty or not {"Lane", "Status"}.issubset(command_center.columns):
        return "; ".join(f"{lane}=SOURCE_MISSING" for lane in lanes)
    status_by_lane = {str(row["Lane"]).strip(): str(row["Status"]).strip() for _, row in command_center.iterrows()}
    return "; ".join(f"{lane}={status_by_lane.get(lane, 'SOURCE_MISSING')}" for lane in lanes)


def build_coverage_audit(root: Path) -> pd.DataFrame:
    root = Path(root)
    try:
        command_center = pd.read_csv(root / "data" / "research_promotion_command_center.csv")
    except Exception:
        command_center = pd.DataFrame()
    rows = []
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
    return pd.DataFrame([{
        "Signal_Classes": int(len(audit)),
        "High_Priority_Gaps": int(audit["Gap_Priority"].eq("HIGH").sum()) if not audit.empty else 0,
        "Medium_Priority_Candidates": int(audit["Gap_Priority"].eq("MEDIUM").sum()) if not audit.empty else 0,
        "Rows_With_Missing_Research_Source": int(audit["Research_Statuses"].astype(str).str.contains("SOURCE_MISSING", regex=False).sum()) if not audit.empty else 0,
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

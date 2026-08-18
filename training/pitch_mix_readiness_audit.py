from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

VERSION = "pitch-mix-readiness-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

FAMILIES = {
    "PITCHER_PITCH_TYPES": ("pitch_mix_pitch_types", "arsenal_pitch_types", "pitch_types"),
    "PITCHER_USAGE": ("pitch_mix_usage", "arsenal_usage", "pitch_usage"),
    "BATTER_PITCH_K_RATES": ("pitch_mix_batter_k_rates", "batter_pitch_k_rates", "pitch_k_rates"),
    "PREGAME_CAPTURE_TIME": ("pitch_mix_captured_at_utc", "arsenal_captured_at_utc"),
    "LINEUP_FINGERPRINT": ("pitch_mix_lineup_hash", "lineup_hash"),
}

REQUIRED_FOR_VALIDATION = (
    "PITCHER_PITCH_TYPES",
    "PITCHER_USAGE",
    "BATTER_PITCH_K_RATES",
    "PREGAME_CAPTURE_TIME",
    "LINEUP_FINGERPRINT",
)

FIELD_COLUMNS = [
    "Requirement", "Satisfied", "Matched_Column", "Non_Null_Rows", "Reason",
    "Report_Only", "Production_Authority", "Validation_Version",
]
SUMMARY_COLUMNS = [
    "Status", "Projection_Rows", "Handedness_Context_Rows", "Satisfied_Requirements",
    "Required_Requirements", "Missing_Requirements", "Historical_Backfill_Allowed",
    "Reason", "Recommended_Action", "Report_Only", "Production_Authority",
    "Validation_Version",
]


def _first_present(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str:
    for column in aliases:
        if column in frame.columns:
            return column
    return ""


def build_field_audit(projections: pd.DataFrame) -> pd.DataFrame:
    projections = projections.copy() if projections is not None else pd.DataFrame()
    rows: list[dict[str, object]] = []
    for requirement, aliases in FAMILIES.items():
        matched = _first_present(projections, aliases)
        non_null = 0
        if matched:
            values = projections[matched]
            non_null = int(values.notna().sum())
            if values.dtype == object:
                non_null = int((values.notna() & values.astype(str).str.strip().ne("") & values.astype(str).str.lower().ne("nan")).sum())
        satisfied = bool(matched and non_null > 0)
        if satisfied:
            reason = f"Persisted pregame field family is available through {matched}."
        elif matched:
            reason = f"Column {matched} exists but has no usable persisted values."
        else:
            reason = "No persisted column in the current projection archive satisfies this input family."
        rows.append({
            "Requirement": requirement,
            "Satisfied": satisfied,
            "Matched_Column": matched,
            "Non_Null_Rows": non_null,
            "Reason": reason,
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Validation_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=FIELD_COLUMNS)


def build_summary(projections: pd.DataFrame, hand_context: pd.DataFrame, fields: pd.DataFrame) -> pd.DataFrame:
    required = fields.loc[fields["Requirement"].isin(REQUIRED_FOR_VALIDATION)].copy()
    satisfied = int(required["Satisfied"].astype(bool).sum()) if not required.empty else 0
    needed = len(REQUIRED_FOR_VALIDATION)
    missing = required.loc[~required["Satisfied"].astype(bool), "Requirement"].astype(str).tolist()

    if satisfied == needed:
        status = "READY_FOR_CAPTURED_VALIDATION"
        reason = "All frozen pregame input families required by the legacy pitch-mix concept are persisted."
        action = "OPEN_REPORT_ONLY_PITCH_MIX_VALIDATION_DESIGN"
    elif satisfied == 0:
        status = "BLOCKED_CAPTURE_REQUIRED"
        reason = "Pitch-mix modeling is not auditable from the current archive because frozen arsenal usage and batter-by-pitch vulnerability inputs are not persisted."
        action = "DESIGN_PREGAME_PITCH_MIX_CAPTURE_BEFORE_MODELING"
    else:
        status = "PARTIAL_CAPTURE_SCHEMA"
        reason = "Some pitch-mix lineage inputs are persisted, but the full auditable input contract is incomplete."
        action = "COMPLETE_PREGAME_PITCH_MIX_CAPTURE_SCHEMA"

    return pd.DataFrame([{
        "Status": status,
        "Projection_Rows": 0 if projections is None else int(len(projections)),
        "Handedness_Context_Rows": 0 if hand_context is None else int(len(hand_context)),
        "Satisfied_Requirements": satisfied,
        "Required_Requirements": needed,
        "Missing_Requirements": "|".join(missing),
        "Historical_Backfill_Allowed": False,
        "Reason": reason,
        "Recommended_Action": action,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VERSION,
    }], columns=SUMMARY_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit whether frozen pregame data can support pitch-mix matchup validation.")
    parser.add_argument("--projection-log", default="data/projection_log.csv")
    parser.add_argument("--hand-context", default="data/handedness_matchup_effective_context.csv")
    parser.add_argument("--fields-output", default="data/pitch_mix_readiness_fields.csv")
    parser.add_argument("--summary-output", default="data/pitch_mix_readiness_summary.csv")
    args = parser.parse_args()

    projection_path = Path(args.projection_log)
    hand_path = Path(args.hand_context)
    projections = pd.read_csv(projection_path) if projection_path.exists() else pd.DataFrame()
    hand_context = pd.read_csv(hand_path) if hand_path.exists() else pd.DataFrame()
    fields = build_field_audit(projections)
    summary = build_summary(projections, hand_context, fields)
    for path, frame in ((Path(args.fields_output), fields), (Path(args.summary_output), summary)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    print(summary.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()

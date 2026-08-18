from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

VERSION = "pitch-mix-readiness-v2-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

FAMILIES = {
    "PITCHER_PITCH_TYPES": ("pitch_mix_pitch_types", "arsenal_pitch_types", "pitch_types"),
    "PITCHER_USAGE": ("pitch_mix_usage", "arsenal_usage", "pitch_usage"),
    "BATTER_PITCH_K_RATES": ("pitch_mix_batter_k_rates", "batter_pitch_k_rates", "pitch_k_rates"),
    "PREGAME_CAPTURE_TIME": ("pitch_mix_captured_at_utc", "arsenal_captured_at_utc"),
    "LINEUP_FINGERPRINT": ("pitch_mix_lineup_hash", "lineup_hash"),
}

PITCH_CONTEXT_REQUIREMENTS = {
    "PITCHER_PITCH_TYPES",
    "PITCHER_USAGE",
    "PREGAME_CAPTURE_TIME",
}

REQUIRED_FOR_VALIDATION = (
    "PITCHER_PITCH_TYPES",
    "PITCHER_USAGE",
    "BATTER_PITCH_K_RATES",
    "PREGAME_CAPTURE_TIME",
    "LINEUP_FINGERPRINT",
)

FIELD_COLUMNS = [
    "Requirement", "Satisfied", "Matched_Source", "Matched_Column", "Non_Null_Rows",
    "Reason", "Report_Only", "Production_Authority", "Validation_Version",
]
SUMMARY_COLUMNS = [
    "Status", "Projection_Rows", "Handedness_Context_Rows", "Pitch_Arsenal_Rows",
    "Pitch_Arsenal_Eligible_Rows", "Satisfied_Requirements", "Required_Requirements",
    "Missing_Requirements", "Historical_Backfill_Allowed", "Reason",
    "Recommended_Action", "Report_Only", "Production_Authority", "Validation_Version",
]


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _eligible_pitch_context(frame: pd.DataFrame | None) -> pd.DataFrame:
    frame = frame.copy() if frame is not None else pd.DataFrame()
    if frame.empty or "audit_eligible" not in frame.columns:
        return frame
    mask = frame["audit_eligible"].map(_truthy)
    return frame.loc[mask].copy()


def _usable_non_null(frame: pd.DataFrame, column: str) -> int:
    if frame is None or frame.empty or column not in frame.columns:
        return 0
    values = frame[column]
    mask = values.notna()
    if values.dtype == object:
        text = values.astype(str).str.strip()
        mask = mask & text.ne("") & text.str.lower().ne("nan")
    return int(mask.sum())


def _first_present(
    requirement: str,
    aliases: tuple[str, ...],
    projections: pd.DataFrame,
    pitch_context: pd.DataFrame,
) -> tuple[str, str, int]:
    if requirement in PITCH_CONTEXT_REQUIREMENTS:
        sources = (("pitch_arsenal_context", pitch_context), ("projection_log", projections))
    else:
        sources = (("projection_log", projections), ("pitch_arsenal_context", pitch_context))
    for source_name, frame in sources:
        for column in aliases:
            if column not in frame.columns:
                continue
            non_null = _usable_non_null(frame, column)
            return source_name, column, non_null
    return "", "", 0


def build_field_audit(
    projections: pd.DataFrame,
    pitch_context: pd.DataFrame | None = None,
) -> pd.DataFrame:
    projections = projections.copy() if projections is not None else pd.DataFrame()
    pitch_context = _eligible_pitch_context(pitch_context)
    rows: list[dict[str, object]] = []
    for requirement, aliases in FAMILIES.items():
        source, matched, non_null = _first_present(requirement, aliases, projections, pitch_context)
        satisfied = bool(matched and non_null > 0)
        if satisfied:
            reason = f"Persisted pregame field family is available through {source}:{matched}."
        elif matched:
            reason = f"Column {source}:{matched} exists but has no usable persisted values."
        else:
            reason = "No eligible persisted pregame source satisfies this input family."
        rows.append({
            "Requirement": requirement,
            "Satisfied": satisfied,
            "Matched_Source": source,
            "Matched_Column": matched,
            "Non_Null_Rows": non_null,
            "Reason": reason,
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Validation_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=FIELD_COLUMNS)


def build_summary(
    projections: pd.DataFrame,
    hand_context: pd.DataFrame,
    fields: pd.DataFrame,
    pitch_context: pd.DataFrame | None = None,
) -> pd.DataFrame:
    required = fields.loc[fields["Requirement"].isin(REQUIRED_FOR_VALIDATION)].copy()
    satisfied = int(required["Satisfied"].astype(bool).sum()) if not required.empty else 0
    needed = len(REQUIRED_FOR_VALIDATION)
    missing = required.loc[~required["Satisfied"].astype(bool), "Requirement"].astype(str).tolist()
    pitch_context = pitch_context.copy() if pitch_context is not None else pd.DataFrame()
    eligible_pitch_context = _eligible_pitch_context(pitch_context)

    if satisfied == needed:
        status = "READY_FOR_CAPTURED_VALIDATION"
        reason = "All frozen pregame input families required by the legacy pitch-mix concept are persisted."
        action = "OPEN_REPORT_ONLY_PITCH_MIX_VALIDATION_DESIGN"
    elif missing == ["BATTER_PITCH_K_RATES"]:
        status = "PITCHER_CONTEXT_READY_BATTER_CONTEXT_MISSING"
        reason = (
            "Frozen pitcher arsenal and lineup lineage are available, but the batter-by-pitch "
            "vulnerability definition and capture are still missing."
        )
        action = "DEFINE_BATTER_PITCH_VULNERABILITY_BEFORE_MODELING"
    elif satisfied == 0:
        status = "BLOCKED_CAPTURE_REQUIRED"
        reason = (
            "Pitch-mix modeling is not auditable from the current archive because frozen arsenal "
            "usage and batter-by-pitch vulnerability inputs are not persisted."
        )
        action = "DESIGN_PREGAME_PITCH_MIX_CAPTURE_BEFORE_MODELING"
    else:
        status = "PARTIAL_CAPTURE_SCHEMA"
        reason = "Some pitch-mix lineage inputs are persisted, but the full auditable input contract is incomplete."
        action = "COMPLETE_PREGAME_PITCH_MIX_CAPTURE_SCHEMA"

    return pd.DataFrame([{
        "Status": status,
        "Projection_Rows": 0 if projections is None else int(len(projections)),
        "Handedness_Context_Rows": 0 if hand_context is None else int(len(hand_context)),
        "Pitch_Arsenal_Rows": int(len(pitch_context)),
        "Pitch_Arsenal_Eligible_Rows": int(len(eligible_pitch_context)),
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
    parser.add_argument("--pitch-context", default="data/pitch_arsenal_context_log.csv")
    parser.add_argument("--fields-output", default="data/pitch_mix_readiness_fields.csv")
    parser.add_argument("--summary-output", default="data/pitch_mix_readiness_summary.csv")
    args = parser.parse_args()

    projection_path = Path(args.projection_log)
    hand_path = Path(args.hand_context)
    pitch_path = Path(args.pitch_context)
    projections = pd.read_csv(projection_path) if projection_path.exists() else pd.DataFrame()
    hand_context = pd.read_csv(hand_path) if hand_path.exists() else pd.DataFrame()
    pitch_context = pd.read_csv(pitch_path) if pitch_path.exists() else pd.DataFrame()
    fields = build_field_audit(projections, pitch_context)
    summary = build_summary(projections, hand_context, fields, pitch_context)
    for path, frame in ((Path(args.fields_output), fields), (Path(args.summary_output), summary)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    print(summary.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()

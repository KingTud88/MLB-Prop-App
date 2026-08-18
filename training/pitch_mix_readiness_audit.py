from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

VERSION = "pitch-mix-readiness-v3-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

FAMILIES = {
    "PITCHER_PITCH_TYPES": ("pitch_mix_pitch_types", "arsenal_pitch_types", "pitch_types"),
    "PITCHER_USAGE": ("pitch_mix_usage", "arsenal_usage", "pitch_usage"),
    "BATTER_PITCH_WHIFF_RATES": ("batter_pitch_whiff_rates_json",),
    "PREGAME_CAPTURE_TIME": ("pitch_mix_captured_at_utc", "arsenal_captured_at_utc"),
    "LINEUP_FINGERPRINT": ("pitch_mix_lineup_hash", "lineup_hash"),
}

PITCH_CONTEXT_REQUIREMENTS = {
    "PITCHER_PITCH_TYPES",
    "PITCHER_USAGE",
    "PREGAME_CAPTURE_TIME",
}
WHIFF_CONTEXT_REQUIREMENTS = {"BATTER_PITCH_WHIFF_RATES"}

REQUIRED_FOR_VALIDATION = (
    "PITCHER_PITCH_TYPES",
    "PITCHER_USAGE",
    "BATTER_PITCH_WHIFF_RATES",
    "PREGAME_CAPTURE_TIME",
    "LINEUP_FINGERPRINT",
)

FIELD_COLUMNS = [
    "Requirement", "Satisfied", "Matched_Source", "Matched_Column", "Non_Null_Rows",
    "Reason", "Report_Only", "Production_Authority", "Validation_Version",
]
SUMMARY_COLUMNS = [
    "Status", "Projection_Rows", "Handedness_Context_Rows", "Pitch_Arsenal_Rows",
    "Pitch_Arsenal_Eligible_Rows", "Batter_Whiff_Rows", "Batter_Whiff_Eligible_Rows",
    "Batter_Whiff_Current_Lineage_Rows", "Satisfied_Requirements", "Required_Requirements",
    "Missing_Requirements", "Historical_Backfill_Allowed", "Reason",
    "Recommended_Action", "Report_Only", "Production_Authority", "Validation_Version",
]


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _eligible_context(frame: pd.DataFrame | None) -> pd.DataFrame:
    frame = frame.copy() if frame is not None else pd.DataFrame()
    if frame.empty or "audit_eligible" not in frame.columns:
        return frame
    return frame.loc[frame["audit_eligible"].map(_truthy)].copy()


def _context_key(row: pd.Series) -> tuple[int, int, str, str] | None:
    game_pk = pd.to_numeric(pd.Series([row.get("game_pk")]), errors="coerce").iloc[0]
    pitcher_id = pd.to_numeric(pd.Series([row.get("pitcher_id")]), errors="coerce").iloc[0]
    if pd.isna(game_pk) or pd.isna(pitcher_id):
        return None
    return (
        int(game_pk),
        int(pitcher_id),
        _clean_text(row.get("lineup_source")) or "ACTIVE_ROSTER",
        _clean_text(row.get("lineup_hash")),
    )


def _current_lineage_whiff_context(
    whiff_context: pd.DataFrame | None,
    hand_context: pd.DataFrame | None,
) -> pd.DataFrame:
    whiff = _eligible_context(whiff_context)
    hand = _eligible_context(hand_context)
    if whiff.empty or hand.empty:
        return whiff.iloc[0:0].copy()

    current_keys: set[tuple[int, int, str, str]] = set()
    for _, row in hand.iterrows():
        key = _context_key(row)
        if key is not None:
            current_keys.add(key)
    if not current_keys:
        return whiff.iloc[0:0].copy()

    mask = []
    for _, row in whiff.iterrows():
        key = _context_key(row)
        mask.append(key is not None and key in current_keys)
    return whiff.loc[pd.Series(mask, index=whiff.index, dtype=bool)].copy()


def _usable_non_null(frame: pd.DataFrame, column: str) -> int:
    if frame is None or frame.empty or column not in frame.columns:
        return 0
    values = frame[column]
    mask = values.notna()
    if values.dtype == object:
        text = values.astype(str).str.strip()
        mask = mask & text.ne("") & text.str.lower().ne("nan") & text.ne("{}")
    return int(mask.sum())


def _first_present(
    requirement: str,
    aliases: tuple[str, ...],
    projections: pd.DataFrame,
    pitch_context: pd.DataFrame,
    current_whiff_context: pd.DataFrame,
) -> tuple[str, str, int]:
    if requirement in PITCH_CONTEXT_REQUIREMENTS:
        sources = (
            ("pitch_arsenal_context", pitch_context),
            ("projection_log", projections),
        )
    elif requirement in WHIFF_CONTEXT_REQUIREMENTS:
        sources = (("batter_pitch_whiff_context", current_whiff_context),)
    else:
        sources = (
            ("projection_log", projections),
            ("pitch_arsenal_context", pitch_context),
            ("batter_pitch_whiff_context", current_whiff_context),
        )
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
    whiff_context: pd.DataFrame | None = None,
    hand_context: pd.DataFrame | None = None,
) -> pd.DataFrame:
    projections = projections.copy() if projections is not None else pd.DataFrame()
    pitch_context = _eligible_context(pitch_context)
    current_whiff_context = _current_lineage_whiff_context(whiff_context, hand_context)
    rows: list[dict[str, object]] = []
    for requirement, aliases in FAMILIES.items():
        source, matched, non_null = _first_present(
            requirement,
            aliases,
            projections,
            pitch_context,
            current_whiff_context,
        )
        satisfied = bool(matched and non_null > 0)
        if satisfied:
            reason = f"Persisted pregame field family is available through {source}:{matched}."
        elif matched:
            reason = f"Column {source}:{matched} exists but has no usable persisted values."
        else:
            reason = "No eligible current-lineage pregame source satisfies this input family."
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
    whiff_context: pd.DataFrame | None = None,
) -> pd.DataFrame:
    required = fields.loc[fields["Requirement"].isin(REQUIRED_FOR_VALIDATION)].copy()
    satisfied = int(required["Satisfied"].astype(bool).sum()) if not required.empty else 0
    needed = len(REQUIRED_FOR_VALIDATION)
    missing = required.loc[~required["Satisfied"].astype(bool), "Requirement"].astype(str).tolist()

    pitch_context = pitch_context.copy() if pitch_context is not None else pd.DataFrame()
    whiff_context = whiff_context.copy() if whiff_context is not None else pd.DataFrame()
    eligible_pitch_context = _eligible_context(pitch_context)
    eligible_whiff_context = _eligible_context(whiff_context)
    current_whiff_context = _current_lineage_whiff_context(whiff_context, hand_context)

    if satisfied == needed:
        status = "READY_FOR_REPORT_ONLY_VALIDATION_DESIGN"
        reason = (
            "Frozen pitcher arsenal, current-lineage batter Whiff% by pitch type, capture timestamps, "
            "and lineup fingerprinting are all persisted."
        )
        action = "OPEN_REPORT_ONLY_PITCH_MIX_VALIDATION_DESIGN"
    elif missing == ["BATTER_PITCH_WHIFF_RATES"]:
        status = "PITCHER_CONTEXT_READY_BATTER_CONTEXT_MISSING"
        reason = (
            "Frozen pitcher arsenal and lineup lineage are available, but no eligible current-lineage "
            "batter Whiff% by pitch type capture is persisted yet."
        )
        action = "CAPTURE_BATTER_PITCH_WHIFF_CONTEXT"
    elif satisfied == 0:
        status = "BLOCKED_CAPTURE_REQUIRED"
        reason = (
            "Pitch-mix modeling is not auditable from the current archive because frozen arsenal, "
            "batter Whiff% by pitch type, and lineup lineage inputs are not persisted."
        )
        action = "COMPLETE_PREGAME_PITCH_MIX_CAPTURE_BEFORE_MODELING"
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
        "Batter_Whiff_Rows": int(len(whiff_context)),
        "Batter_Whiff_Eligible_Rows": int(len(eligible_whiff_context)),
        "Batter_Whiff_Current_Lineage_Rows": int(len(current_whiff_context)),
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
    parser.add_argument("--whiff-context", default="data/batter_pitch_whiff_context_log.csv")
    parser.add_argument("--fields-output", default="data/pitch_mix_readiness_fields.csv")
    parser.add_argument("--summary-output", default="data/pitch_mix_readiness_summary.csv")
    args = parser.parse_args()

    projection_path = Path(args.projection_log)
    hand_path = Path(args.hand_context)
    pitch_path = Path(args.pitch_context)
    whiff_path = Path(args.whiff_context)
    projections = pd.read_csv(projection_path) if projection_path.exists() else pd.DataFrame()
    hand_context = pd.read_csv(hand_path) if hand_path.exists() else pd.DataFrame()
    pitch_context = pd.read_csv(pitch_path) if pitch_path.exists() else pd.DataFrame()
    whiff_context = pd.read_csv(whiff_path) if whiff_path.exists() else pd.DataFrame()

    fields = build_field_audit(projections, pitch_context, whiff_context, hand_context)
    summary = build_summary(projections, hand_context, fields, pitch_context, whiff_context)
    for path, frame in ((Path(args.fields_output), fields), (Path(args.summary_output), summary)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    print(summary.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.handedness_matchup_capture import COLUMNS as CONTEXT_COLUMNS

VERSION = "handedness-matchup-lineage-guard-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

GATE_COLUMNS = [
    "Status", "Total_Captures", "Pregame_Captures", "Distinct_Starts",
    "Multi_State_Starts", "Roster_To_Confirmed_Starts", "Latest_Eligible_Starts",
    "Latest_Ineligible_Starts", "Stale_Fallback_Blocked_Starts", "Reason",
    "Recommended_Action", "Report_Only", "Production_Authority", "Validation_Version",
]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _bool(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    raw = frame[column]
    if pd.api.types.is_bool_dtype(raw):
        return raw.fillna(False).astype(bool)
    return raw.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _prepared(context: pd.DataFrame) -> pd.DataFrame:
    if context is None or context.empty:
        return pd.DataFrame(columns=list(context.columns) if context is not None else CONTEXT_COLUMNS)
    work = context.copy()
    work["_game_pk"] = _num(work, "game_pk")
    work["_pitcher_id"] = _num(work, "pitcher_id")
    work["_captured"] = pd.to_datetime(work.get("hand_context_captured_at_utc"), errors="coerce", utc=True)
    work["_game_time"] = pd.to_datetime(work.get("game_time"), errors="coerce", utc=True)
    work = work.dropna(subset=["_game_pk", "_pitcher_id", "_captured", "_game_time"])
    return work.loc[work["_captured"].lt(work["_game_time"])].copy()


def build_effective_context(context: pd.DataFrame) -> pd.DataFrame:
    """Return exactly the latest pregame handedness state for each start.

    Selection intentionally happens before filtering on audit eligibility. If a later
    confirmed-lineup state is invalid, that invalid state supersedes any earlier
    roster context so downstream research cannot silently fall back to stale evidence.
    """
    original_columns = list(context.columns) if context is not None and len(context.columns) else list(CONTEXT_COLUMNS)
    work = _prepared(context)
    if work.empty:
        return pd.DataFrame(columns=original_columns)
    latest = (
        work.sort_values("_captured")
        .drop_duplicates(["_game_pk", "_pitcher_id"], keep="last")
        .copy()
    )
    for column in original_columns:
        if column not in latest.columns:
            latest[column] = np.nan
    return latest[original_columns].reset_index(drop=True)


def build_gate(context: pd.DataFrame, effective: pd.DataFrame) -> pd.DataFrame:
    pregame = _prepared(context)
    total = 0 if context is None else int(len(context))
    pregame_n = int(len(pregame))
    distinct = 0
    multi_state = 0
    roster_to_confirmed = 0
    stale_blocked = 0

    if not pregame.empty:
        groups = pregame.sort_values("_captured").groupby(["_game_pk", "_pitcher_id"], sort=False)
        distinct = int(groups.ngroups)
        for _, group in groups:
            if len(group) > 1:
                multi_state += 1
            sources = group.get("lineup_source", pd.Series("", index=group.index)).fillna("").astype(str)
            latest = group.iloc[-1]
            if sources.eq("ACTIVE_ROSTER").any() and str(latest.get("lineup_source", "")) == "CONFIRMED_LINEUP":
                roster_to_confirmed += 1
            latest_eligible = str(latest.get("audit_eligible", "")).strip().lower() in {"true", "1", "yes", "y"}
            prior = group.iloc[:-1]
            prior_eligible = False if prior.empty else bool(_bool(prior, "audit_eligible").any())
            if prior_eligible and not latest_eligible:
                stale_blocked += 1

    eligible_latest = 0 if effective is None or effective.empty else int(_bool(effective, "audit_eligible").sum())
    latest_n = 0 if effective is None else int(len(effective))
    ineligible_latest = latest_n - eligible_latest

    status = "CLEAN" if stale_blocked == 0 else "STALE_FALLBACK_BLOCKED"
    reason = (
        "Latest pregame handedness state is authoritative for each start; invalid later states cannot fall back to older roster evidence."
        if stale_blocked == 0
        else f"Blocked stale fallback on {stale_blocked} start(s) where an earlier eligible context was superseded by a later ineligible state."
    )
    return pd.DataFrame([{
        "Status": status,
        "Total_Captures": total,
        "Pregame_Captures": pregame_n,
        "Distinct_Starts": distinct,
        "Multi_State_Starts": multi_state,
        "Roster_To_Confirmed_Starts": roster_to_confirmed,
        "Latest_Eligible_Starts": eligible_latest,
        "Latest_Ineligible_Starts": ineligible_latest,
        "Stale_Fallback_Blocked_Starts": stale_blocked,
        "Reason": reason,
        "Recommended_Action": "USE_EFFECTIVE_CONTEXT_FOR_HANDEDNESS_AUDIT",
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VERSION,
    }], columns=GATE_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enforce latest-state lineage for report-only handedness matchup context.")
    parser.add_argument("--context-log", default="data/handedness_matchup_context_log.csv")
    parser.add_argument("--effective-output", default="data/handedness_matchup_effective_context.csv")
    parser.add_argument("--gate-output", default="data/handedness_matchup_lineage_gate.csv")
    args = parser.parse_args()

    source = Path(args.context_log)
    context = pd.read_csv(source) if source.exists() else pd.DataFrame(columns=CONTEXT_COLUMNS)
    effective = build_effective_context(context)
    gate = build_gate(context, effective)
    for path, frame in ((Path(args.effective_output), effective), (Path(args.gate_output), gate)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    print(gate.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()

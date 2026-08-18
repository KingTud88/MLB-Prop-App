from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.catcher_context_validation import MIN_PRIOR_STARTS

MATURITY_VERSION = "catcher-prior-maturity-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

DETAIL_COLUMNS = [
    "Catcher_ID",
    "Catcher_Name",
    "Resolved_Context_Starts",
    "Authentic_Pregame_Resolved_Starts",
    "Post_Start_Backfill_Resolved_Starts",
    "Max_Leakage_Safe_Prior_Starts_Seen",
    "Auditable_Targets_To_Date",
    "First_Auditable_Target_Date",
    "Latest_Target_Date",
    "Starts_To_Min_Prior",
    "Next_Appearance_Prior_Ready",
    "Maturity_Status",
    "Reason",
    "Min_Prior_Starts",
    "Report_Only",
    "Production_Authority",
    "Maturity_Version",
]

SUMMARY_COLUMNS = [
    "Min_Prior_Starts",
    "Known_Resolved_Catchers",
    "Resolved_Context_Starts",
    "Authentic_Pregame_Resolved_Starts",
    "Post_Start_Backfill_Resolved_Starts",
    "Current_Auditable_Starts",
    "Catchers_With_Auditable_Target",
    "Next_Appearance_Ready_No_Auditable_Yet",
    "Near_Ready_3_4",
    "Building_0_2",
    "Reason",
    "Report_Only",
    "Production_Authority",
    "Maturity_Version",
]


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _clean_text(value: object) -> str:
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "null", "nat", "<na>"} else text


def _latest_name(group: pd.DataFrame) -> str:
    work = group.copy()
    if "Game_Time_UTC" in work.columns:
        work["_time"] = pd.to_datetime(work["Game_Time_UTC"], errors="coerce", utc=True)
        work = work.sort_values("_time", kind="stable", na_position="first")
    for value in reversed(work.get("Catcher_Name", pd.Series(dtype=object)).tolist()):
        name = _clean_text(value)
        if name:
            return name
    return "Unknown"


def _status(*, resolved_contexts: int, auditable_targets: int) -> str:
    if auditable_targets > 0:
        return "AUDITABLE_EXISTS"
    if resolved_contexts >= MIN_PRIOR_STARTS:
        return "NEXT_APPEARANCE_READY"
    if resolved_contexts >= max(MIN_PRIOR_STARTS - 2, 0):
        return "NEAR_READY_3_4"
    return "BUILDING_0_2"


def _reason(status: str, resolved_contexts: int, auditable_targets: int) -> str:
    if status == "AUDITABLE_EXISTS":
        return (
            f"{auditable_targets} target start(s) already cleared the locked {MIN_PRIOR_STARTS}-prior "
            "leakage-safe catcher requirement. This remains report-only."
        )
    if status == "NEXT_APPEARANCE_READY":
        return (
            f"{resolved_contexts} resolved catcher contexts are now in the historical pool. A future catcher "
            f"appearance may clear the locked {MIN_PRIOR_STARTS}-prior requirement if all chronology rules are "
            "satisfied at that future capture; no past target becomes auditable retroactively."
        )
    needed = max(MIN_PRIOR_STARTS - resolved_contexts, 0)
    if status == "NEAR_READY_3_4":
        return (
            f"{resolved_contexts} resolved catcher contexts are in the pool; {needed} more are needed to reach "
            f"the locked {MIN_PRIOR_STARTS}-prior threshold for a possible future auditable target."
        )
    return (
        f"{resolved_contexts} resolved catcher contexts are in the pool; {needed} more are needed to reach "
        f"the locked {MIN_PRIOR_STARTS}-prior threshold for a possible future auditable target."
    )


def build_maturity(detail: pd.DataFrame) -> pd.DataFrame:
    """Summarize catcher evidence maturity without changing validation authority.

    The existing catcher validator remains authoritative for target-level auditability.
    This diagnostic only describes the resolved prior pool available to a *future*
    catcher appearance. It never makes a historical target auditable retroactively.
    """
    if detail is None or detail.empty or "Catcher_ID" not in detail.columns:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    work = detail.copy()
    work["_catcher_id"] = pd.to_numeric(work["Catcher_ID"], errors="coerce")
    work["_actual_k"] = pd.to_numeric(work.get("Actual_Strikeouts"), errors="coerce")
    work["_prior"] = pd.to_numeric(work.get("Prior_Catcher_Starts"), errors="coerce")
    work["_auditable"] = work.get("Candidate_Auditable", pd.Series(False, index=work.index)).map(_truthy)
    work["_lineage"] = work.get("Lineage", pd.Series("", index=work.index)).fillna("").astype(str)
    work["_game_date"] = work.get("Game_Date", pd.Series("", index=work.index)).fillna("").astype(str)
    work = work.loc[work["_catcher_id"].notna()].copy()
    if work.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    rows: list[dict[str, object]] = []
    for catcher_id, group in work.groupby("_catcher_id", sort=False):
        resolved = group.loc[group["_actual_k"].notna()].copy()
        if resolved.empty:
            continue

        # Each detail row represents one archived pitcher start. The pool count is
        # a future-maturity diagnostic only; target-level chronology is still
        # enforced by catcher_context_validation.py.
        resolved_contexts = int(len(resolved))
        authentic = int(resolved["_lineage"].eq("PRE_GAME_CAPTURE").sum())
        backfilled = int(resolved["_lineage"].eq("POST_START_BACKFILL").sum())
        prior_values = pd.to_numeric(group["_prior"], errors="coerce").dropna()
        max_prior = int(prior_values.max()) if not prior_values.empty else 0
        audit = group.loc[group["_auditable"]].copy()
        auditable_targets = int(len(audit))
        first_auditable = ""
        if auditable_targets:
            dated = audit["_game_date"].replace("", np.nan).dropna().astype(str)
            first_auditable = str(dated.min()) if not dated.empty else ""
        dated_all = group["_game_date"].replace("", np.nan).dropna().astype(str)
        latest_target = str(dated_all.max()) if not dated_all.empty else ""
        starts_to_min = max(int(MIN_PRIOR_STARTS) - resolved_contexts, 0)
        status = _status(resolved_contexts=resolved_contexts, auditable_targets=auditable_targets)
        rows.append({
            "Catcher_ID": int(catcher_id),
            "Catcher_Name": _latest_name(group),
            "Resolved_Context_Starts": resolved_contexts,
            "Authentic_Pregame_Resolved_Starts": authentic,
            "Post_Start_Backfill_Resolved_Starts": backfilled,
            "Max_Leakage_Safe_Prior_Starts_Seen": max_prior,
            "Auditable_Targets_To_Date": auditable_targets,
            "First_Auditable_Target_Date": first_auditable,
            "Latest_Target_Date": latest_target,
            "Starts_To_Min_Prior": starts_to_min,
            "Next_Appearance_Prior_Ready": bool(resolved_contexts >= MIN_PRIOR_STARTS),
            "Maturity_Status": status,
            "Reason": _reason(status, resolved_contexts, auditable_targets),
            "Min_Prior_Starts": int(MIN_PRIOR_STARTS),
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Maturity_Version": MATURITY_VERSION,
        })

    if not rows:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    output = pd.DataFrame(rows, columns=DETAIL_COLUMNS)
    order = {
        "AUDITABLE_EXISTS": 0,
        "NEXT_APPEARANCE_READY": 1,
        "NEAR_READY_3_4": 2,
        "BUILDING_0_2": 3,
    }
    output["_status_order"] = output["Maturity_Status"].map(order).fillna(9)
    return output.sort_values(
        ["_status_order", "Resolved_Context_Starts", "Catcher_Name"],
        ascending=[True, False, True],
        kind="stable",
    ).drop(columns="_status_order").reset_index(drop=True)


def summarize_maturity(maturity: pd.DataFrame) -> pd.DataFrame:
    if maturity is None or maturity.empty:
        row = {
            "Min_Prior_Starts": int(MIN_PRIOR_STARTS),
            "Known_Resolved_Catchers": 0,
            "Resolved_Context_Starts": 0,
            "Authentic_Pregame_Resolved_Starts": 0,
            "Post_Start_Backfill_Resolved_Starts": 0,
            "Current_Auditable_Starts": 0,
            "Catchers_With_Auditable_Target": 0,
            "Next_Appearance_Ready_No_Auditable_Yet": 0,
            "Near_Ready_3_4": 0,
            "Building_0_2": 0,
            "Reason": (
                f"No resolved catcher context is available yet. The locked prior threshold remains {MIN_PRIOR_STARTS}."
            ),
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Maturity_Version": MATURITY_VERSION,
        }
        return pd.DataFrame([row], columns=SUMMARY_COLUMNS)

    status = maturity["Maturity_Status"].astype(str)
    resolved = int(pd.to_numeric(maturity["Resolved_Context_Starts"], errors="coerce").fillna(0).sum())
    authentic = int(pd.to_numeric(maturity["Authentic_Pregame_Resolved_Starts"], errors="coerce").fillna(0).sum())
    backfilled = int(pd.to_numeric(maturity["Post_Start_Backfill_Resolved_Starts"], errors="coerce").fillna(0).sum())
    auditable = int(pd.to_numeric(maturity["Auditable_Targets_To_Date"], errors="coerce").fillna(0).sum())
    row = {
        "Min_Prior_Starts": int(MIN_PRIOR_STARTS),
        "Known_Resolved_Catchers": int(len(maturity)),
        "Resolved_Context_Starts": resolved,
        "Authentic_Pregame_Resolved_Starts": authentic,
        "Post_Start_Backfill_Resolved_Starts": backfilled,
        "Current_Auditable_Starts": auditable,
        "Catchers_With_Auditable_Target": int(status.eq("AUDITABLE_EXISTS").sum()),
        "Next_Appearance_Ready_No_Auditable_Yet": int(status.eq("NEXT_APPEARANCE_READY").sum()),
        "Near_Ready_3_4": int(status.eq("NEAR_READY_3_4").sum()),
        "Building_0_2": int(status.eq("BUILDING_0_2").sum()),
        "Reason": (
            f"Operational maturity only. Target auditability remains controlled by catcher-context-walkforward-v1 "
            f"with the locked {MIN_PRIOR_STARTS}-prior chronological requirement; no production activation is authorized."
        ),
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Maturity_Version": MATURITY_VERSION,
    }
    return pd.DataFrame([row], columns=SUMMARY_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only catcher prior-sample maturity diagnostic.")
    parser.add_argument(
        "--validation-detail",
        type=Path,
        default=Path("data/catcher_context_validation_detail.csv"),
    )
    parser.add_argument("--detail", type=Path, default=Path("data/catcher_prior_maturity.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/catcher_prior_maturity_summary.csv"))
    args = parser.parse_args()

    detail = pd.read_csv(args.validation_detail) if args.validation_detail.exists() else pd.DataFrame()
    maturity = build_maturity(detail)
    summary = summarize_maturity(maturity)
    for path, frame in ((args.detail, maturity), (args.summary, summary)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    print(summary.to_string(index=False))
    print(
        f"catcher_prior_maturity_version={MATURITY_VERSION} min_prior_starts={MIN_PRIOR_STARTS} "
        "report_only=true production_authority=NONE"
    )


if __name__ == "__main__":
    main()

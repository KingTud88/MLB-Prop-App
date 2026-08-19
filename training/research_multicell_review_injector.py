from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from training.calibration_shadow_gate import (
    GATE_VERSION as CALIBRATION_GATE_VERSION,
    MILESTONES as CALIBRATION_MILESTONES,
    MIN_OOS_STARTS as CALIBRATION_MIN_OOS_STARTS,
)
from training.live_role_shadow_gate import (
    GATE_VERSION as ROLE_GATE_VERSION,
    MIN_RESOLVED_STARTS as ROLE_MIN_RESOLVED_STARTS,
    REQUIRED_METRICS,
    REQUIRED_ROLES,
)
from training.research_manual_review_packet import (
    AUTOMATIC_DECISION_ALLOWED as PACKET_AUTOMATIC_DECISION_ALLOWED,
    NO_AUTO_PROMOTION as PACKET_NO_AUTO_PROMOTION,
    PACKET_COLUMNS,
    PRODUCTION_AUTHORITY as PACKET_PRODUCTION_AUTHORITY,
    REPORT_ONLY as PACKET_REPORT_ONLY,
    VERSION as PACKET_VERSION,
    build_packet_summary,
)

VERSION = "research-multicell-review-injector-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True
AUTOMATIC_DECISION_ALLOWED = False
REVIEW_TRIGGER = "MULTICELL_MATURITY_TRANSITION"


def _clean(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _integer(value: object) -> int | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else int(parsed)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def _packet_contract_ok() -> bool:
    return bool(
        PACKET_REPORT_ONLY
        and PACKET_PRODUCTION_AUTHORITY == PRODUCTION_AUTHORITY
        and PACKET_NO_AUTO_PROMOTION
        and PACKET_AUTOMATIC_DECISION_ALLOWED is False
    )


def _source_version_matches(frame: pd.DataFrame, expected: str) -> bool:
    if frame is None or frame.empty or "Gate_Version" not in frame.columns:
        return False
    versions = {_clean(value) for value in frame["Gate_Version"] if _clean(value)}
    return versions == {expected}


def _calibration_candidate(frame: pd.DataFrame) -> dict[str, object] | None:
    required = tuple(int(value) for value in CALIBRATION_MILESTONES)
    required_set = set(required)
    if frame is None or frame.empty:
        return None
    needed = {"Milestone", "OOS_Starts", "Promotion_Gate_Status", "Gate_Version"}
    if not needed.issubset(frame.columns) or not _source_version_matches(frame, CALIBRATION_GATE_VERSION):
        return None

    milestones = pd.to_numeric(frame["Milestone"], errors="coerce")
    valid = frame.loc[milestones.notna()].copy()
    valid["_Milestone_Key"] = milestones.loc[milestones.notna()].astype(int)
    if len(valid) != len(required) or set(valid["_Milestone_Key"]) != required_set:
        return None
    if valid["_Milestone_Key"].duplicated().any():
        return None

    starts = pd.to_numeric(valid["OOS_Starts"], errors="coerce")
    if starts.isna().any() or bool((starts < CALIBRATION_MIN_OOS_STARTS).any()):
        return None

    ordered = valid.sort_values("_Milestone_Key")
    statuses = ordered["Promotion_Gate_Status"].fillna("").astype(str).str.strip().str.upper()
    fail_count = int(statuses.eq("FAIL").sum())
    pass_count = int(statuses.eq("PASS").sum())
    total = len(required)
    status = "FAIL" if fail_count else ("PASS" if pass_count == total else "MIXED")
    min_starts = int(starts.min())
    reasons = "; ".join(
        sorted({_clean(value) for value in ordered.get("Reasons", pd.Series(dtype=object)) if _clean(value)})
    )
    secondary = "; ".join(
        f"{int(row['_Milestone_Key'])}:{_clean(row.get('Promotion_Gate_Status'))}"
        for _, row in ordered.iterrows()
    )
    return {
        "Lane": "Calibration Shadow",
        "Category": "CALIBRATION",
        "Status": status,
        "Evidence_Direction": f"milestones_pass={pass_count}/{total}; milestones_fail={fail_count}/{total}",
        "Current_Starts": min_starts,
        "Required_Starts": int(CALIBRATION_MIN_OOS_STARTS),
        "Breadth_Label": "MILESTONE_CELLS",
        "Current_Breadth": total,
        "Required_Breadth": total,
        "Secondary_Progress": f"mature_cells={total}/{total}; {secondary}",
        "Recommended_Action": "MANUAL_REVIEW_MULTICELL_CALIBRATION_EVIDENCE_ONLY",
        "Source_Path": "data/calibration_shadow_gate.csv",
        "Source_Version": CALIBRATION_GATE_VERSION,
        "Source_Reason": (
            f"All {total} frozen calibration milestone cells meet the existing "
            f"{CALIBRATION_MIN_OOS_STARTS}-OOS-start sample requirement."
            + (f" Source reasons: {reasons}" if reasons else "")
        ),
    }


def _role_candidate(frame: pd.DataFrame) -> dict[str, object] | None:
    required_keys = {(str(role), str(metric)) for role in REQUIRED_ROLES for metric in REQUIRED_METRICS}
    if frame is None or frame.empty:
        return None
    needed = {"Role", "Metric", "Resolved_Starts", "Live_Gate_Status", "Gate_Version"}
    if not needed.issubset(frame.columns) or not _source_version_matches(frame, ROLE_GATE_VERSION):
        return None

    valid = frame.copy()
    valid["_Role_Key"] = valid["Role"].fillna("").astype(str).str.strip()
    valid["_Metric_Key"] = valid["Metric"].fillna("").astype(str).str.strip()
    keys = list(zip(valid["_Role_Key"], valid["_Metric_Key"]))
    if len(valid) != len(required_keys) or set(keys) != required_keys or len(set(keys)) != len(keys):
        return None

    starts = pd.to_numeric(valid["Resolved_Starts"], errors="coerce")
    if starts.isna().any() or bool((starts < ROLE_MIN_RESOLVED_STARTS).any()):
        return None

    order_role = {str(role): index for index, role in enumerate(REQUIRED_ROLES)}
    order_metric = {str(metric): index for index, metric in enumerate(REQUIRED_METRICS)}
    valid["_Role_Order"] = valid["_Role_Key"].map(order_role)
    valid["_Metric_Order"] = valid["_Metric_Key"].map(order_metric)
    ordered = valid.sort_values(["_Role_Order", "_Metric_Order"])

    statuses = ordered["Live_Gate_Status"].fillna("").astype(str).str.strip().str.upper()
    fail_count = int(statuses.eq("FAIL").sum())
    pass_count = int(statuses.eq("PASS").sum())
    total = len(required_keys)
    status = "FAIL" if fail_count else ("PASS" if pass_count == total else "MIXED")
    min_starts = int(starts.min())
    reasons = "; ".join(
        sorted({_clean(value) for value in ordered.get("Reasons", pd.Series(dtype=object)) if _clean(value)})
    )
    secondary = "; ".join(
        f"{_clean(row.get('Role'))}/{_clean(row.get('Metric'))}:{_clean(row.get('Live_Gate_Status'))}"
        for _, row in ordered.iterrows()
    )
    return {
        "Lane": "Starter Role Live Shadow",
        "Category": "WORKLOAD",
        "Status": status,
        "Evidence_Direction": f"cells_pass={pass_count}/{total}; cells_fail={fail_count}/{total}",
        "Current_Starts": min_starts,
        "Required_Starts": int(ROLE_MIN_RESOLVED_STARTS),
        "Breadth_Label": "ROLE_METRIC_CELLS",
        "Current_Breadth": total,
        "Required_Breadth": total,
        "Secondary_Progress": f"mature_cells={total}/{total}; {secondary}",
        "Recommended_Action": "MANUAL_REVIEW_MULTICELL_ROLE_EVIDENCE_ONLY",
        "Source_Path": "data/live_role_shadow_gate.csv",
        "Source_Version": ROLE_GATE_VERSION,
        "Source_Reason": (
            f"All {total} frozen starter-role role/metric cells meet the existing "
            f"{ROLE_MIN_RESOLVED_STARTS}-resolved-start sample requirement."
            + (f" Source reasons: {reasons}" if reasons else "")
        ),
    }


def _already_queued(queue: pd.DataFrame, lane: str, source_version: str) -> bool:
    if queue is None or queue.empty:
        return False
    lane_values = queue.get("Lane", pd.Series(index=queue.index, dtype=object)).astype(str)
    triggers = queue.get("Review_Trigger", pd.Series(index=queue.index, dtype=object)).astype(str)
    versions = queue.get("Source_Version", pd.Series(index=queue.index, dtype=object)).astype(str)
    return bool(
        (
            lane_values.eq(str(lane))
            & triggers.eq(REVIEW_TRIGGER)
            & versions.eq(str(source_version))
        ).any()
    )


def _already_in_current_packet(packet: pd.DataFrame, lane: str) -> bool:
    if packet is None or packet.empty:
        return False
    lane_values = packet.get("Lane", pd.Series(index=packet.index, dtype=object)).astype(str)
    return bool(lane_values.eq(str(lane)).any())


def _packet_row(candidate: dict[str, object], refresh_at_utc: str) -> dict[str, object]:
    current_starts = _integer(candidate.get("Current_Starts"))
    required_starts = _integer(candidate.get("Required_Starts"))
    current_breadth = _integer(candidate.get("Current_Breadth"))
    required_breadth = _integer(candidate.get("Required_Breadth"))
    starts_remaining = (
        max(0, required_starts - current_starts)
        if current_starts is not None and required_starts is not None
        else None
    )
    breadth_remaining = (
        max(0, required_breadth - current_breadth)
        if current_breadth is not None and required_breadth is not None
        else None
    )

    row = {
        "Refresh_At_UTC": refresh_at_utc,
        "Lane": candidate.get("Lane"),
        "Category": candidate.get("Category"),
        "Review_Trigger": REVIEW_TRIGGER,
        "Previous_Status": candidate.get("Status"),
        "Status": candidate.get("Status"),
        "Previous_Ready_For_Manual_Review": False,
        "Ready_For_Manual_Review": True,
        "Previous_Evidence_Direction": candidate.get("Evidence_Direction"),
        "Evidence_Direction": candidate.get("Evidence_Direction"),
        "Previous_Starts": None,
        "Current_Starts": current_starts,
        "Required_Starts": required_starts,
        "Starts_Remaining": starts_remaining,
        "Previous_Days": None,
        "Current_Days": None,
        "Required_Days": None,
        "Days_Remaining": None,
        "Breadth_Label": candidate.get("Breadth_Label"),
        "Previous_Breadth": None,
        "Current_Breadth": current_breadth,
        "Required_Breadth": required_breadth,
        "Breadth_Remaining": breadth_remaining,
        "Previous_Secondary_Progress": "",
        "Secondary_Progress": candidate.get("Secondary_Progress"),
        "Previous_Recommended_Action": "",
        "Recommended_Action": candidate.get("Recommended_Action"),
        "Source_Path": candidate.get("Source_Path"),
        "Source_Version": candidate.get("Source_Version"),
        "Source_Reason": candidate.get("Source_Reason"),
        "Change_Summary": (
            f"Multicell_Maturity:False->True; "
            f"Current_Starts:{current_starts}; Required_Starts:{required_starts}; "
            f"Source_Version:{candidate.get('Source_Version')}; Injector_Version:{VERSION}"
        ),
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
        "Human_Review_Required": True,
        "Control_Violation": False,
        "Packet_Version": PACKET_VERSION,
    }
    return {column: row.get(column) for column in PACKET_COLUMNS}


def inject_multicell_reviews(
    packet: pd.DataFrame,
    queue: pd.DataFrame,
    calibration_gate: pd.DataFrame,
    role_gate: pd.DataFrame,
    refresh_at_utc: str,
) -> pd.DataFrame:
    if not _packet_contract_ok():
        raise ValueError("Manual-review packet contract is not report-only/NONE/no-auto-promotion.")
    frame = packet.copy() if packet is not None else pd.DataFrame(columns=PACKET_COLUMNS)
    for column in PACKET_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    frame = frame[PACKET_COLUMNS]

    if not refresh_at_utc:
        return frame.reset_index(drop=True)

    candidates = [
        _calibration_candidate(calibration_gate),
        _role_candidate(role_gate),
    ]
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        if candidate is None:
            continue
        lane = str(candidate["Lane"])
        source_version = str(candidate["Source_Version"])
        if _already_in_current_packet(frame, lane):
            continue
        if _already_queued(queue, lane, source_version):
            continue
        rows.append(_packet_row(candidate, refresh_at_utc))

    if rows:
        frame = pd.concat([frame, pd.DataFrame(rows, columns=PACKET_COLUMNS)], ignore_index=True)
    return frame[PACKET_COLUMNS].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inject one-time report-only manual review cases for mature multi-cell research gates."
    )
    parser.add_argument("--packet", default="data/research_manual_review_packet.csv")
    parser.add_argument("--packet-summary", default="data/research_manual_review_packet_summary.csv")
    parser.add_argument("--queue", default="data/research_manual_review_queue.csv")
    parser.add_argument("--digest", default="data/research_evidence_transition_digest.csv")
    parser.add_argument("--calibration-gate", default="data/calibration_shadow_gate.csv")
    parser.add_argument("--role-gate", default="data/live_role_shadow_gate.csv")
    parser.add_argument("--refresh-at-utc", default=os.getenv("RESEARCH_REFRESH_AT_UTC"))
    args = parser.parse_args()

    refresh_at = args.refresh_at_utc or ""
    packet_path = Path(args.packet)
    packet = _read_csv(packet_path)
    queue = _read_csv(Path(args.queue))
    calibration = _read_csv(Path(args.calibration_gate))
    role = _read_csv(Path(args.role_gate))
    digest = _read_csv(Path(args.digest))

    injected = inject_multicell_reviews(packet, queue, calibration, role, refresh_at)
    summary = build_packet_summary(injected, digest, refresh_at)

    packet_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path = Path(args.packet_summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    injected.to_csv(packet_path, index=False)
    summary.to_csv(summary_path, index=False)

    added = len(injected) - len(packet)
    print(injected.to_string(index=False) if not injected.empty else "NO_MANUAL_REVIEW_PACKET_ROWS")
    print(summary.to_string(index=False))
    print(
        f"multicell_reviews_added={added} report_only={REPORT_ONLY} "
        f"production_authority={PRODUCTION_AUTHORITY} no_auto_promotion={NO_AUTO_PROMOTION} "
        f"automatic_decision_allowed={AUTOMATIC_DECISION_ALLOWED} injector_version={VERSION}"
    )


if __name__ == "__main__":
    main()

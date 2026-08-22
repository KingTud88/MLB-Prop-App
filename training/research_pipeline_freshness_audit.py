from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from training.research_evidence_command_center import build_command_center
from training.research_promotion_command_center import build_promotion_command_center
from training.research_governance_v2 import (
    MANIFEST_COLUMNS as GOVERNANCE_MANIFEST_COLUMNS,
    UNCERTAINTY_COLUMNS as GOVERNANCE_UNCERTAINTY_COLUMNS,
    SUMMARY_COLUMNS as GOVERNANCE_SUMMARY_COLUMNS,
    build_governance_summary,
    build_hypothesis_manifest,
    build_uncertainty_report,
)
from training.research_evidence_history import fingerprint_row
from training.research_evidence_transition_digest import (
    DIGEST_COLUMNS,
    SUMMARY_COLUMNS as DIGEST_SUMMARY_COLUMNS,
    build_digest_summary,
    build_transition_digest,
)
from training.research_manual_review_packet import (
    PACKET_COLUMNS,
    SUMMARY_COLUMNS as PACKET_SUMMARY_COLUMNS,
    build_manual_review_packet,
    build_packet_summary,
)
from training.research_manual_review_queue import (
    QUEUE_COLUMNS,
    SUMMARY_COLUMNS as QUEUE_SUMMARY_COLUMNS,
    append_review_queue,
    build_queue_summary,
)
from training.research_multicell_review_injector import inject_multicell_reviews

VERSION = "research-pipeline-freshness-v4-governance-v2-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_AUTO_PROMOTION = True
GOVERNANCE_UNCERTAINTY_SIGNATURE_DIGITS = 12

STAGE_COLUMNS = [
    "Stage", "Depends_On", "Freshness_Status", "Current_Items", "Expected_Items",
    "Mismatch_Items", "Detail", "Report_Only", "Production_Authority",
    "No_Auto_Promotion", "Freshness_Version",
]

SUMMARY_COLUMNS = [
    "Overall_Status", "Total_Stages", "Current_Stages", "Stale_Stages",
    "Missing_Stages", "Control_Violation_Stages", "All_Report_Only",
    "All_Production_Authority_None", "No_Auto_Promotion", "Freshness_Version",
]

CURRENT = "CURRENT"
SOURCE_NEWER = "SOURCE_NEWER_THAN_DERIVED"
DERIVED_DRIFT = "DERIVED_DRIFT"
DERIVED_MISSING = "DERIVED_MISSING"
SOURCE_MISSING = "SOURCE_MISSING"
UPSTREAM_STALE = "UPSTREAM_STALE"
CONTROL_VIOLATION = "CONTROL_VIOLATION"


def _clean(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _truthy(value: object) -> bool:
    return _clean(value).lower() in {"true", "1", "yes", "y"}


def _normalize(value: object, float_significant_digits: int | None = None) -> object:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if number.is_integer():
            return int(number)
        if float_significant_digits is not None:
            return float(f"{number:.{float_significant_digits}g}")
        return number
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        number = float(text)
        if number.is_integer():
            return int(number)
        if float_significant_digits is not None:
            return float(f"{number:.{float_significant_digits}g}")
        return number
    except ValueError:
        return text


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def _frame_signature(
    frame: pd.DataFrame,
    columns: list[str],
    sort_columns: list[str] | None = None,
    float_significant_digits: int | None = None,
) -> tuple[tuple[object, ...], ...]:
    if frame is None or frame.empty:
        return tuple()
    working = frame.copy()
    for column in columns:
        if column not in working.columns:
            working[column] = None
    if sort_columns:
        present = [column for column in sort_columns if column in working.columns]
        if present:
            working = working.sort_values(present, kind="stable", na_position="last")
    return tuple(
        tuple(_normalize(row.get(column), float_significant_digits) for column in columns)
        for _, row in working[columns].iterrows()
    )


def _contract_violation(frame: pd.DataFrame) -> bool:
    if frame is None or frame.empty:
        return False
    report_only = frame.get("Report_Only", pd.Series(index=frame.index, dtype=object)).map(_truthy)
    authority = frame.get("Production_Authority", pd.Series(index=frame.index, dtype=object)).map(_clean).str.upper()
    no_auto = frame.get("No_Auto_Promotion", pd.Series(index=frame.index, dtype=object)).map(_truthy)
    return bool((~report_only | ~authority.eq("NONE") | ~no_auto).any())


def _stage(stage: str, depends_on: str, status: str, current_items: int, expected_items: int, mismatch_items: int, detail: str) -> dict[str, object]:
    return {
        "Stage": stage,
        "Depends_On": depends_on,
        "Freshness_Status": status,
        "Current_Items": current_items,
        "Expected_Items": expected_items,
        "Mismatch_Items": mismatch_items,
        "Detail": detail,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Freshness_Version": VERSION,
    }


def _lane_fingerprints(frame: pd.DataFrame) -> dict[str, str]:
    if frame is None or frame.empty or "Lane" not in frame.columns:
        return {}
    result: dict[str, str] = {}
    for _, row in frame.iterrows():
        lane = _clean(row.get("Lane"))
        if lane:
            result[lane] = fingerprint_row(row)
    return result


def _latest_history_fingerprints(history: pd.DataFrame) -> dict[str, str]:
    if history is None or history.empty or "Lane" not in history.columns:
        return {}
    result: dict[str, str] = {}
    for lane, group in history.groupby("Lane", sort=False):
        fingerprint = _clean(group.iloc[-1].get("Fingerprint"))
        if fingerprint:
            result[str(lane)] = fingerprint
    return result


def _fingerprint_mismatches(expected: dict[str, str], current: dict[str, str]) -> list[str]:
    lanes = sorted(set(expected) | set(current))
    return [lane for lane in lanes if expected.get(lane) != current.get(lane)]


def _iso_max(values: pd.Series) -> pd.Timestamp | None:
    if values is None or values.empty:
        return None
    parsed = pd.to_datetime(values, utc=True, errors="coerce").dropna()
    return None if parsed.empty else parsed.max()


def _queue_before_refresh(queue: pd.DataFrame, refresh: str) -> pd.DataFrame:
    if queue is None or queue.empty:
        return pd.DataFrame(columns=QUEUE_COLUMNS)
    if not refresh or "Queued_At_UTC" not in queue.columns:
        return pd.DataFrame(columns=queue.columns)
    refresh_ts = pd.to_datetime(refresh, utc=True, errors="coerce")
    if pd.isna(refresh_ts):
        return pd.DataFrame(columns=queue.columns)
    queued = pd.to_datetime(queue["Queued_At_UTC"], utc=True, errors="coerce")
    return queue.loc[queued.notna() & queued.lt(refresh_ts)].copy().reset_index(drop=True)


def _compare_center_stage(root: Path, expected: pd.DataFrame, filename: str, stage_name: str, depends_on: str) -> tuple[dict[str, object], pd.DataFrame]:
    saved = _read_csv(root / filename)
    source_missing = int(expected.get("Status", pd.Series(dtype=object)).astype(str).eq(SOURCE_MISSING).sum()) if not expected.empty else 0
    expected_fp = _lane_fingerprints(expected)
    saved_fp = _lane_fingerprints(saved)
    mismatches = _fingerprint_mismatches(expected_fp, saved_fp)
    if source_missing:
        status = SOURCE_MISSING
        detail = f"{source_missing} registered source(s) are missing; no reconstruction is allowed."
    elif saved.empty:
        status = DERIVED_MISSING
        detail = f"Committed {filename} artifact is missing or unreadable."
    elif _contract_violation(saved):
        status = CONTROL_VIOLATION
        detail = f"Committed {filename} violates the report-only authority contract."
    elif mismatches:
        status = SOURCE_NEWER
        detail = "Recomputed current-source rows differ for: " + ", ".join(mismatches)
    else:
        status = CURRENT
        detail = f"Committed {filename} exactly matches fresh recomputation from registered sources."
    return _stage(stage_name, depends_on, status, len(saved_fp), len(expected_fp), len(mismatches), detail), saved


def _read_governance_artifact(path: Path, required_columns: list[str]) -> tuple[bool, pd.DataFrame]:
    if not path.exists():
        return False, pd.DataFrame(columns=required_columns)
    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return False, pd.DataFrame(columns=required_columns)
    return set(required_columns).issubset(frame.columns), frame


def _governance_control_violation(manifest: pd.DataFrame, uncertainty: pd.DataFrame, summary: pd.DataFrame) -> bool:
    if _contract_violation(manifest) or _contract_violation(summary):
        return True
    if uncertainty is not None and not uncertainty.empty:
        report_only = uncertainty.get("Report_Only", pd.Series(index=uncertainty.index, dtype=object)).map(_truthy)
        authority = uncertainty.get("Production_Authority", pd.Series(index=uncertainty.index, dtype=object)).map(_clean).str.upper()
        if bool((~report_only | ~authority.eq("NONE")).any()):
            return True
    if summary is not None and not summary.empty:
        automatic = summary.get("Automatic_Decision_Allowed", pd.Series(index=summary.index, dtype=object)).map(_truthy)
        if bool(automatic.any()):
            return True
    return False


def _build_governance_stage(root: Path, expected_center: pd.DataFrame, promotion_status: str) -> dict[str, object]:
    manifest_ok, manifest = _read_governance_artifact(root / "research_hypothesis_manifest.csv", GOVERNANCE_MANIFEST_COLUMNS)
    uncertainty_ok, uncertainty = _read_governance_artifact(root / "research_uncertainty_v2.csv", GOVERNANCE_UNCERTAINTY_COLUMNS)
    summary_ok, summary = _read_governance_artifact(root / "research_governance_v2_summary.csv", GOVERNANCE_SUMMARY_COLUMNS)
    current_items = int(len(manifest) + len(uncertainty) + len(summary))

    if promotion_status != CURRENT:
        return _stage(
            "GOVERNANCE_V2", "PROMOTION_COMMAND_CENTER", UPSTREAM_STALE, current_items, 0, 1,
            "Promotion command center is not current, so Governance v2 artifacts cannot be certified fresh.",
        )

    expected_manifest = build_hypothesis_manifest(expected_center)
    expected_uncertainty = build_uncertainty_report(root)
    expected_summary = build_governance_summary(expected_center, expected_manifest, expected_uncertainty)
    expected_items = int(len(expected_manifest) + len(expected_uncertainty) + len(expected_summary))

    missing = [
        name for name, ok in (
            ("research_hypothesis_manifest.csv", manifest_ok),
            ("research_uncertainty_v2.csv", uncertainty_ok),
            ("research_governance_v2_summary.csv", summary_ok),
        ) if not ok
    ]
    if missing:
        return _stage(
            "GOVERNANCE_V2", "PROMOTION_COMMAND_CENTER", DERIVED_MISSING, current_items, expected_items, len(missing),
            "Governance v2 artifact(s) are missing or unreadable: " + ", ".join(missing),
        )
    if _governance_control_violation(manifest, uncertainty, summary):
        return _stage(
            "GOVERNANCE_V2", "PROMOTION_COMMAND_CENTER", CONTROL_VIOLATION, current_items, expected_items, 1,
            "Governance v2 artifacts violate report-only, Production Authority NONE, no-auto-promotion, or automatic-decision controls.",
        )

    manifest_match = _frame_signature(manifest, GOVERNANCE_MANIFEST_COLUMNS, ["Lane"]) == _frame_signature(expected_manifest, GOVERNANCE_MANIFEST_COLUMNS, ["Lane"])
    uncertainty_match = _frame_signature(
        uncertainty,
        GOVERNANCE_UNCERTAINTY_COLUMNS,
        ["Lane", "Segment", "Metric"],
        float_significant_digits=GOVERNANCE_UNCERTAINTY_SIGNATURE_DIGITS,
    ) == _frame_signature(
        expected_uncertainty,
        GOVERNANCE_UNCERTAINTY_COLUMNS,
        ["Lane", "Segment", "Metric"],
        float_significant_digits=GOVERNANCE_UNCERTAINTY_SIGNATURE_DIGITS,
    )
    summary_match = _frame_signature(summary, GOVERNANCE_SUMMARY_COLUMNS) == _frame_signature(expected_summary, GOVERNANCE_SUMMARY_COLUMNS)
    mismatch = int(not manifest_match) + int(not uncertainty_match) + int(not summary_match)
    status = DERIVED_DRIFT if mismatch else CURRENT
    detail = (
        "Governance v2 manifest, uncertainty diagnostics, or summary do not reproduce from current all-lane evidence."
        if mismatch else
        "Governance v2 manifest, uncertainty diagnostics, and summary exactly reproduce from current all-lane evidence."
    )
    return _stage("GOVERNANCE_V2", "PROMOTION_COMMAND_CENTER", status, current_items, expected_items, mismatch, detail)


def _build_history_stage(root: Path, expected_center: pd.DataFrame, upstream_status: str) -> tuple[dict[str, object], pd.DataFrame]:
    history = _read_csv(root / "research_evidence_history.csv")
    expected_fp = _lane_fingerprints(expected_center)
    current_fp = _latest_history_fingerprints(history)
    mismatches = _fingerprint_mismatches(expected_fp, current_fp)
    if upstream_status != CURRENT:
        status = UPSTREAM_STALE
        detail = "Promotion command center is not current, so all-lane history cannot be certified fresh."
    elif history.empty:
        status = DERIVED_MISSING
        detail = "Change-only history is missing or unreadable."
    elif _contract_violation(history):
        status = CONTROL_VIOLATION
        detail = "History contains a row that violates the report-only authority contract."
    elif mismatches:
        status = SOURCE_NEWER
        detail = "Latest history fingerprint is behind current promotion evidence for: " + ", ".join(mismatches)
    else:
        status = CURRENT
        detail = "Latest history fingerprint for every registered promotion lane matches current evidence."
    return _stage("HISTORY", "PROMOTION_COMMAND_CENTER", status, len(current_fp), len(expected_fp), len(mismatches), detail), history


def _build_digest_stage(root: Path, history: pd.DataFrame, history_status: str) -> tuple[dict[str, object], pd.DataFrame, str]:
    digest = _read_csv(root / "research_evidence_transition_digest.csv")
    summary = _read_csv(root / "research_evidence_transition_digest_summary.csv")
    refresh = _clean(summary.iloc[0].get("Refresh_At_UTC")) if not summary.empty else ""
    if history_status != CURRENT:
        return _stage("TRANSITION_DIGEST", "HISTORY", UPSTREAM_STALE, len(digest), len(digest), 1, "History is not current, so the exact-refresh digest cannot be certified fresh."), digest, refresh
    if summary.empty or not refresh:
        return _stage("TRANSITION_DIGEST", "HISTORY", DERIVED_MISSING, len(digest), 0, 1, "Digest summary is missing or has no refresh ID."), digest, refresh
    if _contract_violation(digest) or _contract_violation(summary):
        return _stage("TRANSITION_DIGEST", "HISTORY", CONTROL_VIOLATION, len(digest), len(digest), 1, "Digest violates the report-only authority contract."), digest, refresh
    changes = history.loc[history.get("Event_Type", pd.Series(index=history.index, dtype=object)).astype(str).eq("EVIDENCE_CHANGE")]
    latest_change = _iso_max(changes.get("Observed_At_UTC", pd.Series(dtype=object))) if not changes.empty else None
    refresh_ts = pd.to_datetime(refresh, utc=True, errors="coerce")
    if latest_change is not None and pd.notna(refresh_ts) and latest_change > refresh_ts:
        return _stage("TRANSITION_DIGEST", "HISTORY", SOURCE_NEWER, len(digest), len(digest), 1, f"History contains an evidence change at {latest_change.isoformat()} after digest refresh {refresh}."), digest, refresh
    expected_digest = build_transition_digest(history, refresh)
    expected_summary = build_digest_summary(expected_digest, refresh)
    digest_match = _frame_signature(digest, DIGEST_COLUMNS, ["Lane"]) == _frame_signature(expected_digest, DIGEST_COLUMNS, ["Lane"])
    summary_match = _frame_signature(summary, DIGEST_SUMMARY_COLUMNS) == _frame_signature(expected_summary, DIGEST_SUMMARY_COLUMNS)
    mismatch = int(not digest_match) + int(not summary_match)
    status = DERIVED_DRIFT if mismatch else CURRENT
    detail = "Committed digest/detail does not reproduce from the exact refresh ID and current history." if mismatch else f"Digest exactly reproduces from history for refresh {refresh}."
    return _stage("TRANSITION_DIGEST", "HISTORY", status, len(digest), len(expected_digest), mismatch, detail), digest, refresh


def _build_packet_stage(root: Path, digest: pd.DataFrame, history: pd.DataFrame, expected_center: pd.DataFrame, refresh: str, digest_status: str) -> tuple[dict[str, object], pd.DataFrame]:
    packet = _read_csv(root / "research_manual_review_packet.csv")
    summary = _read_csv(root / "research_manual_review_packet_summary.csv")
    if digest_status != CURRENT:
        return _stage("MANUAL_REVIEW_PACKET", "TRANSITION_DIGEST", UPSTREAM_STALE, len(packet), len(packet), 1, "Transition digest is not current, so the review packet cannot be certified fresh."), packet
    if summary.empty or not refresh:
        return _stage("MANUAL_REVIEW_PACKET", "TRANSITION_DIGEST", DERIVED_MISSING, len(packet), 0, 1, "Review-packet summary is missing or the digest refresh ID is unavailable."), packet
    if _contract_violation(packet) or _contract_violation(summary):
        return _stage("MANUAL_REVIEW_PACKET", "TRANSITION_DIGEST", CONTROL_VIOLATION, len(packet), len(packet), 1, "Review packet violates the report-only authority contract."), packet
    packet_refresh = _clean(summary.iloc[0].get("Refresh_At_UTC"))
    if packet_refresh != refresh:
        return _stage("MANUAL_REVIEW_PACKET", "TRANSITION_DIGEST", SOURCE_NEWER, len(packet), len(packet), 1, f"Packet refresh {packet_refresh or 'MISSING'} does not match digest refresh {refresh}."), packet
    queue = _read_csv(root / "research_manual_review_queue.csv")
    prior_queue = _queue_before_refresh(queue, refresh)
    calibration_gate = _read_csv(root / "calibration_shadow_gate.csv")
    role_gate = _read_csv(root / "live_role_shadow_gate.csv")
    expected_packet = build_manual_review_packet(digest, history, expected_center, refresh)
    expected_packet = inject_multicell_reviews(expected_packet, prior_queue, calibration_gate, role_gate, refresh)
    expected_summary = build_packet_summary(expected_packet, digest, refresh)
    packet_match = _frame_signature(packet, PACKET_COLUMNS, ["Lane"]) == _frame_signature(expected_packet, PACKET_COLUMNS, ["Lane"])
    summary_match = _frame_signature(summary, PACKET_SUMMARY_COLUMNS) == _frame_signature(expected_summary, PACKET_SUMMARY_COLUMNS)
    mismatch = int(not packet_match) + int(not summary_match)
    status = DERIVED_DRIFT if mismatch else CURRENT
    detail = "Committed manual-review packet does not reproduce from the exact-refresh all-lane evidence plus one-time multicell review state." if mismatch else f"Manual-review packet exactly reproduces for refresh {refresh}."
    return _stage("MANUAL_REVIEW_PACKET", "TRANSITION_DIGEST", status, len(packet), len(expected_packet), mismatch, detail), packet


def _build_queue_stage(root: Path, packet: pd.DataFrame, refresh: str, packet_status: str) -> dict[str, object]:
    queue = _read_csv(root / "research_manual_review_queue.csv")
    summary = _read_csv(root / "research_manual_review_queue_summary.csv")
    if packet_status != CURRENT:
        return _stage("MANUAL_REVIEW_QUEUE", "MANUAL_REVIEW_PACKET", UPSTREAM_STALE, len(queue), len(queue), 1, "Manual-review packet is not current, so queue completeness cannot be certified.")
    if summary.empty:
        return _stage("MANUAL_REVIEW_QUEUE", "MANUAL_REVIEW_PACKET", DERIVED_MISSING, len(queue), len(queue), 1, "Review-queue summary is missing or unreadable.")
    if _contract_violation(queue) or _contract_violation(summary):
        return _stage("MANUAL_REVIEW_QUEUE", "MANUAL_REVIEW_PACKET", CONTROL_VIOLATION, len(queue), len(queue), 1, "Review queue violates the report-only authority contract.")
    expected_queue = append_review_queue(packet, queue, queued_at_utc=refresh or None)
    queue_match = _frame_signature(queue, QUEUE_COLUMNS, ["Review_Case_ID"]) == _frame_signature(expected_queue, QUEUE_COLUMNS, ["Review_Case_ID"])
    generated = _clean(summary.iloc[0].get("Generated_At_UTC")) or refresh or None
    expected_summary = build_queue_summary(queue, generated)
    summary_match = _frame_signature(summary, QUEUE_SUMMARY_COLUMNS) == _frame_signature(expected_summary, QUEUE_SUMMARY_COLUMNS)
    mismatch = int(not queue_match) + int(not summary_match)
    if mismatch:
        status = SOURCE_NEWER if not queue_match else DERIVED_DRIFT
        detail = "Current packet is not fully persisted in the durable queue." if not queue_match else "Queue summary does not reproduce from the durable queue."
    else:
        status = CURRENT
        detail = "Durable queue contains every current packet case and its operational summary reproduces exactly."
    return _stage("MANUAL_REVIEW_QUEUE", "MANUAL_REVIEW_PACKET", status, len(queue), len(expected_queue), mismatch, detail)


def build_pipeline_freshness_audit(data_dir: Path | str = "data") -> pd.DataFrame:
    root = Path(data_dir)
    expected_base = build_command_center(root)
    expected_promotion = build_promotion_command_center(root)
    command_stage, _ = _compare_center_stage(root, expected_base, "research_evidence_command_center.csv", "COMMAND_CENTER", "AUTHORITATIVE_EVIDENCE")
    promotion_stage, _ = _compare_center_stage(root, expected_promotion, "research_promotion_command_center.csv", "PROMOTION_COMMAND_CENTER", "COMMAND_CENTER + PROMOTION_SOURCES")
    governance_stage = _build_governance_stage(root, expected_promotion, str(promotion_stage["Freshness_Status"]))
    history_stage, history = _build_history_stage(root, expected_promotion, str(promotion_stage["Freshness_Status"]))
    digest_stage, digest, refresh = _build_digest_stage(root, history, str(history_stage["Freshness_Status"]))
    packet_stage, packet = _build_packet_stage(root, digest, history, expected_promotion, refresh, str(digest_stage["Freshness_Status"]))
    queue_stage = _build_queue_stage(root, packet, refresh, str(packet_stage["Freshness_Status"]))
    return pd.DataFrame([command_stage, promotion_stage, governance_stage, history_stage, digest_stage, packet_stage, queue_stage], columns=STAGE_COLUMNS)


def build_freshness_summary(audit: pd.DataFrame) -> pd.DataFrame:
    frame = audit.copy() if audit is not None else pd.DataFrame(columns=STAGE_COLUMNS)
    statuses = frame.get("Freshness_Status", pd.Series(dtype=object)).fillna("").astype(str)
    current = int(statuses.eq(CURRENT).sum())
    stale = int(statuses.isin({SOURCE_NEWER, DERIVED_DRIFT, UPSTREAM_STALE}).sum())
    missing = int(statuses.isin({SOURCE_MISSING, DERIVED_MISSING}).sum())
    violations = int(statuses.eq(CONTROL_VIOLATION).sum())
    if violations:
        overall = CONTROL_VIOLATION
    elif missing:
        overall = "INCOMPLETE"
    elif stale:
        overall = "STALE"
    else:
        overall = "HEALTHY"
    report_only = frame.get("Report_Only", pd.Series(dtype=object)).map(_truthy) if not frame.empty else pd.Series(dtype=bool)
    authority = frame.get("Production_Authority", pd.Series(dtype=object)).map(_clean).str.upper() if not frame.empty else pd.Series(dtype=object)
    return pd.DataFrame([{
        "Overall_Status": overall,
        "Total_Stages": int(len(frame)),
        "Current_Stages": current,
        "Stale_Stages": stale,
        "Missing_Stages": missing,
        "Control_Violation_Stages": violations,
        "All_Report_Only": bool(report_only.all()) if not report_only.empty else True,
        "All_Production_Authority_None": bool(authority.eq("NONE").all()) if not authority.empty else True,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Freshness_Version": VERSION,
    }], columns=SUMMARY_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit report-only research dependency freshness across base and promotion lanes by deterministic recomputation.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default="data/research_pipeline_freshness_audit.csv")
    parser.add_argument("--summary-output", default="data/research_pipeline_freshness_summary.csv")
    args = parser.parse_args()
    audit = build_pipeline_freshness_audit(args.data_dir)
    summary = build_freshness_summary(audit)
    output = Path(args.output)
    summary_output = Path(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output, index=False)
    summary.to_csv(summary_output, index=False)
    print(audit.to_string(index=False))
    print(summary.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} no_auto_promotion={NO_AUTO_PROMOTION} freshness_version={VERSION}")


if __name__ == "__main__":
    main()

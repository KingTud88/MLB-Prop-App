from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing patch anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"non-unique patch anchor: {label} count={text.count(old)}")
    return text.replace(old, new, 1)


freshness_path = Path("training/research_pipeline_freshness_audit.py")
text = freshness_path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from training.research_promotion_command_center import build_promotion_command_center\n",
    "from training.research_promotion_command_center import build_promotion_command_center\n"
    "from training.research_governance_v2 import (\n"
    "    MANIFEST_COLUMNS as GOVERNANCE_MANIFEST_COLUMNS,\n"
    "    UNCERTAINTY_COLUMNS as GOVERNANCE_UNCERTAINTY_COLUMNS,\n"
    "    SUMMARY_COLUMNS as GOVERNANCE_SUMMARY_COLUMNS,\n"
    "    build_governance_summary,\n"
    "    build_hypothesis_manifest,\n"
    "    build_uncertainty_report,\n"
    ")\n",
    "governance imports",
)
text = replace_once(
    text,
    'VERSION = "research-pipeline-freshness-v3-all-lanes-report-only"',
    'VERSION = "research-pipeline-freshness-v4-governance-v2-report-only"',
    "freshness version",
)
anchor = '''    return _stage(stage_name, depends_on, status, len(saved_fp), len(expected_fp), len(mismatches), detail), saved\n\n\ndef _build_history_stage'''
insert = '''    return _stage(stage_name, depends_on, status, len(saved_fp), len(expected_fp), len(mismatches), detail), saved\n\n\ndef _read_governance_artifact(path: Path, required_columns: list[str]) -> tuple[bool, pd.DataFrame]:\n    if not path.exists():\n        return False, pd.DataFrame(columns=required_columns)\n    try:\n        frame = pd.read_csv(path)\n    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):\n        return False, pd.DataFrame(columns=required_columns)\n    return set(required_columns).issubset(frame.columns), frame\n\n\ndef _governance_control_violation(manifest: pd.DataFrame, uncertainty: pd.DataFrame, summary: pd.DataFrame) -> bool:\n    if _contract_violation(manifest) or _contract_violation(summary):\n        return True\n    if uncertainty is not None and not uncertainty.empty:\n        report_only = uncertainty.get("Report_Only", pd.Series(index=uncertainty.index, dtype=object)).map(_truthy)\n        authority = uncertainty.get("Production_Authority", pd.Series(index=uncertainty.index, dtype=object)).map(_clean).str.upper()\n        if bool((~report_only | ~authority.eq("NONE")).any()):\n            return True\n    if summary is not None and not summary.empty:\n        automatic = summary.get("Automatic_Decision_Allowed", pd.Series(index=summary.index, dtype=object)).map(_truthy)\n        if bool(automatic.any()):\n            return True\n    return False\n\n\ndef _build_governance_stage(root: Path, expected_center: pd.DataFrame, promotion_status: str) -> dict[str, object]:\n    manifest_ok, manifest = _read_governance_artifact(root / "research_hypothesis_manifest.csv", GOVERNANCE_MANIFEST_COLUMNS)\n    uncertainty_ok, uncertainty = _read_governance_artifact(root / "research_uncertainty_v2.csv", GOVERNANCE_UNCERTAINTY_COLUMNS)\n    summary_ok, summary = _read_governance_artifact(root / "research_governance_v2_summary.csv", GOVERNANCE_SUMMARY_COLUMNS)\n    current_items = int(len(manifest) + len(uncertainty) + len(summary))\n\n    if promotion_status != CURRENT:\n        return _stage(\n            "GOVERNANCE_V2", "PROMOTION_COMMAND_CENTER", UPSTREAM_STALE, current_items, 0, 1,\n            "Promotion command center is not current, so Governance v2 artifacts cannot be certified fresh.",\n        )\n\n    expected_manifest = build_hypothesis_manifest(expected_center)\n    expected_uncertainty = build_uncertainty_report(root)\n    expected_summary = build_governance_summary(expected_center, expected_manifest, expected_uncertainty)\n    expected_items = int(len(expected_manifest) + len(expected_uncertainty) + len(expected_summary))\n\n    missing = [\n        name for name, ok in (\n            ("research_hypothesis_manifest.csv", manifest_ok),\n            ("research_uncertainty_v2.csv", uncertainty_ok),\n            ("research_governance_v2_summary.csv", summary_ok),\n        ) if not ok\n    ]\n    if missing:\n        return _stage(\n            "GOVERNANCE_V2", "PROMOTION_COMMAND_CENTER", DERIVED_MISSING, current_items, expected_items, len(missing),\n            "Governance v2 artifact(s) are missing or unreadable: " + ", ".join(missing),\n        )\n    if _governance_control_violation(manifest, uncertainty, summary):\n        return _stage(\n            "GOVERNANCE_V2", "PROMOTION_COMMAND_CENTER", CONTROL_VIOLATION, current_items, expected_items, 1,\n            "Governance v2 artifacts violate report-only, Production Authority NONE, no-auto-promotion, or automatic-decision controls.",\n        )\n\n    manifest_match = _frame_signature(manifest, GOVERNANCE_MANIFEST_COLUMNS, ["Lane"]) == _frame_signature(expected_manifest, GOVERNANCE_MANIFEST_COLUMNS, ["Lane"])\n    uncertainty_match = _frame_signature(uncertainty, GOVERNANCE_UNCERTAINTY_COLUMNS, ["Lane", "Segment", "Metric"]) == _frame_signature(expected_uncertainty, GOVERNANCE_UNCERTAINTY_COLUMNS, ["Lane", "Segment", "Metric"])\n    summary_match = _frame_signature(summary, GOVERNANCE_SUMMARY_COLUMNS) == _frame_signature(expected_summary, GOVERNANCE_SUMMARY_COLUMNS)\n    mismatch = int(not manifest_match) + int(not uncertainty_match) + int(not summary_match)\n    status = DERIVED_DRIFT if mismatch else CURRENT\n    detail = (\n        "Governance v2 manifest, uncertainty diagnostics, or summary do not reproduce from current all-lane evidence."\n        if mismatch else\n        "Governance v2 manifest, uncertainty diagnostics, and summary exactly reproduce from current all-lane evidence."\n    )\n    return _stage("GOVERNANCE_V2", "PROMOTION_COMMAND_CENTER", status, current_items, expected_items, mismatch, detail)\n\n\ndef _build_history_stage'''
text = replace_once(text, anchor, insert, "governance stage insertion")
old_build = '''    promotion_stage, _ = _compare_center_stage(root, expected_promotion, "research_promotion_command_center.csv", "PROMOTION_COMMAND_CENTER", "COMMAND_CENTER + PROMOTION_SOURCES")\n    history_stage, history = _build_history_stage(root, expected_promotion, str(promotion_stage["Freshness_Status"]))\n    digest_stage, digest, refresh = _build_digest_stage(root, history, str(history_stage["Freshness_Status"]))\n    packet_stage, packet = _build_packet_stage(root, digest, history, expected_promotion, refresh, str(digest_stage["Freshness_Status"]))\n    queue_stage = _build_queue_stage(root, packet, refresh, str(packet_stage["Freshness_Status"]))\n    return pd.DataFrame([command_stage, promotion_stage, history_stage, digest_stage, packet_stage, queue_stage], columns=STAGE_COLUMNS)'''
new_build = '''    promotion_stage, _ = _compare_center_stage(root, expected_promotion, "research_promotion_command_center.csv", "PROMOTION_COMMAND_CENTER", "COMMAND_CENTER + PROMOTION_SOURCES")\n    governance_stage = _build_governance_stage(root, expected_promotion, str(promotion_stage["Freshness_Status"]))\n    history_stage, history = _build_history_stage(root, expected_promotion, str(promotion_stage["Freshness_Status"]))\n    digest_stage, digest, refresh = _build_digest_stage(root, history, str(history_stage["Freshness_Status"]))\n    packet_stage, packet = _build_packet_stage(root, digest, history, expected_promotion, refresh, str(digest_stage["Freshness_Status"]))\n    queue_stage = _build_queue_stage(root, packet, refresh, str(packet_stage["Freshness_Status"]))\n    return pd.DataFrame([command_stage, promotion_stage, governance_stage, history_stage, digest_stage, packet_stage, queue_stage], columns=STAGE_COLUMNS)'''
text = replace_once(text, old_build, new_build, "pipeline stage list")
freshness_path.write_text(text, encoding="utf-8")


test_path = Path("tests/test_research_pipeline_freshness_audit.py")
test = test_path.read_text(encoding="utf-8")
test = replace_once(
    test,
    "from training.research_evidence_history import append_history\n",
    "from training.research_evidence_history import append_history\n"
    "from training.research_governance_v2 import build_governance_summary, build_hypothesis_manifest, build_uncertainty_report\n",
    "test governance imports",
)
write_anchor = '''    promotion.to_csv(root / "research_promotion_command_center.csv", index=False)\n    history.to_csv(root / "research_evidence_history.csv", index=False)'''
write_insert = '''    promotion.to_csv(root / "research_promotion_command_center.csv", index=False)\n    manifest = build_hypothesis_manifest(promotion)\n    uncertainty = build_uncertainty_report(root)\n    governance_summary = build_governance_summary(promotion, manifest, uncertainty)\n    manifest.to_csv(root / "research_hypothesis_manifest.csv", index=False)\n    uncertainty.to_csv(root / "research_uncertainty_v2.csv", index=False)\n    governance_summary.to_csv(root / "research_governance_v2_summary.csv", index=False)\n    history.to_csv(root / "research_evidence_history.csv", index=False)'''
test = replace_once(test, write_anchor, write_insert, "test pipeline governance artifacts")
test = replace_once(
    test,
    '''        "COMMAND_CENTER", "PROMOTION_COMMAND_CENTER", "HISTORY",\n        "TRANSITION_DIGEST", "MANUAL_REVIEW_PACKET", "MANUAL_REVIEW_QUEUE",\n    ]\n    assert audit["Freshness_Status"].tolist() == [freshness.CURRENT] * 6\n    assert summary["Overall_Status"] == "HEALTHY"\n    assert int(summary["Current_Stages"]) == 6\n    assert int(summary["Total_Stages"]) == 6''',
    '''        "COMMAND_CENTER", "PROMOTION_COMMAND_CENTER", "GOVERNANCE_V2", "HISTORY",\n        "TRANSITION_DIGEST", "MANUAL_REVIEW_PACKET", "MANUAL_REVIEW_QUEUE",\n    ]\n    assert audit["Freshness_Status"].tolist() == [freshness.CURRENT] * 7\n    assert summary["Overall_Status"] == "HEALTHY"\n    assert int(summary["Current_Stages"]) == 7\n    assert int(summary["Total_Stages"]) == 7''',
    "healthy stage expectations",
)
test = replace_once(test, 'assert int(summary["Current_Stages"]) == 6\n\n\ndef test_base_command_center', 'assert int(summary["Current_Stages"]) == 7\n\n\ndef test_base_command_center', "multicell stage count")
test = replace_once(
    test,
    'assert freshness.VERSION == "research-pipeline-freshness-v3-all-lanes-report-only"',
    'assert freshness.VERSION == "research-pipeline-freshness-v4-governance-v2-report-only"',
    "freshness version assertion",
)
extra_tests = '''\n\ndef test_governance_v2_missing_artifact_is_incomplete_without_relabeling_history(tmp_path: Path, monkeypatch) -> None:\n    center = _center()\n    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")\n    refresh = "2026-08-18T13:00:00+00:00"\n    _write_pipeline(tmp_path, center, center, history, refresh)\n    (tmp_path / "research_governance_v2_summary.csv").unlink()\n    _patch_centers(monkeypatch, center, center)\n\n    audit = freshness.build_pipeline_freshness_audit(tmp_path).set_index("Stage")\n    summary = freshness.build_freshness_summary(audit.reset_index()).iloc[0]\n    assert audit.loc["GOVERNANCE_V2", "Freshness_Status"] == freshness.DERIVED_MISSING\n    assert audit.loc["HISTORY", "Freshness_Status"] == freshness.CURRENT\n    assert audit.loc["MANUAL_REVIEW_QUEUE", "Freshness_Status"] == freshness.CURRENT\n    assert summary["Overall_Status"] == "INCOMPLETE"\n\n\ndef test_governance_v2_manifest_drift_is_detected_without_changing_source_verdicts(tmp_path: Path, monkeypatch) -> None:\n    center = _center()\n    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")\n    refresh = "2026-08-18T13:00:00+00:00"\n    _write_pipeline(tmp_path, center, center, history, refresh)\n    manifest_path = tmp_path / "research_hypothesis_manifest.csv"\n    manifest = pd.read_csv(manifest_path)\n    manifest.loc[0, "Source_Fingerprint"] = "drifted"\n    manifest.to_csv(manifest_path, index=False)\n    _patch_centers(monkeypatch, center, center)\n\n    audit = freshness.build_pipeline_freshness_audit(tmp_path).set_index("Stage")\n    assert audit.loc["GOVERNANCE_V2", "Freshness_Status"] == freshness.DERIVED_DRIFT\n    assert audit.loc["PROMOTION_COMMAND_CENTER", "Freshness_Status"] == freshness.CURRENT\n    assert audit.loc["HISTORY", "Freshness_Status"] == freshness.CURRENT\n\n\ndef test_governance_v2_control_violation_is_loud(tmp_path: Path, monkeypatch) -> None:\n    center = _center()\n    history = append_history(center, observed_at_utc="2026-08-18T12:00:00+00:00")\n    refresh = "2026-08-18T13:00:00+00:00"\n    _write_pipeline(tmp_path, center, center, history, refresh)\n    manifest_path = tmp_path / "research_hypothesis_manifest.csv"\n    manifest = pd.read_csv(manifest_path)\n    manifest.loc[0, "Report_Only"] = False\n    manifest.to_csv(manifest_path, index=False)\n    _patch_centers(monkeypatch, center, center)\n\n    audit = freshness.build_pipeline_freshness_audit(tmp_path).set_index("Stage")\n    summary = freshness.build_freshness_summary(audit.reset_index()).iloc[0]\n    assert audit.loc["GOVERNANCE_V2", "Freshness_Status"] == freshness.CONTROL_VIOLATION\n    assert summary["Overall_Status"] == freshness.CONTROL_VIOLATION\n'''
if extra_tests.strip() in test:
    raise SystemExit("extra governance freshness tests already present")
test += extra_tests
test_path.write_text(test, encoding="utf-8")

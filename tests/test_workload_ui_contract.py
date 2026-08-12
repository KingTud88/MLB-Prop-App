from pathlib import Path


def test_daily_runner_uses_shared_workload_for_all_three_markets():
    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    assert "build_workload_context(log" in source
    assert '"expected_bf": float(workload.expected_bf)' in source
    assert "bf_sd=workload.bf_sd" in source
    assert "expected_outs=workload.expected_outs" in source
    assert "**workload.snapshot_fields()" in source
    assert "needs_workload" in source


def test_projection_page_surfaces_workload_intelligence():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "workload_ctx=build_workload_context" in source
    assert 'w1.metric("Expected pitches"' in source
    assert 'w2.metric("Expected BF"' in source
    assert 'w3.metric("Expected outs"' in source
    assert "bf_sd=workload_ctx.bf_sd" in source


def test_history_has_direct_workload_validation_and_resolved_only_rolling():
    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    assert "⚙️ Workload intelligence audit" in source
    assert "Pitch-count MAE" in source
    assert "BF MAE" in source
    assert "resolved_any" in source
    assert 'current = current.loc[resolved_any]' in source


def test_workload_pages_compile():
    for path in ["streamlit_app.py", "pages/4_Projection_History.py", "pages/5_Daily_Projection_Run.py"]:
        source = Path(path).read_text(encoding="utf-8")
        compile(source, path, "exec")


def test_workload_upgrade_isolated_from_lineup_and_seed_drift():
    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    assert "snapshot_matchup_override(row) if needs_workload else None" in source
    assert '"seed_version": row.get("app_version", APP_VERSION) if needs_workload else APP_VERSION' in source
    assert '"workload_preupgrade_app_version"' in source
    assert '"workload_upgraded_at_utc"' in source
    assert '"workload_projection_delta_k"' in source
    assert 'lineup_refreshes = 0' in source
    assert 'lineup_refreshes = refresh_pregame_lineups(frame, rows)' in source


def test_lineup_refresh_preserves_workload_upgrade_audit():
    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    assert '"workload_preupgrade_projection"' in source
    assert '"workload_projection_delta_outs"' in source
    assert '"workload_upgraded_at_utc"' in source

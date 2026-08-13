from pathlib import Path


def test_team_leash_is_context_only_in_live_projection_ui():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "Team leash candidate · CONTEXT ONLY" in source
    assert "These values do not alter Ks, Hits Allowed, Outs, or Top Plays" in source
    build_pos = source.index("workload_ctx=build_workload_context")
    role_pos = source.index("role_workload_decision=build_role_workload_decision")
    leash_pos = source.index("team_leash_ctx=build_team_leash_context")
    projection_pos = source.index("proj=calculate_projection", leash_pos)
    assert build_pos < role_pos < leash_pos < projection_pos
    # Team leash is diagnostic only. The projection consumes the role gate's
    # effective workload context, never the team-leash candidate fields.
    projection_slice = source[projection_pos:projection_pos + 350]
    assert "confirmed_count,effective_workload_ctx" in projection_slice
    assert "team_leash_candidate" not in projection_slice
    assert 'mode=os.getenv("STRIKEOUT_ROLE_WORKLOAD_MODE","shadow")' in source


def test_daily_snapshot_logs_candidate_without_using_it_as_expected_bf():
    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    assert "**team_leash.snapshot_fields()" in source
    assert "**team_leash_candidate" in source
    assert 'expected_bf=f["expected_bf"]' in source
    assert "team_leash_candidate_expected_bf" not in source[source.index("hits = project_hits_allowed"):source.index("outs = project_total_outs")]


def test_projection_history_explicitly_keeps_team_leash_out_of_forecast():
    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    assert "Team leash candidate · workload backtest" in source
    assert "remains CONTEXT ONLY and does not change the baseball forecast" in source
    assert "zero projection or Top Plays influence" in source

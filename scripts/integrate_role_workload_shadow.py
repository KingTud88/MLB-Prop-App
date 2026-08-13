from __future__ import annotations

from pathlib import Path

APP = Path("streamlit_app.py")
text = APP.read_text(encoding="utf-8")

old_import = "from engine.workload_context import WorkloadContext, build_workload_context\n"
new_import = old_import + "from engine.role_workload_gate import build_role_workload_decision\n"
assert old_import in text, "workload import anchor missing"
text = text.replace(old_import, new_import, 1)

old_loader = '''def load_observation_history():\n    try:return pd.read_csv(OBS_LOG)\n    except Exception:return pd.DataFrame()\n'''
new_loader = old_loader + '''\ndef load_role_runtime_state():\n    try:return pd.read_csv(APP_DIR / "data" / "starter_role_runtime_state.csv")\n    except Exception:return pd.DataFrame()\n'''
assert old_loader in text, "observation loader anchor missing"
text = text.replace(old_loader, new_loader, 1)

old_block = '''workload_ctx=build_workload_context(log,game.game_time)\nteam_leash_ctx=build_team_leash_context(load_projection_history(),load_observation_history(),game.team,game.game_time)\nteam_leash_candidate=candidate_workload_fields(team_leash_ctx,workload_ctx.expected_pitches,workload_ctx.expected_bf,workload_ctx.expected_outs)\nproj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count,workload_ctx); kdf=ladder(proj,12)\nfeatures_for_hits=build_engine_features(log,game,float(opponent_matchup["k_rate"]),confirmed_count,workload_ctx)\n'''
new_block = '''workload_ctx=build_workload_context(log,game.game_time)\nrole_workload_decision=build_role_workload_decision(\n    log,workload_ctx,load_role_runtime_state(),game.game_time,\n    mode=os.getenv("STRIKEOUT_ROLE_WORKLOAD_MODE","shadow"),\n)\neffective_workload_ctx=role_workload_decision.effective\nteam_leash_ctx=build_team_leash_context(load_projection_history(),load_observation_history(),game.team,game.game_time)\nteam_leash_candidate=candidate_workload_fields(team_leash_ctx,workload_ctx.expected_pitches,workload_ctx.expected_bf,workload_ctx.expected_outs)\nproj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count,effective_workload_ctx); kdf=ladder(proj,12)\nfeatures_for_hits=build_engine_features(log,game,float(opponent_matchup["k_rate"]),confirmed_count,effective_workload_ctx)\n'''
assert old_block in text, "projection workload anchor missing"
text = text.replace(old_block, new_block, 1)

old_form = '''    st.caption(f"Pitch trend {workload_ctx.pitch_trend:+.1%} · BF trend {workload_ctx.bf_trend:+.1%} · outs trend {workload_ctx.outs_trend:+.1%} · short-rest exposure multiplier {workload_ctx.rest_multiplier:.3f}.")\n    st.markdown("#### 🧭 Team leash candidate · CONTEXT ONLY")\n'''
new_form = '''    st.caption(f"Pitch trend {workload_ctx.pitch_trend:+.1%} · BF trend {workload_ctx.bf_trend:+.1%} · outs trend {workload_ctx.outs_trend:+.1%} · short-rest exposure multiplier {workload_ctx.rest_multiplier:.3f}.")\n    role_name="LOW_RECENT_EXPOSURE" if role_workload_decision.role=="RESTRICTED" else role_workload_decision.role\n    st.markdown("#### 🧪 Starter role workload · SHADOW / FEATURE GATED")\n    r1,r2,r3,r4,r5=st.columns(5)\n    r1.metric("Role",role_name)\n    r2.metric("Gate mode",role_workload_decision.mode.upper())\n    r3.metric("Candidate pitches",f"{role_workload_decision.candidate.expected_pitches:.1f}")\n    r4.metric("Candidate BF",f"{role_workload_decision.candidate.expected_bf:.1f}")\n    r5.metric("Candidate outs",f"{role_workload_decision.candidate.expected_outs:.1f}")\n    st.caption(f"Applied to projection: {'YES' if role_workload_decision.applied else 'NO'} · {role_workload_decision.reason} · corrections {role_workload_decision.correction_pitches:+.2f} pitches / {role_workload_decision.correction_bf:+.2f} BF / {role_workload_decision.correction_outs:+.2f} outs.")\n    st.markdown("#### 🧭 Team leash candidate · CONTEXT ONLY")\n'''
assert old_form in text, "form workload anchor missing"
text = text.replace(old_form, new_form, 1)

APP.write_text(text, encoding="utf-8")
print("Integrated starter-role workload gate into Projection page; default mode is shadow.")

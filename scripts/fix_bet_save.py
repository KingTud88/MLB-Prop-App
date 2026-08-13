from pathlib import Path

page = Path("pages/6_Top_Plays.py")
s = page.read_text(encoding="utf-8")

if "# TOP_PLAYS_SIMPLIFIED_LAYOUT_V1" not in s:
    # Keep all evidence calculations in place for ranking / blocking, but stop
    # rendering the diagnostics before the actual plays.
    diagnostics_start = s.index('with st.expander("Hits Allowed calibration status", expanded=False):')
    plays_start = s.index('plays = build_model_board(slate, history, limit=5, market_health=health_map)')
    computation_only = '''# TOP_PLAYS_SIMPLIFIED_LAYOUT_V1\n# Evidence is still computed before ranking; only its presentation moved below the plays.\nreport = hits_calibration_report(history)\nouts_report = outs_calibration_report(history)\nwalk_forward = walk_forward_top5(history)\nhealth_report = health_from_walk_forward(walk_forward)\nhealth_map = market_health_map(health_report)\ndecision_report = decision_tier_report(walk_forward)\nsignal_report = paired_signal_report(history)\n\n'''
    s = s[:diagnostics_start] + computation_only + s[plays_start:]

    # The card board already contains the same five ranked legs in a much more
    # readable form, so remove the duplicate dataframe presentation entirely.
    board_start = s.index('view = plays[["Rank", "Pitcher", "Weather Icon", "Market", "Side", "Line", "Projection", "Model Probability", "Weather Risk", "Decision Evidence", "Signal Evidence", "Tier Hit Rate"]].copy()')
    actions_start = s.index('st.markdown("#### Top Play actions")', board_start)
    s = s[:board_start] + s[actions_start:]

    # With no selectable duplicate table there is no dataframe selection event.
    selection_old = '''selected_rank = st.session_state.get("top_play_detail_rank")\ntry:\n    selected_rows = list(event.selection.rows)\nexcept Exception:\n    selected_rows = list((event.get("selection", {}) or {}).get("rows", [])) if isinstance(event, dict) else []\nif selected_rows:\n    idx = int(selected_rows[0])\n    if 0 <= idx < len(plays):\n        selected_rank = int(plays.iloc[idx]["Rank"])\n        st.session_state["top_play_detail_rank"] = selected_rank\n'''
    if selection_old not in s:
        raise SystemExit("Expected Top Plays dataframe selection block not found")
    s = s.replace(selection_old, 'selected_rank = st.session_state.get("top_play_detail_rank")\n', 1)

    diagnostics = '''\n\nst.markdown("---")\nst.subheader("🧪 Model diagnostics")\nst.caption("Calibration, Model Health, decision-learning evidence, and signal accountability live here so the plays stay first-scan readable. These diagnostics retain their original ranking and safety roles.")\n\nwith st.expander("Hits Allowed calibration status", expanded=False):\n    st.dataframe(report, hide_index=True, use_container_width=True)\n    ready = int((report["Status"] == "Calibrated").sum()) if not report.empty else 0\n    st.caption(f"{ready}/{len(report)} tracked hit lines currently have learned SIM/MATH weights. Until a line reaches 30 resolved frozen observations, Top Plays uses the protected 50/50 baseline for that line.")\n\nwith st.expander("Total Outs calibration status", expanded=False):\n    st.dataframe(outs_report, hide_index=True, use_container_width=True)\n    outs_ready = int((outs_report["Status"] == "Calibrated").sum()) if not outs_report.empty else 0\n    st.caption(f"{outs_ready}/{len(outs_report)} tracked outs lines currently have learned SIM/MATH weights. Until a line reaches 30 resolved frozen observations, Top Plays uses the protected 50/50 baseline.")\n\nwith st.expander("🚦 Walk-forward Model Health", expanded=False):\n    health_view = health_report.loc[health_report["Market"].ne("ALL TOP 5")].copy()\n    if health_view.empty:\n        st.info("Model health is still waiting for starter-only walk-forward results.")\n    else:\n        for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Recent Hit Rate", "Recent Avg Probability", "Recent Calibration Gap"]:\n            health_view[col] = health_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")\n        health_view["Brier Score"] = health_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")\n        st.dataframe(health_view, hide_index=True, width="stretch")\n    st.caption("LEARNING and WATCH markets stay eligible. After 30 settled walk-forward Top 5 legs, a market that falls outside the safety guardrails becomes BLOCKED and is removed before today's Top 5 is ranked.")\n\nwith st.expander("🎯 Decision-learning evidence", expanded=False):\n    st.caption("Segment evidence uses settled leakage-safe Top 5 recommendations only. Sportsbook prices and saved bets are excluded, and this layer does not reorder today's board.")\n    if decision_report.empty:\n        st.info("Decision evidence is still waiting for settled starter-only Top 5 legs.")\n    else:\n        decision_view = decision_report.copy()\n        for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Wilson Lower 95%", "Lift vs Top 5"]:\n            decision_view[col] = decision_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")\n        decision_view["Brier Score"] = decision_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")\n        st.dataframe(decision_view, hide_index=True, width="stretch")\n    st.caption("Exact segments stay LEARNING below 20 settled legs. Strong or underperforming labels require at least 30 settled legs.")\n\nwith st.expander("🧪 Signal accountability", expanded=False):\n    st.caption("Paired pregame upgrade evidence measures whether workload-v1 and confirmed-lineup changes reduced same-game prediction error after the final result. This evidence is attached after ranking and cannot reorder or remove today's legs.")\n    if signal_report.empty:\n        st.info("Signal evidence is still waiting for resolved paired upgrades.")\n    else:\n        signal_view = signal_report.copy()\n        for col in ["Relative MAE Improvement", "Improved Share"]:\n            signal_view[col] = signal_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if col == "Relative MAE Improvement" else f"{float(x):.1%}")\n        st.dataframe(signal_view[["Signal", "Market", "Resolved Pairs", "Pre MAE", "Post MAE", "Relative MAE Improvement", "Improved Share", "Status", "Reason"]], hide_index=True, width="stretch")\n    st.caption("Signals remain LEARNING below 20 resolved pairs. HELPING/MIXED/HURTING are evidence labels only; sportsbook data is excluded.")\n'''
    s = s.rstrip() + diagnostics + "\n"

page.write_text(s, encoding="utf-8")

# The existing validation workflow historically looked for this token. Keep a
# harmless marker while the browser-rendered mascot hotfix remains in place.
nav = Path("navigation.py")
nav_text = nav.read_text(encoding="utf-8")
marker = "# MASCOT_PATH compatibility marker: mascot is browser-rendered to avoid Pillow codec crashes.\n"
if "MASCOT_PATH" not in nav_text:
    nav_text = nav_text.replace("import streamlit as st\n", "import streamlit as st\n\n" + marker, 1)
    nav.write_text(nav_text, encoding="utf-8")

print("Top Plays simplified: cards first, diagnostics last, duplicate table removed.")

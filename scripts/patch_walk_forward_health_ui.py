from pathlib import Path

HISTORY = Path("pages/4_Projection_History.py")
TOP = Path("pages/6_Top_Plays.py")
TEST = Path("tests/test_walk_forward_health_ui.py")

history = HISTORY.read_text(encoding="utf-8")
old = 'from engine.starter_history import HISTORY_SEMANTICS\n'
new = '''from engine.starter_history import HISTORY_SEMANTICS\nfrom engine.model_health import (\n    daily_top5_summary,\n    health_from_walk_forward,\n    reliability_table,\n    walk_forward_top5,\n)\n'''
if old not in history:
    raise SystemExit("Projection History import anchor not found")
history = history.replace(old, new, 1)

anchor = '''st.divider()\nst.subheader("📋 Projection archive")\n'''
block = '''st.divider()\nst.subheader("🚦 Walk-forward Top 5 model health")\nst.caption(\n    "Leakage-safe replay: each historical slate is rebuilt from its frozen pregame snapshots while calibration can only use earlier game dates. "\n    "Same-day/future results and sportsbook prices are excluded. LEARNING and WATCH markets remain eligible; only BLOCKED markets are removed from Top Plays."\n)\nwalk_forward = walk_forward_top5(df)\nhealth_report = health_from_walk_forward(walk_forward)\nsettled_walk = walk_forward.loc[walk_forward.get("Hit", pd.Series(index=walk_forward.index, dtype=object)).notna()].copy() if not walk_forward.empty else pd.DataFrame()\nall_health = health_report.loc[health_report["Market"].eq("ALL TOP 5")].iloc[0] if not health_report.empty and health_report["Market"].eq("ALL TOP 5").any() else None\nblocked_count = int((health_report.loc[health_report["Market"].ne("ALL TOP 5"), "Status"] == "BLOCKED").sum()) if not health_report.empty else 0\n\nwf1, wf2, wf3, wf4 = st.columns(4)\nwf1.metric("Settled walk-forward Top 5 legs", len(settled_walk))\nwf2.metric("Historical Top 5 hit rate", "—" if all_health is None or pd.isna(all_health["Hit Rate"]) else f"{float(all_health['Hit Rate']):.1%}")\nwf3.metric("Avg predicted probability", "—" if all_health is None or pd.isna(all_health["Avg Model Probability"]) else f"{float(all_health['Avg Model Probability']):.1%}")\nwf4.metric("Markets currently blocked", blocked_count)\n\nhealth_view = health_report.copy()\nif not health_view.empty:\n    for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Recent Hit Rate", "Recent Avg Probability", "Recent Calibration Gap"]:\n        health_view[col] = health_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")\n    health_view["Brier Score"] = health_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")\n    st.dataframe(health_view, hide_index=True, width="stretch")\n    st.caption("Health guard activates after 30 settled walk-forward Top 5 legs for that market. Until then the status is LEARNING and the market remains eligible.")\n\nwith st.expander("Probability reliability — walk-forward Top 5"):\n    reliability = reliability_table(walk_forward)\n    if reliability.empty:\n        st.info("Reliability buckets will populate as starter-only Top 5 legs resolve.")\n    else:\n        reliability_view = reliability.copy()\n        for col in ["Avg Model Probability", "Observed Hit Rate", "Calibration Gap"]:\n            reliability_view[col] = reliability_view[col].map(lambda x: f"{float(x):.1%}")\n        st.dataframe(reliability_view, hide_index=True, width="stretch")\n\nwith st.expander("Daily historical Top 5 replay"):\n    daily = daily_top5_summary(walk_forward)\n    if daily.empty:\n        st.info("Daily Top 5 replay will populate after current starter-only recommendations resolve.")\n    else:\n        daily_view = daily.sort_values("Date", ascending=False).head(60).copy()\n        daily_view["Hit Rate"] = daily_view["Hit Rate"].map(lambda x: f"{float(x):.1%}")\n        daily_view["Avg Model Probability"] = daily_view["Avg Model Probability"].map(lambda x: f"{float(x):.1%}")\n        daily_view["Brier Score"] = daily_view["Brier Score"].map(lambda x: f"{float(x):.3f}")\n        daily_view["5/5 Sweep"] = daily_view["5/5 Sweep"].map(lambda x: "👑 YES" if bool(x) else "—")\n        st.dataframe(daily_view, hide_index=True, width="stretch")\n\nst.divider()\nst.subheader("📋 Projection archive")\n'''
if anchor not in history:
    raise SystemExit("Projection History archive anchor not found")
history = history.replace(anchor, block, 1)
HISTORY.write_text(history, encoding="utf-8")

top = TOP.read_text(encoding="utf-8")
old = 'from engine.model_top_plays import build_model_board\n'
new = '''from engine.model_top_plays import build_model_board\nfrom engine.model_health import market_health_map, market_health_report\n'''
if old not in top:
    raise SystemExit("Top Plays import anchor not found")
top = top.replace(old, new, 1)

old = '''plays = build_model_board(slate, history, limit=5)\nif plays.empty:\n    st.warning("Today's frozen snapshots do not yet contain enough current two-path probability data to build the model Top 5. Re-run Daily Projection Run while the games are still pregame so missing paths can be backfilled safely.")\n    st.stop()\n'''
new = '''health_report = market_health_report(history)\nhealth_map = market_health_map(health_report)\nwith st.expander("🚦 Walk-forward model health", expanded=False):\n    health_view = health_report.loc[health_report["Market"].ne("ALL TOP 5")].copy()\n    if health_view.empty:\n        st.info("Model health is still waiting for starter-only walk-forward results.")\n    else:\n        for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Recent Hit Rate", "Recent Avg Probability", "Recent Calibration Gap"]:\n            health_view[col] = health_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")\n        health_view["Brier Score"] = health_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")\n        st.dataframe(health_view, hide_index=True, width="stretch")\n    st.caption("LEARNING and WATCH markets stay eligible. After 30 settled walk-forward Top 5 legs, a market that falls outside the safety guardrails becomes BLOCKED and is removed before today's Top 5 is ranked.")\n\nplays = build_model_board(slate, history, limit=5, market_health=health_map)\nif plays.empty:\n    st.warning("No current market passed the starter-history, probability-path, and model-health eligibility guards. The app will not manufacture a Top Play when the validated board is empty.")\n    st.stop()\n'''
if old not in top:
    raise SystemExit("Top Plays board anchor not found")
top = top.replace(old, new, 1)

old = 'view = plays[["Rank", "Status", "Pitcher", "Weather Icon", "Weather Risk", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Starter History", "Book", "Odds"]].copy()'
new = 'view = plays[["Rank", "Status", "Model Health", "Pitcher", "Weather Icon", "Weather Risk", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Starter History", "Book", "Odds"]].copy()'
if old not in top:
    raise SystemExit("Top Plays view anchor not found")
top = top.replace(old, new, 1)

old = 'st.caption("Ranked only by our calibrated hit probability, with data quality as the tie-breaker. Sportsbook odds and market edge do not decide the Top 5.")'
new = 'st.caption("Eligible markets are ranked only by our calibrated hit probability, with data quality as the tie-breaker. Walk-forward model health can block a proven-unhealthy market; sportsbook odds and market edge never decide the Top 5.")'
if old not in top:
    raise SystemExit("Top Plays ranking caption anchor not found")
top = top.replace(old, new, 1)
TOP.write_text(top, encoding="utf-8")

TEST.write_text('''from pathlib import Path\n\n\ndef test_projection_history_has_walk_forward_health_dashboard():\n    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")\n    compile(source, "pages/4_Projection_History.py", "exec")\n    assert "Walk-forward Top 5 model health" in source\n    assert "walk_forward_top5(df)" in source\n    assert "health_from_walk_forward" in source\n    assert "Probability reliability — walk-forward Top 5" in source\n    assert "Daily historical Top 5 replay" in source\n\n\ndef test_top_plays_applies_health_before_ranking():\n    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")\n    compile(source, "pages/6_Top_Plays.py", "exec")\n    assert "market_health_report(history)" in source\n    assert "market_health=health_map" in source\n    assert '"Model Health"' in source\n    assert "BLOCKED and is removed before today's Top 5 is ranked" in source\n''', encoding="utf-8")

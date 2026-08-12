from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor not found: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Projection History: add the full decision-learning segment scoreboard.
# ---------------------------------------------------------------------------
path = Path("pages/4_Projection_History.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''from engine.model_health import (\n    daily_top5_summary,\n    health_from_walk_forward,\n    reliability_table,\n    walk_forward_top5,\n)\n''',
    '''from engine.model_health import (\n    daily_top5_summary,\n    health_from_walk_forward,\n    reliability_table,\n    walk_forward_top5,\n)\nfrom engine.decision_learning import decision_tier_report\n''',
    "history decision import",
)

archive_anchor = '''st.divider()\nst.subheader("📋 Projection archive")\n'''
decision_section = '''st.divider()\nst.subheader("🎯 Decision-learning tiers")\nst.caption(\n    "This layer studies settled leakage-safe Top 5 legs by market + model-probability band + data-quality band. "\n    "Sportsbook odds, sportsbook edge, book choice, and saved bet selections are excluded. These labels are descriptive evidence only and do not change Top 5 ranking."\n)\ndecision_report = decision_tier_report(walk_forward)\nif decision_report.empty:\n    st.info("Decision-learning segments will populate as current starter-only Top 5 legs settle.")\nelse:\n    decision_settled = int(pd.to_numeric(decision_report["Settled Legs"], errors="coerce").fillna(0).sum())\n    decision_supported = int(decision_report["Decision Evidence"].isin(["SUPPORTED", "STRONG EVIDENCE"]).sum())\n    decision_strong = int(decision_report["Decision Evidence"].eq("STRONG EVIDENCE").sum())\n    decision_under = int(decision_report["Decision Evidence"].eq("UNDERPERFORMING").sum())\n    d1, d2, d3, d4 = st.columns(4)\n    d1.metric("Settled decision legs", decision_settled)\n    d2.metric("Supported segments", decision_supported)\n    d3.metric("Strong-evidence segments", decision_strong)\n    d4.metric("Underperforming segments", decision_under)\n\n    decision_view = decision_report.copy()\n    for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Wilson Lower 95%", "Lift vs Top 5"]:\n        decision_view[col] = decision_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")\n    decision_view["Brier Score"] = decision_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")\n    st.dataframe(decision_view, hide_index=True, width="stretch")\n    st.caption(\n        "An exact segment stays LEARNING until it has 20 settled walk-forward legs. STRONG EVIDENCE and UNDERPERFORMING require at least 30, preventing tiny samples from driving decisions."\n    )\n\nst.divider()\nst.subheader("📋 Projection archive")\n'''
text = replace_once(text, archive_anchor, decision_section, "history decision section")
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Top Plays: attach descriptive decision evidence without changing ranking.
# ---------------------------------------------------------------------------
path = Path("pages/6_Top_Plays.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from engine.model_health import market_health_map, market_health_report\n',
    'from engine.model_health import health_from_walk_forward, market_health_map, walk_forward_top5\nfrom engine.decision_learning import attach_decision_profiles, decision_tier_report\n',
    "top plays decision imports",
)
text = replace_once(
    text,
    '''health_report = market_health_report(history)\nhealth_map = market_health_map(health_report)\n''',
    '''walk_forward = walk_forward_top5(history)\nhealth_report = health_from_walk_forward(walk_forward)\nhealth_map = market_health_map(health_report)\n''',
    "top plays shared walk-forward",
)

health_caption = '''    st.caption("LEARNING and WATCH markets stay eligible. After 30 settled walk-forward Top 5 legs, a market that falls outside the safety guardrails becomes BLOCKED and is removed before today's Top 5 is ranked.")\n\nplays = build_model_board(slate, history, limit=5, market_health=health_map)\n'''
decision_block = '''    st.caption("LEARNING and WATCH markets stay eligible. After 30 settled walk-forward Top 5 legs, a market that falls outside the safety guardrails becomes BLOCKED and is removed before today's Top 5 is ranked.")\n\ndecision_report = decision_tier_report(walk_forward)\nwith st.expander("🎯 Decision-learning evidence", expanded=False):\n    st.caption(\n        "Segment evidence is built only from settled leakage-safe Top 5 recommendations, grouped by market + probability band + data-quality band. "\n        "Sportsbook prices and saved bets are excluded, and this layer does not reorder today's board."\n    )\n    if decision_report.empty:\n        st.info("Decision evidence is still waiting for settled starter-only Top 5 legs.")\n    else:\n        decision_view = decision_report.copy()\n        for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Wilson Lower 95%", "Lift vs Top 5"]:\n            decision_view[col] = decision_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")\n        decision_view["Brier Score"] = decision_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")\n        st.dataframe(decision_view, hide_index=True, width="stretch")\n    st.caption("Exact segments stay LEARNING below 20 settled legs. Strong or underperforming labels require at least 30 settled legs.")\n\nplays = build_model_board(slate, history, limit=5, market_health=health_map)\n'''
text = replace_once(text, health_caption, decision_block, "top plays decision evidence block")
text = replace_once(
    text,
    '''if plays.empty:\n    st.warning("No current market passed the starter-history, probability-path, and model-health eligibility guards. The app will not manufacture a Top Play when the validated board is empty.")\n    st.stop()\n\n# The board exists before any paid sportsbook request. Credit Saver keeps paid\n''',
    '''if plays.empty:\n    st.warning("No current market passed the starter-history, probability-path, and model-health eligibility guards. The app will not manufacture a Top Play when the validated board is empty.")\n    st.stop()\nplays = attach_decision_profiles(plays, decision_report)\n\n# The board exists before any paid sportsbook request. Credit Saver keeps paid\n''',
    "top plays attach decision profiles",
)
text = replace_once(
    text,
    '''c1, c2, c3 = st.columns(3)\nc1.metric("Highest model hit probability", f"{plays['Model Probability'].max():.1%}")\nc2.metric("Model-qualified Top 5", model_plays)\nc3.metric("Exact live prices found", f"{live_offers}/{len(plays)}")\n\nview = plays[["Rank", "Status", "Model Health", "Pitcher", "Weather Icon", "Weather Risk", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Starter History", "Book", "Odds"]].copy()\n''',
    '''decision_supported = int(plays["Decision Evidence"].isin(["SUPPORTED", "STRONG EVIDENCE"]).sum())\nc1, c2, c3, c4 = st.columns(4)\nc1.metric("Highest model hit probability", f"{plays['Model Probability'].max():.1%}")\nc2.metric("Model-qualified Top 5", model_plays)\nc3.metric("Decision-supported legs", decision_supported)\nc4.metric("Exact live prices found", f"{live_offers}/{len(plays)}")\n\nview = plays[["Rank", "Status", "Model Health", "Decision Evidence", "Decision Sample", "Tier Hit Rate", "Pitcher", "Weather Icon", "Weather Risk", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Starter History", "Book", "Odds"]].copy()\n''',
    "top plays decision table columns",
)
text = replace_once(
    text,
    '''view["Model Probability"] = view["Model Probability"].map(lambda x: f"{float(x):.1%}")\nview["Projection"] = view["Projection"].map(lambda x: f"{float(x):.2f}")\n''',
    '''view["Model Probability"] = view["Model Probability"].map(lambda x: f"{float(x):.1%}")\nview["Tier Hit Rate"] = view["Tier Hit Rate"].map(lambda x: "—" if x is None or pd.isna(x) else f"{float(x):.1%}")\nview["Projection"] = view["Projection"].map(lambda x: f"{float(x):.2f}")\n''',
    "top plays decision hit formatting",
)
text = replace_once(
    text,
    '''st.caption("Eligible markets are ranked only by our calibrated hit probability, with data quality as the tie-breaker. Walk-forward model health can block a proven-unhealthy market; sportsbook odds and market edge never decide the Top 5.")\n''',
    '''st.caption("Eligible markets are ranked only by our calibrated hit probability, with data quality as the tie-breaker. Walk-forward model health can block a proven-unhealthy market; decision evidence is descriptive only; sportsbook odds and market edge never decide the Top 5.")\n''',
    "top plays ranking caption",
)

live_edge_anchor = '''    if live_edge is not None and live_implied is not None:\n        st.caption(f"Market comparison only: no-vig implied {live_implied:.1%} · model edge {live_edge:+.1%}. These values do not affect Top 5 ranking.")\n\n    market = str(play.get("Market", ""))\n'''
live_edge_new = '''    if live_edge is not None and live_implied is not None:\n        st.caption(f"Market comparison only: no-vig implied {live_implied:.1%} · model edge {live_edge:+.1%}. These values do not affect Top 5 ranking.")\n\n    decision_evidence = str(play.get("Decision Evidence", "LEARNING"))\n    decision_sample = int(play.get("Decision Sample", 0) or 0)\n    tier_hit = numeric(play.get("Tier Hit Rate"))\n    decision_band = str(play.get("Decision Probability Band", ""))\n    decision_quality = str(play.get("Decision Quality Band", ""))\n    tier_text = "—" if tier_hit is None else f"{tier_hit:.1%}"\n    st.caption(\n        f"Decision evidence: {decision_evidence} · exact segment {decision_band} model probability / quality {decision_quality} · "\n        f"{decision_sample} settled walk-forward legs · historical hit rate {tier_text}. This evidence does not change the projection itself."\n    )\n\n    market = str(play.get("Market", ""))\n'''
text = replace_once(text, live_edge_anchor, live_edge_new, "top plays rationale decision evidence")

card_anchor = '''        st.caption(f"#{rank} {play_row['Pitcher']} {weather_icon} · {play_row['Side']} {float(play_row['Line']):g}".replace("  ·", " ·"))\n'''
card_new = '''        st.caption(f"#{rank} {play_row['Pitcher']} {weather_icon} · {play_row['Side']} {float(play_row['Line']):g}".replace("  ·", " ·"))\n        st.caption(f"Decision evidence: {play_row.get('Decision Evidence', 'LEARNING')} · n={int(play_row.get('Decision Sample', 0) or 0)}")\n'''
text = replace_once(text, card_anchor, card_new, "top plays action card decision evidence")
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# UI contracts: decision evidence is visible but never allowed into ranking.
# ---------------------------------------------------------------------------
Path("tests/test_decision_learning_ui.py").write_text('''from pathlib import Path\n\n\ndef test_projection_history_surfaces_decision_learning_scoreboard():\n    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")\n    assert "🎯 Decision-learning tiers" in source\n    assert "decision_tier_report(walk_forward)" in source\n    assert "Sportsbook odds, sportsbook edge, book choice, and saved bet selections are excluded" in source\n    assert "STRONG EVIDENCE" in source\n    assert "UNDERPERFORMING" in source\n\n\ndef test_top_plays_attaches_decision_evidence_without_ranking_by_it():\n    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")\n    assert "attach_decision_profiles(plays, decision_report)" in source\n    assert '"Decision Evidence"' in source\n    assert '"Decision Sample"' in source\n    assert '"Tier Hit Rate"' in source\n    assert "decision evidence is descriptive only" in source\n    assert "walk_forward = walk_forward_top5(history)" in source\n    assert "market_health_map(health_report)" in source\n\n\ndef test_decision_learning_pages_compile():\n    for page in ["pages/4_Projection_History.py", "pages/6_Top_Plays.py"]:\n        source = Path(page).read_text(encoding="utf-8")\n        compile(source, page, "exec")\n''', encoding="utf-8")

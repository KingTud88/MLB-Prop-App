from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor not found: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Daily snapshots: preserve confirmed-lineup before/after evidence for Hits as
# well as Ks. Workload and lineup audit evidence must not overwrite each other.
# ---------------------------------------------------------------------------
path = Path("automation/daily_projection_runner.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        "lineup_preconfirm_projection": np.nan, "lineup_preconfirm_opponent_k_pct": np.nan,\n        "lineup_projection_delta": np.nan, "lineup_opponent_k_delta": np.nan,\n''',
    '''        "lineup_preconfirm_projection": np.nan, "lineup_preconfirm_opponent_k_pct": np.nan,\n        "lineup_preconfirm_hits_projection": np.nan, "lineup_preconfirm_opponent_hit_rate": np.nan,\n        "lineup_projection_delta": np.nan, "lineup_opponent_k_delta": np.nan,\n        "lineup_hits_projection_delta": np.nan, "lineup_opponent_hit_delta": np.nan,\n''',
    "daily lineup audit snapshot fields",
)
text = replace_once(
    text,
    '''        old_projection = pd.to_numeric(pd.Series([row.get("projection")]), errors="coerce").iloc[0]\n        old_opp_k = pd.to_numeric(pd.Series([row.get("opponent_k_pct")]), errors="coerce").iloc[0]\n''',
    '''        old_projection = pd.to_numeric(pd.Series([row.get("projection")]), errors="coerce").iloc[0]\n        old_opp_k = pd.to_numeric(pd.Series([row.get("opponent_k_pct")]), errors="coerce").iloc[0]\n        old_hits_projection = pd.to_numeric(pd.Series([row.get("hits_projection")]), errors="coerce").iloc[0]\n        old_opp_hit = pd.to_numeric(pd.Series([row.get("opponent_hit_rate")]), errors="coerce").iloc[0]\n''',
    "lineup preconfirm hit values",
)
text = replace_once(
    text,
    '''        frame.at[idx, "lineup_preconfirm_projection"] = old_projection\n        frame.at[idx, "lineup_preconfirm_opponent_k_pct"] = old_opp_k\n        new_projection = pd.to_numeric(pd.Series([projected.get("projection")]), errors="coerce").iloc[0]\n        new_opp_k = pd.to_numeric(pd.Series([projected.get("opponent_k_pct")]), errors="coerce").iloc[0]\n        frame.at[idx, "lineup_projection_delta"] = np.nan if pd.isna(old_projection) or pd.isna(new_projection) else float(new_projection - old_projection)\n        frame.at[idx, "lineup_opponent_k_delta"] = np.nan if pd.isna(old_opp_k) or pd.isna(new_opp_k) else float(new_opp_k - old_opp_k)\n''',
    '''        frame.at[idx, "lineup_preconfirm_projection"] = old_projection\n        frame.at[idx, "lineup_preconfirm_opponent_k_pct"] = old_opp_k\n        frame.at[idx, "lineup_preconfirm_hits_projection"] = old_hits_projection\n        frame.at[idx, "lineup_preconfirm_opponent_hit_rate"] = old_opp_hit\n        new_projection = pd.to_numeric(pd.Series([projected.get("projection")]), errors="coerce").iloc[0]\n        new_opp_k = pd.to_numeric(pd.Series([projected.get("opponent_k_pct")]), errors="coerce").iloc[0]\n        new_hits_projection = pd.to_numeric(pd.Series([projected.get("hits_projection")]), errors="coerce").iloc[0]\n        new_opp_hit = pd.to_numeric(pd.Series([projected.get("opponent_hit_rate")]), errors="coerce").iloc[0]\n        frame.at[idx, "lineup_projection_delta"] = np.nan if pd.isna(old_projection) or pd.isna(new_projection) else float(new_projection - old_projection)\n        frame.at[idx, "lineup_opponent_k_delta"] = np.nan if pd.isna(old_opp_k) or pd.isna(new_opp_k) else float(new_opp_k - old_opp_k)\n        frame.at[idx, "lineup_hits_projection_delta"] = np.nan if pd.isna(old_hits_projection) or pd.isna(new_hits_projection) else float(new_hits_projection - old_hits_projection)\n        frame.at[idx, "lineup_opponent_hit_delta"] = np.nan if pd.isna(old_opp_hit) or pd.isna(new_opp_hit) else float(new_opp_hit - old_opp_hit)\n''',
    "lineup postconfirm hit audit",
)
text = text.replace(
    '''                "lineup_preconfirm_projection", "lineup_preconfirm_opponent_k_pct", "lineup_projection_delta", "lineup_opponent_k_delta",\n''',
    '''                "lineup_preconfirm_projection", "lineup_preconfirm_opponent_k_pct", "lineup_preconfirm_hits_projection",\n                "lineup_preconfirm_opponent_hit_rate", "lineup_projection_delta", "lineup_opponent_k_delta",\n                "lineup_hits_projection_delta", "lineup_opponent_hit_delta",\n''',
)
text = text.replace(
    "Started/finished games are never touched. The old K projection and opponent-K\n    input are retained in audit fields so the impact of the lineup can be measured.",
    "Started/finished games are never touched. Old K/Hits projections and opponent\n    K/contact inputs are retained so the lineup impact can be measured with paired outcomes.",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Projection History: paired feature-credit dashboard plus descriptive context
# performance. These reports are outcome-only and sportsbook-independent.
# ---------------------------------------------------------------------------
path = Path("pages/4_Projection_History.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from engine.decision_learning import decision_tier_report\n',
    'from engine.decision_learning import decision_tier_report\nfrom engine.signal_validation import context_performance_report, paired_signal_report\n',
    "history signal validation imports",
)
signal_section = '''st.divider()\nst.subheader("🧪 Signal accountability")\nst.caption(\n    "Paired upgrade evidence compares the same pitcher/game before and after a pregame feature upgrade, then grades both predictions against the same final result. "\n    "That is stronger evidence than comparing unrelated pitcher groups. Sportsbook odds, saved bets, and market prices are excluded. Signals stay LEARNING below 20 resolved pairs."\n)\npaired_signals = paired_signal_report(df)\nif paired_signals.empty:\n    st.info("Signal accountability will populate as paired pregame upgrades resolve.")\nelse:\n    helping = int(paired_signals["Status"].eq("HELPING").sum())\n    hurting = int(paired_signals["Status"].eq("HURTING").sum())\n    learning = int(paired_signals["Status"].eq("LEARNING").sum())\n    paired_outcomes = int(pd.to_numeric(paired_signals["Resolved Pairs"], errors="coerce").fillna(0).sum())\n    s1,s2,s3,s4 = st.columns(4)\n    s1.metric("Paired market outcomes", paired_outcomes)\n    s2.metric("Helping signals", helping)\n    s3.metric("Hurting signals", hurting)\n    s4.metric("Still learning", learning)\n    signal_view = paired_signals.copy()\n    for col in ["Relative MAE Improvement", "Improved Share"]:\n        signal_view[col] = signal_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if col == "Relative MAE Improvement" else f"{float(x):.1%}")\n    for col in ["Pre MAE", "Post MAE", "MAE Improvement", "Pre Bias", "Post Bias"]:\n        signal_view[col] = signal_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.3f}" if col in {"MAE Improvement", "Pre Bias", "Post Bias"} else f"{float(x):.3f}")\n    st.dataframe(signal_view, hide_index=True, width="stretch")\n    st.caption("HELPING requires at least 20 resolved pairs, at least 5% lower post-upgrade MAE, and improvement in at least 55% of paired starts. HURTING uses the symmetric downside guardrail. These labels do not alter Top Plays yet.")\n\nwith st.expander("Context performance — descriptive, not causal", expanded=False):\n    context_report = context_performance_report(df)\n    if context_report.empty:\n        st.info("Context buckets will populate as current starter-only snapshots resolve.")\n    else:\n        context_view = context_report.copy()\n        context_view["80% Range Coverage"] = context_view["80% Range Coverage"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")\n        context_view["MAE"] = context_view["MAE"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")\n        context_view["Bias"] = context_view["Bias"].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.3f}")\n        st.dataframe(context_view, hide_index=True, width="stretch")\n        st.caption("Lineup, workload, rest, history source, opponent K/contact environments are model inputs. Weather Delay Risk is labeled CONTEXT ONLY because weather still does not modify the baseball forecast.")\n\n'''
text = replace_once(
    text,
    'st.divider()\nst.subheader("🚦 Walk-forward Top 5 model health")\n',
    signal_section + 'st.divider()\nst.subheader("🚦 Walk-forward Top 5 model health")\n',
    "history signal section",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Top Plays: attach signal evidence only AFTER the board has been ranked. It is
# visible beside decision evidence but cannot reorder/filter today's Top 5.
# ---------------------------------------------------------------------------
path = Path("pages/6_Top_Plays.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from engine.decision_learning import attach_decision_profiles, decision_tier_report\n',
    'from engine.decision_learning import attach_decision_profiles, decision_tier_report\nfrom engine.signal_validation import attach_signal_profiles, paired_signal_report\n',
    "top signal validation import",
)
signal_expander = '''\nsignal_report = paired_signal_report(history)\nwith st.expander("🧪 Signal accountability", expanded=False):\n    st.caption(\n        "Paired pregame upgrade evidence measures whether workload-v1 and confirmed-lineup changes reduced same-game prediction error after the final result. "\n        "This evidence is attached after ranking and cannot reorder or remove today's legs."\n    )\n    if signal_report.empty:\n        st.info("Signal evidence is still waiting for resolved paired upgrades.")\n    else:\n        signal_view = signal_report.copy()\n        for col in ["Relative MAE Improvement", "Improved Share"]:\n            signal_view[col] = signal_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if col == "Relative MAE Improvement" else f"{float(x):.1%}")\n        st.dataframe(signal_view[["Signal", "Market", "Resolved Pairs", "Pre MAE", "Post MAE", "Relative MAE Improvement", "Improved Share", "Status", "Reason"]], hide_index=True, width="stretch")\n    st.caption("Signals remain LEARNING below 20 resolved pairs. HELPING/MIXED/HURTING are evidence labels only; sportsbook data is excluded.")\n\n'''
text = replace_once(
    text,
    'plays = build_model_board(slate, history, limit=5, market_health=health_map)\n',
    signal_expander + 'plays = build_model_board(slate, history, limit=5, market_health=health_map)\n',
    "top signal expander",
)
text = replace_once(
    text,
    'plays = attach_decision_profiles(plays, decision_report)\n',
    'plays = attach_decision_profiles(plays, decision_report)\nplays = attach_signal_profiles(plays, history, signal_report)\n',
    "attach top signal profiles after ranking",
)
text = replace_once(
    text,
    '''decision_supported = int(plays["Decision Evidence"].isin(["SUPPORTED", "STRONG EVIDENCE"]).sum())\nc1, c2, c3, c4 = st.columns(4)\nc1.metric("Highest model hit probability", f"{plays['Model Probability'].max():.1%}")\nc2.metric("Model-qualified Top 5", model_plays)\nc3.metric("Decision-supported legs", decision_supported)\nc4.metric("Exact live prices found", f"{live_offers}/{len(plays)}")\n''',
    '''decision_supported = int(plays["Decision Evidence"].isin(["SUPPORTED", "STRONG EVIDENCE"]).sum())\nsignal_supported = int(plays["Signal Evidence"].eq("SUPPORTED").sum())\nc1, c2, c3, c4, c5 = st.columns(5)\nc1.metric("Highest model hit probability", f"{plays['Model Probability'].max():.1%}")\nc2.metric("Model-qualified Top 5", model_plays)\nc3.metric("Decision-supported legs", decision_supported)\nc4.metric("Signal-supported legs", signal_supported)\nc5.metric("Exact live prices found", f"{live_offers}/{len(plays)}")\n''',
    "top signal metric",
)
text = replace_once(
    text,
    'view = plays[["Rank", "Status", "Model Health", "Decision Evidence", "Decision Sample", "Tier Hit Rate", "Pitcher", "Weather Icon", "Weather Risk", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Starter History", "Book", "Odds"]].copy()\n',
    'view = plays[["Rank", "Status", "Model Health", "Decision Evidence", "Decision Sample", "Signal Evidence", "Signal Sample", "Tier Hit Rate", "Pitcher", "Weather Icon", "Weather Risk", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Starter History", "Book", "Odds"]].copy()\n',
    "top signal columns",
)
text = replace_once(
    text,
    'st.caption("Eligible markets are ranked only by our calibrated hit probability, with data quality as the tie-breaker. Walk-forward model health can block a proven-unhealthy market; decision evidence is descriptive only; sportsbook odds and market edge never decide the Top 5.")\n',
    'st.caption("Eligible markets are ranked only by our calibrated hit probability, with data quality as the tie-breaker. Walk-forward model health can block a proven-unhealthy market; decision evidence and signal evidence are descriptive only; sportsbook odds and market edge never decide the Top 5.")\n',
    "top board caption signal",
)
text = replace_once(
    text,
    '''        st.caption(f"Decision evidence: {play_row.get('Decision Evidence', 'LEARNING')} · n={int(play_row.get('Decision Sample', 0) or 0)}")\n''',
    '''        st.caption(f"Decision evidence: {play_row.get('Decision Evidence', 'LEARNING')} · n={int(play_row.get('Decision Sample', 0) or 0)}")\n        st.caption(f"Signal evidence: {play_row.get('Signal Evidence', 'LEARNING')} · {play_row.get('Signal Detail', 'No mature paired signal evidence yet.')}")\n''',
    "top action signal caption",
)
# Add signal evidence to the detailed rationale immediately after decision evidence.
rationale_anchor = '''    st.caption(\n        f"Decision evidence: {decision_evidence} · exact segment {decision_band} model probability / quality {decision_quality} · "\n        f"{decision_sample} settled walk-forward legs · historical hit rate {tier_text}. This evidence does not change the projection itself."\n    )\n'''
rationale_new = rationale_anchor + '''    st.caption(\n        f"Signal evidence: {play.get('Signal Evidence', 'LEARNING')} · {play.get('Signal Detail', 'No mature paired signal evidence yet.')} "\n        "Paired signal evidence is attached after ranking and does not change the baseball projection or Top 5 order."\n    )\n'''
text = replace_once(text, rationale_anchor, rationale_new, "top rationale signal evidence")
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Contracts: signal evidence must be post-ranking and lineup Hits audit must be
# retained. The UI must explicitly keep weather as context-only.
# ---------------------------------------------------------------------------
path = Path("tests/test_signal_ui_contract.py")
path.write_text('''from pathlib import Path\n\n\ndef test_top_plays_attaches_signal_evidence_after_model_board():\n    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")\n    build_pos = source.index("plays = build_model_board(slate, history, limit=5, market_health=health_map)")\n    attach_pos = source.index("plays = attach_signal_profiles(plays, history, signal_report)")\n    assert attach_pos > build_pos\n    assert "signal evidence are descriptive only" in source\n    assert "Signal Evidence" in source\n\n\ndef test_projection_history_exposes_paired_signal_accountability():\n    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")\n    assert "🧪 Signal accountability" in source\n    assert "paired_signal_report(df)" in source\n    assert "context_performance_report(df)" in source\n    assert "Weather Delay Risk is labeled CONTEXT ONLY" in source\n\n\ndef test_lineup_refresh_preserves_hits_before_after_evidence():\n    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")\n    for field in (\n        "lineup_preconfirm_hits_projection",\n        "lineup_preconfirm_opponent_hit_rate",\n        "lineup_hits_projection_delta",\n        "lineup_opponent_hit_delta",\n    ):\n        assert field in source\n''', encoding="utf-8")

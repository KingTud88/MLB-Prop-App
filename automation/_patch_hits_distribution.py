from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing patch anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"non-unique patch anchor: {label} count={text.count(old)}")
    return text.replace(old, new, 1)


app_path = Path("streamlit_app.py")
app = app_path.read_text(encoding="utf-8")
old = '''    st.markdown('<div class="section-head">DISTRIBUTION</div>',unsafe_allow_html=True); st.caption(f"{game.pitcher_name} · {game.team} vs {game.opponent}"); a,b=st.columns(2)\n    with a:\n        st.markdown("### Strikeout probability distribution")\n        st.bar_chart(pd.DataFrame({"Probability":proj.k_probs},index=np.arange(len(proj.k_probs))))\n        explain_popover(static_explanation("distribution_k"),label="ⓘ EXPLAIN K DISTRIBUTION")\n    with b:\n        st.markdown("### Outs probability distribution")\n        st.bar_chart(pd.DataFrame({"Probability":proj.outs_probs},index=np.arange(len(proj.outs_probs))))\n        explain_popover(static_explanation("distribution_outs"),label="ⓘ EXPLAIN OUTS DISTRIBUTION")\n    st.stop()'''
new = '''    st.markdown('<div class="section-head">DISTRIBUTION</div>',unsafe_allow_html=True); st.caption(f"{game.pitcher_name} · {game.team} vs {game.opponent}"); a,b,c=st.columns(3)\n    with a:\n        st.markdown("### Strikeout probability distribution")\n        st.bar_chart(pd.DataFrame({"Probability":proj.k_probs},index=np.arange(len(proj.k_probs))))\n        explain_popover(static_explanation("distribution_k"),label="ⓘ EXPLAIN K DISTRIBUTION")\n    with b:\n        st.markdown("### Outs probability distribution")\n        st.bar_chart(pd.DataFrame({"Probability":proj.outs_probs},index=np.arange(len(proj.outs_probs))))\n        explain_popover(static_explanation("distribution_outs"),label="ⓘ EXPLAIN OUTS DISTRIBUTION")\n    with c:\n        st.markdown("### Hits Allowed probability distribution")\n        hits_distribution=np.bincount(np.asarray(hits_proj.simulation_samples,dtype=int))\n        hits_distribution=hits_distribution/hits_distribution.sum()\n        st.bar_chart(pd.DataFrame({"Probability":hits_distribution},index=np.arange(len(hits_distribution))))\n        explain_popover(static_explanation("distribution_hits"),label="ⓘ EXPLAIN HITS DISTRIBUTION")\n    st.stop()'''
app = replace_once(app, old, new, "Distribution block")
app_path.write_text(app, encoding="utf-8")


explain_path = Path("engine/explainability_ui.py")
explain = explain_path.read_text(encoding="utf-8")
anchor = '''        "distribution_outs": Explanation(\n            "Outs probability distribution",\n            "The bars show the simulated probability mass across possible total outs recorded by the starter.",\n            "The independent outs model uses starter-only workload history and its own simulation/math paths. The displayed distribution comes from its simulation samples.",\n            note="Outs are projected independently from strikeouts; they are not derived by multiplying the K projection.",\n        ),'''
replacement = anchor + '''\n        "distribution_hits": Explanation(\n            "Hits Allowed probability distribution",\n            "The bars show how often each Hits Allowed total occurred in the independent Hits Allowed simulation path for this start.",\n            "The existing Hits Allowed simulation samples workload/batters faced and a pregame matchup hit rate, then draws game-level hit totals. This chart only summarizes those already-computed simulation outcomes.",\n            note="This is the Hits Allowed simulation path only. It does not use sportsbook prices and does not change the projection or recommendation.",\n        ),'''
explain = replace_once(explain, anchor, replacement, "Hits distribution explanation")
explain_path.write_text(explain, encoding="utf-8")

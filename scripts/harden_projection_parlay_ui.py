from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'st.markdown("#### Add recommendation to Bet Tracker")\n',
    'st.markdown("#### Add recommendation to Bet Tracker / Parlay")\n',
    "recommendation action heading",
)
text = replace_once(
    text,
    'render_projection_parlay_builder()\nwith st.expander(f"🔎 Why this projection? · {game.pitcher_name}", expanded=False):\n',
    'with st.expander(f"🔎 Why this projection? · {game.pitcher_name}", expanded=False):\n',
    "remove early builder",
)
text = replace_once(
    text,
    '''    else: st.info("Live market data will populate here when the Odds API returns the pitcher props.")\nst.markdown(f'<div class="search-note">Data status: {proj.confidence} confidence · quality {proj.quality}/100 · locked: {locked} · engine v{APP_VERSION}</div>',unsafe_allow_html=True)\n''',
    '''    else: st.info("Live market data will populate here when the Odds API returns the pitcher props.")\nrender_projection_parlay_builder()\nst.markdown(f'<div class="search-note">Data status: {proj.confidence} confidence · quality {proj.quality}/100 · locked: {locked} · engine v{APP_VERSION}</div>',unsafe_allow_html=True)\n''',
    "move builder after all actions",
)
path.write_text(text, encoding="utf-8")

path = Path("pages/2_Bet_Tracker.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''if stake_series.isna().any():\n    st.caption("Older saved bets without a stake are still graded, but they are excluded from P/L and ROI calculations.")\n\nst.subheader("Tracked bets")\n''',
    '''if stake_series.isna().any():\n    st.caption("Older saved bets without a stake are still graded, but they are excluded from P/L and ROI calculations.")\nif "american_odds" in tracker.columns and pd.to_numeric(tracker["american_odds"], errors="coerce").isna().any():\n    st.caption("Unpriced model tickets are still graded WIN/LOSS from MLB results, but they stay excluded from P/L and ROI because no sportsbook price was assumed.")\n\nst.subheader("Tracked bets")\n''',
    "unpriced tracker explanation",
)
path.write_text(text, encoding="utf-8")

path = Path("tests/test_bet_add_buttons_contract.py")
text = path.read_text(encoding="utf-8")
anchor = '''    assert "Fair Odds are model-only and are never saved as a sportsbook price" in source\n\n\n'''
replacement = '''    assert "Fair Odds are model-only and are never saved as a sportsbook price" in source\n    ladder_pos = source.index('key=f"projection_k_ladder_{game.key}"')\n    builder_pos = source.rindex("render_projection_parlay_builder()")\n    assert ladder_pos < builder_pos\n\n\n'''
text = replace_once(text, anchor, replacement, "builder ordering contract")
path.write_text(text, encoding="utf-8")

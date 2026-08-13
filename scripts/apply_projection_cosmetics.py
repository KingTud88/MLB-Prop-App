from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        ".reco-good{color:#49efb0}.reco-neutral{color:#f2f6fa}.reco-warn{color:#ffd166}",
        ".reco-good{color:#49efb0}.reco-under{color:#ff4b5f}.reco-neutral{color:#f2f6fa}.reco-warn{color:#ffd166}",
        "recommendation color CSS",
    ),
    (
        'cls="reco-warn" if side=="PASS" else "reco-good"',
        'cls="reco-warn" if side=="PASS" else "reco-under" if side=="UNDER" else "reco-good"',
        "recommendation side class",
    ),
    (
        '    st.divider(); selected_date=st.date_input("Slate date",value=datetime.now(EASTERN).date()); st.markdown("### PITCHER SEARCH")\n'
        '    locked_key=st.session_state.get("locked_pitcher"); search=st.text_input("Search pitcher...",placeholder="Search pitcher...",label_visibility="collapsed",disabled=bool(locked_key)); st.caption("Search and select a pitcher to lock the projection 🔒")\n',
        '    st.divider(); selected_date=st.date_input("Slate date",value=datetime.now(EASTERN).date()); st.markdown("### PITCHER")\n'
        '    locked_key=st.session_state.get("locked_pitcher"); st.caption("Select a probable starter, then lock the projection 🔒")\n',
        "pitcher search sidebar",
    ),
    (
        'matches=schedule if locked_game else [g for g in schedule if not search or search.lower() in g.pitcher_name.lower() or search.lower() in g.team.lower()]\n'
        'if not matches: st.info("No pitchers match that search."); st.stop()',
        'matches=schedule if locked_game is None else [locked_game]\n'
        'if not matches: st.info("No probable pitchers are available for this slate."); st.stop()',
        "pitcher search filtering",
    ),
]

for old, new, label in replacements:
    if new in text:
        continue
    if old not in text:
        raise SystemExit(f"{label} anchor not found")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Projection cosmetic cleanup applied")

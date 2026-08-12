from pathlib import Path

# Fix Daily summary: create c6 where it is actually used, and keep rationale at 5 columns.
path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    '    c1, c2, c3, c4, c5, c6 = st.columns(6)\n    c1.metric("Projected Ks"',
    '    c1, c2, c3, c4, c5 = st.columns(5)\n    c1.metric("Projected Ks"',
    1,
)
old = '''    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Projected starters", len(slate))
'''
new = '''    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Projected starters", len(slate))
'''
if old not in text:
    raise SystemExit("Daily summary metric anchor missing")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# A totally missing confirmed-lineup person payload should explicitly carry
# league H/PA rather than relying on DataFrame column completion to create NaN.
path = Path("engine/opposing_batters.py")
text = path.read_text(encoding="utf-8")
old = '''                    "Lineup Spot": slot_map.get(pid, np.nan),
                    "K% vs Pitcher": LEAGUE_K_RATE,
                    "PA": 0.0,
                    "Risk": _risk(LEAGUE_K_RATE),
'''
new = '''                    "Lineup Spot": slot_map.get(pid, np.nan),
                    "K% vs Pitcher": LEAGUE_K_RATE,
                    "H/PA vs Pitcher": LEAGUE_HIT_RATE,
                    "PA": 0.0,
                    "Risk": _risk(LEAGUE_K_RATE),
'''
if old not in text:
    raise SystemExit("confirmed hitter contact fallback anchor missing")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# Strengthen contract so this Streamlit regression cannot come back.
path = Path("tests/test_lineup_integration_contract.py")
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_daily_confirmed_lineup_metric_has_sixth_column():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    summary = source[source.index('slate = st.session_state.get("daily_slate")'):]\n    assert 'c1, c2, c3, c4, c5, c6 = st.columns(6)' in summary\n    assert 'c6.metric("Confirmed lineups", confirmed_lineups)' in summary\n'''
path.write_text(text, encoding="utf-8")

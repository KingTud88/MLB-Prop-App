from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
anchor = '''    if nav == "Daily Projection Run":
        st.switch_page("pages/5_Daily_Projection_Run.py")
'''
insert = '''    if nav == "Bet Tracker":
        st.switch_page("pages/2_Bet_Tracker.py")
    if nav == "Daily Projection Run":
        st.switch_page("pages/5_Daily_Projection_Run.py")
'''
if 'st.switch_page("pages/2_Bet_Tracker.py")' not in text:
    if anchor not in text:
        raise SystemExit("Bet Tracker route anchor not found")
    text = text.replace(anchor, insert, 1)
path.write_text(text, encoding="utf-8")

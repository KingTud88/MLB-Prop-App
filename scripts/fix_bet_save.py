from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

old = '''    nav=st.radio("Navigation",["Projection","Distribution","Form & Workload","Model Card","Bet Tracker","Projection History","Daily Projection Run"],label_visibility="collapsed")
    st.divider(); selected_date=st.date_input("Slate date",value=datetime.now(EASTERN).date()); st.markdown("### PITCHER SEARCH")'''

new = '''    nav=st.radio("Navigation",["Projection","Distribution","Form & Workload","Model Card","Bet Tracker","Projection History","Daily Projection Run"],label_visibility="collapsed")
    if nav == "Daily Projection Run":
        st.switch_page("pages/5_Daily_Projection_Run.py")
    st.divider(); selected_date=st.date_input("Slate date",value=datetime.now(EASTERN).date()); st.markdown("### PITCHER SEARCH")'''

if new in text:
    print("Daily Projection Run navigation already routed.")
elif old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Daily Projection Run now routes to the batch page.")
else:
    raise SystemExit("Expected Daily Projection Run navigation block was not found; refusing unsafe patch")

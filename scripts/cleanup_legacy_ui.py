from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

old_sidebar = '''with st.sidebar:\n    st.markdown("## StrikeOut King 9000"); st.caption(f"Distributional MLB starter projections · v{APP_VERSION}"); selected_date=st.date_input("Slate date",value=odds_default_date); st.markdown("### Model controls"); simulations=st.select_slider("Simulation draws",[5000,10000,25000,50000],value=25000); opponent_k_pct=st.slider("Projected lineup K%",15.0,32.0,22.4,.1); pitch_limit=st.slider("Expected pitch limit",60,115,92); umpire_k_factor=st.slider("Umpire K factor",.94,1.06,1.00,.01); weather_factor=st.slider("Weather K factor",.96,1.04,1.00,.01); rest_days=st.slider("Days rest",3,10,5); rest_factor=.96 if rest_days<=3 else 1.0 if rest_days<=6 else 1.01; st.caption("Market lines affect edge display only, never the baseball forecast.")'''

new_sidebar = '''with st.sidebar:\n    st.markdown("## StrikeOut King 9000")\n    st.caption(f"Distributional MLB starter projections · v{APP_VERSION}")\n    selected_date=st.date_input("Slate date",value=odds_default_date)\n    st.caption("Model inputs are now handled by the projection engine; legacy manual controls have been removed.")\n\n# Keep stable internal defaults for the current projection engine while dedicated feeds are added.\nsimulations=25000\nopponent_k_pct=22.4\npitch_limit=92\numprire_k_factor=1.00\numpire_k_factor=1.00\nweather_factor=1.00\nrest_factor=1.00'''

if old_sidebar not in text:
    raise SystemExit("Expected legacy sidebar block was not found; refusing to edit.")
text = text.replace(old_sidebar, new_sidebar, 1)

old_manual = 'st.divider(); st.subheader("Manual sportsbook line"); st.caption("Enter the line and price you see at your sportsbook. No sportsbook API or paid credits required.")'
new_manual = 'st.divider(); st.subheader("Manual sportsbook line (fallback)"); st.caption("Use this only when an Odds API line is unavailable. No sportsbook API or paid credits required.")'
if old_manual not in text:
    raise SystemExit("Expected manual-line block was not found; refusing to edit.")
text = text.replace(old_manual, new_manual, 1)

old_limitations = '- Projected lineup K%, umpire, weather, and pitch limit are manual until dedicated feeds are connected.\\\n- This is an inference dashboard, not yet a trained walk-forward gradient-boosted production model.\\\n- Calibration must be measured on archived pregame snapshots before probabilities can be considered production-grade.'
new_limitations = '- Legacy sidebar controls have been removed; the current engine uses stable internal defaults while dedicated lineup, umpire, weather, and workload feeds are connected.\\\n- This is an inference dashboard, not yet a trained walk-forward gradient-boosted production model.\\\n- Calibration must be measured on archived pregame snapshots before probabilities can be considered production-grade.'
if old_limitations in text:
    text = text.replace(old_limitations, new_limitations, 1)

path.write_text(text, encoding="utf-8")
print("Legacy StrikeOut King 9000 UI cleanup applied.")

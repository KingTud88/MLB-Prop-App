from pathlib import Path

p=Path('streamlit_app.py')
s=p.read_text(encoding='utf-8')
s=s.replace('from engine.calibration import calibrate_blend, calibration_summary','from engine.calibration import calibrate_blend, calibration_summary, milestone_calibration_report',1)
# Insert a reusable dashboard helper before the page-routing section.
anchor='def ladder(proj,max_line=10):'
if anchor not in s:
    raise SystemExit('ladder anchor not found')
helper='''def render_calibration_dashboard():\n    st.markdown("### Milestone Calibration Dashboard")\n    st.caption("Resolved pregame projections only. Sportsbook prices are excluded from training.")\n    history=load_projection_history()\n    report=milestone_calibration_report(history, range(3,11), min_observations=30)\n    display=report.copy()\n    for col in ["Simulation Brier","Math Brier","Calibrated Brier"]:\n        display[col]=display[col].map(lambda x:"—" if pd.isna(x) else f"{x:.4f}")\n    for col in ["Simulation Weight","Math Weight","Actual Hit Rate"]:\n        display[col]=display[col].map(lambda x:"—" if pd.isna(x) else f"{x:.1%}")\n    st.dataframe(display,use_container_width=True,hide_index=True)\n    resolved=int(pd.to_numeric(history.get("actual_strikeouts"),errors="coerce").notna().sum()) if not history.empty and "actual_strikeouts" in history.columns else 0\n    st.info(f"{resolved} resolved projections currently available. Each milestone learns independently after 30 valid observations; until then it stays at a 50/50 simulation/math baseline.")\n\n\n'''
s=s.replace(anchor,helper+anchor,1)
# Add the dashboard to Model Card if that page block exists.
needle='st.markdown("### Calibration diagnostics")'
if needle in s:
    s=s.replace(needle,needle+'\n    render_calibration_dashboard()',1)
else:
    # Safe fallback: expose it as a standalone call immediately before page routing.
    s=s.replace(anchor,'render_calibration_dashboard()\n\n'+anchor,1)
p.write_text(s,encoding='utf-8')
print('calibration dashboard integrated')

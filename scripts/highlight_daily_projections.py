from pathlib import Path

page = Path("pages/5_Daily_Projection_Run.py")
text = page.read_text(encoding="utf-8")

anchor = '''        st.subheader(f"{slate_date:%B %d, %Y} starter slate")\n        st.caption("Click any pitcher row to inspect why the model produced that frozen projection.")\n        event = st.dataframe(\n            display,\n'''
replacement = '''        projection_highlight_cols = [\n            col for col in ("Projection K", "Projection Hits Allowed", "Projection Outs")\n            if col in display.columns\n        ]\n        styled_display = display.style\n        if projection_highlight_cols:\n            styled_display = styled_display.map(\n                lambda value: "color: #22c55e; font-weight: 700;" if pd.notna(value) else "",\n                subset=projection_highlight_cols,\n            )\n\n        st.subheader(f"{slate_date:%B %d, %Y} starter slate")\n        st.caption("Click any pitcher row to inspect why the model produced that frozen projection. Headline projection numbers are highlighted in green for faster scanning.")\n        event = st.dataframe(\n            styled_display,\n'''
if anchor not in text:
    raise SystemExit("Daily dataframe render anchor not found")
page.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")

contract = Path("tests/test_daily_projection_highlight.py")
contract.write_text('''from pathlib import Path\n\n\ndef test_daily_headline_projection_numbers_are_green_and_bold():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert '("Projection K", "Projection Hits Allowed", "Projection Outs")' in source\n    assert 'color: #22c55e; font-weight: 700;' in source\n    assert 'subset=projection_highlight_cols' in source\n    assert 'st.dataframe(\\n            styled_display,' in source\n''', encoding="utf-8")

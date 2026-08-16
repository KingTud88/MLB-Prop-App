from pathlib import Path

path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")
old = '''def _manual_input_default(row: pd.Series, line_col: str, source_col: str) -> str:\n    if str(row.get(source_col, "") or "").strip().upper() != "MANUAL":\n        return ""\n    value = pd.to_numeric(pd.Series([row.get(line_col)]), errors="coerce").iloc[0]\n    return "" if pd.isna(value) else f"{float(value):g}"\n'''
new = '''def _manual_input_default(row: pd.Series, line_col: str, source_col: str) -> str:\n    source = row.get(source_col, "")\n    if pd.isna(source) or str(source).strip().upper() != "MANUAL":\n        return ""\n    value = pd.to_numeric(pd.Series([row.get(line_col)]), errors="coerce").iloc[0]\n    return "" if pd.isna(value) else f"{float(value):g}"\n'''
if new in text:
    print("Manual prefill NA guard already applied")
elif old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Applied manual prefill NA guard")
else:
    raise RuntimeError("Could not find _manual_input_default patch anchor")

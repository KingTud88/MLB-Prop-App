from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
old = 'return True,f"Added to Projection Parlay Builder ({len(legs)}/5)."'
new = 'return True,f"Added to Projection Parlay Builder ({len(legs)} leg" + ("" if len(legs)==1 else "s") + ")."'
if old not in text:
    raise SystemExit("old capped counter message not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

path = Path("tests/test_bet_add_buttons_contract.py")
text = path.read_text(encoding="utf-8")
anchor = '    assert "does not multiply model probabilities" in source\n'
replacement = anchor + '    assert "({len(legs)}/5)" not in source\n'
if anchor not in text:
    raise SystemExit("parlay contract anchor not found")
text = text.replace(anchor, replacement, 1)
path.write_text(text, encoding="utf-8")

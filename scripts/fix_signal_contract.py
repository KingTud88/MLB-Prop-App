from pathlib import Path

path = Path("pages/6_Top_Plays.py")
text = path.read_text(encoding="utf-8")
old = "decision evidence and signal evidence are descriptive only"
new = "decision evidence is descriptive only; signal evidence is descriptive only"
if old not in text:
    raise SystemExit("signal/decision descriptive contract anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

from pathlib import Path

page = Path("pages/6_Top_Plays.py")
text = page.read_text(encoding="utf-8")
old = "decision evidence and signal evidence are descriptive only"
new = "decision evidence is descriptive only; signal evidence is descriptive only"
if old not in text:
    raise SystemExit("signal/decision descriptive contract anchor missing")
page.write_text(text.replace(old, new, 1), encoding="utf-8")

contract = Path("tests/test_signal_ui_contract.py")
contract_text = contract.read_text(encoding="utf-8")
contract_text = contract_text.replace(
    'assert "signal evidence are descriptive only" in source',
    'assert "signal evidence is descriptive only" in source',
)
contract.write_text(contract_text, encoding="utf-8")

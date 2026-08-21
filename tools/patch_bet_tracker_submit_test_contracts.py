from pathlib import Path

path = Path("tests/test_bet_tracker_page_contract.py")
source = path.read_text(encoding="utf-8")
replacements = {
    'selectbox("Status", ["All", "Open / Live", "Settled", "Invalid"]': 'selectbox("Status", status_options',
    'selectbox("Ticket type", ["All", "Straight", "Parlay"]': 'selectbox("Ticket type", type_options',
    'selectbox("Pitcher", ["All"] + pitcher_options': 'selectbox("Pitcher", pitcher_choices',
    'selectbox("Game date", ["All"] + date_options': 'selectbox("Game date", date_choices',
}
for old, new in replacements.items():
    if old in source:
        source = source.replace(old, new)
    elif new not in source:
        raise SystemExit(f"missing expected filter contract: {old}")
path.write_text(source, encoding="utf-8")

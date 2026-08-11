from pathlib import Path

page = Path("pages/6_Top_Plays.py")
source = page.read_text(encoding="utf-8")

old_caption = '''st.caption(
    "Build a parlay directly from our model Top 5. No sportsbook, live-price, or book-matching data is used here. "
    "Select any 2–5 model legs and choose one stake for the entire tracked model ticket."
)'''
new_caption = '''st.caption(
    "Build a parlay directly from our model Top 5. Sportsbook data never filters, ranks, or selects the legs. "
    "Select any 2–5 model legs and choose one stake for the entire tracked model ticket; the sportsbook dropdown is recordkeeping only."
)'''
if old_caption not in source:
    raise SystemExit("Parlay caption anchor not found")
source = source.replace(old_caption, new_caption, 1)

old_stake = '''parlay_stake = st.number_input("Parlay stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_parlay_stake")

if len(selected) >= 2:'''
new_stake = '''parlay_stake = st.number_input("Parlay stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_parlay_stake")
parlay_book = st.selectbox(
    "Sportsbook (recordkeeping only)",
    [
        "Not tracked",
        "FanDuel",
        "DraftKings",
        "BetMGM",
        "Caesars Sportsbook",
        "Fanatics Sportsbook",
        "bet365",
        "ESPN BET",
        "Hard Rock Bet",
        "BetRivers",
        "Other / Not listed",
    ],
    key="top_plays_parlay_book",
    help="This only labels the saved Bet Tracker ticket. It never changes the Top 5, available legs, model probability, or parlay selection.",
)
parlay_book_value = "" if parlay_book == "Not tracked" else parlay_book

if len(selected) >= 2:'''
if old_stake not in source:
    raise SystemExit("Parlay stake anchor not found")
source = source.replace(old_stake, new_stake, 1)

old_record = '''            record = make_parlay_record(
                legs=legs,
                stake=float(parlay_stake),
                game_date=today,
                source="Top Plays Model Parlay",
            )'''
new_record = '''            record = make_parlay_record(
                legs=legs,
                stake=float(parlay_stake),
                game_date=today,
                book=parlay_book_value,
                source="Top Plays Model Parlay",
            )'''
if old_record not in source:
    raise SystemExit("Parlay record anchor not found")
source = source.replace(old_record, new_record, 1)
page.write_text(source, encoding="utf-8")

contract_path = Path("tests/test_bet_add_buttons_contract.py")
contract = contract_path.read_text(encoding="utf-8")
needle = '''    assert 'Actual parlay American odds (optional)' not in source\n    assert 'book=book_note' not in source\n'''
replacement = '''    assert 'Actual parlay American odds (optional)' not in source\n    assert 'book=book_note' not in source\n    assert '"Sportsbook (recordkeeping only)"' in source\n    assert 'book=parlay_book_value' in source\n    parlay_block = source[source.index('st.subheader("🎟️ Parlay Builder")'):]\n    assert 'candidate_pool' not in parlay_block\n    assert 'parlay_book_value' in parlay_block\n'''
if needle not in contract:
    raise SystemExit("Contract anchor not found")
contract = contract.replace(needle, replacement, 1)
contract_path.write_text(contract, encoding="utf-8")

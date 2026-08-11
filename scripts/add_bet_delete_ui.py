from pathlib import Path

# One-shot patch for persistent Bet Tracker deletion UI.
path = Path("pages/2_Bet_Tracker.py")
source = path.read_text(encoding="utf-8")

source = source.replace(
    "from training.bet_storage import append_bet, load_bet_log",
    "from training.bet_storage import append_bet, bet_row_key, delete_bet, load_bet_log",
    1,
)

parlay_anchor = '''            resolved_rows.append({
                "Pitcher": f"{len(legs)}-leg parlay",'''
parlay_replacement = '''            resolved_rows.append({
                "_BetKey": bet_row_key(row),
                "Pitcher": f"{len(legs)}-leg parlay",'''
if parlay_anchor not in source:
    raise SystemExit("Parlay resolved-row anchor not found")
source = source.replace(parlay_anchor, parlay_replacement, 1)

straight_anchor = '''        resolved_rows.append({
            "Pitcher": player,'''
straight_replacement = '''        resolved_rows.append({
            "_BetKey": bet_row_key(row),
            "Pitcher": player,'''
if straight_anchor not in source:
    raise SystemExit("Straight resolved-row anchor not found")
source = source.replace(straight_anchor, straight_replacement, 1)

view_anchor = '''st.subheader("Tracked bets")
view = results.copy()
'''
view_replacement = '''st.subheader("Tracked bets")

ticket_labels: dict[str, str] = {}
for _, ticket in results.iterrows():
    key = str(ticket.get("_BetKey", ""))
    if not key:
        continue
    date = str(ticket.get("Date", ""))
    pitcher = str(ticket.get("Pitcher", "Unknown"))
    market = str(ticket.get("Market", ""))
    bet = str(ticket.get("Bet", ""))
    book = str(ticket.get("Book", "") or "—")
    ticket_labels[key] = f"{date} · {pitcher} · {market} · {bet} · {book}"

with st.expander("🗑️ Delete a saved bet", expanded=False):
    if ticket_labels:
        delete_key = st.selectbox(
            "Saved ticket",
            options=list(ticket_labels),
            format_func=lambda key: ticket_labels[key],
            key="bet_tracker_delete_key",
        )
        confirm_delete = st.checkbox(
            "Confirm deletion of this saved ticket",
            value=False,
            key="bet_tracker_delete_confirm",
            help="Deletion permanently removes this tracked ticket from the persistent bet ledger.",
        )
        if st.button(
            "🗑️ Delete selected bet",
            disabled=not confirm_delete,
            use_container_width=True,
            key="bet_tracker_delete_button",
        ):
            try:
                if delete_bet(BET_LOG, delete_key, st.secrets):
                    st.success("Deleted the selected bet from Bet Tracker.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("That saved bet could not be found. Refresh the tracker and try again.")
            except Exception as exc:
                st.error(f"Could not delete bet: {exc}")
    else:
        st.caption("No saved tickets are available to delete.")

view = results.drop(columns=["_BetKey"], errors="ignore").copy()
'''
if view_anchor not in source:
    raise SystemExit("Tracked bets view anchor not found")
source = source.replace(view_anchor, view_replacement, 1)

source = source.replace(
    '''    results.to_csv(index=False),''',
    '''    results.drop(columns=["_BetKey"], errors="ignore").to_csv(index=False),''',
    1,
)

path.write_text(source, encoding="utf-8")

contract_path = Path("tests/test_bet_add_buttons_contract.py")
contract = contract_path.read_text(encoding="utf-8")
needle = '''    assert 'if bet_type == "Parlay":' in source
'''
replacement = '''    assert 'if bet_type == "Parlay":' in source
    assert "delete_bet" in source
    assert 'st.expander("🗑️ Delete a saved bet"' in source
    assert '"Confirm deletion of this saved ticket"' in source
    assert '"🗑️ Delete selected bet"' in source
'''
if needle not in contract:
    raise SystemExit("Bet tracker contract anchor not found")
contract = contract.replace(needle, replacement, 1)
contract_path.write_text(contract, encoding="utf-8")

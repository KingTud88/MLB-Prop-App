from pathlib import Path

page = Path("pages/2_Bet_Tracker.py")
source = page.read_text(encoding="utf-8")

reset_old = '''    if st.session_state.pop("_bet_tracker_reset_delete_confirm", False):
        st.session_state["bet_tracker_delete_confirm"] = False
'''
reset_new = '''    if st.session_state.pop("_bet_tracker_reset_delete_confirm", False):
        st.session_state["bet_tracker_delete_confirm"] = False
    if st.session_state.pop("_bet_tracker_reset_delete_key", False):
        st.session_state.pop("bet_tracker_delete_key", None)
'''
if source.count(reset_old) != 1:
    raise SystemExit(f"expected one delete reset block, found {source.count(reset_old)}")
source = source.replace(reset_old, reset_new, 1)

filter_start = '    st.markdown(\'<div class="bt-section">Ticket Filters</div>\', unsafe_allow_html=True)\n'
filter_end = '    display_results = results.copy()\n'
if source.count(filter_start) != 1 or source.count(filter_end) != 1:
    raise SystemExit("expected unique Bet Tracker filter boundaries")
start = source.index(filter_start)
end = source.index(filter_end, start)
filter_block = '''    # BET_TRACKER_SUBMIT_CONTROLS_V1
    st.markdown('<div class="bt-section">Ticket Filters</div>', unsafe_allow_html=True)
    settled_states = {"WIN", "LOSS", "PUSH", "PUSH LEG"}
    pitcher_options = sorted({
        str(leg.get("Player", "")).strip()
        for legs in results["_Legs"]
        if isinstance(legs, list)
        for leg in legs
        if isinstance(leg, dict) and str(leg.get("Player", "")).strip()
    })
    date_options = sorted({str(value) for value in results["Date"].dropna().tolist() if str(value).strip()}, reverse=True)

    status_options = ["All", "Open / Live", "Settled", "Invalid"]
    type_options = ["All", "Straight", "Parlay"]
    pitcher_choices = ["All"] + pitcher_options
    date_choices = ["All"] + date_options
    applied_filter_specs = (
        ("_bet_tracker_applied_status_filter", "bet_tracker_status_filter", status_options),
        ("_bet_tracker_applied_type_filter", "bet_tracker_type_filter", type_options),
        ("_bet_tracker_applied_pitcher_filter", "bet_tracker_pitcher_filter", pitcher_choices),
        ("_bet_tracker_applied_date_filter", "bet_tracker_date_filter", date_choices),
    )
    for applied_key, draft_key, options in applied_filter_specs:
        if applied_key not in st.session_state:
            candidate = st.session_state.get(draft_key, "All")
            st.session_state[applied_key] = candidate if candidate in options else "All"
        elif st.session_state.get(applied_key) not in options:
            st.session_state[applied_key] = "All"
        if st.session_state.get(draft_key, "All") not in options:
            st.session_state[draft_key] = st.session_state[applied_key]

    with st.form("bet_tracker_filter_form", clear_on_submit=False):
        f1, f2, f3, f4 = st.columns([1.0, 1.0, 1.45, 1.0])
        status_draft = f1.selectbox("Status", status_options, key="bet_tracker_status_filter")
        type_draft = f2.selectbox("Ticket type", type_options, key="bet_tracker_type_filter")
        pitcher_draft = f3.selectbox("Pitcher", pitcher_choices, key="bet_tracker_pitcher_filter")
        date_draft = f4.selectbox("Game date", date_choices, key="bet_tracker_date_filter")
        apply_filters = st.form_submit_button("Apply filters", type="primary", use_container_width=True)

    if apply_filters:
        st.session_state["_bet_tracker_applied_status_filter"] = status_draft
        st.session_state["_bet_tracker_applied_type_filter"] = type_draft
        st.session_state["_bet_tracker_applied_pitcher_filter"] = pitcher_draft
        st.session_state["_bet_tracker_applied_date_filter"] = date_draft

    status_filter = st.session_state.get("_bet_tracker_applied_status_filter", "All")
    type_filter = st.session_state.get("_bet_tracker_applied_type_filter", "All")
    pitcher_filter = st.session_state.get("_bet_tracker_applied_pitcher_filter", "All")
    date_filter = st.session_state.get("_bet_tracker_applied_date_filter", "All")

'''
source = source[:start] + filter_block + source[end:]

delete_start = '    with st.expander("🗑️ Delete a saved bet", expanded=False):\n'
delete_end = '    # BET_TRACKER_TICKET_CARDS_V1\n'
if source.count(delete_start) != 1 or source.count(delete_end) != 1:
    raise SystemExit("expected unique Bet Tracker delete boundaries")
start = source.index(delete_start)
end = source.index(delete_end, start)
delete_block = '''    with st.expander("🗑️ Delete a saved bet", expanded=False):
        if ticket_labels:
            if st.session_state.get("bet_tracker_delete_key") not in ticket_labels:
                st.session_state.pop("bet_tracker_delete_key", None)
            with st.form("bet_tracker_delete_form", clear_on_submit=False):
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
                delete_submitted = st.form_submit_button(
                    "🗑️ Delete selected bet",
                    use_container_width=True,
                )
            if delete_submitted:
                if not confirm_delete:
                    st.warning("Confirm deletion before deleting the selected ticket.")
                else:
                    try:
                        if delete_bet(BET_LOG, delete_key, st.secrets):
                            deleted_keys.add(str(delete_key))
                            st.session_state["_bet_tracker_deleted_keys"] = sorted(deleted_keys)
                            st.session_state["_bet_tracker_reset_delete_confirm"] = True
                            st.session_state["_bet_tracker_reset_delete_key"] = True
                            st.success("Deleted the selected bet from Bet Tracker.")
                            st.rerun(scope="fragment")
                        else:
                            st.warning("That saved bet could not be found. Refresh the tracker and try again.")
                    except Exception as exc:
                        st.error(f"Could not delete bet: {exc}")
        else:
            st.caption("No saved tickets are available to delete.")

'''
source = source[:start] + delete_block + source[end:]
page.write_text(source, encoding="utf-8")

test_path = Path("tests/test_bet_tracker_page_contract.py")
test_source = test_path.read_text(encoding="utf-8")
contract = '''\n\ndef test_bet_tracker_filter_and_delete_choices_wait_for_submit():\n    path = Path(__file__).resolve().parents[1] / "pages" / "2_Bet_Tracker.py"\n    source = path.read_text(encoding="utf-8")\n    compile(source, str(path), "exec")\n    marker = "# BET_TRACKER_SUBMIT_CONTROLS_V1"\n    assert marker in source\n    block = source[source.index("# BET_TRACKER_FRAGMENT_WORKSPACE_V1"):]\n    assert 'with st.form("bet_tracker_filter_form", clear_on_submit=False):' in block\n    assert 'apply_filters = st.form_submit_button("Apply filters"' in block\n    assert 'st.session_state["_bet_tracker_applied_status_filter"] = status_draft' in block\n    assert 'st.session_state["_bet_tracker_applied_type_filter"] = type_draft' in block\n    assert 'with st.form("bet_tracker_delete_form", clear_on_submit=False):' in block\n    assert 'delete_submitted = st.form_submit_button(' in block\n    assert 'st.button(\n                "🗑️ Delete selected bet"' not in block\n    assert 'st.session_state["_bet_tracker_reset_delete_key"] = True' in block\n    assert 'st.rerun(scope="fragment")' in block\n'''
if "def test_bet_tracker_filter_and_delete_choices_wait_for_submit():" not in test_source:
    test_path.write_text(test_source.rstrip() + contract + "\n", encoding="utf-8")

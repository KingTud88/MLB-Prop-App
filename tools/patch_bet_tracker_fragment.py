from pathlib import Path

page = Path("pages/2_Bet_Tracker.py")
source = page.read_text(encoding="utf-8")
start_marker = 'wins = int((results["Result"] == "WIN").sum())\n'
if source.count(start_marker) != 1:
    raise SystemExit(f"expected exactly one workspace start marker, found {source.count(start_marker)}")
start = source.index(start_marker)
head = source[:start]
tail = source[start:]

old_delete = '''                if delete_bet(BET_LOG, delete_key, st.secrets):
                    st.success("Deleted the selected bet from Bet Tracker.")
                    st.cache_data.clear()
                    st.rerun()
'''
new_delete = '''                if delete_bet(BET_LOG, delete_key, st.secrets):
                    deleted_keys.add(str(delete_key))
                    st.session_state["_bet_tracker_deleted_keys"] = sorted(deleted_keys)
                    st.session_state["_bet_tracker_reset_delete_confirm"] = True
                    st.success("Deleted the selected bet from Bet Tracker.")
                    st.rerun(scope="fragment")
'''
if tail.count(old_delete) != 1:
    raise SystemExit(f"expected exactly one delete success block, found {tail.count(old_delete)}")
tail = tail.replace(old_delete, new_delete, 1)

prefix = '''# BET_TRACKER_FRAGMENT_WORKSPACE_V1
@st.fragment
def render_tracker_workspace(results: pd.DataFrame, tracker: pd.DataFrame) -> None:
    deleted_keys = set(st.session_state.get("_bet_tracker_deleted_keys", []))
    if deleted_keys:
        results = results.loc[~results["_BetKey"].astype(str).isin(deleted_keys)].copy()
        if not tracker.empty:
            keep_mask = [bet_row_key(row) not in deleted_keys for _, row in tracker.iterrows()]
            tracker = tracker.loc[keep_mask].copy()
    if st.session_state.pop("_bet_tracker_reset_delete_confirm", False):
        st.session_state["bet_tracker_delete_confirm"] = False

'''
indented_tail = "".join("    " + line if line.strip() else line for line in tail.splitlines(keepends=True))
new_source = head + prefix + indented_tail + '\n\nrender_tracker_workspace(results, tracker)\n'
page.write_text(new_source, encoding="utf-8")

test_path = Path("tests/test_bet_tracker_page_contract.py")
test_source = test_path.read_text(encoding="utf-8")
contract = '''\n\ndef test_bet_tracker_delete_and_filters_are_fragment_scoped():\n    path = Path(__file__).resolve().parents[1] / "pages" / "2_Bet_Tracker.py"\n    source = path.read_text(encoding="utf-8")\n    compile(source, str(path), "exec")\n    marker = "# BET_TRACKER_FRAGMENT_WORKSPACE_V1"\n    assert marker in source\n    start = source.index(marker)\n    block = source[start:]\n    assert "@st.fragment\\ndef render_tracker_workspace(" in block\n    assert 'selectbox("Status", ["All", "Open / Live", "Settled", "Invalid"]' in block\n    assert 'with st.expander("🗑️ Delete a saved bet"' in block\n    assert '"Confirm deletion of this saved ticket"' in block\n    assert '"🗑️ Delete selected bet"' in block\n    assert 'st.rerun(scope="fragment")' in block\n    delete_start = block.index('with st.expander("🗑️ Delete a saved bet"')\n    delete_end = block.index("# BET_TRACKER_TICKET_CARDS_V1", delete_start)\n    delete_block = block[delete_start:delete_end]\n    assert "st.rerun()" not in delete_block\n    assert 'st.session_state["_bet_tracker_deleted_keys"]' in delete_block\n    assert source.rstrip().endswith("render_tracker_workspace(results, tracker)")\n'''
if "def test_bet_tracker_delete_and_filters_are_fragment_scoped():" not in test_source:
    test_path.write_text(test_source.rstrip() + contract + "\n", encoding="utf-8")

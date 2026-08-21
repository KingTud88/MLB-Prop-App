from pathlib import Path

page = Path("pages/2_Bet_Tracker.py")
source = page.read_text(encoding="utf-8")

load_block = '''tracker = load_tracker()\nif tracker.empty:\n    st.info("No saved bets yet. Use Add a bet above to start the ledger.")\n    st.stop()\n\n'''
replacement = '''tracker = load_tracker()\nif tracker.empty:\n    st.info("No saved bets yet. Use Add a bet above to start the ledger.")\n    st.stop()\n\n# BET_TRACKER_PERSISTED_KEY_V1\n# Capture the identity from the raw persisted row before display normalization.\ntracker["_PersistedBetKey"] = [bet_row_key(row) for _, row in tracker.iterrows()]\n\n'''
if source.count(load_block) != 1:
    raise SystemExit(f"expected one tracker load block, found {source.count(load_block)}")
source = source.replace(load_block, replacement, 1)

old_key = '"_BetKey": bet_row_key(row),'
new_key = '"_BetKey": str(row.get("_PersistedBetKey") or bet_row_key(row)),'
if source.count(old_key) != 2:
    raise SystemExit(f"expected two resolved ticket key assignments, found {source.count(old_key)}")
source = source.replace(old_key, new_key)
page.write_text(source, encoding="utf-8")

test_path = Path("tests/test_bet_tracker_page_contract.py")
test_source = test_path.read_text(encoding="utf-8")
contract = '''\n\ndef test_bet_tracker_preserves_raw_persisted_key_before_display_normalization():\n    path = Path(__file__).resolve().parents[1] / "pages" / "2_Bet_Tracker.py"\n    source = path.read_text(encoding="utf-8")\n    compile(source, str(path), "exec")\n    marker = '# BET_TRACKER_PERSISTED_KEY_V1'\n    assert marker in source\n    assert 'tracker["_PersistedBetKey"] = [bet_row_key(row) for _, row in tracker.iterrows()]' in source\n    assert source.index(marker) < source.index('tracker.loc[straight_mask, "market"]')\n    assert source.count('"_BetKey": str(row.get("_PersistedBetKey") or bet_row_key(row)),') == 2\n'''
if "def test_bet_tracker_preserves_raw_persisted_key_before_display_normalization():" not in test_source:
    test_path.write_text(test_source.rstrip() + contract + "\n", encoding="utf-8")

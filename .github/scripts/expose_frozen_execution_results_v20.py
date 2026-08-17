from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

history_path = ROOT / "pages" / "4_Projection_History.py"
source = history_path.read_text(encoding="utf-8")
old = '''        "projection", "archive_k_target", "actual_strikeouts", "archive_k_result", "manual_strikeout_line",
        "outs_projection", "actual_outs", "manual_outs_line",
        "manual_hits_allowed_line", "hits_projection", "actual_hits_allowed",
        "confidence", "data_quality", "archive_source", "archive_committed_at_utc",
'''
new = '''        "projection", "archive_k_target", "actual_strikeouts", "archive_k_result", "manual_strikeout_line",
        "outs_projection", "manual_outs_line", "manual_outs_side", "actual_outs", "archive_outs_bet_result",
        "hits_projection", "manual_hits_allowed_line", "manual_hits_allowed_side", "actual_hits_allowed", "archive_hits_bet_result",
        "confidence", "data_quality", "archive_source", "archive_committed_at_utc",
'''
if old not in source:
    raise SystemExit("Projection Archive column anchor not found")
source = source.replace(old, new, 1)
history_path.write_text(source, encoding="utf-8")

test_path = ROOT / "tests" / "test_frozen_execution_history.py"
test_source = test_path.read_text(encoding="utf-8")
anchor = '''    assert '"Hits Side"' in history and '"Hits Bet Result"' in history
    assert "manual_outs_side_frozen_at_utc" in storage
'''
replacement = '''    assert '"Hits Side"' in history and '"Hits Bet Result"' in history
    archive_block = history[history.index("archive_columns = ["):history.index("unique_dates =", history.index("archive_columns = ["))]
    assert '"manual_outs_side"' in archive_block and '"archive_outs_bet_result"' in archive_block
    assert '"manual_hits_allowed_side"' in archive_block and '"archive_hits_bet_result"' in archive_block
    assert "manual_outs_side_frozen_at_utc" in storage
'''
if anchor not in test_source:
    raise SystemExit("Execution history test anchor not found")
test_source = test_source.replace(anchor, replacement, 1)
test_path.write_text(test_source, encoding="utf-8")

print("expose_frozen_execution_results_v20 applied")

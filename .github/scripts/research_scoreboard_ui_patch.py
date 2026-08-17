from pathlib import Path

PAGE = Path("pages/4_Projection_History.py")
TEST = Path("tests/test_research_promotion_scoreboard_ui_contract.py")

text = PAGE.read_text(encoding="utf-8")

import_anchor = "from engine.execution_history import backfill_legacy_execution_sides, grade_frozen_execution\n"
import_line = "from engine.research_promotion_scoreboard import render_research_promotion_scoreboard\n"
if import_line not in text:
    if import_anchor not in text:
        raise SystemExit("Projection History import anchor not found")
    text = text.replace(import_anchor, import_anchor + import_line, 1)

call = "render_research_promotion_scoreboard(ROOT)"
if call not in text:
    anchor = '    label="ⓘ EXPLAIN EVIDENCE SCOREBOARD",\n)\n\nst.divider()\nst.markdown(\'<div class="history-kicker">Actionable K results</div>\', unsafe_allow_html=True)'
    replacement = '    label="ⓘ EXPLAIN EVIDENCE SCOREBOARD",\n)\n\n# RESEARCH_PROMOTION_SCOREBOARD_V1 · presentation/reporting only.\nrender_research_promotion_scoreboard(ROOT)\n\nst.divider()\nst.markdown(\'<div class="history-kicker">Actionable K results</div>\', unsafe_allow_html=True)'
    if anchor not in text:
        raise SystemExit("Projection History evidence-scoreboard insertion anchor not found")
    text = text.replace(anchor, replacement, 1)

PAGE.write_text(text, encoding="utf-8")

TEST.write_text(
    '''from pathlib import Path\n\n\ndef test_projection_history_renders_research_promotion_scoreboard_after_evidence_scoreboard() -> None:\n    text = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")\n    assert "from engine.research_promotion_scoreboard import render_research_promotion_scoreboard" in text\n    assert "render_research_promotion_scoreboard(ROOT)" in text\n    evidence = text.index('label="ⓘ EXPLAIN EVIDENCE SCOREBOARD"')\n    board = text.index("render_research_promotion_scoreboard(ROOT)")\n    actionable = text.index("Actionable K results")\n    assert evidence < board < actionable\n\n\ndef test_research_scoreboard_is_report_only_and_source_owned() -> None:\n    text = Path("engine/research_promotion_scoreboard.py").read_text(encoding="utf-8")\n    assert "Native research verdicts are displayed as written by each validator" in text\n    assert "Production Authority" in text\n    assert "The scoreboard does not recalculate them" in text\n    assert "cannot change the live baseball projection" in text\n''',
    encoding="utf-8",
)

print("Research Promotion Scoreboard UI patch staged")

from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "pages" / "5_Daily_Projection_Run.py"


def test_daily_run_uses_automated_market_line_ui_without_manual_entry_boxes():
    source = PAGE.read_text(encoding="utf-8")

    assert "📡 Automated sportsbook lines" in source
    assert "SportsGameOdds captures real pregame Strikeouts, Total Outs, and Hits Allowed lines automatically." in source

    # Historical MANUAL persistence can remain underneath for old rows, but the
    # active Daily Run UI must not expose the old per-pitcher line-entry boxes.
    assert "daily_manual_k_" not in source
    assert "daily_manual_outs_" not in source
    assert "daily_manual_hits_" not in source
    assert "daily_apply_archive" not in source

    # Keep the explicitly labeled K-only emergency backup available without
    # turning it back into the primary execution-line workflow.
    assert "LOAD STRIKEOUT LINES · BACKUP API" in source
    assert "SportsGameOdds remains the primary automated execution-line source." in source

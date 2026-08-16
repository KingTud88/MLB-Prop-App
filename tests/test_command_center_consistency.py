from pathlib import Path

from engine.command_center_consistency import COMMAND_CENTER_UI_VERSION, SUPPORTED_PAGES


ROOT = Path(__file__).resolve().parents[1]


def test_all_secondary_pages_use_shared_command_center_consistency():
    pages = {
        "pages/2_Bet_Tracker.py": "bet_tracker",
        "pages/4_Projection_History.py": "projection_history",
        "pages/5_Daily_Projection_Run.py": "daily_run",
        "pages/6_Top_Plays.py": "top_plays",
    }
    assert set(pages.values()) == SUPPORTED_PAGES
    for path, page_key in pages.items():
        source = (ROOT / path).read_text(encoding="utf-8")
        assert "from engine.command_center_consistency import apply_command_center_consistency" in source
        assert f'apply_command_center_consistency("{page_key}")' in source


def test_consistency_layer_is_presentation_only():
    source = (ROOT / "engine" / "command_center_consistency.py").read_text(encoding="utf-8")
    assert COMMAND_CENTER_UI_VERSION == "command-center-consistency-v1"
    assert "requests" not in source
    assert "ProjectionEngine" not in source
    assert "append_bet" not in source
    assert "projection_log" not in source
    assert "odds" not in source.lower()
    assert "COMMAND_CENTER_CONSISTENCY_V1" in source


def test_old_top_plays_mascot_override_is_removed():
    source = (ROOT / "pages" / "6_Top_Plays.py").read_text(encoding="utf-8")
    assert "Reliable sidebar mascot fallback for this page" not in source
    assert 'sk-nav-mascot img{display:none!important}' not in source


def test_bet_tracker_duplicate_style_triplet_is_collapsed():
    source = (ROOT / "pages" / "2_Bet_Tracker.py").read_text(encoding="utf-8")
    marker = '[data-testid="stCaptionContainer"]{color:#b8c8d6!important;font-size:.80rem!important;line-height:1.42!important}'
    assert source.count(marker) == 1


def test_secondary_pages_have_deliberate_mobile_reflow():
    source = (ROOT / "engine" / "command_center_consistency.py").read_text(encoding="utf-8")
    assert "COMMAND_CENTER_MOBILE_V2" in source
    assert "@media (max-width:640px)" in source
    assert "@media (max-width:480px)" in source
    assert 'flex:1 1 100%!important' in source

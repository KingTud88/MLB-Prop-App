from pathlib import Path


def test_command_center_embeds_local_mascot_and_uses_readable_small_text():
    source = Path("engine/ui_command_center.py").read_text(encoding="utf-8")
    assert 'COMMAND_CENTER_UI_VERSION = "cle-command-center-v6"' in source
    assert 'MASCOT_PATH = ASSET_DIR / "strikeout_king_9000.png"' in source
    assert "cc-hero-fallback" in source
    assert "st.image(str(MASCOT_PATH)" not in source
    assert "data:image/png;base64" not in source
    assert "raw.githubusercontent.com" not in source
    assert 'font-family:Inter,"Segoe UI",Roboto,Arial,sans-serif' in source
    assert ".cc-status-label" in source
    assert ".cc-matchup-name" in source

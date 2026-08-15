from pathlib import Path


def test_command_center_embeds_local_mascot_and_uses_readable_small_text():
    source = Path("engine/ui_command_center.py").read_text(encoding="utf-8")
    assert 'COMMAND_CENTER_UI_VERSION = "cle-command-center-v7"' in source
    assert 'MASCOT_PATH = ASSET_DIR / "strikeout_king_9000_clean.png"' in source
    assert "cc-hero-fallback" in source
    assert "st.image(str(MASCOT_PATH), width=190)" in source
    assert "data:image/png;base64" not in source
    assert "raw.githubusercontent.com" not in source
    assert '--cc-ui-font:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif' in source
    assert ".cc-status-label" in source
    assert ".cc-matchup-name" in source


def test_verified_mascot_asset_is_real_png():
    from PIL import Image
    path = Path("assets/strikeout_king_9000_clean.png")
    assert path.exists()
    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.size[0] >= 160 and image.size[1] >= 160
        image.verify()

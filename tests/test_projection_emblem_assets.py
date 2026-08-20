from pathlib import Path

from PIL import Image

NAMES = [
    "projection_k.webp", "projection_k_plus.webp",
    "projection_outs.webp", "projection_outs_plus.webp",
    "projection_hits.webp", "projection_hits_plus.webp",
]


def test_projection_emblems_are_high_resolution_assets():
    for name in NAMES:
        image = Image.open(Path("assets") / name)
        assert image.size == (256, 256)
        assert image.format == "WEBP"


def test_projection_page_uses_v14_highres_asset_cache_key():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    for name in NAMES:
        assert f"{name}?v=14" in source

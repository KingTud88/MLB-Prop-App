from __future__ import annotations

from pathlib import Path

from PIL import Image


ASSETS = Path("assets")
APPROVED_EMBLEMS = (
    "projection_k.webp",
    "projection_k_plus.webp",
    "projection_outs.webp",
    "projection_outs_plus.webp",
    "projection_hits.webp",
    "projection_hits_plus.webp",
)
CORRUPT_LEGACY_SPRITE = "projection_summary_emblems_v2.webp"


def test_projection_summary_uses_individual_approved_emblem_assets() -> None:
    for filename in APPROVED_EMBLEMS:
        path = ASSETS / filename
        assert path.is_file(), f"missing approved projection emblem: {filename}"
        with Image.open(path) as image:
            assert image.size == (256, 256), f"unexpected dimensions for {filename}"
            assert image.format == "WEBP", f"unexpected image format for {filename}"


def test_corrupt_projection_summary_sprite_stays_retired() -> None:
    assert not (ASSETS / CORRUPT_LEGACY_SPRITE).exists()

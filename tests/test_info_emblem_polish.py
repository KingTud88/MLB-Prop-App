from pathlib import Path


def test_card_info_v5_uses_geometric_centered_i():
    source = Path("engine/card_explainability.py").read_text(encoding="utf-8")
    assert 'CARD_EXPLAINABILITY_VERSION = "card-info-v5"' in source
    assert "CARD_INFO_GEOMETRIC_V5" in source
    assert 'button::before' in source
    assert 'button::after' in source
    assert 'left:50%!important' in source


def test_projection_emblems_use_reliable_individual_assets_at_larger_size():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "PROJECTION_EMBLEM_HIGHRES_V14" in source
    assert "width:124px!important" in source
    assert "height:124px!important" in source
    assert "background-size:120px 120px!important" in source
    for asset in ("projection_k.webp?v=14", "projection_k_plus.webp?v=14", "projection_outs.webp?v=14", "projection_outs_plus.webp?v=14", "projection_hits.webp?v=14", "projection_hits_plus.webp?v=14"):
        assert asset in source


def test_ui_polish_does_not_change_projection_or_market_contracts():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "calculate_projection(" in source
    assert "load_pitcher_market_odds" in source
    assert "aligned_bet_lean(" in source


def test_projection_emblem_assets_are_high_resolution():
    from PIL import Image

    for name in (
        "projection_k.webp",
        "projection_k_plus.webp",
        "projection_outs.webp",
        "projection_outs_plus.webp",
        "projection_hits.webp",
        "projection_hits_plus.webp",
    ):
        with Image.open(Path("assets") / name) as img:
            assert img.size == (256, 256), f"{name} was {img.size}"

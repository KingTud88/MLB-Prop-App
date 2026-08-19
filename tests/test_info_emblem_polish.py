from pathlib import Path


def test_card_info_v3_uses_clean_plain_i_control():
    source = Path("engine/card_explainability.py").read_text(encoding="utf-8")
    assert 'CARD_EXPLAINABILITY_VERSION = "card-info-v4"' in source
    assert '        "i",\n        help=f"Explain {explanation.title}",' in source
    assert 'button [data-testid=\"stIconMaterial\"]' in source
    assert 'width:1.96rem!important' in source
    assert 'font:900 1.04rem/1' in source
    assert 'button::before' in source
    assert 'top:49%!important' in source


def test_projection_emblems_render_at_native_128px_master_size():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "PROJECTION_EMBLEM_SIZE_V10" in source
    assert "projection_summary_emblems_v2.webp" in source
    assert "PROJECTION_EMBLEM_NATIVE_V12" in source
    assert "width:128px!important" in source
    assert "height:128px!important" in source
    assert "projection_summary_emblems_v2.webp?v=12" in source
    assert "background-size:600% 100%!important" in source
    assert "drop-shadow(0 1px 1px" in source
    assert "projection_k.webp?v=11" in source
    assert "projection_k_plus.webp?v=11" in source
    assert "projection_outs.webp?v=11" in source
    assert "projection_outs_plus.webp?v=11" in source
    assert "projection_hits.webp?v=11" in source
    assert "projection_hits_plus.webp?v=11" in source


def test_ui_polish_does_not_change_projection_or_market_contracts():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "calculate_projection(" in source
    assert "load_pitcher_market_odds" in source
    assert "aligned_bet_lean(" in source
    assert "require_market_lines=True" not in source  # Top Plays owns that contract, not Projection

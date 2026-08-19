from pathlib import Path

APP = Path("streamlit_app.py")
CARD = Path("engine/card_explainability.py")
TEST = Path("tests/test_info_emblem_polish.py")

app = APP.read_text(encoding="utf-8")
card = CARD.read_text(encoding="utf-8")

marker = "/* PROJECTION_SUMMARY_NO_LINE_V14"
block = r'''/* PROJECTION_EMBLEM_RECOVERY_V13 · reliable individual approved assets, larger footprint */
.metric-card,.reco-card{padding-right:142px!important}
.metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{
    right:8px!important;
    top:36px!important;
    width:120px!important;
    height:120px!important;
    min-width:120px!important;
    flex:0 0 120px!important;
    background-size:116px 116px!important;
    background-repeat:no-repeat!important;
    background-position:center!important;
    image-rendering:auto!important;
    filter:drop-shadow(0 1px 1px rgba(0,0,0,.22))!important;
    transform:translateZ(0)!important;
}
.metric-card .cc-emblem.whiff{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_k.webp?v=13")!important}
.reco-card .cc-emblem.whiff{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_k_plus.webp?v=13")!important}
.metric-card .cc-emblem.glove{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_outs.webp?v=13")!important}
.reco-card .cc-emblem.glove{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_outs_plus.webp?v=13")!important}
.metric-card .cc-emblem.contact{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_hits.webp?v=13")!important}
.reco-card .cc-emblem.contact{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_hits_plus.webp?v=13")!important}
@media (max-width:900px){
    .metric-card,.reco-card{padding-right:120px!important}
    .metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{
        right:8px!important;top:42px!important;width:98px!important;height:98px!important;min-width:98px!important;flex-basis:98px!important;background-size:94px 94px!important
    }
}
@media (max-width:620px){
    .metric-card,.reco-card{padding-right:100px!important}
    .metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{
        right:7px!important;top:46px!important;width:82px!important;height:82px!important;min-width:82px!important;flex-basis:82px!important;background-size:78px 78px!important
    }
}

'''
if "PROJECTION_EMBLEM_RECOVERY_V13" not in app:
    app = app.replace(marker, block + marker, 1)
APP.write_text(app, encoding="utf-8")

card = card.replace('CARD_EXPLAINABILITY_VERSION = "card-info-v4"', 'CARD_EXPLAINABILITY_VERSION = "card-info-v5"')
geo = r'''
        /* CARD_INFO_GEOMETRIC_V5 · exact centered dot + stem, no font-baseline dependency */
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button::before{
            content:""!important;
            position:absolute!important;
            left:50%!important;
            top:6px!important;
            transform:translateX(-50%)!important;
            width:3.5px!important;
            height:3.5px!important;
            border-radius:50%!important;
            background:#f6fbff!important;
            pointer-events:none!important;
        }
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button::after{
            content:""!important;
            position:absolute!important;
            left:50%!important;
            top:11px!important;
            transform:translateX(-50%)!important;
            width:3px!important;
            height:8px!important;
            border-radius:2px!important;
            background:#f6fbff!important;
            pointer-events:none!important;
        }
'''
insert = '        @media (max-width:640px){\n'
if "CARD_INFO_GEOMETRIC_V5" not in card:
    card = card.replace(insert, geo + insert, 1)
CARD.write_text(card, encoding="utf-8")

TEST.write_text('''from pathlib import Path\n\n\ndef test_card_info_v5_uses_geometric_centered_i():\n    source = Path("engine/card_explainability.py").read_text(encoding="utf-8")\n    assert 'CARD_EXPLAINABILITY_VERSION = "card-info-v5"' in source\n    assert "CARD_INFO_GEOMETRIC_V5" in source\n    assert 'button::before' in source\n    assert 'button::after' in source\n    assert 'left:50%!important' in source\n\n\ndef test_projection_emblems_use_reliable_individual_assets_at_larger_size():\n    source = Path("streamlit_app.py").read_text(encoding="utf-8")\n    assert "PROJECTION_EMBLEM_RECOVERY_V13" in source\n    assert "width:120px!important" in source\n    assert "height:120px!important" in source\n    assert "background-size:116px 116px!important" in source\n    for asset in ("projection_k.webp?v=13", "projection_k_plus.webp?v=13", "projection_outs.webp?v=13", "projection_outs_plus.webp?v=13", "projection_hits.webp?v=13", "projection_hits_plus.webp?v=13"):\n        assert asset in source\n\n\ndef test_ui_polish_does_not_change_projection_or_market_contracts():\n    source = Path("streamlit_app.py").read_text(encoding="utf-8")\n    assert "calculate_projection(" in source\n    assert "load_pitcher_market_odds" in source\n    assert "aligned_bet_lean(" in source\n''', encoding="utf-8")

from pathlib import Path

CARD = Path("engine/card_explainability.py")
APP = Path("streamlit_app.py")
TEST = Path("tests/test_info_emblem_polish.py")

card = CARD.read_text(encoding="utf-8")
app = APP.read_text(encoding="utf-8")
test = TEST.read_text(encoding="utf-8")

if 'CARD_EXPLAINABILITY_VERSION = "card-info-v3"' not in card:
    raise SystemExit("unexpected card explainability version")
card = card.replace('CARD_EXPLAINABILITY_VERSION = "card-info-v3"', 'CARD_EXPLAINABILITY_VERSION = "card-info-v4"', 1)
card = card.replace('2.06rem', '1.96rem')

center_css = r'''
        /* CARD_INFO_CENTER_V4 · optically centered plain-i control */
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button{
            position:relative!important;
            padding:0!important;
            line-height:0!important;
            font-size:0!important;
        }
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button p,
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button [data-testid="stMarkdownContainer"] p{
            margin:0!important;
            padding:0!important;
            font-size:0!important;
            line-height:0!important;
            color:transparent!important;
            transform:none!important;
        }
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button::before{
            content:"i";
            position:absolute!important;
            left:50%!important;
            top:49%!important;
            transform:translate(-50%,-50%)!important;
            width:100%!important;
            text-align:center!important;
            font:900 1.02rem/1 Arial,"Helvetica Neue",sans-serif!important;
            color:#f6fbff!important;
            letter-spacing:0!important;
            pointer-events:none!important;
        }
'''
anchor = '        @media (max-width:640px){\n'
if center_css.strip() not in card:
    if anchor not in card:
        raise SystemExit("card media anchor missing")
    card = card.replace(anchor, center_css + anchor, 1)

emblem_css = r'''
/* PROJECTION_EMBLEM_NATIVE_V12 · native 128px sprite tiles, larger and sharper */
.metric-card,.reco-card{padding-right:150px!important}
.metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{
    right:8px!important;
    top:34px!important;
    width:128px!important;
    height:128px!important;
    min-width:128px!important;
    flex:0 0 128px!important;
    background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_summary_emblems_v2.webp?v=12")!important;
    background-size:600% 100%!important;
    background-repeat:no-repeat!important;
    image-rendering:auto!important;
    filter:drop-shadow(0 1px 1px rgba(0,0,0,.28)) drop-shadow(0 0 1px rgba(236,22,56,.08))!important;
    transform:translateZ(0)!important;
}
.metric-card .cc-emblem.whiff{background-position:0% 50%!important}
.reco-card .cc-emblem.whiff{background-position:20% 50%!important}
.metric-card .cc-emblem.glove{background-position:40% 50%!important}
.reco-card .cc-emblem.glove{background-position:60% 50%!important}
.metric-card .cc-emblem.contact{background-position:80% 50%!important}
.reco-card .cc-emblem.contact{background-position:100% 50%!important}
@media (max-width:900px){
    .metric-card,.reco-card{padding-right:126px!important}
    .metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{
        right:8px!important;top:40px!important;width:104px!important;height:104px!important;min-width:104px!important;flex-basis:104px!important;background-size:600% 100%!important
    }
}
@media (max-width:620px){
    .metric-card,.reco-card{padding-right:106px!important}
    .metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{
        right:7px!important;top:45px!important;width:88px!important;height:88px!important;min-width:88px!important;flex-basis:88px!important;background-size:600% 100%!important
    }
}

'''
marker = '/* PROJECTION_SUMMARY_NO_LINE_V14'
if emblem_css.strip() not in app:
    if marker not in app:
        raise SystemExit("projection summary marker missing")
    app = app.replace(marker, emblem_css + marker, 1)

# Refresh the focused regression contract to describe the final visual path.
test = test.replace('CARD_EXPLAINABILITY_VERSION = "card-info-v3"', 'CARD_EXPLAINABILITY_VERSION = "card-info-v4"')
test = test.replace('width:2.06rem!important', 'width:1.96rem!important')
if 'assert \'button::before\' in source' not in test:
    test = test.replace('    assert \'font:900 1.04rem/1\' in source\n', '    assert \'font:900 1.04rem/1\' in source\n    assert \'button::before\' in source\n    assert \'top:49%!important\' in source\n')

test = test.replace('def test_projection_emblems_render_larger_from_existing_128px_master():', 'def test_projection_emblems_render_at_native_128px_master_size():')
test = test.replace('    assert "width:108px!important" in source\n', '    assert "PROJECTION_EMBLEM_NATIVE_V12" in source\n    assert "width:128px!important" in source\n')
test = test.replace('    assert "height:108px!important" in source\n', '    assert "height:128px!important" in source\n')
test = test.replace('    assert "background-size:104px 104px!important" in source\n', '    assert "projection_summary_emblems_v2.webp?v=12" in source\n    assert "background-size:600% 100%!important" in source\n')
test = test.replace('    assert "drop-shadow(0 2px 1px" in source\n', '    assert "drop-shadow(0 1px 1px" in source\n')

CARD.write_text(card, encoding="utf-8")
APP.write_text(app, encoding="utf-8")
TEST.write_text(test, encoding="utf-8")

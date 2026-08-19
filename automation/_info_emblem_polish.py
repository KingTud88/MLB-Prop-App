from pathlib import Path

CARD = Path("engine/card_explainability.py")
APP = Path("streamlit_app.py")
TEST = Path("tests/test_info_emblem_polish.py")

card = CARD.read_text(encoding="utf-8")

card = card.replace('CARD_EXPLAINABILITY_VERSION = "card-info-v2"', 'CARD_EXPLAINABILITY_VERSION = "card-info-v3"')

replacements = {
    '            top:.48rem!important;\n            right:.52rem!important;\n            z-index:40!important;\n            width:1.78rem!important;':
    '            top:.42rem!important;\n            right:.46rem!important;\n            z-index:40!important;\n            width:2.06rem!important;',
    '            width:1.78rem!important;\n            min-width:1.78rem!important;\n            margin:0!important;':
    '            width:2.06rem!important;\n            min-width:2.06rem!important;\n            margin:0!important;',
    '            width:1.78rem!important;\n            min-width:1.78rem!important;\n            height:1.78rem!important;\n            min-height:1.78rem!important;\n            padding:0!important;\n            border-radius:999px!important;\n            border:1px solid rgba(113,154,188,.78)!important;\n            background:rgba(7,25,43,.92)!important;\n            color:#d9ebf8!important;\n            font:900 .88rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;\n            letter-spacing:0!important;\n            text-transform:none!important;\n            box-shadow:0 4px 12px rgba(0,0,0,.22)!important;':
    '            width:2.06rem!important;\n            min-width:2.06rem!important;\n            height:2.06rem!important;\n            min-height:2.06rem!important;\n            padding:0 0 .06rem!important;\n            display:flex!important;\n            align-items:center!important;\n            justify-content:center!important;\n            border-radius:999px!important;\n            border:1.5px solid rgba(151,192,222,.88)!important;\n            background:linear-gradient(145deg,rgba(12,39,63,.98),rgba(5,20,35,.98))!important;\n            color:#f3f9fd!important;\n            font:900 1.04rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;\n            letter-spacing:0!important;\n            text-transform:none!important;\n            box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 5px 13px rgba(0,0,0,.28),0 0 0 1px rgba(77,135,179,.08)!important;',
    '            border-color:#ff3655!important;\n            color:#fff!important;\n            background:#351225!important;\n            box-shadow:0 0 0 1px rgba(236,22,56,.12),0 6px 15px rgba(236,22,56,.20)!important;':
    '            border-color:#ff3655!important;\n            color:#fff!important;\n            background:linear-gradient(145deg,#451327,#281020)!important;\n            box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 0 0 2px rgba(236,22,56,.12),0 7px 17px rgba(236,22,56,.22)!important;',
    '                width:1.72rem!important;\n                min-width:1.72rem!important;\n                height:1.72rem!important;\n                min-height:1.72rem!important;':
    '                width:1.86rem!important;\n                min-width:1.86rem!important;\n                height:1.86rem!important;\n                min-height:1.86rem!important;'
}
for old, new in replacements.items():
    if old not in card:
        raise SystemExit(f"expected card CSS block not found: {old[:60]}")
    card = card.replace(old, new, 1)

anchor = '''        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button:hover{\n            border-color:#ff3655!important;\n            color:#fff!important;\n            background:linear-gradient(145deg,#451327,#281020)!important;\n            box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 0 0 2px rgba(236,22,56,.12),0 7px 17px rgba(236,22,56,.22)!important;\n        }\n'''
extra = '''        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button svg{display:none!important}\n        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button p,\n        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button [data-testid="stMarkdownContainer"] p{\n            margin:0!important;\n            padding:0!important;\n            font:900 1.04rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;\n            transform:translateY(-.015rem)!important;\n        }\n        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button:focus-visible{\n            outline:none!important;\n            border-color:#fff!important;\n            box-shadow:0 0 0 2px rgba(236,22,56,.34),0 7px 17px rgba(0,0,0,.30)!important;\n        }\n'''
if extra not in card:
    if anchor not in card:
        raise SystemExit("hover anchor not found")
    card = card.replace(anchor, anchor + extra, 1)

if '        "ⓘ",\n        help=f"Explain {explanation.title}",' not in card:
    raise SystemExit("popover glyph anchor not found")
card = card.replace('        "ⓘ",\n        help=f"Explain {explanation.title}",', '        "i",\n        help=f"Explain {explanation.title}",', 1)
CARD.write_text(card, encoding="utf-8")

app = APP.read_text(encoding="utf-8")
marker = '/* PROJECTION_EMBLEM_SIZE_V10 · larger 128px-master rendering with crisper edge treatment */'
if marker not in app:
    insert_at = '''.reco-card .cc-emblem.contact{background-position:100% 50%!important}\n\n\n/* PROJECTION_SUMMARY_NO_LINE_V14'''
    if insert_at not in app:
        raise SystemExit("emblem master anchor not found")
    polish = '''.reco-card .cc-emblem.contact{background-position:100% 50%!important}\n\n/* PROJECTION_EMBLEM_SIZE_V10 · larger 128px-master rendering with crisper edge treatment */\n.metric-card,.reco-card{padding-right:132px!important}\n.metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{\n    right:12px!important;\n    top:42px!important;\n    width:108px!important;\n    height:108px!important;\n    min-width:108px!important;\n    flex:0 0 108px!important;\n    background-size:600% 100%!important;\n    background-repeat:no-repeat!important;\n    image-rendering:auto!important;\n    filter:drop-shadow(0 2px 1px rgba(0,0,0,.30)) drop-shadow(0 0 1px rgba(236,22,56,.10))!important;\n    transform:translateZ(0)!important;\n}\n@media (max-width:900px){\n    .metric-card,.reco-card{padding-right:108px!important}\n    .metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{\n        right:10px!important;top:48px!important;width:88px!important;height:88px!important;min-width:88px!important;flex-basis:88px!important;background-size:600% 100%!important\n    }\n}\n@media (max-width:620px){\n    .metric-card,.reco-card{padding-right:92px!important}\n    .metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{\n        right:8px!important;top:49px!important;width:76px!important;height:76px!important;min-width:76px!important;flex-basis:76px!important;background-size:600% 100%!important\n    }\n}\n\n\n/* PROJECTION_SUMMARY_NO_LINE_V14'''
    app = app.replace(insert_at, polish, 1)
APP.write_text(app, encoding="utf-8")

TEST.write_text('''from pathlib import Path\n\n\ndef test_card_info_v3_uses_clean_plain_i_control():\n    source = Path("engine/card_explainability.py").read_text(encoding="utf-8")\n    assert 'CARD_EXPLAINABILITY_VERSION = "card-info-v3"' in source\n    assert '        "i",\\n        help=f"Explain {explanation.title}",' in source\n    assert 'button svg{display:none!important}' in source\n    assert 'width:2.06rem!important' in source\n    assert 'font:900 1.04rem/1' in source\n\n\ndef test_projection_emblems_render_larger_from_existing_128px_master():\n    source = Path("streamlit_app.py").read_text(encoding="utf-8")\n    assert "PROJECTION_EMBLEM_SIZE_V10" in source\n    assert "projection_summary_emblems_v2.webp" in source\n    assert "width:108px!important" in source\n    assert "height:108px!important" in source\n    assert "background-size:600% 100%!important" in source\n    assert "drop-shadow(0 2px 1px" in source\n\n\ndef test_ui_polish_does_not_change_projection_or_market_contracts():\n    source = Path("streamlit_app.py").read_text(encoding="utf-8")\n    assert "calculate_projection(" in source\n    assert "load_pitcher_market_odds" in source\n    assert "aligned_bet_lean(" in source\n    assert "require_market_lines=True" not in source  # Top Plays owns that contract, not Projection\n''', encoding="utf-8")

from pathlib import Path

APP = Path("streamlit_app.py")
INFO = Path("engine/card_explainability.py")
TEST = Path("tests/test_info_emblem_polish.py")

app = APP.read_text(encoding="utf-8")
marker = "/* PROJECTION_EMBLEM_SIZE_V10 · larger 128px-master rendering with crisper edge treatment */"
if marker not in app:
    raise SystemExit("missing emblem size marker")
head, tail = app.split(marker, 1)
# The six approved individual images already win the background-image cascade.
# The bug was forcing sprite-sheet sizing (600% x 100%) onto those individual images.
for replacement in (
    "background-size:104px 104px!important;",
    "background-size:84px 84px!important",
    "background-size:72px 72px!important",
):
    if "background-size:600% 100%!important" not in tail:
        raise SystemExit("expected sprite-size override missing")
    tail = tail.replace("background-size:600% 100%!important", replacement, 1)

explicit_images = r'''
/* PROJECTION_EMBLEM_IMAGE_LOCK_V11 · individual approved art; no sprite-sheet scaling */
.metric-card .cc-emblem.whiff{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_k.webp?v=11")!important;background-position:center!important}
.reco-card .cc-emblem.whiff{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_k_plus.webp?v=11")!important;background-position:center!important}
.metric-card .cc-emblem.glove{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_outs.webp?v=11")!important;background-position:center!important}
.reco-card .cc-emblem.glove{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_outs_plus.webp?v=11")!important;background-position:center!important}
.metric-card .cc-emblem.contact{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_hits.webp?v=11")!important;background-position:center!important}
.reco-card .cc-emblem.contact{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_hits_plus.webp?v=11")!important;background-position:center!important}
'''
if "PROJECTION_EMBLEM_IMAGE_LOCK_V11" not in tail:
    insert_at = tail.find("@media (max-width:900px){")
    if insert_at < 0:
        raise SystemExit("missing emblem responsive marker")
    tail = tail[:insert_at] + explicit_images + tail[insert_at:]
APP.write_text(head + marker + tail, encoding="utf-8")

info = INFO.read_text(encoding="utf-8")
needle = '.stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button svg{display:none!important}'
replacement = '''.stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button svg,
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button [data-testid="stIconMaterial"],
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button span[class*="material-symbols"]{display:none!important}
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button{gap:0!important}'''
if needle not in info:
    raise SystemExit("missing info icon hide rule")
info = info.replace(needle, replacement, 1)
INFO.write_text(info, encoding="utf-8")

test = TEST.read_text(encoding="utf-8")
test = test.replace("assert 'button svg{display:none!important}' in source", "assert 'button [data-testid=\\\"stIconMaterial\\\"]' in source")
test = test.replace('assert "background-size:600% 100%!important" in source', 'assert "background-size:104px 104px!important" in source')
if 'projection_k_plus.webp?v=11' not in test:
    test = test.replace(
        'assert "drop-shadow(0 2px 1px" in source',
        'assert "drop-shadow(0 2px 1px" in source\n    assert "projection_k.webp?v=11" in source\n    assert "projection_k_plus.webp?v=11" in source\n    assert "projection_outs.webp?v=11" in source\n    assert "projection_outs_plus.webp?v=11" in source\n    assert "projection_hits.webp?v=11" in source\n    assert "projection_hits_plus.webp?v=11" in source',
    )
TEST.write_text(test, encoding="utf-8")

# Fast deterministic checks before the normal PR quality workflow.
app2 = APP.read_text(encoding="utf-8")
info2 = INFO.read_text(encoding="utf-8")
assert "PROJECTION_EMBLEM_IMAGE_LOCK_V11" in app2
assert "background-size:104px 104px!important" in app2
assert "background-size:84px 84px!important" in app2
assert "background-size:72px 72px!important" in app2
assert "projection_k_plus.webp?v=11" in app2
assert 'button [data-testid="stIconMaterial"]' in info2
print("emblem render hotfix applied")

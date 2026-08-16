from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
MARKER = "PROJECTION_SUMMARY_EMBLEMS_V3"


def uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


WHIFF = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">
<defs><linearGradient id="bat" x1="0" x2="1"><stop stop-color="#7b3518"/><stop offset=".55" stop-color="#d88739"/><stop offset="1" stop-color="#ffd08a"/></linearGradient><radialGradient id="ball"><stop stop-color="#fff"/><stop offset="1" stop-color="#dfe7ed"/></radialGradient></defs>
<path d="M19 70 C28 65 35 58 43 49" fill="none" stroke="#25a9ff" stroke-width="4" stroke-linecap="round" opacity=".62"/>
<path d="M14 76 C27 72 39 65 50 54" fill="none" stroke="#25a9ff" stroke-width="2.5" stroke-linecap="round" opacity=".28"/>
<g transform="rotate(-35 52 40)"><rect x="31" y="33" width="51" height="11" rx="5.5" fill="url(#bat)" stroke="#ffe1ad" stroke-width="1.5"/><rect x="23" y="35.5" width="14" height="6" rx="3" fill="#6d2b13"/></g>
<circle cx="28" cy="67" r="15" fill="url(#ball)" stroke="#f2f5f8" stroke-width="2"/>
<path d="M19 59c8 3 12 11 12 19M35 57c-8 5-10 12-8 21" fill="none" stroke="#e21e3f" stroke-width="2.4" stroke-linecap="round"/>
<path d="M47 52l7 3M44 58l8 5" stroke="#ff3553" stroke-width="2.4" stroke-linecap="round" opacity=".85"/>
</svg>'''

GLOVE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">
<defs><linearGradient id="leather" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#d66c2d"/><stop offset=".48" stop-color="#8d3c1c"/><stop offset="1" stop-color="#4f2115"/></linearGradient><radialGradient id="ball"><stop stop-color="#fff"/><stop offset="1" stop-color="#dfe7ed"/></radialGradient></defs>
<path d="M27 69c-7-9-7-22-3-34 2-5 8-4 9 1l2 13 1-24c0-6 8-6 9 0l2 22 2-27c1-6 9-5 9 1l1 27 4-22c1-6 9-4 8 2l-2 26 5-15c2-5 9-3 8 3-2 13-6 27-16 37-8 8-29 7-38-10z" fill="url(#leather)" stroke="#ffc08a" stroke-width="2" stroke-linejoin="round"/>
<path d="M31 63c11-11 28-15 42-7M39 74c8-10 20-15 34-15" fill="none" stroke="#ffbf83" stroke-width="2.2" opacity=".65"/>
<circle cx="55" cy="58" r="14.5" fill="url(#ball)" stroke="#f4f7fa" stroke-width="2"/>
<path d="M46 50c8 3 12 11 12 19M62 48c-8 5-10 12-8 21" fill="none" stroke="#e21e3f" stroke-width="2.3" stroke-linecap="round"/>
</svg>'''

CONTACT = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">
<defs><linearGradient id="bat" x1="0" x2="1"><stop stop-color="#6d2b13"/><stop offset=".58" stop-color="#d88739"/><stop offset="1" stop-color="#ffd08a"/></linearGradient><radialGradient id="ball"><stop stop-color="#fff"/><stop offset="1" stop-color="#dfe7ed"/></radialGradient></defs>
<path d="M67 29l3-11M74 33l10-7M76 41l12 2M65 36l8-9M72 46l10 7" stroke="#ff3553" stroke-width="3" stroke-linecap="round"/>
<circle cx="67" cy="39" r="7" fill="#ffb01f" opacity=".85"/><circle cx="67" cy="39" r="3" fill="#fff0b8"/>
<g transform="rotate(-36 46 54)"><rect x="13" y="49" width="63" height="12" rx="6" fill="url(#bat)" stroke="#ffe1ad" stroke-width="1.5"/><rect x="7" y="52" width="14" height="6" rx="3" fill="#5a2312"/></g>
<circle cx="69" cy="36" r="14.5" fill="url(#ball)" stroke="#f4f7fa" stroke-width="2"/>
<path d="M60 28c8 3 12 11 12 19M76 26c-8 5-10 12-8 21" fill="none" stroke="#e21e3f" stroke-width="2.3" stroke-linecap="round"/>
</svg>'''


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    if MARKER in text:
        print("Projection summary emblem V3 already present")
        return

    anchor = ".active-market-line{padding:.72rem .78rem;border:1px solid #20425f;border-radius:12px;background:rgba(9,27,44,.94);text-align:center}"
    if anchor not in text:
        raise RuntimeError("Could not find Projection summary emblem CSS anchor")

    css = f'''/* {MARKER} · mockup-style emblem-only override */
.cc-card-icon.cc-emblem{{
    width:64px!important;height:64px!important;flex:0 0 64px!important;
    border:2px solid rgba(236,22,56,.86)!important;
    background-color:#071a30!important;background-repeat:no-repeat!important;background-position:center!important;background-size:60px 60px!important;
    box-shadow:inset 0 0 0 4px rgba(255,255,255,.025),0 7px 18px rgba(0,0,0,.34),0 0 12px rgba(236,22,56,.17)!important;
}}
.cc-card-icon.cc-emblem::before,.cc-card-icon.cc-emblem::after{{display:none!important;content:none!important}}
.cc-card-icon.cc-emblem.whiff{{background-image:url("{uri(WHIFF)}")!important}}
.cc-card-icon.cc-emblem.glove{{background-image:url("{uri(GLOVE)}")!important}}
.cc-card-icon.cc-emblem.contact{{background-image:url("{uri(CONTACT)}")!important}}
.reco-card .cc-card-icon.cc-emblem{{width:64px!important;height:64px!important;flex-basis:64px!important}}
@media (max-width:900px){{.cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{{width:56px!important;height:56px!important;flex-basis:56px!important;background-size:53px 53px!important}}}}
'''
    text = text.replace(anchor, css + anchor, 1)
    APP.write_text(text, encoding="utf-8")
    print("Applied mockup-style Projection Summary emblems")


if __name__ == "__main__":
    main()

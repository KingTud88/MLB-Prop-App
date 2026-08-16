from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"


def uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


NAV = {
    "projection": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><g fill="none" stroke="#f7f7fb" stroke-width="4" stroke-linecap="round"><circle cx="32" cy="32" r="14"/><circle cx="32" cy="32" r="4" fill="#ec1638" stroke="#ec1638"/><path d="M32 6v12M32 46v12M6 32h12M46 32h12"/></g></svg>',
    "distribution": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><g fill="none" stroke="#f7f7fb" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><path d="M10 54h44"/><rect x="13" y="34" width="8" height="18" rx="2"/><rect x="28" y="22" width="8" height="30" rx="2" fill="#ec1638" stroke="#ec1638"/><rect x="43" y="12" width="8" height="40" rx="2"/></g></svg>',
    "form": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M6 34h12l6-14 9 28 8-20 5 6h12" fill="none" stroke="#f7f7fb" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/><circle cx="33" cy="34" r="3" fill="#ec1638"/></svg>',
    "model": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><g fill="none" stroke="#f7f7fb" stroke-width="4" stroke-linecap="round"><rect x="17" y="17" width="30" height="30" rx="6"/><rect x="26" y="26" width="12" height="12" rx="2" fill="#ec1638" stroke="#ec1638"/><path d="M24 8v9M40 8v9M24 47v9M40 47v9M8 24h9M8 40h9M47 24h9M47 40h9"/></g></svg>',
    "bet": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M14 14h36v12a7 7 0 0 0 0 12v12H14V38a7 7 0 0 0 0-12V14Z" fill="none" stroke="#f7f7fb" stroke-width="4" stroke-linejoin="round"/><path d="M27 22v20" stroke="#ec1638" stroke-width="4" stroke-dasharray="4 5"/></svg>',
    "history": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><g fill="none" stroke="#f7f7fb" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><path d="M18 20H8v-10"/><path d="M10 20a24 24 0 1 1-2 22"/><circle cx="34" cy="34" r="16"/><path d="M34 24v11l8 5" stroke="#ec1638"/></g></svg>',
    "daily": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M36 6 16 36h15l-3 22 20-31H34l2-21Z" fill="#f7f7fb" stroke="#ec1638" stroke-width="3" stroke-linejoin="round"/></svg>',
    "top": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="m10 22 12 9 10-17 10 17 12-9-5 28H15L10 22Z" fill="none" stroke="#f7f7fb" stroke-width="4" stroke-linejoin="round"/><circle cx="32" cy="39" r="4" fill="#ec1638"/></svg>',
}

WHIFF = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><g fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M67 16 34 49" stroke="#d08a45" stroke-width="10"/><path d="M72 11 64 20" stroke="#f3bf77" stroke-width="5"/><path d="M31 52 25 58" stroke="#7a3b18" stroke-width="8"/><circle cx="25" cy="72" r="13" fill="#f7f2e8" stroke="#d4d9df" stroke-width="2"/><path d="M18 64c5 3 7 8 7 16M32 64c-5 3-7 8-7 16" stroke="#d8213f" stroke-width="2.5"/><path d="M10 38c11-10 23-13 35-11M9 50c10-6 20-7 30-5" stroke="#53a7ff" stroke-width="3" opacity=".85"/><path d="M43 59c5 2 9 6 12 10" stroke="#ec1638" stroke-width="3" stroke-dasharray="3 6"/></g></svg>'
CONTACT = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><g fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M18 76 58 38" stroke="#d08a45" stroke-width="11"/><path d="M13 81 22 72" stroke="#f3bf77" stroke-width="5"/><path d="M58 38 65 31" stroke="#7a3b18" stroke-width="8"/><circle cx="66" cy="30" r="13" fill="#f7f2e8" stroke="#d4d9df" stroke-width="2"/><path d="M59 22c5 3 7 8 7 16M73 22c-5 3-7 8-7 16" stroke="#d8213f" stroke-width="2.5"/><path d="m66 7 3 10M84 14l-8 8M91 31H80M83 48l-8-8" stroke="#ffb347" stroke-width="4"/><path d="M44 49c4 6 8 10 14 14" stroke="#ec1638" stroke-width="3" opacity=".85"/></g></svg>'
GLOVE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><g stroke-linecap="round" stroke-linejoin="round"><path d="M22 70c-7-10-4-20 4-24l-1-19c0-5 7-6 9-1l3 14-1-23c0-5 8-6 9 0l2 21 1-24c0-5 8-5 9 0l1 25 4-19c1-5 9-3 8 3l-4 25c8-2 14 6 10 13-5 9-16 19-28 20-12 1-21-3-26-11Z" fill="#8b4a28" stroke="#f2a45b" stroke-width="3"/><path d="M33 45c7 7 18 11 31 9M39 27l1 20M50 19l1 31M61 25l-2 27" fill="none" stroke="#5b2a17" stroke-width="3"/><circle cx="58" cy="60" r="13" fill="#f7f2e8" stroke="#d4d9df" stroke-width="2"/><path d="M51 52c5 3 7 8 7 16M65 52c-5 3-7 8-7 16" fill="none" stroke="#d8213f" stroke-width="2.5"/></g></svg>'


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    start = text.find("/* PROJECTION_EMBLEMS_V1")
    if start < 0:
        start = text.find("/* PROJECTION_EMBLEMS_V2")
    end = text.find(".active-market-line{", start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not locate Projection emblem CSS block")

    nav_urls = [uri(NAV[key]) for key in ("projection", "distribution", "form", "model", "bet", "history", "daily", "top")]
    nav_rules = "\n".join(
        f'[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child({i})::before{{background-image:url("{url}")!important}}'
        for i, url in enumerate(nav_urls, 1)
    )
    css = f'''/* PROJECTION_EMBLEMS_V2 · corrected placement + vector artwork only */
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label{{
    display:flex!important;align-items:center!important;flex-direction:row!important;flex-wrap:nowrap!important;
    position:relative!important;gap:.52rem!important;min-height:2.42rem!important;padding:.26rem .38rem!important;
    border-radius:9px!important;transition:background .14s ease,border-color .14s ease,box-shadow .14s ease!important;
}}
/* Remove Streamlit's native radio circle completely. The custom icon occupies that exact leading slot. */
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label input[type="radio"]{{display:none!important}}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label>div:has(input[type="radio"]){{display:none!important;width:0!important;height:0!important;margin:0!important;padding:0!important}}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label [role="radio"]{{display:none!important}}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label::before{{
    content:""!important;display:inline-block!important;width:1.72rem!important;height:1.72rem!important;flex:0 0 1.72rem!important;
    border:1px solid rgba(236,22,56,.68)!important;border-radius:7px!important;background-color:#0b2038!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:1.20rem 1.20rem!important;
    box-shadow:inset 0 0 0 2px rgba(255,255,255,.025),0 4px 10px rgba(0,0,0,.25)!important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:has(input:checked)::before{{
    border-color:#ff3553!important;background-color:#411225!important;
    box-shadow:inset 0 0 0 2px rgba(255,255,255,.04),0 0 13px rgba(236,22,56,.48)!important;
}}
{nav_rules}

/* True vector baseball emblems inside the existing 48px circular card slot. */
.cc-card-icon.cc-emblem{{position:relative!important;overflow:hidden!important;font-size:0!important}}
.cc-card-icon.cc-emblem::before{{
    content:""!important;position:absolute!important;inset:2px!important;display:block!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:42px 42px!important;
    filter:drop-shadow(0 3px 4px rgba(0,0,0,.30));pointer-events:none!important;
}}
.cc-card-icon.cc-emblem::after{{display:none!important;content:none!important}}
.cc-card-icon.cc-emblem.whiff::before{{background-image:url("{uri(WHIFF)}")!important}}
.cc-card-icon.cc-emblem.glove::before{{background-image:url("{uri(GLOVE)}")!important}}
.cc-card-icon.cc-emblem.contact::before{{background-image:url("{uri(CONTACT)}")!important}}
'''
    text = text[:start] + css + text[end:]
    APP.write_text(text, encoding="utf-8")
    print("Applied Projection emblem placement/vector fix")


if __name__ == "__main__":
    main()

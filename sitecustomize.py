"""StrikeOut King 9000 visual theme bootstrap.

Loaded automatically by Python when the repository root is on sys.path. It adds
an extra layer of CSS to the existing Streamlit UI without touching projection
logic or data calculations.
"""
from __future__ import annotations

import base64

try:
    import streamlit as st
except Exception:
    st = None

if st is not None:
    _MASCOT = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        '<defs><linearGradient id="r" x1="0" y1="0" x2="1" y2="1">'
        '<stop stop-color="#ff334d"/><stop offset="1" stop-color="#c90024"/></linearGradient>'
        '<linearGradient id="n" x1="0" y1="0" x2="1" y2="1">'
        '<stop stop-color="#172c66"/><stop offset="1" stop-color="#07163d"/></linearGradient></defs>'
        '<path d="M348 70l55-45 39 104-62 61z" fill="url(#r)" stroke="#08163d" stroke-width="18" stroke-linejoin="round"/>'
        '<path d="M82 266c-5-86 61-155 150-155h93c74 0 126 48 126 120v118c0 92-71 145-171 145H181C108 494 62 447 62 371z" fill="url(#r)" stroke="#08163d" stroke-width="18"/>'
        '<path d="M82 250c10-73 66-119 142-119h113c70 0 112 38 112 108v31H82z" fill="url(#n)" stroke="#fff" stroke-width="12"/>'
        '<path d="M101 169h93v105h-93zM238 150h102v124H238z" fill="#fff" stroke="#08163d" stroke-width="10"/>'
        '<ellipse cx="147" cy="222" rx="43" ry="31" fill="#0b1d4d" stroke="#ff334d" stroke-width="11"/>'
        '<ellipse cx="289" cy="220" rx="47" ry="34" fill="#0b1d4d" stroke="#ff334d" stroke-width="11"/>'
        '<path d="M116 332l48-72 35 47 45-62 51 64 43-55 55 78-72 20H183z" fill="#08163d"/>'
        '<path d="M118 330c26 25 59 36 101 36 44 0 79-13 108-40l26 44c-35 40-80 58-136 58-55 0-98-18-128-54z" fill="#fff" stroke="#08163d" stroke-width="10"/>'
        '<path d="M149 345l28 48M187 353l24 40M229 356l18 36M271 351l-2 39M313 340l-15 45" stroke="#08163d" stroke-width="8"/>'
        '<path d="M391 270c30 4 53 27 53 58v65c0 29-18 48-45 48h-20V270z" fill="#fff" stroke="#08163d" stroke-width="12"/>'
        '<circle cx="414" cy="333" r="23" fill="#fff" stroke="#c90024" stroke-width="8"/>'
        '<path d="M405 314c15 10 20 25 19 39M400 339c12 1 23 6 29 16" stroke="#c90024" stroke-width="5" fill="none"/>'
        '<path d="M213 112h98l-9 55h-80z" fill="#fff" stroke="#08163d" stroke-width="10"/>'
        '<text x="222" y="150" font-family="Arial Black,Impact,sans-serif" font-size="28" font-weight="900" fill="#c90024">9000</text>'
        '<path d="M154 274l-33 13M196 267l-36 19M336 272l35 18" stroke="#08163d" stroke-width="12" stroke-linecap="round"/>'
        '<circle cx="150" cy="286" r="9" fill="#fff"/><circle cx="350" cy="286" r="9" fill="#fff"/></svg>'
    )
    _MASCOT_URI = "data:image/svg+xml;base64," + base64.b64encode(_MASCOT.encode()).decode()

    _CSS = f"""
    <style id="sok-1000-mascot-theme">
    /* 1000% mascot treatment + reference-layout polish */
    .sok-hero {{position:relative !important;min-height:230px !important;grid-template-columns:230px minmax(0,1fr) 205px !important;gap:1.2rem !important;padding:.35rem 0 !important;}}
    .sok-hero [data-testid="stImage"] {{position:relative !important;z-index:2 !important;transform:scale(1.14) !important;transform-origin:center center !important;filter:drop-shadow(0 18px 22px rgba(0,0,0,.38)) !important;}}
    .sok-hero [data-testid="stImage"] img {{max-height:255px !important;object-fit:contain !important;}}
    .sok-hero:after {{content:"";position:absolute;left:18px;top:8px;bottom:8px;width:205px;background-image:url('{_MASCOT_URI}');background-repeat:no-repeat;background-position:center;background-size:205px 205px;opacity:.07;pointer-events:none;z-index:0;}}
    .sok-title {{font-size:5.55rem !important;line-height:.78 !important;letter-spacing:.025em !important;}}
    .sok-title .red {{text-shadow:3px 3px 0 #f7f8fa,6px 6px 0 #162d50,0 14px 25px rgba(0,0,0,.35) !important;}}
    .sok-ribbon {{box-shadow:0 8px 18px rgba(227,24,55,.18) !important;}}
    .sok-status {{position:relative !important;overflow:hidden !important;}}
    .sok-status:before {{content:"BUILT FOR\\A CLE\\A BASEBALL";white-space:pre;display:block;text-align:center;font-family:Impact,"Arial Narrow",sans-serif;letter-spacing:.08em;font-size:.72rem;line-height:1.12;color:#fff;border:1px solid #46617b;border-radius:10px;padding:.45rem;margin-bottom:.65rem;background:linear-gradient(145deg,#0e2a4d,#07172b);}}
    .matchup {{border-width:2px !important;box-shadow:0 14px 30px rgba(0,0,0,.24),inset 0 0 0 1px rgba(255,255,255,.025) !important;}}
    .section-frame {{box-shadow:0 16px 30px rgba(0,0,0,.22),inset 0 0 35px rgba(227,24,55,.025) !important;}}
    .proj-card {{min-height:225px !important;border-width:2px !important;transition:transform .15s ease,box-shadow .15s ease !important;}}
    .proj-card:hover {{transform:translateY(-3px) !important;box-shadow:0 20px 32px rgba(0,0,0,.3) !important;}}
    .proj-value {{font-size:3.65rem !important;}}
    .table-panel {{border-width:2px !important;}}
    .footer-sok {{border-top:2px solid #203e5b !important;position:relative;overflow:hidden;}}
    .footer-sok:before,.footer-sok:after {{content:"★ ★ ★";color:#e31837;letter-spacing:.35rem;font-size:1.1rem;position:absolute;top:1rem;}}
    .footer-sok:before {{left:8%;}} .footer-sok:after {{right:8%;}}
    @media(max-width:1000px){{.sok-hero{{grid-template-columns:120px 1fr!important}}.sok-title{{font-size:3.7rem!important}}}}
    </style>
    """

    _original_markdown = st.markdown
    _theme_injected = False

    def _sok_markdown(body=None, *args, **kwargs):
        global _theme_injected
        if not _theme_injected and isinstance(body, str):
            _original_markdown(_CSS, unsafe_allow_html=True)
            _theme_injected = True
        return _original_markdown(body, *args, **kwargs)

    st.markdown = _sok_markdown

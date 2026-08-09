"""StrikeOut King 9000 visual theme bootstrap.

This keeps the projection engine untouched and applies the CLE-themed visual
system globally. The real custom mascot lives in assets/strikeout_king_9000.png
and is used by the existing hero/sidebar image calls.
"""
from __future__ import annotations

try:
    import streamlit as st
except Exception:
    st = None

if st is not None:
    _CSS = """
    <style id="sok-cle-final-theme">
    :root{--sok-navy:#061426;--sok-navy2:#0a2038;--sok-blue:#17365f;--sok-red:#e31837;--sok-red2:#ff2948;--sok-white:#f5f7fa;--sok-muted:#aebed0;--sok-green:#38ee89}
    .stApp{background:radial-gradient(circle at 72% 8%,rgba(23,54,95,.34),transparent 32%),linear-gradient(145deg,#041020 0%,#07182c 52%,#041020 100%)!important;color:var(--sok-white)!important}
    [data-testid="stHeader"]{background:#071a35!important}
    [data-testid="stSidebar"]{background:linear-gradient(180deg,#061326,#071a31 55%,#051120)!important;border-right:1px solid #294866!important}
    [data-testid="stSidebar"] [data-testid="stImage"]{display:none!important}
    .sok-sidebar-logo{height:125px!important;display:flex!important;align-items:center!important;justify-content:center!important;margin:.15rem 0 .1rem!important;position:relative!important}
    .sok-sidebar-logo:after{content:"";width:112px;height:112px;background:url('/app/static/assets/strikeout_king_9000.png') center/contain no-repeat;filter:drop-shadow(0 10px 14px rgba(0,0,0,.4));display:block}
    .sok-sidebar-title{font-family:Impact,"Arial Narrow",sans-serif!important;font-size:1.45rem!important;line-height:1!important;letter-spacing:.02em!important;text-shadow:2px 2px 0 #172c50!important}
    .sok-sidebar-title span{color:var(--sok-red)!important}
    .sok-sidebar-sub{color:#b8c8d9!important}
    .sok-nav .active{background:linear-gradient(90deg,#ed1838,#bd0d2b)!important;box-shadow:0 5px 14px rgba(227,24,55,.2)!important}
    .sok-nav a:hover{background:#102b4c!important}
    .sok-side-card,.sok-date{border-color:#35536f!important;background:linear-gradient(145deg,#0a2039,#061528)!important}
    .sok-search-title,.sok-date .label,.sok-side-card .title{color:#ff2948!important}

    .sok-hero{position:relative!important;min-height:270px!important;grid-template-columns:245px minmax(0,1fr) 205px!important;gap:1rem!important;align-items:center!important;padding:.25rem 0!important}
    .sok-hero [data-testid="stImage"]{position:relative!important;z-index:3!important;transform:scale(1.18)!important;transform-origin:center center!important;filter:drop-shadow(0 18px 20px rgba(0,0,0,.45))!important}
    .sok-hero [data-testid="stImage"] img{max-height:285px!important;width:auto!important;object-fit:contain!important}
    .sok-title{font-family:Impact,"Arial Narrow",sans-serif!important;font-size:5.9rem!important;line-height:.78!important;letter-spacing:.015em!important;color:#f7f8fa!important;text-shadow:4px 4px 0 #172d4f,0 12px 25px rgba(0,0,0,.35)!important}
    .sok-title .red{color:var(--sok-red)!important;text-shadow:3px 3px 0 #f7f8fa,6px 6px 0 #152b4c,0 13px 24px rgba(0,0,0,.35)!important}
    .sok-ribbon{margin-top:.8rem!important;border:2px solid var(--sok-red)!important;background:#081a31!important;box-shadow:0 8px 20px rgba(227,24,55,.18)!important}
    .sok-status{border:1px solid #3a5773!important;background:linear-gradient(145deg,#0d2746,#07182c)!important;box-shadow:0 14px 26px rgba(0,0,0,.25)!important}
    .sok-status:before{content:"BUILT FOR\\A CLE BASEBALL"!important}

    .matchup{border:2px solid #35536f!important;border-radius:17px!important;background:linear-gradient(145deg,#0b2440,#06162a)!important;box-shadow:0 16px 30px rgba(0,0,0,.25)!important}
    .matchup .pitcher{font-family:Impact,"Arial Narrow",sans-serif!important;font-size:2.2rem!important}
    .matchup .teams{color:var(--sok-red2)!important}
    .cle-badge{width:82px!important;height:82px!important;border-color:#405c78!important;background:radial-gradient(circle,#19365e,#07172b)!important;color:#fff!important;text-shadow:3px 3px 0 var(--sok-red)!important}
    .live-schedule .head{color:#2fe777!important}

    .section-frame{border:2px solid var(--sok-red)!important;border-radius:17px!important;background:linear-gradient(160deg,rgba(8,28,51,.97),rgba(4,15,29,.97))!important;box-shadow:0 18px 32px rgba(0,0,0,.24)!important}
    .section-ribbon{background:linear-gradient(180deg,#ed193a,#c60c2a)!important;border-color:#ff4d67!important;box-shadow:0 8px 16px rgba(227,24,55,.2)!important}
    .proj-card{min-height:225px!important;border:2px solid #405970!important;border-radius:16px!important;background:radial-gradient(circle at 15% 12%,rgba(255,255,255,.08),transparent 25%),linear-gradient(145deg,#102d4b,#07182d)!important;box-shadow:0 15px 28px rgba(0,0,0,.24)!important}
    .proj-card:hover{transform:translateY(-3px)!important;box-shadow:0 20px 34px rgba(0,0,0,.32)!important}
    .proj-value{font-family:Impact,"Arial Narrow",sans-serif!important;font-size:3.7rem!important}
    .proj-pill{background:#083a2a!important;border-color:#0d8150!important;color:#4bf092!important}
    .table-panel{border:2px solid #35536f!important;border-radius:16px!important;background:linear-gradient(145deg,#0a203b,#06162a)!important}
    .table-title{background:linear-gradient(180deg,#ed193a,#c60c2a)!important}
    .sok-table th{background:#0b1d34!important}
    .sok-table th,.sok-table td{border-bottom-color:#223d58!important}
    .footer-sok{border-top:2px solid #294866!important;background:linear-gradient(180deg,rgba(4,16,31,.35),rgba(4,16,31,.85))!important}
    .footer-sok:before,.footer-sok:after{color:var(--sok-red)!important}
    @media(max-width:1000px){.sok-hero{grid-template-columns:135px 1fr!important}.sok-title{font-size:3.8rem!important}.sok-status{display:none!important}}
    </style>
    """
    _original_markdown=st.markdown
    _theme_injected=False
    def _sok_markdown(body=None,*args,**kwargs):
        global _theme_injected
        if not _theme_injected and isinstance(body,str):
            _original_markdown(_CSS,unsafe_allow_html=True)
            _theme_injected=True
        return _original_markdown(body,*args,**kwargs)
    st.markdown=_sok_markdown

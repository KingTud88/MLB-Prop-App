from __future__ import annotations

import requests
import streamlit as st
from pathlib import Path

LEGACY = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/d87e181aed527cebd1b902e7cc224aa96b06fbcc/streamlit_app.py"
MASCOT_URL = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/strikeout_king_9000.svg"

_original_markdown_fn = st.markdown
_original_image_fn = st.image

CLE_OVERRIDE = r'''
<style>
[data-testid="stSidebar"]{width:205px!important;min-width:205px!important}
[data-testid="stSidebar"]>div:first-child{width:205px!important}
[data-testid="stSidebarNav"]{display:none!important}
.block-container{max-width:1540px!important;padding:.75rem 1rem 2rem!important}
.sok-sidebar-logo{height:145px!important;margin:-.2rem 0 .2rem!important;display:flex!important;justify-content:center!important;align-items:center!important}
.sok-sidebar-logo .sok-mascot-image{height:140px!important;width:140px!important;max-height:140px!important;object-fit:contain!important;display:block!important;margin:0 auto!important}
.sok-hero{position:relative!important;display:grid!important;grid-template-columns:270px minmax(0,1fr) 220px!important;gap:1.05rem!important;min-height:300px!important;padding:.25rem .2rem!important;align-items:center!important}
.sok-hero:before{content:"";position:absolute;inset:-.2rem 0;border:1px solid #294866;border-radius:20px;background:radial-gradient(circle at 15% 48%,rgba(227,24,55,.18),transparent 25%),linear-gradient(145deg,rgba(9,29,51,.72),rgba(4,15,29,.2));z-index:-1}
.sok-hero .sok-mascot-image{display:block!important;max-height:295px!important;width:255px!important;height:295px!important;object-fit:contain!important;margin:0 auto!important;filter:drop-shadow(0 18px 22px rgba(0,0,0,.5))!important}
.sok-title{font-family:Impact,Haettenschweiler,"Arial Narrow Bold","Arial Black",sans-serif!important;font-weight:900!important;font-size:clamp(5rem,6.8vw,7.6rem)!important;line-height:.76!important;letter-spacing:.012em!important;color:#f7f8fa!important;text-shadow:5px 5px 0 #172d4f,0 15px 28px rgba(0,0,0,.45)!important;white-space:nowrap!important}
.sok-title .red{color:#e31837!important;text-shadow:3px 3px 0 #fff,6px 6px 0 #152b4c,0 15px 28px rgba(0,0,0,.45)!important}
.sok-ribbon{margin-top:1.15rem!important;padding:.45rem 1.45rem!important;border:2px solid #e31837!important;background:#081a31!important;box-shadow:0 8px 18px rgba(227,24,55,.2)!important;font-size:.86rem!important;letter-spacing:.11em!important}
.section-frame{margin-top:1.2rem!important;border:2px solid #e31837!important;border-radius:17px!important;box-shadow:0 18px 34px rgba(0,0,0,.25)!important;padding:1.05rem!important}
.section-ribbon,.table-title{background:linear-gradient(180deg,#ed193a,#c60c2a)!important;border-color:#ff4d67!important}
.proj-card{min-height:220px!important;border:2px solid #405970!important;border-radius:16px!important;background:linear-gradient(145deg,#102d4b,#07182d)!important;box-shadow:0 15px 28px rgba(0,0,0,.25)!important}
.proj-value{font-family:Impact,Haettenschweiler,"Arial Narrow Bold",sans-serif!important;font-size:3.8rem!important}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]{border-radius:8px!important;padding:.42rem .55rem!important;margin:.08rem 0!important;color:#dce6f0!important;font-weight:800!important;text-decoration:none!important}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover{background:#102b4c!important;color:#fff!important}
</style>
'''

def patched_markdown(body=None,*args,**kwargs):
    if isinstance(body,str) and '<style>' in body and '--navy:' in body:
        return _original_markdown_fn(body + CLE_OVERRIDE,*args,**kwargs)
    return _original_markdown_fn(body,*args,**kwargs)

def patched_image(image,*args,**kwargs):
    image_text = str(image) if isinstance(image,(str,Path)) else ""
    if "strikeout_king_9000" in image_text or image_text.lower().endswith(".svg"):
        width = kwargs.get("width")
        style = f"width:{int(width)}px;" if isinstance(width,(int,float)) else ""
        html = (
            f'<div class="sok-mascot-wrap" style="{style}">'
            f'<img class="sok-mascot-image" src="{MASCOT_URL}" alt="StrikeOut King 9000 mascot" />'
            f'</div>'
        )
        return _original_markdown_fn(html, unsafe_allow_html=True)
    return _original_image_fn(image,*args,**kwargs)

st.markdown = patched_markdown
st.image = patched_image

response = requests.get(LEGACY, timeout=20)
response.raise_for_status()
source = response.text
source = source.replace('initial_sidebar_state="expanded"', 'initial_sidebar_state="collapsed"')

old_nav_stmt = '''st.markdown('<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="/3_Odds_API">◎ &nbsp; Odds API</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>',unsafe_allow_html=True)'''
nav_code = '''with st.sidebar:
    st.page_link("streamlit_app.py", label="⌂  Projection", use_container_width=True)
    st.page_link("pages/2_Bet_Tracker.py", label="♧  Bet Tracker", use_container_width=True)
    st.page_link("pages/3_Odds_API.py", label="◎  Odds API", use_container_width=True)
    st.page_link("pages/4_Projection_History.py", label="▣  Projection History", use_container_width=True)
    st.page_link("pages/5_Daily_Projection_Run.py", label="▤  Daily Projection Run", use_container_width=True)'''
if old_nav_stmt not in source:
    raise RuntimeError("Legacy sidebar navigation block was not found; refusing to deploy a partial patch.")
source = source.replace(old_nav_stmt, nav_code, 1)

code = compile(source, LEGACY, "exec")
exec(code, globals(), globals())
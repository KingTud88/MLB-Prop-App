from __future__ import annotations

import requests
import streamlit as st

LEGACY = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/d87e181aed527cebd1b902e7cc224aa96b06fbcc/streamlit_app.py"

_original_markdown_fn = st.markdown

CLE_OVERRIDE = r'''
<style>
[data-testid="stSidebar"]{width:205px!important;min-width:205px!important}
.block-container{max-width:1540px!important;padding:1rem 1.1rem 2rem!important}
.sok-sidebar-logo{height:135px!important;margin:0!important}
.sok-sidebar-logo img{max-height:135px!important;object-fit:contain!important}
.sok-sidebar-title{font-family:Impact,Haettenschweiler,"Arial Narrow Bold","Arial Black",sans-serif!important;font-size:1.55rem!important;letter-spacing:.01em!important;text-shadow:2px 2px 0 #172d4f!important}
.sok-hero{position:relative!important;grid-template-columns:255px minmax(0,1fr) 210px!important;gap:1.15rem!important;min-height:275px!important;padding:.35rem 0!important;align-items:center!important}
.sok-hero:before{content:"";position:absolute;inset:0;border:1px solid #294866;border-radius:18px;background:radial-gradient(circle at 20% 45%,rgba(227,24,55,.13),transparent 27%),linear-gradient(135deg,rgba(9,29,51,.8),rgba(4,15,29,.25));z-index:-1}
.sok-hero [data-testid="stImage"]{transform:scale(1.38)!important;transform-origin:center!important;filter:drop-shadow(0 16px 18px rgba(0,0,0,.48))!important;z-index:4!important}
.sok-hero [data-testid="stImage"] img{max-height:285px!important;width:auto!important;object-fit:contain!important}
.sok-title{font-family:Impact,Haettenschweiler,"Arial Narrow Bold","Arial Black",sans-serif!important;font-weight:900!important;font-size:clamp(4.8rem,6.2vw,7rem)!important;line-height:.76!important;letter-spacing:.012em!important;color:#f7f8fa!important;text-shadow:5px 5px 0 #172d4f,0 15px 28px rgba(0,0,0,.4)!important}
.sok-title .red{color:#e31837!important;text-shadow:3px 3px 0 #fff,6px 6px 0 #152b4c,0 15px 28px rgba(0,0,0,.4)!important}
.sok-ribbon{margin-top:1rem!important;padding:.45rem 1.4rem!important;border:2px solid #e31837!important;background:#081a31!important;box-shadow:0 8px 18px rgba(227,24,55,.2)!important}
.sok-status{border:1px solid #3b5874!important;border-radius:16px!important;background:linear-gradient(145deg,#0d2746,#07182c)!important;box-shadow:0 14px 28px rgba(0,0,0,.25)!important}
.matchup{grid-template-columns:1.55fr .8fr 1fr!important;min-height:122px!important;border:2px solid #35536f!important;border-radius:17px!important;background:linear-gradient(145deg,#0b2440,#06162a)!important;box-shadow:0 16px 30px rgba(0,0,0,.24)!important}
.matchup .pitcher{font-family:Impact,Haettenschweiler,"Arial Narrow Bold",sans-serif!important;font-size:2.25rem!important;letter-spacing:.02em!important}
.cle-badge{width:86px!important;height:86px!important}
.section-frame{margin-top:1.2rem!important;border:2px solid #e31837!important;border-radius:17px!important;box-shadow:0 18px 34px rgba(0,0,0,.25)!important}
.section-ribbon{background:linear-gradient(180deg,#ed193a,#c60c2a)!important;border-color:#ff4d67!important;box-shadow:0 8px 16px rgba(227,24,55,.2)!important}
.proj-card{min-height:220px!important;border:2px solid #405970!important;border-radius:16px!important;background:radial-gradient(circle at 15% 12%,rgba(255,255,255,.08),transparent 25%),linear-gradient(145deg,#102d4b,#07182d)!important;box-shadow:0 15px 28px rgba(0,0,0,.25)!important}
.proj-card:hover{transform:translateY(-3px)!important}
.proj-value{font-family:Impact,Haettenschweiler,"Arial Narrow Bold",sans-serif!important;font-size:3.7rem!important}
.table-panel{border:2px solid #35536f!important;border-radius:16px!important;box-shadow:0 14px 25px rgba(0,0,0,.2)!important}
.table-title{background:linear-gradient(180deg,#ed193a,#c60c2a)!important}
.footer-sok{border-top:2px solid #294866!important}
@media(max-width:1000px){.sok-hero{grid-template-columns:145px 1fr!important;min-height:220px!important}.sok-hero [data-testid="stImage"]{transform:scale(1.05)!important}.sok-title{font-size:4rem!important}.sok-status{display:none!important}}
</style>
'''

def patched_markdown(body=None,*args,**kwargs):
    if isinstance(body,str) and '<style>' in body and '--navy:' in body:
        return _original_markdown_fn(body + CLE_OVERRIDE,*args,**kwargs)
    return _original_markdown_fn(body,*args,**kwargs)

st.markdown = patched_markdown

response = requests.get(LEGACY, timeout=20)
response.raise_for_status()
code = compile(response.text, LEGACY, "exec")
exec(code, globals(), globals())

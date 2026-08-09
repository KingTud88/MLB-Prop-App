from __future__ import annotations

import requests
import streamlit as st

LEGACY = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/d87e181aed527cebd1b902e7cc224aa96b06fbcc/streamlit_app.py"

_original_markdown_fn = st.markdown

CLE_OVERRIDE = r'''
<style>
/* Final CLE presentation pass */
[data-testid="stSidebar"]{width:205px!important;min-width:205px!important}
.block-container{max-width:1540px!important;padding:.75rem 1rem 2rem!important}
.sok-sidebar-logo{height:145px!important;margin:-.2rem 0 .2rem!important;display:flex!important;justify-content:center!important;align-items:center!important}
.sok-sidebar-logo img{height:140px!important;width:140px!important;max-height:140px!important;object-fit:contain!important}
.sok-sidebar-title{font-family:Impact,Haettenschweiler,"Arial Narrow Bold","Arial Black",sans-serif!important;font-size:1.55rem!important;letter-spacing:.01em!important;text-shadow:2px 2px 0 #172d4f!important}

.sok-hero{position:relative!important;display:grid!important;grid-template-columns:270px minmax(0,1fr) 220px!important;gap:1.05rem!important;min-height:300px!important;padding:.25rem .2rem!important;align-items:center!important}
.sok-hero:before{content:"";position:absolute;inset:-.2rem 0;border:1px solid #294866;border-radius:20px;background:radial-gradient(circle at 15% 48%,rgba(227,24,55,.18),transparent 25%),radial-gradient(circle at 72% 30%,rgba(30,74,130,.18),transparent 30%),linear-gradient(145deg,rgba(9,29,51,.72),rgba(4,15,29,.2));box-shadow:inset 0 0 50px rgba(0,0,0,.16);z-index:-1}
.sok-hero [data-testid="stImage"]{transform:none!important;filter:drop-shadow(0 18px 22px rgba(0,0,0,.5))!important;z-index:4!important}
.sok-hero [data-testid="stImage"] img{display:block!important;max-height:295px!important;width:255px!important;height:295px!important;object-fit:contain!important;margin:0 auto!important}
.sok-title{font-family:Impact,Haettenschweiler,"Arial Narrow Bold","Arial Black",sans-serif!important;font-weight:900!important;font-size:clamp(5rem,6.8vw,7.6rem)!important;line-height:.76!important;letter-spacing:.012em!important;color:#f7f8fa!important;text-shadow:5px 5px 0 #172d4f,0 15px 28px rgba(0,0,0,.45)!important;white-space:nowrap!important}
.sok-title .red{color:#e31837!important;text-shadow:3px 3px 0 #fff,6px 6px 0 #152b4c,0 15px 28px rgba(0,0,0,.45)!important}
.sok-ribbon{margin-top:1.15rem!important;padding:.45rem 1.45rem!important;border:2px solid #e31837!important;background:#081a31!important;box-shadow:0 8px 18px rgba(227,24,55,.2)!important;font-size:.86rem!important;letter-spacing:.11em!important}
.sok-status{border:1px solid #3b5874!important;border-radius:16px!important;background:linear-gradient(145deg,#0d2746,#07182c)!important;box-shadow:0 14px 28px rgba(0,0,0,.28)!important;padding:1rem!important}

.matchup{grid-template-columns:1.55fr .8fr 1fr!important;min-height:122px!important;border:2px solid #35536f!important;border-radius:17px!important;background:linear-gradient(145deg,#0b2440,#06162a)!important;box-shadow:0 16px 30px rgba(0,0,0,.24)!important}
.matchup .pitcher{font-family:Impact,Haettenschweiler,"Arial Narrow Bold",sans-serif!important;font-size:2.35rem!important;letter-spacing:.02em!important}
.cle-badge{width:86px!important;height:86px!important}

.section-frame{margin-top:1.2rem!important;border:2px solid #e31837!important;border-radius:17px!important;box-shadow:0 18px 34px rgba(0,0,0,.25)!important;padding:1.05rem!important}
.section-ribbon{background:linear-gradient(180deg,#ed193a,#c60c2a)!important;border-color:#ff4d67!important;box-shadow:0 8px 16px rgba(227,24,55,.2)!important;font-size:1.05rem!important}
.proj-card{min-height:220px!important;border:2px solid #405970!important;border-radius:16px!important;background:radial-gradient(circle at 15% 12%,rgba(255,255,255,.08),transparent 25%),linear-gradient(145deg,#102d4b,#07182d)!important;box-shadow:0 15px 28px rgba(0,0,0,.25)!important}
.proj-card:hover{transform:translateY(-3px)!important}
.proj-value{font-family:Impact,Haettenschweiler,"Arial Narrow Bold",sans-serif!important;font-size:3.8rem!important}
.table-panel{border:2px solid #35536f!important;border-radius:16px!important;box-shadow:0 14px 25px rgba(0,0,0,.2)!important}
.table-title{background:linear-gradient(180deg,#ed193a,#c60c2a)!important}
.footer-sok{border-top:2px solid #294866!important}

@media(max-width:1100px){.sok-hero{grid-template-columns:180px 1fr!important;min-height:250px!important}.sok-hero [data-testid="stImage"] img{width:180px!important;height:225px!important}.sok-title{font-size:4.6rem!important}.sok-status{display:none!important}}
@media(max-width:700px){.sok-hero{grid-template-columns:1fr!important;min-height:0!important;text-align:center!important}.sok-hero [data-testid="stImage"] img{width:190px!important;height:190px!important}.sok-title{font-size:3.4rem!important;white-space:normal!important}.sok-ribbon{display:inline-block!important}.matchup{grid-template-columns:1fr!important}.live-schedule{border-left:0!important;border-top:1px solid #2d4763!important;padding:1rem 0 0!important;margin-top:1rem!important}}
</style>
'''

def patched_markdown(body=None,*args,**kwargs):
    if isinstance(body,str) and '<style>' in body and '--navy:' in body:
        return _original_markdown_fn(body + CLE_OVERRIDE,*args,**kwargs)
    return _original_markdown_fn(body,*args,**kwargs)

st.markdown = patched_markdown

response = requests.get(LEGACY, timeout=20)
response.raise_for_status()
# The legacy app referenced an SVG wrapper around the mascot. Streamlit's SVG/image
# handling was producing broken-image placeholders, so force the real PNG asset.
source = response.text.replace('strikeout_king_9000.svg', 'strikeout_king_9000.png')
code = compile(source, LEGACY, "exec")
exec(code, globals(), globals())

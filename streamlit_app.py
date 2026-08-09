from __future__ import annotations

import requests
import streamlit as st

LEGACY = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/f0b28d2a9f91cc145736eb2d3e0c1a72d3275f43/streamlit_app.py"
# Use the verified PNG asset. The main .png is actually WebP data despite its extension,
# which is why browsers/Streamlit were showing the alt text instead of the mascot.
MASCOT_URL = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/strikeout_king_9000_96.png"

_original_markdown = st.markdown
_original_image = st.image

STYLE = r'''
<style>
[data-testid="stSidebar"]{width:205px!important;min-width:205px!important;background:linear-gradient(180deg,#061225 0%,#071a32 100%)!important}
[data-testid="stSidebar"]>div:first-child{width:205px!important}
[data-testid="stSidebar"] .block-container{padding:.3rem .65rem 1rem!important}
[data-testid="stSidebarNav"]{display:none!important}
[data-testid="stAppViewContainer"] .main{padding-top:0!important}
[data-testid="stAppViewContainer"] .main .block-container{max-width:1500px!important;padding:0 .8rem 2rem!important;margin-top:0!important}
.sok-sidebar-logo{display:flex!important;justify-content:center!important;align-items:center!important;height:100px!important;margin:0!important}
.sok-sidebar-logo img{width:150px!important;height:100px!important;object-fit:contain!important;display:block!important}
.sok-sidebar-title{font-size:1.3rem!important;line-height:1!important}
.sok-sidebar-sub{font-size:.72rem!important;line-height:1.25!important;margin:.25rem 0 .4rem!important}
.sok-nav{gap:.08rem!important;margin:.2rem 0 .45rem!important}
.sok-nav a,.sok-disabled-nav{padding:.36rem .45rem!important;font-size:.78rem!important;border-radius:8px!important;color:#dce6f0!important;font-weight:800!important}
.sok-disabled-nav{display:block!important}
.sok-search-title{margin-top:.45rem!important;font-size:.85rem!important}
.sok-lock{font-size:.68rem!important;line-height:1.25!important;margin-top:.25rem!important}
.sok-date{margin-top:.4rem!important;padding:.55rem!important}
.sok-side-card{margin-top:.45rem!important;padding:.6rem!important}
.sok-hero{display:grid!important;grid-template-columns:250px minmax(0,1fr) 200px!important;gap:.8rem!important;align-items:center!important;min-height:165px!important;margin:0!important;padding:0!important}
.sok-hero .sok-mascot-image{width:250px!important;height:205px!important;object-fit:contain!important;display:block!important;filter:drop-shadow(0 12px 18px rgba(0,0,0,.35))!important;image-rendering:auto!important}
.sok-title{font-size:clamp(4.6rem,6vw,6.6rem)!important;line-height:.78!important;white-space:nowrap!important}
.sok-ribbon{margin-top:.45rem!important;font-size:.75rem!important;padding:.3rem 1rem!important}
.sok-status{padding:.8rem!important}
.sok-status:before{content:"BUILT FOR";display:block;text-align:center;font-family:Impact,"Arial Narrow",sans-serif;font-size:.7rem;letter-spacing:.06em;color:#fff;border:2px solid #6d7f92;border-radius:12px;padding:.25rem;margin-bottom:.35rem;background:linear-gradient(145deg,#142b48,#07172b)}
.sok-status:after{content:"CLE";display:block;text-align:center;font-family:Impact,"Arial Narrow",sans-serif;font-size:1.25rem;letter-spacing:.08em;color:#e31837;border:2px solid #6d7f92;border-radius:12px;padding:.05rem;background:linear-gradient(145deg,#142b48,#07172b);margin-top:-.95rem}
.matchup{margin-top:.1rem!important}
.matchup .pitcher-block{display:flex!important;align-items:center!important;gap:.85rem!important}
.matchup .team-logo{width:82px!important;height:82px!important;object-fit:contain!important;display:block!important;filter:drop-shadow(0 6px 10px rgba(0,0,0,.3))!important}
.matchup .pitcher{font-size:1.8rem!important}
.section-frame{margin-top:.8rem!important}
.proj-card{min-height:205px!important}
@media(max-width:1000px){.sok-hero{grid-template-columns:1fr!important;min-height:0!important}.sok-hero .sok-mascot-image{margin:auto!important}.sok-status:before,.sok-status:after{display:none!important}}
</style>
'''

def patched_markdown(body=None,*args,**kwargs):
    if isinstance(body,str) and '<style>' in body and '--navy:' in body:
        return _original_markdown(body + STYLE,*args,**kwargs)
    return _original_markdown(body,*args,**kwargs)

def patched_image(image,*args,**kwargs):
    text=str(image) if isinstance(image,(str,bytes)) else ''
    if 'strikeout_king_9000' in text:
        width=kwargs.get('width',250)
        html=f'<div class="sok-local-image"><img class="sok-mascot-image" src="{MASCOT_URL}" alt="StrikeOut King 9000 mascot" style="width:{int(width)}px"></div>'
        return _original_markdown(html,unsafe_allow_html=True)
    return _original_image(image,*args,**kwargs)

st.markdown=patched_markdown
st.image=patched_image

response=requests.get(LEGACY,timeout=20)
response.raise_for_status()
source=response.text

# Keep the full original search/lock behavior, but match the approved sidebar order.
old_sidebar='''    selected_date=st.date_input("Slate date",value=odds_default_date)
    st.markdown(f'<div class="sok-date"><div class="label">SLATE DATE</div><div class="value">{selected_date:%Y/%m/%d}</div><div class="updated">Updated {now:%I:%M %p ET}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="sok-search-title">PITCHER SEARCH</div>',unsafe_allow_html=True)
    pitcher_query=st.text_input("Search pitcher",placeholder="Search pitcher...",label_visibility="collapsed",key="sok_pitcher_search")
    st.markdown('<div class="sok-lock">Search and select a pitcher to lock the projection 🔒</div>',unsafe_allow_html=True)
    st.markdown('<div class="sok-side-card"><div class="title">ABOUT STRIKEOUT KING 9000</div><p>Elite two-path projections combining simulated games and mathematical modeling for maximum accuracy.</p><div class="stars">★ ★ ★ ★ ★</div></div>',unsafe_allow_html=True)
'''
new_sidebar='''    st.markdown('<div class="sok-search-title">PITCHER SEARCH</div>',unsafe_allow_html=True)
    pitcher_query=st.text_input("Search pitcher",placeholder="Search pitcher...",label_visibility="collapsed",key="sok_pitcher_search")
    st.markdown('<div class="sok-lock">Search and select a pitcher to lock the projection 🔒</div>',unsafe_allow_html=True)
    selected_date=st.date_input("Slate date",value=odds_default_date)
    st.markdown(f'<div class="sok-date"><div class="label">SLATE DATE</div><div class="value">{selected_date:%Y/%m/%d}</div><div class="updated">Updated {now:%I:%M %p ET}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="sok-side-card"><div class="title">ABOUT STRIKEOUT KING 9000</div><p>Elite two-path projections combining simulated games and mathematical modeling for maximum accuracy.</p><div class="stars">★ ★ ★ ★ ★</div></div>',unsafe_allow_html=True)
'''
source=source.replace(old_sidebar,new_sidebar,1)

# Full approved navigation.
old_nav='<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="/3_Odds_API">◎ &nbsp; Odds API</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>'
new_nav='<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><div class="sok-disabled-nav">♧ &nbsp; Distribution</div><div class="sok-disabled-nav">♨ &nbsp; Form &amp; Workload</div><div class="sok-disabled-nav">▤ &nbsp; Model Card</div><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="/3_Odds_API">◎ &nbsp; Odds API</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>'
source=source.replace(old_nav,new_nav,1)

# Always use the verified real PNG mascot asset in the approved hero/sidebar locations.
old_side_logo='''    if logo_path.exists():st.markdown('<div class="sok-sidebar-logo">',unsafe_allow_html=True);st.image(str(logo_path),width=130);st.markdown('</div>',unsafe_allow_html=True)'''
new_side_logo='''    st.markdown(f'<div class="sok-sidebar-logo"><img src="{MASCOT_URL}" alt="StrikeOut King 9000"></div>',unsafe_allow_html=True)'''
source=source.replace(old_side_logo,new_side_logo,1)
old_hero_logo='''with h1:
    if logo_path.exists():st.image(str(logo_path),width=175)'''
new_hero_logo='''with h1:
    st.markdown(f'<div class="sok-local-image"><img class="sok-mascot-image" src="{MASCOT_URL}" alt="StrikeOut King 9000 mascot"></div>',unsafe_allow_html=True)'''
source=source.replace(old_hero_logo,new_hero_logo,1)

# Put the scheduled pitcher's actual MLB team logo directly beside the name.
old_matchup='''st.markdown(f'<div class="matchup"><div><div class="pitcher">{game.pitcher_name.upper()}</div><div class="teams">{game.team} <span>vs</span> {game.opponent}</div><div class="detail">⚾ {game.venue} · {game.side} · {game.status}</div></div><div class="cle-badge">C</div><div class="live-schedule">'''
new_matchup='''team_id_by_abbr={abbr:tid for tid,abbr in TEAM_ABBR.items()}
team_logo_id=team_id_by_abbr.get(game.team,114)
team_logo_url=f"https://www.mlbstatic.com/team-logos/{team_logo_id}.svg"
st.markdown(f'<div class="matchup"><div class="pitcher-block"><img class="team-logo" src="{team_logo_url}" alt="{game.team} logo"><div><div class="pitcher">{game.pitcher_name.upper()}</div><div class="teams">{game.team} <span>vs</span> {game.opponent}</div><div class="detail">⚾ {game.venue} · {game.side} · {game.status}</div></div></div><div class="cle-badge">C</div><div class="live-schedule">'''
source=source.replace(old_matchup,new_matchup,1)

compile(source,LEGACY,'exec')
exec(compile(source,LEGACY,'exec'),globals(),globals())

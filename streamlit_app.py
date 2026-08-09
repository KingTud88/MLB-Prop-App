from __future__ import annotations

from pathlib import Path

import requests
import streamlit as st

LEGACY = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/d87e181aed527cebd1b902e7cc224aa96b06fbcc/streamlit_app.py"

_original_markdown_fn = st.markdown
_original_image_fn = st.image

STYLE_OVERRIDE = r'''
<style>
/* Approved reference layout: open 205px sidebar + compact hero. */
[data-testid="stSidebar"]{width:205px!important;min-width:205px!important;background:linear-gradient(180deg,#061225 0%,#071a32 100%)!important}
[data-testid="stSidebar"]>div:first-child{width:205px!important}
[data-testid="stSidebar"] .block-container{padding:0 .65rem 1.2rem!important}
[data-testid="stSidebarNav"]{display:none!important}
[data-testid="stAppViewContainer"] .main{padding-top:0!important}
[data-testid="stAppViewContainer"] .main .block-container{padding:0 1rem 2rem!important;margin-top:0!important;max-width:1500px!important}
.sok-hero{display:grid!important;grid-template-columns:250px minmax(0,1fr) 220px!important;gap:1rem!important;align-items:center!important;height:auto!important;min-height:190px!important;margin:0!important;padding:0!important;overflow:visible!important}
.sok-hero .sok-mascot-image{display:block!important;width:245px!important;height:210px!important;object-fit:contain!important;filter:drop-shadow(0 12px 18px rgba(0,0,0,.35))!important}
.sok-sidebar-logo{display:flex!important;justify-content:center!important;align-items:center!important;min-height:55px!important;margin:0 0 .15rem!important}
.sok-sidebar-logo .sok-mascot-image{display:block!important;width:140px!important;height:140px!important;object-fit:contain!important}
.sok-sidebar-title{font-size:1.35rem!important}
.sok-sidebar-sub{margin:.35rem 0 .55rem!important;font-size:.73rem!important}
.sok-nav{gap:.12rem!important;margin:.35rem 0 .65rem!important}
.sok-nav a,.sok-disabled-nav{padding:.48rem .5rem!important;font-size:.82rem!important}
.sok-search-title{margin-top:.65rem!important}
.sok-date{margin-top:.55rem!important}
.sok-side-card{margin-top:.6rem!important}
.sok-title{font-size:clamp(5rem,6.8vw,7.6rem)!important;line-height:.76!important;white-space:nowrap!important}
.sok-ribbon{margin-top:.55rem!important;font-size:.82rem!important;padding:.35rem 1.1rem!important}
.sok-status{position:relative!important;margin-top:0!important}
.sok-status:before{content:"BUILT FOR\A CLE";white-space:pre;display:flex;align-items:center;justify-content:center;text-align:center;position:absolute;right:0;top:-118px;width:118px;height:88px;border:2px solid #6d7f92;border-radius:15px;background:linear-gradient(145deg,#142b48,#07172b);color:#fff;font-family:Impact,"Arial Narrow",sans-serif;font-size:1.05rem;line-height:.95;letter-spacing:.06em;box-shadow:0 10px 20px rgba(0,0,0,.25)}
.matchup{margin-top:0!important}
.matchup .team-logo{width:86px!important;height:86px!important;object-fit:contain!important;display:block!important;margin:0 auto!important;filter:drop-shadow(0 6px 10px rgba(0,0,0,.3))!important}
.matchup .pitcher-block{display:flex!important;align-items:center!important;gap:1rem!important}
.section-frame{border-width:2px!important;border-color:#e31837!important;border-radius:17px!important}
.section-ribbon{font-size:1rem!important}
.proj-card{min-height:220px!important;border-width:1px!important;border-radius:16px!important}
.proj-value{font-size:3.65rem!important}
.table-panel{border-radius:15px!important}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]{border-radius:8px!important;padding:.42rem .5rem!important;margin:.05rem 0!important;color:#dce6f0!important;font-weight:800!important}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover{background:#102b4c!important;color:#fff!important}
@media(max-width:1000px){.sok-hero{grid-template-columns:1fr!important;min-height:0!important}.sok-status:before{display:none!important}.sok-hero .sok-mascot-image{width:220px!important;height:180px!important;margin:auto!important}}
</style>
'''

def patched_markdown(body=None, *args, **kwargs):
    if isinstance(body, str) and '<style>' in body and '--navy:' in body:
        return _original_markdown_fn(body + STYLE_OVERRIDE, *args, **kwargs)
    return _original_markdown_fn(body, *args, **kwargs)

def patched_image(image, *args, **kwargs):
    return _original_image_fn(image, *args, **kwargs)

st.markdown = patched_markdown
st.image = patched_image

response = requests.get(LEGACY, timeout=20)
response.raise_for_status()
source = response.text
source = source.replace('initial_sidebar_state="collapsed"', 'initial_sidebar_state="expanded"', 1)
source = source.replace('initial_sidebar_state="expanded"', 'initial_sidebar_state="expanded"', 1)

# Use the full mascot PNG in the hero while retaining the compact sidebar branding.
source = source.replace(
    'logo_path=ASSET_DIR/"strikeout_king_9000.svg"',
    'logo_path=ASSET_DIR/"strikeout_king_9000.svg"\nhero_logo_path=ASSET_DIR/"strikeout_king_9000.png"\nteam_id_by_abbr={abbr:tid for tid,abbr in TEAM_ABBR.items()}',
    1,
)
source = source.replace(
    'if logo_path.exists():st.image(str(logo_path),width=175)',
    'if hero_logo_path.exists():st.image(str(hero_logo_path),width=245)',
    1,
)

nav_lines = [
    'st.page_link("streamlit_app.py", label="⌂  Projection", use_container_width=True)',
    'st.markdown("<div class=\\"sok-disabled-nav\\">♧  Distribution</div>", unsafe_allow_html=True)',
    'st.markdown("<div class=\\"sok-disabled-nav\\">♨  Form &amp; Workload</div>", unsafe_allow_html=True)',
    'st.markdown("<div class=\\"sok-disabled-nav\\">▤  Model Card</div>", unsafe_allow_html=True)',
    'st.page_link("pages/2_Bet_Tracker.py", label="♧  Bet Tracker", use_container_width=True)',
    'st.page_link("pages/3_Odds_API.py", label="◎  Odds API", use_container_width=True)',
    'st.page_link("pages/4_Projection_History.py", label="▣  Projection History", use_container_width=True)',
    'st.page_link("pages/5_Daily_Projection_Run.py", label="▤  Daily Projection Run", use_container_width=True)',
]
lines = source.splitlines()
nav_index = next((i for i, line in enumerate(lines) if 'class="sok-nav"' in line and 'st.markdown' in line), None)
if nav_index is not None:
    indent = lines[nav_index][:len(lines[nav_index]) - len(lines[nav_index].lstrip())]
    lines[nav_index:nav_index + 1] = [indent + line for line in nav_lines]
    source = "\n".join(lines) + "\n"

# Replace the placeholder CLE circle with the actual scheduled pitcher's MLB team logo.
old_matchup = 'st.markdown(f\'<div class="matchup"><div><div class="pitcher">{game.pitcher_name.upper()}</div><div class="teams">{game.team} <span>vs</span> {game.opponent}</div><div class="detail">⚾ {game.venue} · {game.side} · {game.status}</div></div><div class="cle-badge">C</div><div class="live-schedule"><div class="head">LIVE SCHEDULE</div><div class="row">▣ &nbsp; Today &nbsp; <span>{game_clock}</span></div><div class="row">Scheduled &nbsp; • &nbsp; {game.side}</div></div></div>\',unsafe_allow_html=True)'
new_matchup = 'team_logo_id=team_id_by_abbr.get(game.team,114)\nteam_logo_url=f"https://www.mlbstatic.com/team-logos/{team_logo_id}.svg"\nst.markdown(f\'<div class="matchup"><div class="pitcher-block"><img class="team-logo" src="{team_logo_url}" alt="{game.team} logo"><div><div class="pitcher">{game.pitcher_name.upper()}</div><div class="teams">{game.team} <span>vs</span> {game.opponent}</div><div class="detail">⚾ {game.venue} · {game.side} · {game.status}</div></div></div><div></div><div class="live-schedule"><div class="head">LIVE SCHEDULE</div><div class="row">▣ &nbsp; Today &nbsp; <span>{game_clock}</span></div><div class="row">Scheduled &nbsp; • &nbsp; {game.side}</div></div></div>\',unsafe_allow_html=True)'
if old_matchup in source:
    source = source.replace(old_matchup, new_matchup, 1)

old_market = '''try:k_line=float(st.session_state.get("odds_selected_line",5.5))
except (TypeError,ValueError):k_line=5.5
try:outs_line=float(st.session_state.get("odds_selected_outs_line",15.5))
except (TypeError,ValueError):outs_line=15.5
k_over=over_probability(projection.k_samples,k_line);outs_over=over_probability(projection.outs_samples,outs_line);k_lo,k_hi=interval(projection.k_samples);o_lo,o_hi=interval(projection.outs_samples)
'''
new_market = '''try:k_line=float(st.session_state.get("odds_selected_line",5.5))
except (TypeError,ValueError):k_line=5.5
try:outs_line=float(st.session_state.get("odds_selected_outs_line",15.5))
except (TypeError,ValueError):outs_line=15.5
k_side=str(st.session_state.get("odds_selected_side","Over")).title()
k_over=over_probability(projection.k_samples,k_line);k_market_prob=k_over if k_side=="Over" else 1-k_over
k_market_label=str(st.session_state.get("odds_selected_display_line",f"OVER {k_line:g}"))
outs_over=over_probability(projection.outs_samples,outs_line);k_lo,k_hi=interval(projection.k_samples);o_lo,o_hi=interval(projection.outs_samples)
'''
if old_market in source:
    source = source.replace(old_market, new_market, 1)

old_card = '("5.5+","OVER 5.5 STRIKEOUTS",f"{k_over:.1%}",f"↑ FAIR {fair_american(k_over)}")'
new_card = '("K+",k_market_label,f"{k_market_prob:.1%}",f"↑ FAIR {fair_american(k_market_prob)}")'
if old_card in source:
    source = source.replace(old_card, new_card, 1)

projection_end = 'st.caption("Probabilities are model estimates, not guarantees.")\n'
if projection_end in source and 'render_merged_odds(game, selected_date, projection)' not in source:
    source = source.replace(
        projection_end,
        projection_end + 'from training.merged_odds import render_merged_odds\nrender_merged_odds(game, selected_date, projection)\n',
        1,
    )

compile(source, LEGACY, "exec")
exec(compile(source, LEGACY, "exec"), globals(), globals())

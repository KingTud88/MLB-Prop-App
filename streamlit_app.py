from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
import requests
import streamlit as st

LEGACY = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/f0b28d2a9f91cc145736eb2d3e0c1a72d3275f43/streamlit_app.py"
BASE_DIR = Path(__file__).resolve().parent
MASCOT_PATH = BASE_DIR / "assets" / "strikeout_king_9000_96.png"
if not MASCOT_PATH.exists():
    MASCOT_PATH = BASE_DIR / "assets" / "strikeout_king_9000.png"

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
.sok-sidebar-logo{display:flex!important;justify-content:center!important;align-items:center!important;height:100px!important;margin:0!important}.sok-sidebar-logo img{width:150px!important;height:100px!important;object-fit:contain!important;display:block!important}.sok-sidebar-title{font-size:1.3rem!important;line-height:1!important}.sok-sidebar-sub{font-size:.72rem!important;line-height:1.25!important;margin:.25rem 0 .4rem!important}
.sok-nav{gap:.08rem!important;margin:.2rem 0 .45rem!important}.sok-nav a,.sok-disabled-nav{padding:.36rem .45rem!important;font-size:.78rem!important;border-radius:8px!important;color:#dce6f0!important;font-weight:800!important}.sok-disabled-nav{display:block!important}.sok-search-title{margin-top:.45rem!important;font-size:.85rem!important}.sok-lock{font-size:.68rem!important;line-height:1.25!important;margin-top:.25rem!important}.sok-date{margin-top:.4rem!important;padding:.55rem!important}.sok-side-card{margin-top:.45rem!important;padding:.6rem!important}
.sok-hero{display:grid!important;grid-template-columns:250px minmax(0,1fr) 200px!important;gap:.8rem!important;align-items:center!important;min-height:165px!important}.sok-hero .sok-mascot-image{width:250px!important;height:205px!important;object-fit:contain!important;display:block!important;filter:drop-shadow(0 12px 18px rgba(0,0,0,.35))!important}.sok-title{font-size:clamp(4.6rem,6vw,6.6rem)!important;line-height:.78!important;white-space:nowrap!important}.sok-ribbon{margin-top:.45rem!important;font-size:.75rem!important;padding:.3rem 1rem!important}.sok-status{padding:.8rem!important}
.sok-status:before{content:"BUILT FOR";display:block;text-align:center;font-family:Impact,"Arial Narrow",sans-serif;font-size:.7rem;letter-spacing:.06em;color:#fff;border:2px solid #6d7f92;border-radius:12px;padding:.25rem;margin-bottom:.35rem;background:linear-gradient(145deg,#142b48,#07172b)}.sok-status:after{content:"CLE";display:block;text-align:center;font-family:Impact,"Arial Narrow",sans-serif;font-size:1.25rem;letter-spacing:.08em;color:#e31837;border:2px solid #6d7f92;border-radius:12px;padding:.05rem;background:linear-gradient(145deg,#142b48,#07172b);margin-top:-.95rem}.matchup{margin-top:.1rem!important}.matchup .pitcher-block{display:flex!important;align-items:center!important;gap:.85rem!important}.matchup .team-logo{width:82px!important;height:82px!important;object-fit:contain!important;display:block!important;filter:drop-shadow(0 6px 10px rgba(0,0,0,.3))!important}.matchup .pitcher{font-size:1.8rem!important}.section-frame{margin-top:.8rem!important}.proj-card{min-height:205px!important}
.sok-two-path{margin-top:1rem!important;border:1px solid #35516d!important;border-radius:15px!important;background:linear-gradient(145deg,#0a203b,#06162a)!important;overflow:hidden!important;box-shadow:0 12px 22px rgba(0,0,0,.16)!important}.sok-two-path-title{display:block!important;text-align:center!important;padding:.5rem 1.5rem!important;background:linear-gradient(180deg,#ed193a,#c60c2a)!important;color:#fff!important;font-family:Impact,"Arial Narrow",sans-serif!important;letter-spacing:.07em!important;font-size:1rem!important}.sok-two-path-grid{display:grid!important;grid-template-columns:1fr 1fr 1.2fr!important}.sok-two-path-cell{padding:.8rem 1rem!important;border-right:1px solid #223d58!important}.sok-two-path-cell:last-child{border-right:0!important}.sok-two-path-kicker{color:#aebed0!important;font-size:.68rem!important;letter-spacing:.06em!important;font-weight:900!important}.sok-two-path-value{color:#fff!important;font-family:Impact,"Arial Narrow",sans-serif!important;font-size:2rem!important;margin-top:.2rem!important}.sok-two-path-detail{color:#aebed0!important;font-size:.72rem!important;line-height:1.45!important;margin-top:.25rem!important}.sok-two-path-ensemble{color:#42ef90!important}
.sok-odds-panel{margin-top:1rem!important;border:1px solid #35516d!important;border-radius:15px!important;background:linear-gradient(145deg,#0a203b,#06162a)!important;overflow:hidden!important;box-shadow:0 12px 22px rgba(0,0,0,.16)!important}.sok-odds-title{display:block!important;text-align:center!important;padding:.5rem 1.5rem!important;background:linear-gradient(180deg,#ed193a,#c60c2a)!important;color:#fff!important;font-family:Impact,"Arial Narrow",sans-serif!important;letter-spacing:.07em!important;font-size:1rem!important}.sok-odds-sub{padding:.55rem .8rem .25rem!important;color:#aebed0!important;font-size:.72rem!important;text-align:center!important}.sok-odds-table{width:100%!important;border-collapse:collapse!important;color:#e6edf4!important;font-size:.78rem!important}.sok-odds-table th{color:#d9e2eb!important;background:#0b1d34!important;font-family:Impact,"Arial Narrow",sans-serif!important;letter-spacing:.05em!important;font-weight:500!important}.sok-odds-table th,.sok-odds-table td{padding:.55rem .6rem!important;border-bottom:1px solid #223d58!important;text-align:left!important}.sok-odds-table tr:last-child td{border-bottom:0!important}.sok-odds-live{color:#42ef90!important;font-weight:900!important}.sok-odds-muted{color:#9eb0c4!important}
@media(max-width:1000px){.sok-hero{grid-template-columns:1fr!important;min-height:0!important}.sok-hero .sok-mascot-image{margin:auto!important}.sok-status:before,.sok-status:after{display:none!important}.sok-two-path-grid{grid-template-columns:1fr!important}.sok-two-path-cell{border-right:0!important;border-bottom:1px solid #223d58!important}}
</style>
'''

def patched_markdown(body=None,*args,**kwargs):
    if isinstance(body,str) and '<style>' in body and '--navy:' in body:return _original_markdown(body+STYLE,*args,**kwargs)
    return _original_markdown(body,*args,**kwargs)

def patched_image(image,*args,**kwargs):
    text=str(image) if isinstance(image,(str,bytes,Path)) else ''
    if 'strikeout_king_9000' in text:return _original_image(str(MASCOT_PATH),width=kwargs.get('width',250))
    return _original_image(image,*args,**kwargs)

st.markdown=patched_markdown
st.image=patched_image
response=requests.get(LEGACY,timeout=20);response.raise_for_status();source=response.text

source=source.replace('''    selected_date=st.date_input("Slate date",value=odds_default_date)
    st.markdown(f'<div class="sok-date"><div class="label">SLATE DATE</div><div class="value">{selected_date:%Y/%m/%d}</div><div class="updated">Updated {now:%I:%M %p ET}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="sok-search-title">PITCHER SEARCH</div>',unsafe_allow_html=True)
    pitcher_query=st.text_input("Search pitcher",placeholder="Search pitcher...",label_visibility="collapsed",key="sok_pitcher_search")
    st.markdown('<div class="sok-lock">Search and select a pitcher to lock the projection 🔒</div>',unsafe_allow_html=True)''','''    st.markdown('<div class="sok-search-title">PITCHER SEARCH</div>',unsafe_allow_html=True)
    pitcher_query=st.text_input("Search pitcher",placeholder="Search pitcher...",label_visibility="collapsed",key="sok_pitcher_search")
    st.markdown('<div class="sok-lock">Search and select a pitcher to lock the projection 🔒</div>',unsafe_allow_html=True)
    selected_date=st.date_input("Slate date",value=odds_default_date)
    st.markdown(f'<div class="sok-date"><div class="label">SLATE DATE</div><div class="value">{selected_date:%Y/%m/%d}</div><div class="updated">Updated {now:%I:%M %p ET}</div></div>',unsafe_allow_html=True)''',1)
source=source.replace('<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="/3_Odds_API">◎ &nbsp; Odds API</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>','<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><div class="sok-disabled-nav">♧ &nbsp; Distribution</div><div class="sok-disabled-nav">♨ &nbsp; Form &amp; Workload</div><div class="sok-disabled-nav">▤ &nbsp; Model Card</div><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>',1)
source=source.replace('''    if logo_path.exists():st.markdown('<div class="sok-sidebar-logo">',unsafe_allow_html=True);st.image(str(logo_path),width=130);st.markdown('</div>',unsafe_allow_html=True)''','''    st.markdown('<div class="sok-sidebar-logo">',unsafe_allow_html=True);st.image(str(MASCOT_PATH),width=130);st.markdown('</div>',unsafe_allow_html=True)''',1)
source=source.replace('''with h1:
    if logo_path.exists():st.image(str(logo_path),width=175)''','''with h1:
    st.image(str(MASCOT_PATH),width=250)''',1)
source=source.replace('''st.markdown(f'<div class="matchup"><div><div class="pitcher">{game.pitcher_name.upper()}</div><div class="teams">{game.team} <span>vs</span> {game.opponent}</div><div class="detail">⚾ {game.venue} · {game.side} · {game.status}</div></div><div class="cle-badge">C</div><div class="live-schedule">''','''team_id_by_abbr={abbr:tid for tid,abbr in TEAM_ABBR.items()}
team_logo_id=team_id_by_abbr.get(game.team,114)
team_logo_url=f"https://www.mlbstatic.com/team-logos/{team_logo_id}.svg"
st.markdown(f'<div class="matchup"><div class="pitcher-block"><img class="team-logo" src="{team_logo_url}" alt="{game.team} logo"><div><div class="pitcher">{game.pitcher_name.upper()}</div><div class="teams">{game.team} <span>vs</span> {game.opponent}</div><div class="detail">⚾ {game.venue} · {game.side} · {game.status}</div></div></div><div class="cle-badge">C</div><div class="live-schedule">''',1)

TWO_PATH = r'''
@dataclass(frozen=True)
class Projection:
    mean_k: float
    mean_outs: float
    k_sd: float
    outs_sd: float
    k_probs: np.ndarray
    outs_probs: np.ndarray
    k_samples: np.ndarray
    outs_samples: np.ndarray
    confidence: str
    data_quality: int
    factors: list[tuple[str,float]]
    sim_mean_k: float
    sim_mean_outs: float
    math_mean_k: float
    math_mean_outs: float
    sim_k_sd: float
    sim_outs_sd: float
    math_k_sd: float
    math_outs_sd: float

def _sok_math_path(log,game,manual):
    starts=log[log["games_started"]>0].copy().tail(35)
    if starts.empty:starts=log.tail(20).copy()
    bf=weighted_mean(starts["batters_faced"],5.0,22.0);outs=weighted_mean(starts["outs"],5.0,16.0);pitches=weighted_mean(starts["pitches"],5.0,88.0);total_bf=float(starts["batters_faced"].sum());raw_k_rate=float(starts["strikeouts"].sum()/max(total_bf,1));k_rate=shrink(raw_k_rate,total_bf,.224,120.0)
    opponent_factor=manual["opponent_k_pct"]/22.4;park_factor=PARK_K_FACTOR.get(game.venue,1.0);ump_factor=manual["umpire_k_factor"];weather_factor=manual["weather_factor"];rest_factor=manual["rest_factor"];pitch_limit_factor=float(np.clip(manual["pitch_limit"]/max(pitches,75.0),.78,1.12));projected_bf=bf*pitch_limit_factor*rest_factor;projected_outs=outs*pitch_limit_factor*rest_factor;projected_k=projected_bf*k_rate*opponent_factor*park_factor*ump_factor*weather_factor;projected_k=float(np.clip(.78*projected_k+.22*weighted_mean(starts["strikeouts"],5,5.0),.5,13.5));projected_outs=float(np.clip(projected_outs,3.0,24.0))
    k_variance=float(starts["strikeouts"].var(ddof=1)) if len(starts)>2 else projected_k*1.25;dispersion=max((k_variance-projected_k)/max(projected_k**2,.1),.08);k_probs=negbin_pmf(projected_k,dispersion,18);outs_sd=float(starts["outs"].std(ddof=1)) if len(starts)>2 else 4.0;outs_sd=float(np.clip(outs_sd,2.5,6.5));outs_probs=discrete_normal_probs(projected_outs,outs_sd,27)
    return {"mean_k":projected_k,"mean_outs":projected_outs,"k_probs":k_probs,"outs_probs":outs_probs,"k_sd":math.sqrt(k_variance),"outs_sd":outs_sd,"pitch_limit_factor":pitch_limit_factor,"opponent_factor":opponent_factor,"park_factor":park_factor,"ump_factor":ump_factor,"weather_factor":weather_factor,"rest_factor":rest_factor,"starts":starts,"total_bf":total_bf}

def _sok_simulation_path(log,game,manual,simulations,seed):
    starts=log[log["games_started"]>0].copy().tail(35)
    if starts.empty:starts=log.tail(20).copy()
    starts=starts.reset_index(drop=True);n=len(starts)
    if n==0:raise ValueError("No historical starts available for simulation.")
    ages=np.arange(n-1,-1,-1,dtype=float);weights=np.exp(-.08*ages);weights=weights/weights.sum();rng=np.random.default_rng(seed);idx=rng.choice(n,size=simulations,p=weights);bf_hist=starts["batters_faced"].to_numpy(float);outs_hist=starts["outs"].to_numpy(float);bf_base=bf_hist[idx];outs_base=outs_hist[idx];bf_sd=float(starts["batters_faced"].std(ddof=1)) if n>2 else 3.5;outs_sd=float(starts["outs"].std(ddof=1)) if n>2 else 3.0;total_bf=float(starts["batters_faced"].sum());total_k=float(starts["strikeouts"].sum());alpha=max(.224*120.0+total_k,.5);beta=max(.776*120.0+total_bf-total_k,.5);latent_k_rate=rng.beta(alpha,beta,size=simulations);opponent_factor=manual["opponent_k_pct"]/22.4;park_factor=PARK_K_FACTOR.get(game.venue,1.0);ump_factor=manual["umpire_k_factor"];weather_factor=manual["weather_factor"];rest_factor=manual["rest_factor"];mean_pitch=float(weighted_mean(starts["pitches"],5.0,88.0));pitch_limit_factor=float(np.clip(manual["pitch_limit"]/max(mean_pitch,75.0),.78,1.12));adjusted_rate=np.clip(latent_k_rate*opponent_factor*park_factor*ump_factor*weather_factor,.02,.55);sim_bf=np.clip(np.rint(bf_base+rng.normal(0.0,max(bf_sd*.35,1.0),size=simulations)),12,35).astype(int);sim_bf=np.clip(np.rint(sim_bf*pitch_limit_factor*rest_factor),8,35).astype(int);sim_k=rng.binomial(sim_bf,adjusted_rate).astype(float);sim_outs=np.clip(np.rint(outs_base+rng.normal(0.0,max(outs_sd*.35,1.0),size=simulations)),3,27).astype(float);sim_outs=np.clip(np.rint(sim_outs*pitch_limit_factor*rest_factor),3,27)
    return {"k_samples":sim_k,"outs_samples":sim_outs,"mean_k":float(np.mean(sim_k)),"mean_outs":float(np.mean(sim_outs)),"k_sd":float(np.std(sim_k,ddof=1)),"outs_sd":float(np.std(sim_outs,ddof=1))}

def _sok_hist_probs(samples,maximum):
    values=np.clip(np.rint(samples).astype(int),0,maximum);counts=np.bincount(values,minlength=maximum+1).astype(float);return counts/counts.sum()

def calculate_projection(log,game,manual,simulations)->Projection:
    simulations=max(int(simulations),1000);math_path=_sok_math_path(log,game,manual);seed=int(hashlib.sha256(f"{game.key}|{date.today()}|{APP_VERSION}|two-path-v2".encode()).hexdigest()[:8],16);sim_path=_sok_simulation_path(log,game,manual,simulations,seed);rng=np.random.default_rng(seed+1);take_sim=rng.random(simulations)<.5;math_k=rng.choice(np.arange(len(math_path["k_probs"])),size=simulations,p=math_path["k_probs"]);math_o=rng.choice(np.arange(len(math_path["outs_probs"])),size=simulations,p=math_path["outs_probs"]);k_samples=np.where(take_sim,sim_path["k_samples"],math_k);outs_samples=np.where(take_sim,sim_path["outs_samples"],math_o);k_probs=_sok_hist_probs(k_samples,18);outs_probs=_sok_hist_probs(outs_samples,27);quality=min(100,35+len(math_path["starts"])*2+(15 if math_path["total_bf"]>=250 else 0)+(10 if game.pitcher_id else 0));confidence="High" if quality>=85 else "Medium" if quality>=65 else "Low";factors=[("Opponent strikeout profile",math_path["opponent_factor"]-1),("Recent workload / pitch limit",math_path["pitch_limit_factor"]-1),("Park",math_path["park_factor"]-1),("Umpire",math_path["ump_factor"]-1),("Weather",math_path["weather_factor"]-1),("Rest",math_path["rest_factor"]-1)]
    return Projection(float(np.mean(k_samples)),float(np.mean(outs_samples)),float(np.std(k_samples,ddof=1)),float(np.std(outs_samples,ddof=1)),k_probs,outs_probs,k_samples,outs_samples,confidence,quality,factors,sim_path["mean_k"],sim_path["mean_outs"],math_path["mean_k"],math_path["mean_outs"],sim_path["k_sd"],sim_path["outs_sd"],math_path["k_sd"],math_path["outs_sd"])
'''
source=re.sub(r'@dataclass\(frozen=True\)\nclass Projection:.*?\n\ndef over_probability',TWO_PATH+'\n\ndef over_probability',source,count=1,flags=re.S)

TWO_PATH_BLOCK=r"""
st.markdown(f'''<div class="sok-two-path"><div class="sok-two-path-title">TWO-PATH PROJECTION ENGINE</div><div class="sok-two-path-grid"><div class="sok-two-path-cell"><div class="sok-two-path-kicker">PATH 1 · 25,000 SIMULATED GAMES</div><div class="sok-two-path-value">K {projection.sim_mean_k:.2f} · OUTS {projection.sim_mean_outs:.2f}</div><div class="sok-two-path-detail">Independent game draws using recency-weighted historical workloads, empirical-Bayes pitcher skill, opponent/park/context adjustments, and a game-level binomial strikeout process.</div></div><div class="sok-two-path-cell"><div class="sok-two-path-kicker">PATH 2 · MATHEMATICAL MODEL</div><div class="sok-two-path-value">K {projection.math_mean_k:.2f} · OUTS {projection.math_mean_outs:.2f}</div><div class="sok-two-path-detail">Weighted recent form, empirical-Bayes shrinkage, context factors, Negative Binomial strikeout distribution, and bounded outs distribution.</div></div><div class="sok-two-path-cell"><div class="sok-two-path-kicker">FINAL ENSEMBLE · 50/50</div><div class="sok-two-path-value sok-two-path-ensemble">K {projection.mean_k:.2f} · OUTS {projection.mean_outs:.2f}</div><div class="sok-two-path-detail">Final probabilities, ranges, fair odds, ladder and displayed projection are generated from the blended path distributions.</div></div></div></div>''',unsafe_allow_html=True)
"""
source=source.replace("\nst.markdown('</div>',unsafe_allow_html=True)\n\nleft,right=st.columns([1,1])",TWO_PATH_BLOCK+"\nst.markdown('</div>',unsafe_allow_html=True)\n\nleft,right=st.columns([1,1])",1)

ODDS_HELPER=r'''
def _sok_odds_api_key():
    key=os.environ.get("THE_ODDS_API_KEY","").strip()
    if key:return key
    try:return str(st.secrets.get("THE_ODDS_API_KEY","")).strip()
    except Exception:return ""
@st.cache_data(ttl=60,show_spinner=False)
def _sok_live_pitcher_odds(pitcher_name,team_abbr,opponent_abbr):
    key=_sok_odds_api_key()
    if not key:return {"status":"model_only","bookmakers":{},"lines":[]}
    try:
        events=requests.get("https://api.the-odds-api.com/v4/sports/baseball_mlb/events",params={"apiKey":key},timeout=12).json();event_id=None
        for event in events if isinstance(events,list) else []:
            names=f"{event.get('home_team','')} {event.get('away_team','')}".upper()
            if team_abbr.upper() in names and opponent_abbr.upper() in names:event_id=event.get("id");break
        if not event_id:return {"status":"no_event","bookmakers":{},"lines":[]}
        payload=requests.get(f"https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{event_id}/odds",params={"apiKey":key,"regions":"us","oddsFormat":"american","markets":"pitcher_strikeouts,pitcher_strikeouts_alternate"},timeout=12).json();rows=[];books={}
        for bookmaker in payload.get("bookmakers",[]) if isinstance(payload,dict) else []:
            title=bookmaker.get("title",bookmaker.get("key","Book"));books[title]=True
            for market in bookmaker.get("markets",[]):
                if market.get("key") not in {"pitcher_strikeouts","pitcher_strikeouts_alternate"}:continue
                for outcome in market.get("outcomes",[]):
                    if str(outcome.get("description","")).strip().lower()!=pitcher_name.strip().lower():continue
                    if outcome.get("point") is not None and outcome.get("price") is not None:rows.append({"book":title,"side":outcome.get("name"),"point":float(outcome["point"]),"price":int(outcome["price"])})
        return {"status":"live" if rows else "no_player_market","bookmakers":books,"lines":rows}
    except Exception:return {"status":"error","bookmakers":{},"lines":[]}
'''
source=source.replace('\nnow=datetime.now(EASTERN);query_day=now.date()',ODDS_HELPER+'\nnow=datetime.now(EASTERN);query_day=now.date()',1)
ODDS_BLOCK=r'''
try:live_odds=_sok_live_pitcher_odds(game.pitcher_name,game.team,game.opponent)
except Exception:live_odds={"status":"error","bookmakers":{},"lines":[]}
ladder_rows=[]
for milestone in range(3,11):
    model_prob=float(np.mean(projection.k_samples>=milestone));fair=fair_american(model_prob);live_matches=[r for r in live_odds.get("lines",[]) if r.get("side")=="Over" and abs(float(r.get("point",0))-(milestone-.5))<1e-9];live_best="—";live_book="—"
    if live_matches:
        best=max(live_matches,key=lambda r:int(r.get("price",-9999)));live_best=f"{int(best['price']):+d}";live_book=str(best.get("book","Book"))
    ladder_rows.append([f"{milestone}+",f"{model_prob:.1%}",fair,live_best,live_book])
status_text="LIVE SPORTSBOOK" if live_odds.get("status")=="live" else "MODEL FAIR ODDS";status_cls="sok-odds-live" if live_odds.get("status")=="live" else "sok-odds-muted";ladder_html='<table class="sok-odds-table"><thead><tr><th>STRIKEOUT LADDER</th><th>MODEL PROB.</th><th>FAIR ODDS</th><th>BEST LIVE OVER</th><th>BOOK</th></tr></thead><tbody>'
for row in ladder_rows:ladder_html+='<tr>'+''.join(f'<td>{cell}</td>' for cell in row)+'</tr>'
ladder_html+='</tbody></table>';book_count=len(live_odds.get("bookmakers",{}));source_odds_note=(f"{book_count} US books connected · refreshed automatically" if live_odds.get("status")=="live" else "Connect THE_ODDS_API_KEY for live sportsbook lines · model fair odds remain active")
st.markdown(f'<div class="sok-odds-panel"><div class="sok-odds-title">ODDS &amp; LINES</div><div class="sok-odds-sub"><span class="{status_cls}">{status_text}</span> &nbsp; 3+ through 10+ strikeout ladder · {source_odds_note}</div>{ladder_html}</div>',unsafe_allow_html=True)
'''
source=source.replace('\nst.caption("Probabilities are model estimates, not guarantees.")',ODDS_BLOCK+'\nst.caption("Probabilities are model estimates, not guarantees.")',1)

compile(source,LEGACY,'exec')
exec(compile(source,LEGACY,'exec'),globals(),globals())
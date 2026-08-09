from __future__ import annotations
import hashlib, os, re, math
from pathlib import Path
import requests
import streamlit as st

LEGACY="https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/f0b28d2a9f91cc145736eb2d3e0c1a72d3275f43/streamlit_app.py"
BASE_DIR=Path(__file__).resolve().parent
MASCOT_PATH=BASE_DIR/"assets"/"strikeout_king_9000_96.png"
if not MASCOT_PATH.exists(): MASCOT_PATH=BASE_DIR/"assets"/"strikeout_king_9000.png"
_original_markdown=st.markdown
_original_image=st.image

OVERRIDES="""
<style>
[data-testid="stSidebar"]{width:205px!important;min-width:205px!important}
[data-testid="stSidebar"] .block-container{padding:.3rem .65rem 1rem!important}
[data-testid="stSidebarNav"]{display:none!important}
[data-testid="stAppViewContainer"] .main .block-container{max-width:1500px!important;padding:0 .8rem 2rem!important}
.sok-search-title{margin-top:.45rem!important}.sok-lock{font-size:.68rem!important}.sok-date{margin-top:.4rem!important}
.sok-two-path{margin-top:1rem!important;border:1px solid #35516d!important;border-radius:15px!important;background:linear-gradient(145deg,#0a203b,#06162a)!important;overflow:hidden!important}.sok-two-path-title,.sok-odds-title{display:block!important;text-align:center!important;padding:.5rem 1.5rem!important;background:linear-gradient(180deg,#ed193a,#c60c2a)!important;color:#fff!important;font-family:Impact,"Arial Narrow",sans-serif!important;letter-spacing:.07em!important;font-size:1rem!important}.sok-two-path-grid{display:grid!important;grid-template-columns:1fr 1fr 1.2fr!important}.sok-two-path-cell{padding:.8rem 1rem!important;border-right:1px solid #223d58!important}.sok-two-path-cell:last-child{border-right:0!important}.sok-two-path-kicker{color:#aebed0!important;font-size:.68rem!important;font-weight:900!important}.sok-two-path-value{color:#fff!important;font-family:Impact,"Arial Narrow",sans-serif!important;font-size:2rem!important}.sok-two-path-detail{color:#aebed0!important;font-size:.72rem!important;line-height:1.45!important}.sok-two-path-ensemble,.sok-odds-live{color:#42ef90!important;font-weight:900!important}
.sok-odds-panel{margin-top:1rem!important;border:1px solid #35516d!important;border-radius:15px!important;background:linear-gradient(145deg,#0a203b,#06162a)!important;overflow:hidden!important}.sok-odds-sub{padding:.55rem .8rem .25rem!important;color:#aebed0!important;font-size:.72rem!important;text-align:center!important}.sok-odds-table{width:100%!important;border-collapse:collapse!important;color:#e6edf4!important;font-size:.78rem!important}.sok-odds-table th{color:#d9e2eb!important;background:#0b1d34!important;font-family:Impact,"Arial Narrow",sans-serif!important}.sok-odds-table th,.sok-odds-table td{padding:.55rem .6rem!important;border-bottom:1px solid #223d58!important;text-align:left!important}
@media(max-width:1000px){.sok-two-path-grid{grid-template-columns:1fr!important}.sok-two-path-cell{border-right:0!important;border-bottom:1px solid #223d58!important}}
</style>
"""

def patched_markdown(body=None,*args,**kwargs):
    if isinstance(body,str) and '<style>' in body and '--navy:' in body:return _original_markdown(body+OVERRIDES,*args,**kwargs)
    return _original_markdown(body,*args,**kwargs)

def patched_image(image,*args,**kwargs):
    text=str(image) if isinstance(image,(str,bytes,Path)) else ''
    if 'strikeout_king_9000' in text:return _original_image(str(MASCOT_PATH),width=kwargs.get('width',250))
    return _original_image(image,*args,**kwargs)

st.markdown=patched_markdown
st.image=patched_image

r=requests.get(LEGACY,timeout=20);r.raise_for_status();source=r.text

# UI substitutions only. The legacy schedule/client/history functions are intentionally preserved.
source=source.replace('''    selected_date=st.date_input("Slate date",value=odds_default_date)
    st.markdown(f'<div class="sok-date"><div class="label">SLATE DATE</div><div class="value">{selected_date:%Y/%m/%d}</div><div class="updated">Updated {now:%I:%M %p ET}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="sok-search-title">PITCHER SEARCH</div>',unsafe_allow_html=True)
    pitcher_query=st.text_input("Search pitcher",placeholder="Search pitcher...",label_visibility="collapsed",key="sok_pitcher_search")
    st.markdown('<div class="sok-lock">Search and select a pitcher to lock the projection 🔒</div>',unsafe_allow_html=True)''','''    st.markdown('<div class="sok-search-title">PITCHER SEARCH</div>',unsafe_allow_html=True)
    pitcher_query=st.text_input("Search pitcher",placeholder="Search pitcher...",label_visibility="collapsed",key="sok_pitcher_search")
    st.markdown('<div class="sok-lock">Search and select a pitcher to lock the projection</div>',unsafe_allow_html=True)
    selected_date=st.date_input("Slate date",value=odds_default_date)
    st.markdown(f'<div class="sok-date"><div class="label">SLATE DATE</div><div class="value">{selected_date:%Y/%m/%d}</div><div class="updated">Updated {now:%I:%M %p ET}</div></div>',unsafe_allow_html=True)''',1)
source=source.replace('<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="/3_Odds_API">◎ &nbsp; Odds API</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>','<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><div class="sok-disabled-nav">Distribution</div><div class="sok-disabled-nav">Form &amp; Workload</div><div class="sok-disabled-nav">Model Card</div><a href="/2_Bet_Tracker">Bet Tracker</a><a href="/4_Projection_History">Projection History</a><a href="/5_Daily_Projection_Run">Daily Projection Run</a></div>',1)
source=source.replace('''    if logo_path.exists():st.markdown('<div class="sok-sidebar-logo">',unsafe_allow_html=True);st.image(str(logo_path),width=130);st.markdown('</div>',unsafe_allow_html=True)''','''    st.markdown('<div class="sok-sidebar-logo">',unsafe_allow_html=True);st.image(str(MASCOT_PATH),width=130);st.markdown('</div>',unsafe_allow_html=True)''',1)
source=source.replace('''with h1:
    if logo_path.exists():st.image(str(logo_path),width=175)''','''with h1:
    st.image(str(MASCOT_PATH),width=250)''',1)

TWO_PATH=r'''
@dataclass(frozen=True)
class Projection:
    mean_k: float; mean_outs: float; k_sd: float; outs_sd: float
    k_probs: np.ndarray; outs_probs: np.ndarray; k_samples: np.ndarray; outs_samples: np.ndarray
    confidence: str; data_quality: int; factors: list[tuple[str,float]]
    sim_mean_k: float; sim_mean_outs: float; math_mean_k: float; math_mean_outs: float
    sim_k_sd: float; sim_outs_sd: float; math_k_sd: float; math_outs_sd: float

def _sok_math_path(log,game,manual):
    starts=log[log["games_started"]>0].copy().tail(35)
    if starts.empty:starts=log.tail(20).copy()
    bf=weighted_mean(starts["batters_faced"],5.0,22.0);outs=weighted_mean(starts["outs"],5.0,16.0);pitches=weighted_mean(starts["pitches"],5.0,88.0)
    total_bf=float(starts["batters_faced"].sum());raw_k=float(starts["strikeouts"].sum()/max(total_bf,1));k_rate=shrink(raw_k,total_bf,.224,120.0)
    opp=manual["opponent_k_pct"]/22.4;park=PARK_K_FACTOR.get(game.venue,1.0);ump=manual["umpire_k_factor"];weather=manual["weather_factor"];rest=manual["rest_factor"]
    limit=float(np.clip(manual["pitch_limit"]/max(pitches,75.0),.78,1.12));proj_bf=bf*limit*rest;proj_outs=float(np.clip(outs*limit*rest,3,24))
    proj_k=float(np.clip(.78*(proj_bf*k_rate*opp*park*ump*weather)+.22*weighted_mean(starts["strikeouts"],5,5.0),.5,13.5))
    kv=float(starts["strikeouts"].var(ddof=1)) if len(starts)>2 else proj_k*1.25;disp=max((kv-proj_k)/max(proj_k**2,.1),.08)
    return dict(mean_k=proj_k,mean_outs=proj_outs,k_probs=negbin_pmf(proj_k,disp,18),outs_probs=discrete_normal_probs(proj_outs,float(np.clip(starts["outs"].std(ddof=1) if len(starts)>2 else 4,2.5,6.5)),27),k_sd=math.sqrt(kv),outs_sd=float(np.clip(starts["outs"].std(ddof=1) if len(starts)>2 else 4,2.5,6.5)),pitch_limit_factor=limit,opponent_factor=opp,park_factor=park,ump_factor=ump,weather_factor=weather,rest_factor=rest,starts=starts,total_bf=total_bf)

def _sok_simulation_path(log,game,manual,simulations,seed):
    starts=log[log["games_started"]>0].copy().tail(35)
    if starts.empty:starts=log.tail(20).copy()
    starts=starts.reset_index(drop=True);n=len(starts)
    if n==0:raise ValueError("No historical starts available for simulation.")
    ages=np.arange(n-1,-1,-1,dtype=float);weights=np.exp(-.08*ages);weights/=weights.sum();rng=np.random.default_rng(seed);idx=rng.choice(n,size=simulations,p=weights)
    bf=starts["batters_faced"].to_numpy(float)[idx];outs=starts["outs"].to_numpy(float)[idx];bf_sd=float(starts["batters_faced"].std(ddof=1)) if n>2 else 3.5;out_sd=float(starts["outs"].std(ddof=1)) if n>2 else 3
    total_bf=float(starts["batters_faced"].sum());total_k=float(starts["strikeouts"].sum());a=max(.224*120+total_k,.5);b=max(.776*120+total_bf-total_k,.5);rate=rng.beta(a,b,size=simulations)
    opp=manual["opponent_k_pct"]/22.4;park=PARK_K_FACTOR.get(game.venue,1.0);ump=manual["umpire_k_factor"];weather=manual["weather_factor"];rest=manual["rest_factor"];mean_pitch=weighted_mean(starts["pitches"],5,88);limit=float(np.clip(manual["pitch_limit"]/max(mean_pitch,75),.78,1.12));rate=np.clip(rate*opp*park*ump*weather,.02,.55)
    sim_bf=np.clip(np.rint(bf+rng.normal(0,max(bf_sd*.35,1),size=simulations)),12,35).astype(int);sim_bf=np.clip(np.rint(sim_bf*limit*rest),8,35).astype(int);sim_k=rng.binomial(sim_bf,rate).astype(float)
    sim_outs=np.clip(np.rint(outs+rng.normal(0,max(out_sd*.35,1),size=simulations)),3,27);sim_outs=np.clip(np.rint(sim_outs*limit*rest),3,27)
    return dict(k_samples=sim_k,outs_samples=sim_outs,mean_k=float(sim_k.mean()),mean_outs=float(sim_outs.mean()),k_sd=float(sim_k.std(ddof=1)),outs_sd=float(sim_outs.std(ddof=1)))

def _sok_hist_probs(samples,maximum):
    values=np.clip(np.rint(samples).astype(int),0,maximum);counts=np.bincount(values,minlength=maximum+1).astype(float);return counts/counts.sum()

def calculate_projection(log,game,manual,simulations)->Projection:
    simulations=max(int(simulations),25000);m=_sok_math_path(log,game,manual);seed=int(hashlib.sha256(f"{game.key}|{date.today()}|{APP_VERSION}|two-path-v4".encode()).hexdigest()[:8],16);s=_sok_simulation_path(log,game,manual,simulations,seed);rng=np.random.default_rng(seed+1)
    mk=rng.choice(np.arange(len(m["k_probs"])),size=simulations,p=m["k_probs"]);mo=rng.choice(np.arange(len(m["outs_probs"])),size=simulations,p=m["outs_probs"]);take=rng.random(simulations)<.5;k=np.where(take,s["k_samples"],mk);o=np.where(take,s["outs_samples"],mo);kp=_sok_hist_probs(k,18);op=_sok_hist_probs(o,27)
    q=min(100,35+len(m["starts"])*2+(15 if m["total_bf"]>=250 else 0)+(10 if game.pitcher_id else 0));conf="High" if q>=85 else "Medium" if q>=65 else "Low";f=[("Opponent strikeout profile",m["opponent_factor"]-1),("Recent workload / pitch limit",m["pitch_limit_factor"]-1),("Park",m["park_factor"]-1),("Umpire",m["ump_factor"]-1),("Weather",m["weather_factor"]-1),("Rest",m["rest_factor"]-1)]
    return Projection(float(k.mean()),float(o.mean()),float(k.std(ddof=1)),float(o.std(ddof=1)),kp,op,k,o,conf,q,f,s["mean_k"],s["mean_outs"],m["mean_k"],m["mean_outs"],s["k_sd"],s["outs_sd"],m["k_sd"],m["outs_sd"])
'''

# CRITICAL FIX: replace ONLY Projection, stopping immediately before MLBClient.
block=re.search(r'@dataclass\(frozen=True\)\nclass Projection:.*?\n\n(?=class MLBClient:)',source,flags=re.S)
if not block:raise RuntimeError("Legacy Projection block not found")
source=source[:block.start()]+TWO_PATH+'\n\n'+source[block.end():]
# Remove ONLY the original calculate_projection function.
source,n=re.subn(r'def calculate_projection\(log,game,manual,simulations\)->Projection:.*?\n(?=def over_probability)','',source,count=1,flags=re.S)
if n!=1:raise RuntimeError("Legacy calculate_projection block not found")

PANEL="""\nst.markdown(f'<div class=\"sok-two-path\"><div class=\"sok-two-path-title\">TWO-PATH PROJECTION ENGINE</div><div class=\"sok-two-path-grid\"><div class=\"sok-two-path-cell\"><div class=\"sok-two-path-kicker\">PATH 1 - 25,000 SIMULATED GAMES</div><div class=\"sok-two-path-value\">K {projection.sim_mean_k:.2f} · OUTS {projection.sim_mean_outs:.2f}</div><div class=\"sok-two-path-detail\">Recency-weighted historical workloads, empirical-Bayes skill, context adjustments, and game-level draws.</div></div><div class=\"sok-two-path-cell\"><div class=\"sok-two-path-kicker\">PATH 2 - MATHEMATICAL MODEL</div><div class=\"sok-two-path-value\">K {projection.math_mean_k:.2f} · OUTS {projection.math_mean_outs:.2f}</div><div class=\"sok-two-path-detail\">Weighted form, shrinkage, context factors, Negative Binomial strikeout distribution, and bounded outs distribution.</div></div><div class=\"sok-two-path-cell\"><div class=\"sok-two-path-kicker\">FINAL ENSEMBLE - 50/50</div><div class=\"sok-two-path-value sok-two-path-ensemble\">K {projection.mean_k:.2f} · OUTS {projection.mean_outs:.2f}</div><div class=\"sok-two-path-detail\">Final probabilities, ranges, fair odds, and ladder use the blended distributions.</div></div></div></div>',unsafe_allow_html=True)\n"""
marker=';projection=calculate_projection(log,game,manual,simulations)'
if marker not in source:raise RuntimeError("Projection marker not found")
source=source.replace(marker,marker+PANEL,1)

ODDS_HELPER=r'''
def _sok_odds_api_key():
    key=os.environ.get("THE_ODDS_API_KEY","").strip()
    if key:return key
    try:return str(st.secrets.get("THE_ODDS_API_KEY","")).strip()
    except Exception:return ""
def _sok_live_pitcher_odds(pitcher_name,team_abbr,opponent_abbr):
    key=_sok_odds_api_key()
    if not key:return {"status":"model_only","bookmakers":{},"lines":[]}
    try:
        events=requests.get("https://api.the-odds-api.com/v4/sports/baseball_mlb/events",params={"apiKey":key},timeout=12).json();event_id=None
        for e in events if isinstance(events,list) else []:
            names=f"{e.get('home_team','')} {e.get('away_team','')}".upper()
            if team_abbr.upper() in names and opponent_abbr.upper() in names:event_id=e.get("id");break
        if not event_id:return {"status":"no_event","bookmakers":{},"lines":[]}
        p=requests.get(f"https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{event_id}/odds",params={"apiKey":key,"regions":"us","oddsFormat":"american","markets":"pitcher_strikeouts,pitcher_strikeouts_alternate"},timeout=12).json();rows=[];books={}
        for b in p.get("bookmakers",[]) if isinstance(p,dict) else []:
            title=b.get("title",b.get("key","Book"));books[title]=True
            for m in b.get("markets",[]):
                if m.get("key") not in {"pitcher_strikeouts","pitcher_strikeouts_alternate"}:continue
                for o in m.get("outcomes",[]):
                    if str(o.get("description","")).strip().lower()==pitcher_name.strip().lower() and o.get("point") is not None and o.get("price") is not None:rows.append({"book":title,"side":o.get("name"),"point":float(o["point"]),"price":int(o["price"])})
        return {"status":"live" if rows else "no_player_market","bookmakers":books,"lines":rows}
    except Exception:return {"status":"error","bookmakers":{},"lines":[]}
'''
source=source.replace('\nnow=datetime.now(EASTERN);query_day=now.date()',ODDS_HELPER+'\nnow=datetime.now(EASTERN);query_day=now.date()',1)
ODDS_BLOCK=r'''
try:live_odds=_sok_live_pitcher_odds(game.pitcher_name,game.team,game.opponent)
except Exception:live_odds={"status":"error","bookmakers":{},"lines":[]}
rows=[]
for milestone in range(3,11):
    prob=float(np.mean(projection.k_samples>=milestone));fair=fair_american(prob);matches=[r for r in live_odds.get("lines",[]) if r.get("side")=="Over" and abs(float(r.get("point",0))-(milestone-.5))<1e-9];best=max(matches,key=lambda r:int(r.get("price",-9999))) if matches else None;rows.append([f"{milestone}+",f"{prob:.1%}",fair,f"{int(best['price']):+d}" if best else "—",str(best.get("book","Book")) if best else "—"])
status="LIVE SPORTSBOOK" if live_odds.get("status")=="live" else "MODEL FAIR ODDS";cls="sok-odds-live" if live_odds.get("status")=="live" else "sok-odds-muted";html='<table class="sok-odds-table"><thead><tr><th>STRIKEOUT LADDER</th><th>MODEL PROB.</th><th>FAIR ODDS</th><th>BEST LIVE OVER</th><th>BOOK</th></tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{c}</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>';note=(f"{len(live_odds.get('bookmakers',{}))} US books connected · refreshed automatically" if live_odds.get("status")=="live" else "Connect THE_ODDS_API_KEY for live sportsbook lines · model fair odds remain active")
st.markdown(f'<div class="sok-odds-panel"><div class="sok-odds-title">ODDS &amp; LINES</div><div class="sok-odds-sub"><span class="{cls}">{status}</span> &nbsp; 3+ through 10+ strikeout ladder · {note}</div>{html}</div>',unsafe_allow_html=True)
'''
source=source.replace('\nst.caption("Probabilities are model estimates, not guarantees.")',ODDS_BLOCK+'\nst.caption("Probabilities are model estimates, not guarantees.")',1)

# Fail closed: syntax must be valid before Streamlit executes anything.
compile(source,LEGACY,'exec')
exec(compile(source,LEGACY,'exec'),globals(),globals())

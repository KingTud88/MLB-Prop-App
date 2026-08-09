from __future__ import annotations

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

OVERRIDES = r'''
<style>
[data-testid="stSidebar"]{width:205px!important;min-width:205px!important}
[data-testid="stSidebar"] .block-container{padding:.35rem .65rem 1rem!important}
[data-testid="stSidebarNav"]{display:none!important}
[data-testid="stAppViewContainer"] .main .block-container{max-width:1500px!important;padding:0 .8rem 2rem!important}
.sok-search-title{margin-top:.45rem!important}.sok-lock{font-size:.68rem!important}.sok-date{margin-top:.4rem!important}
.sok-two-path,.sok-odds-panel{margin-top:1rem!important;border:1px solid #35516d!important;border-radius:15px!important;background:linear-gradient(145deg,#0a203b,#06162a)!important;overflow:hidden!important}
.sok-two-path-title,.sok-odds-title{display:block!important;text-align:center!important;padding:.5rem 1.5rem!important;background:linear-gradient(180deg,#ed193a,#c60c2a)!important;color:#fff!important;font-family:Impact,"Arial Narrow",sans-serif!important;letter-spacing:.07em!important;font-size:1rem!important}
.sok-two-path-grid{display:grid!important;grid-template-columns:1fr 1fr 1.2fr!important}.sok-two-path-cell{padding:.8rem 1rem!important;border-right:1px solid #223d58!important}.sok-two-path-cell:last-child{border-right:0!important}
.sok-two-path-kicker{color:#aebed0!important;font-size:.68rem!important;font-weight:900!important}.sok-two-path-value{color:#fff!important;font-family:Impact,"Arial Narrow",sans-serif!important;font-size:2rem!important}.sok-two-path-detail{color:#aebed0!important;font-size:.72rem!important;line-height:1.45!important}.sok-two-path-ensemble,.sok-odds-live{color:#42ef90!important;font-weight:900!important}
.sok-odds-sub{padding:.55rem .8rem .25rem!important;color:#aebed0!important;font-size:.72rem!important;text-align:center!important}.sok-odds-table{width:100%!important;border-collapse:collapse!important;color:#e6edf4!important;font-size:.78rem!important}.sok-odds-table th{color:#d9e2eb!important;background:#0b1d34!important;font-family:Impact,"Arial Narrow",sans-serif!important}.sok-odds-table th,.sok-odds-table td{padding:.55rem .6rem!important;border-bottom:1px solid #223d58!important;text-align:left!important}
@media(max-width:1000px){.sok-two-path-grid{grid-template-columns:1fr!important}.sok-two-path-cell{border-right:0!important;border-bottom:1px solid #223d58!important}}
</style>
'''

def patched_markdown(body=None,*args,**kwargs):
    if isinstance(body,str) and '<style>' in body and '--navy:' in body:
        return _original_markdown(body+OVERRIDES,*args,**kwargs)
    return _original_markdown(body,*args,**kwargs)

def patched_image(image,*args,**kwargs):
    text=str(image) if isinstance(image,(str,bytes,Path)) else ''
    if 'strikeout_king_9000' in text and MASCOT_PATH.exists():
        return _original_image(str(MASCOT_PATH),width=kwargs.get('width',250))
    return _original_image(image,*args,**kwargs)

st.markdown=patched_markdown
st.image=patched_image

try:
    response=requests.get(LEGACY,timeout=20)
    response.raise_for_status()
    source=response.text
except requests.RequestException as exc:
    st.error(f"StrikeOut King 9000 source unavailable: {exc}")
    st.stop()

# Guard the legacy source before we transform anything. This is the failure that caused
# the repeated get_schedule NameError during the previous patch cycle.
required=["class MLBClient:","def get_schedule(","def get_pitcher_game_log(","def calculate_projection(","def over_probability("]
missing=[item for item in required if item not in source]
if missing:
    st.error("Legacy source validation failed before execution: "+", ".join(missing))
    st.stop()

# Keep the legacy model as Path 2. Rename only the function; all schedule/history/client
# code stays byte-for-byte intact. Then add Path 1 and a 50/50 ensemble wrapper.
source=source.replace("def calculate_projection(","def _sok_math_projection(",1)

TWO_PATH=r'''
TWO_PATH_DETAILS={}

def _sok_simulated_path(log,game,manual,simulations,seed):
    starts=log[log["games_started"]>0].copy().tail(35)
    if starts.empty: starts=log.tail(20).copy()
    if starts.empty: raise ValueError("No historical starts available for simulation.")
    starts=starts.reset_index(drop=True)
    rng=np.random.default_rng(seed)
    n=len(starts)
    ages=np.arange(n-1,-1,-1,dtype=float)
    weights=np.exp(-0.08*ages);weights/=weights.sum()
    idx=rng.choice(n,size=simulations,p=weights)
    bf=starts["batters_faced"].to_numpy(float)[idx]
    outs=starts["outs"].to_numpy(float)[idx]
    bf_sd=float(starts["batters_faced"].std(ddof=1)) if n>2 else 3.5
    out_sd=float(starts["outs"].std(ddof=1)) if n>2 else 3.0
    total_bf=float(starts["batters_faced"].sum());total_k=float(starts["strikeouts"].sum())
    alpha=max(.224*120.0+total_k,.5);beta=max(.776*120.0+total_bf-total_k,.5)
    rate=rng.beta(alpha,beta,size=simulations)
    opp=manual["opponent_k_pct"]/22.4
    park=PARK_K_FACTOR.get(game.venue,1.0);ump=manual["umpire_k_factor"];weather=manual["weather_factor"];rest=manual["rest_factor"]
    mean_pitch=weighted_mean(starts["pitches"],5.0,88.0)
    limit=float(np.clip(manual["pitch_limit"]/max(mean_pitch,75.0),.78,1.12))
    rate=np.clip(rate*opp*park*ump*weather,.02,.55)
    sampled_bf=np.clip(np.rint(bf+rng.normal(0,max(bf_sd*.35,1.0),simulations)),12,35).astype(int)
    sampled_bf=np.clip(np.rint(sampled_bf*limit*rest),8,35).astype(int)
    k=rng.binomial(sampled_bf,rate).astype(float)
    o=np.clip(np.rint(outs+rng.normal(0,max(out_sd*.35,1.0),simulations)),3,27)
    o=np.clip(np.rint(o*limit*rest),3,27).astype(float)
    return k,o

def calculate_projection(log,game,manual,simulations):
    simulations=max(int(simulations),25000)
    math_projection=_sok_math_projection(log,game,manual,simulations)
    seed=int(hashlib.sha256(f"{game.key}|{date.today()}|{APP_VERSION}|two-path-v5".encode()).hexdigest()[:8],16)
    sim_k,sim_outs=_sok_simulated_path(log,game,manual,simulations,seed)
    rng=np.random.default_rng(seed+1)
    # Re-sample the mathematical distribution so the final ensemble is a true 50/50
    # mixture of Path 1 and Path 2 rather than an average of two means.
    math_k=rng.choice(np.arange(len(math_projection.k_probs)),size=simulations,p=math_projection.k_probs)
    math_outs=rng.choice(np.arange(len(math_projection.outs_probs)),size=simulations,p=math_projection.outs_probs)
    use_sim=rng.random(simulations)<0.5
    final_k=np.where(use_sim,sim_k,math_k).astype(float)
    final_outs=np.where(use_sim,sim_outs,math_outs).astype(float)
    k_probs=np.bincount(np.clip(np.rint(final_k).astype(int),0,18),minlength=19).astype(float);k_probs/=k_probs.sum()
    outs_probs=np.bincount(np.clip(np.rint(final_outs).astype(int),0,27),minlength=28).astype(float);outs_probs/=outs_probs.sum()
    TWO_PATH_DETAILS[game.key]={
        "sim_k":float(sim_k.mean()),"sim_outs":float(sim_outs.mean()),"sim_k_sd":float(sim_k.std(ddof=1)),"sim_outs_sd":float(sim_outs.std(ddof=1)),
        "math_k":float(math_projection.mean_k),"math_outs":float(math_projection.mean_outs),"math_k_sd":float(math_projection.k_sd),"math_outs_sd":float(math_projection.outs_sd),
        "ensemble_k":float(final_k.mean()),"ensemble_outs":float(final_outs.mean()),
    }
    return Projection(float(final_k.mean()),float(final_outs.mean()),float(final_k.std(ddof=1)),float(final_outs.std(ddof=1)),k_probs,outs_probs,final_k,final_outs,math_projection.confidence,math_projection.data_quality,math_projection.factors)
'''

source=source.replace("def over_probability(",TWO_PATH+"\ndef over_probability(",1)

PANEL=r'''
try:
    two_path=TWO_PATH_DETAILS.get(game.key,{})
    st.markdown(f'<div class="sok-two-path"><div class="sok-two-path-title">TWO-PATH PROJECTION ENGINE</div><div class="sok-two-path-grid"><div class="sok-two-path-cell"><div class="sok-two-path-kicker">PATH 1 - 25,000 SIMULATED GAMES</div><div class="sok-two-path-value">K {two_path.get("sim_k",projection.mean_k):.2f} · OUTS {two_path.get("sim_outs",projection.mean_outs):.2f}</div><div class="sok-two-path-detail">Recency-weighted historical starts, empirical-Bayes strikeout skill, context factors, and game-level draws.</div></div><div class="sok-two-path-cell"><div class="sok-two-path-kicker">PATH 2 - MATHEMATICAL MODEL</div><div class="sok-two-path-value">K {two_path.get("math_k",projection.mean_k):.2f} · OUTS {two_path.get("math_outs",projection.mean_outs):.2f}</div><div class="sok-two-path-detail">Weighted form, shrinkage, Negative Binomial strikeout distribution, and bounded outs distribution.</div></div><div class="sok-two-path-cell"><div class="sok-two-path-kicker">FINAL ENSEMBLE - 50/50</div><div class="sok-two-path-value sok-two-path-ensemble">K {projection.mean_k:.2f} · OUTS {projection.mean_outs:.2f}</div><div class="sok-two-path-detail">Final probabilities, ranges, and fair odds use the blended distribution.</div></div></div></div>',unsafe_allow_html=True)
except Exception:
    pass
'''
marker=';projection=calculate_projection(log,game,manual,simulations)'
if marker not in source:
    marker='\nprojection=calculate_projection(log,game,manual,simulations)'
if marker not in source:
    raise RuntimeError("Projection execution marker not found")
source=source.replace(marker,marker+'\n'+PANEL,1)

# Merge sportsbook odds into the Projection page. If the key is absent, model fair odds
# remain available and the page never fails because of the external market feed.
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
        payload=requests.get(f"https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{event_id}/odds",params={"apiKey":key,"regions":"us","oddsFormat":"american","markets":"pitcher_strikeouts,pitcher_strikeouts_alternate"},timeout=12).json();rows=[];books={}
        for b in payload.get("bookmakers",[]) if isinstance(payload,dict) else []:
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
try:
    live_odds=_sok_live_pitcher_odds(game.pitcher_name,game.team,game.opponent)
    rows=[]
    for milestone in range(3,11):
        prob=float(np.mean(projection.k_samples>=milestone));fair=fair_american(prob)
        matches=[r for r in live_odds.get("lines",[]) if r.get("side")=="Over" and abs(float(r.get("point",0))-(milestone-.5))<1e-9]
        best=max(matches,key=lambda r:int(r.get("price",-9999))) if matches else None
        rows.append([f"{milestone}+",f"{prob:.1%}",fair,f"{int(best['price']):+d}" if best else "—",str(best.get("book","Book")) if best else "—"])
    status="LIVE SPORTSBOOK" if live_odds.get("status")=="live" else "MODEL FAIR ODDS";cls="sok-odds-live" if live_odds.get("status")=="live" else "sok-odds-muted"
    html='<table class="sok-odds-table"><thead><tr><th>STRIKEOUT LADDER</th><th>MODEL PROB.</th><th>FAIR ODDS</th><th>BEST LIVE OVER</th><th>BOOK</th></tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{c}</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'
    note=f"{len(live_odds.get('bookmakers',{}))} US books connected · refreshed automatically" if live_odds.get("status")=="live" else "Connect THE_ODDS_API_KEY for live sportsbook lines · model fair odds remain active"
    st.markdown(f'<div class="sok-odds-panel"><div class="sok-odds-title">ODDS &amp; LINES</div><div class="sok-odds-sub"><span class="{cls}">{status}</span> &nbsp; 3+ through 10+ strikeout ladder · {note}</div>{html}</div>',unsafe_allow_html=True)
except Exception as exc:
    st.caption(f"Odds feed unavailable · model fair odds remain active ({type(exc).__name__})")
'''
source=source.replace('\nst.caption("Probabilities are model estimates, not guarantees.")',ODDS_BLOCK+'\nst.caption("Probabilities are model estimates, not guarantees.")',1)

try:
    compile(source,LEGACY,"exec")
except SyntaxError as exc:
    st.error(f"StrikeOut King 9000 source validation failed before Streamlit execution: line {exc.lineno}: {exc.msg}")
    st.stop()

exec(compile(source,LEGACY,"exec"),globals(),globals())

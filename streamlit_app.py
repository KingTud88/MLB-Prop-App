from __future__ import annotations
import hashlib, json, math, os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests
import streamlit as st

APP_VERSION="3.0.1"
EASTERN=ZoneInfo("America/New_York")
MLB_API="https://statsapi.mlb.com/api/v1"
ODDS_API="https://api.the-odds-api.com/v4"
APP_DIR=Path(__file__).resolve().parent
TEAM_ABBR={108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSH",121:"NYM",133:"ATH",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",147:"NYY",158:"MIL"}
PARK_K_FACTOR={"Coors Field":.94,"T-Mobile Park":1.05,"Petco Park":1.03,"Oracle Park":1.02,"Dodger Stadium":1.01,"Yankee Stadium":.99,"Fenway Park":.98,"Wrigley Field":1.00}

st.set_page_config(page_title="StrikeOut King 9000", page_icon="⚾", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
:root{--bg:#06111d;--panel:#0b1c2e;--line:#1b3851;--red:#f0193c;--green:#24e69b;--ink:#f2f6fa;--muted:#8fa5b7}
.stApp{background:linear-gradient(145deg,#04101b,#091a2a);color:var(--ink)}
[data-testid="stSidebar"]{background:#071727;border-right:1px solid #18334b}
.block-container{padding-top:1.2rem;max-width:1500px} h1,h2,h3{letter-spacing:-.02em}
.king-title{font-size:4rem;font-weight:900;line-height:.9;text-align:center}.king-red{color:var(--red)}
.subline{text-align:center;color:#fff;border-bottom:2px solid var(--red);padding-bottom:10px;font-weight:800;letter-spacing:.12em}
.pitcher-card,.metric-card,.panel{background:rgba(9,27,44,.94);border:1px solid #20425f;border-radius:16px}.pitcher-card{padding:18px 24px}
.section-head{background:linear-gradient(90deg,#ed1236,#f0193c);padding:9px 16px;border-radius:14px 14px 0 0;text-align:center;font-weight:900;letter-spacing:.08em}
.metric-card{padding:18px;text-align:center;min-height:155px}.metric-label{font-weight:800;color:#d8e5ef;letter-spacing:.05em}.metric-value{font-size:3.1rem;font-weight:900;line-height:1.05}
.badge{display:inline-block;background:#073d2c;border:1px solid #087c59;color:#49efb0;border-radius:999px;padding:5px 10px;font-weight:800;font-size:.82rem}
.search-note{color:var(--muted);font-size:.82rem}
</style>""",unsafe_allow_html=True)

@dataclass(frozen=True)
class GamePitcher:
    key:str; pitcher_id:int; pitcher_name:str; team:str; opponent:str; side:str; venue:str; game_pk:int; game_time:str; status:str
@dataclass
class Projection:
    mean_k:float; mean_outs:float; k_sd:float; outs_sd:float; k_probs:np.ndarray; outs_probs:np.ndarray; k_samples:np.ndarray; outs_samples:np.ndarray; confidence:str; quality:int; factors:list[tuple[str,float]]

class MLBClient:
    def __init__(self):
        self.session=requests.Session(); self.session.headers.update({"Accept":"application/json","User-Agent":f"StrikeOutKing9000/{APP_VERSION}"})
    def get(self,endpoint,params):
        r=self.session.get(f"{MLB_API}/{endpoint}",params=params,timeout=20); r.raise_for_status(); data=r.json()
        if not isinstance(data,dict): raise ValueError("Unexpected MLB response")
        return data

def get_schedule(day):
    try:p=MLBClient().get("schedule",{"sportId":1,"date":day,"hydrate":"probablePitcher,team,venue"})
    except Exception as e:return [],str(e)
    rows=[]
    for block in p.get("dates",[]):
        for game in block.get("games",[]):
            teams=game.get("teams",{}); pk=int(game.get("gamePk",0)); venue=game.get("venue",{}).get("name","Unknown")
            for side,other in (("away","home"),("home","away")):
                node=teams.get(side,{}) or {}; opp=teams.get(other,{}) or {}; pit=node.get("probablePitcher") or {}
                if not pit.get("id"):continue
                tn=node.get("team",{}); on=opp.get("team",{})
                team=TEAM_ABBR.get(tn.get("id"),tn.get("abbreviation","UNK")); opponent=TEAM_ABBR.get(on.get("id"),on.get("abbreviation","UNK"))
                rows.append(GamePitcher(f"{pk}:{pit['id']}",int(pit["id"]),pit.get("fullName","Unknown"),team,opponent,side.title(),venue,pk,game.get("gameDate",""),game.get("status",{}).get("detailedState","Scheduled")))
    return rows,None

def parse_ip(v):
    try:
        whole,frac=str(v).split("."); return int(whole)+int(frac)/3
    except: return 0.0

@st.cache_data(ttl=1800,show_spinner=False)
def get_log(pid,season):
    try:p=MLBClient().get(f"people/{pid}/stats",{"stats":"gameLog","group":"pitching","season":season,"gameType":"R"})
    except Exception as e:return pd.DataFrame(),str(e)
    rec=[]
    for sb in p.get("stats",[]):
        for sp in sb.get("splits",[]):
            s=sp.get("stat",{}); bf=float(s.get("battersFaced",0) or 0)
            rec.append({"date":pd.to_datetime(sp.get("date"),errors="coerce"),"opponent":sp.get("opponent",{}).get("name",""),"bf":bf,"k":float(s.get("strikeOuts",0) or 0),"pitches":float(s.get("numberOfPitches",0) or 0),"outs":parse_ip(s.get("inningsPitched","0.0"))*3})
    df=pd.DataFrame(rec); return (df.sort_values("date"),None) if not df.empty else (df,"No regular-season game log returned.")

def weighted(s,half,fallback):
    x=pd.to_numeric(s,errors="coerce").dropna().to_numpy(float)
    if not len(x):return fallback
    age=np.arange(len(x)-1,-1,-1); w=.5**(age/half); return float(np.average(x,weights=w))
def shrink(rate,opp,prior=.224,weight=120):return (rate*opp+prior*weight)/max(opp+weight,1)
def nb_pmf(mean,disp,maxk=18):
    mean=max(mean,.05); disp=max(disp,.08); r=1/disp; p=r/(r+mean)
    probs=np.array([math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)+r*math.log(p)+k*math.log(1-p)) for k in range(maxk+1)])
    probs[-1]+=max(0,1-probs.sum()); return probs/probs.sum()
def norm_probs(mean,sd,maxv=27):
    xs=np.arange(maxv+1); sd=max(sd,.5); erf=np.vectorize(math.erf); hi=(xs+.5-mean)/(sd*math.sqrt(2)); lo=(xs-.5-mean)/(sd*math.sqrt(2))
    p=.5*(erf(hi)-erf(lo)); p[0]+=.5*(1+math.erf((-.5-mean)/(sd*math.sqrt(2)))); p[-1]+=.5*(1-math.erf((maxv+.5-mean)/(sd*math.sqrt(2)))); p=np.clip(p,0,None); return p/p.sum()

def calculate_projection(log,game,simulations):
    starts=log.tail(35).copy(); bf=weighted(starts.bf,5,22); outs=weighted(starts.outs,5,16); pitches=weighted(starts.pitches,5,88); total_bf=float(starts.bf.sum())
    raw=float(starts.k.sum()/max(total_bf,1)); kr=shrink(raw,total_bf); park=PARK_K_FACTOR.get(game.venue,1); workload=float(np.clip(92/max(pitches,75),.78,1.12))
    mean_bf=bf*workload; mean_outs=float(np.clip(outs*workload,3,24)); mean_k=float(np.clip(.78*(mean_bf*kr*park)+.22*weighted(starts.k,5,5),.5,13.5))
    var=float(starts.k.var(ddof=1)) if len(starts)>2 else mean_k*1.25; disp=max((var-mean_k)/max(mean_k**2,.1),.08); kp=nb_pmf(mean_k,disp)
    osd=float(np.clip(starts.outs.std(ddof=1) if len(starts)>2 else 4,2.5,6.5)); op=norm_probs(mean_outs,osd)
    seed=int(hashlib.sha256(f"{game.key}|{date.today()}|{APP_VERSION}".encode()).hexdigest()[:8],16); rng=np.random.default_rng(seed)
    ks=rng.choice(np.arange(len(kp)),simulations,p=kp); os=rng.choice(np.arange(len(op)),simulations,p=op); q=min(100,35+len(starts)*2+(15 if total_bf>=250 else 0)); conf="High" if q>=85 else "Medium" if q>=65 else "Low"
    factors=[("Opponent strikeout profile",0),("Recent workload / pitch limit",workload-1),("Park",park-1),("Umpire",0),("Weather",0),("Rest",0)]
    return Projection(mean_k,mean_outs,math.sqrt(max(var,.1)),osd,kp,op,ks,os,conf,q,factors)

def american(p):
    p=float(np.clip(p,.001,.999)); o=-100*p/(1-p) if p>=.5 else 100*(1-p)/p; return f"{o:+.0f}"
def sim_prob(samples,line):return float(np.mean(samples>=math.ceil(line))) if float(line).is_integer() else float(np.mean(samples>line))
def math_prob_from_pmf(pmf,line):
    cutoff=math.floor(line)+1; return float(pmf[cutoff:].sum()) if cutoff<len(pmf) else 0.0
def ladder(proj,max_line=10):
    rows=[]
    for line in range(3,max_line+1):
        sim=sim_prob(proj.k_samples,line); analytic=math_prob_from_pmf(proj.k_probs,line); blended=.5*sim+.5*analytic; rows.append({"Line":f"{line}+","Probability":blended,"Fair Odds":american(blended),"Simulation":sim,"Math":analytic})
    return pd.DataFrame(rows)

def get_secret():
    for k in ("ODDS_API_KEY","THE_ODDS_API_KEY","odds_api_key"):
        try:
            if k in st.secrets:return str(st.secrets[k])
        except:pass
    return os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY")
@st.cache_data(ttl=60,show_spinner=False)
def get_odds_events():
    key=get_secret()
    if not key:return [],"Odds API key not found in Streamlit secrets."
    try:
        r=requests.get(f"{ODDS_API}/sports/baseball_mlb/events",params={"apiKey":key},timeout=15); r.raise_for_status(); return r.json(),None
    except Exception as e:return [],f"Odds API unavailable: {e}"
@st.cache_data(ttl=60,show_spinner=False)
def get_event_props(event_id):
    key=get_secret()
    if not key:return [],"Odds API key not found in Streamlit secrets."
    params={"apiKey":key,"regions":"us","markets":"pitcher_strikeouts_alternate,pitcher_outs_alternate","oddsFormat":"american"}
    try:
        r=requests.get(f"{ODDS_API}/sports/baseball_mlb/events/{event_id}/odds",params=params,timeout=15); r.raise_for_status(); return r.json(),None
    except Exception as e:return [],f"Odds API unavailable: {e}"
def find_odds_event(events,game):
    target={game.team,game.opponent}
    for event in events if isinstance(events,list) else []:
        teams={str(event.get("home_team","")),str(event.get("away_team",""))}
        if teams==target or (game.team in teams and game.opponent in teams):return event.get("id")
    return None
def extract_player_odds(payload,pitcher_name):
    rows=[]
    for bm in payload.get("bookmakers",[]) if isinstance(payload,dict) else []:
        for m in bm.get("markets",[]):
            if m.get("key") not in ("pitcher_strikeouts_alternate","pitcher_outs_alternate"):continue
            for o in m.get("outcomes",[]):
                if o.get("description","").lower()!=pitcher_name.lower():continue
                rows.append({"book":bm.get("title",bm.get("key","")),"market":m["key"],"name":o.get("name"),"point":o.get("point"),"price":o.get("price")})
    return rows

with st.sidebar:
    st.markdown("## StrikeOut King 9000"); st.caption("CLE-themed MLB starter projection engine")
    nav=st.radio("Navigation",["Projection","Distribution","Form & Workload","Model Card","Bet Tracker","Projection History","Daily Projection Run"],label_visibility="collapsed")
    st.divider(); selected_date=st.date_input("Slate date",value=datetime.now(EASTERN).date()); st.markdown("### PITCHER SEARCH")
    search=st.text_input("Search pitcher...",placeholder="Search pitcher...",label_visibility="collapsed"); st.caption("Search and select a pitcher to lock the projection 🔒")

schedule,err=get_schedule(selected_date.isoformat())
if err:st.error(err)
if not schedule:st.warning("No announced probable pitchers are available for this date."); st.stop()
matches=[g for g in schedule if not search or search.lower() in g.pitcher_name.lower() or search.lower() in g.team.lower()]
if not matches:st.info("No pitchers match that search."); st.stop()
names=[f"{g.pitcher_name} · {g.team} vs {g.opponent}" for g in matches]
with st.sidebar:
    choice=st.selectbox("Matching pitchers",names,label_visibility="collapsed",key="pitcher_selector")
game=matches[names.index(choice)]
locked=st.session_state.get("locked_pitcher")==game.key
with st.sidebar:
    if st.button("🔒 LOCK PITCHER" if not locked else "🔓 UNLOCK PITCHER",use_container_width=True):
        st.session_state["locked_pitcher"]=None if locked else game.key
        st.rerun()

log,herr=get_log(game.pitcher_id,selected_date.year)
if log.empty:log,herr=get_log(game.pitcher_id,selected_date.year-1)
if log.empty:st.error(herr or "Pitcher history unavailable."); st.stop()
proj=calculate_projection(log,game,25000); kdf=ladder(proj,10)
odds_events,odds_err=get_odds_events(); odds_event_id=find_odds_event(odds_events,game)
if odds_event_id:
    odds_payload,prop_err=get_event_props(odds_event_id)
    if prop_err:odds_err=prop_err
else:
    odds_payload=[]
    if odds_err is None:odds_err="No matching Odds API event found for this MLB game."
odds_rows=extract_player_odds(odds_payload,game.pitcher_name)

if nav=="Distribution":
    st.markdown('<div class="section-head">DISTRIBUTION</div>',unsafe_allow_html=True)
    st.caption(f"{game.pitcher_name} · {game.team} vs {game.opponent}")
    a,b=st.columns(2)
    with a:st.markdown("### Strikeout probability distribution"); st.bar_chart(pd.DataFrame({"Probability":proj.k_probs},index=np.arange(len(proj.k_probs))))
    with b:st.markdown("### Outs probability distribution"); st.bar_chart(pd.DataFrame({"Probability":proj.outs_probs},index=np.arange(len(proj.outs_probs))))
    st.stop()
elif nav=="Form & Workload":
    st.markdown('<div class="section-head">FORM & WORKLOAD</div>',unsafe_allow_html=True)
    st.caption(f"{game.pitcher_name} · last 15 starts")
    d=log.tail(15).copy(); st.line_chart(d.set_index("date")[["k","outs"]]); st.dataframe(d.sort_values("date",ascending=False),use_container_width=True,hide_index=True)
    st.stop()
elif nav=="Model Card":
    st.markdown('<div class="section-head">MODEL CARD</div>',unsafe_allow_html=True)
    st.write("Two-path architecture: (1) Monte Carlo game simulation draws from the fitted strikeout/outs distributions; (2) analytical Negative Binomial / bounded-normal probabilities. Milestone probabilities blend both paths. Sportsbook prices are used only for edge display, not to create the baseball forecast.")
    st.markdown("### Current model outputs")
    st.dataframe(kdf[["Line","Probability","Simulation","Math","Fair Odds"]].assign(Probability=lambda x:x.Probability.map(lambda v:f"{v:.1%}"),Simulation=lambda x:x.Simulation.map(lambda v:f"{v:.1%}"),Math=lambda x:x.Math.map(lambda v:f"{v:.1%}")),use_container_width=True,hide_index=True)
    st.stop()
elif nav=="Bet Tracker":
    st.markdown('<div class="section-head">BET TRACKER</div>',unsafe_allow_html=True)
    st.caption("Current pitcher markets available from the Odds API are shown here when posted.")
    if odds_err:st.info(odds_err)
    if odds_rows:st.dataframe(pd.DataFrame(odds_rows),use_container_width=True,hide_index=True)
    else:st.info("No live player-prop markets are currently available for this game.")
    st.stop()
elif nav=="Projection History":
    st.markdown('<div class="section-head">PROJECTION HISTORY</div>',unsafe_allow_html=True)
    history=st.session_state.get("projection_history",[])
    current={"Date":selected_date.isoformat(),"Pitcher":game.pitcher_name,"Matchup":f"{game.team} vs {game.opponent}","Projected K":round(proj.mean_k,2),"3+":f"{kdf.iloc[0].Probability:.1%}","5+":f"{kdf.iloc[2].Probability:.1%}"}
    if st.button("Save current projection"):
        history.append(current); st.session_state["projection_history"]=history; st.rerun()
    st.dataframe(pd.DataFrame(history) if history else pd.DataFrame([current]),use_container_width=True,hide_index=True)
    st.stop()
elif nav=="Daily Projection Run":
    st.markdown('<div class="section-head">DAILY PROJECTION RUN</div>',unsafe_allow_html=True)
    st.write(f"Slate: {selected_date.isoformat()} · {len(matches)} probable pitcher entries loaded.")
    st.dataframe(pd.DataFrame([{"Pitcher":g.pitcher_name,"Team":g.team,"Opponent":g.opponent,"Status":g.status} for g in matches]),use_container_width=True,hide_index=True)
    st.info("Select a pitcher from the left-rail dropdown to run the full two-path projection for that pitcher.")
    st.stop()

if not locked:st.info("Lock the pitcher in the left rail to freeze all projection outputs for this pitcher.")
st.markdown('<div class="king-title">STRIKEOUT<br><span class="king-red">KING 9000</span></div><div class="subline">★ MLB PITCHER PROJECTION ENGINE ★ TWO-PATH ANALYTICS ★</div>',unsafe_allow_html=True)
st.markdown(f'<div class="pitcher-card"><h2>{game.pitcher_name.upper()}</h2><b>{game.team} vs {game.opponent}</b><br><span class="search-note">{game.venue} · {game.side} · {game.status}</span></div>',unsafe_allow_html=True)
st.markdown('<div class="section-head">PROJECTION SUMMARY</div>',unsafe_allow_html=True)

c1,c2,c3,c4=st.columns(4)
for col,label,value,sub in [(c1,"PROJECTED STRIKEOUTS",f"{proj.mean_k:.2f}",f"↑ 80% RANGE {int(np.quantile(proj.k_samples,.1))}-{int(np.quantile(proj.k_samples,.9))}"),(c2,"3+ STRIKEOUTS",f"{kdf.iloc[0].Probability:.1%}",f"FAIR {kdf.iloc[0]['Fair Odds']}"),(c3,"PROJECTED OUTS",f"{proj.mean_outs:.2f}",f"↑ 80% RANGE {int(np.quantile(proj.outs_samples,.1))}-{int(np.quantile(proj.outs_samples,.9))}"),(c4,"5+ STRIKEOUTS",f"{kdf.iloc[2].Probability:.1%}",f"FAIR {kdf.iloc[2]['Fair Odds']}")]:
    with col:st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><span class="badge">{sub}</span></div>',unsafe_allow_html=True)

left,right=st.columns([1.35,1])
with left:
    st.markdown('<div class="section-head">STRIKEOUT MILESTONE LADDER</div>',unsafe_allow_html=True)
    view=kdf[["Line","Probability","Fair Odds","Simulation","Math"]].copy(); view["Probability"]=view["Probability"].map(lambda x:f"{x:.1%}"); view["Simulation"]=view["Simulation"].map(lambda x:f"{x:.1%}"); view["Math"]=view["Math"].map(lambda x:f"{x:.1%}")
    st.dataframe(view,use_container_width=True,hide_index=True); st.caption("Each X+ probability blends the Monte Carlo path with the analytical distribution path. This is a model estimate, not a guarantee.")
with right:
    st.markdown('<div class="section-head">MARKET ODDS / EDGE</div>',unsafe_allow_html=True)
    if odds_err:st.caption(odds_err)
    if odds_rows:
        rows=[]
        for r in odds_rows:
            if r["market"]!="pitcher_strikeouts_alternate":continue
            line=float(r["point"] or 0); match=kdf[kdf.Line==f"{int(line)}+"]
            if match.empty:continue
            p=float(match.iloc[0].Probability); price=float(r["price"]); implied=(100/(price+100)) if price>0 else (-price)/(-price+100)
            rows.append({"Book":r["book"],"Line":r["point"],"Price":r["price"],"Model":p,"Implied":implied,"Edge":p-implied})
        if rows:
            mdf=pd.DataFrame(rows)
            for c in ("Model","Implied","Edge"):mdf[c]=mdf[c].map(lambda x:f"{x:.1%}")
            st.dataframe(mdf,use_container_width=True,hide_index=True)
        else:st.info("No matching alternate strikeout markets returned yet.")
    else:st.info("Live market data will populate here when the API returns the pitcher props.")

st.markdown(f'<div class="search-note">Data status: {proj.confidence} confidence · quality {proj.quality}/100 · locked: {locked} · engine v{APP_VERSION}</div>',unsafe_allow_html=True)
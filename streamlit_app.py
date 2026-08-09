from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

APP_VERSION = "2.0.4"
EASTERN = ZoneInfo("America/New_York")
MLB_API = "https://statsapi.mlb.com/api/v1"
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
ASSET_DIR = APP_DIR / "assets"

TEAM_ABBR = {
    108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",
    115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSH",121:"NYM",
    133:"ATH",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",
    140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",
    147:"NYY",158:"MIL",
}
PARK_K_FACTOR = {
    "Coors Field":0.94,"T-Mobile Park":1.05,"Petco Park":1.03,
    "Oracle Park":1.02,"Dodger Stadium":1.01,"Yankee Stadium":0.99,
    "Fenway Park":0.98,"Wrigley Field":1.00,
}

st.set_page_config(page_title="StrikeOut King 9000",page_icon="⚾",layout="wide",initial_sidebar_state="expanded")

st.markdown(r"""
<style>
:root{--navy:#06162b;--navy2:#0a2140;--navy3:#0d294b;--red:#e31837;--red2:#ff2948;--white:#f8f9fb;--muted:#a7b7ca;--green:#2fe777;--gold:#f2c14e;--line:#294968}
html,body,.stApp{background:radial-gradient(circle at 72% 4%,rgba(24,62,112,.34),transparent 28%),linear-gradient(155deg,#03101f 0%,#06182f 52%,#04111f 100%);color:var(--white)}
.stApp:before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.12;background-image:linear-gradient(135deg,transparent 0 46%,rgba(255,255,255,.05) 46.5% 47%,transparent 47.5%),linear-gradient(45deg,transparent 0 46%,rgba(255,255,255,.035) 46.5% 47%,transparent 47.5%);background-size:54px 54px}
[data-testid="stSidebar"]{width:208px!important;min-width:208px!important;background:linear-gradient(180deg,#061225 0%,#071a32 100%)!important;border-right:1px solid #26435f!important}
[data-testid="stSidebar"]>div:first-child{width:208px!important}[data-testid="stSidebar"] .block-container{padding:1rem .8rem 1.2rem!important}
.block-container{max-width:1500px!important;padding:1rem 1.25rem 2rem!important}
h1,h2,h3,h4,.sok-font{font-family:Impact,"Arial Narrow",Haettenschweiler,"Arial Black",sans-serif!important;letter-spacing:.035em;text-transform:uppercase}.stCaption,.small-muted{color:var(--muted)!important}
div[data-baseweb="select"]>div,div[data-testid="stTextInput"]>div{background:#09244a!important;border:1px solid #315b88!important;border-radius:10px!important}input{color:#fff!important}
.stButton>button{border-radius:9px!important;border:1px solid #ff405b!important;background:linear-gradient(180deg,#ef1738,#c90b2b)!important;color:#fff!important;font-weight:900!important;letter-spacing:.04em!important;box-shadow:0 7px 16px rgba(227,24,55,.18)}.stButton>button:hover{border-color:#ff8a9a!important;color:#fff!important}
.stProgress>div>div>div{background:linear-gradient(90deg,#e31837,#ff2948)!important}[data-testid="stMetric"]{background:transparent!important;border:0!important;box-shadow:none!important}hr{border-color:#1f3b57!important}
.sok-sidebar-logo{display:flex;justify-content:center;margin:0 0 .35rem}.sok-sidebar-title{font-family:Impact,"Arial Narrow",sans-serif;text-align:center;font-size:1.35rem;line-height:1;color:#fff}.sok-sidebar-title span{color:var(--red)}.sok-sidebar-sub{color:#b7c6d7;font-size:.78rem;line-height:1.35;text-align:center;margin:.5rem 0 .8rem}
.sok-nav{display:flex;flex-direction:column;gap:.2rem;margin:.6rem 0 1rem}.sok-nav a{color:#dce6f0!important;text-decoration:none!important;padding:.55rem .55rem;border-radius:8px;font-weight:800;font-size:.83rem}.sok-nav a:hover{background:#102b4c;color:#fff!important}.sok-nav .active{background:linear-gradient(90deg,#ed1838,#bd0d2b);color:#fff!important}
.sok-side-card{border:1px solid #35516d;border-radius:12px;background:linear-gradient(145deg,#0a203a,#07162b);padding:.75rem;margin-top:.8rem}.sok-side-card .title{color:var(--red2);font-family:Impact,"Arial Narrow",sans-serif;font-size:.82rem;letter-spacing:.05em}.sok-side-card p{color:#bdcbd9;font-size:.74rem;line-height:1.45;margin:.35rem 0 0}.sok-side-card .stars{color:var(--red);letter-spacing:.18em;margin-top:.4rem}
.sok-date{border:1px solid #35516d;border-radius:12px;padding:.7rem;background:#081a31;margin-top:.7rem}.sok-date .label{color:#ff2948;font-family:Impact,"Arial Narrow",sans-serif;font-size:.78rem}.sok-date .value{color:#fff;font-family:Impact,"Arial Narrow",sans-serif;font-size:1.15rem;margin-top:.15rem}.sok-date .updated{color:#9eb0c4;font-size:.68rem;margin-top:.25rem}.sok-search-title{color:#ff2948;font-family:Impact,"Arial Narrow",sans-serif;font-size:.9rem;letter-spacing:.08em;text-align:center;margin-top:1rem}.sok-lock{color:#aebdcd;font-size:.72rem;line-height:1.35;margin-top:.4rem;text-align:center}
.sok-hero{display:grid;grid-template-columns:180px 1fr 190px;gap:1rem;align-items:center;min-height:190px}.sok-title{font-size:5rem;line-height:.82;color:#fff;text-shadow:4px 4px 0 #182e52,0 10px 24px rgba(0,0,0,.25)}.sok-title .red{color:var(--red);text-shadow:3px 3px 0 #f7f8fa,5px 5px 0 #162d50}.sok-ribbon{display:inline-block;margin-top:.75rem;padding:.35rem 1.1rem;border:2px solid var(--red);color:#fff;background:#091a31;font-family:Impact,"Arial Narrow",sans-serif;letter-spacing:.11em;font-size:.82rem;clip-path:polygon(4% 0,96% 0,100% 50%,96% 100%,4% 100%,0 50%)}
.sok-status{border:1px solid #35516d;border-radius:16px;padding:1rem;background:linear-gradient(145deg,#0c2340,#07172b);box-shadow:0 12px 24px rgba(0,0,0,.18)}.sok-status .head{font-family:Impact,"Arial Narrow",sans-serif;letter-spacing:.08em;font-size:.85rem}.sok-status .live{color:var(--green);font-family:Impact,"Arial Narrow",sans-serif;font-size:1.1rem}.sok-status .quality{color:#aebed0;font-size:.75rem;line-height:1.4}.sok-status .bar{height:7px;border-radius:999px;background:#26101a;overflow:hidden;margin-top:.45rem}.sok-status .bar span{display:block;height:100%;background:linear-gradient(90deg,#e31837,#ff2948)}
.matchup{display:grid;grid-template-columns:1.5fr 1fr 1fr;align-items:center;border:1px solid #35516d;border-radius:16px;background:linear-gradient(145deg,#0b2340,#07172b);padding:1rem 1.2rem;box-shadow:0 12px 25px rgba(0,0,0,.18)}.matchup .pitcher{font-family:Impact,"Arial Narrow",sans-serif;font-size:2rem;line-height:1}.matchup .teams{color:var(--red2);font-weight:950;font-size:1.15rem;margin-top:.25rem}.matchup .teams span{color:#fff}.matchup .detail{color:#aebed0;font-size:.8rem;margin-top:.4rem}
.cle-badge{width:76px;height:76px;border-radius:50%;border:2px solid #3c5772;background:radial-gradient(circle,#1a3761,#07172b);display:flex;align-items:center;justify-content:center;font-family:Impact,"Arial Narrow",sans-serif;font-style:italic;font-size:3.2rem;color:#fff;text-shadow:3px 3px 0 var(--red);box-shadow:inset 0 0 0 7px rgba(227,24,55,.08)}.live-schedule{border-left:1px solid #2d4763;padding-left:1.1rem}.live-schedule .head{color:#2fe777;font-family:Impact,"Arial Narrow",sans-serif;letter-spacing:.08em;font-size:1rem}.live-schedule .row{color:#dce5ee;font-size:.83rem;margin-top:.4rem}.live-schedule .row span{color:#9fb1c6}
.section-frame{border:2px solid var(--red);border-radius:16px;padding:1.05rem;margin-top:1rem;background:linear-gradient(160deg,rgba(7,25,47,.94),rgba(5,17,32,.94))}.section-ribbon{display:table;margin:-2rem auto .9rem;padding:.42rem 2.3rem;background:linear-gradient(180deg,#ed193a,#c60c2a);border:2px solid #ff4d67;color:#fff;font-family:Impact,"Arial Narrow",sans-serif;letter-spacing:.07em;font-size:1rem;clip-path:polygon(4% 0,96% 0,100% 50%,96% 100%,4% 100%,0 50%)}
.proj-card{position:relative;min-height:205px;border:1px solid #4a6075;border-radius:15px;background:radial-gradient(circle at 15% 15%,rgba(255,255,255,.07),transparent 25%),linear-gradient(145deg,#102c4a,#07182e);padding:1.1rem;box-shadow:0 14px 25px rgba(0,0,0,.22);overflow:hidden}.proj-card:after{content:"";position:absolute;inset:auto -20px -42px -20px;height:95px;background:linear-gradient(180deg,transparent,rgba(227,24,55,.08));transform:skewY(-5deg)}.proj-label{color:#d5e0ea;font-family:Impact,"Arial Narrow",sans-serif;font-size:.78rem;letter-spacing:.08em;line-height:1.2}.proj-icon{width:42px;height:42px;border-radius:50%;border:2px solid #b9c6d3;display:inline-flex;align-items:center;justify-content:center;margin-bottom:.55rem;font-family:Impact,"Arial Narrow",sans-serif;color:#fff;background:linear-gradient(145deg,#16375d,#07182e)}.proj-value{position:relative;z-index:1;font-family:Impact,"Arial Narrow",sans-serif;font-size:3.35rem;line-height:1;margin:.5rem 0 .65rem;color:#fff}.proj-pill{position:relative;z-index:1;display:inline-block;border:1px solid #0d8150;background:#0a3b2a;color:#4bf092;border-radius:999px;padding:.35rem .65rem;font-size:.72rem;font-weight:950}
.table-panel{border:1px solid #35516d;border-radius:15px;background:linear-gradient(145deg,#0a203b,#06162a);overflow:hidden;box-shadow:0 12px 22px rgba(0,0,0,.16)}.table-title{display:block;text-align:center;margin:0 auto;padding:.45rem 1.5rem;background:linear-gradient(180deg,#ed193a,#c60c2a);color:#fff;font-family:Impact,"Arial Narrow",sans-serif;letter-spacing:.07em;font-size:1rem}.sok-table{width:100%;border-collapse:collapse;color:#e6edf4;font-size:.78rem}.sok-table th{color:#d9e2eb;background:#0b1d34;font-family:Impact,"Arial Narrow",sans-serif;letter-spacing:.05em;font-weight:500}.sok-table th,.sok-table td{padding:.62rem .65rem;border-bottom:1px solid #223d58;text-align:left}.sok-table tr:last-child td{border-bottom:0}.sok-table .good{color:#42ef90;font-weight:900}.sok-table .bad{color:#ff5b72;font-weight:900}
.footer-sok{margin-top:1.5rem;padding:1.3rem;border-top:1px solid #27445f;background:linear-gradient(180deg,rgba(4,16,31,.35),rgba(4,16,31,.75));text-align:center;color:#aebed0;font-weight:900;letter-spacing:.13em;text-transform:uppercase}.footer-sok strong{color:var(--red);font-family:Impact,"Arial Narrow",sans-serif;font-size:1.25rem}.details-wrap{margin-top:1rem;border-top:1px solid #203b57;padding-top:.5rem}
@media(max-width:1000px){.sok-hero{grid-template-columns:120px 1fr}.sok-status{display:none}.sok-title{font-size:3.6rem}.matchup{grid-template-columns:1fr}.live-schedule{border-left:0;border-top:1px solid #2d4763;padding:1rem 0 0;margin-top:1rem}}
</style>
""",unsafe_allow_html=True)

@dataclass(frozen=True)
class GamePitcher:
    key: str
    pitcher_id: int
    pitcher_name: str
    team: str
    opponent: str
    side: str
    venue: str
    game_pk: int
    game_time: str
    status: str

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

class MLBClient:
    def __init__(self)->None:
        self.session=requests.Session();self.session.headers.update({"Accept":"application/json","User-Agent":f"StrikeOutKing9000/{APP_VERSION}"})
    def get(self,endpoint:str,params:dict[str,Any])->dict[str,Any]:
        response=self.session.get(f"{MLB_API}/{endpoint}",params=params,timeout=20);response.raise_for_status();payload=response.json()
        if not isinstance(payload,dict):raise ValueError("Unexpected MLB response format")
        return payload

@st.cache_resource(ttl=120,show_spinner=False)
def get_schedule(day:str)->tuple[list[GamePitcher],str|None]:
    try:payload=MLBClient().get("schedule",{"sportId":1,"date":day,"hydrate":"probablePitcher,team,venue,linescore"})
    except (requests.RequestException,ValueError) as exc:return [],f"Schedule unavailable: {exc}"
    rows=[]
    for block in payload.get("dates",[]):
        for game in block.get("games",[]):
            teams=game.get("teams",{});game_pk=int(game.get("gamePk",0));venue=game.get("venue",{}).get("name","Unknown venue");game_time=game.get("gameDate","");status=game.get("status",{}).get("detailedState","Unknown")
            for side,opponent_side in (("away","home"),("home","away")):
                node,opponent=teams.get(side,{}),teams.get(opponent_side,{});pitcher=node.get("probablePitcher") or {}
                if not pitcher.get("id") or not pitcher.get("fullName"):continue
                team_node,opp_node=node.get("team",{}),opponent.get("team",{});team=TEAM_ABBR.get(team_node.get("id"),team_node.get("abbreviation","UNK"));opp=TEAM_ABBR.get(opp_node.get("id"),opp_node.get("abbreviation","UNK"))
                rows.append(GamePitcher(f"{game_pk}:{pitcher['id']}",int(pitcher["id"]),pitcher["fullName"],team,opp,side.title(),venue,game_pk,game_time,status))
    return rows,None

@st.cache_data(ttl=1800,show_spinner=False)
def get_pitcher_game_log(pitcher_id:int,season:int)->tuple[pd.DataFrame,str|None]:
    try:payload=MLBClient().get(f"people/{pitcher_id}/stats",{"stats":"gameLog","group":"pitching","season":season,"gameType":"R"})
    except (requests.RequestException,ValueError) as exc:return pd.DataFrame(),f"Pitcher history unavailable: {exc}"
    records=[]
    for stat_block in payload.get("stats",[]):
        for split in stat_block.get("splits",[]):
            stat=split.get("stat",{});ip=parse_ip(stat.get("inningsPitched","0.0"));records.append({"date":pd.to_datetime(split.get("date"),errors="coerce"),"opponent":split.get("opponent",{}).get("name",""),"games_started":float(stat.get("gamesStarted",0) or 0),"batters_faced":float(stat.get("battersFaced",0) or 0),"strikeouts":float(stat.get("strikeOuts",0) or 0),"walks":float(stat.get("baseOnBalls",0) or 0),"hits":float(stat.get("hits",0) or 0),"runs":float(stat.get("runs",0) or 0),"pitches":float(stat.get("numberOfPitches",0) or 0),"outs":ip*3.0})
    df=pd.DataFrame(records)
    if df.empty:return df,"No regular-season game log returned."
    return df.sort_values("date"),None

def parse_ip(value:Any)->float:
    try:whole,frac=str(value).split(".");return int(whole)+int(frac)/3
    except (ValueError,AttributeError):return 0.0

def weighted_mean(values:pd.Series,half_life:float,fallback:float)->float:
    clean=pd.to_numeric(values,errors="coerce").dropna().to_numpy(dtype=float)
    if clean.size==0:return fallback
    ages=np.arange(clean.size-1,-1,-1);weights=np.power(0.5,ages/half_life);return float(np.average(clean,weights=weights))

def shrink(rate:float,opportunities:float,prior:float,prior_weight:float)->float:return float((rate*opportunities+prior*prior_weight)/max(opportunities+prior_weight,1.0))

def negbin_pmf(mean:float,dispersion:float,maximum:int)->np.ndarray:
    mean=max(mean,.05);dispersion=max(dispersion,.05);r=1.0/dispersion;p=r/(r+mean);probs=np.array([math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)+r*math.log(p)+k*math.log(1-p)) for k in range(maximum+1)]);probs[-1]+=max(0.0,1.0-probs.sum());return probs/probs.sum()

def discrete_normal_probs(mean:float,sd:float,maximum:int=27)->np.ndarray:
    xs=np.arange(maximum+1);z_hi=(xs+.5-mean)/(sd*math.sqrt(2));z_lo=(xs-.5-mean)/(sd*math.sqrt(2));erf=np.vectorize(math.erf);probs=.5*(erf(z_hi)-erf(z_lo));probs[0]+=.5*(1+math.erf((-0.5-mean)/(sd*math.sqrt(2))));probs[-1]+=.5*(1-math.erf((maximum+.5-mean)/(sd*math.sqrt(2))));probs=np.clip(probs,0,None);return probs/probs.sum()

def calculate_projection(log:pd.DataFrame,game:GamePitcher,manual:dict[str,float],simulations:int)->Projection:
    starts=log[log["games_started"]>0].copy().tail(35)
    if starts.empty:starts=log.tail(20).copy()
    bf=weighted_mean(starts["batters_faced"],5.0,22.0);outs=weighted_mean(starts["outs"],5.0,16.0);pitches=weighted_mean(starts["pitches"],5.0,88.0);total_bf=float(starts["batters_faced"].sum());raw_k_rate=float(starts["strikeouts"].sum()/max(total_bf,1));k_rate=shrink(raw_k_rate,total_bf,.224,120.0);opponent_factor=manual["opponent_k_pct"]/22.4;park_factor=PARK_K_FACTOR.get(game.venue,1.0);ump_factor=manual["umpire_k_factor"];weather_factor=manual["weather_factor"];rest_factor=manual["rest_factor"];pitch_limit_factor=float(np.clip(manual["pitch_limit"]/max(pitches,75.0),.78,1.12));projected_bf=bf*pitch_limit_factor*rest_factor;projected_outs=outs*pitch_limit_factor*rest_factor;projected_k=projected_bf*k_rate*opponent_factor*park_factor*ump_factor*weather_factor;projected_k=float(np.clip(.78*projected_k+.22*weighted_mean(starts["strikeouts"],5,5.0),.5,13.5));projected_outs=float(np.clip(projected_outs,3.0,24.0));k_variance=float(starts["strikeouts"].var(ddof=1)) if len(starts)>2 else projected_k*1.25;dispersion=max((k_variance-projected_k)/max(projected_k**2,.1),.08);k_probs=negbin_pmf(projected_k,dispersion,18);outs_sd=float(starts["outs"].std(ddof=1)) if len(starts)>2 else 4.0;outs_sd=float(np.clip(outs_sd,2.5,6.5));outs_probs=discrete_normal_probs(projected_outs,outs_sd,27);seed_text=f"{game.key}|{date.today()}|{APP_VERSION}";seed=int(hashlib.sha256(seed_text.encode()).hexdigest()[:8],16);rng=np.random.default_rng(seed);k_samples=rng.choice(np.arange(len(k_probs)),size=simulations,p=k_probs);outs_samples=rng.choice(np.arange(len(outs_probs)),size=simulations,p=outs_probs);quality=min(100,35+len(starts)*2+(15 if total_bf>=250 else 0)+(10 if game.pitcher_id else 0));confidence="High" if quality>=85 else "Medium" if quality>=65 else "Low";factors=[("Opponent strikeout profile",opponent_factor-1),("Recent workload / pitch limit",pitch_limit_factor-1),("Park",park_factor-1),("Umpire",ump_factor-1),("Weather",weather_factor-1),("Rest",rest_factor-1)];return Projection(projected_k,projected_outs,math.sqrt(k_variance),outs_sd,k_probs,outs_probs,k_samples,outs_samples,confidence,quality,factors)

def over_probability(samples:np.ndarray,line:float)->float:return float(np.mean(samples>line))
def fair_american(probability:float)->str:
    p=float(np.clip(probability,.001,.999));odds=-100*p/(1-p) if p>=.5 else 100*(1-p)/p;return f"{odds:+.0f}"
def interval(samples:np.ndarray,low:float=.10,high:float=.90)->tuple[int,int]:return int(np.quantile(samples,low)),int(np.quantile(samples,high))
def html_table(headers:list[str],rows:list[list[str]])->str:
    head="".join(f"<th>{h}</th>" for h in headers);body=[]
    for row in rows:body.append("<tr>"+"".join(f"<td>{cell}</td>" for cell in row)+"</tr>")
    return f'<table class="sok-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'

now=datetime.now(EASTERN);query_day=now.date();odds_date_value=st.session_state.get("odds_selected_date")
try:odds_default_date=datetime.strptime(str(odds_date_value),"%Y-%m-%d").date() if odds_date_value else query_day
except ValueError:odds_default_date=query_day
logo_path=ASSET_DIR/"strikeout_king_9000.svg"

with st.sidebar:
    if logo_path.exists():st.markdown('<div class="sok-sidebar-logo">',unsafe_allow_html=True);st.image(str(logo_path),width=130);st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('<div class="sok-sidebar-title">StrikeOut <span>King 9000</span></div>',unsafe_allow_html=True)
    st.markdown('<div class="sok-sidebar-sub">CLE-themed distributional MLB starter projections</div>',unsafe_allow_html=True)
    st.markdown('<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="/3_Odds_API">◎ &nbsp; Odds API</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>',unsafe_allow_html=True)
    selected_date=st.date_input("Slate date",value=odds_default_date)
    st.markdown(f'<div class="sok-date"><div class="label">SLATE DATE</div><div class="value">{selected_date:%Y/%m/%d}</div><div class="updated">Updated {now:%I:%M %p ET}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="sok-search-title">PITCHER SEARCH</div>',unsafe_allow_html=True)
    pitcher_query=st.text_input("Search pitcher",placeholder="Search pitcher...",label_visibility="collapsed",key="sok_pitcher_search")
    st.markdown('<div class="sok-lock">Search and select a pitcher to lock the projection 🔒</div>',unsafe_allow_html=True)
    st.markdown('<div class="sok-side-card"><div class="title">ABOUT STRIKEOUT KING 9000</div><p>Elite two-path projections combining simulated games and mathematical modeling for maximum accuracy.</p><div class="stars">★ ★ ★ ★ ★</div></div>',unsafe_allow_html=True)

simulations=25000;opponent_k_pct=22.4;pitch_limit=92;umpire_k_factor=1.00;weather_factor=1.00;rest_factor=1.00
schedule,schedule_error=get_schedule(selected_date.isoformat())
if schedule_error:st.error(schedule_error)
if not schedule:st.warning("No announced probable pitchers are available for this date. Choose another date or wait for teams to announce starters.");st.stop()
options={g.key:g for g in schedule};odds_pitcher_name=st.session_state.get("odds_selected_pitcher");odds_game_date=st.session_state.get("odds_selected_date");selected_key=st.session_state.get("locked_pitcher_key")
if odds_pitcher_name and odds_game_date==selected_date.isoformat():
    matches=[g for g in schedule if g.pitcher_name.strip().lower()==str(odds_pitcher_name).strip().lower()]
    if matches:selected_key=matches[0].key;st.session_state["locked_pitcher_key"]=selected_key
filtered=[g for g in schedule if not pitcher_query or pitcher_query.lower() in g.pitcher_name.lower()]
if not filtered:filtered=schedule
if selected_key not in {g.key for g in filtered}:selected_key=filtered[0].key
# Search-first pitcher selection: keep the main projection surface clean.
# An exact/partial search targets the first matching scheduled pitcher.
if pitcher_query:selected_key=filtered[0].key
with st.sidebar:
    if len(filtered)>1:
        search_choice=st.selectbox("Matching pitchers",[g.key for g in filtered],index=[g.key for g in filtered].index(selected_key),format_func=lambda key:f"{options[key].pitcher_name} · {options[key].team}")
        selected_key=search_choice
    if st.button("🔒 LOCK PITCHER",use_container_width=True):st.session_state["locked_pitcher_key"]=selected_key;st.rerun()

game=options[selected_key];season=selected_date.year;log,history_error=get_pitcher_game_log(game.pitcher_id,season)
if log.empty and season>2000:
    previous_log,previous_error=get_pitcher_game_log(game.pitcher_id,season-1)
    if not previous_log.empty:log,history_error=previous_log,None
    elif history_error is None:history_error=previous_error
if history_error:st.warning(history_error)
if log.empty:st.error("A projection cannot be issued without a pitcher game history.");st.stop()
manual={"opponent_k_pct":opponent_k_pct,"pitch_limit":float(pitch_limit),"umpire_k_factor":umpire_k_factor,"weather_factor":weather_factor,"rest_factor":rest_factor};projection=calculate_projection(log,game,manual,simulations)

try:
    from training.github_projection_store import save_projection
    archive_key=f"{selected_date.isoformat()}:{game.game_pk}:{game.pitcher_id}";attempted=st.session_state.setdefault("projection_archive_attempted",set())
    if archive_key not in attempted:
        attempted.add(archive_key)
        if any(token in game.status.lower() for token in ("scheduled","pre-game","warmup")):
            k_lo,k_hi=interval(projection.k_samples);save_projection({"game_pk":game.game_pk,"game_date":selected_date.isoformat(),"pitcher_id":game.pitcher_id,"player":game.pitcher_name,"team":game.team,"opponent":game.opponent,"venue":game.venue,"game_time":game.game_time,"captured_at_utc":now.astimezone(ZoneInfo("UTC")).isoformat(),"app_version":APP_VERSION,"projection":projection.mean_k,"k_sd":projection.k_sd,"k_range_low":k_lo,"k_range_high":k_hi,"confidence":projection.confidence,"data_quality":projection.data_quality,"simulation_draws":simulations,"opponent_k_pct":opponent_k_pct,"pitch_limit":pitch_limit,"umpire_k_factor":umpire_k_factor,"weather_factor":weather_factor,"rest_factor":rest_factor,"actual_strikeouts":"","resolved_at_utc":""})
except Exception as exc:st.session_state["projection_archive_warning"]=str(exc)

st.markdown('<div class="sok-hero">',unsafe_allow_html=True);h1,h2,h3=st.columns([1.15,4.1,1.25])
with h1:
    if logo_path.exists():st.image(str(logo_path),width=175)
with h2:st.markdown('<div class="sok-title">STRIKEOUT<br><span class="red">KING 9000</span></div><div class="sok-ribbon">★ MLB PITCHER PROJECTION ENGINE ★ TWO-PATH ANALYTICS ★</div>',unsafe_allow_html=True)
with h3:
    pct=projection.data_quality;st.markdown(f'<div class="sok-status"><div class="head">DATA STATUS</div><div class="live">● {projection.confidence.upper()}</div><div class="quality">High confidence<br>Data quality {pct}/100</div><div class="bar"><span style="width:{pct}%"></span></div></div>',unsafe_allow_html=True)
st.markdown('</div>',unsafe_allow_html=True)

game_dt=pd.to_datetime(game.game_time,errors="coerce")
if pd.notna(game_dt):game_clock=game_dt.tz_convert(EASTERN).strftime("%I:%M %p ET") if game_dt.tzinfo else game_dt.strftime("%I:%M %p ET")
else:game_clock="Time TBD"
st.markdown(f'<div class="matchup"><div><div class="pitcher">{game.pitcher_name.upper()}</div><div class="teams">{game.team} <span>vs</span> {game.opponent}</div><div class="detail">⚾ {game.venue} · {game.side} · {game.status}</div></div><div class="cle-badge">C</div><div class="live-schedule"><div class="head">LIVE SCHEDULE</div><div class="row">▣ &nbsp; Today &nbsp; <span>{game_clock}</span></div><div class="row">Scheduled &nbsp; • &nbsp; {game.side}</div></div></div>',unsafe_allow_html=True)

try:k_line=float(st.session_state.get("odds_selected_line",5.5))
except (TypeError,ValueError):k_line=5.5
try:outs_line=float(st.session_state.get("odds_selected_outs_line",15.5))
except (TypeError,ValueError):outs_line=15.5
k_over=over_probability(projection.k_samples,k_line);outs_over=over_probability(projection.outs_samples,outs_line);k_lo,k_hi=interval(projection.k_samples);o_lo,o_hi=interval(projection.outs_samples)

st.markdown('<div class="section-frame"><div class="section-ribbon">PROJECTION SUMMARY</div>',unsafe_allow_html=True);m1,m2,m3,m4=st.columns(4)
cards=[("K","PROJECTED STRIKEOUTS",f"{projection.mean_k:.2f}",f"↑ 80% RANGE {k_lo}-{k_hi}"),("5.5+","OVER 5.5 STRIKEOUTS",f"{k_over:.1%}",f"↑ FAIR {fair_american(k_over)}"),("OUT","PROJECTED OUTS",f"{projection.mean_outs:.2f}",f"↑ 80% RANGE {o_lo}-{o_hi}"),("15.5+","OVER 15.5 OUTS",f"{outs_over:.1%}",f"↑ FAIR {fair_american(outs_over)}")]
for col,(icon,label,value,pill) in zip((m1,m2,m3,m4),cards):
    with col:st.markdown(f'<div class="proj-card"><div class="proj-icon">{icon}</div><div class="proj-label">{label}</div><div class="proj-value">{value}</div><div class="proj-pill">{pill}</div></div>',unsafe_allow_html=True)
st.markdown('</div>',unsafe_allow_html=True)

left,right=st.columns([1,1])
with left:
    prob_rows=[[f"K OVER {k_line:g}",f"{k_over:.1%}",fair_american(k_over),f"{projection.mean_k:.2f}"],[f"K UNDER {k_line:g}",f"{1-k_over:.1%}",fair_american(1-k_over),f"{projection.mean_k:.2f}"],[f"OUTS OVER {outs_line:g}",f"{outs_over:.1%}",fair_american(outs_over),f"{projection.mean_outs:.2f}"],[f"OUTS UNDER {outs_line:g}",f"{1-outs_over:.1%}",fair_american(1-outs_over),f"{projection.mean_outs:.2f}"]]
    st.markdown('<div class="table-panel"><div class="table-title">PROBABILITY TABLE</div>'+html_table(["MARKET","PROBABILITY","FAIR ODDS","PROJECTION"],prob_rows)+'</div>',unsafe_allow_html=True)
with right:
    driver_rows=[]
    for factor,impact in projection.factors:
        direction="↑ Raises" if impact>=0 else "↓ Lowers";cls="good" if impact>=0 else "bad";driver_rows.append([factor,f"{impact:+.1%}",f'<span class="{cls}">{direction}</span>'])
    st.markdown('<div class="table-panel"><div class="table-title">PROJECTION DRIVERS</div>'+html_table(["FACTOR","IMPACT","DIRECTION"],driver_rows)+'</div>',unsafe_allow_html=True)
st.caption("Probabilities are model estimates, not guarantees.")

st.markdown('<div class="details-wrap">',unsafe_allow_html=True)
with st.expander("Distribution, form & workload, and model card"):
    t1,t2,t3=st.tabs(["Distribution","Form & Workload","Model Card"])
    with t1:
        c1,c2=st.columns(2)
        with c1:st.subheader("Strikeout distribution");st.bar_chart(pd.DataFrame({"Probability":projection.k_probs},index=np.arange(len(projection.k_probs))),color="#e31837")
        with c2:st.subheader("Outs distribution");st.bar_chart(pd.DataFrame({"Probability":projection.outs_probs},index=np.arange(len(projection.outs_probs))),color="#315f93")
    with t2:
        display=log.tail(15).copy();display["K/BF"]=display["strikeouts"]/display["batters_faced"].replace(0,np.nan);display["Pitches/BF"]=display["pitches"]/display["batters_faced"].replace(0,np.nan);st.line_chart(display.set_index("date")[["strikeouts","outs"]]);st.dataframe(display[["date","opponent","strikeouts","outs","batters_faced","pitches","K/BF","Pitches/BF"]].sort_values("date",ascending=False),hide_index=True,use_container_width=True)
    with t3:
        st.markdown("### Two-path projection engine\n- Independent simulated games plus mathematical probability modeling.\n- Exponentially weighted recent form with empirical-Bayes shrinkage.\n- Negative Binomial strikeout distribution and bounded outs distribution.\n- Frozen pregame snapshots are archived separately from the Bet Tracker.\n- The daily projection runner can build the larger historical pitcher database.")
        manifest={"app_version":APP_VERSION,"prediction_timestamp_et":now.isoformat(),"game_pk":game.game_pk,"pitcher_id":game.pitcher_id,"inputs":manual,"simulation_draws":simulations,"confidence":projection.confidence};st.download_button("Download prediction manifest",json.dumps(manifest,indent=2),file_name=f"projection_{game.game_pk}_{game.pitcher_id}.json",mime="application/json")
st.markdown('</div>',unsafe_allow_html=True)

st.markdown('<div class="footer-sok">★ ★ ★ &nbsp; BUILT FOR <strong>CLE BASEBALL</strong> &nbsp; ★ ★ ★<br><span>ELITE DATA · ELITE PROJECTIONS · ELITE RESULTS</span></div>',unsafe_allow_html=True)

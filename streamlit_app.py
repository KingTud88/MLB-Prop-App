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

APP_VERSION = "2.0.3"
EASTERN = ZoneInfo("America/New_York")
MLB_API = "https://statsapi.mlb.com/api/v1"
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"

TEAM_ABBR = {
    108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",
    115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSH",121:"NYM",
    133:"ATH",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",
    140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",
    147:"NYY",158:"MIL"
}
PARK_K_FACTOR = {
    "Coors Field":0.94,"T-Mobile Park":1.05,"Petco Park":1.03,
    "Oracle Park":1.02,"Dodger Stadium":1.01,"Yankee Stadium":0.99,
    "Fenway Park":0.98,"Wrigley Field":1.00
}

st.set_page_config(page_title="StrikeOut King 9000", page_icon="⚾", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root{--navy:#06152d;--navy2:#0a2143;--panel:#0b1c35;--panel2:#102743;--red:#e31837;--red2:#ff334d;--white:#f7f8fa;--muted:#9fb1c7;--green:#34e27a;--line:#27425f}
.stApp{background:radial-gradient(circle at 72% 0%,rgba(25,65,120,.28),transparent 34%),linear-gradient(150deg,#04101f 0%,#07172d 55%,#05111f 100%);color:var(--white)}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#061225,#081a33);border-right:1px solid #183657}
[data-testid="stSidebar"] .block-container{padding-top:1rem}
.block-container{max-width:1540px;padding-top:1.2rem}
h1,h2,h3,h4{font-family:Impact,"Arial Narrow",Haettenschweiler,sans-serif;letter-spacing:.025em}
h1{font-size:3.2rem!important;text-transform:uppercase}
h2,h3{color:var(--white)}
[data-testid="stMetric"]{background:linear-gradient(155deg,#102b4a,#081a31);border:1px solid #365271;border-radius:18px;padding:18px 18px 14px;box-shadow:0 10px 28px rgba(0,0,0,.22)}
[data-testid="stMetricLabel"]{color:#b8c7d8!important;font-weight:800}
[data-testid="stMetricValue"]{font-family:Impact,"Arial Narrow",sans-serif;font-size:2.35rem!important}
.stButton>button{border-radius:10px;border:1px solid #ef2945;background:linear-gradient(180deg,#f0223f,#c90f2d);color:white;font-weight:900}
.stButton>button:hover{border-color:#ff6a7b;color:white}
div[data-baseweb="select"]>div,div[data-testid="stNumberInput"]>div{background:#0d2a55!important;border:1px solid #31537b!important;border-radius:10px!important}
input{color:#fff!important}
.sok-title{font-family:Impact,"Arial Narrow",Haettenschweiler,sans-serif;font-size:4.4rem;line-height:.88;letter-spacing:.02em;text-transform:uppercase;color:#fff;text-shadow:3px 3px 0 #102b50}
.sok-title span{display:block;color:var(--red);text-shadow:3px 3px 0 #fff}
.sok-sub{color:#aabbd0;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.badge{display:inline-block;padding:7px 12px;border-radius:999px;background:#113b2b;color:#5df29a;font-weight:900;letter-spacing:.04em}
.live-dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#31e66f;margin-right:7px}
.game-card{border:1px solid #3a5775;border-radius:18px;padding:18px 22px;background:linear-gradient(145deg,#0c2645,#08182f)}
.section-bar{background:linear-gradient(90deg,#b70e29,#ef1939,#b70e29);color:#fff;text-align:center;font-family:Impact,"Arial Narrow",sans-serif;letter-spacing:.08em;text-transform:uppercase;padding:7px 16px;border-radius:10px;margin:8px auto 14px;max-width:360px}
.projection-card{background:linear-gradient(160deg,#102b49,#08192f);border:1px solid #42617f;border-radius:20px;padding:20px;min-height:180px;box-shadow:0 12px 25px rgba(0,0,0,.2)}
.projection-card .label{font-weight:900;color:#c8d5e3;text-transform:uppercase;font-size:.82rem;letter-spacing:.06em}
.projection-card .value{font-family:Impact,"Arial Narrow",sans-serif;font-size:3rem;margin:12px 0 8px}
.projection-card .pill{display:inline-block;border:1px solid #146b46;background:#0d3d2b;color:#4ee58d;padding:5px 10px;border-radius:999px;font-weight:900;font-size:.78rem}
.table-card{border:1px solid #3b5772;border-radius:18px;padding:12px 16px;background:linear-gradient(150deg,#0b213d,#07172b)}
.locked{color:#58ed93;font-weight:900}
.small-muted{color:var(--muted);font-size:.86rem}
.footer-sok{margin-top:28px;padding:22px;text-align:center;border-top:1px solid #203d5b;color:#b9c8d8;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.footer-sok strong{color:var(--red);font-family:Impact,"Arial Narrow",sans-serif;font-size:1.4rem}
</style>
""", unsafe_allow_html=True)

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
        self.session=requests.Session()
        self.session.headers.update({"Accept":"application/json","User-Agent":f"StrikeOutKing9000/{APP_VERSION}"})
    def get(self,endpoint:str,params:dict[str,Any])->dict[str,Any]:
        response=self.session.get(f"{MLB_API}/{endpoint}",params=params,timeout=20)
        response.raise_for_status()
        payload=response.json()
        if not isinstance(payload,dict): raise ValueError("Unexpected MLB response format")
        return payload

def get_schedule(day:str)->tuple[list[GamePitcher],str|None]:
    try: payload=MLBClient().get("schedule",{"sportId":1,"date":day,"hydrate":"probablePitcher,team,venue,linescore"})
    except (requests.RequestException,ValueError) as exc: return [],f"Schedule unavailable: {exc}"
    rows=[]
    for block in payload.get("dates",[]):
        for game in block.get("games",[]):
            teams=game.get("teams",{});game_pk=int(game.get("gamePk",0));venue=game.get("venue",{}).get("name","Unknown venue");game_time=game.get("gameDate","");status=game.get("status",{}).get("detailedState","Unknown")
            for side,opponent_side in (("away","home"),("home","away")):
                node,opponent=teams.get(side,{}),teams.get(opponent_side,{})
                pitcher=node.get("probablePitcher") or {}
                if not pitcher.get("id") or not pitcher.get("fullName"): continue
                team_node,opp_node=node.get("team",{}),opponent.get("team",{})
                team=TEAM_ABBR.get(team_node.get("id"),team_node.get("abbreviation","UNK"));opp=TEAM_ABBR.get(opp_node.get("id"),opp_node.get("abbreviation","UNK"))
                rows.append(GamePitcher(f"{game_pk}:{pitcher['id']}",int(pitcher["id"]),pitcher["fullName"],team,opp,side.title(),venue,game_pk,game_time,status))
    return rows,None

@st.cache_data(ttl=1800,show_spinner=False)
def get_pitcher_game_log(pitcher_id:int,season:int)->tuple[pd.DataFrame,str|None]:
    try: payload=MLBClient().get(f"people/{pitcher_id}/stats",{"stats":"gameLog","group":"pitching","season":season,"gameType":"R"})
    except (requests.RequestException,ValueError) as exc: return pd.DataFrame(),f"Pitcher history unavailable: {exc}"
    records=[]
    for stat_block in payload.get("stats",[]):
        for split in stat_block.get("splits",[]):
            stat=split.get("stat",{});ip=parse_ip(stat.get("inningsPitched","0.0"))
            records.append({"date":pd.to_datetime(split.get("date"),errors="coerce"),"opponent":split.get("opponent",{}).get("name",""),"games_started":float(stat.get("gamesStarted",0) or 0),"batters_faced":float(stat.get("battersFaced",0) or 0),"strikeouts":float(stat.get("strikeOuts",0) or 0),"walks":float(stat.get("baseOnBalls",0) or 0),"hits":float(stat.get("hits",0) or 0),"runs":float(stat.get("runs",0) or 0),"pitches":float(stat.get("numberOfPitches",0) or 0),"outs":ip*3.0})
    df=pd.DataFrame(records)
    if df.empty:return df,"No regular-season game log returned."
    return df.sort_values("date"),None

def parse_ip(value:Any)->float:
    try: whole,frac=str(value).split(".");return int(whole)+int(frac)/3
    except (ValueError,AttributeError):return 0.0

def weighted_mean(values:pd.Series,half_life:float,fallback:float)->float:
    clean=pd.to_numeric(values,errors="coerce").dropna().to_numpy(dtype=float)
    if clean.size==0:return fallback
    ages=np.arange(clean.size-1,-1,-1);weights=np.power(0.5,ages/half_life);return float(np.average(clean,weights=weights))

def shrink(rate:float,opportunities:float,prior:float,prior_weight:float)->float:return float((rate*opportunities+prior*prior_weight)/max(opportunities+prior_weight,1.0))

def negbin_pmf(mean:float,dispersion:float,maximum:int)->np.ndarray:
    mean=max(mean,.05);dispersion=max(dispersion,.05);r=1.0/dispersion;p=r/(r+mean)
    probs=np.array([math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)+r*math.log(p)+k*math.log(1-p)) for k in range(maximum+1)]);probs[-1]+=max(0.0,1.0-probs.sum());return probs/probs.sum()

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

now=datetime.now(EASTERN);query_day=now.date();odds_date_value=st.session_state.get("odds_selected_date")
try:odds_default_date=datetime.strptime(str(odds_date_value),"%Y-%m-%d").date() if odds_date_value else query_day
except ValueError:odds_default_date=query_day

with st.sidebar:
    logo_path=APP_DIR/"assets"/"strikeout_king_9000.svg"
    if logo_path.exists():st.image(str(logo_path),width=150)
    st.markdown("### StrikeOut King 9000")
    st.caption("CLE-themed distributional MLB starter projections")
    selected_date=st.date_input("Slate date",value=odds_default_date)
    st.markdown("---")
    st.markdown("**PITCHER SEARCH**")
    pitcher_query=st.text_input("Search pitcher",placeholder="Search pitcher...",label_visibility="collapsed")
    st.caption("Search and select a pitcher to lock the projection 🔒")

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
selected_key=st.selectbox("Pitcher",[g.key for g in filtered],index=[g.key for g in filtered].index(selected_key),format_func=lambda key:f"{options[key].pitcher_name} · {options[key].team} vs {options[key].opponent}")
if st.button("🔒 Lock pitcher",use_container_width=True):st.session_state["locked_pitcher_key"]=selected_key;st.rerun()
game=options[selected_key];season=selected_date.year;log,history_error=get_pitcher_game_log(game.pitcher_id,season)
if log.empty and season>2000:
    previous_log,previous_error=get_pitcher_game_log(game.pitcher_id,season-1)
    if not previous_log.empty:log,history_error=previous_log,None
    elif history_error is None:history_error=previous_error
if history_error:st.warning(history_error)
if log.empty:st.error("A projection cannot be issued without a pitcher game history.");st.stop()
manual={"opponent_k_pct":opponent_k_pct,"pitch_limit":float(pitch_limit),"umpire_k_factor":umpire_k_factor,"weather_factor":weather_factor,"rest_factor":rest_factor};projection=calculate_projection(log,game,manual,simulations)

from training.github_projection_store import save_projection
archive_key=f"{selected_date.isoformat()}:{game.game_pk}:{game.pitcher_id}"
if archive_key not in st.session_state.get("projection_archive_attempted",set()):
    st.session_state.setdefault("projection_archive_attempted",set()).add(archive_key)
    if any(token in game.status.lower() for token in ("scheduled","pre-game","warmup")):
        try:
            k_lo,k_hi=interval(projection.k_samples);save_projection({"game_pk":game.game_pk,"game_date":selected_date.isoformat(),"pitcher_id":game.pitcher_id,"player":game.pitcher_name,"team":game.team,"opponent":game.opponent,"venue":game.venue,"game_time":game.game_time,"captured_at_utc":now.astimezone(ZoneInfo("UTC")).isoformat(),"app_version":APP_VERSION,"projection":projection.mean_k,"k_sd":projection.k_sd,"k_range_low":k_lo,"k_range_high":k_hi,"confidence":projection.confidence,"data_quality":projection.data_quality,"simulation_draws":simulations,"opponent_k_pct":opponent_k_pct,"pitch_limit":pitch_limit,"umpire_k_factor":umpire_k_factor,"weather_factor":weather_factor,"rest_factor":rest_factor,"actual_strikeouts":"","resolved_at_utc":""})
        except Exception as exc:st.warning(f"Projection archive unavailable: {exc}")

hero_left,hero_mid,hero_right=st.columns([1.1,3.8,1.2])
with hero_left:
    if logo_path.exists():st.image(str(logo_path),width=180)
with hero_mid:
    st.markdown('<div class="sok-title">STRIKEOUT<span>KING 9000</span></div><div class="sok-sub">MLB PITCHER PROJECTION ENGINE · TWO-PATH ANALYTICS</div>',unsafe_allow_html=True)
with hero_right:
    st.markdown(f'<div class="table-card"><b>DATA STATUS</b><br><span class="live-dot"></span><span class="locked">{projection.confidence.upper()}</span><br><span class="small-muted">Quality {projection.data_quality}/100</span></div>',unsafe_allow_html=True)

st.markdown(f'<div class="game-card"><div style="font-size:1.65rem;font-weight:900">{game.pitcher_name.upper()}</div><div style="color:#ff334d;font-weight:900;font-size:1.2rem">{game.team} <span style="color:white">vs</span> {game.opponent}</div><div class="small-muted">⚾ {game.venue} · {game.side} · {game.status} · Updated {now:%I:%M %p ET}</div></div>',unsafe_allow_html=True)
st.markdown('<span class="badge"><span class="live-dot"></span>LIVE SCHEDULE</span>',unsafe_allow_html=True)
line_col1,line_col2,line_col3=st.columns([1,1,1.5])
with line_col1:k_line=st.number_input("Strikeout line",.5,15.5,5.5,.5)
with line_col2:outs_line=st.number_input("Outs line",.5,26.5,15.5,.5)
with line_col3:st.markdown("#### Model status");st.progress(projection.data_quality/100,text=f"{projection.confidence} confidence · {simulations:,} simulation draws")

k_over=over_probability(projection.k_samples,k_line);outs_over=over_probability(projection.outs_samples,outs_line);k_lo,k_hi=interval(projection.k_samples);o_lo,o_hi=interval(projection.outs_samples)
st.markdown('<div class="section-bar">PROJECTION SUMMARY</div>',unsafe_allow_html=True)
m1,m2,m3,m4=st.columns(4)
for col,(label,value,pill) in zip((m1,m2,m3,m4),[("PROJECTED STRIKEOUTS",f"{projection.mean_k:.2f}",f"↑ 80% RANGE {k_lo}-{k_hi}"),(f"OVER {k_line:g} STRIKEOUTS",f"{k_over:.1%}",f"↑ FAIR {fair_american(k_over)}"),("PROJECTED OUTS",f"{projection.mean_outs:.2f}",f"↑ 80% RANGE {o_lo}-{o_hi}"),(f"OVER {outs_line:g} OUTS",f"{outs_over:.1%}",f"↑ FAIR {fair_american(outs_over)}")]):
    with col:st.markdown(f'<div class="projection-card"><div class="label">{label}</div><div class="value">{value}</div><div class="pill">{pill}</div></div>',unsafe_allow_html=True)

tab1,tab2,tab3,tab4=st.tabs(["Projection","Distribution","Form & Workload","Model Card"])
with tab1:
    st.markdown('<div class="section-bar">PROBABILITY TABLE</div>',unsafe_allow_html=True)
    prob_df=pd.DataFrame([{"Market":f"K OVER {k_line:g}","Probability":k_over,"Fair odds":fair_american(k_over),"Projection":projection.mean_k},{"Market":f"K UNDER {k_line:g}","Probability":1-k_over,"Fair odds":fair_american(1-k_over),"Projection":projection.mean_k},{"Market":f"OUTS OVER {outs_line:g}","Probability":outs_over,"Fair odds":fair_american(outs_over),"Projection":projection.mean_outs},{"Market":f"OUTS UNDER {outs_line:g}","Probability":1-outs_over,"Fair odds":fair_american(1-outs_over),"Projection":projection.mean_outs}])
    st.dataframe(prob_df.style.format({"Probability":"{:.1%}","Projection":"{:.2f}"}),hide_index=True,use_container_width=True);st.caption("Probabilities are model estimates, not guarantees.")
    st.markdown('<div class="section-bar">PROJECTION DRIVERS</div>',unsafe_allow_html=True)
    factor_df=pd.DataFrame(projection.factors,columns=["Factor","Impact"]);factor_df["Direction"]=np.where(factor_df["Impact"]>=0,"↑ Raises","↓ Lowers");factor_df["Impact"]=factor_df["Impact"].map(lambda x:f"{x:+.1%}");st.dataframe(factor_df,hide_index=True,use_container_width=True)
with tab2:
    c1,c2=st.columns(2)
    with c1:st.subheader("Strikeout distribution");st.bar_chart(pd.DataFrame({"Probability":projection.k_probs},index=np.arange(len(projection.k_probs))),color="#e31837")
    with c2:st.subheader("Outs distribution");st.bar_chart(pd.DataFrame({"Probability":projection.outs_probs},index=np.arange(len(projection.outs_probs))),color="#315f93")
with tab3:
    display=log.tail(15).copy();display["K/BF"]=display["strikeouts"]/display["batters_faced"].replace(0,np.nan);display["Pitches/BF"]=display["pitches"]/display["batters_faced"].replace(0,np.nan);st.line_chart(display.set_index("date")[["strikeouts","outs"]]);st.dataframe(display[["date","opponent","strikeouts","outs","batters_faced","pitches","K/BF","Pitches/BF"]].sort_values("date",ascending=False).style.format({"K/BF":"{:.1%}","Pitches/BF":"{:.2f}"}),hide_index=True,use_container_width=True)
with tab4:
    st.markdown("### Two-path projection engine");st.markdown("- Independent game simulation plus mathematical probability modeling.\n- Exponentially weighted recent form with empirical-Bayes shrinkage.\n- Negative Binomial strikeout distribution and bounded outs distribution.\n- Archived pregame snapshots remain separate from the Bet Tracker.\n- Calibration and walk-forward evaluation remain part of the production roadmap.")
    manifest={"app_version":APP_VERSION,"prediction_timestamp_et":now.isoformat(),"game_pk":game.game_pk,"pitcher_id":game.pitcher_id,"inputs":manual,"simulation_draws":simulations,"confidence":projection.confidence};st.download_button("Download prediction manifest",json.dumps(manifest,indent=2),file_name=f"projection_{game.game_pk}_{game.pitcher_id}.json",mime="application/json")

from training.manual_lines import ManualLine,analyze_manual_line,confidence_tier
from training.github_bet_store import save_bet,load_bets
with st.expander("Betting line fallback · sportsbook line"):
    st.caption("Use only when an Odds API line is unavailable. This does not change the projection itself.")
    odds_transfer_active=st.session_state.get("odds_selected_date")==selected_date.isoformat() and st.session_state.get("odds_selected_line") is not None and not st.session_state.get("odds_selection_applied",False)
    if odds_transfer_active:
        st.session_state["manual_side"]=str(st.session_state.get("odds_selected_side","Over"));st.session_state["manual_line"]=float(st.session_state.get("odds_selected_line"));st.session_state["manual_odds"]=int(st.session_state.get("odds_selected_odds",-110));st.session_state["odds_selection_applied"]=True
    b1,b2,b3,b4=st.columns([1.2,1,1,1])
    with b1:manual_side=st.selectbox("Side",["Over","Under"],key="manual_side")
    with b2:manual_line=st.number_input("K line",.5,15.5,float(k_line),.5,key="manual_line")
    with b3:manual_odds=st.number_input("American odds",-500,500,-110,5,key="manual_odds")
    with b4:st.write("");analyze_button=st.button("Analyze line",type="primary",use_container_width=True)
    if analyze_button:
        manual_over=over_probability(projection.k_samples,manual_line);analysis=analyze_manual_line(projection.mean_k,manual_over,manual_line,manual_side,int(manual_odds));st.session_state["pending_manual_bet"]={"analysis":analysis,"record":ManualLine(game.pitcher_name,selected_date.isoformat(),manual_line,manual_side,int(manual_odds))}
    pending=st.session_state.get("pending_manual_bet")
    if pending:
        analysis=pending["analysis"];confidence=confidence_tier(analysis["model_probability"],analysis["edge"]);a1,a2,a3,a4=st.columns(4);a1.metric("Model probability",f"{analysis['model_probability']:.1%}");a2.metric("Sportsbook implied",f"{analysis['implied_probability']:.1%}");a3.metric("Model edge",f"{analysis['edge']:+.1%}");a4.metric("Provisional confidence",confidence);st.info("Confidence is provisional until historical sportsbook lines are available for calibration.")
        if st.button("Save to Bet Tracker",key="save_bet"):
            record={**pending["record"].__dict__,**analysis,"confidence":confidence,"game_pk":game.game_pk,"pitcher_id":game.pitcher_id,"actual_strikeouts":""};save_bet(record);st.session_state.pop("pending_manual_bet",None);st.success("Bet saved to the persistent tracker.")
tracker_rows=load_bets()
if tracker_rows:
    with st.expander("Recent Bet Tracker"):
        tracker=pd.DataFrame(tracker_rows);st.dataframe(tracker.sort_values("entered_at_utc",ascending=False),hide_index=True,use_container_width=True)

st.markdown('<div class="footer-sok">★ ★ ★ &nbsp; BUILT FOR <strong>CLE BASEBALL</strong> &nbsp; ★ ★ ★<br><span class="small-muted">ELITE DATA · ELITE PROJECTIONS · ELITE RESULTS</span></div>',unsafe_allow_html=True)

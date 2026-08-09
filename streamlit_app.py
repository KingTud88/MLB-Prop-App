from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

APP_VERSION = "2.0.2"
EASTERN = ZoneInfo("America/New_York")
MLB_API = "https://statsapi.mlb.com/api/v1"
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
MODEL_DIR = APP_DIR / "models"

TEAM_ABBR = {108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSH",121:"NYM",133:"ATH",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",147:"NYY",158:"MIL"}
PARK_K_FACTOR = {"Coors Field":0.94,"T-Mobile Park":1.05,"Petco Park":1.03,"Oracle Park":1.02,"Dodger Stadium":1.01,"Yankee Stadium":0.99,"Fenway Park":0.98,"Wrigley Field":1.00}

st.set_page_config(page_title="StrikeOut King 9000", page_icon="⚾", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --bg:#071019; --panel:#0d1b2a; --ink:#e8f1f8; --muted:#89a1b3; --cyan:#31d7ff; --green:#31e6a1; --red:#ff5d73; }
.stApp { background:linear-gradient(145deg,#06101a,#0b1723); color:var(--ink); }
[data-testid="stSidebar"] { background:#07131f; border-right:1px solid #173149; }
.block-container { padding-top:1.5rem; max-width:1500px; }
h1,h2,h3 { letter-spacing:-.02em; }
div[data-testid="stMetric"] { background:#0d1b2a; border:1px solid #1b3851; padding:16px; border-radius:14px; }
.status-live {display:inline-block;background:#123c32;color:#65f0bd;padding:5px 10px;border-radius:999px;font-weight:700}
.status-warn {display:inline-block;background:#442c17;color:#ffc766;padding:5px 10px;border-radius:999px;font-weight:700}
.small-muted {color:#89a1b3;font-size:.85rem}
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
    factors: list[tuple[str, float]]

class MLBClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"Accept":"application/json","User-Agent":f"StrikeOutKing9000/{APP_VERSION}"})
    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.get(f"{MLB_API}/{endpoint}", params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict): raise ValueError("Unexpected MLB response format")
        return payload

def get_schedule(day: str) -> tuple[list[GamePitcher], str | None]:
    try: payload = MLBClient().get("schedule", {"sportId":1,"date":day,"hydrate":"probablePitcher,team,venue,linescore"})
    except (requests.RequestException, ValueError) as exc: return [], f"Schedule unavailable: {exc}"
    rows=[]
    for block in payload.get("dates", []):
        for game in block.get("games", []):
            teams=game.get("teams",{}); game_pk=int(game.get("gamePk",0)); venue=game.get("venue",{}).get("name","Unknown venue"); game_time=game.get("gameDate",""); status=game.get("status",{}).get("detailedState","Unknown")
            for side, opponent_side in (("away","home"),("home","away")):
                node, opponent=teams.get(side,{}), teams.get(opponent_side,{})
                pitcher=node.get("probablePitcher") or {}
                if not pitcher.get("id") or not pitcher.get("fullName"): continue
                team_node, opp_node=node.get("team",{}), opponent.get("team",{})
                team=TEAM_ABBR.get(team_node.get("id"),team_node.get("abbreviation","UNK")); opp=TEAM_ABBR.get(opp_node.get("id"),opp_node.get("abbreviation","UNK"))
                rows.append(GamePitcher(f"{game_pk}:{pitcher['id']}",int(pitcher["id"]),pitcher["fullName"],team,opp,side.title(),venue,game_pk,game_time,status))
    return rows,None

@st.cache_data(ttl=1800, show_spinner=False)
def get_pitcher_game_log(pitcher_id:int, season:int)->tuple[pd.DataFrame,str|None]:
    try: payload=MLBClient().get(f"people/{pitcher_id}/stats",{"stats":"gameLog","group":"pitching","season":season,"gameType":"R"})
    except (requests.RequestException,ValueError) as exc: return pd.DataFrame(),f"Pitcher history unavailable: {exc}"
    records=[]
    for stat_block in payload.get("stats",[]):
        for split in stat_block.get("splits",[]):
            stat=split.get("stat",{}); ip=parse_ip(stat.get("inningsPitched","0.0"))
            records.append({"date":pd.to_datetime(split.get("date"),errors="coerce"),"opponent":split.get("opponent",{}).get("name",""),"games_started":float(stat.get("gamesStarted",0) or 0),"batters_faced":float(stat.get("battersFaced",0) or 0),"strikeouts":float(stat.get("strikeOuts",0) or 0),"walks":float(stat.get("baseOnBalls",0) or 0),"hits":float(stat.get("hits",0) or 0),"runs":float(stat.get("runs",0) or 0),"pitches":float(stat.get("numberOfPitches",0) or 0),"outs":ip*3.0})
    df=pd.DataFrame(records)
    if df.empty:return df,"No regular-season game log returned."
    return df.sort_values("date"),None

def parse_ip(value:Any)->float:
    try: whole,frac=str(value).split("."); return int(whole)+int(frac)/3
    except (ValueError,AttributeError): return 0.0

def weighted_mean(values:pd.Series,half_life:float,fallback:float)->float:
    clean=pd.to_numeric(values,errors="coerce").dropna().to_numpy(dtype=float)
    if clean.size==0:return fallback
    ages=np.arange(clean.size-1,-1,-1); weights=np.power(0.5,ages/half_life); return float(np.average(clean,weights=weights))

def shrink(rate:float,opportunities:float,prior:float,prior_weight:float)->float:return float((rate*opportunities+prior*prior_weight)/max(opportunities+prior_weight,1.0))

def negbin_pmf(mean:float,dispersion:float,maximum:int)->np.ndarray:
    mean=max(mean,.05); dispersion=max(dispersion,.05); r=1.0/dispersion; p=r/(r+mean)
    probs=np.array([math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)+r*math.log(p)+k*math.log(1-p)) for k in range(maximum+1)]); probs[-1]+=max(0.0,1.0-probs.sum()); return probs/probs.sum()

def discrete_normal_probs(mean:float,sd:float,maximum:int=27)->np.ndarray:
    xs=np.arange(maximum+1); z_hi=(xs+.5-mean)/(sd*math.sqrt(2)); z_lo=(xs-.5-mean)/(sd*math.sqrt(2)); erf=np.vectorize(math.erf); probs=.5*(erf(z_hi)-erf(z_lo)); probs[0]+=.5*(1+math.erf((-0.5-mean)/(sd*math.sqrt(2)))); probs[-1]+=.5*(1-math.erf((maximum+.5-mean)/(sd*math.sqrt(2)))); probs=np.clip(probs,0,None); return probs/probs.sum()

def calculate_projection(log:pd.DataFrame,game:GamePitcher,manual:dict[str,float],simulations:int)->Projection:
    starts=log[log["games_started"]>0].copy().tail(35)
    if starts.empty: starts=log.tail(20).copy()
    bf=weighted_mean(starts["batters_faced"],5.0,22.0); outs=weighted_mean(starts["outs"],5.0,16.0); pitches=weighted_mean(starts["pitches"],5.0,88.0); total_bf=float(starts["batters_faced"].sum()); raw_k_rate=float(starts["strikeouts"].sum()/max(total_bf,1)); k_rate=shrink(raw_k_rate,total_bf,.224,120.0); opponent_factor=manual["opponent_k_pct"]/22.4; park_factor=PARK_K_FACTOR.get(game.venue,1.0); ump_factor=manual["umpire_k_factor"]; weather_factor=manual["weather_factor"]; rest_factor=manual["rest_factor"]; pitch_limit_factor=float(np.clip(manual["pitch_limit"]/max(pitches,75.0),.78,1.12)); projected_bf=bf*pitch_limit_factor*rest_factor; projected_outs=outs*pitch_limit_factor*rest_factor; projected_k=projected_bf*k_rate*opponent_factor*park_factor*ump_factor*weather_factor; projected_k=float(np.clip(.78*projected_k+.22*weighted_mean(starts["strikeouts"],5,5.0),.5,13.5)); projected_outs=float(np.clip(projected_outs,3.0,24.0)); k_variance=float(starts["strikeouts"].var(ddof=1)) if len(starts)>2 else projected_k*1.25; dispersion=max((k_variance-projected_k)/max(projected_k**2,.1),.08); k_probs=negbin_pmf(projected_k,dispersion,18); outs_sd=float(starts["outs"].std(ddof=1)) if len(starts)>2 else 4.0; outs_sd=float(np.clip(outs_sd,2.5,6.5)); outs_probs=discrete_normal_probs(projected_outs,outs_sd,27); seed_text=f"{game.key}|{date.today()}|{APP_VERSION}"; seed=int(hashlib.sha256(seed_text.encode()).hexdigest()[:8],16); rng=np.random.default_rng(seed); k_samples=rng.choice(np.arange(len(k_probs)),size=simulations,p=k_probs); outs_samples=rng.choice(np.arange(len(outs_probs)),size=simulations,p=outs_probs); quality=min(100,35+len(starts)*2+(15 if total_bf>=250 else 0)+(10 if game.pitcher_id else 0)); confidence="High" if quality>=85 else "Medium" if quality>=65 else "Low"; factors=[("Opponent strikeout profile",opponent_factor-1),("Recent workload / pitch limit",pitch_limit_factor-1),("Park",park_factor-1),("Umpire",ump_factor-1),("Weather",weather_factor-1),("Rest",rest_factor-1)]; return Projection(projected_k,projected_outs,math.sqrt(k_variance),outs_sd,k_probs,outs_probs,k_samples,outs_samples,confidence,quality,factors)

def over_probability(samples:np.ndarray,line:float)->float:return float(np.mean(samples>line))
def fair_american(probability:float)->str:
    p=float(np.clip(probability,.001,.999)); odds=-100*p/(1-p) if p>=.5 else 100*(1-p)/p; return f"{odds:+.0f}"
def interval(samples:np.ndarray,low:float=.10,high:float=.90)->tuple[int,int]:return int(np.quantile(samples,low)),int(np.quantile(samples,high))

def load_local_csv(filename:str)->pd.DataFrame:
    candidates=[DATA_DIR/filename,APP_DIR/filename]
    for path in candidates:
        if path.exists():return pd.read_csv(path)
    return pd.DataFrame()

now=datetime.now(EASTERN); query_day=now.date()
odds_date_value = st.session_state.get("odds_selected_date")
try:
    odds_default_date = datetime.strptime(str(odds_date_value), "%Y-%m-%d").date() if odds_date_value else query_day
except ValueError:
    odds_default_date = query_day
with st.sidebar:
    st.markdown("## StrikeOut King 9000"); st.caption(f"Distributional MLB starter projections · v{APP_VERSION}"); selected_date=st.date_input("Slate date",value=odds_default_date); st.markdown("### Model controls"); simulations=st.select_slider("Simulation draws",[5000,10000,25000,50000],value=25000); opponent_k_pct=st.slider("Projected lineup K%",15.0,32.0,22.4,.1); pitch_limit=st.slider("Expected pitch limit",60,115,92); umpire_k_factor=st.slider("Umpire K factor",.94,1.06,1.00,.01); weather_factor=st.slider("Weather K factor",.96,1.04,1.00,.01); rest_days=st.slider("Days rest",3,10,5); rest_factor=.96 if rest_days<=3 else 1.0 if rest_days<=6 else 1.01; st.caption("Market lines affect edge display only, never the baseball forecast.")

schedule,schedule_error=get_schedule(selected_date.isoformat()); st.title("⚾ StrikeOut King 9000"); st.markdown("Pregame strikeout and starter-outs distributions with transparent assumptions and uncertainty.")
if schedule_error:st.error(schedule_error)
if not schedule:st.warning("No announced probable pitchers are available for this date. Choose another date or wait for teams to announce starters."); st.stop()
options={g.key:g for g in schedule}
odds_pitcher_name = st.session_state.get("odds_selected_pitcher")
odds_game_date = st.session_state.get("odds_selected_date")
selected_index = 0
if odds_pitcher_name and odds_game_date == selected_date.isoformat():
    matches = [i for i, pitcher in enumerate(options.values()) if pitcher.pitcher_name.strip().lower() == str(odds_pitcher_name).strip().lower()]
    if matches:
        selected_index = matches[0]
        st.info(f"Odds API line loaded for {odds_pitcher_name}. Review the line below, then click Analyze line.")
selected_key=st.selectbox("Pitcher",list(options),index=selected_index,format_func=lambda key:f"{options[key].pitcher_name} · {options[key].team} vs {options[key].opponent}"); game=options[selected_key]; season=selected_date.year; log,history_error=get_pitcher_game_log(game.pitcher_id,season)
if log.empty and season>2000:
    previous_log,previous_error=get_pitcher_game_log(game.pitcher_id,season-1)
    if not previous_log.empty:log,history_error=previous_log,None
    elif history_error is None:history_error=previous_error
if history_error:st.warning(history_error)
if log.empty:st.error("A projection cannot be issued without a pitcher game history."); st.stop()
manual={"opponent_k_pct":opponent_k_pct,"pitch_limit":float(pitch_limit),"umpire_k_factor":umpire_k_factor,"weather_factor":weather_factor,"rest_factor":rest_factor}; projection=calculate_projection(log,game,manual,simulations); st.markdown(f"<span class='status-live'>LIVE SCHEDULE</span> &nbsp; <span class='small-muted'>{game.status} · {game.side} · {game.venue} · Updated {now:%I:%M %p ET}</span>",unsafe_allow_html=True)
line_col1,line_col2,line_col3=st.columns([1,1,2])
with line_col1:k_line=st.number_input("Strikeout line",.5,15.5,5.5,.5)
with line_col2:outs_line=st.number_input("Outs line",.5,26.5,15.5,.5)
with line_col3:st.markdown("#### Data status"); st.progress(projection.data_quality/100,text=f"{projection.confidence} confidence · data quality {projection.data_quality}/100")
k_over=over_probability(projection.k_samples,k_line); outs_over=over_probability(projection.outs_samples,outs_line); k_lo,k_hi=interval(projection.k_samples); o_lo,o_hi=interval(projection.outs_samples); m1,m2,m3,m4=st.columns(4); m1.metric("Projected strikeouts",f"{projection.mean_k:.2f}",f"80% range {k_lo}-{k_hi}"); m2.metric(f"Over {k_line:g}",f"{k_over:.1%}",f"Fair {fair_american(k_over)}"); m3.metric("Projected outs",f"{projection.mean_outs:.2f}",f"80% range {o_lo}-{o_hi}"); m4.metric(f"Over {outs_line:g}",f"{outs_over:.1%}",f"Fair {fair_american(outs_over)}")

tab1,tab2,tab3,tab4=st.tabs(["Projection","Distribution","Form & workload","Model card"])
with tab1:
    left,right=st.columns([1.4,1])
    with left:
        st.subheader("Decision table"); decision=pd.DataFrame([{"Market":f"K over {k_line:g}","Probability":k_over,"Fair odds":fair_american(k_over),"Projection":projection.mean_k},{"Market":f"K under {k_line:g}","Probability":1-k_over,"Fair odds":fair_american(1-k_over),"Projection":projection.mean_k},{"Market":f"Outs over {outs_line:g}","Probability":outs_over,"Fair odds":fair_american(outs_over),"Projection":projection.mean_outs},{"Market":f"Outs under {outs_line:g}","Probability":1-outs_over,"Fair odds":fair_american(1-outs_over),"Projection":projection.mean_outs}]); st.dataframe(decision.style.format({"Probability":"{:.1%}","Projection":"{:.2f}"}),hide_index=True,use_container_width=True); st.caption("Probabilities are model estimates, not guarantees.")
    with right:
        st.subheader("Projection drivers"); factor_df=pd.DataFrame(projection.factors,columns=["Factor","Impact"]); factor_df["Direction"]=np.where(factor_df["Impact"]>=0,"Raises","Lowers"); factor_df["Impact"]=factor_df["Impact"].map(lambda x:f"{x:+.1%}"); st.dataframe(factor_df,hide_index=True,use_container_width=True)
with tab2:
    k_chart=pd.DataFrame({"Strikeouts":np.arange(len(projection.k_probs)),"Probability":projection.k_probs}).set_index("Strikeouts"); outs_chart=pd.DataFrame({"Outs":np.arange(len(projection.outs_probs)),"Probability":projection.outs_probs}).set_index("Outs"); c1,c2=st.columns(2)
    with c1:st.subheader("Strikeout distribution"); st.bar_chart(k_chart,color="#31d7ff")
    with c2:st.subheader("Outs distribution"); st.bar_chart(outs_chart,color="#31e6a1")
with tab3:
    display=log.tail(15).copy(); display["K/BF"]=display["strikeouts"]/display["batters_faced"].replace(0,np.nan); display["Pitches/BF"]=display["pitches"]/display["batters_faced"].replace(0,np.nan); st.line_chart(display.set_index("date")[["strikeouts","outs"]]); st.dataframe(display[["date","opponent","strikeouts","outs","batters_faced","pitches","K/BF","Pitches/BF"]].sort_values("date",ascending=False).style.format({"K/BF":"{:.1%}","Pitches/BF":"{:.2f}"}),hide_index=True,use_container_width=True)
with tab4:
    st.subheader("What this version does"); st.markdown("""- Separates expected workload from strikeout skill instead of multiplying arbitrary static values.\n- Uses exponentially weighted form with empirical-Bayes shrinkage toward league average.\n- Produces full Negative Binomial strikeout and bounded outs distributions.\n- Keeps sportsbook inputs outside the forecast to avoid market leakage.\n- Refuses to publish a projection when required player history is unavailable.\n- Exposes every manual assumption and reports an uncertainty range."""); st.subheader("Current limitations"); st.markdown("""- Projected lineup K%, umpire, weather, and pitch limit are manual until dedicated feeds are connected.\n- This is an inference dashboard, not yet a trained walk-forward gradient-boosted production model.\n- Calibration must be measured on archived pregame snapshots before probabilities can be considered production-grade.""")
    manifest={"app_version":APP_VERSION,"prediction_timestamp_et":now.isoformat(),"game_pk":game.game_pk,"pitcher_id":game.pitcher_id,"inputs":manual,"simulation_draws":simulations,"confidence":projection.confidence}; st.download_button("Download prediction manifest",json.dumps(manifest,indent=2),file_name=f"projection_{game.game_pk}_{game.pitcher_id}.json",mime="application/json")

from training.manual_lines import ManualLine, analyze_manual_line, confidence_tier
from training.github_bet_store import save_bet

# Apply an Odds API selection once when entering this page. We intentionally
# keep these as separate non-widget keys because Streamlit cleans widget keys
# when switching pages.
odds_transfer_active = (
    st.session_state.get("odds_selected_date") == selected_date.isoformat()
    and st.session_state.get("odds_selected_line") is not None
    and not st.session_state.get("odds_selection_applied", False)
)
if odds_transfer_active:
    st.session_state["manual_side"] = str(st.session_state.get("odds_selected_side", "Over"))
    st.session_state["manual_line"] = float(st.session_state["odds_selected_line"])
    st.session_state["manual_odds"] = int(st.session_state.get("odds_selected_odds", -110))
    st.session_state["odds_selection_applied"] = True

st.divider(); st.subheader("Manual sportsbook line"); st.caption("Enter the line and price you see at your sportsbook. No sportsbook API or paid credits required.")
manual_col1,manual_col2,manual_col3,manual_col4=st.columns([1.2,1,1,1])
with manual_col1:manual_side=st.selectbox("Side",["Over","Under"],key="manual_side")
with manual_col2:manual_line=st.number_input("K line",.5,15.5,float(k_line),.5,key="manual_line")
with manual_col3:manual_odds=st.number_input("American odds",-500,500,-110,5,key="manual_odds")
with manual_col4:st.write(""); analyze_button=st.button("Analyze line",type="primary",use_container_width=True)
if analyze_button:
    manual_over=over_probability(projection.k_samples,manual_line); analysis=analyze_manual_line(projection.mean_k,manual_over,manual_line,manual_side,int(manual_odds)); st.session_state["pending_manual_bet"]={"analysis":analysis,"record":ManualLine(game.pitcher_name,selected_date.isoformat(),manual_line,manual_side,int(manual_odds))}
pending=st.session_state.get("pending_manual_bet")
if pending:
    analysis=pending["analysis"]; confidence=confidence_tier(analysis["model_probability"],analysis["edge"]); a1,a2,a3,a4=st.columns(4); a1.metric("Model probability",f"{analysis['model_probability']:.1%}"); a2.metric("Sportsbook implied",f"{analysis['implied_probability']:.1%}"); a3.metric("Model edge",f"{analysis['edge']:+.1%}"); a4.metric("Provisional confidence",confidence); st.info("Confidence is provisional until historical sportsbook lines are available for calibration.")
    if st.button("Save to bet tracker",key="save_bet"):
        record={**pending["record"].__dict__,**analysis,"confidence":confidence,"game_pk":game.game_pk,"pitcher_id":game.pitcher_id,"actual_strikeouts":""}; save_bet(record); st.session_state.pop("pending_manual_bet",None); st.session_state["odds_selected_pitcher"] = None; st.session_state["odds_selected_date"] = None; st.session_state["odds_selected_side"] = None; st.session_state["odds_selected_line"] = None; st.session_state["odds_selected_odds"] = None; st.session_state["odds_selection_applied"] = False; st.success("Bet saved to the persistent tracker.")

from training.github_bet_store import load_bets
tracker_rows=load_bets()
if tracker_rows:
    with st.expander("Bet tracker"):
        tracker=pd.DataFrame(tracker_rows); st.dataframe(tracker.sort_values("entered_at_utc",ascending=False),hide_index=True,use_container_width=True); st.download_button("Download bet tracker CSV",tracker.to_csv(index=False),file_name="bet_tracker.csv",mime="text/csv")

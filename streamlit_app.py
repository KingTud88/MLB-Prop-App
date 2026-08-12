from __future__ import annotations
import hashlib, math, os, re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

from engine.calibration import PROBABILITY_SEMANTICS, calibrate_blend, calibration_summary, milestone_calibration_report
from engine.projection_engine import ProjectionEngine, ProjectionResult
from engine.hits_allowed import project_hits_allowed
from engine.hits_calibration import calibrate_hits_blend
from engine.outs_projection import project_total_outs, OutsProjection
from engine.outs_calibration import calibrate_outs_blend
from engine.starter_history import TARGET_STARTER_HISTORY, combine_starter_history, starter_only
from engine.opposing_batters import get_opposing_batters, matchup_summary
from engine.lineup_context import LINEUP_CONFIRMED, get_confirmed_lineup
from engine.weather_risk import WeatherDelayRisk, fetch_weather_delay_risk
from engine.workload_context import WorkloadContext, build_workload_context
from engine.team_leash import build_team_leash_context, candidate_workload_fields
from engine.bet_lean import aligned_bet_lean
from engine.bet_tracker import make_bet_record, make_parlay_record
from training.bet_storage import append_bet

APP_VERSION = "3.7.0"
EASTERN = ZoneInfo("America/New_York")
MLB_API = "https://statsapi.mlb.com/api/v1"
ODDS_API = "https://api.the-odds-api.com/v4"
APP_DIR = Path(__file__).resolve().parent
BET_LOG = APP_DIR / "data" / "bet_log.csv"
OBS_LOG = APP_DIR / "data" / "starter_observation_log.csv"
TEAM_ABBR = {108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSH",121:"NYM",133:"ATH",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",147:"NYY",158:"MIL"}
TEAM_ID_BY_ABBR = {abbr: team_id for team_id, abbr in TEAM_ABBR.items()}
TEAM_NAMES = {"LAA":"Los Angeles Angels","ARI":"Arizona Diamondbacks","BAL":"Baltimore Orioles","BOS":"Boston Red Sox","CHC":"Chicago Cubs","CIN":"Cincinnati Reds","CLE":"Cleveland Guardians","COL":"Colorado Rockies","DET":"Detroit Tigers","HOU":"Houston Astros","KCR":"Kansas City Royals","LAD":"Los Angeles Dodgers","WSH":"Washington Nationals","NYM":"New York Mets","ATH":"Athletics","PIT":"Pittsburgh Pirates","SDP":"San Diego Padres","SEA":"Seattle Mariners","SFG":"San Francisco Giants","STL":"St. Louis Cardinals","TBR":"Tampa Bay Rays","TEX":"Texas Rangers","TOR":"Toronto Blue Jays","MIN":"Minnesota Twins","PHI":"Philadelphia Phillies","ATL":"Atlanta Braves","CHW":"Chicago White Sox","MIA":"Miami Marlins","NYY":"New York Yankees","MIL":"Milwaukee Brewers"}
PARK_K_FACTOR = {"Coors Field":.94,"T-Mobile Park":1.05,"Petco Park":1.03,"Oracle Park":1.02,"Dodger Stadium":1.01,"Yankee Stadium":.99,"Fenway Park":.98,"Wrigley Field":1.00}

st.set_page_config(page_title="StrikeOut King 9000", page_icon="⚾", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
:root{--bg:#06111d;--panel:#0b1c2e;--line:#1b3851;--red:#f0193c;--green:#24e69b;--ink:#f2f6fa;--muted:#8fa5b7}
.stApp{background:linear-gradient(145deg,#04101b,#091a2a);color:var(--ink)}
[data-testid="stSidebar"]{background:#071727;border-right:1px solid #18334b}
.block-container{padding-top:3.25rem;max-width:1500px}
h1,h2,h3{letter-spacing:-.02em}
.king-title{font-size:4rem;font-weight:900;line-height:.9;text-align:center}.king-red{color:var(--red)}
.subline{text-align:center;color:#fff;border-bottom:2px solid var(--red);padding-bottom:10px;font-weight:800;letter-spacing:.12em}
.pitcher-card,.metric-card,.panel{background:rgba(9,27,44,.94);border:1px solid #20425f;border-radius:16px}.pitcher-card{padding:18px 24px}
.section-head{background:linear-gradient(90deg,#ed1236,#f0193c);padding:9px 16px;border-radius:14px 14px 0 0;text-align:center;font-weight:900;letter-spacing:.08em}
.metric-card{padding:16px;text-align:center;min-height:150px}.metric-label{font-weight:800;color:#d8e5ef;letter-spacing:.05em}.metric-value{font-size:3.0rem;font-weight:900;line-height:1.05}
.reco-card{padding:14px 12px;text-align:center;min-height:150px;background:rgba(9,27,44,.94);border:1px solid #20425f;border-radius:16px}.reco-label{font-weight:900;color:#d8e5ef;letter-spacing:.05em;font-size:.92rem}.reco-side{font-size:2.15rem;font-weight:900;line-height:1.0;margin-top:8px}.reco-line{font-size:1.05rem;font-weight:900;margin-top:6px}.reco-meta{color:#9fb3c3;font-size:.78rem;margin-top:6px}.reco-good{color:#49efb0}.reco-neutral{color:#f2f6fa}.reco-warn{color:#ffd166}
.badge{display:inline-block;background:#073d2c;border:1px solid #087c59;color:#49efb0;border-radius:999px;padding:5px 10px;font-weight:800;font-size:.82rem}
.search-note{color:var(--muted);font-size:.82rem}
.market-ok{color:#49efb0;font-weight:800}.market-empty{color:#8fa5b7}
</style>""", unsafe_allow_html=True)

@dataclass(frozen=True)
class GamePitcher:
    key:str; pitcher_id:int; pitcher_name:str; team:str; opponent:str; side:str; venue_id:int; venue:str; game_pk:int; game_time:str; status:str

@dataclass
class Projection:
    mean_k:float; mean_outs:float; k_sd:float; outs_sd:float; k_probs:np.ndarray; outs_probs:np.ndarray; k_samples:np.ndarray; outs_samples:np.ndarray; confidence:str; quality:int; factors:list[tuple[str,float]]; engine:ProjectionResult; outs_engine:OutsProjection

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
            teams=game.get("teams",{}); pk=int(game.get("gamePk",0)); venue_node=game.get("venue",{}) or {}; venue=venue_node.get("name","Unknown"); venue_id=int(venue_node.get("id",0) or 0)
            for side,other in (("away","home"),("home","away")):
                node=teams.get(side,{}) or {}; opp=teams.get(other,{}) or {}; pit=node.get("probablePitcher") or {}
                if not pit.get("id"): continue
                tn=node.get("team",{}); on=opp.get("team",{})
                team=TEAM_ABBR.get(tn.get("id"),tn.get("abbreviation","UNK")); opponent=TEAM_ABBR.get(on.get("id"),on.get("abbreviation","UNK"))
                rows.append(GamePitcher(f"{pk}:{pit['id']}",int(pit["id"]),pit.get("fullName","Unknown"),team,opponent,side.title(),venue_id,venue,pk,game.get("gameDate",""),game.get("status",{}).get("detailedState","Scheduled")))
    return rows,None

def parse_ip(v):
    try:
        whole,frac=str(v).split("."); return int(whole)+int(frac)/3
    except Exception: return 0.0

@st.cache_data(ttl=1800,show_spinner=False)
def get_log(pid,season):
    try:p=MLBClient().get(f"people/{pid}/stats",{"stats":"gameLog","group":"pitching","season":season,"gameType":"R"})
    except Exception as e:return pd.DataFrame(),str(e)
    rec=[]
    for sb in p.get("stats",[]):
        for sp in sb.get("splits",[]):
            s=sp.get("stat",{}); bf=float(s.get("battersFaced",0) or 0)
            rec.append({"date":pd.to_datetime(sp.get("date"),errors="coerce"),"opponent":sp.get("opponent",{}).get("name",""),"bf":bf,"k":float(s.get("strikeOuts",0) or 0),"hits":float(s.get("hits",0) or 0),"pitches":float(s.get("numberOfPitches",0) or 0),"outs":parse_ip(s.get("inningsPitched","0.0"))*3,"games_started":int(float(s.get("gamesStarted",0) or 0))})
    df=pd.DataFrame(rec); starts=starter_only(df); return (starts,None) if not starts.empty else (starts,"No regular-season starter game log returned.")

def weighted(s,half,fallback):
    x=pd.to_numeric(s,errors="coerce").dropna().to_numpy(float)
    if not len(x): return fallback
    age=np.arange(len(x)-1,-1,-1); w=.5**(age/half); return float(np.average(x,weights=w))

def shrink(rate,opp,prior=.224,weight=120): return (rate*opp+prior*weight)/max(opp+weight,1)

@st.cache_data(ttl=1800,show_spinner=False)
def get_pitcher_hand(pid):
    try:
        payload=MLBClient().get(f"people/{int(pid)}",{})
        people=payload.get("people") or []
        if not people:
            return ""
        # MLB Person uses `pitchHand`; retain the legacy key only as a defensive fallback.
        hand=people[0].get("pitchHand") or people[0].get("pitchingHand") or {}
        return str(hand.get("code") or "").upper()
    except Exception:
        return ""

@st.cache_data(ttl=21600,show_spinner=False)
def get_venue_coordinates(venue_id):
    if not venue_id: return None
    try:
        payload=MLBClient().get(f"venues/{int(venue_id)}",{})
        venues=payload.get("venues") or []
        coords=((venues[0].get("location") or {}).get("defaultCoordinates") or {}) if venues else {}
        lat=coords.get("latitude"); lon=coords.get("longitude")
        return (float(lat),float(lon)) if lat is not None and lon is not None else None
    except Exception:
        return None

@st.cache_data(ttl=900,show_spinner=False)
def get_game_weather(venue_id,game_time):
    coords=get_venue_coordinates(venue_id)
    if not coords:
        return WeatherDelayRisk("UNKNOWN","",None,None,None,"Venue coordinates unavailable for weather risk.",False)
    return fetch_weather_delay_risk(coords[0],coords[1],game_time)

def load_projection_history():
    try:return pd.read_csv(APP_DIR / "data" / "projection_log.csv")
    except Exception:return pd.DataFrame()

def load_observation_history():
    try:return pd.read_csv(OBS_LOG)
    except Exception:return pd.DataFrame()

def calibrated_weights(history): return {line:calibrate_blend(history,line) for line in range(3,11)}

def build_engine_features(log,game,opponent_k_pct=.224,lineup_batters=0,workload_context:WorkloadContext|None=None):
    starts=log.tail(35).copy(); total_bf=float(starts.bf.sum()); raw_k=float(starts.k.sum()/max(total_bf,1)); pitcher_k=float(np.clip(shrink(raw_k,total_bf),.05,.45)); workload_context=workload_context or build_workload_context(starts,game.game_time)
    return {"pitcher_k_pct":pitcher_k,"opponent_k_pct":float(np.clip(opponent_k_pct,.08,.45)),"handedness_factor":1.0,"arsenal_factor":1.0,"park_factor":PARK_K_FACTOR.get(game.venue,1.0),"umpire_factor":1.0,"weather_factor":1.0,"expected_bf":float(workload_context.expected_bf),"bf_sd":float(workload_context.bf_sd),"rest_factor":1.0,"historical_k_sd":float(np.clip(starts.k.std(ddof=1) if len(starts)>2 else 2.0,.75,4.5)),"historical_games":int(len(starts)),"lineup_batters":int(lineup_batters),"arsenal_sample_size":0,"weather_available":0,"umpire_available":0}

def calculate_projection(log,game,simulations,opponent_k_pct=.224,lineup_batters=0,workload_context:WorkloadContext|None=None):
    history=load_projection_history(); cal=calibrated_weights(history); workload_context=workload_context or build_workload_context(log,game.game_time); seed=int(hashlib.sha256(f"{game.key}|{game.game_time}|{APP_VERSION}".encode()).hexdigest()[:8],16); features=build_engine_features(log,game,opponent_k_pct,lineup_batters,workload_context); engine=ProjectionEngine(simulation_weight=.5,seed=seed); result=engine.project(features,draws=simulations,lines=tuple(float(x) for x in range(3,11))); global_w=float(np.mean([r.weight_simulation for r in cal.values()])) if cal else .5; mean_k=global_w*result.simulation_mean+(1-global_w)*result.mathematical_mean; outs_seed=int(hashlib.sha256(f"outs|{game.key}|{APP_VERSION}".encode()).hexdigest()[:8],16); outs_model=project_total_outs(log,expected_outs=workload_context.expected_outs,workload_sd=workload_context.outs_sd,seed=outs_seed,draws=simulations,lines=(13.5,14.5,15.5,16.5,17.5,18.5)); mean_outs=outs_model.ensemble_mean; osd=outs_model.ensemble_sd; outs_samples=outs_model.simulation_samples; outs_probs=np.array([float(np.mean(outs_samples==i)) for i in range(28)]); quality=int(round(result.data_quality)); confidence="High" if result.confidence>=.75 else "Medium" if result.confidence>=.60 else "Low"; return Projection(mean_k,mean_outs,result.ensemble_sd,osd,result.mathematical_pmf,outs_probs,result.simulation_samples,outs_samples,confidence,quality,[(n,v) for n,v,_ in result.drivers],result,outs_model)

def american(p):
    p=float(np.clip(p,.001,.999)); o=-100*p/(1-p) if p>=.5 else 100*(1-p)/p; return f"{o:+.0f}"

def implied_prob(price):
    try:
        p=float(price); return 100/(p+100) if p>0 else abs(p)/(abs(p)+100)
    except Exception:return None

def best_market_offer(odds_rows, market_keys, line, side):
    wanted=str(side).lower(); candidates=[]
    for row in odds_rows:
        if row.get("market") not in set(market_keys): continue
        if str(row.get("name","")).lower()!=wanted: continue
        try:
            if abs(float(row.get("point"))-float(line))>1e-9: continue
            float(row.get("price"))
        except Exception: continue
        candidates.append(row)
    return max(candidates,key=lambda row:float(row.get("price"))) if candidates else None

PROJECTION_PARLAY_KEY="projection_page_parlay_legs"
PROJECTION_PARLAY_BOOKS=[
    "Not tracked","FanDuel","DraftKings","BetMGM","Caesars Sportsbook",
    "Fanatics Sportsbook","bet365","ESPN BET","Hard Rock Bet","BetRivers","Other / Not listed",
]

def projection_parlay_leg(game,game_date,market,line,side,projection,model_probability,data_quality):
    return {
        "player":game.pitcher_name,"market":market,"game_date":str(game_date)[:10],
        "line":float(line),"side":str(side).title(),"american_odds":None,
        "game_pk":int(game.game_pk),"pitcher_id":int(game.pitcher_id),
        "projection":float(projection),"model_probability":float(model_probability),
        "data_quality":float(data_quality),"app_version":APP_VERSION,
        "probability_semantics":PROBABILITY_SEMANTICS,"snapshot_captured_at_utc":"",
    }

def _projection_leg_key(leg):
    return (
        str(leg.get("game_date","")),str(leg.get("game_pk","")),str(leg.get("pitcher_id","")),
        str(leg.get("market","")),str(leg.get("side","")),float(leg.get("line",0.0)),
    )

def queue_projection_parlay_leg(leg):
    legs=list(st.session_state.get(PROJECTION_PARLAY_KEY,[]))
    if legs and str(legs[0].get("game_date","")) != str(leg.get("game_date","")):
        return False,"The Projection Parlay Builder already contains a different slate date. Save or clear it first."
    key=_projection_leg_key(leg)
    if any(_projection_leg_key(existing)==key for existing in legs):
        return False,"That exact leg is already in the Projection Parlay Builder."
    if len(legs)>=5:
        return False,"The Projection Parlay Builder is capped at five legs."
    legs.append(dict(leg)); st.session_state[PROJECTION_PARLAY_KEY]=legs
    return True,f"Added to Projection Parlay Builder ({len(legs)}/5)."

def save_projection_straight(*,game,game_date,market,line,side,projection,model_probability,stake,confidence,data_quality,offer,source):
    price=float(offer.get("price")) if offer is not None and offer.get("price") is not None else None
    implied=implied_prob(price) if price is not None else None
    record=make_bet_record(
        player=game.pitcher_name,market=market,game_date=game_date,line=float(line),side=side,
        american_odds=price,stake=float(stake),book=str(offer.get("book","")) if offer is not None else "",
        projection=float(projection),model_probability=float(model_probability),implied_probability=implied,
        edge=None if implied is None else float(model_probability)-implied,confidence=confidence,
        game_pk=game.game_pk,pitcher_id=game.pitcher_id,source=source,data_quality=float(data_quality),
        app_version=APP_VERSION,probability_semantics=PROBABILITY_SEMANTICS,
    )
    append_bet(BET_LOG,record,st.secrets)
    return price

def render_add_bet_button(container,reco,market_label,market_keys,projection_mean,stake,game,game_date,odds_rows,confidence,data_quality,key):
    side=str(reco.get("side","PASS"))
    offer=best_market_offer(odds_rows,market_keys,reco.get("line"),side) if side in {"OVER","UNDER"} else None
    with container:
        if offer is not None:
            st.caption(f"Best posted: {offer.get('book','')} {float(offer.get('price')):+.0f}")
        elif side=="PASS":
            st.caption("No aligned model-side recommendation to track")
        else:
            st.caption("Model leg available · sportsbook price optional")
        straight_col,parlay_col=st.columns(2)
        straight_clicked=straight_col.button("➕ Straight",key=f"{key}_straight",use_container_width=True,disabled=(side=="PASS"))
        parlay_clicked=parlay_col.button("🎟️ Parlay",key=f"{key}_parlay",use_container_width=True,disabled=(side=="PASS"))
        if straight_clicked:
            try:
                price=save_projection_straight(
                    game=game,game_date=game_date,market=market_label,line=float(reco.get("line")),side=side,
                    projection=projection_mean,model_probability=float(reco.get("model")),stake=stake,
                    confidence=confidence,data_quality=data_quality,offer=offer,source="Projection Recommendation",
                )
                st.success("Added to Bet Tracker" if price is not None else "Added unpriced model straight to Bet Tracker · result will grade, P/L stays blank because no sportsbook price was assumed.")
            except Exception as exc:
                st.error(f"Could not add bet: {exc}")
        if parlay_clicked:
            leg=projection_parlay_leg(
                game,game_date,market_label,float(reco.get("line")),side,projection_mean,float(reco.get("model")),data_quality
            )
            added,message=queue_projection_parlay_leg(leg)
            (st.success if added else st.info)(message)

def render_projection_parlay_builder():
    legs=list(st.session_state.get(PROJECTION_PARLAY_KEY,[]))
    with st.expander(f"🎟️ Projection Parlay Builder · {len(legs)}/5 legs",expanded=bool(legs)):
        st.caption(
            "Add model legs from recommendations or the Strikeout Ladder, then move between pitchers on the same slate. "
            "Sportsbook availability never gates this builder; saved model parlays are unpriced and the sportsbook label is recordkeeping only."
        )
        if not legs:
            st.info("No parlay legs queued yet. Use any 🎟️ Parlay button on this Projection page.")
            return
        rows=[]
        for idx,leg in enumerate(legs,1):
            milestone=""
            if str(leg.get("market"))=="Strikeouts" and str(leg.get("side")).lower()=="over":
                line=float(leg.get("line",0.0)); milestone=f" ({int(line+0.5)}+ K)" if abs((line+0.5)-round(line+0.5))<1e-9 else ""
            rows.append({
                "#":idx,"Pitcher":leg.get("player",""),"Market":leg.get("market",""),
                "Bet":f"{leg.get('side','')} {float(leg.get('line',0.0)):g}{milestone}",
                "Projection":leg.get("projection",""),"Model Probability":leg.get("model_probability",""),
            })
        builder_view=pd.DataFrame(rows)
        builder_view["Projection"]=pd.to_numeric(builder_view["Projection"],errors="coerce").map(lambda x:"—" if pd.isna(x) else f"{x:.2f}")
        builder_view["Model Probability"]=pd.to_numeric(builder_view["Model Probability"],errors="coerce").map(lambda x:"—" if pd.isna(x) else f"{x:.1%}")
        st.dataframe(builder_view,hide_index=True,use_container_width=True)
        remove_col,clear_col=st.columns([2,1])
        remove_idx=remove_col.selectbox("Remove leg",range(len(legs)),format_func=lambda i:f"#{i+1} {legs[i].get('player','')} · {legs[i].get('market','')} · {legs[i].get('side','')} {float(legs[i].get('line',0.0)):g}",key="projection_parlay_remove")
        if clear_col.button("🗑️ Remove selected",use_container_width=True,key="projection_parlay_remove_button"):
            legs.pop(int(remove_idx)); st.session_state[PROJECTION_PARLAY_KEY]=legs; st.rerun()
        if st.button("Clear Projection Parlay Builder",use_container_width=True,key="projection_parlay_clear"):
            st.session_state[PROJECTION_PARLAY_KEY]=[]; st.rerun()
        duplicate_pitchers=pd.Series([str(leg.get("player","")) for leg in legs]).value_counts()
        correlated=duplicate_pitchers[duplicate_pitchers>1]
        if not correlated.empty:
            st.warning("Multiple legs for the same pitcher can be correlated: "+", ".join(correlated.index.tolist())+". The app does not treat parlay probability as independent.")
        parlay_stake=st.number_input("Parlay stake (units)",min_value=0.0,value=1.0,step=0.5,key="projection_parlay_stake")
        parlay_book=st.selectbox("Sportsbook (recordkeeping only)",PROJECTION_PARLAY_BOOKS,key="projection_parlay_book")
        if len(legs)>=2:
            if st.button(f"🎟️ Save {len(legs)}-leg model parlay to Bet Tracker",type="primary",use_container_width=True,key="projection_parlay_save"):
                try:
                    record=make_parlay_record(
                        legs=legs,stake=float(parlay_stake),game_date=str(legs[0].get("game_date",""))[:10],
                        book="" if parlay_book=="Not tracked" else parlay_book,source="Projection Page Model Parlay",
                    )
                    append_bet(BET_LOG,record,st.secrets)
                    st.session_state[PROJECTION_PARLAY_KEY]=[]
                    st.success(f"Saved {len(legs)}-leg model parlay to Bet Tracker · no sportsbook price was assumed.")
                except Exception as exc:
                    st.error(f"Could not save parlay: {exc}")
        else:
            st.info("Add at least one more leg to save a parlay ticket.")

def market_recommendation(proj,odds_rows,market_key,default_line,kind):
    base_key=market_key.replace("_alternate",""); allowed={market_key,base_key}; rows=[r for r in odds_rows if r.get("market") in allowed and r.get("point") is not None]
    line=default_line; over_price=under_price=None
    if rows:
        points=[]
        for r in rows:
            try: points.append(float(r["point"]))
            except Exception: pass
        if points: line=min(points,key=lambda x:abs(x-default_line))
        chosen=[r for r in rows if abs(float(r.get("point"))-line)<1e-9]
        over_offers=[r for r in chosen if str(r.get("name","")).lower()=="over" and r.get("price") is not None]
        under_offers=[r for r in chosen if str(r.get("name","")).lower()=="under" and r.get("price") is not None]
        if over_offers: over_price=max(float(r.get("price")) for r in over_offers)
        if under_offers: under_price=max(float(r.get("price")) for r in under_offers)
    history=load_projection_history(); cutoff=int(math.floor(line)+1)
    if kind=="k":
        sim=float(proj.engine.simulation_probabilities.get(float(cutoff),np.mean(proj.k_samples>=cutoff)))
        math_p=float(proj.engine.mathematical_probabilities.get(float(cutoff),0.0))
        cal=calibrate_blend(history,cutoff)
        over_model=cal.weight_simulation*sim+cal.weight_math*math_p
        projection_mean=proj.mean_k
    else:
        sim=float(proj.outs_engine.simulation_probabilities.get(float(line),np.mean(proj.outs_samples>=cutoff)))
        math_p=float(proj.outs_engine.mathematical_probabilities.get(float(line),0.0))
        cal=calibrate_outs_blend(history,float(line))
        over_model=cal.weight_simulation*sim+cal.weight_math*math_p
        projection_mean=proj.mean_outs
    decision=aligned_bet_lean(
        projection_mean,
        line,
        over_model,
        over_implied=implied_prob(over_price) if over_price is not None else None,
        under_implied=implied_prob(under_price) if under_price is not None else None,
        has_market=bool(rows),
    )
    confidence=abs(decision.model_probability-.5)*2
    return {"side":decision.side,"line":line,"model":decision.model_probability,"edge":decision.edge,"confidence":confidence,"has_market":bool(rows),"reason":decision.reason,"projection_mean":projection_mean,"over_model":over_model}

def render_reco(card,reco):
    side=reco["side"]
    cls="reco-warn" if side=="PASS" else "reco-good"
    reason_labels={"no_positive_aligned_edge":"NO POSITIVE ALIGNED EDGE","probability_conflicts_with_projection":"PROJECTION / PROBABILITY DISAGREE","projection_on_line":"PROJECTION ON LINE","model_direction":"MODEL LEAN","aligned_positive_edge":"POSITIVE ALIGNED EDGE"}
    if side=="PASS":
        meta=f"Proj {reco.get('projection_mean',float('nan')):.2f} vs {reco['line']:g} · {reason_labels.get(reco.get('reason'),'NO BET')}"
    else:
        edge=f"EDGE {reco['edge']:+.1%}" if reco["edge"] is not None else "MODEL LEAN"
        meta=f"Model {reco['model']:.1%} · {edge}"
    with card: st.markdown(f'<div class="reco-card"><div class="reco-label">{reco["label"]}</div><div class="reco-side {cls}">{side}</div><div class="reco-line">{reco["line"]:g} LINE</div><div class="reco-meta">{meta}</div></div>',unsafe_allow_html=True)

def render_calibration_dashboard():
    st.markdown("### Milestone Calibration Dashboard"); st.caption("Resolved pregame projections only. Sportsbook prices are excluded from training.")
    history=load_projection_history(); report=milestone_calibration_report(history,range(3,11),min_observations=30); display=report.copy()
    for col in ["Simulation Brier","Math Brier","Calibrated Brier"]: display[col]=display[col].map(lambda x:"—" if pd.isna(x) else f"{x:.4f}")
    for col in ["Simulation Weight","Math Weight","Actual Hit Rate"]: display[col]=display[col].map(lambda x:"—" if pd.isna(x) else f"{x:.1%}")
    st.dataframe(display,use_container_width=True,hide_index=True); resolved=int(pd.to_numeric(history.get("actual_strikeouts"),errors="coerce").notna().sum()) if not history.empty and "actual_strikeouts" in history.columns else 0; st.info(f"{resolved} resolved projections currently available. Each milestone learns independently after 30 valid observations; until then it stays at a 50/50 simulation/math baseline.")

def ladder(proj,max_line=10):
    history=load_projection_history(); rows=[]
    for line in range(3,max_line+1):
        cal=calibrate_blend(history,line); sim=proj.engine.simulation_probabilities.get(float(line),0.0); analytic=proj.engine.mathematical_probabilities.get(float(line),0.0); w=cal.weight_simulation; blended=w*sim+(1-w)*analytic; rows.append({"Line":f"{line}+","Probability":blended,"Fair Odds":american(blended),"Simulation":sim,"Math":analytic,"Sim Weight":w})
    return pd.DataFrame(rows)

def get_secret():
    for k in ("ODDS_API_KEY","THE_ODDS_API_KEY","odds_api_key"):
        try:
            if k in st.secrets:return str(st.secrets[k])
        except Exception:pass
    return os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY")

def safe_odds_error(exc):
    response=getattr(exc,"response",None)
    status=getattr(response,"status_code",None)
    if status==401:
        return "Odds API unavailable: authentication failed (401). Check or rotate the Odds API key in Streamlit secrets."
    if status==403:
        return "Odds API unavailable: request forbidden (403). Check the Odds API account/permissions."
    if status==429:
        return "Odds API unavailable: rate or credit limit reached (429)."
    if status is not None:
        return f"Odds API unavailable: HTTP {int(status)}."
    return f"Odds API unavailable: {type(exc).__name__}."

@st.cache_data(ttl=900,show_spinner=False)
def get_odds_events():
    key=get_secret()
    if not key:return [],"Odds API key not found in Streamlit secrets."
    try:
        r=requests.get(f"{ODDS_API}/sports/baseball_mlb/events",params={"apiKey":key},timeout=15); r.raise_for_status(); return r.json(),None
    except requests.RequestException as e:return [],safe_odds_error(e)

MAIN_PROP_MARKETS="pitcher_strikeouts,pitcher_outs,pitcher_hits_allowed"

@st.cache_data(ttl=900,show_spinner=False)
def get_event_props(event_id):
    key=get_secret()
    if not key:return [],"Odds API key not found in Streamlit secrets.",{}
    params={"apiKey":key,"regions":"us","markets":MAIN_PROP_MARKETS,"oddsFormat":"american"}
    try:
        r=requests.get(f"{ODDS_API}/sports/baseball_mlb/events/{event_id}/odds",params=params,timeout=15)
        r.raise_for_status()
        def _h(name):
            value=r.headers.get(name)
            try:return int(value) if value is not None else None
            except (TypeError,ValueError):return None
        quota={"remaining":_h("x-requests-remaining"),"used":_h("x-requests-used"),"last":_h("x-requests-last")}
        return r.json(),None,quota
    except requests.RequestException as e:return [],safe_odds_error(e),{}

def normalize_team(value):
    text=re.sub(r"[^a-z0-9]","",str(value).lower())
    for abbr,name in TEAM_NAMES.items():
        if text==re.sub(r"[^a-z0-9]","",abbr.lower()) or text==re.sub(r"[^a-z0-9]","",name.lower()): return abbr
    aliases={"oaklandathletics":"ATH","oaklandas":"ATH","athletics":"ATH","washingtonnationals":"WSH","kansascityroyals":"KCR","tampabayrays":"TBR","sandiegopadres":"SDP","sanfranciscogiants":"SFG","stlouiscardinals":"STL","arizonadiamondbacks":"ARI","chicagowhitesox":"CHW","losangelesangels":"LAA","losangelesdodgers":"LAD","newyorkyankees":"NYY","newyorkmets":"NYM","torontobluejays":"TOR"}
    return aliases.get(text,text)

def find_odds_event(events,game):
    wanted={normalize_team(game.team),normalize_team(game.opponent)}
    for event in events if isinstance(events,list) else []:
        teams={normalize_team(event.get("home_team","")),normalize_team(event.get("away_team",""))}
        if teams==wanted or wanted.issubset(teams): return event.get("id")
    return None

def extract_player_odds(payload,pitcher_name):
    rows=[]; target=" ".join(str(pitcher_name).lower().split()); allowed={"pitcher_strikeouts","pitcher_strikeouts_alternate","pitcher_outs","pitcher_outs_alternate","pitcher_hits_allowed","pitcher_hits_allowed_alternate"}
    for bm in payload.get("bookmakers",[]) if isinstance(payload,dict) else []:
        for m in bm.get("markets",[]):
            if m.get("key") not in allowed: continue
            for o in m.get("outcomes",[]):
                desc=" ".join(str(o.get("description","")).lower().split())
                if desc!=target: continue
                rows.append({"book":bm.get("title",bm.get("key","")),"market":m["key"],"name":o.get("name"),"point":o.get("point"),"price":o.get("price")})
    return rows

def market_model_probability(proj,market,line,hits_proj=None):
    line=float(line); cutoff=int(math.floor(line)+1); history=load_projection_history()
    if market in ("pitcher_strikeouts","pitcher_strikeouts_alternate"):
        sim=float(proj.engine.simulation_probabilities.get(float(cutoff),np.mean(proj.k_samples>=cutoff))); math_p=float(proj.engine.mathematical_probabilities.get(float(cutoff),0.0)); cal=calibrate_blend(history,cutoff); return cal.weight_simulation*sim+cal.weight_math*math_p
    if market in ("pitcher_hits_allowed","pitcher_hits_allowed_alternate") and hits_proj is not None:
        sim=float(hits_proj.simulation_probabilities.get(line,np.mean(hits_proj.simulation_samples>=cutoff))); math_p=float(hits_proj.mathematical_probabilities.get(line,0.0)); cal=calibrate_hits_blend(history,line); return cal.weight_simulation*sim+cal.weight_math*math_p
    sim=float(proj.outs_engine.simulation_probabilities.get(line,np.mean(proj.outs_samples>=cutoff))); math_p=float(proj.outs_engine.mathematical_probabilities.get(line,0.0)); cal=calibrate_outs_blend(history,line); return cal.weight_simulation*sim+cal.weight_math*math_p

def build_market_table(proj,odds_rows,hits_proj=None):
    grouped={}
    for r in odds_rows:
        try: line=float(r["point"])
        except Exception: continue
        key=(r["book"],r["market"],line); grouped.setdefault(key,{})[str(r.get("name","")).lower()]=r.get("price")
    rows=[]
    for (book,market,line),prices in grouped.items():
        model=market_model_probability(proj,market,line,hits_proj); over=prices.get("over"); under=prices.get("under"); op=implied_prob(over) if over is not None else None; up=implied_prob(under) if under is not None else None; oe=model-op if op is not None else None; ue=(1-model)-up if up is not None else None; best=max([e for e in (oe,ue) if e is not None],default=None)
        rows.append({"Market":"K" if "strikeouts" in market else "HITS" if "hits_allowed" in market else "OUTS","Type":"ALT" if market.endswith("_alternate") else "MAIN","Book":book,"Line":f"{line:g}","Over":over,"Under":under,"Model":model,"Over Edge":oe,"Under Edge":ue,"Best Edge":best})
    return pd.DataFrame(rows).sort_values(["Market","Line","Book"]) if rows else pd.DataFrame()

with st.sidebar:
    st.markdown("## StrikeOut King 9000"); st.caption("CLE-themed MLB starter projection engine")
    nav=st.radio("Navigation",["Projection","Distribution","Form & Workload","Model Card","Bet Tracker","Projection History","Daily Projection Run","Top Plays"],label_visibility="collapsed")
    if nav == "Bet Tracker":
        st.switch_page("pages/2_Bet_Tracker.py")
    if nav == "Daily Projection Run":
        st.switch_page("pages/5_Daily_Projection_Run.py")
    if nav == "Projection History":
        st.switch_page("pages/4_Projection_History.py")
    if nav == "Top Plays":
        st.switch_page("pages/6_Top_Plays.py")
    st.divider(); selected_date=st.date_input("Slate date",value=datetime.now(EASTERN).date()); st.markdown("### PITCHER SEARCH")
    locked_key=st.session_state.get("locked_pitcher"); search=st.text_input("Search pitcher...",placeholder="Search pitcher...",label_visibility="collapsed",disabled=bool(locked_key)); st.caption("Search and select a pitcher to lock the projection 🔒")

schedule,err=get_schedule(selected_date.isoformat())
if err: st.error(err)
if not schedule: st.warning("No announced probable pitchers are available for this date."); st.stop()
locked_game=next((g for g in schedule if g.key==locked_key),None) if locked_key else None
if locked_key and locked_game is None: st.session_state["locked_pitcher"]=None; locked_key=None
matches=schedule if locked_game else [g for g in schedule if not search or search.lower() in g.pitcher_name.lower() or search.lower() in g.team.lower()]
if not matches: st.info("No pitchers match that search."); st.stop()
names=[f"{g.pitcher_name} · {g.team} vs {g.opponent}" for g in matches]
with st.sidebar:
    default_index=names.index(f"{locked_game.pitcher_name} · {locked_game.team} vs {locked_game.opponent}") if locked_game else 0
    choice=st.selectbox("Matching pitchers",names,index=default_index,label_visibility="collapsed",key="pitcher_selector",disabled=bool(locked_game))
game=matches[names.index(choice)]; locked=st.session_state.get("locked_pitcher")==game.key
with st.sidebar:
    if st.button("🔒 LOCK PITCHER" if not locked else "🔓 UNLOCK PITCHER",use_container_width=True): st.session_state["locked_pitcher"]=None if locked else game.key; st.rerun()

log,herr=get_log(game.pitcher_id,selected_date.year)
if len(log) < TARGET_STARTER_HISTORY:
    prior,prior_err=get_log(game.pitcher_id,selected_date.year-1)
    log=combine_starter_history(log,prior)
    herr=herr or prior_err
if log.empty: st.error(herr or "Pitcher starter history unavailable."); st.stop()
pitcher_hand=get_pitcher_hand(game.pitcher_id)
opponent_team_id=TEAM_ID_BY_ABBR.get(game.opponent,0)
lineup_context=get_confirmed_lineup(game.game_pk,opponent_team_id)
opposing_batters=get_opposing_batters(
    game.opponent,pitcher_hand,selected_date.year,opponent_team_id,
    lineup_context.player_ids if lineup_context.confirmed else (),
    lineup_context.spots if lineup_context.confirmed else (),
)
opponent_matchup=matchup_summary(opposing_batters,confirmed_lineup=lineup_context.confirmed)
weather_risk=get_game_weather(game.venue_id,game.game_time)
confirmed_count=lineup_context.batter_count if lineup_context.confirmed else 0
workload_ctx=build_workload_context(log,game.game_time)
team_leash_ctx=build_team_leash_context(load_projection_history(),load_observation_history(),game.team,game.game_time)
team_leash_candidate=candidate_workload_fields(team_leash_ctx,workload_ctx.expected_pitches,workload_ctx.expected_bf,workload_ctx.expected_outs)
proj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count,workload_ctx); kdf=ladder(proj,10)
features_for_hits=build_engine_features(log,game,float(opponent_matchup["k_rate"]),confirmed_count,workload_ctx)
hits_seed=int(hashlib.sha256(f"hits|{game.key}|{game.game_time}|{APP_VERSION}".encode()).hexdigest()[:8],16)
hits_proj=project_hits_allowed(log,expected_bf=features_for_hits["expected_bf"],bf_sd=workload_ctx.bf_sd,opponent_hit_rate=float(opponent_matchup.get("hit_rate",.235)),seed=hits_seed,draws=25000,lines=(3.5,4.5,5.5,6.5,7.5,8.5))
odds_events,odds_err=get_odds_events(); odds_event_id=find_odds_event(odds_events,game)
odds_payload_key=f"projection_live_odds:{game.key}"
odds_quota_key=f"projection_live_odds_quota:{game.key}"
odds_payload=st.session_state.get(odds_payload_key,{})
if odds_event_id:
    with st.sidebar:
        st.markdown("#### 💳 Odds API Credit Saver")
        st.caption("Paid odds are OFF by default. Main Strikeouts + Outs + Hits only; one US region; up to 3 credits when you press load. Alternate markets stay off.")
        load_live_odds=st.button("LOAD LIVE ODDS · ≤3 credits",key=f"load_live_odds:{game.key}",use_container_width=True)
    if load_live_odds:
        loaded_payload,prop_err,quota=get_event_props(odds_event_id)
        if loaded_payload:
            odds_payload=loaded_payload
            st.session_state[odds_payload_key]=loaded_payload
        if quota:
            st.session_state[odds_quota_key]=quota
        odds_err=prop_err if prop_err else odds_err
else:
    odds_payload=[]
    odds_err=odds_err if odds_err else "No matching Odds API event found for this MLB game."
quota_view=st.session_state.get(odds_quota_key,{})
if quota_view:
    with st.sidebar:
        st.caption(f"Last paid load: {quota_view.get('last','—')} credit(s) · {quota_view.get('remaining','—')} remaining · {quota_view.get('used','—')} used.")
if not odds_payload and not odds_err:
    odds_err="Live sportsbook prices not loaded. Credit Saver is ON; the baseball projection does not need sportsbook data."
odds_rows=extract_player_odds(odds_payload,game.pitcher_name)
k_reco=market_recommendation(proj,odds_rows,"pitcher_strikeouts_alternate",5.5,"k"); k_reco["label"]="STRIKEOUT BET LEAN"
out_reco=market_recommendation(proj,odds_rows,"pitcher_outs_alternate",15.5,"outs"); out_reco["label"]="TOTAL OUTS BET LEAN"
hit_rows=[r for r in odds_rows if r.get("market") in {"pitcher_hits_allowed","pitcher_hits_allowed_alternate"} and r.get("point") is not None]
hit_line=min([float(r["point"]) for r in hit_rows],key=lambda x:abs(x-5.5)) if hit_rows else 5.5
hit_sim=float(hits_proj.simulation_probabilities.get(float(hit_line),0.0)); hit_math=float(hits_proj.mathematical_probabilities.get(float(hit_line),0.0))
hit_cal=calibrate_hits_blend(load_projection_history(),float(hit_line)); hit_over=hit_cal.weight_simulation*hit_sim+hit_cal.weight_math*hit_math
hit_over_offer=best_market_offer(odds_rows,{"pitcher_hits_allowed","pitcher_hits_allowed_alternate"},hit_line,"OVER")
hit_under_offer=best_market_offer(odds_rows,{"pitcher_hits_allowed","pitcher_hits_allowed_alternate"},hit_line,"UNDER")
hit_over_price=hit_over_offer.get("price") if hit_over_offer else None
hit_under_price=hit_under_offer.get("price") if hit_under_offer else None
hit_decision=aligned_bet_lean(hits_proj.ensemble_mean,hit_line,hit_over,over_implied=implied_prob(hit_over_price) if hit_over_price is not None else None,under_implied=implied_prob(hit_under_price) if hit_under_price is not None else None,has_market=bool(hit_rows))
hit_reco={"side":hit_decision.side,"line":hit_line,"model":hit_decision.model_probability,"edge":hit_decision.edge,"confidence":abs(hit_decision.model_probability-.5)*2,"has_market":bool(hit_rows),"label":"HITS ALLOWED BET LEAN","reason":hit_decision.reason,"projection_mean":hits_proj.ensemble_mean,"over_model":hit_over}

if nav=="Distribution":
    st.markdown('<div class="section-head">DISTRIBUTION</div>',unsafe_allow_html=True); st.caption(f"{game.pitcher_name} · {game.team} vs {game.opponent}"); a,b=st.columns(2)
    with a: st.markdown("### Strikeout probability distribution"); st.bar_chart(pd.DataFrame({"Probability":proj.k_probs},index=np.arange(len(proj.k_probs))))
    with b: st.markdown("### Outs probability distribution"); st.bar_chart(pd.DataFrame({"Probability":proj.outs_probs},index=np.arange(len(proj.outs_probs))))
    st.stop()
elif nav=="Form & Workload":
    st.markdown('<div class="section-head">FORM & WORKLOAD</div>',unsafe_allow_html=True); st.caption(f"{game.pitcher_name} · workload-v1 uses starter history only; sportsbook data is not an input.")
    w1,w2,w3,w4,w5,w6=st.columns(6)
    w1.metric("Expected pitches",f"{workload_ctx.expected_pitches:.1f}")
    w2.metric("Expected BF",f"{workload_ctx.expected_bf:.1f}")
    w3.metric("Expected outs",f"{workload_ctx.expected_outs:.1f}")
    w4.metric("Pitches / BF",f"{workload_ctx.pitches_per_bf:.2f}")
    w5.metric("Days since last start","—" if workload_ctx.days_since_last_start is None else workload_ctx.days_since_last_start)
    w6.metric("Recent leash",workload_ctx.leash_label)
    st.caption(f"Pitch trend {workload_ctx.pitch_trend:+.1%} · BF trend {workload_ctx.bf_trend:+.1%} · outs trend {workload_ctx.outs_trend:+.1%} · short-rest exposure multiplier {workload_ctx.rest_multiplier:.3f}.")
    st.markdown("#### 🧭 Team leash candidate · CONTEXT ONLY")
    t1,t2,t3,t4,t5,t6=st.columns(6)
    t1.metric("Team starts tracked",team_leash_ctx.starts_used)
    t2.metric("Team avg pitches",f"{team_leash_ctx.team_avg_pitches:.1f}")
    t3.metric("Team avg BF",f"{team_leash_ctx.team_avg_bf:.1f}")
    t4.metric("TTO reached",f"{team_leash_ctx.tto_reach_rate:.1%}")
    t5.metric("90+ pitches",f"{team_leash_ctx.pitch_90_rate:.1%}")
    t6.metric("Team leash",team_leash_ctx.label)
    st.caption(
        f"Status {team_leash_ctx.status} · candidate-only multipliers: pitches {team_leash_ctx.pitch_multiplier_candidate:.3f}, "
        f"BF {team_leash_ctx.bf_multiplier_candidate:.3f}, outs {team_leash_ctx.outs_multiplier_candidate:.3f}. "
        "These values do not alter Ks, Hits Allowed, Outs, or Top Plays until leakage-safe validation earns that right."
    )
    d=log.tail(15).copy(); st.line_chart(d.set_index("date")[["pitches","bf","outs","k"]]); st.dataframe(d.sort_values("date",ascending=False),use_container_width=True,hide_index=True); st.stop()
elif nav=="Model Card":
    st.markdown('<div class="section-head">MODEL CARD</div>',unsafe_allow_html=True); st.write("Two independent paths: (1) plate-appearance Monte Carlo game simulation with workload uncertainty; (2) independent mathematical Negative-Binomial probability model. Milestone probabilities are calibrated from resolved pregame projections when enough observations exist. Sportsbook prices are used only for edge display, never to create the baseball forecast."); st.markdown("### Path comparison"); path_df=pd.DataFrame([{"Path":"Simulation","Mean K":proj.engine.simulation_mean,"SD":proj.engine.simulation_sd},{"Path":"Mathematical","Mean K":proj.engine.mathematical_mean,"SD":proj.engine.mathematical_sd},{"Path":"Ensemble","Mean K":proj.mean_k,"SD":proj.k_sd}]); path_df["Mean K"]=path_df["Mean K"].map(lambda v:f"{v:.2f}"); path_df["SD"]=path_df["SD"].map(lambda v:f"{v:.2f}"); st.dataframe(path_df,use_container_width=True,hide_index=True); model_view=kdf[["Line","Probability","Simulation","Math","Sim Weight"]].copy()
    for c in ("Probability","Simulation","Math","Sim Weight"): model_view[c]=model_view[c].map(lambda v:f"{v:.1%}")
    st.dataframe(model_view,use_container_width=True,hide_index=True); st.markdown("### Calibration diagnostics"); render_calibration_dashboard(); st.dataframe(calibration_summary(load_projection_history()),use_container_width=True,hide_index=True); st.stop()
elif nav=="Bet Tracker":
    st.markdown('<div class="section-head">BET TRACKER</div>',unsafe_allow_html=True); st.caption("Current pitcher markets available from the Odds API are shown here when posted.")
    if odds_err: st.info(odds_err)
    if odds_rows: st.dataframe(pd.DataFrame(odds_rows),use_container_width=True,hide_index=True)
    else: st.info("No live player-prop markets are currently available for this game.")
    st.stop()
elif nav=="Projection History":
    st.markdown('<div class="section-head">PROJECTION HISTORY</div>',unsafe_allow_html=True); history=st.session_state.get("projection_history",[]); current={"Date":selected_date.isoformat(),"Pitcher":game.pitcher_name,"Matchup":f"{game.team} vs {game.opponent}","Projected K":round(proj.mean_k,2),"3+":f"{kdf.iloc[0].Probability:.1%}","5+":f"{kdf.iloc[2].Probability:.1%}"}
    if st.button("Save current projection"): history.append(current); st.session_state["projection_history"]=history; st.rerun()
    st.dataframe(pd.DataFrame(history) if history else pd.DataFrame([current]),use_container_width=True,hide_index=True); st.stop()
elif nav=="Daily Projection Run":
    st.markdown('<div class="section-head">DAILY PROJECTION RUN</div>',unsafe_allow_html=True); st.write(f"Slate: {selected_date.isoformat()} · {len(matches)} probable pitcher entries loaded."); st.dataframe(pd.DataFrame([{"Pitcher":g.pitcher_name,"Team":g.team,"Opponent":g.opponent,"Status":g.status} for g in matches]),use_container_width=True,hide_index=True); st.info("Select a pitcher from the left-rail dropdown to run the full two-path projection for that pitcher."); st.stop()

if not locked: st.info("Lock the pitcher in the left rail to freeze all projection outputs for this pitcher.")
st.markdown('<div class="king-title">STRIKEOUT<br><span class="king-red">KING 9000</span></div><div class="subline">★ MLB PITCHER PROJECTION ENGINE ★ TWO-PATH ANALYTICS ★</div>',unsafe_allow_html=True)
weather_marker=f" {weather_risk.icon}" if weather_risk.icon else ""
st.markdown(f'<div class="pitcher-card"><h2>{game.pitcher_name.upper()}{weather_marker}</h2><b>{game.team} vs {game.opponent}</b><br><span class="search-note">{game.venue} · {game.side} · {game.status}</span></div>',unsafe_allow_html=True)
if weather_risk.available and weather_risk.level in {"HIGH","ELEVATED"}:
    st.warning(f"{weather_risk.icon} {weather_risk.summary}. Weather risk is informational and does not currently modify the projection.")
elif weather_risk.available and weather_risk.level == "LOW":
    st.caption(f"{weather_risk.icon} {weather_risk.summary}. Informational only.")
st.markdown('<div class="section-head">PROJECTION SUMMARY</div>',unsafe_allow_html=True)
c1,c2,c3,c4=st.columns(4)
with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">PROJECTED STRIKEOUTS</div><div class="metric-value">{proj.mean_k:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.k_samples,.1))}-{int(np.quantile(proj.k_samples,.9))}</span></div>',unsafe_allow_html=True)
render_reco(c2,k_reco)
with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">PROJECTED OUTS</div><div class="metric-value">{proj.mean_outs:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.outs_samples,.1))}-{int(np.quantile(proj.outs_samples,.9))}</span></div>',unsafe_allow_html=True)
render_reco(c4,out_reco)
h1,h2=st.columns(2)
with h1: st.markdown(f'<div class="metric-card"><div class="metric-label">PROJECTED HITS ALLOWED</div><div class="metric-value">{hits_proj.ensemble_mean:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(hits_proj.simulation_samples,.1))}-{int(np.quantile(hits_proj.simulation_samples,.9))}</span></div>',unsafe_allow_html=True)
render_reco(h2,hit_reco)

st.markdown('<div class="section-head">OPPOSING BATTER BOX</div>',unsafe_allow_html=True)
lineup_label="✅ CONFIRMED BATTING ORDER" if lineup_context.confirmed else "ACTIVE ROSTER FALLBACK · lineup not posted yet"
st.caption(f"{lineup_label} · {game.opponent} hitters vs a {pitcher_hand or 'unknown-hand'} pitcher. Pitcher-hand K% and H/PA feed the baseball matchup; incomplete hitter splits shrink safely toward league rates.")
if opposing_batters.empty:
    st.info("Opposing batter split data is not available yet. The projection falls back to protected league opponent baselines.")
else:
    b1,b2,b3,b4,b5=st.columns(5)
    b1.metric("Matchup K%",f"{float(opponent_matchup['k_rate']):.1%}")
    b2.metric("Matchup H/PA",f"{float(opponent_matchup.get('hit_rate',.235)):.1%}")
    b3.metric("Split PA",int(opponent_matchup["pa"]))
    b4.metric("HIGH K hitters",int(opponent_matchup["high"]))
    b5.metric("ELEVATED K hitters",int(opponent_matchup["elevated"]))
    batter_display=opposing_batters.copy()
    batter_display["K% vs Pitcher"]=pd.to_numeric(batter_display["K% vs Pitcher"],errors="coerce")*100.0
    batter_display["H/PA vs Pitcher"]=pd.to_numeric(batter_display["H/PA vs Pitcher"],errors="coerce")*100.0
    batter_display["Risk"]=batter_display["Risk"].map({"HIGH":"🔥 HIGH","ELEVATED":"⚠️ ELEVATED","NORMAL":"NORMAL"}).fillna(batter_display["Risk"])
    batter_display["Split Available"]=batter_display["Split Available"].map({True:"MLB split",False:"League fallback"}).fillna("League fallback")
    columns=["Lineup Spot","Batter","Hand","K% vs Pitcher","H/PA vs Pitcher","PA","Risk","Split Available"] if lineup_context.confirmed else ["Batter","Hand","K% vs Pitcher","H/PA vs Pitcher","PA","Risk","Split Available"]
    st.dataframe(
        batter_display[columns],
        hide_index=True,
        width="stretch",
        column_config={
            "Lineup Spot":st.column_config.NumberColumn("Order",format="%.0f"),
            "Batter":st.column_config.TextColumn("Batter"),
            "Hand":st.column_config.TextColumn("Bats"),
            "K% vs Pitcher":st.column_config.NumberColumn(f"K% vs {pitcher_hand or 'Pitcher'}",format="%.1f%%"),
            "H/PA vs Pitcher":st.column_config.NumberColumn(f"H/PA vs {pitcher_hand or 'Pitcher'}",format="%.1f%%"),
            "PA":st.column_config.NumberColumn("Split PA",format="%.0f"),
            "Risk":st.column_config.TextColumn("K Risk"),
            "Split Available":st.column_config.TextColumn("Data"),
        },
    )

st.markdown("#### Add recommendation to Bet Tracker")
quick_add_stake=st.number_input("Quick-add stake",min_value=0.0,value=1.0,step=0.5,key=f"projection_quick_stake_{game.key}")
add1,add2,add3=st.columns(3)
render_add_bet_button(add1,k_reco,"Strikeouts",{"pitcher_strikeouts","pitcher_strikeouts_alternate"},proj.mean_k,quick_add_stake,game,selected_date.isoformat(),odds_rows,proj.confidence,proj.quality,f"add_k_{game.key}")
render_add_bet_button(add2,out_reco,"Total Outs",{"pitcher_outs","pitcher_outs_alternate"},proj.mean_outs,quick_add_stake,game,selected_date.isoformat(),odds_rows,proj.confidence,proj.quality,f"add_outs_{game.key}")
render_add_bet_button(add3,hit_reco,"Hits Allowed",{"pitcher_hits_allowed","pitcher_hits_allowed_alternate"},hits_proj.ensemble_mean,quick_add_stake,game,selected_date.isoformat(),odds_rows,proj.confidence,proj.quality,f"add_hits_{game.key}")
render_projection_parlay_builder()
with st.expander(f"🔎 Why this projection? · {game.pitcher_name}", expanded=False):
    st.caption("Live single-pitcher rationale using the same model paths shown in the projection cards. Sportsbook prices are comparison inputs only; they do not create the forecast.")
    x1,x2,x3,x4=st.columns(4)
    x1.metric("Projected Ks",f"{proj.mean_k:.2f}")
    x2.metric("Projected outs",f"{proj.mean_outs:.2f}")
    x3.metric("Projected hits allowed",f"{hits_proj.ensemble_mean:.2f}")
    x4.metric("Data quality",f"{proj.quality}/100")
    why_left,why_right=st.columns(2)
    with why_left:
        st.markdown("#### Strikeouts · 5+")
        k_cal=calibrate_blend(load_projection_history(),5)
        k_sim=float(proj.engine.simulation_probabilities.get(5.0,np.mean(proj.k_samples>=5)))
        k_math=float(proj.engine.mathematical_probabilities.get(5.0,0.0))
        k_blend=k_cal.weight_simulation*k_sim+k_cal.weight_math*k_math
        k_paths=pd.DataFrame([{"Path":"Simulation","Probability":k_sim,"Weight":k_cal.weight_simulation},{"Path":"Mathematical","Probability":k_math,"Weight":k_cal.weight_math}])
        for c in ("Probability","Weight"): k_paths[c]=k_paths[c].map(lambda v:f"{v:.1%}")
        st.dataframe(k_paths,use_container_width=True,hide_index=True)
        st.write(f"**Blended 5+ probability:** {k_blend:.1%}")
        st.caption(f"Calibration: {'learned' if k_cal.calibrated else '50/50 baseline'} · {k_cal.observations} compatible resolved observations.")
        st.write(f"Opponent K input: **{features_for_hits['opponent_k_pct']:.1%}**")
        st.write(f"Expected batters faced: **{features_for_hits['expected_bf']:.1f}**")
        st.write(f"Expected pitches: **{workload_ctx.expected_pitches:.1f}** · expected outs: **{workload_ctx.expected_outs:.1f}**")
        st.write(f"Pitch efficiency: **{workload_ctx.pitches_per_bf:.2f} pitches/BF** · recent leash: **{workload_ctx.leash_label}**")
        st.write(f"Days since last start: **{'—' if workload_ctx.days_since_last_start is None else workload_ctx.days_since_last_start}** · pitch trend: **{workload_ctx.pitch_trend:+.1%}**")
        st.write(f"Park K factor: **{features_for_hits['park_factor']:.3f}**")
    with why_right:
        st.markdown("#### Hits Allowed · Over 5.5")
        h_cal=calibrate_hits_blend(load_projection_history(),5.5)
        h_sim=float(hits_proj.simulation_probabilities.get(5.5,0.0))
        h_math=float(hits_proj.mathematical_probabilities.get(5.5,0.0))
        h_blend=h_cal.weight_simulation*h_sim+h_cal.weight_math*h_math
        h_paths=pd.DataFrame([{"Path":"Simulation","Probability":h_sim,"Weight":h_cal.weight_simulation},{"Path":"Mathematical","Probability":h_math,"Weight":h_cal.weight_math}])
        for c in ("Probability","Weight"): h_paths[c]=h_paths[c].map(lambda v:f"{v:.1%}")
        st.dataframe(h_paths,use_container_width=True,hide_index=True)
        st.write(f"**Blended O5.5 probability:** {h_blend:.1%}")
        st.caption(f"Calibration: {'learned' if h_cal.calibrated else '50/50 baseline'} · {h_cal.observations} resolved hit observations.")
        st.write(f"Pitcher hit rate: **{hits_proj.pitcher_hit_rate:.1%}**")
        st.write(f"Opponent hit-rate input: **{hits_proj.opponent_hit_rate:.1%}**")
        st.write(f"Matchup hit rate: **{hits_proj.matchup_hit_rate:.1%}**")
    st.markdown("#### Total Outs · Over 15.5")
    o_cal=calibrate_outs_blend(load_projection_history(),15.5)
    o_sim=float(proj.outs_engine.simulation_probabilities.get(15.5,0.0)); o_math=float(proj.outs_engine.mathematical_probabilities.get(15.5,0.0))
    o_blend=o_cal.weight_simulation*o_sim+o_cal.weight_math*o_math
    o_paths=pd.DataFrame([{"Path":"Simulation","Probability":o_sim,"Weight":o_cal.weight_simulation},{"Path":"Mathematical","Probability":o_math,"Weight":o_cal.weight_math}])
    for c in ("Probability","Weight"): o_paths[c]=o_paths[c].map(lambda v:f"{v:.1%}")
    st.dataframe(o_paths,use_container_width=True,hide_index=True)
    st.write(f"**Blended O15.5 probability:** {o_blend:.1%}")
    st.caption(f"Projected outs {proj.mean_outs:.2f} · SD {proj.outs_sd:.2f} · calibration {'learned' if o_cal.calibrated else '50/50 baseline'} · {o_cal.observations} resolved outs observations.")
    drivers=pd.DataFrame(proj.factors,columns=["Driver","Impact"]) if proj.factors else pd.DataFrame()
    if not drivers.empty:
        st.markdown("#### Leading model drivers")
        st.dataframe(drivers,use_container_width=True,hide_index=True)
left,right=st.columns([1.35,1])
with left:
    st.markdown('<div class="section-head">STRIKEOUT MILESTONE LADDER</div>',unsafe_allow_html=True)
    view=kdf[["Line","Probability","Fair Odds","Simulation","Math","Sim Weight"]].copy()
    view["Probability"]=view["Probability"].map(lambda x:f"{x:.1%}")
    view["Simulation"]=view["Simulation"].map(lambda x:f"{x:.1%}")
    view["Math"]=view["Math"].map(lambda x:f"{x:.1%}")
    view["Sim Weight"]=view["Sim Weight"].map(lambda x:f"{x:.1%}")
    ladder_event=st.dataframe(
        view,use_container_width=True,hide_index=True,on_select="rerun",selection_mode="single-row",key=f"projection_k_ladder_{game.key}"
    )
    st.caption("Click any 3+ through 10+ milestone to add it as a straight or parlay leg. A milestone like 5+ is tracked as Over 4.5 so Bet Tracker grading matches K ≥ 5. Fair Odds are model-only and are never saved as a sportsbook price.")
    try:
        ladder_selected=list(ladder_event.selection.rows)
    except Exception:
        ladder_selected=list((ladder_event.get("selection",{}) or {}).get("rows",[])) if isinstance(ladder_event,dict) else []
    if ladder_selected:
        ladder_idx=int(ladder_selected[0])
        if 0<=ladder_idx<len(kdf):
            ladder_row=kdf.iloc[ladder_idx]
            milestone=int(str(ladder_row["Line"]).replace("+",""))
            tracker_line=float(milestone)-0.5
            model_probability=float(ladder_row["Probability"])
            ladder_offer=best_market_offer(odds_rows,{"pitcher_strikeouts","pitcher_strikeouts_alternate"},tracker_line,"OVER")
            offer_text=f" · exact posted {ladder_offer.get('book','')} {float(ladder_offer.get('price')):+.0f}" if ladder_offer is not None else " · no sportsbook price required"
            st.markdown(f"**Selected: {milestone}+ Ks · model {model_probability:.1%} · fair {ladder_row['Fair Odds']}**{offer_text}")
            ladder_straight,ladder_parlay=st.columns(2)
            if ladder_straight.button("➕ Add selected as straight",use_container_width=True,key=f"ladder_straight_{game.key}_{milestone}"):
                try:
                    price=save_projection_straight(
                        game=game,game_date=selected_date.isoformat(),market="Strikeouts",line=tracker_line,side="OVER",
                        projection=proj.mean_k,model_probability=model_probability,stake=quick_add_stake,
                        confidence=proj.confidence,data_quality=proj.quality,offer=ladder_offer,source="Projection Strikeout Ladder",
                    )
                    st.success(f"Added {milestone}+ K as Over {tracker_line:g} to Bet Tracker"+("" if price is not None else " · unpriced model straight"))
                except Exception as exc:
                    st.error(f"Could not add ladder straight: {exc}")
            if ladder_parlay.button("🎟️ Add selected to parlay",use_container_width=True,key=f"ladder_parlay_{game.key}_{milestone}"):
                leg=projection_parlay_leg(game,selected_date.isoformat(),"Strikeouts",tracker_line,"OVER",proj.mean_k,model_probability,proj.quality)
                added,message=queue_projection_parlay_leg(leg)
                (st.success if added else st.info)(message)
with right:
    st.markdown('<div class="section-head">MARKET ODDS / EDGE</div>',unsafe_allow_html=True)
    if odds_err: st.caption(odds_err)
    market_df=build_market_table(proj,odds_rows,hits_proj)
    if not market_df.empty:
        for c in ("Model","Over Edge","Under Edge","Best Edge"): market_df[c]=market_df[c].map(lambda x:"—" if pd.isna(x) else f"{x:.1%}")
        st.dataframe(market_df,use_container_width=True,hide_index=True)
        st.caption("Live sportsbook prices are shown for strikeouts, total outs, and hits allowed markets. Edge compares the independent model probability with implied probability; market prices never feed the forecast.")
    else: st.info("Live market data will populate here when the Odds API returns the pitcher props.")
st.markdown(f'<div class="search-note">Data status: {proj.confidence} confidence · quality {proj.quality}/100 · locked: {locked} · engine v{APP_VERSION}</div>',unsafe_allow_html=True)

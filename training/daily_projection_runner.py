from __future__ import annotations

import hashlib
import math
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import requests
from training.daily_role_shadow import attach_daily_role_shadow, load_runtime_state

APP_VERSION = "2.0.2"
MLB_API = "https://statsapi.mlb.com/api/v1"
TEAM_ABBR = {108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSH",121:"NYM",133:"ATH",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",147:"NYY",158:"MIL"}
PARK_K_FACTOR = {"Coors Field":.94,"T-Mobile Park":1.05,"Petco Park":1.03,"Oracle Park":1.02,"Dodger Stadium":1.01,"Yankee Stadium":.99,"Fenway Park":.98,"Wrigley Field":1.0}

def _get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    r = requests.get(f"{MLB_API}/{endpoint}", params=params, timeout=20, headers={"Accept":"application/json","User-Agent":f"StrikeOutKing9000/{APP_VERSION}"})
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict): raise ValueError("Unexpected MLB response format")
    return data

def get_schedule(day: str) -> list[dict[str, Any]]:
    data = _get("schedule", {"sportId":1,"date":day,"hydrate":"probablePitcher,team,venue"})
    rows=[]
    for block in data.get("dates",[]):
        for game in block.get("games",[]):
            teams=game.get("teams",{}); pk=int(game.get("gamePk",0)); venue=game.get("venue",{}).get("name","Unknown venue"); game_time=game.get("gameDate",""); status=game.get("status",{}).get("detailedState","Unknown")
            for side,other in (("away","home"),("home","away")):
                node=teams.get(side,{}); opp_node=teams.get(other,{}); pitcher=node.get("probablePitcher") or {}
                if not pitcher.get("id") or not pitcher.get("fullName"): continue
                team_node=node.get("team",{}); other_team=opp_node.get("team",{})
                team=TEAM_ABBR.get(team_node.get("id"),team_node.get("abbreviation","UNK")); opponent=TEAM_ABBR.get(other_team.get("id"),other_team.get("abbreviation","UNK"))
                rows.append({"key":f"{pk}:{pitcher['id']}","game_pk":pk,"pitcher_id":int(pitcher["id"]),"player":pitcher["fullName"],"team":team,"opponent":opponent,"venue":venue,"game_time":game_time,"status":status})
    return rows

def parse_ip(v: Any)->float:
    try:
        whole,frac=str(v).split("."); return int(whole)+int(frac)/3
    except (ValueError,AttributeError): return 0.0

def game_log(pid:int, season:int)->pd.DataFrame:
    data=_get(f"people/{pid}/stats",{"stats":"gameLog","group":"pitching","season":season,"gameType":"R"}); rows=[]
    for block in data.get("stats",[]):
        for split in block.get("splits",[]):
            s=split.get("stat",{}); rows.append({"date":pd.to_datetime(split.get("date"),errors="coerce"),"games_started":float(s.get("gamesStarted",0) or 0),"batters_faced":float(s.get("battersFaced",0) or 0),"strikeouts":float(s.get("strikeOuts",0) or 0),"pitches":float(s.get("numberOfPitches",0) or 0),"outs":parse_ip(s.get("inningsPitched","0.0"))*3})
    df=pd.DataFrame(rows); return df.sort_values("date") if not df.empty else df

def weighted(v:pd.Series,half:float,fallback:float)->float:
    a=pd.to_numeric(v,errors="coerce").dropna().to_numpy(dtype=float)
    if not len(a): return fallback
    ages=np.arange(len(a)-1,-1,-1); return float(np.average(a,weights=np.power(.5,ages/half)))

def shrink(rate:float,opp:float,prior:float=.224,weight:float=120)->float: return float((rate*opp+prior*weight)/max(opp+weight,1))

def pmf(mean:float,disp:float,max_k:int=18)->np.ndarray:
    mean=max(mean,.05); disp=max(disp,.05); r=1/disp; p=r/(r+mean)
    out=np.array([math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)+r*math.log(p)+k*math.log(1-p)) for k in range(max_k+1)]); out[-1]+=max(0,1-out.sum()); return out/out.sum()

def project(game:dict[str,Any],log:pd.DataFrame,opponent_k_pct:float=22.4,pitch_limit:float=92,umpire_k_factor:float=1,weather_factor:float=1,rest_factor:float=1,simulations:int=5000)->dict[str,Any]:
    starts=log[log.games_started>0].tail(35)
    if starts.empty: starts=log.tail(20)
    bf=weighted(starts.batters_faced,5,22); pitches=weighted(starts.pitches,5,88); total_bf=float(starts.batters_faced.sum()); rate=shrink(float(starts.strikeouts.sum()/max(total_bf,1)),total_bf); opponent_factor=opponent_k_pct/22.4; park=PARK_K_FACTOR.get(game["venue"],1); pitch_factor=float(np.clip(pitch_limit/max(pitches,75),.78,1.12)); projected_bf=bf*pitch_factor*rest_factor; mean=float(np.clip(.78*(projected_bf*rate*opponent_factor*park*umpire_k_factor*weather_factor)+.22*weighted(starts.strikeouts,5,5),.5,13.5)); variance=float(starts.strikeouts.var(ddof=1)) if len(starts)>2 else mean*1.25; probs=pmf(mean,max((variance-mean)/max(mean**2,.1),.08)); seed=int(hashlib.sha256(f"{game['key']}|{game['game_time']}|{APP_VERSION}".encode()).hexdigest()[:8],16); samples=np.random.default_rng(seed).choice(np.arange(len(probs)),size=simulations,p=probs); quality=min(100,35+len(starts)*2+(15 if total_bf>=250 else 0)+10); confidence="High" if quality>=85 else "Medium" if quality>=65 else "Low"
    return {"game_pk":game["game_pk"],"game_date":game["game_time"][:10],"pitcher_id":game["pitcher_id"],"player":game["player"],"team":game["team"],"opponent":game["opponent"],"venue":game["venue"],"game_time":game["game_time"],"app_version":APP_VERSION,"projection":mean,"k_sd":math.sqrt(variance),"k_range_low":int(np.quantile(samples,.10)),"k_range_high":int(np.quantile(samples,.90)),"confidence":confidence,"data_quality":quality,"simulation_draws":simulations,"opponent_k_pct":opponent_k_pct,"pitch_limit":pitch_limit,"umpire_k_factor":umpire_k_factor,"weather_factor":weather_factor,"rest_factor":rest_factor,"actual_strikeouts":"","resolved_at_utc":"","status":game["status"]}

def run_daily_projections(day:str,**kwargs)->tuple[list[dict[str,Any]],list[str],int]:
    games=get_schedule(day); records=[]; errors=[]; skipped=0; season=date.fromisoformat(day).year; role_history=load_runtime_state()
    for game in games:
        if not any(x in game["status"].lower() for x in ("scheduled","pre-game","warmup")): skipped+=1; continue
        try:
            log=game_log(game["pitcher_id"],season)
            if log.empty: log=game_log(game["pitcher_id"],season-1)
            if log.empty: errors.append(f"{game['player']}: no game history"); continue
            record=project(game,log,**kwargs)
            records.append(attach_daily_role_shadow(record,log,game["game_time"],role_history))
        except (requests.RequestException,ValueError,TypeError) as exc: errors.append(f"{game['player']}: {exc}")
    return records,errors,skipped

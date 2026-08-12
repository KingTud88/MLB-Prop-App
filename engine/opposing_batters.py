from __future__ import annotations

from functools import lru_cache
import numpy as np
import pandas as pd
import requests

MLB_API = "https://statsapi.mlb.com/api/v1"
LEAGUE_K_RATE = 0.224


def _risk(rate: float) -> str:
    if rate >= 0.30:
        return "HIGH"
    if rate >= 0.25:
        return "ELEVATED"
    return "NORMAL"


def _team_id(team_id: int | None, opponent: str | None) -> int | None:
    if team_id:
        return int(team_id)
    # Keep this local so the module can be used independently of streamlit_app.
    ids = {"LAA":108,"ARI":109,"BAL":110,"BOS":111,"CHC":112,"CIN":113,"CLE":114,"COL":115,"DET":116,"HOU":117,"KCR":118,"LAD":119,"WSH":120,"NYM":121,"ATH":133,"PIT":134,"SDP":135,"SEA":136,"SFG":137,"STL":138,"TBR":139,"TEX":140,"TOR":141,"MIN":142,"PHI":143,"ATL":144,"CHW":145,"MIA":146,"NYY":147,"MIL":158}
    return ids.get(str(opponent or "").upper())


@lru_cache(maxsize=64)
def get_opposing_batters(opponent: str, pitcher_hand: str, season: int, team_id: int | None = None) -> pd.DataFrame:
    """Return active opposing hitters with the platoon K split used by the projection.

    The same MLB Stats API statSplits source used by the projection engine is used here,
    so the visible table cannot silently diverge from the matchup input.
    """
    tid = _team_id(team_id, opponent)
    hand = str(pitcher_hand or "").upper()
    sit = "vr" if hand == "R" else "vl" if hand == "L" else None
    if not tid or not sit:
        return pd.DataFrame(columns=["Batter", "Hand", "K% vs Pitcher", "PA", "Risk"])

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "User-Agent": "StrikeOutKing9000/3.5"})
    try:
        roster = session.get(f"{MLB_API}/teams/{tid}/roster", params={"rosterType":"active","season":season}, timeout=12)
        roster.raise_for_status()
        people = [x for x in roster.json().get("roster", []) if x.get("person", {}).get("id") and x.get("position", {}).get("code") != "1"]
        ids = [int(x["person"]["id"]) for x in people]
        handed = {int(x["person"]["id"]): str(x.get("person", {}).get("batSide", {}).get("code", "")) for x in people}
        names = {int(x["person"]["id"]): x.get("person", {}).get("fullName", "Unknown") for x in people}
        rows = []
        for start in range(0, len(ids), 20):
            batch = ids[start:start + 20]
            response = session.get(f"{MLB_API}/people", params={"personIds": ",".join(map(str, batch)), "hydrate": f"stats(group=hitting,type=statSplits,sitCodes={sit},season={season})"}, timeout=15)
            response.raise_for_status()
            for person in response.json().get("people", []):
                pid = int(person.get("id"))
                person_bat_side = str(((person.get("batSide") or {}).get("code")) or handed.get(pid, ""))
                found = False
                for block in person.get("stats", []):
                    for split in block.get("splits", []):
                        stat = split.get("stat", {}) or {}
                        pa = float(stat.get("plateAppearances", 0) or 0)
                        so = float(stat.get("strikeOuts", 0) or 0)
                        if pa <= 0:
                            continue
                        rate = float(np.clip(so / pa, 0.0, 1.0))
                        rows.append({"Batter": names.get(pid, person.get("fullName", "Unknown")), "Hand": person_bat_side, "K% vs Pitcher": rate, "PA": pa, "Risk": _risk(rate)})
                        found = True
                if not found:
                    continue
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(columns=["Batter", "Hand", "K% vs Pitcher", "PA", "Risk"])
        return df.sort_values(["K% vs Pitcher", "PA"], ascending=[False, False]).drop_duplicates("Batter").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["Batter", "Hand", "K% vs Pitcher", "PA", "Risk"])


def matchup_summary(batters: pd.DataFrame) -> dict[str, float | int]:
    if batters.empty:
        return {"k_rate": LEAGUE_K_RATE, "pa": 0, "high": 0, "elevated": 0}
    pa = pd.to_numeric(batters["PA"], errors="coerce").fillna(0.0)
    rates = pd.to_numeric(batters["K% vs Pitcher"], errors="coerce").fillna(LEAGUE_K_RATE)
    total_pa = float(pa.sum())
    rate = float((rates * pa).sum() / total_pa) if total_pa else LEAGUE_K_RATE
    return {"k_rate": rate, "pa": int(total_pa), "high": int((batters["Risk"] == "HIGH").sum()), "elevated": int((batters["Risk"] == "ELEVATED").sum())}

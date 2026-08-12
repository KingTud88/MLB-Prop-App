from __future__ import annotations

from functools import lru_cache
import numpy as np
import pandas as pd
import requests

MLB_API = "https://statsapi.mlb.com/api/v1"
LEAGUE_K_RATE = 0.224
LEAGUE_HIT_RATE = 0.235
LINEUP_SPLIT_PRIOR_PA = 60.0


COLUMNS = ["Batter", "Hand", "Lineup Spot", "K% vs Pitcher", "H/PA vs Pitcher", "PA", "Risk", "Split Available"]


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


@lru_cache(maxsize=128)
def get_opposing_batters(
    opponent: str,
    pitcher_hand: str,
    season: int,
    team_id: int | None = None,
    batter_ids: tuple[int, ...] = (),
    lineup_spots: tuple[tuple[int, int], ...] = (),
) -> pd.DataFrame:
    """Return opponent hitters with the pitcher-hand K split used by the model.

    When ``batter_ids`` contains a posted nine-man lineup, only those hitters are
    used and the returned table stays in batting-order order. Without a confirmed
    lineup, the function safely falls back to the active roster.
    """
    tid = _team_id(team_id, opponent)
    hand = str(pitcher_hand or "").upper()
    sit = "vr" if hand == "R" else "vl" if hand == "L" else None
    if not tid or not sit:
        return pd.DataFrame(columns=COLUMNS)

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "User-Agent": "StrikeOutKing9000/3.6"})
    confirmed_ids = tuple(int(x) for x in batter_ids if x)
    slot_map = {int(pid): int(spot) for pid, spot in lineup_spots}
    try:
        names: dict[int, str] = {}
        handed: dict[int, str] = {}
        if confirmed_ids:
            ids = list(dict.fromkeys(confirmed_ids))
        else:
            roster = session.get(
                f"{MLB_API}/teams/{tid}/roster",
                params={"rosterType": "active", "season": season},
                timeout=12,
            )
            roster.raise_for_status()
            people = [
                x for x in roster.json().get("roster", [])
                if x.get("person", {}).get("id") and x.get("position", {}).get("code") != "1"
            ]
            ids = [int(x["person"]["id"]) for x in people]
            names = {int(x["person"]["id"]): x.get("person", {}).get("fullName", "Unknown") for x in people}
            handed = {
                int(x["person"]["id"]): str(x.get("person", {}).get("batSide", {}).get("code", ""))
                for x in people
            }

        rows: list[dict[str, object]] = []
        seen: set[int] = set()
        for start in range(0, len(ids), 20):
            batch = ids[start:start + 20]
            response = session.get(
                f"{MLB_API}/people",
                params={
                    "personIds": ",".join(map(str, batch)),
                    "hydrate": f"stats(group=hitting,type=statSplits,sitCodes={sit},season={season})",
                },
                timeout=15,
            )
            response.raise_for_status()
            for person in response.json().get("people", []):
                pid = int(person.get("id"))
                name = person.get("fullName") or names.get(pid, "Unknown")
                person_bat_side = str(((person.get("batSide") or {}).get("code")) or handed.get(pid, ""))
                best_pa = -1.0
                best_rate: float | None = None
                best_hit_rate: float | None = None
                for block in person.get("stats", []):
                    for split in block.get("splits", []):
                        stat = split.get("stat", {}) or {}
                        pa = float(stat.get("plateAppearances", 0) or 0)
                        so = float(stat.get("strikeOuts", 0) or 0)
                        hits = float(stat.get("hits", 0) or 0)
                        if pa <= 0:
                            continue
                        rate = float(np.clip(so / pa, 0.0, 1.0))
                        hit_rate = float(np.clip(hits / pa, 0.0, 1.0))
                        if pa > best_pa:
                            best_pa = pa
                            best_rate = rate
                            best_hit_rate = hit_rate
                if best_rate is not None:
                    rows.append({
                        "Batter": name,
                        "Hand": person_bat_side,
                        "Lineup Spot": slot_map.get(pid, np.nan),
                        "K% vs Pitcher": best_rate,
                        "H/PA vs Pitcher": LEAGUE_HIT_RATE if best_hit_rate is None else best_hit_rate,
                        "PA": best_pa,
                        "Risk": _risk(best_rate),
                        "Split Available": True,
                    })
                    seen.add(pid)
                elif confirmed_ids:
                    # Keep a posted lineup intact. The league baseline is safer than
                    # dropping a rookie/low-PA hitter and over-weighting the others.
                    rows.append({
                        "Batter": name,
                        "Hand": person_bat_side,
                        "Lineup Spot": slot_map.get(pid, np.nan),
                        "K% vs Pitcher": LEAGUE_K_RATE,
                        "H/PA vs Pitcher": LEAGUE_HIT_RATE,
                        "PA": 0.0,
                        "Risk": _risk(LEAGUE_K_RATE),
                        "Split Available": False,
                    })
                    seen.add(pid)

        if confirmed_ids:
            # A missing person payload should also degrade safely rather than
            # silently turning a nine-man lineup into eight hitters.
            for pid in confirmed_ids:
                if pid in seen:
                    continue
                rows.append({
                    "Batter": names.get(pid, f"MLB ID {pid}"),
                    "Hand": handed.get(pid, ""),
                    "Lineup Spot": slot_map.get(pid, np.nan),
                    "K% vs Pitcher": LEAGUE_K_RATE,
                    "PA": 0.0,
                    "Risk": _risk(LEAGUE_K_RATE),
                    "Split Available": False,
                })

        df = pd.DataFrame(rows, columns=COLUMNS)
        if df.empty:
            return pd.DataFrame(columns=COLUMNS)
        df = df.drop_duplicates("Batter", keep="first")
        if confirmed_ids and df["Lineup Spot"].notna().any():
            return df.sort_values(["Lineup Spot", "Batter"]).reset_index(drop=True)
        return df.sort_values(["K% vs Pitcher", "PA"], ascending=[False, False]).reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=COLUMNS)


def matchup_summary(batters: pd.DataFrame, confirmed_lineup: bool = False) -> dict[str, float | int | bool]:
    if batters.empty:
        return {"k_rate": LEAGUE_K_RATE, "hit_rate": LEAGUE_HIT_RATE, "pa": 0, "high": 0, "elevated": 0, "batters": 0, "confirmed": False}
    pa = pd.to_numeric(batters["PA"], errors="coerce").fillna(0.0).clip(lower=0.0)
    rates = pd.to_numeric(batters["K% vs Pitcher"], errors="coerce").fillna(LEAGUE_K_RATE).clip(0.0, 1.0)
    hit_rates = pd.to_numeric(batters.get("H/PA vs Pitcher", LEAGUE_HIT_RATE), errors="coerce").fillna(LEAGUE_HIT_RATE).clip(0.0, 1.0)
    total_pa = float(pa.sum())

    if confirmed_lineup:
        # A posted batting order should represent all nine hitters rather than
        # letting the largest historical split sample dominate the matchup.
        # Shrink each hitter independently, then average the lineup.
        adjusted = (rates * pa + LEAGUE_K_RATE * LINEUP_SPLIT_PRIOR_PA) / (pa + LINEUP_SPLIT_PRIOR_PA)
        adjusted_hits = (hit_rates * pa + LEAGUE_HIT_RATE * LINEUP_SPLIT_PRIOR_PA) / (pa + LINEUP_SPLIT_PRIOR_PA)
        rate = float(adjusted.mean()) if len(adjusted) else LEAGUE_K_RATE
        hit_rate = float(adjusted_hits.mean()) if len(adjusted_hits) else LEAGUE_HIT_RATE
    else:
        rate = float((rates * pa).sum() / total_pa) if total_pa else LEAGUE_K_RATE
        hit_rate = float((hit_rates * pa).sum() / total_pa) if total_pa else LEAGUE_HIT_RATE

    return {
        "k_rate": float(np.clip(rate, 0.08, 0.45)),
        "hit_rate": float(np.clip(hit_rate, 0.12, 0.36)),
        "pa": int(total_pa),
        "high": int((batters["Risk"] == "HIGH").sum()),
        "elevated": int((batters["Risk"] == "ELEVATED").sum()),
        "batters": int(len(batters)),
        "confirmed": bool(confirmed_lineup),
    }

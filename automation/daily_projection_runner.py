from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from engine.projection_engine import ProjectionEngine

BASE = "https://statsapi.mlb.com/api/v1"
APP_VERSION = "3.2.0"
EASTERN = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "projection_log.csv"
TEAM_ABBR = {
    108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",115:"COL",
    116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSH",121:"NYM",133:"ATH",134:"PIT",
    135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",140:"TEX",141:"TOR",142:"MIN",
    143:"PHI",144:"ATL",145:"CHW",146:"MIA",147:"NYY",158:"MIL",
}
PARK_K_FACTOR = {"Coors Field":.94,"T-Mobile Park":1.05,"Petco Park":1.03,"Oracle Park":1.02,
                 "Dodger Stadium":1.01,"Yankee Stadium":.99,"Fenway Park":.98,"Wrigley Field":1.00}
SESSION = requests.Session()
SESSION.headers.update({"Accept":"application/json", "User-Agent":f"StrikeOutKing9000/{APP_VERSION}"})


def get_json(endpoint: str, params: dict) -> dict:
    r = SESSION.get(f"{BASE}/{endpoint}", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("Unexpected MLB response")
    return data


def parse_ip(v: object) -> float:
    try:
        whole, frac = str(v).split(".")
        return int(whole) + int(frac) / 3.0
    except Exception:
        return 0.0


def weighted(series: pd.Series, half: float, fallback: float) -> float:
    x = pd.to_numeric(series, errors="coerce").dropna().to_numpy(float)
    if not len(x):
        return fallback
    age = np.arange(len(x) - 1, -1, -1)
    w = 0.5 ** (age / half)
    return float(np.average(x, weights=w))


def shrink(rate: float, opp: float, prior: float = .224, weight: float = 120) -> float:
    return (rate * opp + prior * weight) / max(opp + weight, 1)


def game_log(pitcher_id: int, season: int) -> pd.DataFrame:
    data = get_json(f"people/{pitcher_id}/stats", {"stats":"gameLog", "group":"pitching", "season":season, "gameType":"R"})
    rows = []
    for block in data.get("stats", []):
        for split in block.get("splits", []):
            s = split.get("stat", {})
            rows.append({
                "date": pd.to_datetime(split.get("date"), errors="coerce"),
                "bf": float(s.get("battersFaced", 0) or 0),
                "k": float(s.get("strikeOuts", 0) or 0),
                "pitches": float(s.get("numberOfPitches", 0) or 0),
                "outs": parse_ip(s.get("inningsPitched", "0.0")) * 3,
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values("date")


def features(log: pd.DataFrame, venue: str) -> dict[str, float]:
    starts = log.tail(35).copy()
    total_bf = float(starts.bf.sum())
    raw_k = float(starts.k.sum() / max(total_bf, 1))
    pitcher_k = float(np.clip(shrink(raw_k, total_bf), .05, .45))
    bf = weighted(starts.bf, 5, 22)
    pitches = weighted(starts.pitches, 5, 88)
    workload = float(np.clip(92 / max(pitches, 75), .78, 1.12))
    return {
        "pitcher_k_pct": pitcher_k,
        "opponent_k_pct": .224,
        "handedness_factor": 1.0,
        "arsenal_factor": 1.0,
        "park_factor": PARK_K_FACTOR.get(venue, 1.0),
        "umpire_factor": 1.0,
        "weather_factor": 1.0,
        "expected_bf": float(np.clip(bf * workload, 10, 35)),
        "bf_sd": float(np.clip(starts.bf.std(ddof=1) if len(starts) > 2 else 3.5, 1, 7)),
        "rest_factor": 1.0,
        "historical_k_sd": float(np.clip(starts.k.std(ddof=1) if len(starts) > 2 else 2.0, .75, 4.5)),
        "historical_games": int(len(starts)),
        "lineup_batters": 0,
        "arsenal_sample_size": 0,
        "weather_available": 0,
        "umpire_available": 0,
    }


def schedule(day: str) -> list[dict]:
    data = get_json("schedule", {"sportId":1, "date":day, "hydrate":"probablePitcher,team,venue"})
    rows = []
    for block in data.get("dates", []):
        for game in block.get("games", []):
            teams = game.get("teams", {})
            for side, other in (("away", "home"), ("home", "away")):
                node = teams.get(side, {}) or {}
                opp = teams.get(other, {}) or {}
                pitcher = node.get("probablePitcher") or {}
                if not pitcher.get("id"):
                    continue
                tn = node.get("team", {})
                on = opp.get("team", {})
                rows.append({
                    "game_pk": int(game.get("gamePk", 0)),
                    "game_date": day,
                    "pitcher_id": int(pitcher["id"]),
                    "player": pitcher.get("fullName", "Unknown"),
                    "team": TEAM_ABBR.get(tn.get("id"), tn.get("abbreviation", "UNK")),
                    "opponent": TEAM_ABBR.get(on.get("id"), on.get("abbreviation", "UNK")),
                    "venue": game.get("venue", {}).get("name", "Unknown"),
                    "game_time": game.get("gameDate", ""),
                    "status": game.get("status", {}).get("detailedState", "Scheduled"),
                })
    return rows


def project(row: dict) -> dict | None:
    log = game_log(row["pitcher_id"], datetime.fromisoformat(row["game_date"]).year)
    if log.empty:
        log = game_log(row["pitcher_id"], datetime.fromisoformat(row["game_date"]).year - 1)
    if log.empty:
        return None
    f = features(log, row["venue"])
    seed = int(hashlib.sha256(f"{row['game_pk']}:{row['pitcher_id']}|{row['game_time']}|{APP_VERSION}".encode()).hexdigest()[:8], 16)
    result = ProjectionEngine(seed=seed).project(f, draws=25000, lines=tuple(float(x) for x in range(3, 11)))
    now = datetime.now(timezone.utc).isoformat()
    raw_sim = result.metadata.get("raw_simulation_probabilities", result.simulation_probabilities)
    raw_math = result.metadata.get("raw_mathematical_probabilities", result.mathematical_probabilities)
    out = {
        "game_pk": row["game_pk"], "game_date": row["game_date"], "pitcher_id": row["pitcher_id"],
        "player": row["player"], "team": row["team"], "opponent": row["opponent"], "venue": row["venue"],
        "game_time": row["game_time"], "captured_at_utc": now, "app_version": APP_VERSION,
        "projection": result.ensemble_mean, "k_sd": result.ensemble_sd,
        "k_range_low": int(np.quantile(result.simulation_samples, .10)),
        "k_range_high": int(np.quantile(result.simulation_samples, .90)),
        "confidence": "High" if result.confidence >= .75 else "Medium" if result.confidence >= .60 else "Low",
        "data_quality": int(round(result.data_quality)), "simulation_draws": 25000,
        "opponent_k_pct": float(f.get("opponent_k_pct", .224)) * 100.0, "pitch_limit": 92, "umpire_k_factor": 1.0,
        "weather_factor": 1.0, "rest_factor": 1.0, "actual_strikeouts": np.nan, "resolved_at_utc": "",
    }
    for line in range(3, 11):
        out[f"sim_{line}p"] = raw_sim.get(float(line), np.nan)
        out[f"math_{line}p"] = raw_math.get(float(line), np.nan)
    return out


def row_has_complete_paths(row: pd.Series) -> bool:
    return all(pd.notna(row.get(f"sim_{line}p")) and pd.notna(row.get(f"math_{line}p")) for line in range(3, 11))


def row_is_pregame(row: pd.Series, now: datetime) -> bool:
    try:
        game_time = pd.to_datetime(row.get("game_time"), utc=True, errors="coerce")
        return bool(pd.notna(game_time) and game_time.to_pydatetime() > now)
    except Exception:
        return False


def fill_missing_pregame_paths(frame: pd.DataFrame) -> int:
    """Complete two-path probabilities only for games that have not started.

    We deliberately do not reconstruct missing probabilities for finished games:
    using today's/postgame data would contaminate the historical calibration set.
    """
    if frame.empty:
        return 0
    now = datetime.now(timezone.utc)
    updated = 0
    for idx in frame.index:
        row = frame.loc[idx]
        if row_has_complete_paths(row) or not row_is_pregame(row, now):
            continue
        try:
            projected = project({
                "game_pk": int(row["game_pk"]),
                "game_date": str(row["game_date"]),
                "pitcher_id": int(row["pitcher_id"]),
                "player": row.get("player", "Unknown"),
                "team": row.get("team", "UNK"),
                "opponent": row.get("opponent", "UNK"),
                "venue": row.get("venue", "Unknown"),
                "game_time": row.get("game_time", ""),
                "status": row.get("status", "Scheduled"),
            })
        except Exception as exc:
            print(f"Pregame path refresh failed for {row.get('player', 'Unknown')} ({row.get('game_pk')}): {exc}")
            continue
        if not projected:
            continue
        for line in range(3, 11):
            frame.at[idx, f"sim_{line}p"] = projected[f"sim_{line}p"]
            frame.at[idx, f"math_{line}p"] = projected[f"math_{line}p"]
        updated += 1
    return updated


def resolve_row(row: pd.Series) -> tuple[object, str]:
    if pd.notna(row.get("actual_strikeouts")):
        return row.get("actual_strikeouts"), str(row.get("resolved_at_utc") or "")
    if pd.isna(row.get("game_pk")) or pd.isna(row.get("pitcher_id")):
        return np.nan, ""
    try:
        data = get_json(f"game/{int(row['game_pk'])}/boxscore", {})
        status = data.get("gameData", {}).get("status", {})
        if status.get("abstractGameState") != "Final":
            return np.nan, ""
        player = data.get("teams", {}).get("away", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")
        if not player:
            player = data.get("teams", {}).get("home", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")
        ks = (player or {}).get("stats", {}).get("pitching", {}).get("strikeOuts")
        if ks is None:
            return np.nan, ""
        return int(ks), datetime.now(timezone.utc).isoformat()
    except (requests.RequestException, ValueError, TypeError):
        return np.nan, ""


def main() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists():
        frame = pd.read_csv(LOG_PATH)
    else:
        frame = pd.DataFrame()

    # Resolve completed games first so calibration sees only genuinely finished outcomes.
    if not frame.empty:
        for idx in frame.index:
            actual, resolved = resolve_row(frame.loc[idx])
            if pd.notna(actual):
                frame.at[idx, "actual_strikeouts"] = actual
                frame.at[idx, "resolved_at_utc"] = resolved

    # Capture the current Eastern slate. Deduplication is by game + pitcher so reruns are safe.
    today = datetime.now(EASTERN).date()
    rows = schedule(today.isoformat())
    existing = set()
    if not frame.empty and {"game_pk", "pitcher_id"}.issubset(frame.columns):
        existing = set(zip(pd.to_numeric(frame.game_pk, errors="coerce"), pd.to_numeric(frame.pitcher_id, errors="coerce")))
    new_rows = []
    for row in rows:
        key = (row["game_pk"], row["pitcher_id"])
        if key in existing:
            continue
        try:
            projected = project(row)
        except Exception as exc:
            print(f"Projection failed for {row['player']} ({row['game_pk']}): {exc}")
            continue
        if projected:
            new_rows.append(projected)

    if new_rows:
        frame = pd.concat([frame, pd.DataFrame(new_rows)], ignore_index=True)

    # Some rows were captured before the two-path columns were introduced. Refresh
    # only still-future games; never reconstruct a finished pregame snapshot with
    # postgame information because that would leak future data into calibration.
    refreshed = fill_missing_pregame_paths(frame)

    # Normalize the schema so old logs remain compatible with the calibration module.
    for line in range(3, 11):
        for prefix in ("sim", "math"):
            col = f"{prefix}_{line}p"
            if col not in frame.columns:
                frame[col] = np.nan
    for col in ["actual_strikeouts", "resolved_at_utc"]:
        if col not in frame.columns:
            frame[col] = np.nan if col == "actual_strikeouts" else ""
    frame.to_csv(LOG_PATH, index=False)
    print(f"projection log rows={len(frame)} new={len(new_rows)} pregame_path_refreshes={refreshed}")


if __name__ == "__main__":
    main()

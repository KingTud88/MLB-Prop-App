from __future__ import annotations

import hashlib
import math
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from engine.projection_engine import ProjectionEngine
from engine.opposing_batters import get_opposing_batters, matchup_summary
from engine.hits_allowed import project_hits_allowed
from engine.outs_projection import project_total_outs
from engine.starter_history import HISTORY_SEMANTICS, TARGET_STARTER_HISTORY, combine_starter_history, starter_only
from engine.weather_risk import WeatherDelayRisk, fetch_weather_delay_risk

BASE = "https://statsapi.mlb.com/api/v1"
APP_VERSION = "3.5.0"
PROBABILITY_SEMANTICS = "milestone-ceil-v1"
EASTERN = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "projection_log.csv"
OBS_LOG_PATH = ROOT / "data" / "starter_observation_log.csv"
OBS_COLUMNS = [
    "game_pk", "game_date", "pitcher_id", "player", "team", "opponent", "venue", "game_time",
    "captured_at_utc", "reason", "history_semantics", "history_games_available_at_capture",
    "actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches",
    "resolved_at_utc",
]
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


LIVE_BASE = "https://statsapi.mlb.com/api/v1.1"


def get_json(endpoint: str, params: dict) -> dict:
    # MLB's live-feed endpoint is the reliable source for final game boxscores.
    # Keep v1 for schedule/people/stats calls, but transparently route game
    # boxscore reads through v1.1 and return the shape our resolvers expect.
    if endpoint.startswith("game/") and endpoint.endswith("/boxscore"):
        live_endpoint = endpoint[:-len("boxscore")] + "feed/live"
        r = SESSION.get(f"{LIVE_BASE}/{live_endpoint}", params=params, timeout=30)
        r.raise_for_status()
        live = r.json()
        if not isinstance(live, dict):
            raise ValueError("Unexpected MLB live-feed response")
        return {
            "gameData": live.get("gameData", {}),
            "teams": live.get("liveData", {}).get("boxscore", {}).get("teams", {}),
        }
    base = LIVE_BASE if endpoint.startswith("game/") and endpoint.endswith("/feed/live") else BASE
    r = SESSION.get(f"{base}/{endpoint}", params=params, timeout=30)
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
                "hits": float(s.get("hits", 0) or 0),
                "pitches": float(s.get("numberOfPitches", 0) or 0),
                "outs": parse_ip(s.get("inningsPitched", "0.0")) * 3,
                "games_started": int(float(s.get("gamesStarted", 0) or 0)),
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return starter_only(frame)


def load_observation_log() -> pd.DataFrame:
    if not OBS_LOG_PATH.exists():
        return pd.DataFrame(columns=OBS_COLUMNS)
    try:
        frame = pd.read_csv(OBS_LOG_PATH)
    except Exception:
        return pd.DataFrame(columns=OBS_COLUMNS)
    for col in OBS_COLUMNS:
        if col not in frame.columns:
            frame[col] = np.nan if col.startswith("actual_") or col == "history_games_available_at_capture" else ""
    return frame[OBS_COLUMNS].copy()


def save_observation_log(frame: pd.DataFrame) -> None:
    OBS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    for col in OBS_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan if col.startswith("actual_") or col == "history_games_available_at_capture" else ""
    out[OBS_COLUMNS].to_csv(OBS_LOG_PATH, index=False)


def record_history_only(row: dict, reason: str = "no usable starter history", history_games: int = 0) -> bool:
    frame = load_observation_log()
    if not frame.empty and {"game_pk", "pitcher_id"}.issubset(frame.columns):
        same = (
            pd.to_numeric(frame["game_pk"], errors="coerce").eq(int(row["game_pk"]))
            & pd.to_numeric(frame["pitcher_id"], errors="coerce").eq(int(row["pitcher_id"]))
        )
        if bool(same.any()):
            return False
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "game_pk": int(row["game_pk"]), "game_date": str(row["game_date"]), "pitcher_id": int(row["pitcher_id"]),
        "player": row.get("player", "Unknown"), "team": row.get("team", "UNK"), "opponent": row.get("opponent", "UNK"),
        "venue": row.get("venue", "Unknown"), "game_time": row.get("game_time", ""), "captured_at_utc": now,
        "reason": reason, "history_semantics": HISTORY_SEMANTICS,
        "history_games_available_at_capture": int(history_games),
        "actual_strikeouts": np.nan, "actual_hits_allowed": np.nan, "actual_outs": np.nan,
        "actual_batters_faced": np.nan, "actual_pitches": np.nan, "resolved_at_utc": "",
    }
    frame = pd.concat([frame, pd.DataFrame([record])], ignore_index=True)
    save_observation_log(frame)
    return True


def observation_history(pitcher_id: int) -> pd.DataFrame:
    frame = load_observation_log()
    if frame.empty:
        return pd.DataFrame()
    mask = pd.to_numeric(frame["pitcher_id"], errors="coerce").eq(int(pitcher_id))
    data = frame.loc[mask].copy()
    required = ["actual_batters_faced", "actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_pitches"]
    for col in required:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=required)
    if data.empty:
        return pd.DataFrame()
    return pd.DataFrame({
        "date": pd.to_datetime(data["game_date"], errors="coerce"),
        "bf": data["actual_batters_faced"].to_numpy(float),
        "k": data["actual_strikeouts"].to_numpy(float),
        "hits": data["actual_hits_allowed"].to_numpy(float),
        "pitches": data["actual_pitches"].to_numpy(float),
        "outs": data["actual_outs"].to_numpy(float),
        "games_started": np.ones(len(data), dtype=int),
    }).dropna(subset=["date"])


def supplement_with_observations(log: pd.DataFrame, pitcher_id: int) -> pd.DataFrame:
    observed = observation_history(pitcher_id)
    if observed.empty:
        return log
    if log.empty:
        return observed.sort_values("date").tail(TARGET_STARTER_HISTORY).reset_index(drop=True)
    existing_dates = set(pd.to_datetime(log["date"], errors="coerce").dt.normalize().dropna())
    observed_dates = pd.to_datetime(observed["date"], errors="coerce").dt.normalize()
    observed = observed.loc[~observed_dates.isin(existing_dates)].copy()
    if observed.empty:
        return log
    merged = pd.concat([log, observed], ignore_index=True)
    return merged.sort_values("date").tail(TARGET_STARTER_HISTORY).reset_index(drop=True)


def resolve_observation_row(row: pd.Series) -> dict[str, object]:
    actuals = [row.get("actual_strikeouts"), row.get("actual_hits_allowed"), row.get("actual_outs"), row.get("actual_batters_faced"), row.get("actual_pitches")]
    if all(pd.notna(value) for value in actuals):
        return {}
    if pd.isna(row.get("game_pk")) or pd.isna(row.get("pitcher_id")):
        return {}
    try:
        data = get_json(f"game/{int(row['game_pk'])}/boxscore", {})
        status = data.get("gameData", {}).get("status", {})
        if status.get("abstractGameState") != "Final":
            return {}
        player = data.get("teams", {}).get("away", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")
        if not player:
            player = data.get("teams", {}).get("home", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")
        pitching = (player or {}).get("stats", {}).get("pitching", {})
        innings = pitching.get("inningsPitched")
        outs = int(round(parse_ip(innings) * 3)) if innings is not None else np.nan
        result = {
            "actual_strikeouts": pitching.get("strikeOuts", np.nan),
            "actual_hits_allowed": pitching.get("hits", np.nan),
            "actual_outs": outs,
            "actual_batters_faced": pitching.get("battersFaced", np.nan),
            "actual_pitches": pitching.get("numberOfPitches", np.nan),
            "resolved_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        if all(pd.isna(result[key]) for key in ("actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches")):
            return {}
        return result
    except (requests.RequestException, ValueError, TypeError):
        return {}


def resolve_observation_log() -> int:
    frame = load_observation_log()
    if frame.empty:
        return 0
    updated = 0
    for idx in frame.index:
        result = resolve_observation_row(frame.loc[idx])
        if not result:
            continue
        for key, value in result.items():
            frame.at[idx, key] = value
        updated += 1
    if updated:
        save_observation_log(frame)
    return updated


@lru_cache(maxsize=64)
def venue_coordinates(venue_id: int) -> tuple[float, float] | None:
    if not venue_id:
        return None
    try:
        data = get_json(f"venues/{int(venue_id)}", {})
        venues = data.get("venues") or []
        coords = ((venues[0].get("location") or {}).get("defaultCoordinates") or {}) if venues else {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        return (float(lat), float(lon)) if lat is not None and lon is not None else None
    except (requests.RequestException, ValueError, TypeError, IndexError):
        return None


@lru_cache(maxsize=128)
def game_weather(venue_id: int, game_time: str) -> WeatherDelayRisk:
    coords = venue_coordinates(int(venue_id or 0))
    if not coords:
        return WeatherDelayRisk("UNKNOWN", "", None, None, None, "Venue coordinates unavailable for weather risk.", False)
    return fetch_weather_delay_risk(coords[0], coords[1], str(game_time or ""))


def weather_snapshot_fields(venue_id: int, game_time: str) -> dict[str, object]:
    risk = game_weather(int(venue_id or 0), str(game_time or ""))
    return {
        "weather_delay_risk": risk.level,
        "weather_icon": risk.icon,
        "weather_precip_probability": np.nan if risk.precip_probability is None else risk.precip_probability,
        "weather_precip_mm": np.nan if risk.precipitation_mm is None else risk.precipitation_mm,
        "weather_summary": risk.summary,
    }


def pitcher_hand(pitcher_id: int) -> str:
    try:
        data = get_json(f"people/{int(pitcher_id)}", {})
        people = data.get("people") or []
        return str(((people[0].get("pitchingHand") or {}).get("code")) or "").upper() if people else ""
    except (requests.RequestException, ValueError, TypeError, IndexError):
        return ""


def matchup_k_rate(opponent: str, pitcher_id: int, season: int, opponent_team_id: int | None = None) -> tuple[float, int, int]:
    hand = pitcher_hand(pitcher_id)
    if hand not in {"R", "L"}:
        return .224, 0, 0
    batters = get_opposing_batters(opponent, hand, season, opponent_team_id)
    summary = matchup_summary(batters)
    return float(summary["k_rate"]), int(summary["pa"]), int(len(batters))


def features(log: pd.DataFrame, venue: str, opponent_k_pct: float = .224) -> dict[str, float]:
    starts = log.tail(35).copy()
    total_bf = float(starts.bf.sum())
    raw_k = float(starts.k.sum() / max(total_bf, 1))
    pitcher_k = float(np.clip(shrink(raw_k, total_bf), .05, .45))
    bf = weighted(starts.bf, 5, 22)
    pitches = weighted(starts.pitches, 5, 88)
    workload = float(np.clip(92 / max(pitches, 75), .78, 1.12))
    return {
        "pitcher_k_pct": pitcher_k,
        "opponent_k_pct": float(np.clip(opponent_k_pct, .08, .45)),
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
            venue_node = game.get("venue", {}) or {}
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
                    "opponent_team_id": int(on.get("id")) if on.get("id") else None,
                    "venue_id": int(venue_node.get("id", 0) or 0),
                    "venue": venue_node.get("name", "Unknown"),
                    "game_time": game.get("gameDate", ""),
                    "status": game.get("status", {}).get("detailedState", "Scheduled"),
                })
    return rows


def project(row: dict) -> dict | None:
    season = datetime.fromisoformat(row["game_date"]).year
    current_log = game_log(row["pitcher_id"], season)
    prior_log = pd.DataFrame()
    if len(current_log) < TARGET_STARTER_HISTORY:
        prior_log = game_log(row["pitcher_id"], season - 1)
    log = combine_starter_history(current_log, prior_log)
    log = supplement_with_observations(log, row["pitcher_id"])
    if log.empty:
        record_history_only(row, history_games=0)
        return None
    opponent_k_pct, matchup_pa, matchup_batters = matchup_k_rate(
        row["opponent"], row["pitcher_id"], season, row.get("opponent_team_id")
    )
    f = features(log, row["venue"], opponent_k_pct=opponent_k_pct)
    seed = int(hashlib.sha256(f"{row['game_pk']}:{row['pitcher_id']}|{row['game_time']}|{APP_VERSION}".encode()).hexdigest()[:8], 16)
    result = ProjectionEngine(seed=seed).project(f, draws=25000, lines=tuple(float(x) for x in range(3, 11)))
    hits = project_hits_allowed(
        log,
        expected_bf=f["expected_bf"],
        seed=seed ^ 0x5A17,
        draws=25000,
        lines=(3.5, 4.5, 5.5, 6.5, 7.5, 8.5),
    )
    outs = project_total_outs(
        log,
        seed=seed ^ 0x0A75,
        draws=25000,
        lines=(13.5, 14.5, 15.5, 16.5, 17.5, 18.5),
    )
    now = datetime.now(timezone.utc).isoformat()
    weather = weather_snapshot_fields(int(row.get("venue_id", 0) or 0), str(row.get("game_time", "")))
    raw_sim = result.metadata.get("raw_simulation_probabilities", result.simulation_probabilities)
    raw_math = result.metadata.get("raw_mathematical_probabilities", result.mathematical_probabilities)
    out = {
        "game_pk": row["game_pk"], "game_date": row["game_date"], "pitcher_id": row["pitcher_id"],
        "player": row["player"], "team": row["team"], "opponent": row["opponent"], "venue_id": row.get("venue_id", 0), "venue": row["venue"],
        "game_time": row["game_time"], "captured_at_utc": now, "app_version": APP_VERSION,
        "probability_semantics": PROBABILITY_SEMANTICS,
        "history_semantics": HISTORY_SEMANTICS, "starter_history_games": int(len(log)),
        "projection": result.ensemble_mean, "k_sd": result.ensemble_sd,
        "k_range_low": int(np.quantile(result.simulation_samples, .10)),
        "k_range_high": int(np.quantile(result.simulation_samples, .90)),
        "hits_projection": hits.ensemble_mean, "hits_sd": hits.ensemble_sd,
        "hits_range_low": int(np.quantile(hits.simulation_samples, .10)),
        "hits_range_high": int(np.quantile(hits.simulation_samples, .90)),
        "outs_projection": outs.ensemble_mean, "outs_sd": outs.ensemble_sd,
        "outs_range_low": int(np.quantile(outs.simulation_samples, .10)),
        "outs_range_high": int(np.quantile(outs.simulation_samples, .90)),
        "confidence": "High" if result.confidence >= .75 else "Medium" if result.confidence >= .60 else "Low",
        "data_quality": int(round(result.data_quality)), "simulation_draws": 25000,
        "opponent_k_pct": opponent_k_pct * 100.0, "matchup_pa": matchup_pa, "matchup_batters": matchup_batters,
        "pitch_limit": 92, "umpire_k_factor": 1.0,
        "weather_factor": 1.0, "rest_factor": 1.0,
        **weather,
        "actual_strikeouts": np.nan, "actual_hits_allowed": np.nan, "actual_outs": np.nan, "resolved_at_utc": "",
    }
    for line in range(3, 11):
        out[f"sim_{line}p"] = raw_sim.get(float(line), np.nan)
        out[f"math_{line}p"] = raw_math.get(float(line), np.nan)
    for line in (3.5, 4.5, 5.5, 6.5, 7.5, 8.5):
        key = str(line).replace(".", "_")
        out[f"hits_sim_over_{key}"] = hits.simulation_probabilities.get(line, np.nan)
        out[f"hits_math_over_{key}"] = hits.mathematical_probabilities.get(line, np.nan)
        out[f"hits_over_{key}"] = hits.over_probabilities.get(line, np.nan)
    for line in (13.5, 14.5, 15.5, 16.5, 17.5, 18.5):
        key = str(line).replace(".", "_")
        out[f"outs_sim_over_{key}"] = outs.simulation_probabilities.get(line, np.nan)
        out[f"outs_math_over_{key}"] = outs.mathematical_probabilities.get(line, np.nan)
        out[f"outs_over_{key}"] = outs.over_probabilities.get(line, np.nan)
    return out


def row_has_complete_paths(row: pd.Series) -> bool:
    return all(pd.notna(row.get(f"sim_{line}p")) and pd.notna(row.get(f"math_{line}p")) for line in range(3, 11))


def row_has_current_semantics(row: pd.Series) -> bool:
    return (
        str(row.get("probability_semantics", "")) == PROBABILITY_SEMANTICS
        and str(row.get("history_semantics", "")) == HISTORY_SEMANTICS
    )


def row_is_pregame(row: pd.Series, now: datetime) -> bool:
    try:
        game_time = pd.to_datetime(row.get("game_time"), utc=True, errors="coerce")
        return bool(pd.notna(game_time) and game_time.to_pydatetime() > now)
    except Exception:
        return False


def attach_pregame_weather(frame: pd.DataFrame, announced: list[dict]) -> int:
    if frame.empty or not announced:
        return 0
    now = datetime.now(timezone.utc)
    lookup = {(int(r["game_pk"]), int(r["pitcher_id"])): r for r in announced}
    updated = 0
    for idx in frame.index:
        row = frame.loc[idx]
        if not row_is_pregame(row, now):
            continue
        existing = str(row.get("weather_delay_risk", "") or "").upper()
        if existing in {"NONE", "LOW", "ELEVATED", "HIGH"}:
            continue
        try:
            key = (int(row["game_pk"]), int(row["pitcher_id"]))
        except Exception:
            continue
        scheduled = lookup.get(key)
        if not scheduled:
            continue
        fields = weather_snapshot_fields(int(scheduled.get("venue_id", 0) or 0), str(scheduled.get("game_time", "")))
        frame.at[idx, "venue_id"] = int(scheduled.get("venue_id", 0) or 0)
        for key_name, value in fields.items():
            frame.at[idx, key_name] = value
        updated += 1
    return updated


def fill_missing_pregame_paths(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    now = datetime.now(timezone.utc)
    updated = 0
    for idx in frame.index:
        row = frame.loc[idx]
        needs_hits = pd.isna(row.get("hits_projection"))
        needs_outs = pd.isna(row.get("outs_projection"))
        if ((row_has_complete_paths(row) and row_has_current_semantics(row) and not needs_hits and not needs_outs) or not row_is_pregame(row, now)):
            continue
        try:
            projected = project({
                "game_pk": int(row["game_pk"]),
                "game_date": str(row["game_date"]),
                "pitcher_id": int(row["pitcher_id"]),
                "player": row.get("player", "Unknown"),
                "team": row.get("team", "UNK"),
                "opponent": row.get("opponent", "UNK"),
                "opponent_team_id": int(row["opponent_team_id"]) if pd.notna(row.get("opponent_team_id")) else None,
                "venue_id": int(row["venue_id"]) if pd.notna(row.get("venue_id")) else 0,
                "venue": row.get("venue", "Unknown"),
                "game_time": row.get("game_time", ""),
                "status": row.get("status", "Scheduled"),
            })
        except Exception as exc:
            print(f"Pregame path refresh failed for {row.get('player', 'Unknown')} ({row.get('game_pk')}): {exc}")
            continue
        if not projected:
            continue
        for key, value in projected.items():
            if key.startswith("sim_") or key.startswith("math_") or key.startswith("hits_") or key.startswith("outs_") or key in {"probability_semantics"}:
                frame.at[idx, key] = value
        updated += 1
    return updated


def resolve_row(row: pd.Series) -> tuple[object, object, object, str]:
    if pd.notna(row.get("actual_strikeouts")) and pd.notna(row.get("actual_hits_allowed")) and pd.notna(row.get("actual_outs")):
        return row.get("actual_strikeouts"), row.get("actual_hits_allowed"), row.get("actual_outs"), str(row.get("resolved_at_utc") or "")
    if pd.isna(row.get("game_pk")) or pd.isna(row.get("pitcher_id")):
        return np.nan, np.nan, np.nan, ""
    try:
        data = get_json(f"game/{int(row['game_pk'])}/boxscore", {})
        status = data.get("gameData", {}).get("status", {})
        if status.get("abstractGameState") != "Final":
            return np.nan, np.nan, np.nan, ""
        player = data.get("teams", {}).get("away", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")
        if not player:
            player = data.get("teams", {}).get("home", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")
        pitching = (player or {}).get("stats", {}).get("pitching", {})
        ks = pitching.get("strikeOuts")
        hits = pitching.get("hits")
        innings = pitching.get("inningsPitched")
        outs = int(round(parse_ip(innings) * 3)) if innings is not None else np.nan
        if ks is None and hits is None and pd.isna(outs):
            return np.nan, np.nan, np.nan, ""
        return (int(ks) if ks is not None else np.nan), (int(hits) if hits is not None else np.nan), outs, datetime.now(timezone.utc).isoformat()
    except (requests.RequestException, ValueError, TypeError):
        return np.nan, np.nan, np.nan, ""


def main() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    observation_updates = resolve_observation_log()
    frame = pd.read_csv(LOG_PATH) if LOG_PATH.exists() else pd.DataFrame()

    if not frame.empty:
        for idx in frame.index:
            actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])
            if pd.notna(actual_k):
                frame.at[idx, "actual_strikeouts"] = actual_k
            if pd.notna(actual_hits):
                frame.at[idx, "actual_hits_allowed"] = actual_hits
            if pd.notna(actual_outs):
                frame.at[idx, "actual_outs"] = actual_outs
            if resolved:
                frame.at[idx, "resolved_at_utc"] = resolved

    today = datetime.now(EASTERN).date()
    rows = schedule(today.isoformat())
    weather_refreshes = attach_pregame_weather(frame, rows)
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

    if "probability_semantics" not in frame.columns:
        frame["probability_semantics"] = ""
    refreshed = fill_missing_pregame_paths(frame)

    for line in range(3, 11):
        for prefix in ("sim", "math"):
            col = f"{prefix}_{line}p"
            if col not in frame.columns:
                frame[col] = np.nan
    for col in ["actual_strikeouts", "actual_hits_allowed", "actual_outs", "resolved_at_utc"]:
        if col not in frame.columns:
            frame[col] = np.nan if col != "resolved_at_utc" else ""
    frame.to_csv(LOG_PATH, index=False)
    observations = load_observation_log()
    unresolved_observations = 0 if observations.empty else int(pd.to_numeric(observations["actual_outs"], errors="coerce").isna().sum())
    print(
        f"projection log rows={len(frame)} new={len(new_rows)} pregame_path_refreshes={refreshed} weather_refreshes={weather_refreshes} "
        f"history_observations={len(observations)} observation_resolves={observation_updates} unresolved_observations={unresolved_observations}"
    )


if __name__ == "__main__":
    main()

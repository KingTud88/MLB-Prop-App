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
from engine.lineup_context import LINEUP_ACTIVE_ROSTER, LINEUP_CONFIRMED, get_confirmed_lineup
from engine.hits_allowed import project_hits_allowed
from engine.outs_projection import project_total_outs
from engine.starter_history import HISTORY_SEMANTICS, TARGET_STARTER_HISTORY, combine_starter_history, starter_only
from engine.weather_risk import WeatherDelayRisk, fetch_weather_delay_risk
from engine.workload_context import WORKLOAD_VERSION, WorkloadContext, build_workload_context
from engine.team_leash import build_team_leash_context, candidate_workload_fields

BASE = "https://statsapi.mlb.com/api/v1"
APP_VERSION = "3.7.0"
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
                "history_source": "MLB",
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


def load_projection_context_log() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(LOG_PATH)
    except Exception:
        return pd.DataFrame()


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
        "history_source": np.full(len(data), "OBSERVATION", dtype=object),
    }).dropna(subset=["date"])


def starter_history_provenance(log: pd.DataFrame) -> dict[str, object]:
    """Summarize the actual starter rows used by source without changing the model input."""
    if log.empty:
        return {"source": "NONE", "mlb_games": 0, "observation_games": 0}
    if "history_source" in log.columns:
        source = log["history_source"].fillna("MLB").astype(str).str.upper()
    else:
        source = pd.Series("MLB", index=log.index, dtype=str)
    mlb_games = int(source.eq("MLB").sum())
    observation_games = int(source.eq("OBSERVATION").sum())
    if observation_games and mlb_games:
        label = "MLB_PLUS_OBSERVATIONS"
    elif observation_games:
        label = "OBSERVATIONS_ONLY"
    else:
        label = "MLB_ONLY"
    return {"source": label, "mlb_games": mlb_games, "observation_games": observation_games}


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
        if not people:
            return ""
        hand = people[0].get("pitchHand") or people[0].get("pitchingHand") or {}
        return str(hand.get("code") or "").upper()
    except (requests.RequestException, ValueError, TypeError, IndexError):
        return ""


def matchup_context(
    game_pk: int,
    opponent: str,
    pitcher_id: int,
    season: int,
    opponent_team_id: int | None = None,
) -> dict[str, object]:
    hand = pitcher_hand(pitcher_id)
    if hand not in {"R", "L"}:
        return {"k_rate": .224, "hit_rate": .235, "pa": 0, "batters": 0, "lineup_batters": 0, "source": LINEUP_ACTIVE_ROSTER, "confirmed": False, "lineup_hash": ""}
    lineup = get_confirmed_lineup(int(game_pk), int(opponent_team_id or 0))
    batter_ids = lineup.player_ids if lineup.confirmed else ()
    lineup_spots = lineup.spots if lineup.confirmed else ()
    batters = get_opposing_batters(opponent, hand, season, opponent_team_id, batter_ids, lineup_spots)
    summary = matchup_summary(batters, confirmed_lineup=lineup.confirmed)
    return {
        "k_rate": float(summary["k_rate"]),
        "hit_rate": float(summary.get("hit_rate", .235)),
        "pa": int(summary["pa"]),
        "batters": int(len(batters)),
        "lineup_batters": int(lineup.batter_count if lineup.confirmed else 0),
        "source": lineup.source,
        "confirmed": bool(lineup.confirmed),
        "lineup_hash": lineup.fingerprint,
    }


def matchup_k_rate(opponent: str, pitcher_id: int, season: int, opponent_team_id: int | None = None) -> tuple[float, int, int]:
    """Legacy active-roster wrapper retained for callers/tests that do not have a game id."""
    hand = pitcher_hand(pitcher_id)
    if hand not in {"R", "L"}:
        return .224, 0, 0
    batters = get_opposing_batters(opponent, hand, season, opponent_team_id)
    summary = matchup_summary(batters)
    return float(summary["k_rate"]), int(summary["pa"]), int(len(batters))


def features(
    log: pd.DataFrame,
    venue: str,
    opponent_k_pct: float = .224,
    lineup_batters: int = 0,
    matchup_source: str = LINEUP_ACTIVE_ROSTER,
    workload: WorkloadContext | None = None,
) -> dict[str, float]:
    starts = log.tail(35).copy()
    total_bf = float(starts.bf.sum())
    raw_k = float(starts.k.sum() / max(total_bf, 1))
    pitcher_k = float(np.clip(shrink(raw_k, total_bf), .05, .45))
    workload = workload or build_workload_context(starts)
    return {
        "pitcher_k_pct": pitcher_k,
        "opponent_k_pct": float(np.clip(opponent_k_pct, .08, .45)),
        "handedness_factor": 1.0,
        "arsenal_factor": 1.0,
        "park_factor": PARK_K_FACTOR.get(venue, 1.0),
        "umpire_factor": 1.0,
        "weather_factor": 1.0,
        "expected_bf": float(workload.expected_bf),
        "bf_sd": float(workload.bf_sd),
        # Short-rest handling is already baked into expected exposure. Keep the
        # engine-level factor neutral so the same rest signal is not counted twice.
        "rest_factor": 1.0,
        "historical_k_sd": float(np.clip(starts.k.std(ddof=1) if len(starts) > 2 else 2.0, .75, 4.5)),
        "historical_games": int(len(starts)),
        "lineup_batters": int(lineup_batters),
        "matchup_source": str(matchup_source),
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
                    "team_id": int(tn.get("id")) if tn.get("id") else None,
                    "opponent": TEAM_ABBR.get(on.get("id"), on.get("abbreviation", "UNK")),
                    "opponent_team_id": int(on.get("id")) if on.get("id") else None,
                    "venue_id": int(venue_node.get("id", 0) or 0),
                    "venue": venue_node.get("name", "Unknown"),
                    "game_time": game.get("gameDate", ""),
                    "status": game.get("status", {}).get("detailedState", "Scheduled"),
                })
    return rows


def project(row: dict, matchup_override: dict[str, object] | None = None) -> dict | None:
    season = datetime.fromisoformat(row["game_date"]).year
    current_log = game_log(row["pitcher_id"], season)
    prior_log = pd.DataFrame()
    if len(current_log) < TARGET_STARTER_HISTORY:
        prior_log = game_log(row["pitcher_id"], season - 1)
    log = combine_starter_history(current_log, prior_log)
    log = supplement_with_observations(log, row["pitcher_id"])
    history_provenance = starter_history_provenance(log)
    if log.empty:
        record_history_only(row, history_games=0)
        return None
    workload = build_workload_context(log, row.get("game_time") or row.get("game_date"))
    team_leash = build_team_leash_context(
        load_projection_context_log(), load_observation_log(), str(row.get("team", "UNK")),
        row.get("game_time") or row.get("game_date"),
    )
    team_leash_candidate = candidate_workload_fields(
        team_leash, workload.expected_pitches, workload.expected_bf, workload.expected_outs
    )
    matchup = matchup_override or matchup_context(
        row["game_pk"], row["opponent"], row["pitcher_id"], season, row.get("opponent_team_id")
    )
    opponent_k_pct = float(matchup["k_rate"])
    f = features(
        log,
        row["venue"],
        opponent_k_pct=opponent_k_pct,
        lineup_batters=int(matchup["lineup_batters"]),
        matchup_source=str(matchup["source"]),
        workload=workload,
    )
    seed_version = str(row.get("seed_version") or APP_VERSION)
    seed = int(hashlib.sha256(f"{row['game_pk']}:{row['pitcher_id']}|{row['game_time']}|{seed_version}".encode()).hexdigest()[:8], 16)
    result = ProjectionEngine(seed=seed).project(f, draws=25000, lines=tuple(float(x) for x in range(3, 11)))
    hits = project_hits_allowed(
        log,
        expected_bf=f["expected_bf"],
        bf_sd=workload.bf_sd,
        opponent_hit_rate=float(matchup.get("hit_rate", .235)),
        seed=seed ^ 0x5A17,
        draws=25000,
        lines=(3.5, 4.5, 5.5, 6.5, 7.5, 8.5),
    )
    outs = project_total_outs(
        log,
        expected_outs=workload.expected_outs,
        workload_sd=workload.outs_sd,
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
        "player": row["player"], "team": row["team"], "team_id": row.get("team_id"), "opponent": row["opponent"], "opponent_team_id": row.get("opponent_team_id"), "venue_id": row.get("venue_id", 0), "venue": row["venue"],
        "game_time": row["game_time"], "captured_at_utc": now, "app_version": APP_VERSION,
        "probability_semantics": PROBABILITY_SEMANTICS,
        "history_semantics": HISTORY_SEMANTICS, "starter_history_games": int(len(log)),
        "starter_history_source": str(history_provenance["source"]),
        "starter_history_mlb_games": int(history_provenance["mlb_games"]),
        "starter_history_observation_games": int(history_provenance["observation_games"]),
        **workload.snapshot_fields(),
        **team_leash.snapshot_fields(),
        **team_leash_candidate,
        "workload_preupgrade_projection": np.nan, "workload_preupgrade_hits_projection": np.nan,
        "workload_preupgrade_outs_projection": np.nan, "workload_preupgrade_expected_bf": np.nan,
        "workload_projection_delta_k": np.nan, "workload_projection_delta_hits": np.nan,
        "workload_projection_delta_outs": np.nan, "workload_preupgrade_app_version": "",
        "workload_upgraded_at_utc": "",
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
        "opponent_k_pct": opponent_k_pct * 100.0, "opponent_hit_rate": float(matchup.get("hit_rate", .235)) * 100.0,
        "matchup_pa": int(matchup["pa"]), "matchup_batters": int(matchup["batters"]),
        "lineup_source": str(matchup["source"]), "lineup_confirmed": bool(matchup["confirmed"]),
        "lineup_batters": int(matchup["lineup_batters"]), "lineup_hash": str(matchup["lineup_hash"]),
        "lineup_captured_at_utc": now if bool(matchup["confirmed"]) else "",
        "lineup_preconfirm_projection": np.nan, "lineup_preconfirm_opponent_k_pct": np.nan,
        "lineup_preconfirm_hits_projection": np.nan, "lineup_preconfirm_opponent_hit_rate": np.nan,
        "lineup_projection_delta": np.nan, "lineup_opponent_k_delta": np.nan,
        "lineup_hits_projection_delta": np.nan, "lineup_opponent_hit_delta": np.nan,
        "pitch_limit": float(workload.expected_pitches), "umpire_k_factor": 1.0,
        "weather_factor": 1.0, "rest_factor": 1.0,
        **weather,
        "actual_strikeouts": np.nan, "actual_hits_allowed": np.nan, "actual_outs": np.nan,
        "actual_batters_faced": np.nan, "actual_pitches": np.nan, "resolved_at_utc": "",
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


def attach_pregame_team_leash(frame: pd.DataFrame) -> int:
    """Refresh context-only team leash metadata for still-pregame snapshots.

    The baseball projection fields are never rewritten here. Team context is
    reconstructed from strictly earlier resolved starts, so same-day outcomes
    cannot leak into the current slate.
    """
    if frame.empty:
        return 0
    now = datetime.now(timezone.utc)
    observations = load_observation_log()
    updated = 0
    for idx in frame.index:
        row = frame.loc[idx]
        if not row_is_pregame(row, now):
            continue
        context = build_team_leash_context(
            frame, observations, str(row.get("team", "UNK")), row.get("game_time") or row.get("game_date")
        )
        fields = context.snapshot_fields()
        expected_pitches = pd.to_numeric(pd.Series([row.get("expected_pitches")]), errors="coerce").iloc[0]
        expected_bf = pd.to_numeric(pd.Series([row.get("expected_bf")]), errors="coerce").iloc[0]
        expected_outs = pd.to_numeric(pd.Series([row.get("expected_outs")]), errors="coerce").iloc[0]
        if pd.notna(expected_pitches) and pd.notna(expected_bf) and pd.notna(expected_outs):
            fields.update(candidate_workload_fields(context, float(expected_pitches), float(expected_bf), float(expected_outs)))
        changed = False
        for name, value in fields.items():
            old = row.get(name)
            if pd.isna(value):
                same = pd.isna(old)
            elif isinstance(value, float):
                old_num = pd.to_numeric(pd.Series([old]), errors="coerce").iloc[0]
                same = pd.notna(old_num) and abs(float(old_num) - value) < 1e-12
            else:
                same = str(old) == str(value)
            if not same:
                frame.at[idx, name] = value
                changed = True
        if changed:
            updated += 1
    return updated


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
        try:
            key = (int(row["game_pk"]), int(row["pitcher_id"]))
        except Exception:
            continue
        scheduled = lookup.get(key)
        if not scheduled:
            continue
        fields = weather_snapshot_fields(int(scheduled.get("venue_id", 0) or 0), str(scheduled.get("game_time", "")))
        changed = False
        venue_id = int(scheduled.get("venue_id", 0) or 0)
        old_venue = pd.to_numeric(pd.Series([row.get("venue_id")]), errors="coerce").iloc[0]
        if pd.isna(old_venue) or int(old_venue) != venue_id:
            frame.at[idx, "venue_id"] = venue_id
            changed = True
        for key_name, value in fields.items():
            old_value = row.get(key_name)
            if pd.isna(value):
                same = pd.isna(old_value)
            else:
                same = str(old_value) == str(value)
            if not same:
                frame.at[idx, key_name] = value
                changed = True
        if changed:
            updated += 1
    return updated


def refresh_pregame_lineups(frame: pd.DataFrame, announced: list[dict]) -> int:
    """Upgrade roster-fallback snapshots when a confirmed lineup posts pregame.

    Started/finished games are never touched. Old K/Hits projections and opponent
    K/contact inputs are retained so the lineup impact can be measured with paired outcomes.
    """
    if frame.empty or not announced:
        return 0
    now = datetime.now(timezone.utc)
    lookup = {(int(r["game_pk"]), int(r["pitcher_id"])): r for r in announced}
    updated = 0
    for idx in frame.index:
        row = frame.loc[idx]
        if not row_is_pregame(row, now) or str(row.get("lineup_source", "")) == LINEUP_CONFIRMED:
            continue
        try:
            key = (int(row["game_pk"]), int(row["pitcher_id"]))
        except (TypeError, ValueError):
            continue
        scheduled = lookup.get(key)
        if not scheduled:
            continue
        context = matchup_context(
            int(scheduled["game_pk"]), str(scheduled["opponent"]), int(scheduled["pitcher_id"]),
            datetime.fromisoformat(str(scheduled["game_date"])).year, scheduled.get("opponent_team_id")
        )
        if not bool(context.get("confirmed")):
            continue
        old_projection = pd.to_numeric(pd.Series([row.get("projection")]), errors="coerce").iloc[0]
        old_opp_k = pd.to_numeric(pd.Series([row.get("opponent_k_pct")]), errors="coerce").iloc[0]
        old_hits_projection = pd.to_numeric(pd.Series([row.get("hits_projection")]), errors="coerce").iloc[0]
        old_opp_hit = pd.to_numeric(pd.Series([row.get("opponent_hit_rate")]), errors="coerce").iloc[0]
        try:
            projected = project(scheduled)
        except Exception as exc:
            print(f"Confirmed-lineup refresh failed for {row.get('player', 'Unknown')} ({row.get('game_pk')}): {exc}")
            continue
        if not projected or str(projected.get("lineup_source", "")) != LINEUP_CONFIRMED:
            continue
        protected = {
            "actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches", "resolved_at_utc",
            "workload_preupgrade_projection", "workload_preupgrade_hits_projection", "workload_preupgrade_outs_projection",
            "workload_preupgrade_expected_bf", "workload_projection_delta_k", "workload_projection_delta_hits",
            "workload_projection_delta_outs", "workload_preupgrade_app_version", "workload_upgraded_at_utc",
        }
        for field, value in projected.items():
            if field not in protected and not field.startswith("team_leash_"):
                frame.at[idx, field] = value
        frame.at[idx, "lineup_preconfirm_projection"] = old_projection
        frame.at[idx, "lineup_preconfirm_opponent_k_pct"] = old_opp_k
        frame.at[idx, "lineup_preconfirm_hits_projection"] = old_hits_projection
        frame.at[idx, "lineup_preconfirm_opponent_hit_rate"] = old_opp_hit
        new_projection = pd.to_numeric(pd.Series([projected.get("projection")]), errors="coerce").iloc[0]
        new_opp_k = pd.to_numeric(pd.Series([projected.get("opponent_k_pct")]), errors="coerce").iloc[0]
        new_hits_projection = pd.to_numeric(pd.Series([projected.get("hits_projection")]), errors="coerce").iloc[0]
        new_opp_hit = pd.to_numeric(pd.Series([projected.get("opponent_hit_rate")]), errors="coerce").iloc[0]
        frame.at[idx, "lineup_projection_delta"] = np.nan if pd.isna(old_projection) or pd.isna(new_projection) else float(new_projection - old_projection)
        frame.at[idx, "lineup_opponent_k_delta"] = np.nan if pd.isna(old_opp_k) or pd.isna(new_opp_k) else float(new_opp_k - old_opp_k)
        frame.at[idx, "lineup_hits_projection_delta"] = np.nan if pd.isna(old_hits_projection) or pd.isna(new_hits_projection) else float(new_hits_projection - old_hits_projection)
        frame.at[idx, "lineup_opponent_hit_delta"] = np.nan if pd.isna(old_opp_hit) or pd.isna(new_opp_hit) else float(new_opp_hit - old_opp_hit)
        updated += 1
    return updated


def snapshot_matchup_override(row: pd.Series) -> dict[str, object]:
    def _rate(name: str, fallback: float) -> float:
        value = pd.to_numeric(pd.Series([row.get(name)]), errors="coerce").iloc[0]
        if pd.isna(value):
            return float(fallback)
        value = float(value)
        return value / 100.0 if value > 1.0 else value

    confirmed_text = str(row.get("lineup_confirmed", "")).strip().lower()
    confirmed = confirmed_text in {"true", "1", "yes"}
    return {
        "k_rate": float(np.clip(_rate("opponent_k_pct", .224), .08, .45)),
        "hit_rate": float(np.clip(_rate("opponent_hit_rate", .235), .12, .36)),
        "pa": int(pd.to_numeric(pd.Series([row.get("matchup_pa")]), errors="coerce").fillna(0).iloc[0]),
        "batters": int(pd.to_numeric(pd.Series([row.get("matchup_batters")]), errors="coerce").fillna(0).iloc[0]),
        "lineup_batters": int(pd.to_numeric(pd.Series([row.get("lineup_batters")]), errors="coerce").fillna(0).iloc[0]),
        "source": str(row.get("lineup_source", LINEUP_ACTIVE_ROSTER) or LINEUP_ACTIVE_ROSTER),
        "confirmed": confirmed,
        "lineup_hash": str(row.get("lineup_hash", "") or ""),
    }


def fill_missing_pregame_paths(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    now = datetime.now(timezone.utc)
    updated = 0
    for idx in frame.index:
        row = frame.loc[idx]
        needs_hits = pd.isna(row.get("hits_projection"))
        needs_outs = pd.isna(row.get("outs_projection"))
        needs_workload = str(row.get("workload_version", "")) != WORKLOAD_VERSION
        if ((row_has_complete_paths(row) and row_has_current_semantics(row) and not needs_hits and not needs_outs and not needs_workload) or not row_is_pregame(row, now)):
            continue
        try:
            refresh_row = {
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
                # Preserve the original deterministic seed during a workload-only
                # comparison so app-version seed drift is not mislabeled as workload impact.
                "seed_version": row.get("app_version", APP_VERSION) if needs_workload else APP_VERSION,
            }
            projected = project(
                refresh_row,
                matchup_override=snapshot_matchup_override(row) if needs_workload else None,
            )
        except Exception as exc:
            print(f"Pregame path refresh failed for {row.get('player', 'Unknown')} ({row.get('game_pk')}): {exc}")
            continue
        if not projected:
            continue
        if needs_workload:
            old_k = pd.to_numeric(pd.Series([row.get("projection")]), errors="coerce").iloc[0]
            old_hits = pd.to_numeric(pd.Series([row.get("hits_projection")]), errors="coerce").iloc[0]
            old_outs = pd.to_numeric(pd.Series([row.get("outs_projection")]), errors="coerce").iloc[0]
            old_bf = pd.to_numeric(pd.Series([row.get("expected_bf")]), errors="coerce").iloc[0]
            protected = {
                "actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches", "resolved_at_utc",
                "lineup_preconfirm_projection", "lineup_preconfirm_opponent_k_pct", "lineup_preconfirm_hits_projection",
                "lineup_preconfirm_opponent_hit_rate", "lineup_projection_delta", "lineup_opponent_k_delta",
                "lineup_hits_projection_delta", "lineup_opponent_hit_delta",
            }
            for key, value in projected.items():
                if key not in protected:
                    frame.at[idx, key] = value
            frame.at[idx, "workload_preupgrade_projection"] = old_k
            frame.at[idx, "workload_preupgrade_hits_projection"] = old_hits
            frame.at[idx, "workload_preupgrade_outs_projection"] = old_outs
            frame.at[idx, "workload_preupgrade_expected_bf"] = old_bf
            frame.at[idx, "workload_preupgrade_app_version"] = str(row.get("app_version", "") or "")
            frame.at[idx, "workload_upgraded_at_utc"] = datetime.now(timezone.utc).isoformat()
            for old_value, new_key, delta_key in (
                (old_k, "projection", "workload_projection_delta_k"),
                (old_hits, "hits_projection", "workload_projection_delta_hits"),
                (old_outs, "outs_projection", "workload_projection_delta_outs"),
            ):
                new_value = pd.to_numeric(pd.Series([projected.get(new_key)]), errors="coerce").iloc[0]
                frame.at[idx, delta_key] = np.nan if pd.isna(old_value) or pd.isna(new_value) else float(new_value - old_value)
        else:
            for key, value in projected.items():
                if key.startswith("sim_") or key.startswith("math_") or key.startswith("hits_") or key.startswith("outs_") or key in {"probability_semantics"}:
                    frame.at[idx, key] = value
        updated += 1
    return updated


def resolve_workload_actuals(row: pd.Series) -> tuple[object, object]:
    if pd.notna(row.get("actual_batters_faced")) and pd.notna(row.get("actual_pitches")):
        return row.get("actual_batters_faced"), row.get("actual_pitches")
    if pd.isna(row.get("game_pk")) or pd.isna(row.get("pitcher_id")):
        return np.nan, np.nan
    try:
        data = get_json(f"game/{int(row['game_pk'])}/boxscore", {})
        status = data.get("gameData", {}).get("status", {})
        if status.get("abstractGameState") != "Final":
            return np.nan, np.nan
        player = data.get("teams", {}).get("away", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")
        if not player:
            player = data.get("teams", {}).get("home", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")
        pitching = (player or {}).get("stats", {}).get("pitching", {})
        bf = pitching.get("battersFaced")
        pitches = pitching.get("numberOfPitches")
        return (int(bf) if bf is not None else np.nan), (int(pitches) if pitches is not None else np.nan)
    except (requests.RequestException, ValueError, TypeError):
        return np.nan, np.nan


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
            actual_bf, actual_pitches = resolve_workload_actuals(frame.loc[idx])
            if pd.notna(actual_k):
                frame.at[idx, "actual_strikeouts"] = actual_k
            if pd.notna(actual_hits):
                frame.at[idx, "actual_hits_allowed"] = actual_hits
            if pd.notna(actual_outs):
                frame.at[idx, "actual_outs"] = actual_outs
            if pd.notna(actual_bf):
                frame.at[idx, "actual_batters_faced"] = actual_bf
            if pd.notna(actual_pitches):
                frame.at[idx, "actual_pitches"] = actual_pitches
            if resolved:
                frame.at[idx, "resolved_at_utc"] = resolved

    today = datetime.now(EASTERN).date()
    rows = schedule(today.isoformat())
    weather_refreshes = attach_pregame_weather(frame, rows)
    team_leash_refreshes = attach_pregame_team_leash(frame)
    lineup_refreshes = 0
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
        team_leash_refreshes += attach_pregame_team_leash(frame)

    if "probability_semantics" not in frame.columns:
        frame["probability_semantics"] = ""
    refreshed = fill_missing_pregame_paths(frame)
    team_leash_refreshes += attach_pregame_team_leash(frame)
    lineup_refreshes = refresh_pregame_lineups(frame, rows)

    for line in range(3, 11):
        for prefix in ("sim", "math"):
            col = f"{prefix}_{line}p"
            if col not in frame.columns:
                frame[col] = np.nan
    for col in ["actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches", "resolved_at_utc"]:
        if col not in frame.columns:
            frame[col] = np.nan if col != "resolved_at_utc" else ""
    frame.to_csv(LOG_PATH, index=False)
    observations = load_observation_log()
    unresolved_observations = 0 if observations.empty else int(pd.to_numeric(observations["actual_outs"], errors="coerce").isna().sum())
    print(
        f"projection log rows={len(frame)} new={len(new_rows)} pregame_path_refreshes={refreshed} weather_refreshes={weather_refreshes} team_leash_refreshes={team_leash_refreshes} lineup_refreshes={lineup_refreshes} "
        f"history_observations={len(observations)} observation_resolves={observation_updates} unresolved_observations={unresolved_observations}"
    )


if __name__ == "__main__":
    main()

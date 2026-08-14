from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from automation.daily_projection_runner import get_json

ROOT = Path(__file__).resolve().parents[1]
OBS_PATH = ROOT / "data" / "umpire_observation_log.csv"
CANDIDATE_VERSION = "umpire-k-v1-report-only"
MIN_PRIOR_GAMES = 20
PRIOR_STRENGTH_BF = 600.0
FACTOR_CAP_LOW = 0.94
FACTOR_CAP_HIGH = 1.06

OBS_COLUMNS = [
    "game_pk", "game_date", "umpire_id", "umpire_name", "total_strikeouts",
    "total_batters_faced", "game_k_rate", "resolved_at_utc",
]


def extract_home_plate_umpire(feed: dict) -> dict[str, object] | None:
    officials = ((feed.get("liveData") or {}).get("boxscore") or {}).get("officials") or []
    for item in officials:
        role = str(item.get("officialType") or item.get("type") or "").strip().lower()
        if role not in {"home plate", "homeplate", "home_plate"}:
            continue
        official = item.get("official") or {}
        umpire_id = official.get("id")
        name = official.get("fullName") or official.get("name") or ""
        if umpire_id is None:
            continue
        return {"umpire_id": int(umpire_id), "umpire_name": str(name)}
    return None


def resolved_game_observation(feed: dict, game_pk: int, game_date: str) -> dict[str, object] | None:
    status = ((feed.get("gameData") or {}).get("status") or {})
    if str(status.get("abstractGameState") or "").lower() != "final":
        return None
    umpire = extract_home_plate_umpire(feed)
    if not umpire:
        return None
    teams = ((feed.get("liveData") or {}).get("boxscore") or {}).get("teams") or {}
    strikeouts = 0.0
    batters_faced = 0.0
    for side in ("away", "home"):
        pitching = (((teams.get(side) or {}).get("teamStats") or {}).get("pitching") or {})
        strikeouts += float(pitching.get("strikeOuts", 0) or 0)
        batters_faced += float(pitching.get("battersFaced", 0) or 0)
    if batters_faced <= 0:
        return None
    return {
        "game_pk": int(game_pk),
        "game_date": str(game_date),
        **umpire,
        "total_strikeouts": float(strikeouts),
        "total_batters_faced": float(batters_faced),
        "game_k_rate": float(strikeouts / batters_faced),
        "resolved_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def load_observations(path: Path = OBS_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=OBS_COLUMNS)
    try:
        frame = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=OBS_COLUMNS)
    for col in OBS_COLUMNS:
        if col not in frame.columns:
            frame[col] = np.nan if col not in {"game_date", "umpire_name", "resolved_at_utc"} else ""
    return frame[OBS_COLUMNS].copy()


def save_observations(frame: pd.DataFrame, path: Path = OBS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    for col in OBS_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan if col not in {"game_date", "umpire_name", "resolved_at_utc"} else ""
    out[OBS_COLUMNS].drop_duplicates(subset=["game_pk"], keep="last").to_csv(path, index=False)


def refresh_resolved_observations(
    projection_log: pd.DataFrame,
    observations: pd.DataFrame | None = None,
    fetcher: Callable[[str, dict], dict] = get_json,
) -> tuple[pd.DataFrame, int]:
    obs = load_observations() if observations is None else observations.copy()
    known = set(pd.to_numeric(obs.get("game_pk", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist())
    if projection_log is None or projection_log.empty:
        return obs, 0
    resolved = projection_log.loc[pd.to_numeric(projection_log.get("actual_strikeouts"), errors="coerce").notna()].copy()
    added = 0
    for game_pk, group in resolved.groupby(pd.to_numeric(resolved.get("game_pk"), errors="coerce"), dropna=True):
        if int(game_pk) in known:
            continue
        row = group.iloc[0]
        try:
            feed = fetcher(f"game/{int(game_pk)}/feed/live", {})
            record = resolved_game_observation(feed, int(game_pk), str(row.get("game_date", "")))
        except Exception:
            record = None
        if not record:
            continue
        obs = pd.concat([obs, pd.DataFrame([record])], ignore_index=True)
        known.add(int(game_pk))
        added += 1
    return obs, added


def candidate_from_prior(
    observations: pd.DataFrame,
    umpire_id: int,
    game_date: str,
) -> dict[str, object]:
    empty = {
        "umpire_prior_games": 0,
        "umpire_prior_bf": 0.0,
        "umpire_prior_k_rate": np.nan,
        "umpire_league_prior_k_rate": np.nan,
        "umpire_k_factor_candidate": 1.0,
        "umpire_candidate_status": "LEARNING",
        "umpire_candidate_version": CANDIDATE_VERSION,
    }
    if observations is None or observations.empty:
        return empty
    dates = pd.to_datetime(observations.get("game_date"), errors="coerce").dt.normalize()
    target = pd.to_datetime(game_date, errors="coerce")
    if pd.isna(target):
        return empty
    prior = observations.loc[dates.lt(target.normalize())].copy()
    if prior.empty:
        return empty
    prior["total_strikeouts"] = pd.to_numeric(prior.get("total_strikeouts"), errors="coerce")
    prior["total_batters_faced"] = pd.to_numeric(prior.get("total_batters_faced"), errors="coerce")
    ready = prior["total_strikeouts"].notna() & prior["total_batters_faced"].gt(0)
    prior = prior.loc[ready]
    if prior.empty:
        return empty
    league_bf = float(prior["total_batters_faced"].sum())
    league_k = float(prior["total_strikeouts"].sum())
    league_rate = float(league_k / league_bf) if league_bf > 0 else np.nan
    ump = prior.loc[pd.to_numeric(prior.get("umpire_id"), errors="coerce").eq(int(umpire_id))]
    n = int(len(ump))
    ump_bf = float(ump["total_batters_faced"].sum()) if n else 0.0
    ump_k = float(ump["total_strikeouts"].sum()) if n else 0.0
    raw_rate = float(ump_k / ump_bf) if ump_bf > 0 else np.nan
    factor = 1.0
    status = "LEARNING"
    if n >= MIN_PRIOR_GAMES and ump_bf > 0 and np.isfinite(league_rate) and league_rate > 0:
        shrunk_rate = float((ump_k + PRIOR_STRENGTH_BF * league_rate) / (ump_bf + PRIOR_STRENGTH_BF))
        factor = float(np.clip(shrunk_rate / league_rate, FACTOR_CAP_LOW, FACTOR_CAP_HIGH))
        status = "AUDITABLE"
    return {
        "umpire_prior_games": n,
        "umpire_prior_bf": ump_bf,
        "umpire_prior_k_rate": raw_rate,
        "umpire_league_prior_k_rate": league_rate,
        "umpire_k_factor_candidate": factor,
        "umpire_candidate_status": status,
        "umpire_candidate_version": CANDIDATE_VERSION,
    }


def attach_pregame_umpire_context(
    projection_log: pd.DataFrame,
    observations: pd.DataFrame,
    now: datetime | None = None,
    fetcher: Callable[[str, dict], dict] = get_json,
) -> int:
    if projection_log is None or projection_log.empty:
        return 0
    current = now or datetime.now(timezone.utc)
    current_ts = pd.Timestamp(current)
    if current_ts.tzinfo is None:
        current_ts = current_ts.tz_localize("UTC")
    else:
        current_ts = current_ts.tz_convert("UTC")
    updated = 0
    for idx, row in projection_log.iterrows():
        game_time = pd.to_datetime(row.get("game_time"), errors="coerce", utc=True)
        if pd.isna(game_time) or game_time <= current_ts:
            continue
        if pd.notna(row.get("umpire_id")) and str(row.get("umpire_name") or "").strip():
            continue
        if pd.isna(row.get("game_pk")):
            continue
        try:
            feed = fetcher(f"game/{int(row['game_pk'])}/feed/live", {})
            umpire = extract_home_plate_umpire(feed)
        except Exception:
            umpire = None
        if not umpire:
            continue
        candidate = candidate_from_prior(observations, int(umpire["umpire_id"]), str(row.get("game_date", "")))
        projection_log.at[idx, "umpire_id"] = int(umpire["umpire_id"])
        projection_log.at[idx, "umpire_name"] = str(umpire["umpire_name"])
        projection_log.at[idx, "umpire_source"] = "MLB_LIVE_FEED_PREGAME"
        projection_log.at[idx, "umpire_captured_at_utc"] = datetime.now(timezone.utc).isoformat()
        for key, value in candidate.items():
            projection_log.at[idx, key] = value
        updated += 1
    return updated

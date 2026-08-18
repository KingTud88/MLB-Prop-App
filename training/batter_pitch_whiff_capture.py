from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from engine.lineup_context import LINEUP_ACTIVE_ROSTER, LINEUP_CONFIRMED, get_confirmed_lineup

VERSION = "batter-pitch-whiff-capture-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
HISTORICAL_BACKFILL_ALLOWED = False

BASE_V1 = "https://statsapi.mlb.com/api/v1"
BASE_V11 = "https://statsapi.mlb.com/api/v1.1"
USER_AGENT = "StrikeOut-King-9000/1.0"
RECENT_TEAM_GAMES_LIMIT = 10
TEAM_LOOKBACK_DAYS = 45
MIN_TYPED_PITCH_COVERAGE = 0.90
MIN_CLASSIFIED_PITCH_COVERAGE = 0.98
MIN_TOTAL_SWINGS = 100
MIN_SWINGS_PER_PITCH_TYPE = 5
MIN_BATTERS_WITH_SAMPLE = 5
NON_ARSENAL_CODES = {"", "IN", "PO", "UN"}

# Frozen from MLB Stats API /api/v1/pitchCodes on 2026-08-18.
# The endpoint explicitly exposes swingStatus and swingMissStatus for each result code.
FROZEN_SWING_CODES = frozenset({"S", "L", "M", "F", "R", "T", "X", "W", "Q", "E", "D", "Y", "J", "Z", "O"})
FROZEN_WHIFF_CODES = frozenset({"S", "M", "T", "W", "Q", "O"})
METRIC_DEFINITION = "WHIFF_PER_SWING_BY_BATTER_AND_PITCH_TYPE"

COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "opponent_team_id", "game_time", "projection_captured_at_utc",
    "whiff_context_captured_at_utc", "lineup_source", "lineup_confirmed",
    "lineup_hash", "lineage", "batters_requested", "batter_ids_json",
    "source_game_pks", "prior_team_games_considered", "prior_team_games_with_feed",
    "feed_failures", "raw_pitch_events", "typed_pitch_events", "typed_pitch_coverage",
    "classified_pitch_events", "classified_pitch_coverage", "swing_events",
    "whiff_events", "overall_whiff_rate", "batters_with_sample",
    "sample_batter_coverage", "pitch_types_with_sample", "batter_pitch_counts_json",
    "batter_pitch_whiff_rates_json", "pitch_code_reference_hash", "swing_codes",
    "whiff_codes", "metric_definition", "audit_eligible", "reason", "source",
    "source_endpoint_version", "historical_backfill_allowed", "report_only",
    "production_authority", "capture_version",
]


def _num(value: object) -> int | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else int(parsed)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _clean_text(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _utc(value: object) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce", utc=True)


def _request_json(base: str, path: str, params: dict[str, object] | None = None) -> Any:
    query = urlencode(params or {})
    suffix = f"?{query}" if query else ""
    request = Request(f"{base}/{path.lstrip('/')}{suffix}", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed trusted MLB API host
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"MLB Stats API request failed: {exc}") from exc


def fetch_pitch_code_reference() -> list[dict[str, Any]]:
    payload = _request_json(BASE_V1, "pitchCodes")
    return payload if isinstance(payload, list) else []


def validate_pitch_code_reference(rows: list[dict[str, Any]]) -> tuple[set[str], str]:
    known = {str(row.get("code", "")) for row in rows if row.get("code") not in (None, "")}
    swing = {str(row.get("code")) for row in rows if row.get("swingStatus") is True}
    whiff = {str(row.get("code")) for row in rows if row.get("swingMissStatus") is True}
    if swing != set(FROZEN_SWING_CODES):
        raise RuntimeError(
            f"MLB pitch-code swing semantics changed: expected={sorted(FROZEN_SWING_CODES)} observed={sorted(swing)}"
        )
    if whiff != set(FROZEN_WHIFF_CODES):
        raise RuntimeError(
            f"MLB pitch-code whiff semantics changed: expected={sorted(FROZEN_WHIFF_CODES)} observed={sorted(whiff)}"
        )
    canonical = [
        {
            "code": str(row.get("code", "")),
            "swingStatus": bool(row.get("swingStatus")),
            "swingMissStatus": bool(row.get("swingMissStatus")),
            "pitchStatus": bool(row.get("pitchStatus")),
        }
        for row in rows
    ]
    canonical.sort(key=lambda row: row["code"])
    signature = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return known, signature


def fetch_active_roster_batter_ids(team_id: int, season: int) -> tuple[int, ...]:
    payload = _request_json(
        BASE_V1,
        f"teams/{int(team_id)}/roster",
        {"rosterType": "active", "season": str(int(season))},
    )
    ids: list[int] = []
    for row in payload.get("roster", []) if isinstance(payload, dict) else []:
        pid = _num((row.get("person") or {}).get("id"))
        position_code = str((row.get("position") or {}).get("code", ""))
        if pid is not None and position_code != "1":
            ids.append(pid)
    return tuple(dict.fromkeys(ids))


def fetch_team_schedule(team_id: int, before_date: str) -> dict[str, Any]:
    target = date.fromisoformat(before_date)
    start = target - timedelta(days=TEAM_LOOKBACK_DAYS)
    end = target - timedelta(days=1)
    if end < start:
        return {"dates": []}
    return _request_json(
        BASE_V1,
        "schedule",
        {
            "sportId": "1",
            "teamId": str(int(team_id)),
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        },
    )


def prior_team_game_pks_from_payload(
    payload: dict[str, Any],
    before_date: str,
    *,
    limit: int = RECENT_TEAM_GAMES_LIMIT,
) -> list[int]:
    games: list[tuple[str, int]] = []
    for day in payload.get("dates", []) if isinstance(payload, dict) else []:
        day_date = str(day.get("date", ""))
        if not day_date or day_date >= before_date:
            continue
        for game in day.get("games", []) or []:
            if str((game.get("status") or {}).get("abstractGameState", "")) != "Final":
                continue
            game_pk = _num(game.get("gamePk"))
            if game_pk is None:
                continue
            stamp = str(game.get("gameDate", day_date))
            games.append((stamp, game_pk))
    games.sort(reverse=True)
    return [game_pk for _, game_pk in games[: max(0, int(limit))]]


def fetch_live_feed(game_pk: int) -> dict[str, Any]:
    payload = _request_json(BASE_V11, f"game/{int(game_pk)}/feed/live")
    return payload if isinstance(payload, dict) else {}


def _capture_key(row: pd.Series | dict[str, object]) -> tuple[int, int, str, str] | None:
    game_pk = _num(row.get("game_pk"))
    pitcher_id = _num(row.get("pitcher_id"))
    if game_pk is None or pitcher_id is None:
        return None
    source = _clean_text(row.get("lineup_source")) or LINEUP_ACTIVE_ROSTER
    lineup_hash = _clean_text(row.get("lineup_hash"))
    return game_pk, pitcher_id, source, lineup_hash


def extract_batter_pitch_events(
    feeds: list[dict[str, Any]],
    batter_ids: tuple[int, ...],
    known_result_codes: set[str],
) -> dict[str, object]:
    requested = set(int(x) for x in batter_ids)
    swings: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    whiffs: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    raw = typed = classified = 0

    for payload in feeds:
        plays = (((payload.get("liveData") or {}).get("plays") or {}).get("allPlays") or [])
        for play in plays:
            batter_id = _num(((play.get("matchup") or {}).get("batter") or {}).get("id"))
            if batter_id is None or batter_id not in requested:
                continue
            for event in play.get("playEvents", []) or []:
                if not event.get("isPitch"):
                    continue
                raw += 1
                details = event.get("details") or {}
                pitch_type = _clean_text((details.get("type") or {}).get("code"))
                if not pitch_type or pitch_type in NON_ARSENAL_CODES:
                    continue
                typed += 1
                result_code = _clean_text(details.get("code"))
                if result_code in known_result_codes:
                    classified += 1
                if result_code in FROZEN_SWING_CODES:
                    swings[batter_id][pitch_type] += 1
                    if result_code in FROZEN_WHIFF_CODES:
                        whiffs[batter_id][pitch_type] += 1

    counts_payload: dict[str, dict[str, dict[str, int]]] = {}
    rates_payload: dict[str, dict[str, float]] = {}
    total_swings = 0
    total_whiffs = 0
    sampled_batters = 0
    sampled_pitch_types: set[str] = set()

    for batter_id in sorted(requested):
        pitch_types = sorted(set(swings.get(batter_id, {})) | set(whiffs.get(batter_id, {})))
        batter_counts: dict[str, dict[str, int]] = {}
        batter_rates: dict[str, float] = {}
        for pitch_type in pitch_types:
            swing_count = int(swings[batter_id].get(pitch_type, 0))
            whiff_count = int(whiffs[batter_id].get(pitch_type, 0))
            total_swings += swing_count
            total_whiffs += whiff_count
            batter_counts[pitch_type] = {"swings": swing_count, "whiffs": whiff_count}
            if swing_count >= MIN_SWINGS_PER_PITCH_TYPE:
                batter_rates[pitch_type] = round(whiff_count / swing_count, 6)
                sampled_pitch_types.add(pitch_type)
        if batter_counts:
            counts_payload[str(batter_id)] = batter_counts
        if batter_rates:
            rates_payload[str(batter_id)] = batter_rates
            sampled_batters += 1

    return {
        "raw_pitch_events": raw,
        "typed_pitch_events": typed,
        "classified_pitch_events": classified,
        "swing_events": total_swings,
        "whiff_events": total_whiffs,
        "batters_with_sample": sampled_batters,
        "pitch_types_with_sample": len(sampled_pitch_types),
        "batter_pitch_counts_json": json.dumps(counts_payload, sort_keys=True, separators=(",", ":")),
        "batter_pitch_whiff_rates_json": json.dumps(rates_payload, sort_keys=True, separators=(",", ":")),
    }


def build_capture_records(
    projections: pd.DataFrame,
    existing: pd.DataFrame | None = None,
    *,
    captured_at: pd.Timestamp | None = None,
    pitch_code_resolver: Callable[[], list[dict[str, Any]]] = fetch_pitch_code_reference,
    lineup_resolver: Callable[..., object] = get_confirmed_lineup,
    roster_resolver: Callable[[int, int], tuple[int, ...]] = fetch_active_roster_batter_ids,
    schedule_resolver: Callable[[int, str], dict[str, Any]] = fetch_team_schedule,
    feed_resolver: Callable[[int], dict[str, Any]] = fetch_live_feed,
) -> pd.DataFrame:
    existing = existing.copy() if existing is not None else pd.DataFrame(columns=COLUMNS)
    if projections is None or projections.empty:
        return existing.reindex(columns=COLUMNS)

    now = pd.to_datetime(captured_at if captured_at is not None else pd.Timestamp.now(tz="UTC"), utc=True)
    known_codes, pitch_code_hash = validate_pitch_code_reference(pitch_code_resolver())

    existing_keys: set[tuple[int, int, str, str]] = set()
    if not existing.empty:
        for _, saved in existing.iterrows():
            key = _capture_key(saved)
            if key is not None:
                existing_keys.add(key)

    roster_cache: dict[tuple[int, int], tuple[int, ...]] = {}
    schedule_cache: dict[tuple[int, str], list[int]] = {}
    feed_cache: dict[int, dict[str, Any] | Exception] = {}
    additions: list[dict[str, object]] = []

    for _, row in projections.iterrows():
        key = _capture_key(row)
        if key is None or key in existing_keys:
            continue
        game_time = _utc(row.get("game_time"))
        if pd.isna(game_time) or game_time <= now:
            continue

        game_pk, pitcher_id, saved_source, saved_hash = key
        opponent_team_id = _num(row.get("opponent_team_id"))
        game_date = _clean_text(row.get("game_date"))
        season_stamp = pd.to_datetime(game_date, errors="coerce")
        season = 0 if pd.isna(season_stamp) else int(season_stamp.year)
        confirmed_saved = _truthy(row.get("lineup_confirmed")) or saved_source == LINEUP_CONFIRMED
        lineage = "PRE_GAME_ACTIVE_ROSTER"
        eligible = True
        reason = ""
        batter_ids: tuple[int, ...] = ()

        if opponent_team_id is None or season <= 0 or not game_date:
            eligible = False
            reason = "Opponent team, season, or game date unavailable."
        elif confirmed_saved:
            ctx = lineup_resolver(game_pk, opponent_team_id)
            current_confirmed = bool(getattr(ctx, "confirmed", False))
            current_hash = _clean_text(getattr(ctx, "fingerprint", ""))
            if not current_confirmed:
                lineage = "CONFIRMED_LINEUP_NOT_REPRODUCIBLE"
                eligible = False
                reason = "Saved confirmed lineup could not be reproduced at batter-whiff capture."
            elif saved_hash and current_hash != saved_hash:
                lineage = "CONFIRMED_LINEUP_HASH_MISMATCH"
                eligible = False
                reason = "Current confirmed lineup fingerprint differs from the projection snapshot."
            else:
                lineage = "PRE_GAME_CONFIRMED_MATCH"
                batter_ids = tuple(int(x) for x in getattr(ctx, "player_ids", ()) if x)
        else:
            roster_key = (opponent_team_id, season)
            if roster_key not in roster_cache:
                try:
                    roster_cache[roster_key] = roster_resolver(opponent_team_id, season)
                except Exception:
                    roster_cache[roster_key] = ()
            batter_ids = roster_cache[roster_key]

        if eligible and not batter_ids:
            eligible = False
            reason = "No batter IDs available for the saved lineup state."

        game_pks: list[int] = []
        feeds: list[dict[str, Any]] = []
        feed_failures = 0
        if eligible and opponent_team_id is not None:
            schedule_key = (opponent_team_id, game_date)
            if schedule_key not in schedule_cache:
                try:
                    payload = schedule_resolver(opponent_team_id, game_date)
                    schedule_cache[schedule_key] = prior_team_game_pks_from_payload(payload, game_date)
                except Exception:
                    schedule_cache[schedule_key] = []
            game_pks = schedule_cache[schedule_key]
            for source_game_pk in game_pks:
                if source_game_pk not in feed_cache:
                    try:
                        feed_cache[source_game_pk] = feed_resolver(source_game_pk)
                    except Exception as exc:  # research lane records source failures, never fabricates
                        feed_cache[source_game_pk] = exc
                cached = feed_cache[source_game_pk]
                if isinstance(cached, Exception):
                    feed_failures += 1
                else:
                    feeds.append(cached)

        metrics = extract_batter_pitch_events(feeds, batter_ids, known_codes) if batter_ids else {
            "raw_pitch_events": 0,
            "typed_pitch_events": 0,
            "classified_pitch_events": 0,
            "swing_events": 0,
            "whiff_events": 0,
            "batters_with_sample": 0,
            "pitch_types_with_sample": 0,
            "batter_pitch_counts_json": "{}",
            "batter_pitch_whiff_rates_json": "{}",
        }
        raw = int(metrics["raw_pitch_events"])
        typed = int(metrics["typed_pitch_events"])
        classified = int(metrics["classified_pitch_events"])
        swings = int(metrics["swing_events"])
        whiffs = int(metrics["whiff_events"])
        sampled_batters = int(metrics["batters_with_sample"])
        typed_coverage = float(typed / raw) if raw else np.nan
        classified_coverage = float(classified / typed) if typed else np.nan
        batter_coverage = float(sampled_batters / len(batter_ids)) if batter_ids else np.nan
        overall_whiff = float(whiffs / swings) if swings else np.nan

        if eligible and len(feeds) < min(5, RECENT_TEAM_GAMES_LIMIT):
            eligible = False
            reason = f"Only {len(feeds)} prior team game feeds available; need at least 5."
        if eligible and (pd.isna(typed_coverage) or typed_coverage < MIN_TYPED_PITCH_COVERAGE):
            eligible = False
            reason = f"Typed-pitch coverage {typed_coverage!r} below {MIN_TYPED_PITCH_COVERAGE:.2f}."
        if eligible and (pd.isna(classified_coverage) or classified_coverage < MIN_CLASSIFIED_PITCH_COVERAGE):
            eligible = False
            reason = f"Pitch-result classification coverage {classified_coverage!r} below {MIN_CLASSIFIED_PITCH_COVERAGE:.2f}."
        if eligible and swings < MIN_TOTAL_SWINGS:
            eligible = False
            reason = f"Only {swings} swings available; need at least {MIN_TOTAL_SWINGS}."
        if eligible and sampled_batters < MIN_BATTERS_WITH_SAMPLE:
            eligible = False
            reason = f"Only {sampled_batters} batters have pitch-type samples; need at least {MIN_BATTERS_WITH_SAMPLE}."

        additions.append({
            "game_date": game_date,
            "game_pk": game_pk,
            "pitcher_id": pitcher_id,
            "player": _clean_text(row.get("player")),
            "team": _clean_text(row.get("team")),
            "opponent": _clean_text(row.get("opponent")),
            "opponent_team_id": np.nan if opponent_team_id is None else opponent_team_id,
            "game_time": game_time.isoformat(),
            "projection_captured_at_utc": _clean_text(row.get("captured_at_utc")),
            "whiff_context_captured_at_utc": now.isoformat(),
            "lineup_source": saved_source,
            "lineup_confirmed": confirmed_saved,
            "lineup_hash": saved_hash,
            "lineage": lineage,
            "batters_requested": len(batter_ids),
            "batter_ids_json": json.dumps(list(batter_ids), separators=(",", ":")),
            "source_game_pks": "|".join(str(x) for x in game_pks),
            "prior_team_games_considered": len(game_pks),
            "prior_team_games_with_feed": len(feeds),
            "feed_failures": feed_failures,
            "raw_pitch_events": raw,
            "typed_pitch_events": typed,
            "typed_pitch_coverage": typed_coverage,
            "classified_pitch_events": classified,
            "classified_pitch_coverage": classified_coverage,
            "swing_events": swings,
            "whiff_events": whiffs,
            "overall_whiff_rate": overall_whiff,
            "batters_with_sample": sampled_batters,
            "sample_batter_coverage": batter_coverage,
            "pitch_types_with_sample": int(metrics["pitch_types_with_sample"]),
            "batter_pitch_counts_json": str(metrics["batter_pitch_counts_json"]),
            "batter_pitch_whiff_rates_json": str(metrics["batter_pitch_whiff_rates_json"]),
            "pitch_code_reference_hash": pitch_code_hash,
            "swing_codes": "|".join(sorted(FROZEN_SWING_CODES)),
            "whiff_codes": "|".join(sorted(FROZEN_WHIFF_CODES)),
            "metric_definition": METRIC_DEFINITION,
            "audit_eligible": eligible,
            "reason": reason,
            "source": "MLB_STATS_API_PRIOR_TEAM_LIVE_FEED",
            "source_endpoint_version": "v1 schedule+roster+pitchCodes | v1.1 feed/live",
            "historical_backfill_allowed": HISTORICAL_BACKFILL_ALLOWED,
            "report_only": REPORT_ONLY,
            "production_authority": PRODUCTION_AUTHORITY,
            "capture_version": VERSION,
        })
        existing_keys.add(key)

    if additions:
        existing = pd.concat([existing, pd.DataFrame(additions)], ignore_index=True)
    for column in COLUMNS:
        if column not in existing.columns:
            existing[column] = np.nan
    return existing[COLUMNS].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture report-only frozen batter Whiff% by pitch type.")
    parser.add_argument("--projection-log", default="data/projection_log.csv")
    parser.add_argument("--output", default="data/batter_pitch_whiff_context_log.csv")
    args = parser.parse_args()

    projection_path = Path(args.projection_log)
    output_path = Path(args.output)
    projections = pd.read_csv(projection_path) if projection_path.exists() else pd.DataFrame()
    existing = pd.read_csv(output_path) if output_path.exists() else pd.DataFrame(columns=COLUMNS)
    result = build_capture_records(projections, existing)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    eligible = int(result.get("audit_eligible", pd.Series(dtype=bool)).map(_truthy).sum()) if not result.empty else 0
    print(
        f"batter_pitch_whiff_rows={len(result)} eligible_rows={eligible} "
        f"metric={METRIC_DEFINITION} report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}"
    )


if __name__ == "__main__":
    main()

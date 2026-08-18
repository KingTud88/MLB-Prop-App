from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

VERSION = "pitch-arsenal-capture-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

BASE_V1 = "https://statsapi.mlb.com/api/v1"
BASE_V11 = "https://statsapi.mlb.com/api/v1.1"
USER_AGENT = "StrikeOut-King-9000/1.0"
RECENT_GAMES_LIMIT = 5
MIN_TYPED_PITCHES = 20
MIN_TYPED_PITCH_COVERAGE = 0.90
NON_ARSENAL_CODES = {"", "IN", "PO", "UN"}

COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "game_time", "projection_captured_at_utc", "arsenal_captured_at_utc",
    "source_game_pks", "prior_games_considered", "prior_games_with_feed",
    "prior_games_with_pitch_data", "feed_failures", "raw_pitch_events",
    "typed_pitch_events", "typed_pitch_coverage", "arsenal_pitch_types",
    "arsenal_usage", "pitch_counts_json", "pitch_type_descriptions_json",
    "audit_eligible", "reason", "source", "source_endpoint_version",
    "report_only", "production_authority", "capture_version",
]


def _num(value: object) -> int | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else int(parsed)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _request_json(base: str, path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
    query = urlencode(params or {})
    suffix = f"?{query}" if query else ""
    request = Request(
        f"{base}/{path.lstrip('/')}{suffix}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed trusted MLB API host
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"MLB Stats API request failed: {exc}") from exc


def fetch_pitcher_game_log(pitcher_id: int, season: int) -> dict[str, Any]:
    return _request_json(
        BASE_V1,
        f"people/{int(pitcher_id)}/stats",
        {"stats": "gameLog", "group": "pitching", "season": str(int(season))},
    )


def fetch_live_feed(game_pk: int) -> dict[str, Any]:
    return _request_json(BASE_V11, f"game/{int(game_pk)}/feed/live")


def prior_game_pks_from_payload(
    payload: dict[str, Any],
    before_date: str,
    *,
    limit: int = RECENT_GAMES_LIMIT,
) -> list[int]:
    try:
        cutoff = date.fromisoformat(str(before_date)[:10])
    except ValueError:
        return []

    candidates: list[tuple[date, int]] = []
    for block in payload.get("stats") or []:
        for split in block.get("splits") or []:
            try:
                split_date = date.fromisoformat(str(split.get("date", ""))[:10])
            except ValueError:
                continue
            if split_date >= cutoff:
                continue
            game = split.get("game") if isinstance(split.get("game"), dict) else {}
            game_pk = _num(game.get("gamePk")) or _num(split.get("gamePk"))
            if game_pk is not None:
                candidates.append((split_date, game_pk))

    candidates.sort(key=lambda item: item[0], reverse=True)
    result: list[int] = []
    seen: set[int] = set()
    for _, game_pk in candidates:
        if game_pk in seen:
            continue
        result.append(game_pk)
        seen.add(game_pk)
        if len(result) >= int(limit):
            break
    return result


def extract_pitch_summary(
    feed: dict[str, Any],
    pitcher_id: int,
) -> tuple[Counter[str], dict[str, str], int, int]:
    counts: Counter[str] = Counter()
    descriptions: dict[str, str] = {}
    raw_pitch_events = 0
    typed_pitch_events = 0

    plays = (((feed.get("liveData") or {}).get("plays") or {}).get("allPlays") or [])
    for play in plays:
        matchup = play.get("matchup") if isinstance(play.get("matchup"), dict) else {}
        pitcher = matchup.get("pitcher") if isinstance(matchup.get("pitcher"), dict) else {}
        if _num(pitcher.get("id")) != int(pitcher_id):
            continue
        for event in play.get("playEvents") or []:
            if not bool(event.get("isPitch")):
                continue
            raw_pitch_events += 1
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            pitch_type = details.get("type") if isinstance(details.get("type"), dict) else {}
            code = str(pitch_type.get("code", "") or "").strip().upper()
            if code in NON_ARSENAL_CODES:
                continue
            typed_pitch_events += 1
            counts[code] += 1
            description = str(pitch_type.get("description", "") or "").strip()
            if description and code not in descriptions:
                descriptions[code] = description

    return counts, descriptions, raw_pitch_events, typed_pitch_events


def _capture_key(row: pd.Series) -> tuple[int, int] | None:
    game_pk = _num(row.get("game_pk"))
    pitcher_id = _num(row.get("pitcher_id"))
    if game_pk is None or pitcher_id is None:
        return None
    return game_pk, pitcher_id


def _json_map(values: dict[str, object]) -> str:
    return json.dumps(values, separators=(",", ":"), ensure_ascii=True)


def build_capture_records(
    projections: pd.DataFrame,
    existing: pd.DataFrame | None = None,
    *,
    captured_at: pd.Timestamp | None = None,
    recent_games_limit: int = RECENT_GAMES_LIMIT,
    game_log_resolver: Callable[[int, int], dict[str, Any]] = fetch_pitcher_game_log,
    feed_resolver: Callable[[int], dict[str, Any]] = fetch_live_feed,
) -> pd.DataFrame:
    existing = existing.copy() if existing is not None else pd.DataFrame(columns=COLUMNS)
    if projections is None or projections.empty:
        return existing.reindex(columns=COLUMNS)

    now = pd.to_datetime(captured_at if captured_at is not None else pd.Timestamp.now(tz="UTC"), utc=True)
    work = projections.copy()
    game_time_values = work["game_time"] if "game_time" in work.columns else pd.Series(pd.NaT, index=work.index)
    capture_values = work["captured_at_utc"] if "captured_at_utc" in work.columns else pd.Series(pd.NaT, index=work.index)
    work["_game_time"] = pd.to_datetime(game_time_values, errors="coerce", utc=True)
    work["_projection_capture"] = pd.to_datetime(capture_values, errors="coerce", utc=True)
    work = work.loc[work["_game_time"].notna() & work["_game_time"].gt(now)].copy()
    if work.empty:
        return existing.reindex(columns=COLUMNS)
    work = work.sort_values("_projection_capture", na_position="first")
    work = work.drop_duplicates(subset=["game_pk", "pitcher_id"], keep="last")

    existing_keys: set[tuple[int, int]] = set()
    if not existing.empty:
        for _, row in existing.iterrows():
            key = _capture_key(row)
            if key is not None:
                existing_keys.add(key)

    game_log_cache: dict[tuple[int, int], dict[str, Any]] = {}
    feed_cache: dict[int, dict[str, Any] | Exception] = {}
    additions: list[dict[str, object]] = []

    for _, row in work.iterrows():
        key = _capture_key(row)
        if key is None or key in existing_keys:
            continue
        game_pk, pitcher_id = key
        game_time = pd.to_datetime(row.get("_game_time"), utc=True)
        target_date = str(row.get("game_date", "") or "")[:10]
        if not target_date:
            target_date = game_time.date().isoformat()
        try:
            season = int(target_date[:4])
        except (TypeError, ValueError):
            season = int(game_time.year)

        reason = ""
        try:
            log_key = (pitcher_id, season)
            if log_key not in game_log_cache:
                game_log_cache[log_key] = game_log_resolver(pitcher_id, season)
            source_game_pks = prior_game_pks_from_payload(
                game_log_cache[log_key], target_date, limit=recent_games_limit
            )
        except Exception as exc:  # report-only capture must preserve failure lineage
            source_game_pks = []
            reason = f"Pitcher game-log source unavailable: {type(exc).__name__}."

        total_counts: Counter[str] = Counter()
        descriptions: dict[str, str] = {}
        raw_pitch_events = 0
        typed_pitch_events = 0
        prior_games_with_feed = 0
        prior_games_with_pitch_data = 0
        feed_failures = 0

        for prior_game_pk in source_game_pks:
            if prior_game_pk not in feed_cache:
                try:
                    feed_cache[prior_game_pk] = feed_resolver(prior_game_pk)
                except Exception as exc:  # keep the rest of the prior-game sample usable
                    feed_cache[prior_game_pk] = exc
            cached = feed_cache[prior_game_pk]
            if isinstance(cached, Exception):
                feed_failures += 1
                continue
            prior_games_with_feed += 1
            counts, desc, raw_n, typed_n = extract_pitch_summary(cached, pitcher_id)
            raw_pitch_events += raw_n
            typed_pitch_events += typed_n
            if typed_n > 0:
                prior_games_with_pitch_data += 1
            total_counts.update(counts)
            for code, description in desc.items():
                descriptions.setdefault(code, description)

        typed_coverage = (
            float(typed_pitch_events / raw_pitch_events) if raw_pitch_events > 0 else float("nan")
        )
        ordered_codes = [code for code, _ in total_counts.most_common()]
        usage = {
            code: round(float(total_counts[code] / typed_pitch_events), 6)
            for code in ordered_codes
            if typed_pitch_events > 0
        }

        eligible = True
        if not source_game_pks:
            eligible = False
            reason = reason or "No prior completed MLB game IDs were available before the target start."
        elif typed_pitch_events < MIN_TYPED_PITCHES:
            eligible = False
            reason = reason or (
                f"Only {typed_pitch_events} typed prior pitches were captured; "
                f"need {MIN_TYPED_PITCHES} for usable arsenal context."
            )
        elif pd.isna(typed_coverage) or float(typed_coverage) < MIN_TYPED_PITCH_COVERAGE:
            eligible = False
            coverage_text = "n/a" if pd.isna(typed_coverage) else f"{float(typed_coverage):.1%}"
            reason = reason or (
                f"Typed pitch coverage {coverage_text} is below the "
                f"{MIN_TYPED_PITCH_COVERAGE:.0%} capture floor."
            )
        elif not ordered_codes:
            eligible = False
            reason = reason or "No arsenal pitch types were captured from prior-game feeds."

        additions.append({
            "game_date": target_date,
            "game_pk": game_pk,
            "pitcher_id": pitcher_id,
            "player": str(row.get("player", "") or ""),
            "team": str(row.get("team", "") or ""),
            "opponent": str(row.get("opponent", "") or ""),
            "game_time": game_time.isoformat(),
            "projection_captured_at_utc": str(row.get("captured_at_utc", "") or ""),
            "arsenal_captured_at_utc": now.isoformat(),
            "source_game_pks": "|".join(str(x) for x in source_game_pks),
            "prior_games_considered": len(source_game_pks),
            "prior_games_with_feed": prior_games_with_feed,
            "prior_games_with_pitch_data": prior_games_with_pitch_data,
            "feed_failures": feed_failures,
            "raw_pitch_events": raw_pitch_events,
            "typed_pitch_events": typed_pitch_events,
            "typed_pitch_coverage": typed_coverage,
            "arsenal_pitch_types": "|".join(ordered_codes),
            "arsenal_usage": _json_map(usage) if usage else "",
            "pitch_counts_json": _json_map(dict(total_counts)) if total_counts else "",
            "pitch_type_descriptions_json": _json_map({code: descriptions.get(code, "") for code in ordered_codes}) if ordered_codes else "",
            "audit_eligible": eligible,
            "reason": reason,
            "source": "MLB_STATS_API_PRIOR_GAME_LIVE_FEED",
            "source_endpoint_version": "v1 gameLog + v1.1 game feed/live",
            "report_only": REPORT_ONLY,
            "production_authority": PRODUCTION_AUTHORITY,
            "capture_version": VERSION,
        })
        existing_keys.add(key)

    if additions:
        existing = pd.concat([existing, pd.DataFrame(additions)], ignore_index=True)
    for column in COLUMNS:
        if column not in existing.columns:
            existing[column] = pd.NA
    return existing[COLUMNS].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture frozen report-only pregame pitcher arsenal context.")
    parser.add_argument("--projection-log", default="data/projection_log.csv")
    parser.add_argument("--output", default="data/pitch_arsenal_context_log.csv")
    parser.add_argument("--recent-games", type=int, default=RECENT_GAMES_LIMIT)
    args = parser.parse_args()

    projection_path = Path(args.projection_log)
    output_path = Path(args.output)
    projections = pd.read_csv(projection_path) if projection_path.exists() else pd.DataFrame()
    existing = pd.read_csv(output_path) if output_path.exists() else pd.DataFrame(columns=COLUMNS)
    result = build_capture_records(projections, existing, recent_games_limit=max(1, int(args.recent_games)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    eligible = int(result.get("audit_eligible", pd.Series(dtype=bool)).map(_truthy).sum()) if not result.empty else 0
    print(
        f"pitch_arsenal_rows={len(result)} eligible_rows={eligible} "
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import base64
import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st

DEFAULT_REPO = "KingTud88/MLB-Prop-App"
PROJECTION_LOG_PATH = "data/projection_log.csv"

FIELDNAMES = [
    "game_pk", "game_date", "pitcher_id", "player", "team", "opponent", "venue",
    "game_time", "captured_at_utc", "app_version", "projection", "k_sd",
    "k_range_low", "k_range_high", "confidence", "data_quality", "simulation_draws",
    "opponent_k_pct", "pitch_limit", "umpire_k_factor", "weather_factor", "rest_factor",
    "actual_strikeouts", "resolved_at_utc",
]


def _config() -> tuple[str | None, str]:
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", DEFAULT_REPO)
    return token, str(repo)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def _read() -> tuple[list[dict[str, Any]], str | None]:
    token, repo = _config()
    if not token:
        return [], None
    url = f"https://api.github.com/repos/{repo}/contents/{PROJECTION_LOG_PATH}"
    response = requests.get(url, headers=_headers(token), timeout=20)
    if response.status_code == 404:
        return [], None
    response.raise_for_status()
    payload = response.json()
    raw = base64.b64decode(payload["content"]).decode("utf-8")
    return list(csv.DictReader(io.StringIO(raw))), payload["sha"]


def load_projections() -> list[dict[str, Any]]:
    rows, _ = _read()
    return rows


def _write(rows: list[dict[str, Any]], sha: str | None, message: str) -> None:
    token, repo = _config()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not configured in Streamlit Secrets.")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows([{field: row.get(field, "") for field in FIELDNAMES} for row in rows])
    url = f"https://api.github.com/repos/{repo}/contents/{PROJECTION_LOG_PATH}"
    body = {"message": message, "content": base64.b64encode(output.getvalue().encode("utf-8")).decode("ascii")}
    if sha:
        body["sha"] = sha
    response = requests.put(url, headers=_headers(token), data=json.dumps(body), timeout=20)
    response.raise_for_status()


def save_projection(record: dict[str, Any]) -> bool:
    return save_projections([record]) == 1


def save_projections(records: list[dict[str, Any]]) -> int:
    """Append many unique projections with one GitHub commit."""
    if not records:
        return 0
    rows, sha = _read()
    existing = {(str(row.get("game_pk")), str(row.get("pitcher_id")), str(row.get("game_date"))) for row in rows}
    added = 0
    for record in records:
        key = (str(record.get("game_pk")), str(record.get("pitcher_id")), str(record.get("game_date")))
        if key in existing:
            continue
        clean = {field: record.get(field, "") for field in FIELDNAMES}
        clean["captured_at_utc"] = clean["captured_at_utc"] or datetime.now(timezone.utc).isoformat()
        rows.append(clean)
        existing.add(key)
        added += 1
    if added:
        _write(rows, sha, f"Archive {added} daily pitcher projection(s)")
    return added


def resolve_completed_projections() -> int:
    rows, sha = _read()
    if not rows:
        return 0
    changed = 0
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "User-Agent": "StrikeOutKing9000/2.0.2"})
    for row in rows:
        if str(row.get("actual_strikeouts", "")).strip() not in ("", "None", "nan"):
            continue
        game_pk = str(row.get("game_pk", "")).strip()
        pitcher_id = str(row.get("pitcher_id", "")).strip()
        if not game_pk or not pitcher_id:
            continue
        try:
            response = session.get(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore", timeout=20)
            response.raise_for_status()
            payload = response.json()
            status = payload.get("gameData", {}).get("status", {}).get("abstractGameState")
            if status != "Final":
                continue
            found = None
            for side in ("away", "home"):
                players = payload.get("teams", {}).get(side, {}).get("players", {})
                player = players.get(f"ID{pitcher_id}")
                if player:
                    found = player.get("stats", {}).get("pitching", {}).get("strikeOuts")
                    break
            if found is None:
                continue
            row["actual_strikeouts"] = int(found)
            row["resolved_at_utc"] = datetime.now(timezone.utc).isoformat()
            changed += 1
        except (requests.RequestException, ValueError, TypeError):
            continue
    if changed:
        _write(rows, sha, f"Resolve {changed} projection outcome(s)")
    return changed

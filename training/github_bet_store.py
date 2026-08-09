from __future__ import annotations

import base64
import csv
import io
import json
from typing import Any

import requests
import streamlit as st

DEFAULT_REPO = "KingTud88/MLB-Prop-App"
BET_LOG_PATH = "data/bet_log.csv"


def _config() -> tuple[str | None, str]:
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", DEFAULT_REPO)
    return token, str(repo)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def load_bets() -> list[dict[str, Any]]:
    token, repo = _config()
    if not token:
        return []
    url = f"https://api.github.com/repos/{repo}/contents/{BET_LOG_PATH}"
    response = requests.get(url, headers=_headers(token), timeout=20)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    payload = response.json()
    raw = base64.b64decode(payload["content"]).decode("utf-8")
    return list(csv.DictReader(io.StringIO(raw)))


def save_bet(record: dict[str, Any]) -> None:
    token, repo = _config()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not configured in Streamlit Secrets.")
    url = f"https://api.github.com/repos/{repo}/contents/{BET_LOG_PATH}"
    headers = _headers(token)
    response = requests.get(url, headers=headers, timeout=20)
    if response.status_code == 404:
        existing, sha = "", None
    else:
        response.raise_for_status()
        payload = response.json()
        sha = payload["sha"]
        existing = base64.b64decode(payload["content"]).decode("utf-8")

    fieldnames = [
        "player", "game_date", "line", "side", "american_odds", "entered_at_utc",
        "projection", "model_probability", "implied_probability", "edge", "confidence",
        "actual_strikeouts", "game_pk", "pitcher_id",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    if existing.strip():
        rows = list(csv.DictReader(io.StringIO(existing)))
        writer.writeheader()
        writer.writerows(rows)
    else:
        writer.writeheader()
    writer.writerow(record)

    body = {"message": f"Record bet: {record.get('player', 'unknown player')}", "content": base64.b64encode(output.getvalue().encode("utf-8")).decode("ascii")}
    if sha:
        body["sha"] = sha
    result = requests.put(url, headers=headers, data=json.dumps(body), timeout=20)
    result.raise_for_status()

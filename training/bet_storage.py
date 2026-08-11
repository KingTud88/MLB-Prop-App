from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests

DEFAULT_REPO = "KingTud88/MLB-Prop-App"
DEFAULT_PATH = "data/bet_log.csv"


def _config(secrets: Any = None) -> tuple[str | None, str, str]:
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO", DEFAULT_REPO)
    path = os.getenv("GITHUB_BET_LOG_PATH", DEFAULT_PATH)
    if token is None and secrets is not None:
        try:
            token = secrets.get("GITHUB_TOKEN")
            repo = secrets.get("GITHUB_REPO", repo)
            path = secrets.get("GITHUB_BET_LOG_PATH", path)
        except Exception:
            pass
    return token, repo, path


def github_storage_configured(secrets: Any = None) -> bool:
    token, _, _ = _config(secrets)
    return bool(token)


def load_bet_log(local_path: str | Path, secrets: Any = None) -> pd.DataFrame:
    token, repo, path = _config(secrets)
    if token:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        response = requests.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=15)
        if response.status_code == 200:
            payload = response.json()
            raw = base64.b64decode(payload["content"]).decode("utf-8")
            return pd.read_csv(io.StringIO(raw))
        if response.status_code != 404:
            response.raise_for_status()
    local = Path(local_path)
    if local.exists():
        return pd.read_csv(local)
    return pd.DataFrame()


def append_bet(local_path: str | Path, record: dict[str, Any], secrets: Any = None) -> None:
    token, repo, path = _config(secrets)
    if token:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            payload = response.json()
            raw = base64.b64decode(payload["content"]).decode("utf-8")
            tracker = pd.read_csv(io.StringIO(raw))
            sha = payload["sha"]
        elif response.status_code == 404:
            tracker = pd.DataFrame()
            sha = None
        else:
            response.raise_for_status()
        tracker = pd.concat([tracker, pd.DataFrame([record])], ignore_index=True)
        content = tracker.to_csv(index=False)
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        body = {"message": "Record sportsbook bet", "content": encoded, "branch": "main"}
        if sha:
            body["sha"] = sha
        write = requests.put(url, headers=headers, json=body, timeout=15)
        write.raise_for_status()
        return

    local = Path(local_path)
    local.parent.mkdir(parents=True, exist_ok=True)
    exists = local.exists()
    pd.DataFrame([record]).to_csv(local, mode="a", header=not exists, index=False)

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from engine.ui_weather import clean_ui_text, weather_icon_for_display

DEFAULT_REPO = "KingTud88/MLB-Prop-App"
DEFAULT_PATH = "data/projection_archive.csv"


def _config(secrets: Any = None) -> tuple[str | None, str, str]:
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO", DEFAULT_REPO)
    path = os.getenv("GITHUB_PROJECTION_ARCHIVE_PATH", DEFAULT_PATH)
    if token is None and secrets is not None:
        try:
            token = secrets.get("GITHUB_TOKEN")
            repo = secrets.get("GITHUB_REPO", repo)
            path = secrets.get("GITHUB_PROJECTION_ARCHIVE_PATH", path)
        except Exception:
            pass
    return token, repo, path


def github_projection_storage_configured(secrets: Any = None) -> bool:
    token, _, _ = _config(secrets)
    return bool(token)


def _read_local(local_path: str | Path) -> pd.DataFrame:
    local = Path(local_path)
    if not local.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(local)
    except Exception:
        return pd.DataFrame()


def load_projection_archive(local_path: str | Path, secrets: Any = None) -> pd.DataFrame:
    """Load durable manual/archive data from GitHub when configured."""
    token, repo, path = _config(secrets)
    if token:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                payload = response.json()
                raw = base64.b64decode(payload["content"]).decode("utf-8")
                return pd.read_csv(io.StringIO(raw))
            if response.status_code != 404:
                response.raise_for_status()
        except requests.RequestException:
            pass
    return _read_local(local_path)


def save_projection_archive(local_path: str | Path, frame: pd.DataFrame, secrets: Any = None) -> None:
    """Persist the complete manual/archive overlay using restart-safe GitHub storage."""
    token, repo, path = _config(secrets)
    content = frame.to_csv(index=False)
    if token:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        last_error: Exception | None = None
        for _ in range(4):
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    sha = response.json().get("sha")
                elif response.status_code == 404:
                    sha = None
                else:
                    response.raise_for_status()
                    sha = None
                body = {
                    "message": "Persist projection archive and manual market lines",
                    "content": encoded,
                    "branch": "main",
                }
                if sha:
                    body["sha"] = sha
                write = requests.put(url, headers=headers, json=body, timeout=20)
                if write.status_code in {200, 201}:
                    local = Path(local_path)
                    local.parent.mkdir(parents=True, exist_ok=True)
                    local.write_text(content, encoding="utf-8")
                    return
                if write.status_code in {409, 422}:
                    continue
                write.raise_for_status()
            except requests.RequestException as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("Could not persist projection archive to GitHub after retries.")

    local = Path(local_path)
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(content, encoding="utf-8")


def overlay_manual_market_lines(slate: pd.DataFrame, archive: pd.DataFrame) -> pd.DataFrame:
    """Overlay durable manual execution lines onto frozen model rows without mutating projections."""
    result = slate.copy()
    if "weather_icon" in result.columns:
        levels = result["weather_delay_risk"] if "weather_delay_risk" in result.columns else pd.Series("UNKNOWN", index=result.index)
        result["weather_icon"] = [
            weather_icon_for_display(level, icon, unknown="")
            for level, icon in zip(levels.tolist(), result["weather_icon"].tolist())
        ]
    for col in (
        "manual_strikeout_line", "manual_outs_line", "manual_hits_allowed_line",
        "manual_outs_side", "manual_outs_decision_probability", "manual_outs_decision_reason", "manual_outs_side_frozen_at_utc",
        "manual_hits_allowed_side", "manual_hits_allowed_decision_probability", "manual_hits_allowed_decision_reason", "manual_hits_allowed_side_frozen_at_utc",
        "active_strikeout_line", "active_outs_line", "active_hits_allowed_line",
        "active_strikeout_line_source", "active_outs_line_source", "active_hits_allowed_line_source",
    ):
        if col not in result.columns:
            result[col] = pd.NA
    if "archive_source" not in result.columns:
        result["archive_source"] = ""
    if "archive_committed_at_utc" not in result.columns:
        result["archive_committed_at_utc"] = ""

    if result.empty or archive.empty:
        return result
    required = {"game_pk", "pitcher_id"}
    if not required.issubset(result.columns) or not required.issubset(archive.columns):
        return result

    archive_rows = archive.copy()
    archive_rows["_game_pk"] = archive_rows["game_pk"].astype(str).str.replace(r"\.0$", "", regex=True)
    archive_rows["_pitcher_id"] = archive_rows["pitcher_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    lookup = archive_rows.drop_duplicates(["_game_pk", "_pitcher_id"], keep="last").set_index(["_game_pk", "_pitcher_id"])

    specs = (
        ("manual_strikeout_line", "active_strikeout_line", "active_strikeout_line_source"),
        ("manual_outs_line", "active_outs_line", "active_outs_line_source"),
        ("manual_hits_allowed_line", "active_hits_allowed_line", "active_hits_allowed_line_source"),
    )
    for idx, row in result.iterrows():
        key = (
            str(row.get("game_pk", "")).replace(".0", ""),
            str(row.get("pitcher_id", "")).replace(".0", ""),
        )
        if key not in lookup.index:
            continue
        saved = lookup.loc[key]
        if isinstance(saved, pd.DataFrame):
            saved = saved.iloc[-1]
        for manual_col, line_col, source_col in specs:
            value = pd.to_numeric(pd.Series([saved.get(manual_col)]), errors="coerce").iloc[0]
            if pd.notna(value):
                result.at[idx, manual_col] = float(value)
                result.at[idx, line_col] = float(value)
                result.at[idx, source_col] = "MANUAL"
        for meta_col in (
            "manual_outs_side", "manual_outs_decision_probability", "manual_outs_decision_reason", "manual_outs_side_frozen_at_utc",
            "manual_hits_allowed_side", "manual_hits_allowed_decision_probability", "manual_hits_allowed_decision_reason", "manual_hits_allowed_side_frozen_at_utc",
        ):
            value = saved.get(meta_col)
            if pd.notna(value) and str(value).strip():
                result.at[idx, meta_col] = value
        source = clean_ui_text(saved.get("archive_source"))
        committed = clean_ui_text(saved.get("archive_committed_at_utc"))
        if source:
            result.at[idx, "archive_source"] = source
        if committed:
            result.at[idx, "archive_committed_at_utc"] = committed
    return result


def build_projection_archive_view(evidence: pd.DataFrame, archive: pd.DataFrame) -> pd.DataFrame:
    """Show every durable frozen evidence row, with manual lines layered on when available."""
    if evidence.empty:
        return archive.copy()
    result = overlay_manual_market_lines(evidence, archive)
    if "archive_source" not in result.columns:
        result["archive_source"] = "AUTOMATIC_FROZEN_EVIDENCE"
    else:
        blank = result["archive_source"].fillna("").astype(str).str.strip().eq("")
        result.loc[blank, "archive_source"] = "AUTOMATIC_FROZEN_EVIDENCE"
    if "archive_committed_at_utc" not in result.columns:
        result["archive_committed_at_utc"] = ""
    return result

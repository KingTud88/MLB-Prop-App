from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
PROJECTION_LOG = ROOT / "data" / "projection_log.csv"
OUTPUT_LOG = ROOT / "data" / "catcher_context_log.csv"
MLB_API = "https://statsapi.mlb.com/api/v1"
CAPTURE_VERSION = "catcher-context-v1-report-only"
COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "team_id",
    "catcher_id", "catcher_name", "catcher_source", "catcher_confirmed",
    "catcher_captured_at_utc", "catcher_factor", "candidate_authority",
    "actual_strikeouts", "actual_pitches", "actual_batters_faced", "actual_outs",
    "capture_version",
]


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _batting_order(node: dict) -> int:
    try:
        return int(node.get("battingOrder") or 0)
    except (TypeError, ValueError):
        return 0


def _is_catcher(node: dict) -> bool:
    position = node.get("position") or {}
    if str(position.get("abbreviation") or "").upper() == "C":
        return True
    for item in node.get("allPositions") or []:
        if str((item or {}).get("abbreviation") or "").upper() == "C":
            return True
    return False


def parse_starting_catcher(payload: dict, team_id: int) -> dict[str, object]:
    """Return the posted starting catcher for a team from MLB's game boxscore.

    We require the player to be in the batting order so a backup catcher or
    postgame defensive replacement cannot masquerade as the pregame starter.
    """
    teams = payload.get("teams") or {}
    target: dict | None = None
    for side in ("away", "home"):
        candidate = teams.get(side) or {}
        try:
            candidate_id = int((candidate.get("team") or {}).get("id"))
        except (TypeError, ValueError):
            continue
        if candidate_id == int(team_id):
            target = candidate
            break
    if target is None:
        return {}

    candidates: list[tuple[int, dict]] = []
    for node in (target.get("players") or {}).values():
        if not isinstance(node, dict) or not _is_catcher(node):
            continue
        order = _batting_order(node)
        if order <= 0:
            continue
        candidates.append((order, node))
    if not candidates:
        return {}

    candidates.sort(key=lambda item: item[0])
    node = candidates[0][1]
    person = node.get("person") or {}
    try:
        catcher_id = int(person.get("id"))
    except (TypeError, ValueError):
        return {}
    return {
        "catcher_id": catcher_id,
        "catcher_name": str(person.get("fullName") or person.get("name") or "Unknown"),
        "catcher_source": "MLB_POSTED_LINEUP",
        "catcher_confirmed": True,
    }


def fetch_starting_catcher(game_pk: int, team_id: int, session: requests.Session | None = None) -> dict[str, object]:
    http = session or requests.Session()
    try:
        response = http.get(f"{MLB_API}/game/{int(game_pk)}/boxscore", timeout=15)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return {}
        return parse_starting_catcher(payload, int(team_id))
    except (requests.RequestException, ValueError, TypeError):
        return {}


def _actual(row: pd.Series, key: str) -> object:
    value = pd.to_numeric(pd.Series([row.get(key)]), errors="coerce").iloc[0]
    return value if pd.notna(value) else np.nan


def build_capture(projections: pd.DataFrame, existing: pd.DataFrame | None = None) -> pd.DataFrame:
    if projections.empty or not {"game_pk", "pitcher_id", "team_id"}.issubset(projections.columns):
        return pd.DataFrame(columns=COLUMNS)

    work = projections.copy()
    work["game_pk"] = pd.to_numeric(work["game_pk"], errors="coerce")
    work["pitcher_id"] = pd.to_numeric(work["pitcher_id"], errors="coerce")
    work["team_id"] = pd.to_numeric(work["team_id"], errors="coerce")
    work = work.dropna(subset=["game_pk", "pitcher_id", "team_id"])
    work = work.sort_values("captured_at_utc" if "captured_at_utc" in work.columns else "game_date")
    work = work.drop_duplicates(["game_pk", "pitcher_id"], keep="last")

    prior: dict[tuple[int, int], dict[str, object]] = {}
    if existing is not None and not existing.empty and {"game_pk", "pitcher_id"}.issubset(existing.columns):
        for _, row in existing.iterrows():
            try:
                key = (int(row["game_pk"]), int(row["pitcher_id"]))
            except (TypeError, ValueError):
                continue
            prior[key] = row.to_dict()

    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, object]] = []
    cache: dict[tuple[int, int], dict[str, object]] = {}
    for _, row in work.iterrows():
        key = (int(row["game_pk"]), int(row["pitcher_id"]))
        old = prior.get(key, {})
        confirmed_old = str(old.get("catcher_confirmed", "")).strip().lower() in {"true", "1"}
        if confirmed_old and pd.notna(old.get("catcher_id")):
            catcher = {
                "catcher_id": old.get("catcher_id"),
                "catcher_name": old.get("catcher_name", "Unknown"),
                "catcher_source": old.get("catcher_source", "MLB_POSTED_LINEUP"),
                "catcher_confirmed": True,
            }
            captured_at = old.get("catcher_captured_at_utc", "") or now
        else:
            game_team = (int(row["game_pk"]), int(row["team_id"]))
            if game_team not in cache:
                cache[game_team] = fetch_starting_catcher(*game_team)
            catcher = cache[game_team]
            captured_at = now if catcher else ""

        rows.append({
            "game_date": row.get("game_date", ""),
            "game_pk": key[0],
            "pitcher_id": key[1],
            "player": row.get("player", "Unknown"),
            "team": row.get("team", "UNK"),
            "team_id": int(row["team_id"]),
            "catcher_id": catcher.get("catcher_id", np.nan) if catcher else np.nan,
            "catcher_name": catcher.get("catcher_name", "") if catcher else "",
            "catcher_source": catcher.get("catcher_source", "UNAVAILABLE") if catcher else "UNAVAILABLE",
            "catcher_confirmed": bool(catcher.get("catcher_confirmed", False)) if catcher else False,
            "catcher_captured_at_utc": captured_at,
            # Deliberately neutral until forward evidence proves a catcher signal.
            "catcher_factor": 1.0,
            "candidate_authority": "REPORT_ONLY",
            "actual_strikeouts": _actual(row, "actual_strikeouts"),
            "actual_pitches": _actual(row, "actual_pitches"),
            "actual_batters_faced": _actual(row, "actual_batters_faced"),
            "actual_outs": _actual(row, "actual_outs"),
            "capture_version": CAPTURE_VERSION,
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture posted starting catchers for archived pitcher projections; report-only.")
    parser.add_argument("--projection-log", type=Path, default=PROJECTION_LOG)
    parser.add_argument("--output", type=Path, default=OUTPUT_LOG)
    args = parser.parse_args()

    projections = _load(args.projection_log)
    if projections.empty:
        raise SystemExit("No projection history available")
    existing = _load(args.output)
    out = build_capture(projections, existing)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    confirmed = int(out["catcher_confirmed"].fillna(False).astype(bool).sum()) if not out.empty else 0
    resolved = int(pd.to_numeric(out.get("actual_strikeouts"), errors="coerce").notna().sum()) if not out.empty else 0
    print(f"rows={len(out)} confirmed_catchers={confirmed} resolved_rows={resolved} factor=1.0 authority=REPORT_ONLY")


if __name__ == "__main__":
    main()

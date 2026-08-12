from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

import requests

MLB_API = "https://statsapi.mlb.com/api/v1"
LINEUP_CONFIRMED = "CONFIRMED_LINEUP"
LINEUP_ACTIVE_ROSTER = "ACTIVE_ROSTER"


@dataclass(frozen=True)
class LineupContext:
    source: str
    confirmed: bool
    player_ids: tuple[int, ...]
    spots: tuple[tuple[int, int], ...]
    fingerprint: str

    @property
    def batter_count(self) -> int:
        return len(self.player_ids)


def lineup_fingerprint(player_ids: tuple[int, ...]) -> str:
    if not player_ids:
        return ""
    payload = ",".join(str(int(pid)) for pid in player_ids)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _ordered_ids(team: dict[str, Any]) -> tuple[int, ...]:
    # MLB boxscores commonly expose battingOrder directly. Keep a defensive
    # player-level fallback so a harmless response-shape difference does not
    # turn a posted lineup into a false roster fallback.
    direct = team.get("battingOrder") or []
    ordered: list[int] = []
    for value in direct:
        try:
            pid = int(value)
        except (TypeError, ValueError):
            continue
        if pid not in ordered:
            ordered.append(pid)

    if len(ordered) >= 9:
        return tuple(ordered[:9])

    player_rows: list[tuple[int, int]] = []
    for node in (team.get("players") or {}).values():
        try:
            pid = int((node.get("person") or {}).get("id"))
            raw_order = node.get("battingOrder")
            order = int(raw_order)
        except (TypeError, ValueError):
            continue
        if order <= 0:
            continue
        player_rows.append((order, pid))
    player_rows.sort()
    for _, pid in player_rows:
        if pid not in ordered:
            ordered.append(pid)
    return tuple(ordered[:9])


def get_confirmed_lineup(
    game_pk: int,
    opponent_team_id: int,
    *,
    session: requests.Session | None = None,
) -> LineupContext:
    """Return the posted nine-man opponent batting order when MLB exposes it.

    A lineup is only called confirmed when nine unique hitters are available for
    the requested opponent team. Anything incomplete safely returns the active-
    roster fallback marker; callers may then build the matchup from the roster.
    """
    fallback = LineupContext(LINEUP_ACTIVE_ROSTER, False, (), (), "")
    if not game_pk or not opponent_team_id:
        return fallback

    own_session = session is None
    http = session or requests.Session()
    if own_session:
        http.headers.update({"Accept": "application/json", "User-Agent": "StrikeOutKing9000/3.6"})
    try:
        response = http.get(f"{MLB_API}/game/{int(game_pk)}/boxscore", timeout=12)
        response.raise_for_status()
        payload = response.json()
        teams = payload.get("teams") or {}
        target: dict[str, Any] | None = None
        for side in ("away", "home"):
            candidate = teams.get(side) or {}
            try:
                team_id = int((candidate.get("team") or {}).get("id"))
            except (TypeError, ValueError):
                continue
            if team_id == int(opponent_team_id):
                target = candidate
                break
        if target is None:
            return fallback

        ids = _ordered_ids(target)
        if len(ids) < 9:
            return fallback
        ids = ids[:9]
        spots = tuple((pid, idx + 1) for idx, pid in enumerate(ids))
        return LineupContext(
            source=LINEUP_CONFIRMED,
            confirmed=True,
            player_ids=ids,
            spots=spots,
            fingerprint=lineup_fingerprint(ids),
        )
    except (requests.RequestException, ValueError, TypeError):
        return fallback

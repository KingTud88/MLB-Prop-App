"""StrikeOut King 9000 projection engine package."""

from __future__ import annotations

import requests as _requests

_TEAM_NAMES_TO_ABBR = {
    "Los Angeles Angels": "LAA", "Arizona Diamondbacks": "ARI", "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS", "Chicago Cubs": "CHC", "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE", "Colorado Rockies": "COL", "Detroit Tigers": "DET",
    "Houston Astros": "HOU", "Kansas City Royals": "KCR", "Los Angeles Dodgers": "LAD",
    "Washington Nationals": "WSH", "New York Mets": "NYM", "Oakland Athletics": "ATH",
    "Athletics": "ATH", "Pittsburgh Pirates": "PIT", "San Diego Padres": "SDP",
    "Seattle Mariners": "SEA", "San Francisco Giants": "SFG", "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TBR", "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR",
    "Minnesota Twins": "MIN", "Philadelphia Phillies": "PHI", "Atlanta Braves": "ATL",
    "Chicago White Sox": "CHW", "Miami Marlins": "MIA", "New York Yankees": "NYY",
    "Milwaukee Brewers": "MIL",
}

_original_requests_get = _requests.get


def _normalize_odds_events_response(response):
    try:
        payload = response.json()
        if not isinstance(payload, list):
            return
        for event in payload:
            if not isinstance(event, dict):
                continue
            for field in ("home_team", "away_team"):
                name = str(event.get(field, "")).strip()
                abbr = _TEAM_NAMES_TO_ABBR.get(name)
                if abbr:
                    event[field] = abbr
        response._strikeout_king_normalized_json = payload
        response.json = lambda: response._strikeout_king_normalized_json
    except Exception:
        pass


def _requests_get_with_odds_event_normalization(url, *args, **kwargs):
    response = _original_requests_get(url, *args, **kwargs)
    url_text = str(url)
    if "/sports/baseball_mlb/events" in url_text and "/events/" not in url_text.rstrip("/").split("/events", 1)[-1]:
        _normalize_odds_events_response(response)
    return response


_requests.get = _requests_get_with_odds_event_normalization

# ---------------------------------------------------------------------------
# Opposing-batter profile UI hook
# ---------------------------------------------------------------------------
# The dedicated data layer already exists in engine/opposing_batters.py. We
# wire it into the existing pitcher selector here so streamlit_app.py does not
# need another risky large-file edit. The first CSS markdown call reserves a
# main-page slot; after a pitcher is selected, that slot is filled in place.
try:
    import streamlit as _st

    _original_markdown = _st.markdown
    _original_selectbox = _st.selectbox
    _opponent_slot = None
    _slot_reserved = False
    _last_pitcher_key = None

    def _reserve_opponent_slot(*args, **kwargs):
        global _opponent_slot, _slot_reserved
        result = _original_markdown(*args, **kwargs)
        if not _slot_reserved:
            try:
                _opponent_slot = _st.empty()
                _slot_reserved = True
            except Exception:
                _opponent_slot = None
        return result

    def _pitcher_hand(pitcher_id):
        try:
            response = _requests.get(
                f"https://statsapi.mlb.com/api/v1/people/{int(pitcher_id)}",
                params={},
                timeout=10,
                headers={"Accept": "application/json", "User-Agent": "StrikeOutKing9000/3.5"},
            )
            response.raise_for_status()
            return str(
                ((response.json().get("people") or [{}])[0].get("pitchingHand") or {}).get("code", "")
            ).upper()
        except Exception:
            return ""

    def _render_opponent_profile(game_key):
        if _opponent_slot is None:
            return
        try:
            from .opposing_batters import get_opposing_batters, matchup_summary

            parts = str(game_key).split(":", 1)
            if len(parts) != 2:
                return
            game_pk, pitcher_id = int(parts[0]), int(parts[1])

            schedule = _original_requests_get(
                "https://statsapi.mlb.com/api/v1/schedule",
                params={"sportId": 1, "gamePk": game_pk, "hydrate": "team"},
                timeout=12,
                headers={"Accept": "application/json", "User-Agent": "StrikeOutKing9000/3.5"},
            )
            schedule.raise_for_status()
            games = [
                game
                for day in schedule.json().get("dates", [])
                for game in day.get("games", [])
            ]
            if not games:
                return

            game = games[0]
            teams = game.get("teams", {}) or {}
            opponent = None
            opponent_team_id = None
            pitcher_team = None
            for side, other in (("away", "home"), ("home", "away")):
                node = teams.get(side, {}) or {}
                probable = node.get("probablePitcher", {}) or {}
                if int(probable.get("id", -1)) == pitcher_id:
                    pitcher_team = node.get("team", {}).get("name", "")
                    other_node = teams.get(other, {}) or {}
                    opponent = other_node.get("team", {}).get("abbreviation") or other_node.get("team", {}).get("name")
                    opponent_team_id = other_node.get("team", {}).get("id")
                    break

            hand = _pitcher_hand(pitcher_id)
            season = int(str(game.get("gameDate", ""))[:4] or 2026)
            batters = get_opposing_batters(str(opponent or ""), hand, season, opponent_team_id)
            summary = matchup_summary(batters)

            with _opponent_slot.container():
                _st.markdown(
                    '<div class="section-head">OPPOSING BATTER K-PROFILE</div>',
                    unsafe_allow_html=True,
                )
                if batters.empty:
                    _st.caption("No active-roster hitter split data is available yet for this matchup.")
                    return

                _st.caption(
                    f"{opponent} vs {hand}-handed pitcher · {season} season · "
                    f"weighted K% {summary['k_rate']:.1%} · {summary['high']} high-K bats · "
                    "active-roster profile; confirmed lineup may differ"
                )

                display = batters.head(9).copy()
                display["K% vs Pitcher"] = display["K% vs Pitcher"].map(lambda x: f"{x:.1%}")
                display["PA"] = display["PA"].map(lambda x: f"{x:.0f}")

                def _highlight(row):
                    text = str(row.get("K% vs Pitcher", "0%")).replace("%", "")
                    try:
                        rate = float(text)
                    except ValueError:
                        rate = 0.0
                    if rate >= 30.0:
                        return ["background-color: rgba(240,25,60,.24); font-weight: 800"] * len(row)
                    if rate >= 25.0:
                        return ["background-color: rgba(255,209,102,.14); font-weight: 700"] * len(row)
                    return [""] * len(row)

                _st.dataframe(
                    display[["Batter", "Hand", "K% vs Pitcher", "PA", "Risk"]].style.apply(_highlight, axis=1),
                    use_container_width=True,
                    hide_index=True,
                )
                _st.caption("🔥 HIGH = 30%+ K rate · ⚠️ ELEVATED = 25–29.9% · Risk is based on pitcher-hand split.")
        except Exception:
            # Scouting information is supplemental; never let it break the core projection.
            pass

    def _selectbox_with_opponent_profile(label, options, *args, **kwargs):
        result = _original_selectbox(label, options, *args, **kwargs)
        global _last_pitcher_key
        if str(label).strip().lower() == "pitcher" and result is not None:
            key = str(result)
            if key != _last_pitcher_key:
                _last_pitcher_key = key
                _render_opponent_profile(key)
        return result

    _st.markdown = _reserve_opponent_slot
    _st.selectbox = _selectbox_with_opponent_profile
except Exception:
    pass

from .projection_engine import ProjectionEngine, ProjectionResult

__all__ = ["ProjectionEngine", "ProjectionResult"]

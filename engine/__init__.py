"""StrikeOut King 9000 projection engine package."""

from __future__ import annotations

import inspect as _inspect
import requests as _requests

from runtime_http import (
    install_requests_resilience as _install_requests_resilience,
    set_source_health_observer as _set_source_health_observer,
)

_install_requests_resilience()

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
_TEAM_IDS = {"LAA":108,"ARI":109,"BAL":110,"BOS":111,"CHC":112,"CIN":113,"CLE":114,"COL":115,"DET":116,"HOU":117,"KCR":118,"LAD":119,"WSH":120,"NYM":121,"ATH":133,"PIT":134,"SDP":135,"SEA":136,"SFG":137,"STL":138,"TBR":139,"TEX":140,"TOR":141,"MIN":142,"PHI":143,"ATL":144,"CHW":145,"MIA":146,"NYY":147,"MIL":158}

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
                abbr = _TEAM_NAMES_TO_ABBR.get(str(event.get(field, "")).strip())
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

try:
    import streamlit as _st

    _original_markdown = _st.markdown
    _opponent_slot = None
    _slot_reserved = False
    _profile_rendering = False
    _last_profile_key = None
    _source_health_slots = {}

    def _source_health_session_id():
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            try:
                context = get_script_run_ctx(suppress_warning=True)
            except TypeError:
                context = get_script_run_ctx()
            return str(getattr(context, "session_id", "") or "")
        except Exception:
            return ""

    def _source_health_checked_text(row):
        value = str(row.get("last_attempt_at_utc") or "").strip()
        if not value:
            return "not checked"
        if "T" in value:
            value = value.split("T", 1)[1]
        return value.replace("Z", " UTC")

    def _render_source_health(snapshot, event_host):
        """Refresh a presentation-only health slot after tracked source calls."""
        session_id = _source_health_session_id()
        if not session_id:
            return
        rows = {str(row.get("host") or ""): row for row in snapshot}
        event = rows.get(str(event_host or ""), {})
        if (
            event_host == "statsapi.mlb.com"
            and str(event.get("last_path") or "") == "/api/v1/schedule"
            and session_id not in _source_health_slots
        ):
            _source_health_slots[session_id] = _st.sidebar.empty()
        slot = _source_health_slots.get(session_id)
        if slot is None:
            return
        with slot.container():
            _original_markdown("#### SOURCE HEALTH")
            for host in ("statsapi.mlb.com", "api.open-meteo.com"):
                row = rows.get(host, {})
                service = str(row.get("service") or host)
                status = str(row.get("status") or "NOT CHECKED")
                checked = _source_health_checked_text(row)
                _st.caption(f"{service}: {status} · {checked}")

    _set_source_health_observer(_render_source_health)

    def _pitcher_hand(pitcher_id):
        try:
            response = _original_requests_get(
                f"https://statsapi.mlb.com/api/v1/people/{int(pitcher_id)}",
                timeout=10,
                headers={"Accept": "application/json", "User-Agent": "StrikeOutKing9000/3.5"},
            )
            response.raise_for_status()
            person = (response.json().get("people") or [{}])[0]
            return str((person.get("pitchingHand") or {}).get("code", "")).upper()
        except Exception:
            return ""

    def _find_game_from_call_stack():
        for frame_info in _inspect.stack(context=0):
            frame = frame_info.frame
            game = frame.f_locals.get("game")
            if game is not None and all(hasattr(game, attr) for attr in ("pitcher_id", "opponent", "team", "game_time")):
                return game
        return None

    def _render_opponent_profile(game):
        global _profile_rendering, _last_profile_key
        if _opponent_slot is None or game is None or _profile_rendering:
            return
        key = getattr(game, "key", "")
        if key == _last_profile_key:
            return
        _profile_rendering = True
        try:
            from .opposing_batters import get_opposing_batters, matchup_summary

            opponent = str(game.opponent or "").upper()
            team_id = _TEAM_IDS.get(opponent)
            hand = _pitcher_hand(game.pitcher_id)
            if not team_id or hand not in {"R", "L"}:
                return

            season = int(str(game.game_time or "")[:4] or 2026)
            batters = get_opposing_batters(opponent, hand, season, team_id)
            summary = matchup_summary(batters)

            with _opponent_slot.container():
                _original_markdown('<div class="section-head">OPPOSING BATTER K-PROFILE</div>', unsafe_allow_html=True)
                if batters.empty:
                    _st.caption("No active-roster hitter split data is available yet for this matchup.")
                    _last_profile_key = key
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
                    try:
                        rate = float(str(row.get("K% vs Pitcher", "0%")).replace("%", ""))
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
                _last_profile_key = key
        except Exception:
            # Supplemental scouting data must never break the core projection.
            pass
        finally:
            _profile_rendering = False

    def _reserve_opponent_slot(*args, **kwargs):
        global _opponent_slot, _slot_reserved
        result = _original_markdown(*args, **kwargs)
        if not _slot_reserved:
            try:
                _opponent_slot = _st.empty()
                _slot_reserved = True
            except Exception:
                _opponent_slot = None
        if not _profile_rendering:
            try:
                _render_opponent_profile(_find_game_from_call_stack())
            except Exception:
                pass
        return result

    _st.markdown = _reserve_opponent_slot
except Exception:
    pass

from .projection_engine import ProjectionEngine, ProjectionResult

# Keep the two paths auditable at the public result boundary. The projection
# engine stores the raw independent probabilities in metadata; expose those
# exact arrays through the dedicated result fields instead of accidentally
# returning the blended ensemble probabilities for both paths.
_original_project = ProjectionEngine.project

def _project_with_independent_probability_fields(*args, **kwargs):
    result = _original_project(*args, **kwargs)
    raw_sim = result.metadata.get("raw_simulation_probabilities")
    raw_math = result.metadata.get("raw_mathematical_probabilities")
    if isinstance(raw_sim, dict) and isinstance(raw_math, dict):
        result = ProjectionResult(
            simulation_mean=result.simulation_mean,
            simulation_sd=result.simulation_sd,
            mathematical_mean=result.mathematical_mean,
            mathematical_sd=result.mathematical_sd,
            ensemble_mean=result.ensemble_mean,
            ensemble_sd=result.ensemble_sd,
            over_probabilities=result.over_probabilities,
            simulation_probabilities={float(k): float(v) for k, v in raw_sim.items()},
            mathematical_probabilities={float(k): float(v) for k, v in raw_math.items()},
            simulation_samples=result.simulation_samples,
            mathematical_pmf=result.mathematical_pmf,
            confidence=result.confidence,
            data_quality=result.data_quality,
            drivers=result.drivers,
            metadata=result.metadata,
        )
    return result

ProjectionEngine.project = _project_with_independent_probability_fields

__all__ = ["ProjectionEngine", "ProjectionResult"]

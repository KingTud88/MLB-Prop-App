from __future__ import annotations

import time
import requests
import pandas as pd
import streamlit as st
from training.github_bet_store import load_bets

MLB_API = "https://statsapi.mlb.com/api/v1"
MLB_LIVE_API = "https://statsapi.mlb.com/api/v1.1"
MLB_HEADERS = {"Cache-Control": "no-cache", "Pragma": "no-cache", "Accept": "application/json"}

st.set_page_config(page_title="Bet Tracker", page_icon="📊", layout="wide")
st.markdown(
    """
    <style>
    .block-container { padding-top: 3.25rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("📊 Bet Tracker")
st.caption("Persistent bets with live strikeout progress from MLB game data.")


def _fresh_params(**kwargs):
    params = dict(kwargs)
    params["_"] = str(time.time_ns())
    return params


def _resolve_pitcher_id(name: str) -> int | None:
    try:
        r = requests.get(f"{MLB_API}/people/search", params=_fresh_params(names=name), headers=MLB_HEADERS, timeout=10)
        if not r.ok:
            return None
        people = r.json().get("people", [])
        target = name.strip().lower()
        for person in people:
            if person.get("fullName", "").strip().lower() == target and person.get("id"):
                return int(person["id"])
        return int(people[0]["id"]) if people and people[0].get("id") else None
    except Exception:
        return None


def _date_pitching_stats(pitcher_id: int, game_date: str) -> tuple[float | None, str]:
    try:
        r = requests.get(
            f"{MLB_API}/stats",
            params=_fresh_params(
                stats="byDateRange",
                group="pitching",
                personId=pitcher_id,
                startDate=game_date,
                endDate=game_date,
                sportIds=1,
            ),
            headers=MLB_HEADERS,
            timeout=10,
        )
        if not r.ok:
            return None, "Stats endpoint unavailable"
        splits = r.json().get("stats", [{}])[0].get("splits", [])
        if not splits:
            return None, "No pitching stats posted for this date yet"
        stat = splits[0].get("stat", {}) or {}
        ks = stat.get("strikeOuts")
        if ks is not None:
            return float(ks), "Live stats"
        return None, "Pitching stats found, but strikeouts are not posted yet"
    except Exception:
        return None, "Date-stat lookup unavailable"


def _game_pitching_stats(game_pk: int, pitcher_id: int | None, target: str) -> tuple[float | None, str]:
    """Use MLB's by-game pitching stats endpoint; this is more direct than a cached game feed."""
    try:
        r = requests.get(
            f"{MLB_API}/stats",
            params=_fresh_params(stats="byGamePk", group="pitching", gamePk=game_pk, sportIds=1),
            headers=MLB_HEADERS,
            timeout=10,
        )
        if not r.ok:
            return None, "Game pitching stats unavailable"
        splits = []
        for block in r.json().get("stats", []):
            splits.extend(block.get("splits", []) or [])
        target = target.strip().lower()
        for split in splits:
            player = split.get("player", {}) or {}
            pid = player.get("id")
            pname = player.get("fullName", "").strip().lower()
            if (pitcher_id and pid == pitcher_id) or pname == target:
                ks = (split.get("stat", {}) or {}).get("strikeOuts")
                if ks is not None:
                    return float(ks), "Live stats"
        return None, "No game pitching stats posted yet"
    except Exception:
        return None, "Game pitching stats lookup unavailable"


def _pitcher_ks_from_feed(data: dict, target: str, pitcher_id: int | None) -> float | None:
    players = {}
    teams = data.get("liveData", {}).get("boxscore", {}).get("teams", {})
    for side in ("away", "home"):
        players.update(teams.get(side, {}).get("players", {}))

    player = players.get(f"ID{pitcher_id}") if pitcher_id else None
    if not player:
        for value in players.values():
            if value.get("person", {}).get("fullName", "").strip().lower() == target:
                player = value
                break
    if player:
        stats = player.get("stats", {}).get("pitching", {}) or {}
        ks = stats.get("strikeOuts")
        if ks is not None:
            return float(ks)

    strikeouts = 0
    found_pitcher_events = False
    for play in data.get("liveData", {}).get("plays", {}).get("allPlays", []):
        matchup = play.get("matchup", {}) or {}
        pitcher = matchup.get("pitcher", {}) or {}
        pid = pitcher.get("id")
        pname = pitcher.get("fullName", "").strip().lower()
        if (pitcher_id and pid == pitcher_id) or (not pitcher_id and pname == target):
            found_pitcher_events = True
            event = str(play.get("result", {}).get("event", "")).lower()
            event_type = str(play.get("result", {}).get("eventType", "")).lower()
            if event == "strikeout" or event_type == "strikeout":
                strikeouts += 1
    return float(strikeouts) if found_pitcher_events else None


@st.cache_data(ttl=15, show_spinner=False)
def live_strikeouts(player_name: str, game_date: str, game_pk: int | None = None, pitcher_id: int | None = None) -> tuple[float | None, str]:
    try:
        target = player_name.strip().lower()
        resolved_pitcher_id = pitcher_id or _resolve_pitcher_id(player_name)

        if resolved_pitcher_id:
            date_ks, date_status = _date_pitching_stats(resolved_pitcher_id, game_date)
            if date_ks is not None:
                return date_ks, date_status

        candidates: list[tuple[int, int]] = []
        if game_pk:
            candidates.append((int(game_pk), int(resolved_pitcher_id or 0)))

        schedule = requests.get(
            f"{MLB_API}/schedule",
            params=_fresh_params(sportId=1, date=game_date, hydrate="probablePitcher,team,linescore"),
            headers=MLB_HEADERS,
            timeout=10,
        )
        schedule.raise_for_status()
        for block in schedule.json().get("dates", []):
            for game in block.get("games", []):
                for side in ("away", "home"):
                    pitcher = game.get("teams", {}).get(side, {}).get("probablePitcher", {}) or {}
                    name = pitcher.get("fullName", "").strip().lower()
                    pid = int(pitcher.get("id", 0) or 0)
                    if (resolved_pitcher_id and pid == resolved_pitcher_id) or name == target:
                        if game.get("gamePk"):
                            pair = (int(game["gamePk"]), pid or int(resolved_pitcher_id or 0))
                            if pair not in candidates:
                                candidates.append(pair)

        if not candidates:
            return None, "No MLB game found for this pitcher on the saved date."

        last_status = "Scheduled"
        for candidate_game_pk, candidate_pitcher_id in candidates:
            ks, stats_status = _game_pitching_stats(candidate_game_pk, candidate_pitcher_id or resolved_pitcher_id, target)
            if ks is not None:
                return ks, stats_status

            response = requests.get(
                f"{MLB_LIVE_API}/game/{candidate_game_pk}/feed/live",
                params=_fresh_params(),
                headers=MLB_HEADERS,
                timeout=10,
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            data = response.json()
            game_status = data.get("gameData", {}).get("status", {}) or {}
            status = game_status.get("detailedState") or game_status.get("abstractGameState") or "Unknown"
            last_status = status

            ks = _pitcher_ks_from_feed(data, target, candidate_pitcher_id or resolved_pitcher_id)
            if ks is not None:
                return ks, status

            box = requests.get(
                f"{MLB_API}/game/{candidate_game_pk}/boxscore",
                params=_fresh_params(),
                headers=MLB_HEADERS,
                timeout=10,
            )
            if box.ok:
                box_data = box.json()
                box_status = box_data.get("gameData", {}).get("status", {}) or {}
                status = box_status.get("detailedState") or box_status.get("abstractGameState") or status
                last_status = status
                teams = box_data.get("teams", {}) or {}
                for side in ("away", "home"):
                    for value in (teams.get(side, {}).get("players", {}) or {}).values():
                        person = value.get("person", {}) or {}
                        if (candidate_pitcher_id and person.get("id") == candidate_pitcher_id) or person.get("fullName", "").strip().lower() == target:
                            stats = value.get("stats", {}).get("pitching", {}) or {}
                            if stats.get("strikeOuts") is not None:
                                return float(stats["strikeOuts"]), status

        return None, f"Game found, but MLB has not posted pitching stats yet ({last_status})."
    except Exception as exc:
        return None, f"Live lookup unavailable: {exc}"


try:
    records = load_bets()
except Exception as exc:
    st.error(f"Could not load the persistent bet tracker: {exc}")
    st.stop()

tracker = pd.DataFrame(records)
if tracker.empty:
    st.info("No saved bets yet. Analyze a sportsbook line in StrikeOut King 9000 and click Save to bet tracker.")
    st.stop()

for col in ["model_probability", "implied_probability", "edge", "line", "projection", "actual_strikeouts", "game_pk", "pitcher_id"]:
    if col in tracker:
        tracker[col] = pd.to_numeric(tracker[col], errors="coerce")

c1,c2,c3,c4=st.columns(4)
c1.metric("Tracked bets",len(tracker))
c2.metric("Average model probability",f"{tracker['model_probability'].mean():.1%}")
c3.metric("Average edge",f"{tracker['edge'].mean():+.1%}")
c4.metric("Positive-edge bets",f"{(tracker['edge']>0).sum()} / {len(tracker)}")

st.subheader("Live bet progress")
st.caption("The bar resolves the saved pitcher and game through MLB. Refresh during the game for the latest strikeout count.")
if st.button("🔄 Refresh live results", type="primary"):
    live_strikeouts.clear()
    st.rerun()

for idx,row in tracker.sort_values("entered_at_utc",ascending=False).iterrows():
    player=str(row.get("player","Unknown")); side=str(row.get("side","Over")).title(); line=float(row.get("line",0)); game_pk=row.get("game_pk"); pitcher_id=row.get("pitcher_id"); game_date=str(row.get("game_date", ""))[:10]
    game_pk_value=int(game_pk) if pd.notna(game_pk) else None
    pitcher_id_value=int(pitcher_id) if pd.notna(pitcher_id) else None
    actual,status=live_strikeouts(player,game_date,game_pk_value,pitcher_id_value)
    current=float(actual) if actual is not None else 0.0
    progress=min(max(current/max(line,0.5),0.0),1.0)
    st.markdown(f"### {player} — {side} {line:g}")
    st.progress(progress,text=f"{int(current)} Ks / {line:g} line")
    if actual is None:
        st.caption(f"{status}")
    elif status.lower() == "final":
        won=(current > line) if side == "Over" else (current < line)
        st.write(f"Final: **{int(current)} Ks** · **{'WIN' if won else 'LOSS'}**")
    else:
        ahead=(current > line) if side == "Over" else (current < line)
        st.write(f"Live: **{int(current)} Ks** · {status} · {'Currently ahead' if ahead else 'Currently behind'}")
    st.divider()

st.subheader("Saved bets")
show=tracker.sort_values("entered_at_utc",ascending=False).copy() if "entered_at_utc" in tracker else tracker.copy()
columns=["player","game_date","side","line","american_odds","projection","model_probability","implied_probability","edge","confidence","actual_strikeouts"]
columns=[c for c in columns if c in show.columns]
st.dataframe(show[columns].style.format({"model_probability":"{:.1%}","implied_probability":"{:.1%}","edge":"{:+.1%}","projection":"{:.2f}"}),hide_index=True,use_container_width=True)
st.download_button("Download bet tracker CSV",tracker.to_csv(index=False),file_name="bet_tracker.csv",mime="text/csv")
st.info("Confidence remains provisional until historical sportsbook lines are available for calibration.")
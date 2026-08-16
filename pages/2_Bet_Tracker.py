from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from engine.ui_theme import apply_page_theme

from automation.daily_projection_runner import LOG_PATH as PROJECTION_LOG, schedule as daily_schedule
from engine.bet_tracker import (
    MARKETS,
    default_line_for_market,
    grade_bet,
    grade_parlay,
    normalize_market,
    parse_parlay_legs,
    profit_for,
    projection_for_market,
    result_cell_css,
)
from navigation import render_sidebar
from training.bet_storage import append_bet, bet_row_key, delete_bet, load_bet_log

MLB_API = "https://statsapi.mlb.com/api/v1"
MLB_LIVE_API = "https://statsapi.mlb.com/api/v1.1"
MLB_HEADERS = {"Cache-Control": "no-cache", "Pragma": "no-cache", "Accept": "application/json"}
ROOT = Path(__file__).resolve().parents[1]
BET_LOG = ROOT / "data" / "bet_log.csv"
EASTERN = ZoneInfo("America/New_York")

st.set_page_config(page_title="Bet Tracker", page_icon="📊", layout="wide")
apply_page_theme()
render_sidebar("bets")
# BET_TRACKER_COMMAND_UI_V1
st.markdown(
    """
    <style>
    .block-container{max-width:1520px!important;padding-top:2.15rem!important;padding-bottom:4rem!important}
    .bt-hero{position:relative;overflow:hidden;margin:.1rem 0 .7rem;padding:1rem 1.15rem 1.05rem;border:1px solid rgba(80,108,136,.76);border-radius:18px;background:linear-gradient(110deg,rgba(8,28,50,.98),rgba(5,20,37,.98));box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 18px 42px rgba(0,0,0,.3)}
    .bt-hero:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(#ff3655,#a60c29)}
    .bt-kicker{font:900 .7rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.12em;color:#ff6a7d;text-transform:uppercase}
    .bt-title{margin:.22rem 0 .28rem;font-family:Impact,"Arial Black","Arial Narrow",sans-serif;font-size:clamp(2.6rem,5vw,4.7rem);line-height:.86;letter-spacing:.012em;color:#f5f1e9;text-transform:uppercase;text-shadow:3px 4px 0 #07182b}
    .bt-title span{color:#ec1638;-webkit-text-stroke:1px #f1eee7;paint-order:stroke fill}
    .bt-sub{max-width:1120px;color:#b6c6d5;font:650 .88rem/1.45 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .bt-rule{margin-top:.55rem;width:max-content;max-width:100%;padding:.25rem .58rem;border-top:1px solid rgba(236,22,56,.65);border-bottom:1px solid rgba(236,22,56,.65);color:#e6edf3;font:900 .67rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.09em;text-transform:uppercase}
    [data-testid="stMetric"]{position:relative;overflow:hidden;min-height:112px;padding:.75rem .8rem!important;border:1px solid rgba(77,108,137,.72)!important;border-radius:14px!important;background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98))!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 12px 28px rgba(0,0,0,.25)!important}
    [data-testid="stMetric"]:after{content:"";position:absolute;left:9%;right:9%;bottom:0;height:2px;background:linear-gradient(90deg,transparent,#ec1638,transparent);opacity:.72}
    [data-testid="stMetricLabel"]{color:#dce7ef!important;font-size:.76rem!important;font-weight:850!important;letter-spacing:.025em!important;text-transform:uppercase!important}
    [data-testid="stMetricValue"]{font-family:Impact,"Arial Narrow",sans-serif!important;color:#f7f3ec!important;font-size:2rem!important}
    .bt-section{width:max-content;min-width:245px;max-width:92%;margin:1.15rem auto .65rem;padding:.45rem 1.7rem;border:1px solid #ff3151;border-bottom-color:#790b1d;border-radius:8px;background:linear-gradient(180deg,#f21b3d,#b70d29);box-shadow:0 7px 16px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.22);color:#fff;font:900 .92rem/1.15 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.035em;text-align:center;text-transform:uppercase}
    div[data-testid="stExpander"]{margin:.58rem 0!important;border:1px solid rgba(77,106,135,.72)!important;border-radius:14px!important;background:linear-gradient(145deg,rgba(8,28,50,.97),rgba(4,17,31,.98))!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.035),0 12px 28px rgba(0,0,0,.21)!important}
    div[data-testid="stExpander"] summary{font-weight:900!important;color:#edf3f8!important}
    div[data-testid="stExpander"]:has(.bt-ticket-state.win){border-color:rgba(50,229,141,.62)!important;box-shadow:0 0 0 1px rgba(50,229,141,.08),0 12px 30px rgba(0,0,0,.24)!important}
    div[data-testid="stExpander"]:has(.bt-ticket-state.loss){border-color:rgba(255,71,98,.62)!important;box-shadow:0 0 0 1px rgba(255,71,98,.08),0 12px 30px rgba(0,0,0,.24)!important}
    div[data-testid="stExpander"]:has(.bt-ticket-state.live){border-color:rgba(74,191,230,.72)!important;box-shadow:0 0 0 1px rgba(74,191,230,.09),0 14px 34px rgba(0,0,0,.27)!important}
    div[data-testid="stExpander"]:has(.bt-ticket-state.pending){border-color:rgba(255,209,102,.58)!important}
    .bt-ticket-state{display:flex;align-items:center;justify-content:space-between;gap:.8rem;margin:.1rem 0 .65rem;padding:.58rem .68rem;border-radius:10px;background:rgba(5,23,42,.72);border:1px solid rgba(66,99,130,.62)}
    .bt-ticket-state .name{color:#f7f3ec;font:900 1.02rem/1.15 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .bt-ticket-state .status{white-space:nowrap;border-radius:999px;padding:.25rem .52rem;font:900 .65rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.05em;text-transform:uppercase}
    .bt-ticket-state.win .status{color:#58efad;border:1px solid rgba(50,229,141,.55);background:rgba(8,79,52,.38)}
    .bt-ticket-state.loss .status{color:#ff7085;border:1px solid rgba(255,71,98,.55);background:rgba(125,13,36,.34)}
    .bt-ticket-state.live .status{color:#8eddf4;border:1px solid rgba(74,191,230,.55);background:rgba(10,65,83,.38)}
    .bt-ticket-state.pending .status{color:#ffe08a;border:1px solid rgba(255,209,102,.5);background:rgba(98,71,8,.28)}
    div[data-testid="stProgress"]>div>div>div{background:#32e58d!important}
    @media (max-width:760px){.block-container{padding-top:1rem!important}.bt-hero{padding:.8rem}.bt-title{font-size:2.7rem}.bt-section{min-width:180px;padding:.4rem 1rem;font-size:.82rem}.bt-ticket-state{align-items:flex-start;flex-direction:column}}
    </style>
    <div class="bt-hero">
      <div class="bt-kicker">StrikeOut King 9000 · Wager Command Center</div>
      <div class="bt-title">BET <span>TRACKER</span></div>
      <div class="bt-sub">Open and live tickets stay first. Every saved pitcher prop is graded against MLB live/final pitching stats while sportsbook inputs remain recordkeeping-only.</div>
      <div class="bt-rule">OPEN FIRST · LIVE PROGRESS · SETTLED P/L</div>
    </div>
    """,
    unsafe_allow_html=True,
)


def _fresh_params(**kwargs):
    params = dict(kwargs)
    params["_"] = str(time.time_ns())
    return params


def _parse_ip(value: object) -> float | None:
    try:
        whole, frac = str(value).split(".", 1)
        frac_int = int(frac[:1] or 0)
        if frac_int not in (0, 1, 2):
            return None
        return float(int(whole) * 3 + frac_int)
    except Exception:
        return None


def _resolve_pitcher_id(name: str) -> int | None:
    try:
        r = requests.get(
            f"{MLB_API}/people/search",
            params=_fresh_params(names=name),
            headers=MLB_HEADERS,
            timeout=10,
        )
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


def _find_game(player_name: str, game_date: str, pitcher_id: int | None, saved_game_pk: int | None) -> tuple[int | None, str]:
    try:
        r = requests.get(
            f"{MLB_API}/schedule",
            params=_fresh_params(sportId=1, date=game_date, hydrate="probablePitcher,team"),
            headers=MLB_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        target = player_name.strip().lower()
        fallback_status = "Scheduled"
        for block in r.json().get("dates", []):
            for game in block.get("games", []):
                game_pk = int(game.get("gamePk", 0) or 0)
                status = (game.get("status", {}) or {}).get("detailedState") or "Scheduled"
                if saved_game_pk and game_pk == int(saved_game_pk):
                    return game_pk, status
                for side in ("away", "home"):
                    pitcher = game.get("teams", {}).get(side, {}).get("probablePitcher", {}) or {}
                    pid = int(pitcher.get("id", 0) or 0)
                    name = pitcher.get("fullName", "").strip().lower()
                    if (pitcher_id and pid == pitcher_id) or name == target:
                        return game_pk or None, status
                fallback_status = status
        return saved_game_pk, fallback_status
    except Exception:
        return saved_game_pk, "Status unavailable"


def _date_pitching_stats(pitcher_id: int, game_date: str) -> dict | None:
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
            return None
        blocks = r.json().get("stats", [])
        splits = blocks[0].get("splits", []) if blocks else []
        if not splits:
            return None
        return splits[0].get("stat", {}) or None
    except Exception:
        return None


# BET_TRACKER_LIVE_BOXSCORE_V1
def _live_pitching_stats(game_pk: int | None, pitcher_id: int | None) -> dict | None:
    """Return the pitcher's current game pitching line from MLB's live boxscore."""
    if not game_pk or not pitcher_id:
        return None
    try:
        r = requests.get(
            f"{MLB_LIVE_API}/game/{int(game_pk)}/feed/live",
            params=_fresh_params(),
            headers=MLB_HEADERS,
            timeout=10,
        )
        if not r.ok:
            return None
        teams = (((r.json().get("liveData", {}) or {}).get("boxscore", {}) or {}).get("teams", {}) or {})
        player_key = f"ID{int(pitcher_id)}"
        for side in ("away", "home"):
            players = ((teams.get(side, {}) or {}).get("players", {}) or {})
            player = players.get(player_key) or {}
            pitching = ((player.get("stats", {}) or {}).get("pitching", {}) or {})
            if pitching:
                return pitching
        return None
    except Exception:
        return None


def _live_status(game_pk: int | None, fallback: str) -> tuple[str, bool]:
    if not game_pk:
        final = str(fallback).lower() in {"final", "game over"}
        return fallback, final
    try:
        r = requests.get(
            f"{MLB_LIVE_API}/game/{int(game_pk)}/feed/live",
            params=_fresh_params(),
            headers=MLB_HEADERS,
            timeout=10,
        )
        if r.ok:
            status = (r.json().get("gameData", {}).get("status", {}) or {})
            detailed = status.get("detailedState") or status.get("abstractGameState") or fallback
            final = str(status.get("abstractGameState", "")).lower() == "final" or str(detailed).lower() in {"final", "game over"}
            return str(detailed), final
    except Exception:
        pass
    final = str(fallback).lower() in {"final", "game over"}
    return fallback, final


@st.cache_data(ttl=15, show_spinner=False)
def live_pitcher_prop(
    player_name: str,
    market: str,
    game_date: str,
    game_pk: int | None = None,
    pitcher_id: int | None = None,
) -> tuple[float | None, str, bool]:
    resolved_id = pitcher_id or _resolve_pitcher_id(player_name)
    found_game_pk, schedule_status = _find_game(player_name, game_date, resolved_id, game_pk)
    status, final = _live_status(found_game_pk, schedule_status)
    if not resolved_id:
        return None, "Pitcher could not be resolved", final
    # MLB's date-range stats endpoint can lag during live games. Read the
    # current boxscore first so in-progress K / H / outs update promptly, then
    # fall back to the date-range endpoint for final or transient cases.
    stat = _live_pitching_stats(found_game_pk, resolved_id)
    if not stat:
        stat = _date_pitching_stats(resolved_id, game_date)
    if not stat:
        return None, f"No pitching stats posted yet · {status}", final

    normalized = normalize_market(market)
    if normalized == "Strikeouts":
        value = stat.get("strikeOuts")
    elif normalized == "Hits Allowed":
        value = stat.get("hits")
    else:
        value = _parse_ip(stat.get("inningsPitched"))
    try:
        return float(value), status, final
    except (TypeError, ValueError):
        return None, f"{normalized} stat unavailable · {status}", final


@st.cache_data(ttl=120, show_spinner=False)
def todays_slate(day: str) -> tuple[list[dict], str | None]:
    try:
        return daily_schedule(day), None
    except Exception as exc:
        return [], f"Today's MLB slate could not be loaded: {exc}"


@st.cache_data(ttl=30, show_spinner=False)
def frozen_snapshot(day: str, pitcher_id: int, game_pk: int) -> dict | None:
    if not PROJECTION_LOG.exists():
        return None
    try:
        frame = pd.read_csv(PROJECTION_LOG)
    except Exception:
        return None
    if frame.empty or not {"game_date", "pitcher_id", "game_pk"}.issubset(frame.columns):
        return None
    game_dates = frame["game_date"].astype(str).str[:10]
    pitcher_ids = pd.to_numeric(frame["pitcher_id"], errors="coerce")
    game_pks = pd.to_numeric(frame["game_pk"], errors="coerce")
    matched = frame.loc[game_dates.eq(day) & pitcher_ids.eq(int(pitcher_id)) & game_pks.eq(int(game_pk))].copy()
    if matched.empty:
        return None
    if "captured_at_utc" in matched.columns:
        matched = matched.sort_values("captured_at_utc")
    return matched.iloc[-1].to_dict()


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _int_or_none(value: object) -> int | None:
    number = _num(value)
    return None if number is None else int(number)


def _format_odds(value: object) -> str:
    number = _num(value)
    return "—" if number is None else f"{int(number):+d}"


def _clean_text(value: object) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value or "").strip()


def load_tracker() -> pd.DataFrame:
    try:
        return load_bet_log(BET_LOG, st.secrets)
    except Exception as exc:
        st.error(f"Could not load the persistent bet tracker: {exc}")
        return pd.DataFrame()


with st.expander("➕ Add a bet", expanded=False):
    today = datetime.now(EASTERN).date()
    today_text = today.isoformat()
    slate, slate_error = todays_slate(today_text)
    if slate_error:
        st.warning(slate_error)

    slate_by_key = {
        f"{int(row['game_pk'])}:{int(row['pitcher_id'])}": row
        for row in slate
        if row.get("game_pk") and row.get("pitcher_id")
    }
    manual_key = "manual"
    pitcher_options = list(slate_by_key) + [manual_key]

    def _pitcher_label(key: str) -> str:
        if key == manual_key:
            return "✍️ Manual entry / pitcher not listed"
        row = slate_by_key[key]
        return f"{row.get('player', 'Unknown')} · {row.get('team', 'UNK')} vs {row.get('opponent', 'UNK')}"

    pick_col, market_col = st.columns([1.65, 1])
    pitcher_key = pick_col.selectbox(
        "Pitcher",
        pitcher_options,
        format_func=_pitcher_label,
        help="Today's announced probable starters from MLB. Use manual entry if a pitcher is missing or changes late.",
    )
    market = market_col.selectbox("Market", MARKETS)
    selected_pitcher = slate_by_key.get(pitcher_key)

    if selected_pitcher:
        snapshot = frozen_snapshot(today_text, int(selected_pitcher["pitcher_id"]), int(selected_pitcher["game_pk"]))
        auto_projection = projection_for_market(snapshot, market)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Matchup", f"{selected_pitcher.get('team', 'UNK')} vs {selected_pitcher.get('opponent', 'UNK')}")
        m2.metric("Game PK", int(selected_pitcher["game_pk"]))
        m3.metric("Pitcher ID", int(selected_pitcher["pitcher_id"]))
        m4.metric(f"{market} projection", "—" if auto_projection is None else f"{auto_projection:.2f}")
        st.caption(
            f"{selected_pitcher.get('venue', 'Unknown venue')} · {selected_pitcher.get('status', 'Scheduled')} · "
            + ("frozen Daily Run projection loaded" if auto_projection is not None else "no frozen Daily Run projection found yet")
        )

        with st.form("slate_bet_form", clear_on_submit=False):
            a, b, c, d = st.columns(4)
            side = a.selectbox("Side", ["Over", "Under"])
            line = b.number_input(
                "Line",
                min_value=0.0,
                max_value=30.0,
                value=default_line_for_market(market),
                step=0.5,
                key=f"slate_line_{normalize_market(market)}",
            )
            odds = c.number_input("American odds", min_value=-5000, max_value=5000, value=-110, step=5)
            stake = d.number_input("Stake", min_value=0.0, value=1.0, step=0.5)
            book = st.text_input("Sportsbook", value="")
            submitted = st.form_submit_button("💾 Save bet", type="primary", use_container_width=True)

        if submitted:
            record = {
                "player": str(selected_pitcher["player"]),
                "market": market,
                "game_date": today_text,
                "line": float(line),
                "side": side,
                "american_odds": int(odds),
                "stake": float(stake),
                "book": book.strip(),
                "entered_at_utc": datetime.utcnow().isoformat() + "Z",
                "projection": "" if auto_projection is None else float(auto_projection),
                "model_probability": "",
                "implied_probability": "",
                "edge": "",
                "confidence": "",
                "actual_strikeouts": "",
                "game_pk": int(selected_pitcher["game_pk"]),
                "pitcher_id": int(selected_pitcher["pitcher_id"]),
                "team": str(selected_pitcher.get("team", "")),
                "opponent": str(selected_pitcher.get("opponent", "")),
                "venue": str(selected_pitcher.get("venue", "")),
                "game_time": str(selected_pitcher.get("game_time", "")),
            }
            try:
                append_bet(BET_LOG, record, st.secrets)
                st.success("Bet saved to the tracker.")
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save bet: {exc}")
    else:
        st.caption("Manual mode keeps the tracker usable for late pitcher changes or props not present on today's probable-starter slate.")
        with st.form("manual_bet_form", clear_on_submit=False):
            a, b, c, d = st.columns(4)
            player = a.text_input("Pitcher")
            side = b.selectbox("Side", ["Over", "Under"])
            line = c.number_input(
                "Line",
                min_value=0.0,
                max_value=30.0,
                value=default_line_for_market(market),
                step=0.5,
                key=f"manual_line_{normalize_market(market)}",
            )
            odds = d.number_input("American odds", min_value=-5000, max_value=5000, value=-110, step=5)

            e, f, g, h = st.columns(4)
            stake = e.number_input("Stake", min_value=0.0, value=1.0, step=0.5)
            book = f.text_input("Sportsbook", value="")
            game_date = g.date_input("Game date", value=today)
            projection = h.number_input("Model projection (optional)", min_value=0.0, value=0.0, step=0.1)

            i, j = st.columns(2)
            game_pk_text = i.text_input("Game PK (optional)")
            pitcher_id_text = j.text_input("Pitcher ID (optional)")
            submitted = st.form_submit_button("💾 Save bet", type="primary", use_container_width=True)

        if submitted:
            if not player.strip():
                st.error("Enter a pitcher name before saving the bet.")
            else:
                record = {
                    "player": player.strip(),
                    "market": market,
                    "game_date": game_date.isoformat(),
                    "line": float(line),
                    "side": side,
                    "american_odds": int(odds),
                    "stake": float(stake),
                    "book": book.strip(),
                    "entered_at_utc": datetime.utcnow().isoformat() + "Z",
                    "projection": float(projection) if projection > 0 else "",
                    "model_probability": "",
                    "implied_probability": "",
                    "edge": "",
                    "confidence": "",
                    "actual_strikeouts": "",
                    "game_pk": game_pk_text.strip(),
                    "pitcher_id": pitcher_id_text.strip(),
                    "team": "",
                    "opponent": "",
                    "venue": "",
                    "game_time": "",
                }
                try:
                    append_bet(BET_LOG, record, st.secrets)
                    st.success("Bet saved to the tracker.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not save bet: {exc}")

tracker = load_tracker()
if tracker.empty:
    st.info("No saved bets yet. Use Add a bet above to start the ledger.")
    st.stop()

for col in ["line", "american_odds", "stake", "projection", "model_probability", "implied_probability", "edge", "game_pk", "pitcher_id"]:
    if col in tracker.columns:
        tracker[col] = pd.to_numeric(tracker[col], errors="coerce")
if "market" not in tracker.columns:
    tracker["market"] = "Strikeouts"
if "bet_type" not in tracker.columns:
    tracker["bet_type"] = "Straight"
tracker["bet_type"] = tracker["bet_type"].fillna("Straight").astype(str)
straight_mask = ~tracker["bet_type"].str.lower().eq("parlay")
tracker.loc[straight_mask, "market"] = tracker.loc[straight_mask, "market"].map(normalize_market)
tracker.loc[~straight_mask, "market"] = "Parlay"
if "parlay_legs" not in tracker.columns:
    tracker["parlay_legs"] = ""
if "stake" not in tracker.columns:
    tracker["stake"] = pd.NA
if "book" not in tracker.columns:
    tracker["book"] = ""

if st.button("🔄 Refresh live/final results", type="primary"):
    live_pitcher_prop.clear()
    st.rerun()

resolved_rows: list[dict] = []
ordered = tracker.sort_values("entered_at_utc", ascending=False, na_position="last") if "entered_at_utc" in tracker.columns else tracker.iloc[::-1]
with st.spinner("Checking saved bets against MLB pitching stats..."):
    for _, row in ordered.iterrows():
        bet_type = str(row.get("bet_type", "Straight") or "Straight").title()
        game_date = str(row.get("game_date", ""))[:10]
        stake = _num(row.get("stake"))
        odds = _num(row.get("american_odds"))
        if bet_type == "Parlay":
            legs = parse_parlay_legs(row.get("parlay_legs"))
            leg_grades = []
            leg_summaries = []
            leg_details = []
            statuses = []
            for leg in legs:
                leg_player = str(leg.get("player", "Unknown"))
                leg_market = normalize_market(leg.get("market"))
                leg_line = _num(leg.get("line")) or 0.0
                leg_side = str(leg.get("side", "Over")).title()
                actual, status, final = live_pitcher_prop(
                    leg_player,
                    leg_market,
                    str(leg.get("game_date", game_date))[:10],
                    _int_or_none(leg.get("game_pk")),
                    _int_or_none(leg.get("pitcher_id")),
                )
                leg_grade = grade_bet(leg_side, leg_line, actual, final)
                leg_grades.append(leg_grade)
                statuses.append(status)
                actual_text = "—" if actual is None else f"{actual:g}"
                leg_summaries.append(f"{leg_player} {leg_side} {leg_line:g} {leg_market} [{actual_text} · {leg_grade.result}]")
                leg_details.append({
                    "Player": leg_player,
                    "Market": leg_market,
                    "Side": leg_side,
                    "Line": leg_line,
                    "Actual": actual,
                    "Game Status": status,
                    "Result": leg_grade.result,
                    "Projection": _num(leg.get("projection")),
                    "Model Probability": _num(leg.get("model_probability")),
                })
            grade = grade_parlay(leg_grades)
            profit = profit_for(stake, odds, grade)
            resolved_rows.append({
                "_BetKey": bet_row_key(row),
                "Pitcher": f"{len(legs)}-leg parlay",
                "Matchup": "Multiple",
                "Date": game_date,
                "Market": "Parlay",
                "Bet": " | ".join(leg_summaries),
                "Odds": _format_odds(odds),
                "Book": str(row.get("book", "") or "—"),
                "Stake": stake,
                "Actual": "—",
                "Game Status": " / ".join(sorted(set(statuses))) if statuses else "Pending",
                "Result": grade.result,
                "Profit/Loss": profit,
                "Projection": None,
                "Model Probability": None,
                "Edge": None,
                "_Legs": leg_details,
            })
            continue

        player = str(row.get("player", "Unknown"))
        market = normalize_market(row.get("market"))
        line = _num(row.get("line")) or 0.0
        side = str(row.get("side", "Over")).title()
        actual, status, final = live_pitcher_prop(
            player,
            market,
            game_date,
            _int_or_none(row.get("game_pk")),
            _int_or_none(row.get("pitcher_id")),
        )
        grade = grade_bet(side, line, actual, final)
        profit = profit_for(stake, odds, grade)
        team = _clean_text(row.get("team"))
        opponent = _clean_text(row.get("opponent"))
        matchup = f"{team} vs {opponent}" if team and opponent else "—"
        resolved_rows.append({
            "_BetKey": bet_row_key(row),
            "Pitcher": player,
            "Matchup": matchup,
            "Date": game_date,
            "Market": market,
            "Bet": f"{side} {line:g}",
            "Odds": _format_odds(odds),
            "Book": str(row.get("book", "") or "—"),
            "Stake": stake,
            "Actual": actual,
            "Game Status": status,
            "Result": grade.result,
            "Profit/Loss": profit,
            "Projection": _num(row.get("projection")),
            "Model Probability": _num(row.get("model_probability")),
            "Edge": _num(row.get("edge")),
            "_Legs": [{
                "Player": player,
                "Market": market,
                "Side": side,
                "Line": line,
                "Actual": actual,
                "Game Status": status,
                "Result": grade.result,
                "Projection": _num(row.get("projection")),
                "Model Probability": _num(row.get("model_probability")),
            }],
        })

results = pd.DataFrame(resolved_rows)
# BET_TRACKER_STATUS_ORDER_V1
_status_priority = {
    "LIVE AHEAD": 0,
    "LIVE BEHIND": 0,
    "PENDING": 1,
    "WAITING": 1,
    "WIN": 2,
    "LOSS": 2,
    "PUSH": 2,
    "PUSH LEG": 2,
}
results["_StatusPriority"] = results["Result"].astype(str).str.upper().map(_status_priority).fillna(1).astype(int)
results = results.sort_values(["_StatusPriority", "Date"], ascending=[True, False], kind="stable").reset_index(drop=True)
wins = int((results["Result"] == "WIN").sum())
losses = int((results["Result"] == "LOSS").sum())
pushes = int(results["Result"].isin(["PUSH", "PUSH LEG"]).sum())
pending = int((~results["Result"].isin(["WIN", "LOSS", "PUSH", "PUSH LEG"])).sum())
profit_series = pd.to_numeric(results["Profit/Loss"], errors="coerce")
stake_series = pd.to_numeric(results["Stake"], errors="coerce")
graded_mask = results["Result"].isin(["WIN", "LOSS", "PUSH"]) & stake_series.notna()
net = float(profit_series.fillna(0).sum())
risked = float(stake_series.loc[graded_mask].sum()) if graded_mask.any() else 0.0
roi = net / risked if risked > 0 else None

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Tracked bets", len(results))
m2.metric("Record", f"{wins}-{losses}-{pushes}")
m3.metric("Pending / Live", pending)
m4.metric("Net P/L", f"{net:+.2f}" if profit_series.notna().any() else "—")
m5.metric("ROI", f"{roi:+.1%}" if roi is not None else "—")

if stake_series.isna().any():
    st.caption("Older saved bets without a stake are still graded, but they are excluded from P/L and ROI calculations.")
if "american_odds" in tracker.columns and pd.to_numeric(tracker["american_odds"], errors="coerce").isna().any():
    st.caption("Unpriced model tickets are still graded WIN/LOSS from MLB results, but they stay excluded from P/L and ROI because no sportsbook price was assumed.")

st.markdown('<div class="bt-section">Tracked Tickets</div>', unsafe_allow_html=True)

ticket_labels: dict[str, str] = {}
for _, ticket in results.iterrows():
    key = str(ticket.get("_BetKey", ""))
    if not key:
        continue
    date = str(ticket.get("Date", ""))
    pitcher = str(ticket.get("Pitcher", "Unknown"))
    market = str(ticket.get("Market", ""))
    bet = str(ticket.get("Bet", ""))
    book = str(ticket.get("Book", "") or "—")
    ticket_labels[key] = f"{date} · {pitcher} · {market} · {bet} · {book}"

with st.expander("🗑️ Delete a saved bet", expanded=False):
    if ticket_labels:
        delete_key = st.selectbox(
            "Saved ticket",
            options=list(ticket_labels),
            format_func=lambda key: ticket_labels[key],
            key="bet_tracker_delete_key",
        )
        confirm_delete = st.checkbox(
            "Confirm deletion of this saved ticket",
            value=False,
            key="bet_tracker_delete_confirm",
            help="Deletion permanently removes this tracked ticket from the persistent bet ledger.",
        )
        if st.button(
            "🗑️ Delete selected bet",
            disabled=not confirm_delete,
            use_container_width=True,
            key="bet_tracker_delete_button",
        ):
            try:
                if delete_bet(BET_LOG, delete_key, st.secrets):
                    st.success("Deleted the selected bet from Bet Tracker.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("That saved bet could not be found. Refresh the tracker and try again.")
            except Exception as exc:
                st.error(f"Could not delete bet: {exc}")
    else:
        st.caption("No saved tickets are available to delete.")

# BET_TRACKER_TICKET_CARDS_V1
# The resolver above remains the source of truth. This presentation preserves
# each resolved leg so live progress is visible instead of flattened into one row.

def _ticket_icon(result: object) -> str:
    state = str(result or "").upper()
    if state == "WIN":
        return "✅"
    if state == "LOSS":
        return "❌"
    if state == "LIVE AHEAD":
        return "🟢"
    if state == "LIVE BEHIND":
        return "🟠"
    if state in {"PUSH", "PUSH LEG"}:
        return "🟡"
    return "⏳"


def _progress_value(actual: object, line: object) -> float:
    current = _num(actual)
    target = _num(line)
    if current is None or target is None or target <= 0:
        return 0.0
    return max(0.0, min(float(current) / float(target), 1.0))


st.caption("Open any ticket to see each pitcher leg, live stat progress, line, game status, projection, and current grade.")
for ticket_index, (_, ticket) in enumerate(results.iterrows()):
    ticket_result = str(ticket.get("Result", "PENDING"))
    ticket_pitcher = str(ticket.get("Pitcher", "Unknown"))
    ticket_date = str(ticket.get("Date", ""))
    ticket_market = str(ticket.get("Market", ""))
    label = f"{_ticket_icon(ticket_result)} {ticket_date} · {ticket_pitcher} · {ticket_market} · {ticket_result}"
    with st.expander(label, expanded=ticket_result in {"LIVE AHEAD", "LIVE BEHIND"}):
        # BET_TRACKER_POTENTIAL_WIN_V1
        state_upper = ticket_result.upper()
        state_class = "win" if state_upper == "WIN" else "loss" if state_upper == "LOSS" else "live" if state_upper.startswith("LIVE") else "pending"
        st.markdown(
            f'<div class="bt-ticket-state {state_class}"><div class="name">{ticket_pitcher} · {ticket_market}</div><div class="status">{ticket_result}</div></div>',
            unsafe_allow_html=True,
        )
        h1, h2, h3, h4, h5, h6 = st.columns(6)
        h1.metric("Book", str(ticket.get("Book", "") or "—"))
        stake_value = _num(ticket.get("Stake"))
        h2.metric("Stake", "—" if stake_value is None else f"{stake_value:.2f}u")
        odds_value = _num(str(ticket.get("Odds", "")).replace("+", ""))
        h3.metric("Odds", str(ticket.get("Odds", "—")))
        potential_win = None
        if stake_value is not None and odds_value not in (None, 0):
            potential_win = stake_value * (odds_value / 100.0) if odds_value > 0 else stake_value * (100.0 / abs(odds_value))
        h4.metric("Potential Win", "—" if potential_win is None else f"+{potential_win:.2f}u")
        profit_value = _num(ticket.get("Profit/Loss"))
        h5.metric("P/L", "—" if profit_value is None else f"{profit_value:+.2f}u")
        h6.metric("Status", ticket_result)

        legs = ticket.get("_Legs", [])
        if not isinstance(legs, list) or not legs:
            st.caption("No leg detail is available for this older ticket.")
        for leg_number, leg in enumerate(legs, start=1):
            player = str(leg.get("Player", "Unknown"))
            market = str(leg.get("Market", ""))
            side = str(leg.get("Side", ""))
            line = _num(leg.get("Line")) or 0.0
            actual = _num(leg.get("Actual"))
            leg_result = str(leg.get("Result", "PENDING"))
            status = str(leg.get("Game Status", "Pending"))
            projection = _num(leg.get("Projection"))
            model_probability = _num(leg.get("Model Probability"))
            side_color = "#49efb0" if side.upper() == "OVER" else "#ff4b4b"
            st.markdown(
                f'<div style="border:1px solid #294b6c;border-radius:10px;padding:10px 12px;margin:8px 0 5px">'
                f'<div style="font-size:1.05rem;font-weight:900">{leg_number}. {player}</div>'
                f'<div style="margin-top:2px">{market} · <span style="color:{side_color};font-weight:900">{side.upper()}</span> {line:g}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Current", "—" if actual is None else f"{actual:g}")
            p2.metric("Target line", f"{line:g}")
            p3.metric("Projection", "—" if projection is None else f"{projection:.2f}")
            p4.metric("Model %", "—" if model_probability is None else f"{model_probability:.1%}")
            st.progress(_progress_value(actual, line))
            if actual is None:
                progress_text = "Waiting for MLB pitching stats"
            elif side.upper() == "OVER":
                needed = max(0.0, line - actual)
                progress_text = f"{actual:g} current · {needed:g} to the listed line" if needed > 0 else f"{actual:g} current · above the listed line"
            else:
                room = line - actual
                progress_text = f"{actual:g} current · {max(0.0, room):g} below the listed line" if room > 0 else f"{actual:g} current · at/above the listed line"
            st.caption(f"{_ticket_icon(leg_result)} {leg_result} · {status} · {progress_text}")

        st.caption("Live progress comes from MLB pitching stats. Sportsbook prices and stakes remain tracking-only inputs and never feed the projection model.")

st.download_button(
    "Download bet tracker CSV",
    results.drop(columns=["_BetKey", "_StatusPriority"], errors="ignore").to_csv(index=False),
    file_name="bet_tracker.csv",
    mime="text/csv",
)
st.caption("Sportsbook prices and stakes are tracking inputs only. They do not feed the pitcher projection models.")

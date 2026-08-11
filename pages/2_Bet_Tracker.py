from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from engine.bet_tracker import MARKETS, grade_bet, normalize_market, profit_for
from navigation import render_sidebar
from training.bet_storage import append_bet, load_bet_log

MLB_API = "https://statsapi.mlb.com/api/v1"
MLB_LIVE_API = "https://statsapi.mlb.com/api/v1.1"
MLB_HEADERS = {"Cache-Control": "no-cache", "Pragma": "no-cache", "Accept": "application/json"}
ROOT = Path(__file__).resolve().parents[1]
BET_LOG = ROOT / "data" / "bet_log.csv"
EASTERN = ZoneInfo("America/New_York")

st.set_page_config(page_title="Bet Tracker", page_icon="📊", layout="wide")
render_sidebar("bets")
st.markdown("<style>.block-container{padding-top:3.25rem!important}</style>", unsafe_allow_html=True)
st.title("📊 Bet Tracker")
st.caption("Your saved pitcher bets — Strikeouts, Total Outs, and Hits Allowed — graded against live/final MLB pitching stats.")


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


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _int_or_none(value: object) -> int | None:
    number = _num(value)
    return None if number is None else int(number)


def _format_odds(value: object) -> str:
    number = _num(value)
    return "—" if number is None else f"{int(number):+d}"


def load_tracker() -> pd.DataFrame:
    try:
        return load_bet_log(BET_LOG, st.secrets)
    except Exception as exc:
        st.error(f"Could not load the persistent bet tracker: {exc}")
        return pd.DataFrame()


with st.expander("➕ Add a bet", expanded=False):
    with st.form("manual_bet_form", clear_on_submit=False):
        a, b, c, d = st.columns(4)
        player = a.text_input("Pitcher")
        market = b.selectbox("Market", MARKETS)
        side = c.selectbox("Side", ["Over", "Under"])
        line = d.number_input("Line", min_value=0.0, max_value=30.0, value=5.5, step=0.5)

        e, f, g, h = st.columns(4)
        odds = e.number_input("American odds", min_value=-5000, max_value=5000, value=-110, step=5)
        stake = f.number_input("Stake", min_value=0.0, value=1.0, step=0.5)
        book = g.text_input("Sportsbook", value="")
        game_date = h.date_input("Game date", value=datetime.now(EASTERN).date())

        i, j, k = st.columns(3)
        projection = i.number_input("Model projection (optional)", min_value=0.0, value=0.0, step=0.1)
        game_pk_text = j.text_input("Game PK (optional)")
        pitcher_id_text = k.text_input("Pitcher ID (optional)")
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
tracker["market"] = tracker["market"].map(normalize_market)
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
        player = str(row.get("player", "Unknown"))
        market = normalize_market(row.get("market"))
        line = _num(row.get("line")) or 0.0
        side = str(row.get("side", "Over")).title()
        game_date = str(row.get("game_date", ""))[:10]
        actual, status, final = live_pitcher_prop(
            player,
            market,
            game_date,
            _int_or_none(row.get("game_pk")),
            _int_or_none(row.get("pitcher_id")),
        )
        grade = grade_bet(side, line, actual, final)
        stake = _num(row.get("stake"))
        odds = _num(row.get("american_odds"))
        profit = profit_for(stake, odds, grade)
        resolved_rows.append({
            "Pitcher": player,
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
        })

results = pd.DataFrame(resolved_rows)
wins = int((results["Result"] == "WIN").sum())
losses = int((results["Result"] == "LOSS").sum())
pushes = int((results["Result"] == "PUSH").sum())
pending = int((~results["Result"].isin(["WIN", "LOSS", "PUSH"])).sum())
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

st.subheader("Tracked bets")
view = results.copy()
view["Stake"] = view["Stake"].map(lambda x: "—" if pd.isna(x) else f"{x:.2f}")
view["Actual"] = view["Actual"].map(lambda x: "—" if pd.isna(x) else f"{x:g}")
view["Profit/Loss"] = view["Profit/Loss"].map(lambda x: "—" if pd.isna(x) else f"{x:+.2f}")
view["Projection"] = view["Projection"].map(lambda x: "—" if pd.isna(x) else f"{x:.2f}")
view["Model Probability"] = view["Model Probability"].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
view["Edge"] = view["Edge"].map(lambda x: "—" if pd.isna(x) else f"{x:+.1%}")
st.dataframe(view, hide_index=True, use_container_width=True)

st.download_button(
    "Download bet tracker CSV",
    results.to_csv(index=False),
    file_name="bet_tracker.csv",
    mime="text/csv",
)
st.caption("Sportsbook prices and stakes are tracking inputs only. They do not feed the pitcher projection models.")

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

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
        })

results = pd.DataFrame(resolved_rows)
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

st.subheader("Tracked bets")

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

view = results.drop(columns=["_BetKey"], errors="ignore").copy()
view["Stake"] = view["Stake"].map(lambda x: "—" if pd.isna(x) else f"{x:.2f}")
view["Actual"] = view["Actual"].map(lambda x: "—" if pd.isna(x) else (f"{x:g}" if isinstance(x, (int, float)) else str(x)))
view["Profit/Loss"] = view["Profit/Loss"].map(lambda x: "—" if pd.isna(x) else f"{x:+.2f}")
view["Projection"] = view["Projection"].map(lambda x: "—" if pd.isna(x) else f"{x:.2f}")
view["Model Probability"] = view["Model Probability"].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
view["Edge"] = view["Edge"].map(lambda x: "—" if pd.isna(x) else f"{x:+.1%}")
styled_view = view.style.map(result_cell_css, subset=["Result"])
st.dataframe(styled_view, hide_index=True, use_container_width=True)

st.download_button(
    "Download bet tracker CSV",
    results.drop(columns=["_BetKey"], errors="ignore").to_csv(index=False),
    file_name="bet_tracker.csv",
    mime="text/csv",
)
st.caption("Sportsbook prices and stakes are tracking inputs only. They do not feed the pitcher projection models.")

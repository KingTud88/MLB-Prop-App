from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

from automation.daily_projection_runner import LOG_PATH, game_log
from engine.calibration import calibrate_blend
from engine.hits_calibration import calibrate_hits_blend, hits_calibration_report
from engine.outs_calibration import calibrate_outs_blend, outs_calibration_report
from engine.bet_lean import projection_side
from engine.bet_tracker import (
    combined_parlay_odds,
    make_bet_record,
    make_parlay_record,
    projection_for_market,
)
from navigation import render_sidebar
from training.bet_storage import append_bet

st.set_page_config(page_title="Top Plays", page_icon="👑", layout="wide")
render_sidebar("top")
st.markdown("<style>.block-container{padding-top:3.25rem!important}</style>", unsafe_allow_html=True)
st.title("👑 Top Plays")
st.caption("Best current pitcher-prop legs across strikeouts, total outs, and hits allowed. Click any ranked row to see exactly why the model likes that projection. Sportsbook prices never feed the forecast itself.")

EASTERN = ZoneInfo("America/New_York")
ODDS_API = "https://api.the-odds-api.com/v4"
TEAM_NAMES = {
    "LAA":"Los Angeles Angels","ARI":"Arizona Diamondbacks","BAL":"Baltimore Orioles","BOS":"Boston Red Sox",
    "CHC":"Chicago Cubs","CIN":"Cincinnati Reds","CLE":"Cleveland Guardians","COL":"Colorado Rockies",
    "DET":"Detroit Tigers","HOU":"Houston Astros","KCR":"Kansas City Royals","LAD":"Los Angeles Dodgers",
    "WSH":"Washington Nationals","NYM":"New York Mets","ATH":"Athletics","PIT":"Pittsburgh Pirates",
    "SDP":"San Diego Padres","SEA":"Seattle Mariners","SFG":"San Francisco Giants","STL":"St. Louis Cardinals",
    "TBR":"Tampa Bay Rays","TEX":"Texas Rangers","TOR":"Toronto Blue Jays","MIN":"Minnesota Twins",
    "PHI":"Philadelphia Phillies","ATL":"Atlanta Braves","CHW":"Chicago White Sox","MIA":"Miami Marlins",
    "NYY":"New York Yankees","MIL":"Milwaukee Brewers",
}
MARKETS = "pitcher_strikeouts,pitcher_strikeouts_alternate,pitcher_outs,pitcher_outs_alternate,pitcher_hits_allowed,pitcher_hits_allowed_alternate"
ROOT = Path(__file__).resolve().parents[1]
BET_LOG = ROOT / "data" / "bet_log.csv"


def secret() -> str | None:
    for key in ("ODDS_API_KEY", "THE_ODDS_API_KEY", "odds_api_key"):
        try:
            if key in st.secrets:
                return str(st.secrets[key])
        except Exception:
            pass
    return os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY")


def implied(price: float) -> float:
    price = float(price)
    return 100.0 / (price + 100.0) if price > 0 else abs(price) / (abs(price) + 100.0)


def weighted(series: pd.Series, half: float, fallback: float) -> float:
    x = pd.to_numeric(series, errors="coerce").dropna().to_numpy(float)
    if not len(x):
        return fallback
    age = np.arange(len(x) - 1, -1, -1)
    w = 0.5 ** (age / half)
    return float(np.average(x, weights=w))


def numeric(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def normalize_team(value: str) -> str:
    text = "".join(ch for ch in str(value).lower() if ch.isalnum())
    for abbr, name in TEAM_NAMES.items():
        if text in {"".join(ch for ch in abbr.lower() if ch.isalnum()), "".join(ch for ch in name.lower() if ch.isalnum())}:
            return abbr
    return text.upper()


@st.cache_data(ttl=60, show_spinner=False)
def odds_events(api_key: str) -> list[dict]:
    r = requests.get(f"{ODDS_API}/sports/baseball_mlb/events", params={"apiKey": api_key}, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


@st.cache_data(ttl=60, show_spinner=False)
def event_props(api_key: str, event_id: str) -> dict:
    r = requests.get(
        f"{ODDS_API}/sports/baseball_mlb/events/{event_id}/odds",
        params={"apiKey": api_key, "regions": "us", "markets": MARKETS, "oddsFormat": "american"},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else {}


def match_event(events: list[dict], team: str, opponent: str) -> dict | None:
    wanted = {normalize_team(team), normalize_team(opponent)}
    for event in events:
        got = {normalize_team(event.get("home_team", "")), normalize_team(event.get("away_team", ""))}
        if got == wanted:
            return event
    return None


def strikeout_over_probability(row: pd.Series, line: float, history: pd.DataFrame) -> float | None:
    cutoff = int(math.floor(float(line)) + 1)
    if cutoff < 3 or cutoff > 10:
        return None
    sim = numeric(row.get(f"sim_{cutoff}p"))
    math_p = numeric(row.get(f"math_{cutoff}p"))
    if sim is None or math_p is None:
        return None
    cal = calibrate_blend(history, cutoff)
    return float(cal.weight_simulation * sim + cal.weight_math * math_p)


def hits_over_probability(row: pd.Series, line: float, history: pd.DataFrame) -> float | None:
    key = str(float(line)).replace(".", "_")
    sim = numeric(row.get(f"hits_sim_over_{key}"))
    math_p = numeric(row.get(f"hits_math_over_{key}"))
    if sim is None or math_p is None:
        return None
    cal = calibrate_hits_blend(history, float(line))
    return float(cal.weight_simulation * sim + cal.weight_math * math_p)


def outs_projection_details(row: pd.Series, line: float, history: pd.DataFrame) -> dict[str, float] | None:
    key = str(float(line)).replace(".", "_")
    sim = numeric(row.get(f"outs_sim_over_{key}"))
    math_p = numeric(row.get(f"outs_math_over_{key}"))
    if sim is None or math_p is None:
        return None
    cal = calibrate_outs_blend(history, float(line))
    return {
        "probability": float(cal.weight_simulation * sim + cal.weight_math * math_p),
        "sim": sim,
        "math": math_p,
        "sim_weight": cal.weight_simulation,
        "observations": float(cal.observations),
        "calibrated": float(cal.calibrated),
        "mean": numeric(row.get("outs_projection")) or 0.0,
        "sd": numeric(row.get("outs_sd")) or 0.0,
        "low": numeric(row.get("outs_range_low")) or 0.0,
        "high": numeric(row.get("outs_range_high")) or 0.0,
    }


def outs_over_probability(row: pd.Series, line: float, history: pd.DataFrame) -> float | None:
    details = outs_projection_details(row, line, history)
    return None if details is None else details["probability"]


def model_over_probability(row: pd.Series, market: str, line: float, history: pd.DataFrame) -> float | None:
    if market.startswith("pitcher_strikeouts"):
        return strikeout_over_probability(row, line, history)
    if market.startswith("pitcher_hits_allowed"):
        return hits_over_probability(row, line, history)
    if market.startswith("pitcher_outs"):
        return outs_over_probability(row, line, history)
    return None


def collect_legs(row: pd.Series, payload: dict, history: pd.DataFrame) -> list[dict]:
    player = " ".join(str(row.get("player", "")).lower().split())
    groups: dict[tuple, dict] = {}
    for book in payload.get("bookmakers", []):
        for market in book.get("markets", []):
            key = str(market.get("key", ""))
            if not key.startswith(("pitcher_strikeouts", "pitcher_outs", "pitcher_hits_allowed")):
                continue
            for outcome in market.get("outcomes", []):
                desc = " ".join(str(outcome.get("description", "")).lower().split())
                if desc != player or outcome.get("point") is None or outcome.get("price") is None:
                    continue
                try:
                    point = float(outcome["point"])
                    price = float(outcome["price"])
                except Exception:
                    continue
                g = groups.setdefault((book.get("title", book.get("key", "")), key, point), {})
                g[str(outcome.get("name", "")).lower()] = price

    legs = []
    quality = float(pd.to_numeric(pd.Series([row.get("data_quality")]), errors="coerce").fillna(0).iloc[0])
    for (book, market, point), prices in groups.items():
        if "over" not in prices or "under" not in prices:
            continue
        over_model = model_over_probability(row, market, point, history)
        if over_model is None:
            continue
        po = implied(prices["over"])
        pu = implied(prices["under"])
        total = po + pu
        if total <= 0:
            continue
        fair_over = po / total
        fair_under = pu / total
        if market.startswith("pitcher_strikeouts"):
            projection_mean = numeric(row.get("projection"))
        elif market.startswith("pitcher_hits_allowed"):
            projection_mean = numeric(row.get("hits_projection"))
        else:
            projection_mean = numeric(row.get("outs_projection"))
        if projection_mean is None:
            continue
        direction = projection_side(projection_mean, point)
        if direction == "OVER":
            candidates = [("OVER", over_model, fair_over, prices["over"])]
        elif direction == "UNDER":
            candidates = [("UNDER", 1.0 - over_model, fair_under, prices["under"])]
        else:
            continue
        for side, model_p, fair_p, price in candidates:
            edge = model_p - fair_p
            qualified = model_p >= 0.55 and edge >= 0.02 and quality >= 60
            reasons = []
            if model_p < 0.55:
                reasons.append("probability")
            if edge < 0.02:
                reasons.append("edge")
            if quality < 60:
                reasons.append("quality")
            status = "QUALIFIED" if qualified else "WATCH · " + "/".join(reasons)
            market_label = "Strikeouts" if "strikeouts" in market else "Total Outs" if "outs" in market else "Hits Allowed"
            score = model_p + 0.5 * edge + 0.001 * quality
            legs.append({
                "Pitcher": row.get("player"), "Market": market_label, "Side": side, "Line": point,
                "Model Probability": model_p, "No-Vig Implied": fair_p, "Edge": edge,
                "Book": book, "Odds": int(price), "Data Quality": int(round(quality)), "Score": score,
                "Qualified": qualified, "Status": status,
                "Game PK": row.get("game_pk"), "Pitcher ID": row.get("pitcher_id"), "Team": row.get("team"),
                "Opponent": row.get("opponent"), "Market Key": market,
            })
    return legs


def find_snapshot(history: pd.DataFrame, play: pd.Series) -> pd.Series | None:
    if history.empty:
        return None
    game_pk = numeric(play.get("Game PK"))
    pitcher_id = numeric(play.get("Pitcher ID"))
    if game_pk is None or pitcher_id is None:
        return None
    game_col = pd.to_numeric(history.get("game_pk"), errors="coerce")
    pitcher_col = pd.to_numeric(history.get("pitcher_id"), errors="coerce")
    matched = history.loc[game_col.eq(game_pk) & pitcher_col.eq(pitcher_id)]
    return None if matched.empty else matched.iloc[-1]


def render_projection_rationale(play: pd.Series, snapshot: pd.Series, history: pd.DataFrame) -> None:
    st.markdown("---")
    st.subheader(f"Why this projection? · {play['Pitcher']}")
    st.caption(f"{play.get('Team', '')} vs {play.get('Opponent', '')} · {play['Market']} · {play['Side']} {float(play['Line']):g} · {play['Book']} {int(play['Odds']):+d}")

    a, b, c, d = st.columns(4)
    a.metric("Model probability", f"{float(play['Model Probability']):.1%}")
    b.metric("No-vig market", f"{float(play['No-Vig Implied']):.1%}")
    c.metric("Model edge", f"{float(play['Edge']):+.1%}")
    d.metric("Data quality", f"{int(play['Data Quality'])}/100")

    market = str(play.get("Market", ""))
    line = float(play["Line"])
    side = str(play["Side"])
    cutoff = int(math.floor(line) + 1)

    if market == "Strikeouts":
        sim = numeric(snapshot.get(f"sim_{cutoff}p"))
        math_p = numeric(snapshot.get(f"math_{cutoff}p"))
        cal = calibrate_blend(history, cutoff)
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("SIM over", "—" if sim is None else f"{sim:.1%}")
        p2.metric("MATH over", "—" if math_p is None else f"{math_p:.1%}")
        p3.metric("SIM weight", f"{cal.weight_simulation:.0%}")
        p4.metric("Calibration sample", cal.observations)
        projected = numeric(snapshot.get("projection"))
        low = numeric(snapshot.get("k_range_low")); high = numeric(snapshot.get("k_range_high"))
        opp_k = numeric(snapshot.get("opponent_k_pct")); matchup_pa = numeric(snapshot.get("matchup_pa"))
        st.write(
            f"The frozen pregame strikeout forecast was **{projected:.2f} K**" if projected is not None else "Frozen strikeout mean unavailable.",
            f"The 80% range was **{int(low)}–{int(high)} K**." if low is not None and high is not None else "",
        )
        notes = []
        if opp_k is not None: notes.append(f"opponent matchup K rate {opp_k:.1f}%")
        if matchup_pa is not None: notes.append(f"matchup sample {int(matchup_pa)} PA")
        notes.append("two independent SIM/MATH paths")
        notes.append("learned calibration" if cal.calibrated else "protected 50/50 calibration baseline")
        st.info("Projection basis: " + " · ".join(notes))

    elif market == "Hits Allowed":
        key = str(float(line)).replace(".", "_")
        sim = numeric(snapshot.get(f"hits_sim_over_{key}"))
        math_p = numeric(snapshot.get(f"hits_math_over_{key}"))
        cal = calibrate_hits_blend(history, line)
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("SIM over", "—" if sim is None else f"{sim:.1%}")
        p2.metric("MATH over", "—" if math_p is None else f"{math_p:.1%}")
        p3.metric("SIM weight", f"{cal.weight_simulation:.0%}")
        p4.metric("Calibration sample", cal.observations)
        projected = numeric(snapshot.get("hits_projection"))
        low = numeric(snapshot.get("hits_range_low")); high = numeric(snapshot.get("hits_range_high"))
        if projected is not None:
            st.write(f"The frozen pregame hits-allowed forecast was **{projected:.2f} hits**, with an 80% simulation range of **{int(low)}–{int(high)}**." if low is not None and high is not None else f"The frozen pregame hits-allowed forecast was **{projected:.2f} hits**.")
        st.info("Projection basis: recent pitcher hits allowed per batter faced · workload uncertainty · independent simulation and Negative-Binomial math paths · " + ("learned calibration" if cal.calibrated else "protected 50/50 calibration baseline"))

    else:
        details = outs_projection_details(snapshot, line, history)
        if details is not None:
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("SIM over", f"{details['sim']:.1%}")
            p2.metric("MATH over", f"{details['math']:.1%}")
            p3.metric("SIM weight", f"{details['sim_weight']:.0%}")
            p4.metric("Calibration sample", int(details["observations"]))
            st.write(f"Frozen pregame outs forecast: **{details['mean']:.2f} outs**, 80% simulation range **{int(details['low'])}–{int(details['high'])}**.")
            st.info("Projection basis: recency-weighted empirical workload simulation · independent bounded Beta-Binomial mathematical path · " + ("learned calibration" if details["calibrated"] else "protected 50/50 calibration baseline"))

    confidence = str(snapshot.get("confidence", ""))
    captured = str(snapshot.get("captured_at_utc", ""))
    side_text = "over" if side == "OVER" else "under"
    st.caption(f"Why it ranked: the model gives this {side_text} a {float(play['Model Probability']):.1%} chance versus a {float(play['No-Vig Implied']):.1%} no-vig market probability, a {float(play['Edge']):+.1%} edge. Frozen snapshot confidence: {confidence or '—'}. Captured: {captured or '—'}.")


api_key = secret()
if not api_key:
    st.error("Odds API key not found in Streamlit secrets. Top Plays needs live sportsbook lines to rank actionable legs.")
    st.stop()

if not LOG_PATH.exists():
    st.info("No projection log exists yet. Run the Daily Projection page first.")
    st.stop()

history = pd.read_csv(LOG_PATH)
today = datetime.now(EASTERN).date().isoformat()
slate = history.loc[history.get("game_date", pd.Series(dtype=str)).astype(str).eq(today)].copy()
if slate.empty:
    st.info("No pregame projection snapshots are available for today's slate yet. Run Daily Projection Run first.")
    st.stop()

with st.expander("Hits Allowed calibration status", expanded=False):
    report = hits_calibration_report(history)
    st.dataframe(report, hide_index=True, use_container_width=True)
    ready = int((report["Status"] == "Calibrated").sum()) if not report.empty else 0
    st.caption(f"{ready}/{len(report)} tracked hit lines currently have learned SIM/MATH weights. Until a line reaches 30 resolved frozen observations, Top Plays uses the protected 50/50 baseline for that line.")

with st.expander("Total Outs calibration status", expanded=False):
    outs_report = outs_calibration_report(history)
    st.dataframe(outs_report, hide_index=True, use_container_width=True)
    outs_ready = int((outs_report["Status"] == "Calibrated").sum()) if not outs_report.empty else 0
    st.caption(f"{outs_ready}/{len(outs_report)} tracked outs lines currently have learned SIM/MATH weights. Until a line reaches 30 resolved frozen observations, Top Plays uses the protected 50/50 baseline.")

events = odds_events(api_key)
all_legs: list[dict] = []
progress = st.progress(0.0, text="Matching sportsbook markets to today's pitcher projections...")
for i, (_, row) in enumerate(slate.iterrows(), start=1):
    event = match_event(events, str(row.get("team", "")), str(row.get("opponent", "")))
    if event:
        try:
            all_legs.extend(collect_legs(row, event_props(api_key, str(event.get("id"))), history))
        except requests.RequestException:
            pass
    progress.progress(i / max(len(slate), 1), text=f"Scanned {i}/{len(slate)} pitchers")
progress.empty()

if not all_legs:
    st.info("Sportsbooks have not posted enough two-sided supported pitcher props yet to calculate a no-vig Top Plays board. The daily model projections are still available on Daily Projection Run and the main Projection page.")
    st.stop()

candidate_pool = pd.DataFrame(all_legs)
qualified_total = int(candidate_pool["Qualified"].fillna(False).sum())
plays = candidate_pool.sort_values(["Qualified", "Score", "Edge", "Model Probability"], ascending=False)
plays = plays.drop_duplicates(["Pitcher", "Market", "Side", "Line"], keep="first")
plays = plays.drop_duplicates(["Pitcher", "Market"], keep="first").head(5).copy().reset_index(drop=True)
plays.insert(0, "Rank", range(1, len(plays) + 1))

c1, c2, c3 = st.columns(3)
c1.metric("Qualified candidates", qualified_total)
c2.metric("Pitchers scanned", len(slate))
c3.metric("Top board edge", f"{plays['Edge'].max():.1%}")

view = plays[["Rank", "Status", "Pitcher", "Market", "Side", "Line", "Odds", "Model Probability", "No-Vig Implied", "Edge", "Book", "Data Quality"]].copy()
for col in ("Model Probability", "No-Vig Implied", "Edge"):
    view[col] = view[col].map(lambda x: f"{x:.1%}")
st.subheader("Today's five strongest available legs")
if qualified_total == 0:
    st.warning("No current leg clears all betting thresholds. These are the five closest available candidates, shown for review only — not official model bets.")
else:
    st.caption("QUALIFIED legs clear 55% model probability, +2% no-vig edge, and data quality 60+. WATCH legs are shown so the board never goes blank when the slate is thin.")
st.caption("Click a row or use View details to open its projection breakdown.")
event = st.dataframe(
    view,
    hide_index=True,
    use_container_width=True,
    key="top_plays_selectable",
    on_select="rerun",
    selection_mode="single-row",
)
st.caption("Ranking requires positive no-vig edge and minimum model/data-quality thresholds. One best leg per pitcher/market is kept so duplicate alternate lines do not crowd out the board.")

st.markdown("#### Top Play actions")
st.caption("Straight-bet stake is the amount recorded for one individual leg. It does not place a sportsbook wager and it does not affect the projection model.")
quick_stake = st.number_input("Straight-bet stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_quick_stake")
button_cols = st.columns(len(plays))
for button_idx, (_, play_row) in enumerate(plays.iterrows()):
    snapshot = find_snapshot(history, play_row)
    snapshot_dict = snapshot.to_dict() if snapshot is not None else None
    projection_value = projection_for_market(snapshot_dict, play_row.get("Market")) if snapshot_dict else None
    qualified = bool(play_row.get("Qualified", False))
    with button_cols[button_idx]:
        rank = int(play_row["Rank"])
        st.caption(f"#{rank} {play_row['Pitcher']} · {play_row['Side']} {float(play_row['Line']):g}")
        if st.button("🔎 View details", key=f"view_top_play_{rank}", use_container_width=True):
            st.session_state["top_play_detail_rank"] = rank
        if st.button("➕ Add as bet", key=f"add_top_play_{rank}", use_container_width=True, disabled=not qualified):
            try:
                game_pk = numeric(play_row.get("Game PK"))
                pitcher_id = numeric(play_row.get("Pitcher ID"))
                record = make_bet_record(
                    player=str(play_row["Pitcher"]),
                    market=play_row["Market"],
                    game_date=str(snapshot.get("game_date", today) if snapshot is not None else today),
                    line=float(play_row["Line"]),
                    side=str(play_row["Side"]),
                    american_odds=float(play_row["Odds"]),
                    stake=float(quick_stake),
                    book=str(play_row.get("Book", "")),
                    projection=projection_value,
                    model_probability=float(play_row["Model Probability"]),
                    implied_probability=float(play_row["No-Vig Implied"]),
                    edge=float(play_row["Edge"]),
                    confidence=(snapshot.get("confidence", "") if snapshot is not None else ""),
                    game_pk=None if game_pk is None else int(game_pk),
                    pitcher_id=None if pitcher_id is None else int(pitcher_id),
                )
                append_bet(BET_LOG, record, st.secrets)
                st.success("Added to Bet Tracker")
            except Exception as exc:
                st.error(f"Could not add bet: {exc}")
        if not qualified:
            st.caption("WATCH only")

st.markdown("---")
st.subheader("🎟️ Parlay Builder")
st.caption("A parlay uses one stake for the entire ticket. Legs must come from the same sportsbook. The estimated combined odds are only a starting point; enter the actual price quoted by your sportsbook before saving, especially for same-game or correlated props.")
qualified_pool = candidate_pool.loc[candidate_pool["Qualified"].fillna(False)].copy()
qualified_pool = qualified_pool.sort_values(["Score", "Edge", "Model Probability"], ascending=False)
qualified_pool = qualified_pool.drop_duplicates(["Book", "Pitcher", "Market"], keep="first")
book_counts = qualified_pool.groupby("Book").size() if not qualified_pool.empty else pd.Series(dtype=int)
parlay_books = [str(book) for book, count in book_counts.items() if int(count) >= 2]
if not parlay_books:
    st.info("No sportsbook currently has at least two qualified legs available for a model-backed parlay. WATCH candidates are intentionally excluded from the parlay builder.")
else:
    parlay_book = st.selectbox("Parlay sportsbook", parlay_books, key="top_plays_parlay_book")
    same_book = qualified_pool.loc[qualified_pool["Book"].astype(str).eq(parlay_book)].head(5).copy().reset_index(drop=True)
    option_map = {}
    for idx, leg in same_book.iterrows():
        label = f"{leg['Pitcher']} · {leg['Market']} · {leg['Side']} {float(leg['Line']):g} · {int(leg['Odds']):+d}"
        option_map[label] = idx
    selected_labels = st.multiselect("Parlay legs (2–5)", list(option_map), default=list(option_map), max_selections=5, key="top_plays_parlay_legs")
    selected = same_book.iloc[[option_map[label] for label in selected_labels]].copy() if selected_labels else same_book.iloc[0:0].copy()
    parlay_stake = st.number_input("Parlay stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_parlay_stake")
    if len(selected) >= 2:
        estimated_odds = combined_parlay_odds(selected["Odds"].astype(float).tolist())
        st.caption(f"Estimated standard combined price: {estimated_odds:+d}. Use the actual sportsbook quote if it differs.")
        quoted_odds = st.number_input("Sportsbook quoted parlay odds", min_value=-5000, max_value=100000, value=int(estimated_odds), step=5, key="top_plays_parlay_odds")
        save_parlay = st.button(f"🎟️ Add {len(selected)}-leg parlay to Bet Tracker", type="primary", use_container_width=True, key="save_top_plays_parlay")
        if save_parlay:
            legs = []
            for _, leg in selected.iterrows():
                game_pk = numeric(leg.get("Game PK")); pitcher_id = numeric(leg.get("Pitcher ID"))
                legs.append({
                    "player": str(leg["Pitcher"]), "market": str(leg["Market"]), "game_date": today,
                    "line": float(leg["Line"]), "side": str(leg["Side"]), "american_odds": float(leg["Odds"]),
                    "game_pk": None if game_pk is None else int(game_pk),
                    "pitcher_id": None if pitcher_id is None else int(pitcher_id),
                })
            try:
                record = make_parlay_record(legs=legs, stake=float(parlay_stake), book=parlay_book, american_odds=int(quoted_odds), game_date=today)
                append_bet(BET_LOG, record, st.secrets)
                st.success(f"Saved {len(legs)}-leg {parlay_book} parlay to Bet Tracker")
            except Exception as exc:
                st.error(f"Could not save parlay: {exc}")
    else:
        st.info("Select at least two qualified legs from the same sportsbook to build a parlay.")

selected_rank = st.session_state.get("top_play_detail_rank")
try:
    selected_rows = list(event.selection.rows)
except Exception:
    selected_rows = list((event.get("selection", {}) or {}).get("rows", [])) if isinstance(event, dict) else []
if selected_rows:
    idx = int(selected_rows[0])
    if 0 <= idx < len(plays):
        selected_rank = int(plays.iloc[idx]["Rank"])
        st.session_state["top_play_detail_rank"] = selected_rank

if selected_rank is not None:
    matched = plays.loc[pd.to_numeric(plays["Rank"], errors="coerce").eq(float(selected_rank))]
    if not matched.empty:
        play = matched.iloc[0]
        snapshot = find_snapshot(history, play)
        if snapshot is not None:
            render_projection_rationale(play, snapshot, history)
        else:
            st.warning("The frozen projection snapshot for this ranked leg could not be matched in the history log.")

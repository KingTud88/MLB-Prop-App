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

from engine.ui_theme import apply_page_theme

from automation.daily_projection_runner import LOG_PATH, game_log
from engine.calibration import calibrate_blend
from engine.hits_calibration import calibrate_hits_blend, hits_calibration_report
from engine.outs_calibration import calibrate_outs_blend, outs_calibration_report
from engine.bet_lean import projection_side
from engine.model_top_plays import build_model_board
from engine.model_health import health_from_walk_forward, market_health_map, walk_forward_top5
from engine.decision_learning import attach_decision_profiles, decision_tier_report
from engine.signal_validation import attach_signal_profiles, paired_signal_report
from engine.bet_tracker import (
    make_bet_record,
    make_parlay_record,
    projection_for_market,
)
from navigation import render_sidebar
from training.bet_storage import append_bet

st.set_page_config(page_title="Top Plays", page_icon="👑", layout="wide")
apply_page_theme()
render_sidebar("top")
st.markdown("<style>.block-container{padding-top:3.25rem!important}</style>", unsafe_allow_html=True)
st.title("👑 Top Plays")
st.caption("The five pitcher-prop legs our calibrated projections rate most likely to hit across strikeouts, total outs, and hits allowed. Sportsbook lines/odds are execution info only and never rank the board or feed the forecast.")

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
MAIN_MARKET_KEYS = {
    "Strikeouts": "pitcher_strikeouts",
    "Total Outs": "pitcher_outs",
    "Hits Allowed": "pitcher_hits_allowed",
}
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


@st.cache_data(ttl=900, show_spinner=False)
def odds_events(api_key: str) -> list[dict]:
    r = requests.get(f"{ODDS_API}/sports/baseball_mlb/events", params={"apiKey": api_key}, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


@st.cache_data(ttl=900, show_spinner=False)
def event_props(api_key: str, event_id: str, markets: tuple[str, ...]) -> tuple[dict, dict[str, int | None]]:
    market_csv = ",".join(sorted(set(str(m) for m in markets if str(m))))
    if not market_csv:
        return {}, {"remaining": None, "used": None, "last": 0}
    r = requests.get(
        f"{ODDS_API}/sports/baseball_mlb/events/{event_id}/odds",
        params={"apiKey": api_key, "regions": "us", "markets": market_csv, "oddsFormat": "american"},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    def _header_int(name: str) -> int | None:
        value = r.headers.get(name)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    quota = {
        "remaining": _header_int("x-requests-remaining"),
        "used": _header_int("x-requests-used"),
        "last": _header_int("x-requests-last"),
    }
    return (data if isinstance(data, dict) else {}), quota


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
    """Collect live offers for a pitcher without letting price determine the model ranking."""
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
        over_model = model_over_probability(row, market, point, history)
        if over_model is None:
            continue
        if market.startswith("pitcher_strikeouts"):
            projection_mean = numeric(row.get("projection"))
        elif market.startswith("pitcher_hits_allowed"):
            projection_mean = numeric(row.get("hits_projection"))
        else:
            projection_mean = numeric(row.get("outs_projection"))
        if projection_mean is None:
            continue
        direction = projection_side(projection_mean, point)
        if direction == "PASS":
            continue
        side_key = direction.lower()
        if side_key not in prices:
            continue
        model_p = over_model if direction == "OVER" else 1.0 - over_model
        fair_p = np.nan
        edge = np.nan
        if "over" in prices and "under" in prices:
            po = implied(prices["over"]); pu = implied(prices["under"]); total = po + pu
            if total > 0:
                fair_over = po / total
                fair_p = fair_over if direction == "OVER" else 1.0 - fair_over
                edge = model_p - fair_p
        qualified = model_p >= 0.55 and quality >= 60
        status = "MODEL PLAY" if qualified else "WATCH"
        market_label = "Strikeouts" if "strikeouts" in market else "Total Outs" if "outs" in market else "Hits Allowed"
        legs.append({
            "Pitcher": row.get("player"), "Market": market_label, "Side": direction, "Line": point,
            "Model Probability": model_p, "No-Vig Implied": fair_p, "Edge": edge,
            "Book": book, "Odds": int(prices[side_key]), "Data Quality": int(round(quality)), "Score": model_p,
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
    book = str(play.get("Book", "") or "").strip()
    odds = numeric(play.get("Odds"))
    live_text = f"{book} {int(odds):+d}" if book and odds is not None else "no exact live sportsbook price yet"
    st.caption(f"{play.get('Team', '')} vs {play.get('Opponent', '')} · {play['Market']} · {play['Side']} {float(play['Line']):g} · {live_text}")
    weather_level = str(play.get("Weather Risk", "") or "").upper()
    weather_summary = str(play.get("Weather Summary", "") or "").strip()
    if weather_level in {"HIGH", "ELEVATED"} and weather_summary:
        st.warning(f"{str(play.get('Weather Icon', '') or '🌩️')} {weather_summary}. Weather is informational and does not affect Top 5 ranking.")

    a, b, c, d = st.columns(4)
    a.metric("Model probability", f"{float(play['Model Probability']):.1%}")
    b.metric("Frozen projection", f"{float(play['Projection']):.2f}")
    c.metric("Live price", "—" if odds is None else f"{int(odds):+d}")
    d.metric("Data quality", f"{int(play['Data Quality'])}/100")
    live_edge = numeric(play.get("Edge"))
    live_implied = numeric(play.get("No-Vig Implied"))
    if live_edge is not None and live_implied is not None:
        st.caption(f"Market comparison only: no-vig implied {live_implied:.1%} · model edge {live_edge:+.1%}. These values do not affect Top 5 ranking.")

    decision_evidence = str(play.get("Decision Evidence", "LEARNING"))
    decision_sample = int(play.get("Decision Sample", 0) or 0)
    tier_hit = numeric(play.get("Tier Hit Rate"))
    decision_band = str(play.get("Decision Probability Band", ""))
    decision_quality = str(play.get("Decision Quality Band", ""))
    tier_text = "—" if tier_hit is None else f"{tier_hit:.1%}"
    st.caption(
        f"Decision evidence: {decision_evidence} · exact segment {decision_band} model probability / quality {decision_quality} · "
        f"{decision_sample} settled walk-forward legs · historical hit rate {tier_text}. This evidence does not change the projection itself."
    )
    st.caption(
        f"Signal evidence: {play.get('Signal Evidence', 'LEARNING')} · {play.get('Signal Detail', 'No mature paired signal evidence yet.')} "
        "Paired signal evidence is attached after ranking and does not change the baseball projection or Top 5 order."
    )

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
    st.caption(f"Why it ranked: the calibrated model gives this {side_text} a {float(play['Model Probability']):.1%} chance. Top 5 order is based on model hit probability first and data quality second; sportsbook price and edge never enter the ranking. Frozen snapshot confidence: {confidence or '—'}. Captured: {captured or '—'}.")


api_key = secret()

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

walk_forward = walk_forward_top5(history)
health_report = health_from_walk_forward(walk_forward)
health_map = market_health_map(health_report)
with st.expander("🚦 Walk-forward model health", expanded=False):
    health_view = health_report.loc[health_report["Market"].ne("ALL TOP 5")].copy()
    if health_view.empty:
        st.info("Model health is still waiting for starter-only walk-forward results.")
    else:
        for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Recent Hit Rate", "Recent Avg Probability", "Recent Calibration Gap"]:
            health_view[col] = health_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")
        health_view["Brier Score"] = health_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")
        st.dataframe(health_view, hide_index=True, width="stretch")
    st.caption("LEARNING and WATCH markets stay eligible. After 30 settled walk-forward Top 5 legs, a market that falls outside the safety guardrails becomes BLOCKED and is removed before today's Top 5 is ranked.")

decision_report = decision_tier_report(walk_forward)
with st.expander("🎯 Decision-learning evidence", expanded=False):
    st.caption(
        "Segment evidence is built only from settled leakage-safe Top 5 recommendations, grouped by market + probability band + data-quality band. "
        "Sportsbook prices and saved bets are excluded, and this layer does not reorder today's board."
    )
    if decision_report.empty:
        st.info("Decision evidence is still waiting for settled starter-only Top 5 legs.")
    else:
        decision_view = decision_report.copy()
        for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Wilson Lower 95%", "Lift vs Top 5"]:
            decision_view[col] = decision_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")
        decision_view["Brier Score"] = decision_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")
        st.dataframe(decision_view, hide_index=True, width="stretch")
    st.caption("Exact segments stay LEARNING below 20 settled legs. Strong or underperforming labels require at least 30 settled legs.")


signal_report = paired_signal_report(history)
with st.expander("🧪 Signal accountability", expanded=False):
    st.caption(
        "Paired pregame upgrade evidence measures whether workload-v1 and confirmed-lineup changes reduced same-game prediction error after the final result. "
        "This evidence is attached after ranking and cannot reorder or remove today's legs."
    )
    if signal_report.empty:
        st.info("Signal evidence is still waiting for resolved paired upgrades.")
    else:
        signal_view = signal_report.copy()
        for col in ["Relative MAE Improvement", "Improved Share"]:
            signal_view[col] = signal_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if col == "Relative MAE Improvement" else f"{float(x):.1%}")
        st.dataframe(signal_view[["Signal", "Market", "Resolved Pairs", "Pre MAE", "Post MAE", "Relative MAE Improvement", "Improved Share", "Status", "Reason"]], hide_index=True, width="stretch")
    st.caption("Signals remain LEARNING below 20 resolved pairs. HELPING/MIXED/HURTING are evidence labels only; sportsbook data is excluded.")

plays = build_model_board(slate, history, limit=5, market_health=health_map)
if plays.empty:
    st.warning("No current market passed the starter-history, probability-path, and model-health eligibility guards. The app will not manufacture a Top Play when the validated board is empty.")
    st.stop()
plays = attach_decision_profiles(plays, decision_report)
plays = attach_signal_profiles(plays, history, signal_report)

# The board exists before any paid sportsbook request. Credit Saver keeps paid
# odds OFF by default and only asks for main markets represented in the Top 5.
plays["Book"] = ""
plays["Odds"] = np.nan
plays["No-Vig Implied"] = np.nan
plays["Edge"] = np.nan
plays["Live Offer"] = False

live_state_key = f"top_plays_live_overlay:{today}"
quota_state_key = f"top_plays_live_quota:{today}"
candidate_pool = pd.DataFrame(st.session_state.get(live_state_key, []))
request_plan: dict[str, set[str]] = {}
event_snapshots: dict[str, dict[str, pd.Series]] = {}

if api_key:
    try:
        # /events is quota-free; it only maps MLB games to Odds API event ids.
        events = odds_events(api_key)
        for _, play in plays.iterrows():
            snapshot = find_snapshot(history, play)
            if snapshot is None:
                continue
            event_match = match_event(events, str(snapshot.get("team", "")), str(snapshot.get("opponent", "")))
            market_key = MAIN_MARKET_KEYS.get(str(play.get("Market", "")))
            if not event_match or not market_key:
                continue
            event_id = str(event_match.get("id", ""))
            if not event_id:
                continue
            request_plan.setdefault(event_id, set()).add(market_key)
            pitcher_key = str(play.get("Pitcher ID", play.get("Pitcher", "")))
            event_snapshots.setdefault(event_id, {})[pitcher_key] = snapshot
    except requests.RequestException as exc:
        st.caption(f"Quota-free event matching is unavailable right now ({type(exc).__name__}). The model Top 5 is unaffected.")

estimated_credits = sum(len(markets) for markets in request_plan.values())
if api_key and request_plan:
    st.caption(
        f"💳 Credit Saver: sportsbook odds are OFF until requested. Loading this Top 5 asks only for "
        f"{estimated_credits} main market/event combination(s) in the US region — at most {estimated_credits} credits if returned. "
        "Alternate markets are disabled by default."
    )
    if st.button(
        f"💳 Load / reuse live Top 5 prices · ≤{estimated_credits} credits",
        key="load_top_plays_live_prices",
        help="Paid Odds API call. Results are cached for 15 minutes; clicking again inside that window reuses the cache.",
    ):
        all_legs: list[dict] = []
        quota_rows: list[dict[str, int | None]] = []
        for event_id, market_keys in request_plan.items():
            try:
                payload, quota = event_props(api_key, event_id, tuple(sorted(market_keys)))
                quota_rows.append(quota)
            except requests.RequestException as exc:
                st.caption(f"Live price request failed for one event ({type(exc).__name__}).")
                continue
            for snapshot in event_snapshots.get(event_id, {}).values():
                all_legs.extend(collect_legs(snapshot, payload, history))
        st.session_state[live_state_key] = all_legs
        if quota_rows:
            actual_cost = sum(int(q.get("last") or 0) for q in quota_rows)
            final_quota = quota_rows[-1]
            st.session_state[quota_state_key] = {
                "last": actual_cost,
                "remaining": final_quota.get("remaining"),
                "used": final_quota.get("used"),
            }
        st.rerun()
else:
    if not api_key:
        st.caption("Odds API key is not available, so the model Top 5 is shown without live execution prices. Ranking is unaffected.")

quota_view = st.session_state.get(quota_state_key, {})
if quota_view:
    remaining = quota_view.get("remaining")
    used = quota_view.get("used")
    last = quota_view.get("last")
    st.caption(
        "Odds API usage from the last manual Top 5 load: "
        + f"{last if last is not None else '—'} credit(s) · "
        + f"{remaining if remaining is not None else '—'} remaining · "
        + f"{used if used is not None else '—'} used this quota period."
    )

if not candidate_pool.empty:
    for idx, play in plays.iterrows():
        matches = candidate_pool.loc[
            candidate_pool["Pitcher"].astype(str).eq(str(play["Pitcher"]))
            & candidate_pool["Market"].astype(str).eq(str(play["Market"]))
            & candidate_pool["Side"].astype(str).eq(str(play["Side"]))
            & pd.to_numeric(candidate_pool["Line"], errors="coerce").eq(float(play["Line"]))
        ]
        if matches.empty:
            continue
        best = matches.sort_values("Odds", ascending=False).iloc[0]
        plays.at[idx, "Book"] = best.get("Book", "")
        plays.at[idx, "Odds"] = best.get("Odds", np.nan)
        plays.at[idx, "No-Vig Implied"] = best.get("No-Vig Implied", np.nan)
        plays.at[idx, "Edge"] = best.get("Edge", np.nan)
        plays.at[idx, "Live Offer"] = True

model_plays = int(((plays["Model Probability"] >= 0.55) & (plays["Data Quality"] >= 60)).sum())
live_offers = int(plays["Live Offer"].fillna(False).sum())
decision_supported = int(plays["Decision Evidence"].isin(["SUPPORTED", "STRONG EVIDENCE"]).sum())
signal_supported = int(plays["Signal Evidence"].eq("SUPPORTED").sum())
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Highest model hit probability", f"{plays['Model Probability'].max():.1%}")
c2.metric("Model-qualified Top 5", model_plays)
c3.metric("Decision-supported legs", decision_supported)
c4.metric("Signal-supported legs", signal_supported)
c5.metric("Exact live prices found", f"{live_offers}/{len(plays)}")

view = plays[["Rank", "Status", "Model Health", "Decision Evidence", "Decision Sample", "Signal Evidence", "Signal Sample", "Tier Hit Rate", "Pitcher", "Weather Icon", "Weather Risk", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Starter History", "Book", "Odds"]].copy()
view["Pitcher"] = view.apply(lambda r: f"{r['Pitcher']} {str(r.get('Weather Icon', '') or '')}".strip(), axis=1)
view = view.drop(columns=["Weather Icon"])
view["Model Probability"] = view["Model Probability"].map(lambda x: f"{float(x):.1%}")
view["Tier Hit Rate"] = view["Tier Hit Rate"].map(lambda x: "—" if x is None or pd.isna(x) else f"{float(x):.1%}")
view["Projection"] = view["Projection"].map(lambda x: f"{float(x):.2f}")
view["Book"] = view["Book"].map(lambda x: x if str(x).strip() else "—")
view["Odds"] = view["Odds"].map(lambda x: "—" if pd.isna(x) else f"{int(float(x)):+d}")
st.subheader("Today's five highest-probability model legs")
st.caption("Eligible markets are ranked only by our calibrated hit probability, with data quality as the tie-breaker. Walk-forward model health can block a proven-unhealthy market; decision evidence is descriptive only; signal evidence is descriptive only; sportsbook odds and market edge never decide the Top 5.")
st.caption("Click a row or use View details to open its frozen projection breakdown.")
event = st.dataframe(
    view,
    hide_index=True,
    use_container_width=True,
    key="top_plays_selectable",
    on_select="rerun",
    selection_mode="single-row",
)

st.markdown("#### Top Play actions")
st.caption("Straight-bet stake is the amount recorded for one individual leg. It does not place a sportsbook wager and it does not affect the projection model.")
quick_stake = st.number_input("Straight-bet stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_quick_stake")
button_cols = st.columns(len(plays))
for button_idx, (_, play_row) in enumerate(plays.iterrows()):
    snapshot = find_snapshot(history, play_row)
    snapshot_dict = snapshot.to_dict() if snapshot is not None else None
    projection_value = projection_for_market(snapshot_dict, play_row.get("Market")) if snapshot_dict else numeric(play_row.get("Projection"))
    model_ok = float(play_row["Model Probability"]) >= 0.55 and int(play_row["Data Quality"]) >= 60
    live_offer = bool(play_row.get("Live Offer", False)) and numeric(play_row.get("Odds")) is not None
    with button_cols[button_idx]:
        rank = int(play_row["Rank"])
        weather_icon = str(play_row.get("Weather Icon", "") or "")
        st.caption(f"#{rank} {play_row['Pitcher']} {weather_icon} · {play_row['Side']} {float(play_row['Line']):g}".replace("  ·", " ·"))
        st.caption(f"Decision evidence: {play_row.get('Decision Evidence', 'LEARNING')} · n={int(play_row.get('Decision Sample', 0) or 0)}")
        st.caption(f"Signal evidence: {play_row.get('Signal Evidence', 'LEARNING')} · {play_row.get('Signal Detail', 'No mature paired signal evidence yet.')}")
        if st.button("🔎 View details", key=f"view_top_play_{rank}", use_container_width=True):
            st.session_state["top_play_detail_rank"] = rank
        if st.button("➕ Add as bet", key=f"add_top_play_{rank}", use_container_width=True, disabled=not (model_ok and live_offer)):
            try:
                game_pk = numeric(play_row.get("Game PK")); pitcher_id = numeric(play_row.get("Pitcher ID"))
                implied_p = numeric(play_row.get("No-Vig Implied")); live_edge = numeric(play_row.get("Edge"))
                record = make_bet_record(
                    player=str(play_row["Pitcher"]), market=play_row["Market"],
                    game_date=str(play_row.get("Game Date", today))[:10], line=float(play_row["Line"]),
                    side=str(play_row["Side"]), american_odds=float(play_row["Odds"]), stake=float(quick_stake),
                    book=str(play_row.get("Book", "")), projection=projection_value,
                    model_probability=float(play_row["Model Probability"]), implied_probability=implied_p, edge=live_edge,
                    confidence=(snapshot.get("confidence", "") if snapshot is not None else ""),
                    game_pk=None if game_pk is None else int(game_pk), pitcher_id=None if pitcher_id is None else int(pitcher_id),
                    source="Top Plays", data_quality=float(play_row["Data Quality"]),
                    app_version=str(play_row.get("App Version", "")), probability_semantics=str(play_row.get("Probability Semantics", "")),
                    snapshot_captured_at_utc=str(play_row.get("Captured At UTC", "")),
                )
                append_bet(BET_LOG, record, st.secrets)
                st.success("Added to Bet Tracker")
            except Exception as exc:
                st.error(f"Could not add bet: {exc}")
        if not model_ok:
            st.caption("WATCH · model/data quality below action threshold")
        elif not live_offer:
            st.caption("Model play · waiting for exact live line/price")

st.markdown("---")
st.subheader("🎟️ Parlay Builder")
st.caption(
    "Build a parlay directly from our model Top 5. Sportsbook data never filters, ranks, or selects the legs. "
    "Select any 2–5 model legs and choose one stake for the entire tracked model ticket; the sportsbook dropdown is recordkeeping only."
)

option_map = {}
for idx, leg in plays.iterrows():
    label = (
        f"#{int(leg['Rank'])} {leg['Pitcher']} {str(leg.get('Weather Icon', '') or '')} · {leg['Market']} · {leg['Side']} {float(leg['Line']):g} · "
        f"{float(leg['Model Probability']):.1%} · {leg['Status']}"
    )
    option_map[label] = idx

selected_labels = st.multiselect(
    "Parlay legs (2–5)",
    list(option_map),
    default=list(option_map),
    max_selections=5,
    key="top_plays_parlay_legs",
    help="These choices come only from our model Top 5. Sportsbook availability does not filter the list.",
)
selected = plays.iloc[[option_map[label] for label in selected_labels]].copy() if selected_labels else plays.iloc[0:0].copy()
parlay_stake = st.number_input("Parlay stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_parlay_stake")
parlay_book = st.selectbox(
    "Sportsbook (recordkeeping only)",
    [
        "Not tracked",
        "FanDuel",
        "DraftKings",
        "BetMGM",
        "Caesars Sportsbook",
        "Fanatics Sportsbook",
        "bet365",
        "ESPN BET",
        "Hard Rock Bet",
        "BetRivers",
        "Other / Not listed",
    ],
    key="top_plays_parlay_book",
    help="This only labels the saved Bet Tracker ticket. It never changes the Top 5, available legs, model probability, or parlay selection.",
)
parlay_book_value = "" if parlay_book == "Not tracked" else parlay_book

if len(selected) >= 2:
    watch_count = int((selected["Status"].astype(str) == "WATCH").sum())
    duplicate_pitchers = selected["Pitcher"].astype(str).value_counts()
    correlated = duplicate_pitchers[duplicate_pitchers > 1]
    if not correlated.empty:
        st.warning("This parlay contains multiple props for the same pitcher (" + ", ".join(correlated.index.tolist()) + "). Those legs can be correlated; the app does not treat the parlay probability as independent.")
    if watch_count:
        st.warning(f"This parlay includes {watch_count} WATCH leg(s). They are still in our Top 5, but they fall below the straight-bet model/data-quality action threshold.")
    if st.button(f"🎟️ Add {len(selected)}-leg model parlay to Bet Tracker", type="primary", use_container_width=True, key="save_top_plays_parlay"):
        legs = []
        for _, leg in selected.iterrows():
            game_pk = numeric(leg.get("Game PK")); pitcher_id = numeric(leg.get("Pitcher ID"))
            legs.append({
                "player": str(leg["Pitcher"]), "market": str(leg["Market"]),
                "game_date": str(leg.get("Game Date", today))[:10],
                "line": float(leg["Line"]), "side": str(leg["Side"]), "american_odds": None,
                "game_pk": None if game_pk is None else int(game_pk),
                "pitcher_id": None if pitcher_id is None else int(pitcher_id),
                "projection": numeric(leg.get("Projection")),
                "model_probability": float(leg.get("Model Probability")),
                "data_quality": int(leg.get("Data Quality", 0)),
                "app_version": str(leg.get("App Version", "")),
                "probability_semantics": str(leg.get("Probability Semantics", "")),
                "snapshot_captured_at_utc": str(leg.get("Captured At UTC", "")),
                "status": str(leg.get("Status", "")),
            })
        try:
            record = make_parlay_record(
                legs=legs,
                stake=float(parlay_stake),
                game_date=today,
                book=parlay_book_value,
                source="Top Plays Model Parlay",
            )
            append_bet(BET_LOG, record, st.secrets)
            st.success(f"Saved {len(legs)}-leg model parlay to Bet Tracker. This tracks hit/loss results only; no sportsbook price was assumed.")
        except Exception as exc:
            st.error(f"Could not save parlay: {exc}")
else:
    st.info("Select at least two of our Top 5 model legs to build a parlay.")

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

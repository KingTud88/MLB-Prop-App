from __future__ import annotations

import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

from automation.daily_projection_runner import LOG_PATH, game_log
from engine.calibration import calibrate_blend
from engine.hits_calibration import calibrate_hits_blend, hits_calibration_report
from navigation import render_sidebar

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


def outs_projection_details(row: pd.Series, line: float) -> dict[str, float] | None:
    try:
        log = game_log(int(row["pitcher_id"]), int(str(row["game_date"])[:4]))
        if log.empty:
            return None
        starts = log.tail(35)
        mean = weighted(starts["outs"], 5.0, 16.0)
        sd = float(np.clip(starts["outs"].std(ddof=1) if len(starts) > 2 else 4.0, 2.5, 6.5))
        seed = (int(row["game_pk"]) * 1000003 + int(row["pitcher_id"])) & 0xFFFFFFFF
        rng = np.random.default_rng(seed)
        samples = np.clip(np.rint(rng.normal(mean, sd, 25000)), 0, 27).astype(int)
        cutoff = int(math.floor(float(line)) + 1)
        last5 = pd.to_numeric(starts.tail(5)["outs"], errors="coerce").dropna()
        return {
            "probability": float(np.mean(samples >= cutoff)),
            "mean": mean,
            "sd": sd,
            "last5": float(last5.mean()) if len(last5) else mean,
            "starts": float(len(starts)),
        }
    except Exception:
        return None


def outs_over_probability(row: pd.Series, line: float) -> float | None:
    details = outs_projection_details(row, line)
    return None if details is None else details["probability"]


def model_over_probability(row: pd.Series, market: str, line: float, history: pd.DataFrame) -> float | None:
    if market.startswith("pitcher_strikeouts"):
        return strikeout_over_probability(row, line, history)
    if market.startswith("pitcher_hits_allowed"):
        return hits_over_probability(row, line, history)
    if market.startswith("pitcher_outs"):
        return outs_over_probability(row, line)
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
        candidates = [
            ("OVER", over_model, fair_over, prices["over"]),
            ("UNDER", 1.0 - over_model, fair_under, prices["under"]),
        ]
        for side, model_p, fair_p, price in candidates:
            edge = model_p - fair_p
            if model_p < 0.55 or edge < 0.02 or quality < 60:
                continue
            market_label = "Strikeouts" if "strikeouts" in market else "Total Outs" if "outs" in market else "Hits Allowed"
            score = model_p + 0.5 * edge + 0.001 * quality
            legs.append({
                "Pitcher": row.get("player"), "Market": market_label, "Side": side, "Line": point,
                "Model Probability": model_p, "No-Vig Implied": fair_p, "Edge": edge,
                "Book": book, "Odds": int(price), "Data Quality": int(round(quality)), "Score": score,
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
        details = outs_projection_details(snapshot, line)
        if details is not None:
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Projected outs", f"{details['mean']:.2f}")
            p2.metric("Workload SD", f"{details['sd']:.2f}")
            p3.metric("Last 5 avg outs", f"{details['last5']:.2f}")
            p4.metric("Starts used", int(details["starts"]))
        st.info("Projection basis: recency-weighted pitcher workload and recent outs distribution. Total Outs does **not** yet have the same independent SIM/MATH calibration layer as Strikeouts and Hits Allowed, so the app labels it separately instead of overstating model depth.")

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
    st.info("No legs currently clear the minimum filters (55% model probability, +2% no-vig edge, data quality 60+), or the sportsbooks have not posted supported pitcher props yet.")
    st.stop()

plays = pd.DataFrame(all_legs)
plays = plays.sort_values(["Score", "Edge", "Model Probability"], ascending=False)
plays = plays.drop_duplicates(["Pitcher", "Market", "Side", "Line"], keep="first")
plays = plays.drop_duplicates(["Pitcher", "Market"], keep="first").head(5).copy().reset_index(drop=True)
plays.insert(0, "Rank", range(1, len(plays) + 1))

c1, c2, c3 = st.columns(3)
c1.metric("Qualified legs", len(all_legs))
c2.metric("Pitchers scanned", len(slate))
c3.metric("Top board edge", f"{plays['Edge'].max():.1%}")

view = plays[["Rank", "Pitcher", "Market", "Side", "Line", "Odds", "Model Probability", "No-Vig Implied", "Edge", "Book", "Data Quality"]].copy()
for col in ("Model Probability", "No-Vig Implied", "Edge"):
    view[col] = view[col].map(lambda x: f"{x:.1%}")
st.subheader("Today's five strongest qualified legs")
st.caption("Click a row to open its projection breakdown.")
event = st.dataframe(
    view,
    hide_index=True,
    use_container_width=True,
    key="top_plays_selectable",
    on_select="rerun",
    selection_mode="single-row",
)
st.caption("Ranking requires positive no-vig edge and minimum model/data-quality thresholds. One best leg per pitcher/market is kept so duplicate alternate lines do not crowd out the board.")

try:
    selected_rows = list(event.selection.rows)
except Exception:
    selected_rows = list((event.get("selection", {}) or {}).get("rows", [])) if isinstance(event, dict) else []

if selected_rows:
    idx = int(selected_rows[0])
    if 0 <= idx < len(plays):
        play = plays.iloc[idx]
        snapshot = find_snapshot(history, play)
        if snapshot is not None:
            render_projection_rationale(play, snapshot, history)
        else:
            st.warning("The frozen projection snapshot for this ranked leg could not be matched in the history log.")

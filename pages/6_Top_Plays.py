from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from engine.ui_theme import apply_page_theme
from engine.explainability_ui import (
    Explanation, apply_explainability_theme, explain_popover, leg_explanation,
    metric_help, projection_metric_explanation, recommendation_explanation, static_explanation,
    ticket_explanation, top_play_explanation, weather_explanation,
)
from engine.command_center_consistency import apply_command_center_consistency

from automation.daily_projection_runner import LOG_PATH
from engine.calibration import calibrate_blend
from engine.hits_calibration import calibrate_hits_blend, hits_calibration_report
from engine.outs_calibration import calibrate_outs_blend, outs_calibration_report
from engine.model_top_plays import build_model_board
from engine.sportsgameodds import load_pitcher_market_odds
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
from training.projection_storage import load_projection_archive, overlay_manual_market_lines

st.set_page_config(page_title="Top Plays", page_icon="👑", layout="wide")
apply_page_theme()
render_sidebar("top")
apply_command_center_consistency("top_plays")
apply_explainability_theme()
st.markdown(
    """
    <style>
    .block-container{padding-top:1.7rem!important;padding-bottom:3.25rem!important}

    .tp-page-hero{
        position:relative;overflow:hidden;margin:.1rem 0 .62rem;padding:.9rem 1.15rem .95rem;border:1px solid rgba(80,108,136,.76);border-radius:18px;
        background:linear-gradient(110deg,rgba(8,28,50,.98),rgba(5,20,37,.98));box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 18px 42px rgba(0,0,0,.3)
    }
    .tp-page-hero::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(#ff3655,#a60c29)}
    .tp-page-kicker{font:900 .7rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.12em;color:#ff6a7d;text-transform:uppercase}
    .tp-page-title{margin:.22rem 0 .26rem;font-family:Impact,"Arial Black","Arial Narrow",sans-serif;font-size:clamp(2.7rem,5vw,4.8rem);line-height:.86;letter-spacing:.012em;color:#f5f1e9;text-transform:uppercase;text-shadow:3px 4px 0 #07182b}
    .tp-page-title span{color:#ec1638;-webkit-text-stroke:1px #f1eee7;paint-order:stroke fill}
    .tp-page-sub{max-width:1120px;color:#b6c6d5;font:650 .87rem/1.45 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .tp-page-rule{margin-top:.52rem;width:max-content;max-width:100%;padding:.25rem .58rem;border-top:1px solid rgba(236,22,56,.65);border-bottom:1px solid rgba(236,22,56,.65);color:#e6edf3;font:900 .67rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.09em;text-transform:uppercase}

    .tp-section-ribbon{width:max-content;min-width:245px;max-width:92%;margin:.92rem auto .48rem;padding:.42rem 1.7rem;border:1px solid #ff3151;border-bottom-color:#790b1d;border-radius:8px;background:linear-gradient(180deg,#f21b3d,#b70d29);box-shadow:0 7px 16px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.22);color:#fff;font:900 .9rem/1.15 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.035em;text-align:center;text-transform:uppercase}

    /* Explicit card containers: no DOM-key guessing required for their contents. */
    [class*="st-key-top_play_card_"]{
        position:relative;padding:.8rem!important;border:1px solid rgba(82,112,141,.78)!important;border-radius:16px!important;
        background:linear-gradient(150deg,rgba(10,34,59,.99),rgba(4,18,33,.99))!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.045),0 13px 30px rgba(0,0,0,.27)!important;overflow:hidden
    }
    [class*="st-key-top_play_card_"]::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:linear-gradient(90deg,transparent,#ec1638 18%,#ec1638 82%,transparent);box-shadow:0 0 14px rgba(236,22,56,.32)}
    [class*="st-key-top_play_card_"]:has(.tp-status.watch){opacity:.82;border-color:rgba(68,94,119,.62)!important;background:linear-gradient(150deg,rgba(8,28,49,.96),rgba(4,17,31,.98))!important}
    [class*="st-key-top_play_card_"]:has(.tp-status.model){border-color:rgba(50,229,141,.5)!important}
    .st-key-top_play_card_1{box-shadow:inset 0 1px 0 rgba(255,255,255,.055),0 0 0 1px rgba(236,22,56,.12),0 18px 38px rgba(0,0,0,.32)!important}

    .tp-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:.65rem;margin-bottom:.52rem}
    .tp-rank-wrap{display:flex;align-items:center;gap:.58rem;min-width:0}
    .tp-rank{display:flex;align-items:center;justify-content:center;width:40px;height:40px;flex:0 0 40px;border-radius:50%;border:2px solid rgba(236,22,56,.78);background:radial-gradient(circle at 35% 30%,#173e69,#07182b 66%);color:#fff;font:900 .96rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;box-shadow:0 8px 18px rgba(0,0,0,.26)}
    .st-key-top_play_card_1 .tp-rank{width:46px;height:46px;flex-basis:46px;font-size:1.08rem;background:radial-gradient(circle at 35% 30%,#7d1730,#250815 70%)}
    .tp-pitcher{color:#f7f3ec;font:900 1.14rem/1.1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.002em;overflow-wrap:anywhere}
    .st-key-top_play_card_1 .tp-pitcher{font-size:1.35rem}
    .tp-matchup{margin-top:.12rem;color:#93a9bc;font:750 .73rem/1.25 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;text-transform:uppercase;letter-spacing:.025em}
    .tp-multi-market{display:inline-flex;margin-top:.26rem;padding:.16rem .4rem;border:1px solid rgba(126,162,194,.45);border-radius:999px;background:rgba(17,47,76,.6);color:#bdd0df;font:850 .61rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.04em;text-transform:uppercase}
    .tp-status-stack{display:flex;flex-direction:column;align-items:flex-end;gap:.28rem}
    .tp-status{display:inline-flex;align-items:center;justify-content:center;white-space:nowrap;border-radius:999px;padding:.23rem .52rem;font:900 .64rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.05em;text-transform:uppercase}
    .tp-status.model{border:1px solid rgba(50,229,141,.55);background:rgba(8,79,52,.38);color:#5cf0ae}
    .tp-status.watch{border:1px solid rgba(255,209,102,.5);background:rgba(98,71,8,.28);color:#ffe08a}
    .tp-evidence{display:inline-flex;white-space:nowrap;border-radius:999px;padding:.18rem .42rem;border:1px solid rgba(101,145,183,.45);background:rgba(14,42,69,.58);color:#a9c5dc;font:850 .57rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.045em;text-transform:uppercase}
    .tp-evidence.strong{border-color:rgba(74,191,230,.5);color:#8eddf4;background:rgba(10,65,83,.38)}

    .tp-market-row{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin:.15rem 0 .58rem;padding:.46rem .54rem;border:1px solid rgba(66,99,130,.68);border-radius:11px;background:rgba(5,23,42,.72)}
    .tp-market{color:#dce6ee;font:850 .78rem/1.22 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;text-transform:uppercase;letter-spacing:.025em}
    .tp-side{display:inline-flex;align-items:center;border-radius:8px;padding:.24rem .46rem;font:950 .76rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.035em;white-space:nowrap}
    .tp-side.over{color:#50f2aa;border:1px solid rgba(50,229,141,.55);background:rgba(12,91,61,.34)}
    .tp-side.under{color:#ff6379;border:1px solid rgba(255,71,98,.58);background:rgba(125,13,36,.36)}
    .tp-side.pass{color:#ffe08a;border:1px solid rgba(255,209,102,.55);background:rgba(111,82,15,.3)}

    .tp-stat-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.4rem;margin-bottom:.5rem}
    .tp-stat{min-height:62px;padding:.46rem .5rem;border:1px solid rgba(66,100,133,.68);border-radius:10px;background:linear-gradient(145deg,rgba(12,39,67,.94),rgba(6,23,41,.96));text-align:center}
    .tp-stat-label{color:#91a8bb;font:850 .6rem/1.1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.055em;text-transform:uppercase}
    .tp-stat-value{margin-top:.24rem;color:#f7f3ec;font:950 1.32rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .tp-stat-value.prob{color:#50f2aa}.tp-stat-value.quality{font-size:1.12rem}.tp-stat-value.tier{font-size:1.1rem}
    .st-key-top_play_card_1 .tp-stat-value{font-size:1.5rem}
    .tp-card-note{margin:.1rem 0 .48rem;color:#9fb3c6;font:650 .71rem/1.32 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .tp-card-note strong{color:#dfe8ef}

    [class*="st-key-top_play_card_"] div[data-testid="stButton"] button{min-height:2.35rem!important;border-radius:9px!important;font-weight:900!important}
    [class*="st-key-top_play_card_"] [data-testid="stCaptionContainer"]{font-size:.73rem!important;line-height:1.3!important}
    [data-testid="stNumberInput"]{margin-bottom:.2rem!important}

    /* Remove the old purple visual language everywhere on Top Plays. */
    div[style*="#8b4fc7"],div[style*="93,48,128"],div[style*="139,79,199"]{border-color:rgba(70,105,139,.86)!important;background:linear-gradient(145deg,rgba(12,39,67,.98),rgba(6,23,41,.98))!important}
    div[style*="#8b4fc7"] span,div[style*="139,79,199"] span{border-color:rgba(77,108,137,.72)!important}

    @media (max-width:1050px){.tp-page-title{font-size:3.25rem}.tp-pitcher{font-size:1.04rem}.st-key-top_play_card_1 .tp-pitcher{font-size:1.26rem}}
    @media (max-width:760px){.block-container{padding-top:1rem!important}.tp-page-hero{padding:.8rem}.tp-page-title{font-size:2.7rem}.tp-page-rule{font-size:.62rem;letter-spacing:.06em}.tp-section-ribbon{min-width:180px;padding:.4rem 1rem;font-size:.82rem}.tp-market-row{align-items:flex-start;flex-direction:column}.tp-stat{min-height:60px}.tp-status-stack{align-items:flex-start}}
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="tp-page-hero">
      <div class="tp-page-kicker">StrikeOut King 9000 · Daily Command Board</div>
      <div class="tp-page-title">TOP <span>PLAYS</span></div>
      <div class="tp-page-sub">The five pitcher-prop legs our calibrated projections rate most likely to hit across strikeouts, total outs, and hits allowed. Sportsbook lines and odds are execution information only and never rank the board or feed the forecast.</div>
      <div class="tp-page-rule">Model first · market second · frozen pregame evidence</div>
    </div>
    """,
    unsafe_allow_html=True,
)

EASTERN = ZoneInfo("America/New_York")
MAIN_MARKET_KEYS = {
    "Strikeouts": "pitcher_strikeouts",
    "Total Outs": "pitcher_outs",
    "Hits Allowed": "pitcher_hits_allowed",
}
ROOT = Path(__file__).resolve().parents[1]
BET_LOG = ROOT / "data" / "bet_log.csv"
ARCHIVE_PATH = ROOT / "data" / "projection_archive.csv"




def implied(price: float) -> float:
    price = float(price)
    return 100.0 / (price + 100.0) if price > 0 else abs(price) / (abs(price) + 100.0)




def numeric(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)














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









def attach_sportsgameodds_prices(plays: pd.DataFrame, slate_date: str) -> pd.DataFrame:
    """Attach exact saved SportsGameOdds prices without making an API call or changing rank."""
    enriched = plays.copy()
    for col, default in (
        ("Book", ""),
        ("Odds", np.nan),
        ("No-Vig Implied", np.nan),
        ("Edge", np.nan),
        ("Live Offer", False),
    ):
        enriched[col] = default

    cache: dict[str, list[dict[str, object]]] = {}
    for idx, play in enriched.iterrows():
        pitcher = str(play.get("Pitcher", "") or "").strip()
        market_key = MAIN_MARKET_KEYS.get(str(play.get("Market", "") or ""))
        line = numeric(play.get("Line"))
        side = str(play.get("Side", "") or "").strip().lower()
        if not pitcher or not market_key or line is None or side not in {"over", "under"}:
            continue

        if pitcher not in cache:
            cache[pitcher] = load_pitcher_market_odds(pitcher, slate_date)
        offers = [
            row for row in cache[pitcher]
            if str(row.get("market", "")) == market_key
            and numeric(row.get("point")) is not None
            and abs(float(row.get("point")) - line) <= 1e-9
        ]
        if not offers:
            continue

        target = next((row for row in offers if str(row.get("name", "")).lower() == side), None)
        if target is None:
            continue
        book = str(target.get("book", "") or "").strip()
        same_book = [row for row in offers if str(row.get("book", "") or "").strip() == book]
        over = next((row for row in same_book if str(row.get("name", "")).lower() == "over"), None)
        under = next((row for row in same_book if str(row.get("name", "")).lower() == "under"), None)
        price = numeric(target.get("price"))
        if price is None:
            continue

        enriched.at[idx, "Book"] = book
        enriched.at[idx, "Odds"] = price
        enriched.at[idx, "Live Offer"] = True
        over_price = numeric(over.get("price")) if over else None
        under_price = numeric(under.get("price")) if under else None
        if over_price is not None and under_price is not None:
            po = implied(over_price)
            pu = implied(under_price)
            total = po + pu
            if total > 0:
                fair_over = po / total
                fair_side = fair_over if side == "over" else 1.0 - fair_over
                enriched.at[idx, "No-Vig Implied"] = fair_side
                model_p = numeric(play.get("Model Probability"))
                if model_p is not None:
                    enriched.at[idx, "Edge"] = model_p - fair_side
    return enriched

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



if not LOG_PATH.exists():
    st.info("No projection log exists yet. Run the Daily Projection page first.")
    st.stop()

history = pd.read_csv(LOG_PATH)
today = datetime.now(EASTERN).date().isoformat()
slate = history.loc[history.get("game_date", pd.Series(dtype=str)).astype(str).eq(today)].copy()
# TOP_PLAYS_DURABLE_MANUAL_LINES_V1
durable_archive = load_projection_archive(ARCHIVE_PATH, st.secrets)
slate = overlay_manual_market_lines(slate, durable_archive)
if slate.empty:
    st.info("No pregame projection snapshots are available for today's slate yet. Run Daily Projection Run first.")
    st.stop()

# TOP_PLAYS_SIMPLIFIED_LAYOUT_V1
# Evidence is still computed before ranking; only its presentation moved below the plays.
report = hits_calibration_report(history)
outs_report = outs_calibration_report(history)
walk_forward = walk_forward_top5(history)
health_report = health_from_walk_forward(walk_forward)
health_map = market_health_map(health_report)
decision_report = decision_tier_report(walk_forward)
signal_report = paired_signal_report(history)

plays = build_model_board(slate, history, limit=5, market_health=health_map, require_market_lines=True)
if plays.empty:
    st.warning("No current market has both a valid model path and an authentic active sportsbook line yet. SportsGameOdds capture must supply a real pregame line before Top Plays can rank a bet.")
    st.stop()
plays = attach_decision_profiles(plays, decision_report)
plays = attach_signal_profiles(plays, history, signal_report)

# TOP_PLAYS_REAL_LINE_GUARD_V1
st.caption("Line integrity: every ranked leg below uses an authentic active sportsbook line. SportsGameOdds is primary; legacy MANUAL or backup rows keep their explicit source labels. Markets with no real line are excluded, and model-grid/default lines can never become Top Plays.")

# Exact SportsGameOdds prices are read from the saved disk snapshot only.
# This overlay cannot change the model-first Top 5 order.
plays = attach_sportsgameodds_prices(plays, today)

model_plays = int(((plays["Model Probability"] >= 0.55) & (plays["Data Quality"] >= 60)).sum())
live_offers = int(plays["Live Offer"].fillna(False).sum())
decision_supported = int(plays["Decision Evidence"].isin(["SUPPORTED", "STRONG EVIDENCE"]).sum())
signal_supported = int(plays["Signal Evidence"].eq("SUPPORTED").sum())
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Highest model hit probability", f"{plays['Model Probability'].max():.1%}", help=metric_help("top_highest_probability"))
c2.metric("Actionable model plays", model_plays, help=metric_help("top_actionable"))
c3.metric("Decision-supported legs", decision_supported, help=metric_help("top_decision_supported"))
c4.metric("Signal-supported legs", signal_supported, help=metric_help("top_signal_supported"))
c5.metric("Exact live prices found", f"{live_offers}/{len(plays)}", help=metric_help("top_live_prices"))
explain_popover(static_explanation("top_summary"),label="ⓘ EXPLAIN TOP 5 SUMMARY")

st.markdown('<div class="tp-section-ribbon">Top Play Actions</div>', unsafe_allow_html=True)
st.caption("Straight-bet stake is the amount recorded for one individual leg. It does not place a sportsbook wager and it does not affect the projection model.")
quick_stake = st.number_input("Straight-bet stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_quick_stake")

# Presentation-only layout: the plays dataframe and rank order are unchanged.
play_records = list(plays.iterrows())
pitcher_market_counts = plays["Pitcher"].astype(str).value_counts().to_dict()
layout_slots: list[tuple[object, tuple[object, pd.Series]]] = []
if len(play_records) <= 3:
    cols = st.columns(len(play_records))
    layout_slots.extend(zip(cols, play_records))
else:
    top_count = min(3, len(play_records))
    top_cols = st.columns([1.35, 1, 1][:top_count])
    layout_slots.extend(zip(top_cols, play_records[:top_count]))
    remaining = play_records[top_count:]
    if remaining:
        bottom_cols = st.columns(len(remaining))
        layout_slots.extend(zip(bottom_cols, remaining))

for target_col, (_, play_row) in layout_slots:
    snapshot = find_snapshot(history, play_row)
    snapshot_dict = snapshot.to_dict() if snapshot is not None else None
    projection_value = projection_for_market(snapshot_dict, play_row.get("Market")) if snapshot_dict else numeric(play_row.get("Projection"))
    model_ok = float(play_row["Model Probability"]) >= 0.55 and int(play_row["Data Quality"]) >= 60
    live_offer = bool(play_row.get("Live Offer", False)) and numeric(play_row.get("Odds")) is not None
    rank = int(play_row["Rank"])
    weather_raw = play_row.get("Weather Icon", "")
    weather_icon = "" if pd.isna(weather_raw) else str(weather_raw or "")
    team_raw = play_row.get("Team", "")
    team = "" if pd.isna(team_raw) else str(team_raw or "")
    opponent_raw = play_row.get("Opponent", "")
    opponent = "" if pd.isna(opponent_raw) else str(opponent_raw or "")
    side = str(play_row.get("Side", "PASS") or "PASS").upper()
    side_class = "over" if side == "OVER" else "under" if side == "UNDER" else "pass"
    action_status = "MODEL PLAY" if model_ok else "WATCH"
    status_class = "model" if model_ok else "watch"
    decision_evidence = str(play_row.get("Decision Evidence", "LEARNING") or "LEARNING").upper()
    evidence_class = "strong" if "STRONG" in decision_evidence else ""
    evidence_label = f"Evidence · {decision_evidence}"
    tier_hit = numeric(play_row.get("Tier Hit Rate"))
    tier_text = "—" if tier_hit is None else f"{tier_hit:.1%}"
    quality = int(play_row.get("Data Quality", 0))
    pitcher_name = str(play_row["Pitcher"])
    multi_market_count = int(pitcher_market_counts.get(pitcher_name, 1))
    multi_market_html = f'<div class="tp-multi-market">{multi_market_count} markets ranked</div>' if multi_market_count > 1 else ""
    matchup_text = " · ".join(v for v in [team, f"vs {opponent}" if opponent else "", weather_icon] if v)
    line_source = str(play_row.get("Line Source", "ACTIVE MARKET LINE") or "ACTIVE MARKET LINE")

    with target_col:
        with st.container(border=False, key=f"top_play_card_{rank}"):
            st.markdown(
                f"""
                <div class="tp-card-head">
                  <div class="tp-rank-wrap">
                    <div class="tp-rank">#{rank}</div>
                    <div><div class="tp-pitcher">{pitcher_name}</div><div class="tp-matchup">{matchup_text or 'Pregame snapshot'}</div>{multi_market_html}</div>
                  </div>
                  <div class="tp-status-stack"><div class="tp-status {status_class}">{action_status}</div><div class="tp-evidence {evidence_class}">{evidence_label}</div></div>
                </div>
                <div class="tp-market-row">
                  <div class="tp-market">{play_row['Market']}</div>
                  <div class="tp-side {side_class}">{side} {float(play_row['Line']):g}</div>
                </div>
                <div class="tp-card-note"><strong>Line source:</strong> {line_source}</div>
                <div class="tp-stat-grid">
                  <div class="tp-stat"><div class="tp-stat-label">Projection</div><div class="tp-stat-value">{float(play_row['Projection']):.2f}</div></div>
                  <div class="tp-stat"><div class="tp-stat-label">Model Hit %</div><div class="tp-stat-value prob">{float(play_row['Model Probability']):.1%}</div></div>
                  <div class="tp-stat"><div class="tp-stat-label">Data Quality</div><div class="tp-stat-value quality">{quality}/100</div></div>
                  <div class="tp-stat"><div class="tp-stat-label">Tier Hit Rate</div><div class="tp-stat-value tier">{tier_text}</div></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            explain_popover(top_play_explanation(play_row),label=f"ⓘ WHY IS THIS #{rank}?")
            if live_offer:
                odds_value = int(float(play_row["Odds"]))
                book_value = str(play_row.get("Book", "") or "Live book")
                st.markdown(f'<div class="tp-card-note"><strong>Execution:</strong> {book_value} · {odds_value:+d}</div>', unsafe_allow_html=True)
            elif model_ok:
                st.markdown('<div class="tp-card-note"><strong>Execution:</strong> Model play · active real line captured · current price unavailable</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="tp-card-note"><strong>Action:</strong> WATCH · model/data quality below straight-bet threshold</div>', unsafe_allow_html=True)

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

st.caption("ⓘ Projections are model estimates at the listed line. They are not guaranteed outcomes.")

st.markdown("---")
st.subheader("🎟️ Parlay Builder")
explain_popover(static_explanation("top_parlay"),label="ⓘ EXPLAIN PARLAY BUILDER")
st.caption(
    "Build a parlay directly from our model Top 5. Sportsbook data never filters, ranks, or selects the legs. "
    "Select any 2–5 model legs and choose one stake for the entire tracked model ticket; the sportsbook dropdown is recordkeeping only."
)

option_map = {}
for idx, leg in plays.iterrows():
    label = (
        f"#{int(leg['Rank'])} {leg['Pitcher']} {'' if pd.isna(leg.get('Weather Icon')) else str(leg.get('Weather Icon') or '')} · {leg['Market']} · {leg['Side']} {float(leg['Line']):g} · "
        f"{float(leg['Model Probability']):.1%} · {'MODEL PLAY' if float(leg['Model Probability']) >= 0.55 and int(leg['Data Quality']) >= 60 else 'WATCH'}"
    )
    option_map[label] = idx

selected_labels = st.multiselect(
    "Parlay legs (2–5)",
    list(option_map),
    default=[],
    max_selections=5,
    key="top_plays_parlay_legs_v2",
    help="Start empty and intentionally choose 2–5 model legs. Sportsbook availability never filters this list.",
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
    selected_model_ok = (selected["Model Probability"].astype(float) >= 0.55) & (selected["Data Quality"].astype(int) >= 60)
    watch_count = int((~selected_model_ok).sum())
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
                "line_source": str(leg.get("Line Source", "")),
                "game_pk": None if game_pk is None else int(game_pk),
                "pitcher_id": None if pitcher_id is None else int(pitcher_id),
                "projection": numeric(leg.get("Projection")),
                "model_probability": float(leg.get("Model Probability")),
                "data_quality": int(leg.get("Data Quality", 0)),
                "app_version": str(leg.get("App Version", "")),
                "probability_semantics": str(leg.get("Probability Semantics", "")),
                "snapshot_captured_at_utc": str(leg.get("Captured At UTC", "")),
                "status": "MODEL PLAY" if float(leg.get("Model Probability", 0)) >= 0.55 and int(leg.get("Data Quality", 0)) >= 60 else "WATCH",
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
    st.info("Choose at least two Top 5 legs to build a parlay. Nothing is preselected for you.")

selected_rank = st.session_state.get("top_play_detail_rank")

if selected_rank is not None:
    matched = plays.loc[pd.to_numeric(plays["Rank"], errors="coerce").eq(float(selected_rank))]
    if not matched.empty:
        play = matched.iloc[0]
        snapshot = find_snapshot(history, play)
        if snapshot is not None:
            render_projection_rationale(play, snapshot, history)
        else:
            st.warning("The frozen projection snapshot for this ranked leg could not be matched in the history log.")

st.markdown("---")
st.subheader("🧪 Model diagnostics")
explain_popover(static_explanation("top_diagnostics"),label="ⓘ EXPLAIN DIAGNOSTICS")
st.caption("Calibration, Model Health, decision-learning evidence, and signal accountability live here so the plays stay first-scan readable. These diagnostics retain their original ranking and safety roles.")

with st.expander("Hits Allowed calibration status", expanded=False):
    st.dataframe(report, hide_index=True, use_container_width=True)
    ready = int((report["Status"] == "Calibrated").sum()) if not report.empty else 0
    st.caption(f"{ready}/{len(report)} tracked hit lines currently have learned SIM/MATH weights. Until a line reaches 30 resolved frozen observations, Top Plays uses the protected 50/50 baseline for that line.")

with st.expander("Total Outs calibration status", expanded=False):
    st.dataframe(outs_report, hide_index=True, use_container_width=True)
    outs_ready = int((outs_report["Status"] == "Calibrated").sum()) if not outs_report.empty else 0
    st.caption(f"{outs_ready}/{len(outs_report)} tracked outs lines currently have learned SIM/MATH weights. Until a line reaches 30 resolved frozen observations, Top Plays uses the protected 50/50 baseline.")

with st.expander("🚦 Walk-forward Model Health", expanded=False):
    health_view = health_report.loc[health_report["Market"].ne("ALL TOP 5")].copy()
    if health_view.empty:
        st.info("Model health is still waiting for starter-only walk-forward results.")
    else:
        for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Recent Hit Rate", "Recent Avg Probability", "Recent Calibration Gap"]:
            health_view[col] = health_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")
        health_view["Brier Score"] = health_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")
        st.dataframe(health_view, hide_index=True, width="stretch")
    st.caption("LEARNING and WATCH markets stay eligible. After 30 settled walk-forward Top 5 legs, a market that falls outside the safety guardrails becomes BLOCKED and is removed before today's Top 5 is ranked.")

with st.expander("🎯 Decision-learning evidence", expanded=False):
    st.caption("Segment evidence uses settled leakage-safe Top 5 recommendations only. Sportsbook prices and saved bets are excluded, and this layer does not reorder today's board.")
    if decision_report.empty:
        st.info("Decision evidence is still waiting for settled starter-only Top 5 legs.")
    else:
        decision_view = decision_report.copy()
        for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Wilson Lower 95%", "Lift vs Top 5"]:
            decision_view[col] = decision_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")
        decision_view["Brier Score"] = decision_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")
        st.dataframe(decision_view, hide_index=True, width="stretch")
    st.caption("Exact segments stay LEARNING below 20 settled legs. Strong or underperforming labels require at least 30 settled legs.")

with st.expander("🧪 Signal accountability", expanded=False):
    st.caption("Paired pregame upgrade evidence measures whether workload-v1 and confirmed-lineup changes reduced same-game prediction error after the final result. This evidence is attached after ranking and cannot reorder or remove today's legs.")
    if signal_report.empty:
        st.info("Signal evidence is still waiting for resolved paired upgrades.")
    else:
        signal_view = signal_report.copy()
        for col in ["Relative MAE Improvement", "Improved Share"]:
            signal_view[col] = signal_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if col == "Relative MAE Improvement" else f"{float(x):.1%}")
        st.dataframe(signal_view[["Signal", "Market", "Resolved Pairs", "Pre MAE", "Post MAE", "Relative MAE Improvement", "Improved Share", "Status", "Reason"]], hide_index=True, width="stretch")
    st.caption("Signals remain LEARNING below 20 resolved pairs. HELPING/MIXED/HURTING are evidence labels only; sportsbook data is excluded.")
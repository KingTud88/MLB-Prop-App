from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from training.daily_projection_runner import run_daily_projections
from training.daily_odds import enrich_daily_records
from training.github_projection_store import load_projections, resolve_completed_projections, save_projections
from training.odds_api import get_api_key, usage_summary

st.set_page_config(page_title="Daily Projection Run", page_icon="📊", layout="wide")
st.title("📊 Daily Projection Run")
st.caption("Run StrikeOut King 9000 across the announced MLB starter slate. Live sportsbook enrichment is optional and separate from the projection model.")

EASTERN = ZoneInfo("America/New_York")
today = datetime.now(EASTERN).date()

with st.sidebar:
    st.markdown("## Daily runner")
    slate_date = st.date_input("Slate date", value=today)
    simulations = st.select_slider("Simulation draws", [1000, 2500, 5000, 10000], value=5000)
    opponent_k_pct = st.slider("Projected lineup K%", 15.0, 32.0, 22.4, 0.1)
    pitch_limit = st.slider("Expected pitch limit", 60, 115, 92)
    umpire_k_factor = st.slider("Umpire K factor", 0.94, 1.06, 1.00, 0.01)
    weather_factor = st.slider("Weather K factor", 0.96, 1.04, 1.00, 0.01)
    rest_days = st.slider("Days rest", 3, 10, 5)
    rest_factor = 0.96 if rest_days <= 3 else 1.0 if rest_days <= 6 else 1.01
    odds_key = get_api_key(st.secrets)
    enrich_odds = st.checkbox(
        "Enrich with live Odds API",
        value=False,
        disabled=not bool(odds_key),
        help="Optional. Fetches the current pitcher strikeout market for each announced starter and uses Odds API allowance.",
    )

if enrich_odds:
    st.warning("Odds enrichment is ON. The MLB projection still comes from the model; sportsbook odds are an additional live-data column. Each game's pitcher-prop request consumes Odds API allowance.")
else:
    st.info("The Daily Projection Run works without Odds API. Turn on live Odds API enrichment when you want sportsbook strikeout lines alongside the model results.")

if st.button("▶ Run full MLB starter slate", type="primary", use_container_width=True):
    with st.spinner("Running every announced starter and building the daily archive..."):
        records, errors, skipped = run_daily_projections(
            slate_date.isoformat(),
            opponent_k_pct=opponent_k_pct,
            pitch_limit=float(pitch_limit),
            umpire_k_factor=umpire_k_factor,
            weather_factor=weather_factor,
            rest_factor=rest_factor,
            simulations=simulations,
        )
        odds_errors = []
        odds_usage = {}
        if enrich_odds and odds_key:
            records, odds_errors, odds_headers = enrich_daily_records(records, odds_key, slate_date)
            odds_usage = usage_summary(odds_headers)
            errors.extend(odds_errors)
        try:
            added = save_projections(records)
        except Exception as exc:
            added = 0
            errors.append(f"Archive write failed: {exc}")
    st.session_state["daily_run_records"] = records
    st.session_state["daily_run_errors"] = errors
    st.session_state["daily_run_skipped"] = skipped
    st.session_state["daily_run_added"] = added
    st.session_state["daily_run_odds_usage"] = odds_usage

if "daily_run_added" in st.session_state:
    added = st.session_state["daily_run_added"]
    records = st.session_state.get("daily_run_records", [])
    errors = st.session_state.get("daily_run_errors", [])
    skipped = st.session_state.get("daily_run_skipped", 0)
    odds_usage = st.session_state.get("daily_run_odds_usage", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Projected", len(records))
    c2.metric("Newly archived", added)
    c3.metric("Skipped", skipped)
    c4.metric("Errors", len(errors))
    if odds_usage:
        st.caption(f"Odds API usage · remaining {odds_usage['remaining']} · used {odds_usage['used']} · last request {odds_usage['last_cost']}")
    if records:
        display_cols = ["player","team","opponent","projection","k_range_low","k_range_high","confidence","data_quality","status"]
        if any("odds_market" in record for record in records):
            display_cols += ["odds_market","odds_bookmaker"]
        display = pd.DataFrame(records)[display_cols].copy()
        display = display.rename(columns={"player":"Pitcher","team":"Team","opponent":"Opp","projection":"Projection K","k_range_low":"80% Low","k_range_high":"80% High","confidence":"Confidence","data_quality":"Data Quality","status":"Game Status","odds_market":"Live Odds","odds_bookmaker":"Book"})
        st.subheader(f"{slate_date:%B %-d, %Y} projection slate")
        st.dataframe(display, hide_index=True, width="stretch", column_config={"Projection K":st.column_config.NumberColumn(format="%.2f K"),"80% Low":st.column_config.NumberColumn(format="%.0f"),"80% High":st.column_config.NumberColumn(format="%.0f")})
    if errors:
        st.warning("Some pitchers or odds events could not be processed:")
        for error in errors:
            st.write(f"- {error}")

st.divider()
st.subheader("Resolve completed games")
if st.button("Resolve completed projection outcomes"):
    with st.spinner("Checking MLB box scores and attaching actual strikeouts..."):
        updated = resolve_completed_projections()
    if updated:
        st.success(f"Updated {updated} completed projection(s).")
    else:
        st.info("No new completed outcomes were available.")

rows = load_projections()
if rows:
    df = pd.DataFrame(rows)
    df["projection"] = pd.to_numeric(df["projection"], errors="coerce")
    df["actual_strikeouts"] = pd.to_numeric(df["actual_strikeouts"], errors="coerce")
    df = df[df["game_date"] == slate_date.isoformat()].copy()
    if not df.empty:
        resolved = df["actual_strikeouts"].notna()
        st.caption(f"Archive contains {len(df)} projection(s) for this slate; {int(resolved.sum())} already have actual Ks.")

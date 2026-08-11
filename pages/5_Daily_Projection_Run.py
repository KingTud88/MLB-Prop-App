from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from automation.daily_projection_runner import (
    LOG_PATH,
    PROBABILITY_SEMANTICS,
    fill_missing_pregame_paths,
    project,
    resolve_row,
    schedule,
)
from navigation import render_sidebar

st.set_page_config(page_title="Daily Projection Run", page_icon="📊", layout="wide")
render_sidebar("daily")
st.title("📊 Daily Projection Run")
st.caption(
    "Run StrikeOut King 9000 across every announced MLB starter on the selected slate. "
    "Each pitcher is captured as an immutable pregame SIM + MATH + ensemble snapshot for calibration."
)

EASTERN = ZoneInfo("America/New_York")
today = datetime.now(EASTERN).date()
slate_date = st.date_input("Slate date", value=today)


def load_log() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(LOG_PATH)
    except Exception:
        return pd.DataFrame()


def save_log(frame: pd.DataFrame) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    for line in range(3, 11):
        for prefix in ("sim", "math"):
            col = f"{prefix}_{line}p"
            if col not in frame.columns:
                frame[col] = np.nan
    if "probability_semantics" not in frame.columns:
        frame["probability_semantics"] = ""
    if "actual_strikeouts" not in frame.columns:
        frame["actual_strikeouts"] = np.nan
    if "resolved_at_utc" not in frame.columns:
        frame["resolved_at_utc"] = ""
    frame.to_csv(LOG_PATH, index=False)


def run_full_slate(day: str) -> tuple[pd.DataFrame, int, int, list[str]]:
    frame = load_log()
    announced = schedule(day)
    existing = set()
    if not frame.empty and {"game_pk", "pitcher_id"}.issubset(frame.columns):
        existing = set(
            zip(
                pd.to_numeric(frame["game_pk"], errors="coerce"),
                pd.to_numeric(frame["pitcher_id"], errors="coerce"),
            )
        )

    new_rows: list[dict] = []
    skipped = 0
    errors: list[str] = []
    for row in announced:
        key = (row["game_pk"], row["pitcher_id"])
        if key in existing:
            skipped += 1
            continue
        try:
            result = project(row)
        except Exception as exc:
            errors.append(f"{row.get('player', 'Unknown')}: {type(exc).__name__}: {exc}")
            continue
        if result is None:
            errors.append(f"{row.get('player', 'Unknown')}: no usable pitcher history")
            continue
        new_rows.append(result)

    if new_rows:
        frame = pd.concat([frame, pd.DataFrame(new_rows)], ignore_index=True)

    refreshed = fill_missing_pregame_paths(frame)
    save_log(frame)

    slate = frame.loc[frame.get("game_date", pd.Series(dtype=str)).astype(str).eq(day)].copy() if not frame.empty else pd.DataFrame()
    return slate, len(new_rows), skipped + refreshed, errors


st.info(
    "This page is for batch data capture. The normal Projection page remains the single-pitcher deep-dive workflow. "
    "Existing game/pitcher snapshots are not overwritten after capture."
)

if st.button("⚾ RUN ALL TODAY'S PITCHERS", type="primary", use_container_width=True):
    with st.spinner("Simulating every announced starter and writing pregame snapshots..."):
        try:
            slate, added, skipped, errors = run_full_slate(slate_date.isoformat())
        except Exception as exc:
            slate = pd.DataFrame()
            added = skipped = 0
            errors = [f"Slate run failed: {type(exc).__name__}: {exc}"]
    st.session_state["daily_slate"] = slate
    st.session_state["daily_added"] = added
    st.session_state["daily_skipped"] = skipped
    st.session_state["daily_errors"] = errors

slate = st.session_state.get("daily_slate")
if isinstance(slate, pd.DataFrame):
    added = int(st.session_state.get("daily_added", 0))
    skipped = int(st.session_state.get("daily_skipped", 0))
    errors = list(st.session_state.get("daily_errors", []))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate pitchers", len(slate))
    c2.metric("New snapshots", added)
    c3.metric("Already captured/refreshed", skipped)
    c4.metric("Errors", len(errors))

    if not slate.empty:
        display_cols = [
            "player", "team", "opponent", "projection", "k_range_low", "k_range_high",
            "confidence", "data_quality", "opponent_k_pct", "sim_5p", "math_5p",
            "probability_semantics", "actual_strikeouts",
        ]
        display_cols = [c for c in display_cols if c in slate.columns]
        display = slate[display_cols].copy().rename(
            columns={
                "player": "Pitcher",
                "team": "Team",
                "opponent": "Opp",
                "projection": "Projection K",
                "k_range_low": "80% Low",
                "k_range_high": "80% High",
                "confidence": "Confidence",
                "data_quality": "Data Quality",
                "opponent_k_pct": "Opp K%",
                "sim_5p": "SIM 5+",
                "math_5p": "MATH 5+",
                "probability_semantics": "Semantics",
                "actual_strikeouts": "Actual K",
            }
        )
        st.subheader(f"{slate_date:%B %d, %Y} starter slate")
        st.dataframe(display, hide_index=True, use_container_width=True)
        compatible = int(slate.get("probability_semantics", pd.Series(dtype=str)).astype(str).eq(PROBABILITY_SEMANTICS).sum())
        st.caption(f"{compatible}/{len(slate)} rows use the current calibration probability semantics: {PROBABILITY_SEMANTICS}.")

    if errors:
        st.warning("Some announced starters could not be captured:")
        for error in errors:
            st.write(f"- {error}")

st.divider()
st.subheader("Resolve completed games")
if st.button("Resolve completed projection outcomes"):
    frame = load_log()
    updated = 0
    if not frame.empty:
        with st.spinner("Checking MLB results and attaching actual strikeouts..."):
            for idx in frame.index:
                actual, resolved = resolve_row(frame.loc[idx])
                if pd.notna(actual) and pd.isna(frame.loc[idx].get("actual_strikeouts")):
                    frame.at[idx, "actual_strikeouts"] = actual
                    frame.at[idx, "resolved_at_utc"] = resolved
                    updated += 1
            save_log(frame)
    if updated:
        st.success(f"Resolved {updated} new projection outcome(s).")
    else:
        st.info("No new completed outcomes were available.")

archive = load_log()
if not archive.empty and "game_date" in archive.columns:
    day_rows = archive.loc[archive["game_date"].astype(str).eq(slate_date.isoformat())].copy()
    if not day_rows.empty:
        actual = pd.to_numeric(day_rows.get("actual_strikeouts"), errors="coerce")
        st.caption(
            f"Projection log currently contains {len(day_rows)} snapshot(s) for this slate; "
            f"{int(actual.notna().sum())} have resolved actual strikeouts."
        )

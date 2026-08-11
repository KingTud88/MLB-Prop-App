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
from engine.calibration import calibrate_blend
from engine.hits_calibration import calibrate_hits_blend
from engine.outs_calibration import calibrate_outs_blend
from navigation import render_sidebar

st.set_page_config(page_title="Daily Projection Run", page_icon="📊", layout="wide")
render_sidebar("daily")
st.markdown(
    """
    <style>
    .block-container { padding-top: 3.25rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("📊 Daily Projection Run")
st.caption(
    "Run StrikeOut King 9000 across every announced MLB starter on the selected slate. "
    "Each pitcher is captured as an immutable pregame strikeout + total-outs + hits-allowed snapshot for calibration."
)

EASTERN = ZoneInfo("America/New_York")
today = datetime.now(EASTERN).date()
slate_date = st.date_input("Slate date", value=today)


def load_log() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(LOG_PATH)
    except Exception:
        return pd.DataFrame()
    # Legacy projection logs may predate hits/outs resolution columns. Always
    # materialize them as Series so summary counts never call .notna() on a scalar.
    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs"):
        if col not in frame.columns:
            frame[col] = np.nan
    if "resolved_at_utc" not in frame.columns:
        frame["resolved_at_utc"] = ""
    return frame


def save_log(frame: pd.DataFrame) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    for line in range(3, 11):
        for prefix in ("sim", "math"):
            col = f"{prefix}_{line}p"
            if col not in frame.columns:
                frame[col] = np.nan
    if "probability_semantics" not in frame.columns:
        frame["probability_semantics"] = ""
    if "history_semantics" not in frame.columns:
        frame["history_semantics"] = ""
    if "starter_history_games" not in frame.columns:
        frame["starter_history_games"] = np.nan
    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs"):
        if col not in frame.columns:
            frame[col] = np.nan
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


def _num(row: pd.Series, key: str) -> float | None:
    value = pd.to_numeric(pd.Series([row.get(key)]), errors="coerce").iloc[0]
    return None if pd.isna(value) else float(value)


def render_projection_rationale(row: pd.Series, history: pd.DataFrame) -> None:
    pitcher = str(row.get("player", "Unknown"))
    st.markdown(f"### 🔎 Why we projected {pitcher} this way")
    st.caption(
        "This explanation uses the frozen pregame snapshot. Later game results do not change the inputs or probabilities shown here."
    )

    k_mean = _num(row, "projection")
    hits_mean = _num(row, "hits_projection")
    quality = _num(row, "data_quality")
    opp_k = _num(row, "opponent_k_pct")
    outs_mean = _num(row, "outs_projection")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Projected Ks", "—" if k_mean is None else f"{k_mean:.2f}")
    c2.metric("Projected outs", "—" if outs_mean is None else f"{outs_mean:.2f}")
    c3.metric("Projected hits allowed", "—" if hits_mean is None else f"{hits_mean:.2f}")
    c4.metric("Data quality", "—" if quality is None else f"{quality:.0f}/100")
    c5.metric("Opponent K%", "—" if opp_k is None else f"{opp_k:.1f}%")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Strikeout path · 5+")
        sim = _num(row, "sim_5p")
        math_p = _num(row, "math_5p")
        cal = calibrate_blend(history, 5)
        blended = None if sim is None or math_p is None else cal.weight_simulation * sim + cal.weight_math * math_p
        detail = pd.DataFrame([
            {"Component": "Simulation", "Probability": sim, "Weight": cal.weight_simulation},
            {"Component": "Mathematical", "Probability": math_p, "Weight": cal.weight_math},
        ])
        for col in ("Probability", "Weight"):
            detail[col] = detail[col].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
        st.dataframe(detail, hide_index=True, use_container_width=True)
        st.write("**Blended 5+ probability:**", "—" if blended is None else f"{blended:.1%}")
        st.caption(
            f"Calibration: {'learned' if cal.calibrated else '50/50 baseline'} · {cal.observations} compatible resolved observations."
        )

    with right:
        st.markdown("#### Hits allowed path · Over 5.5")
        hit_sim = _num(row, "hits_sim_over_5_5")
        hit_math = _num(row, "hits_math_over_5_5")
        hit_cal = calibrate_hits_blend(history, 5.5)
        hit_blended = None if hit_sim is None or hit_math is None else hit_cal.weight_simulation * hit_sim + hit_cal.weight_math * hit_math
        detail = pd.DataFrame([
            {"Component": "Simulation", "Probability": hit_sim, "Weight": hit_cal.weight_simulation},
            {"Component": "Mathematical", "Probability": hit_math, "Weight": hit_cal.weight_math},
        ])
        for col in ("Probability", "Weight"):
            detail[col] = detail[col].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
        st.dataframe(detail, hide_index=True, use_container_width=True)
        st.write("**Blended O5.5 probability:**", "—" if hit_blended is None else f"{hit_blended:.1%}")
        st.caption(
            f"Calibration: {'learned' if hit_cal.calibrated else '50/50 baseline'} · {hit_cal.observations} resolved hit observations."
        )

    st.markdown("#### Total outs path · Over 15.5")
    outs_sim = _num(row, "outs_sim_over_15_5")
    outs_math = _num(row, "outs_math_over_15_5")
    outs_cal = calibrate_outs_blend(history, 15.5)
    outs_blended = None if outs_sim is None or outs_math is None else outs_cal.weight_simulation * outs_sim + outs_cal.weight_math * outs_math
    detail = pd.DataFrame([
        {"Component": "Simulation", "Probability": outs_sim, "Weight": outs_cal.weight_simulation},
        {"Component": "Mathematical", "Probability": outs_math, "Weight": outs_cal.weight_math},
    ])
    for col in ("Probability", "Weight"):
        detail[col] = detail[col].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
    st.dataframe(detail, hide_index=True, use_container_width=True)
    st.write("**Blended O15.5 probability:**", "—" if outs_blended is None else f"{outs_blended:.1%}")
    st.caption(f"Calibration: {'learned' if outs_cal.calibrated else '50/50 baseline'} · {outs_cal.observations} resolved outs observations.")

    facts = {
        "Matchup": f"{row.get('team', '—')} vs {row.get('opponent', '—')}",
        "Confidence": row.get("confidence", "—"),
        "Matchup PA sample": int(_num(row, "matchup_pa") or 0),
        "Matchup batters": int(_num(row, "matchup_batters") or 0),
        "K 80% range": f"{row.get('k_range_low', '—')}–{row.get('k_range_high', '—')}",
        "Hits 80% range": f"{row.get('hits_range_low', '—')}–{row.get('hits_range_high', '—')}",
        "Outs 80% range": f"{row.get('outs_range_low', '—')}–{row.get('outs_range_high', '—')}",
        "Probability semantics": row.get("probability_semantics", "—"),
        "History semantics": row.get("history_semantics", "—"),
        "Starter appearances used": int(_num(row, "starter_history_games") or 0),
    }
    st.dataframe(pd.DataFrame([facts]), hide_index=True, use_container_width=True)
    st.caption(
        "Strikeouts, total outs, and hits allowed each use independent simulation + mathematical paths with protected calibration baselines until enough resolved observations exist."
    )


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
            "hits_projection", "hits_range_low", "hits_range_high",
            "outs_projection", "outs_range_low", "outs_range_high",
            "confidence", "data_quality", "opponent_k_pct", "sim_5p", "math_5p",
            "hits_sim_over_5_5", "hits_math_over_5_5", "outs_sim_over_15_5", "outs_math_over_15_5", "probability_semantics",
            "actual_strikeouts", "actual_hits_allowed", "actual_outs",
        ]
        display_cols = [c for c in display_cols if c in slate.columns]
        display = slate[display_cols].copy().rename(
            columns={
                "player": "Pitcher",
                "team": "Team",
                "opponent": "Opp",
                "projection": "Projection K",
                "k_range_low": "K 80% Low",
                "k_range_high": "K 80% High",
                "hits_projection": "Projection Hits Allowed",
                "hits_range_low": "Hits 80% Low",
                "hits_range_high": "Hits 80% High",
                "outs_projection": "Projection Outs",
                "outs_range_low": "Outs 80% Low",
                "outs_range_high": "Outs 80% High",
                "confidence": "Confidence",
                "data_quality": "Data Quality",
                "opponent_k_pct": "Opp K%",
                "sim_5p": "SIM 5+ K",
                "math_5p": "MATH 5+ K",
                "hits_sim_over_5_5": "SIM O5.5 Hits",
                "hits_math_over_5_5": "MATH O5.5 Hits",
                "outs_sim_over_15_5": "SIM O15.5 Outs",
                "outs_math_over_15_5": "MATH O15.5 Outs",
                "probability_semantics": "Semantics",
                "actual_strikeouts": "Actual K",
                "actual_hits_allowed": "Actual Hits Allowed",
                "actual_outs": "Actual Outs",
            }
        )
        st.subheader(f"{slate_date:%B %d, %Y} starter slate")
        st.caption("Click any pitcher row to inspect why the model produced that frozen projection.")
        event = st.dataframe(
            display,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="daily_projection_selection",
        )
        selected_rows = list(event.selection.rows) if event is not None else []
        if selected_rows:
            selected_pos = int(selected_rows[0])
            selected_row = slate.iloc[selected_pos]
            render_projection_rationale(selected_row, load_log())

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
        with st.spinner("Checking MLB results and attaching actual strikeouts + hits allowed + outs..."):
            for idx in frame.index:
                actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])
                changed = False
                if pd.notna(actual_k) and pd.isna(frame.loc[idx].get("actual_strikeouts")):
                    frame.at[idx, "actual_strikeouts"] = actual_k
                    changed = True
                if pd.notna(actual_hits) and pd.isna(frame.loc[idx].get("actual_hits_allowed")):
                    frame.at[idx, "actual_hits_allowed"] = actual_hits
                    changed = True
                if pd.notna(actual_outs) and pd.isna(frame.loc[idx].get("actual_outs")):
                    frame.at[idx, "actual_outs"] = actual_outs
                    changed = True
                if changed:
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
        actual_k = pd.to_numeric(day_rows.get("actual_strikeouts"), errors="coerce")
        actual_hits = pd.to_numeric(day_rows.get("actual_hits_allowed"), errors="coerce")
        actual_outs = pd.to_numeric(day_rows.get("actual_outs"), errors="coerce")
        st.caption(
            f"Projection log currently contains {len(day_rows)} snapshot(s) for this slate; "
            f"{int(actual_k.notna().sum())} have resolved strikeouts and "
            f"{int(actual_hits.notna().sum())} have resolved hits allowed and "
            f"{int(actual_outs.notna().sum())} have resolved outs."
        )

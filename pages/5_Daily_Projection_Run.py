from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from engine.ui_theme import apply_page_theme

from automation.daily_projection_runner import (
    LOG_PATH,
    PROBABILITY_SEMANTICS,
    load_observation_log,
    resolve_observation_log,
    fill_missing_pregame_paths,
    attach_pregame_weather,
    attach_pregame_team_leash,
    refresh_pregame_lineups,
    project,
    resolve_row,
    resolve_workload_actuals,
    schedule,
)
from engine.calibration import calibrate_blend
from engine.hits_calibration import calibrate_hits_blend
from engine.outs_calibration import calibrate_outs_blend
from engine.odds_snapshot import refresh_strikeout_snapshot, resolve_api_key
from navigation import render_sidebar

st.set_page_config(page_title="Daily Projection Run", page_icon="📊", layout="wide")
apply_page_theme()
render_sidebar("daily")
st.markdown(
    """
    <style>
    .block-container { padding-top: 3.25rem !important; }
    /* daily-control-deck-v2: presentation only. */
    .daily-hero { margin:.25rem 0 1.15rem; padding:.9rem 1rem; border:1px solid rgba(73,111,151,.48); border-left:3px solid #ff3655; border-radius:16px; background:linear-gradient(120deg,rgba(227,25,55,.08),rgba(10,29,54,.76) 42%,rgba(6,18,35,.78)); box-shadow:0 14px 34px rgba(0,0,0,.16); }
    .daily-hero strong { color:#f8fbff; font-size:1rem; }
    .daily-hero span { display:block; color:#9db0c5; font-size:.84rem; margin-top:.2rem; }
    .daily-kicker { margin:1.35rem 0 .42rem; color:#aebfd2; font-size:.72rem; font-weight:900; letter-spacing:.13em; text-transform:uppercase; }
    .daily-kicker::before { content:''; display:inline-block; width:22px; height:2px; margin-right:.5rem; vertical-align:middle; background:#ff3655; box-shadow:0 0 11px rgba(227,25,55,.42); }
    .daily-paid-note { margin:.35rem 0 .8rem; padding:.72rem .85rem; border-radius:13px; border:1px solid rgba(250,204,21,.32); background:rgba(120,79,8,.08); color:#c9d7e5; font-size:.86rem; }
    @media (max-width:900px) { .daily-hero { padding:.78rem .85rem; } .daily-kicker { margin-top:1rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("📊 Daily Projection Run")
st.caption(
    "Run StrikeOut King 9000 across every announced MLB starter on the selected slate. "
    "Each pitcher is captured as an immutable pregame strikeout + total-outs + hits-allowed snapshot for calibration."
)
st.markdown(
    '<div class="daily-hero"><strong>Daily Control Deck · frozen pregame capture</strong>'
    '<span>Run the slate first. Paid strikeout lines are a separate manual data pull and never drive the baseball projection.</span></div>',
    unsafe_allow_html=True,
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
    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches"):
        if col not in frame.columns:
            frame[col] = np.nan
    if "resolved_at_utc" not in frame.columns:
        frame["resolved_at_utc"] = ""
    return frame


def history_only_for_day(day: str) -> pd.DataFrame:
    """Return persistent history-only starter observations for one slate date."""
    frame = load_observation_log()
    if frame.empty or "game_date" not in frame.columns:
        return pd.DataFrame()
    rows = frame.loc[frame["game_date"].astype(str).eq(str(day))].copy()
    if rows.empty:
        return rows
    actual_cols = [
        "actual_strikeouts", "actual_hits_allowed", "actual_outs",
        "actual_batters_faced", "actual_pitches",
    ]
    for col in actual_cols + ["history_games_available_at_capture"]:
        if col in rows.columns:
            rows[col] = pd.to_numeric(rows[col], errors="coerce")
    available = [col for col in actual_cols if col in rows.columns]
    resolved = rows[available].notna().all(axis=1) if available else pd.Series(False, index=rows.index)
    rows["observation_status"] = np.where(resolved, "RESOLVED", "PENDING")
    return rows.sort_values(["observation_status", "game_time", "player"], ascending=[True, True, True]).reset_index(drop=True)


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
    if "starter_history_source" not in frame.columns:
        frame["starter_history_source"] = ""
    if "starter_history_mlb_games" not in frame.columns:
        frame["starter_history_mlb_games"] = np.nan
    if "starter_history_observation_games" not in frame.columns:
        frame["starter_history_observation_games"] = np.nan
    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches"):
        if col not in frame.columns:
            frame[col] = np.nan
    if "resolved_at_utc" not in frame.columns:
        frame["resolved_at_utc"] = ""
    frame.to_csv(LOG_PATH, index=False)


def run_full_slate(day: str) -> tuple[pd.DataFrame, int, int, list[str], list[str]]:
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
    history_only: list[str] = []
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
            history_only.append(
                f"{row.get('player', 'Unknown')}: no usable starter history — final K / hits / outs / BF / pitches will be tracked"
            )
            continue
        new_rows.append(result)

    if new_rows:
        frame = pd.concat([frame, pd.DataFrame(new_rows)], ignore_index=True)

    refreshed = fill_missing_pregame_paths(frame)
    weather_refreshed = attach_pregame_weather(frame, announced)
    team_leash_refreshed = attach_pregame_team_leash(frame)
    lineup_refreshed = refresh_pregame_lineups(frame, announced)
    save_log(frame)

    slate = frame.loc[frame.get("game_date", pd.Series(dtype=str)).astype(str).eq(day)].copy() if not frame.empty else pd.DataFrame()
    return slate, len(new_rows), skipped + refreshed + weather_refreshed + team_leash_refreshed + lineup_refreshed, history_only, errors


def _num(row: pd.Series, key: str) -> float | None:
    value = pd.to_numeric(pd.Series([row.get(key)]), errors="coerce").iloc[0]
    return None if pd.isna(value) else float(value)


def _range_text(low: object, high: object) -> str:
    """Render a central outcome interval as one compact human-readable value."""
    lo = pd.to_numeric(pd.Series([low]), errors="coerce").iloc[0]
    hi = pd.to_numeric(pd.Series([high]), errors="coerce").iloc[0]
    if pd.isna(lo) or pd.isna(hi):
        return "—"

    def _endpoint(value: float) -> str:
        value = float(value)
        rounded = round(value)
        return str(int(rounded)) if abs(value - rounded) < 1e-9 else f"{value:.1f}"

    return f"{_endpoint(float(lo))}–{_endpoint(float(hi))}"


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
        "Lineup source": row.get("lineup_source", "ACTIVE_ROSTER"),
        "Confirmed lineup hitters": int(_num(row, "lineup_batters") or 0),
        "Lineup projection delta": _num(row, "lineup_projection_delta"),
        "K 80% range": f"{row.get('k_range_low', '—')}–{row.get('k_range_high', '—')}",
        "Hits 80% range": f"{row.get('hits_range_low', '—')}–{row.get('hits_range_high', '—')}",
        "Outs 80% range": f"{row.get('outs_range_low', '—')}–{row.get('outs_range_high', '—')}",
        "Probability semantics": row.get("probability_semantics", "—"),
        "History semantics": row.get("history_semantics", "—"),
        "Starter appearances used": int(_num(row, "starter_history_games") or 0),
        "History source": row.get("starter_history_source", "—"),
        "MLB starts used": int(_num(row, "starter_history_mlb_games") or 0),
        "Observed starts used": int(_num(row, "starter_history_observation_games") or 0),
        "Workload version": row.get("workload_version", "—"),
        "Expected pitches": _num(row, "expected_pitches"),
        "Expected BF": _num(row, "expected_bf"),
        "Expected outs workload": _num(row, "expected_outs"),
        "Pitches / BF": _num(row, "pitches_per_bf"),
        "Days since last start": _num(row, "days_since_last_start"),
        "Recent leash": row.get("leash_label", "—"),
        "Pitch trend": _num(row, "pitch_trend"),
        "Team leash role": row.get("team_leash_role", "—"),
        "Team leash status": row.get("team_leash_status", "—"),
        "Team leash label": row.get("team_leash_label", "—"),
        "Team starts tracked": int(_num(row, "team_leash_starts") or 0),
        "Team avg pitches": _num(row, "team_leash_avg_pitches"),
        "Team TTO reach rate": _num(row, "team_leash_tto_reach_rate"),
        "Team 90+ pitch rate": _num(row, "team_leash_90_pitch_rate"),
        "Candidate pitch multiplier": _num(row, "team_leash_pitch_multiplier_candidate"),
    }
    st.dataframe(pd.DataFrame([facts]), hide_index=True, use_container_width=True)
    st.caption(
        "Strikeouts, total outs, and hits allowed each use independent simulation + mathematical paths with protected calibration baselines until enough resolved observations exist."
    )


st.info(
    "This page is for batch data capture. The normal Projection page remains the single-pitcher deep-dive workflow. "
    "Existing game/pitcher snapshots stay frozen after first pitch; while still pregame, a roster-fallback row may upgrade once MLB posts a confirmed batting order."
)

st.markdown('<div class="daily-kicker">Manual paid data</div>', unsafe_allow_html=True)
st.markdown('<div class="daily-paid-note">Optional market-data pull · manual only · strikeout lines only · saved snapshot is reused elsewhere without another paid request.</div>', unsafe_allow_html=True)
st.markdown("### 💳 Paid strikeout lines")
st.caption("Manual only. This button is the ONLY paid Odds API path and requests pitcher_strikeouts only. The saved snapshot is reused by Main Projections without another API call.")
if st.button("💳 LOAD STRIKEOUT LINES · PAID API", use_container_width=True, key="daily_paid_k_odds"):
    api_key=resolve_api_key(st.secrets)
    with st.spinner("Loading today's main pitcher strikeout lines once and saving the snapshot..."):
        odds_snapshot,quota,odds_error=refresh_strikeout_snapshot(api_key,slate_date.isoformat())
    if odds_error:
        st.error(odds_error)
    else:
        pitchers=int(odds_snapshot.get("pitcher",pd.Series(dtype=str)).nunique()) if not odds_snapshot.empty else 0
        st.success(f"Saved {len(odds_snapshot)} strikeout offers for {pitchers} pitchers. Main Projections will reuse this snapshot for free.")
        if quota:
            st.caption(f"Last paid request: {quota.get('last','—')} credit(s) · {quota.get('remaining','—')} remaining · {quota.get('used','—')} used.")

st.markdown('<div class="daily-kicker">Projection capture</div>', unsafe_allow_html=True)
if st.button("⚾ RUN ALL TODAY'S PITCHERS", type="primary", use_container_width=True):
    with st.spinner("Simulating every announced starter and writing pregame snapshots..."):
        try:
            slate, added, skipped, history_only, errors = run_full_slate(slate_date.isoformat())
        except Exception as exc:
            slate = pd.DataFrame()
            added = skipped = 0
            history_only = []
            errors = [f"Slate run failed: {type(exc).__name__}: {exc}"]
    st.session_state["daily_slate"] = slate
    st.session_state["daily_added"] = added
    st.session_state["daily_skipped"] = skipped
    st.session_state["daily_history_only"] = history_only
    st.session_state["daily_errors"] = errors

st.markdown('<div class="daily-kicker">Slate output</div>', unsafe_allow_html=True)
slate = st.session_state.get("daily_slate")
if isinstance(slate, pd.DataFrame):
    added = int(st.session_state.get("daily_added", 0))
    skipped = int(st.session_state.get("daily_skipped", 0))
    history_only = list(st.session_state.get("daily_history_only", []))
    errors = list(st.session_state.get("daily_errors", []))
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Projected starters", len(slate))
    c2.metric("New snapshots", added)
    c3.metric("Already captured/refreshed", skipped)
    c4.metric("History-only tracked", len(history_only))
    c5.metric("Errors", len(errors))
    confirmed_lineups = int(slate.get("lineup_source", pd.Series(index=slate.index, dtype=str)).astype(str).eq("CONFIRMED_LINEUP").sum()) if not slate.empty else 0
    c6.metric("Confirmed lineups", confirmed_lineups)

    if not slate.empty:
        # Keep the primary projection scan tight: pitcher/matchup first, then Ks.
        # Audit/context fields (weather, starter sample, workload) stay available
        # but live farther right so they do not separate the pitcher from Projection K.
        display_cols = [
            "player", "team", "opponent", "projection", "k_range_low", "k_range_high", "sim_5p", "math_5p",
            "hits_projection", "hits_range_low", "hits_range_high", "hits_sim_over_5_5", "hits_math_over_5_5",
            "outs_projection", "outs_range_low", "outs_range_high", "outs_sim_over_15_5", "outs_math_over_15_5",
            "confidence", "data_quality", "opponent_k_pct",
            "lineup_source", "lineup_batters", "lineup_projection_delta",
            "weather_icon", "weather_delay_risk", "weather_precip_probability",
            "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games",
            "workload_version", "expected_pitches", "expected_bf", "expected_outs", "pitches_per_bf", "days_since_last_start", "leash_label", "pitch_trend",
            "team_leash_label", "team_leash_status", "team_leash_starts", "team_leash_avg_pitches", "team_leash_tto_reach_rate", "team_leash_90_pitch_rate", "team_leash_pitch_multiplier_candidate", "team_leash_role",
            "probability_semantics", "actual_strikeouts", "actual_hits_allowed", "actual_outs",
        ]
        display_cols = [c for c in display_cols if c in slate.columns]
        display = slate[display_cols].copy()
        if "weather_icon" in display.columns:
            display["player"] = display.apply(lambda r: f"{r.get('player', 'Unknown')} {str(r.get('weather_icon', '') or '')}".strip(), axis=1)
            display = display.drop(columns=["weather_icon"])

        # Low/high columns are endpoints of ONE central 80% interval. Collapse
        # them into a single value so nobody reads either endpoint as an 80%
        # milestone probability. Keep the new range exactly where the old pair
        # lived so each market scans projection -> range -> SIM -> MATH.
        for low_col, high_col, label in (
            ("k_range_low", "k_range_high", "80% K Range"),
            ("hits_range_low", "hits_range_high", "80% Hits Range"),
            ("outs_range_low", "outs_range_high", "80% Outs Range"),
        ):
            if low_col in display.columns and high_col in display.columns:
                insert_at = display.columns.get_loc(low_col)
                values = [
                    _range_text(low, high)
                    for low, high in zip(display[low_col], display[high_col])
                ]
                display.insert(insert_at, label, values)
                display = display.drop(columns=[low_col, high_col])

        display = display.rename(
            columns={
                "player": "Pitcher",
                "starter_history_games": "Starts",
                "starter_history_source": "History",
                "starter_history_mlb_games": "MLB Starts",
                "starter_history_observation_games": "Observed Starts",
                "workload_version": "Workload",
                "expected_pitches": "Exp Pitches",
                "expected_bf": "Exp BF",
                "expected_outs": "Exp Outs",
                "pitches_per_bf": "Pitches/BF",
                "days_since_last_start": "Rest Days",
                "leash_label": "Leash",
                "pitch_trend": "Pitch Trend",
                "team_leash_label": "Team Leash",
                "team_leash_status": "Team Leash Status",
                "team_leash_starts": "Team Starts",
                "team_leash_avg_pitches": "Team Avg Pitches",
                "team_leash_tto_reach_rate": "TTO %",
                "team_leash_90_pitch_rate": "90+ %",
                "team_leash_pitch_multiplier_candidate": "Pitch Adj",
                "team_leash_role": "Team Leash Role",
                "weather_delay_risk": "Weather",
                "weather_precip_probability": "Rain %",
                "lineup_source": "Lineup",
                "lineup_batters": "Hitters",
                "lineup_projection_delta": "Lineup K Δ",
                "team": "Team",
                "opponent": "Opp",
                "projection": "Projection K",
                "hits_projection": "Projection Hits",
                "outs_projection": "Projection Outs",
                "confidence": "Confidence",
                "data_quality": "Quality",
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
        projection_highlight_cols = [
            col for col in ("Projection K", "Projection Hits", "Projection Outs")
            if col in display.columns
        ]
        probability_cols = [
            col for col in (
                "SIM 5+ K", "MATH 5+ K", "SIM O5.5 Hits", "MATH O5.5 Hits",
                "SIM O15.5 Outs", "MATH O15.5 Outs",
            )
            if col in display.columns
        ]
        formatters: dict[str, str] = {}
        for col in projection_highlight_cols:
            formatters[col] = "{:.2f}"
        for col in probability_cols:
            formatters[col] = "{:.1%}"
        for col in ("Exp Pitches", "Exp BF", "Exp Outs", "Team Avg Pitches"):
            if col in display.columns:
                formatters[col] = "{:.1f}"
        for col in ("Pitches/BF",):
            if col in display.columns:
                formatters[col] = "{:.2f}"
        for col in ("Quality", "Starts", "MLB Starts", "Observed Starts", "Rest Days", "Team Starts"):
            if col in display.columns:
                formatters[col] = "{:.0f}"
        if "Opp K%" in display.columns:
            formatters["Opp K%"] = "{:.1f}%"
        if "Rain %" in display.columns:
            formatters["Rain %"] = "{:.0f}%"
        if "Lineup K Δ" in display.columns:
            formatters["Lineup K Δ"] = "{:+.2f}"
        for col in ("Pitch Trend", "TTO %", "90+ %"):
            if col in display.columns:
                formatters[col] = "{:.1%}"
        if "Pitch Adj" in display.columns:
            formatters["Pitch Adj"] = "{:.3f}"
        for col in ("Actual K", "Actual Hits Allowed", "Actual Outs"):
            if col in display.columns:
                formatters[col] = "{:.0f}"

        styled_display = display.style.format(formatters, na_rep="—")
        if projection_highlight_cols:
            styled_display = styled_display.map(
                lambda value: "color: #22c55e; font-weight: 700;" if pd.notna(value) else "",
                subset=projection_highlight_cols,
            )

        st.subheader(f"{slate_date:%B %d, %Y} starter slate")
        st.caption(
            "How to read: Projection = expected average outcome · 80% Range = one central simulated interval (10th–90th percentile), not an 80% chance at each endpoint · "
            "SIM/MATH = the probability from each independent model path. Click a pitcher row for the full breakdown. Headline projections are green."
        )
        event = st.dataframe(
            styled_display,
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

    if history_only:
        st.info("📚 History-only starters being tracked")
        st.caption(
            "These starters were not projected because there was not enough legitimate starter history. "
            "Their final strikeouts, hits allowed, outs, batters faced, and pitches will still be saved so future starts can use the new data."
        )
        for pitcher in history_only:
            st.write(f"- {pitcher}")

    if errors:
        st.warning("Some announced starters hit real capture errors:")
        for error in errors:
            st.write(f"- {error}")

st.divider()
st.subheader("📚 Persistent history-only starter tracker")
st.caption(
    "These rows live in starter_observation_log.csv, separate from projection_log.csv. "
    "They are real starter observations collected specifically for pitchers who could not yet receive a legitimate projection."
)
history_rows = history_only_for_day(slate_date.isoformat())
if history_rows.empty:
    st.info("No history-only starter observations are recorded for this slate date.")
else:
    resolved_count = int(history_rows["observation_status"].eq("RESOLVED").sum())
    pending_count = int(history_rows["observation_status"].eq("PENDING").sum())
    h1, h2, h3 = st.columns(3)
    h1.metric("History-only starts", len(history_rows))
    h2.metric("Pending results", pending_count)
    h3.metric("Resolved into history", resolved_count)

    history_display_cols = [
        "player", "team", "opponent", "reason", "history_games_available_at_capture",
        "observation_status", "actual_strikeouts", "actual_hits_allowed", "actual_outs",
        "actual_batters_faced", "actual_pitches", "resolved_at_utc",
    ]
    history_display_cols = [col for col in history_display_cols if col in history_rows.columns]
    history_display = history_rows[history_display_cols].copy().rename(columns={
        "player": "Pitcher",
        "team": "Team",
        "opponent": "Opp",
        "reason": "Tracking Reason",
        "history_games_available_at_capture": "Starts Available",
        "observation_status": "Status",
        "actual_strikeouts": "Actual K",
        "actual_hits_allowed": "Actual Hits Allowed",
        "actual_outs": "Actual Outs",
        "actual_batters_faced": "Actual BF",
        "actual_pitches": "Actual Pitches",
        "resolved_at_utc": "Resolved At",
    })
    st.dataframe(history_display, hide_index=True, use_container_width=True)
    st.caption(
        "When a row resolves, its full starter line becomes eligible fallback history for that pitcher on a future start. "
        "It never becomes a fake historical projection or calibration row."
    )

st.divider()
st.subheader("Resolve completed games")
if st.button("Resolve completed projection outcomes"):
    frame = load_log()
    updated = 0
    observation_updates = 0
    with st.spinner("Checking MLB results for projected and history-only starters..."):
        if not frame.empty:
            for idx in frame.index:
                actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])
                actual_bf, actual_pitches = resolve_workload_actuals(frame.loc[idx])
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
                if pd.notna(actual_bf) and pd.isna(frame.loc[idx].get("actual_batters_faced")):
                    frame.at[idx, "actual_batters_faced"] = actual_bf
                    changed = True
                if pd.notna(actual_pitches) and pd.isna(frame.loc[idx].get("actual_pitches")):
                    frame.at[idx, "actual_pitches"] = actual_pitches
                    changed = True
                if changed:
                    frame.at[idx, "resolved_at_utc"] = resolved
                    updated += 1
            save_log(frame)
        observation_updates = resolve_observation_log()
    if updated or observation_updates:
        st.success(
            f"Resolved {updated} new projection outcome(s) and {observation_updates} history-only starter observation(s)."
        )
    else:
        st.info("No new completed projected or history-only starter outcomes were available.")

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

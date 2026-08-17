from __future__ import annotations

from pathlib import Path

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
from navigation import render_sidebar
from training.projection_storage import build_projection_archive_view, load_projection_archive

from automation.resolve_projection_log import main as resolve_projection_log
from engine.calibration import milestone_calibration_report
from engine.hits_calibration import hits_calibration_report
from engine.outs_calibration import outs_calibration_report
from engine.starter_history import HISTORY_SEMANTICS
from engine.model_health import (
    daily_top5_summary,
    health_from_walk_forward,
    reliability_table,
    walk_forward_top5,
)
from engine.decision_learning import decision_tier_report
from engine.signal_validation import context_performance_report, paired_signal_report
from engine.team_leash import team_leash_walk_forward_report
from engine.projection_crushers import bettable_k_label, bettable_k_result, bettable_k_target, crusher_report
from engine.execution_history import backfill_legacy_execution_sides, grade_frozen_execution

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "projection_log.csv"
ARCHIVE_PATH = ROOT / "data" / "projection_archive.csv"
OBS_LOG_PATH = ROOT / "data" / "starter_observation_log.csv"
ROLLING_WINDOW = 20

st.set_page_config(page_title="Projection History", page_icon="📚", layout="wide")
apply_page_theme()
render_sidebar("history")
apply_command_center_consistency("projection_history")
apply_explainability_theme()
st.markdown(
    """
    <style>
    .block-container { padding-top: 3.25rem !important; }
    /* history-dashboard-v1: presentation only; no grading/model semantics. */
    .history-hero {
        margin: .25rem 0 1.2rem; padding: .9rem 1rem; border-radius: 16px;
        border: 1px solid rgba(227,25,55,.34);
        background: linear-gradient(120deg, rgba(227,25,55,.09), rgba(10,29,54,.72) 42%, rgba(6,18,35,.76));
        box-shadow: 0 14px 34px rgba(0,0,0,.16);
    }
    .history-hero strong { color:#f8fbff; font-size:1rem; letter-spacing:.01em; }
    .history-hero span { display:block; color:#9db0c5; font-size:.84rem; margin-top:.18rem; }
    .history-kicker {
        margin: 1.35rem 0 .45rem; color:#aebfd2; font-size:.72rem; font-weight:900;
        letter-spacing:.13em; text-transform:uppercase;
    }
    .history-kicker::before {
        content:''; display:inline-block; width:22px; height:2px; margin-right:.5rem; vertical-align:middle;
        background:#ff3655; box-shadow:0 0 11px rgba(227,25,55,.42);
    }
    @media (max-width: 900px) {
        .history-hero { padding:.78rem .85rem; }
        .history-kicker { margin-top:1rem; }
    }
    /* PROJECTION_HISTORY_COMMAND_UI_V2 */
    .block-container{max-width:1540px!important;padding-top:2.05rem!important;padding-bottom:4rem!important}
    .ph-command-hero{position:relative;overflow:hidden;margin:.1rem 0 .85rem;padding:1.05rem 1.2rem 1.1rem;border:1px solid rgba(80,108,136,.78);border-radius:18px;background:linear-gradient(112deg,rgba(8,28,50,.99),rgba(5,19,35,.99));box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 18px 42px rgba(0,0,0,.30)}
    .ph-command-hero:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(#ff3655,#a60c29)}
    .ph-command-kicker{font:900 .70rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.13em;color:#ff6a7d;text-transform:uppercase}
    .ph-command-title{margin:.22rem 0 .28rem;font-family:Impact,"Arial Black","Arial Narrow",sans-serif;font-size:clamp(2.6rem,5vw,4.8rem);line-height:.86;letter-spacing:.012em;color:#f5f1e9;text-transform:uppercase;text-shadow:3px 4px 0 #07182b}
    .ph-command-title span{color:#ec1638;-webkit-text-stroke:1px #f1eee7;paint-order:stroke fill}
    .ph-command-sub{max-width:1180px;color:#c0ceda;font:650 .90rem/1.48 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .ph-command-rule{margin-top:.58rem;width:max-content;max-width:100%;padding:.25rem .58rem;border-top:1px solid rgba(236,22,56,.65);border-bottom:1px solid rgba(236,22,56,.65);color:#edf3f7;font:900 .67rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.09em;text-transform:uppercase}
    .history-section-head{width:max-content;min-width:260px;max-width:92%;margin:1.05rem auto .65rem;padding:.44rem 1.65rem;border:1px solid #ff3151;border-bottom-color:#790b1d;border-radius:8px;background:linear-gradient(180deg,#f21b3d,#b70d29);box-shadow:0 7px 16px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.22);color:#fff;font:900 .90rem/1.15 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.04em;text-align:center;text-transform:uppercase}
    .history-primary-note{margin:.3rem 0 .8rem;padding:.78rem .9rem;border:1px solid rgba(73,111,151,.56);border-left:3px solid #ff3655;border-radius:13px;background:linear-gradient(110deg,rgba(10,34,59,.90),rgba(5,22,40,.92));color:#d2dde6;font:700 .84rem/1.45 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .history-secondary-zone{margin:1.5rem 0 .5rem;padding:.72rem .9rem;border:1px solid rgba(73,111,151,.42);border-radius:12px;background:rgba(5,20,37,.72);color:#8fa6ba;font:900 .68rem/1.3 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.12em;text-align:center;text-transform:uppercase}
    [data-testid="stMetric"]{min-height:108px;padding:.70rem .76rem!important;border:1px solid rgba(77,108,137,.72)!important;border-radius:14px!important;background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98))!important}
    [data-testid="stMetricLabel"]{color:#eef4f8!important;font-size:.78rem!important;font-weight:900!important;text-transform:uppercase!important}
    [data-testid="stMetricValue"]{font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;color:#fff!important;font-size:1.65rem!important;font-weight:900!important}
    div[data-testid="stDataFrame"]{border:1px solid rgba(77,108,137,.62);border-radius:14px;overflow:hidden;box-shadow:0 12px 28px rgba(0,0,0,.20)}
    div[data-testid="stExpander"]{border:1px solid rgba(72,103,134,.60)!important;border-radius:13px!important;background:rgba(5,21,39,.68)!important}
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="ph-command-hero"><div class="ph-command-kicker">StrikeOut King 9000 · Frozen Evidence Vault</div>'
    '<div class="ph-command-title">PROJECTION <span>HISTORY</span></div>'
    '<div class="ph-command-sub">Your manually approved Projection Archive stays first. Frozen model evidence, resolved MLB outcomes, calibration, workload audits, and learning diagnostics remain underneath for deeper review.</div>'
    '<div class="ph-command-rule">ARCHIVE FIRST · REAL LINES · FROZEN MODEL EVIDENCE</div></div>',
    unsafe_allow_html=True,
)



def load_projection_history() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(LOG_PATH)
    except Exception:
        return pd.DataFrame()


def load_user_archive(evidence: pd.DataFrame) -> pd.DataFrame:
    # PROJECTION_HISTORY_DURABLE_ARCHIVE_V1
    durable_manual = load_projection_archive(ARCHIVE_PATH, st.secrets)
    durable_manual, _ = backfill_legacy_execution_sides(durable_manual, evidence)
    return build_projection_archive_view(evidence, durable_manual)


def load_observation_history() -> pd.DataFrame:
    if not OBS_LOG_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(OBS_LOG_PATH)
    except Exception:
        return pd.DataFrame()


def range_result(row: pd.Series, actual_col: str, low_col: str, high_col: str) -> str:
    if pd.isna(row.get(actual_col)):
        return "PENDING"
    if pd.isna(row.get(low_col)) or pd.isna(row.get(high_col)):
        return "RESOLVED"
    actual = float(row[actual_col])
    return "✅ IN RANGE" if float(row[low_col]) <= actual <= float(row[high_col]) else "❌ OUTSIDE"


def rolling_learning_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    current = frame.loc[frame.get("history_semantics", pd.Series(index=frame.index, dtype=str)).astype(str).eq(HISTORY_SEMANTICS)].copy()
    if current.empty:
        return pd.DataFrame()

    current["game_date_dt"] = pd.to_datetime(current.get("game_date"), errors="coerce")
    current = current.sort_values(["game_date_dt", "captured_at_utc"], na_position="last").reset_index(drop=True)
    resolved_any = (
        pd.to_numeric(current.get("actual_strikeouts"), errors="coerce").notna()
        | pd.to_numeric(current.get("actual_hits_allowed"), errors="coerce").notna()
        | pd.to_numeric(current.get("actual_outs"), errors="coerce").notna()
    )
    current = current.loc[resolved_any].reset_index(drop=True)
    if current.empty:
        return current
    current["Resolved Start #"] = np.arange(1, len(current) + 1)

    specs = (
        ("K", "projection", "actual_strikeouts", "k_range_low", "k_range_high"),
        ("Hits", "hits_projection", "actual_hits_allowed", "hits_range_low", "hits_range_high"),
        ("Outs", "outs_projection", "actual_outs", "outs_range_low", "outs_range_high"),
    )
    for label, projection_col, actual_col, low_col, high_col in specs:
        projected = pd.to_numeric(current.get(projection_col), errors="coerce")
        actual = pd.to_numeric(current.get(actual_col), errors="coerce")
        low = pd.to_numeric(current.get(low_col), errors="coerce")
        high = pd.to_numeric(current.get(high_col), errors="coerce")
        valid = projected.notna() & actual.notna()
        abs_error = (actual - projected).abs().where(valid)
        range_ready = actual.notna() & low.notna() & high.notna()
        range_hit = ((actual >= low) & (actual <= high)).astype(float).where(range_ready)
        current[f"{label} Rolling MAE"] = abs_error.rolling(ROLLING_WINDOW, min_periods=3).mean()
        current[f"{label} Rolling Range Hit Rate"] = range_hit.rolling(ROLLING_WINDOW, min_periods=3).mean()
    return current


df = load_projection_history()
if df.empty:
    st.info("No archived projections yet. Use Daily Projection Run to capture the announced starter slate before first pitch.")
    st.stop()

numeric_cols = [
    "projection", "k_range_low", "k_range_high", "actual_strikeouts",
    "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed",
    "outs_projection", "outs_range_low", "outs_range_high", "actual_outs", "starter_history_games",
    "expected_pitches", "expected_bf", "expected_outs", "actual_batters_faced", "actual_pitches",
    "pitches_per_bf", "days_since_last_start", "pitch_trend", "bf_trend", "outs_trend",
]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

for col in [
    "projection", "actual_strikeouts", "k_range_low", "k_range_high",
    "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed",
    "outs_projection", "outs_range_low", "outs_range_high", "actual_outs",
    "history_semantics", "starter_history_games", "captured_at_utc",
]:
    if col not in df.columns:
        df[col] = pd.NA

# PROJECTION_HISTORY_ARCHIVE_COMMAND_V2
st.markdown('<div class="history-section-head">Projection Archive</div>', unsafe_allow_html=True)
st.markdown('<div class="history-primary-note">Every frozen daily projection slate appears here automatically. Your sportsbook lines are a durable execution overlay saved separately, so a reboot cannot remove the slate or detach previously saved manual lines.</div>', unsafe_allow_html=True)
explain_popover(static_explanation("history_archive"),label="ⓘ EXPLAIN PROJECTION ARCHIVE")
user_archive = load_user_archive(df)
if user_archive.empty:
    st.info("No frozen projection slates are available yet. Daily Projection Run or the automatic capture job will populate this archive.")
else:
    user_archive = user_archive.copy()
    user_archive["_archive_date"] = pd.to_datetime(user_archive.get("game_date"), errors="coerce")
    for col in (
        "manual_strikeout_line", "projection", "actual_strikeouts",
        "manual_outs_line", "outs_projection", "actual_outs",
        "manual_hits_allowed_line", "hits_projection", "actual_hits_allowed",
    ):
        if col in user_archive.columns:
            user_archive[col] = pd.to_numeric(user_archive[col], errors="coerce")
    user_archive = user_archive.sort_values(["_archive_date", "player"], ascending=[False, True], na_position="last")
    for col in ("manual_outs_side", "manual_hits_allowed_side"):
        if col not in user_archive.columns:
            user_archive[col] = ""
    user_archive["archive_outs_bet_result"] = user_archive.apply(
        lambda row: grade_frozen_execution(row.get("manual_outs_side"), row.get("manual_outs_line"), row.get("actual_outs")), axis=1
    )
    user_archive["archive_hits_bet_result"] = user_archive.apply(
        lambda row: grade_frozen_execution(row.get("manual_hits_allowed_side"), row.get("manual_hits_allowed_line"), row.get("actual_hits_allowed")), axis=1
    )

    user_archive["archive_k_target"] = user_archive.get("projection", pd.Series(index=user_archive.index, dtype=float)).map(bettable_k_label)
    user_archive["archive_k_result"] = user_archive.apply(
        lambda row: bettable_k_result(row.get("projection"), row.get("actual_strikeouts")), axis=1
    )

    archive_dates = user_archive["_archive_date"].dt.date.dropna()
    archived_slates = int(archive_dates.nunique())
    line_cols = [col for col in ("manual_strikeout_line", "manual_outs_line", "manual_hits_allowed_line") if col in user_archive.columns]
    manual_lines = int(sum(user_archive[col].notna().sum() for col in line_cols))
    actual_cols = [col for col in ("actual_strikeouts", "actual_outs", "actual_hits_allowed") if col in user_archive.columns]
    resolved_pitchers = int(user_archive[actual_cols].notna().any(axis=1).sum()) if actual_cols else 0
    latest_archive_date = max(archive_dates).strftime("%b %d") if len(archive_dates) else "—"

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Archived slates", archived_slates, help=metric_help("history_archived_slates", current=f"{archived_slates} unique slate date(s)"))
    a2.metric("Archived pitchers", len(user_archive), help=metric_help("history_archived_pitchers", current=f"{len(user_archive)} archived pitcher-game row(s)"))
    a3.metric("Manual lines attached", manual_lines, help=metric_help("history_manual_lines", current=f"{manual_lines} saved manual market line(s)"))
    a4.metric("Latest slate", latest_archive_date, help=metric_help("history_latest_slate", current=f"Most recent archive date: {latest_archive_date}"))
    explain_popover(static_explanation("history_archive"),label="ⓘ EXPLAIN ARCHIVE COUNTERS")
    st.caption(f"{resolved_pitchers} archived pitcher row(s) currently have at least one resolved MLB outcome attached.")

    archive_columns = [
        "player", "team", "opponent",
        "projection", "archive_k_target", "actual_strikeouts", "archive_k_result", "manual_strikeout_line",
        "outs_projection", "manual_outs_line", "manual_outs_side", "actual_outs", "archive_outs_bet_result",
        "hits_projection", "manual_hits_allowed_line", "manual_hits_allowed_side", "actual_hits_allowed", "archive_hits_bet_result",
        "confidence", "data_quality", "archive_source", "archive_committed_at_utc",
    ]
    archive_columns = [col for col in archive_columns if col in user_archive.columns]
    unique_dates = user_archive["_archive_date"].dt.date.dropna().drop_duplicates().tolist()
    for idx, archive_date in enumerate(unique_dates):
        group = user_archive.loc[user_archive["_archive_date"].dt.date.eq(archive_date), archive_columns].copy()
        date_label = pd.Timestamp(archive_date).strftime("%B %-d, %Y")
        day_line_count = int(sum(group[col].notna().sum() for col in line_cols if col in group.columns))
        day_resolved = int(group[[col for col in actual_cols if col in group.columns]].notna().any(axis=1).sum()) if actual_cols else 0
        with st.expander(
            f"📅 {date_label} · {len(group)} pitcher{'s' if len(group) != 1 else ''} · {day_line_count} manual lines · {day_resolved} resolved",
            expanded=(idx == 0),
        ):
            view = group.rename(columns={
                "player": "Pitcher", "team": "Team", "opponent": "Opp",
                "projection": "Projected K", "archive_k_target": "K Target", "actual_strikeouts": "Actual K", "archive_k_result": "K Result", "manual_strikeout_line": "K Line",
                "outs_projection": "Projected Outs", "actual_outs": "Actual Outs", "manual_outs_line": "Outs Line", "manual_outs_side": "Outs Side", "archive_outs_bet_result": "Outs Bet Result",
                "manual_hits_allowed_line": "Hits Line", "manual_hits_allowed_side": "Hits Side", "hits_projection": "Projected Hits", "actual_hits_allowed": "Actual Hits", "archive_hits_bet_result": "Hits Bet Result",
                "confidence": "Confidence", "data_quality": "Quality",
                "archive_source": "Archive Source", "archive_committed_at_utc": "Committed UTC",
            })
            # Normalize placeholder strings and hide columns that are empty for this slate.
            for col in view.columns:
                if view[col].dtype == object:
                    cleaned = view[col].astype(str).str.strip()
                    empty_token = cleaned.str.lower().isin({"", "nan", "none", "null", "nat", "<na>"})
                    view.loc[empty_token, col] = pd.NA
            populated = [col for col in view.columns if bool(view[col].notna().any())]
            view = view[populated]
            preferred = [
                "Pitcher", "Team", "Opp",
                "Projected K", "K Target", "Actual K", "K Result", "K Line",
                "Projected Outs", "Outs Line", "Outs Side", "Actual Outs", "Outs Bet Result",
                "Projected Hits", "Hits Line", "Hits Side", "Actual Hits", "Hits Bet Result",
                "Confidence", "Quality", "Archive Source", "Committed UTC",
            ]
            ordered = [col for col in preferred if col in view.columns]
            ordered += [col for col in view.columns if col not in ordered]
            view = view[ordered]

            formatters = {}
            for col in ("K Line", "Outs Line", "Hits Line"):
                if col in view.columns:
                    formatters[col] = "{:.1f}"
            for col in ("Projected K", "Projected Outs", "Projected Hits"):
                if col in view.columns:
                    formatters[col] = "{:.2f}"
            for col in ("Actual K", "Actual Outs", "Actual Hits", "Quality"):
                if col in view.columns:
                    formatters[col] = "{:.0f}"
            styled = view.style.format(formatters, na_rep="—")
            manual_cols = [col for col in ("K Line", "Outs Line", "Hits Line") if col in view.columns]
            projection_cols = [col for col in ("Projected K", "Projected Outs", "Projected Hits") if col in view.columns]
            actual_view_cols = [col for col in ("Actual K", "Actual Outs", "Actual Hits") if col in view.columns]
            target_view_cols = [col for col in ("K Target",) if col in view.columns]
            if manual_cols:
                styled = styled.map(lambda value: "color:#ff9f1c;font-weight:850;background-color:rgba(255,159,28,.10);" if pd.notna(value) else "", subset=manual_cols)
            if projection_cols:
                styled = styled.map(lambda value: "color:#22c55e;font-weight:800;" if pd.notna(value) else "", subset=projection_cols)
            if actual_view_cols:
                styled = styled.map(lambda value: "color:#facc15;font-weight:800;" if pd.notna(value) else "", subset=actual_view_cols)
            if target_view_cols:
                styled = styled.map(lambda value: "color:#38bdf8;font-weight:800;" if pd.notna(value) else "", subset=target_view_cols)
            if "K Result" in view.columns:
                styled = styled.map(
                    lambda value: "color:#22c55e;font-weight:900;" if "WIN" in str(value) else "color:#ff6379;font-weight:900;" if "MISS" in str(value) else "color:#ffd166;font-weight:800;",
                    subset=["K Result"],
                )
            for result_col in ("Outs Bet Result", "Hits Bet Result"):
                if result_col in view.columns:
                    styled = styled.map(
                        lambda value: "color:#22c55e;font-weight:900;" if "WIN" in str(value) else "color:#ff6379;font-weight:900;" if "LOSS" in str(value) else "color:#ffd166;font-weight:850;" if ("PUSH" in str(value) or "NO BET" in str(value)) else "color:#9fb3c6;font-weight:800;",
                        subset=[result_col],
                    )
            st.dataframe(styled, hide_index=True, width="stretch")
            st.caption("Green = frozen projection · Blue = model-supported K target · Gold = resolved MLB result. K Result grades the model-supported K ladder target. Outs/Hits Bet Result grades only a real line plus a side that was frozen before first pitch; legacy/post-start lines remain UNGRADABLE, and PASS remains NO BET.")

st.divider()
if st.button("Resolve completed games", type="primary"):
    with st.spinner("Checking MLB results and attaching completed pitcher outcomes..."):
        try:
            resolve_projection_log()
            st.success("Completed-game resolution finished. History refreshed below.")
        except Exception as exc:
            st.error(f"Could not resolve completed projection outcomes: {exc}")


k_resolved = df["actual_strikeouts"].notna()
k_ready = k_resolved & df["k_range_low"].notna() & df["k_range_high"].notna()
k_hit = k_ready & (df["actual_strikeouts"] >= df["k_range_low"]) & (df["actual_strikeouts"] <= df["k_range_high"])

h_resolved = df["actual_hits_allowed"].notna()
h_ready = h_resolved & df["hits_range_low"].notna() & df["hits_range_high"].notna()
h_hit = h_ready & (df["actual_hits_allowed"] >= df["hits_range_low"]) & (df["actual_hits_allowed"] <= df["hits_range_high"])

o_resolved = df["actual_outs"].notna()
o_ready = o_resolved & df["outs_range_low"].notna() & df["outs_range_high"].notna()
o_hit = o_ready & (df["actual_outs"] >= df["outs_range_low"]) & (df["actual_outs"] <= df["outs_range_high"])

st.markdown('<div class="history-secondary-zone">Automatic Evidence + Model Diagnostics</div>', unsafe_allow_html=True)
st.markdown('<div class="history-kicker">Evidence performance scoreboard</div>', unsafe_allow_html=True)
resolved_any_count = int((k_resolved | h_resolved | o_resolved).sum())
k_ready_count, h_ready_count, o_ready_count = int(k_ready.sum()), int(h_ready.sum()), int(o_ready.sum())
k_hit_count, h_hit_count, o_hit_count = int(k_hit.sum()), int(h_hit.sum()), int(o_hit.sum())
k_hit_rate = float(k_hit_count / k_ready_count) if k_ready_count else None
h_hit_rate = float(h_hit_count / h_ready_count) if h_ready_count else None
o_hit_rate = float(o_hit_count / o_ready_count) if o_ready_count else None

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Automatic evidence rows", len(df), help=metric_help("history_evidence_rows", current=f"{len(df)} frozen evidence row(s) loaded"))
col2.metric("Resolved games", resolved_any_count, help=metric_help("history_resolved_games", current=f"{resolved_any_count}/{len(df)} evidence row(s) have at least one final MLB stat"))
col3.metric("K intervals covered", k_hit_count, help=metric_help("history_k_range_hits", current=f"{k_hit_count}/{k_ready_count} eligible K intervals contained the final Ks"))
col4.metric("K coverage rate", f"{k_hit_rate:.1%}" if k_hit_rate is not None else "—", help=metric_help("history_k_hit_rate", current=(f"{k_hit_count}/{k_ready_count} = {k_hit_rate:.1%}" if k_hit_rate is not None else "No eligible resolved K intervals yet")))
col5.metric("Hits intervals covered", h_hit_count, help=metric_help("history_hits_range_hits", current=f"{h_hit_count}/{h_ready_count} eligible Hits intervals contained the final result"))
col6.metric("Hits coverage rate", f"{h_hit_rate:.1%}" if h_hit_rate is not None else "—", help=metric_help("history_hits_hit_rate", current=(f"{h_hit_count}/{h_ready_count} = {h_hit_rate:.1%}" if h_hit_rate is not None else "No eligible resolved Hits intervals yet")))

outs_metrics1, outs_metrics2 = st.columns(2)
outs_metrics1.metric("Outs intervals covered", o_hit_count, help=metric_help("history_outs_range_hits", current=f"{o_hit_count}/{o_ready_count} eligible Outs intervals contained the final result"))
outs_metrics2.metric("Outs coverage rate", f"{o_hit_rate:.1%}" if o_hit_rate is not None else "—", help=metric_help("history_outs_hit_rate", current=(f"{o_hit_count}/{o_ready_count} = {o_hit_rate:.1%}" if o_hit_rate is not None else "No eligible resolved Outs intervals yet")))

mae1, mae2, mae3 = st.columns(3)
k_mae_value = h_mae_value = o_mae_value = None
k_mae_n = h_mae_n = o_mae_n = 0
if k_resolved.any():
    k_error = df.loc[k_resolved, "actual_strikeouts"] - df.loc[k_resolved, "projection"]
    k_valid_error = k_error.dropna()
    k_mae_n = int(len(k_valid_error))
    k_mae_value = float(k_valid_error.abs().mean()) if k_mae_n else None
mae1.metric("Strikeout MAE", f"{k_mae_value:.2f} K" if k_mae_value is not None else "—", help=metric_help("history_k_mae", current=(f"{k_mae_value:.2f} K average absolute miss across {k_mae_n} valid pair(s)" if k_mae_value is not None else "No valid resolved K pairs yet")))

if h_resolved.any() and df.loc[h_resolved, "hits_projection"].notna().any():
    h_mask = h_resolved & df["hits_projection"].notna()
    h_error = df.loc[h_mask, "actual_hits_allowed"] - df.loc[h_mask, "hits_projection"]
    h_valid_error = h_error.dropna()
    h_mae_n = int(len(h_valid_error))
    h_mae_value = float(h_valid_error.abs().mean()) if h_mae_n else None
mae2.metric("Hits Allowed MAE", f"{h_mae_value:.2f} H" if h_mae_value is not None else "—", help=metric_help("history_hits_mae", current=(f"{h_mae_value:.2f} H average absolute miss across {h_mae_n} valid pair(s)" if h_mae_value is not None else "No valid resolved Hits pairs yet")))

if o_resolved.any() and df.loc[o_resolved, "outs_projection"].notna().any():
    o_mask = o_resolved & df["outs_projection"].notna()
    o_error = df.loc[o_mask, "actual_outs"] - df.loc[o_mask, "outs_projection"]
    o_valid_error = o_error.dropna()
    o_mae_n = int(len(o_valid_error))
    o_mae_value = float(o_valid_error.abs().mean()) if o_mae_n else None
mae3.metric("Total Outs MAE", f"{o_mae_value:.2f} outs" if o_mae_value is not None else "—", help=metric_help("history_outs_mae", current=(f"{o_mae_value:.2f} outs average absolute miss across {o_mae_n} valid pair(s)" if o_mae_value is not None else "No valid resolved Outs pairs yet")))

st.caption("ⓘ Every scorecard now has its own info icon. 80% range coverage means the final result landed inside that market's frozen pregame interval; it is not a sportsbook win/loss grade. MAE measures average miss size.")
explain_popover(
    Explanation(
        "Evidence performance scoreboard",
        "This block measures two different model-health questions: did the final result land inside the frozen uncertainty interval, and how far was the point projection from the final MLB result?",
        "Range hit rate = eligible final results inside the saved 10th–90th percentile interval ÷ all eligible resolved intervals for that market. MAE = mean absolute error = average of |final result − frozen point projection|, so over- and under-predictions cannot cancel each other out.",
        decision="Central 80% interval coverage should trend toward roughly 80% as the sample grows; 100% is not the goal. For MAE, lower is better. These are model-diagnostic conclusions, not sportsbook win/loss calls.",
        inputs=(
            "Frozen pregame point projections",
            "Frozen 10th–90th percentile range bounds",
            "Final MLB pitcher results attached by the resolver",
        ),
        current=(
            f"Evidence archive: {len(df)} rows · {resolved_any_count} have at least one resolved final stat",
            f"K coverage: {k_hit_count}/{k_ready_count} eligible intervals" + (f" = {k_hit_rate:.1%}" if k_hit_rate is not None else ""),
            f"Hits coverage: {h_hit_count}/{h_ready_count} eligible intervals" + (f" = {h_hit_rate:.1%}" if h_hit_rate is not None else ""),
            f"Outs coverage: {o_hit_count}/{o_ready_count} eligible intervals" + (f" = {o_hit_rate:.1%}" if o_hit_rate is not None else ""),
            f"Strikeout MAE: {'—' if k_mae_value is None else f'{k_mae_value:.2f} K'} across {k_mae_n} valid projection/result pairs",
            f"Hits Allowed MAE: {'—' if h_mae_value is None else f'{h_mae_value:.2f} H'} across {h_mae_n} valid projection/result pairs",
            f"Total Outs MAE: {'—' if o_mae_value is None else f'{o_mae_value:.2f} outs'} across {o_mae_n} valid projection/result pairs",
        ),
        note="Range coverage and MAE never retroactively change old projections or grade sportsbook bets.",
    ),
    label="ⓘ EXPLAIN EVIDENCE SCOREBOARD",
)

st.divider()
st.markdown('<div class="history-kicker">Actionable K results</div>', unsafe_allow_html=True)
st.subheader("🔥 Bettable K Wins & Crushers")
st.caption(
    "Archive K grading uses the highest whole-K ladder milestone fully supported by the frozen projection: floor(Projected K), within our 3+–12+ ladder. "
    "Example: 5.07 projects to a 5+ target, so 5 actual Ks = ✅ WIN. Exact projection error and 80% range coverage remain separate model diagnostics."
)
_bettable_ready = df["projection"].notna() & df["actual_strikeouts"].notna()
_bettable = df.loc[_bettable_ready].copy()
_bettable["K Target Value"] = pd.to_numeric(_bettable["projection"], errors="coerce").map(bettable_k_target)
_bettable = _bettable.loc[_bettable["K Target Value"].notna()].copy()
if _bettable.empty:
    st.info("Bettable K wins will appear as supported 3+–12+ frozen projections resolve.")
else:
    _bettable["K Target"] = _bettable["projection"].map(bettable_k_label)
    _bettable["K vs Target"] = pd.to_numeric(_bettable["actual_strikeouts"], errors="coerce") - pd.to_numeric(_bettable["K Target Value"], errors="coerce")
    _bettable["K Result"] = _bettable.apply(lambda r: bettable_k_result(r.get("projection"), r.get("actual_strikeouts")), axis=1)
    _wins = int(_bettable["K Result"].eq("✅ WIN").sum())
    _win_rate = float(_wins / len(_bettable)) if len(_bettable) else float("nan")
    _crushers = crusher_report(df)
    _crusher_count = int(_crushers["Crusher Status"].eq("🔥 CRUSHER").sum()) if not _crushers.empty else 0
    kw1, kw2, kw3, kw4 = st.columns(4)
    kw1.metric("Resolved ladder calls", len(_bettable), help=metric_help("history_ladder_calls", current=f"{len(_bettable)} valid resolved whole-K target call(s)"))
    kw2.metric("Ladder wins", _wins, help=metric_help("history_ladder_wins", current=f"{_wins}/{len(_bettable)} resolved ladder call(s) reached target"))
    kw3.metric("Ladder win rate", f"{_win_rate:.1%}", help=metric_help("history_ladder_win_rate", current=f"{_wins}/{len(_bettable)} = {_win_rate:.1%}"))
    kw4.metric("Consistent crushers", _crusher_count, help=metric_help("history_crushers", current=f"{_crusher_count} pitcher(s) currently meet the existing Crusher tracking rule"))
    explain_popover(Explanation("Bettable K Wins & Crushers","This block grades the model-supported whole-K milestone derived from each frozen strikeout projection and identifies pitchers who have repeatedly cleared those targets.","K Target is floor(Projected K) inside the supported 3+–12+ ladder. Crushers require the existing minimum resolved-call count, win-rate threshold and average margin above target.",note="This is descriptive model tracking. It does not retroactively change old projections or create a new live ranking rule."),label="ⓘ EXPLAIN K RESULTS")

    high_calls = _bettable.loc[_bettable.get("confidence", pd.Series(index=_bettable.index, dtype=str)).astype(str).str.upper().eq("HIGH")].copy()
    if not high_calls.empty:
        st.markdown("#### High-confidence ladder calls")
        high_calls = high_calls.sort_values(["game_date", "captured_at_utc"], ascending=[False, False]).head(30)
        high_view = high_calls[["player", "projection", "K Target", "actual_strikeouts", "K vs Target", "K Result"]].copy()
        high_view = high_view.rename(columns={"player":"Pitcher", "projection":"Projection", "actual_strikeouts":"Actual"})
        high_styled = high_view.style.format({"Projection":"{:.2f}", "Actual":"{:.0f}", "K vs Target":"{:+.0f}"}, na_rep="—")
        high_styled = high_styled.map(lambda _: "color:#22c55e;font-weight:800;", subset=["Projection"])
        high_styled = high_styled.map(lambda _: "color:#38bdf8;font-weight:800;", subset=["K Target"])
        high_styled = high_styled.map(lambda _: "color:#facc15;font-weight:800;", subset=["Actual"])
        st.dataframe(high_styled, hide_index=True, width="stretch")

    st.markdown("#### Projection Crushers")
    if _crushers.empty:
        st.info("Crusher tracking will populate as current starter-only K ladder calls resolve.")
    else:
        crusher_view = _crushers.copy()
        for col in ["Win Rate", "Recent 5 Win Rate"]:
            crusher_view[col] = crusher_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")
        for col in ["Avg K Above Target", "Avg Win Margin", "Total K Above Target"]:
            crusher_view[col] = crusher_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.2f}")
        st.dataframe(crusher_view, hide_index=True, width="stretch")
        st.caption("🔥 CRUSHER requires at least 3 resolved current-model ladder calls, a win rate of at least 66.7%, and average actual Ks more than 0.5 above the bettable target. This board is descriptive tracking only.")

st.divider()
st.markdown('<div class="history-kicker">Learning diagnostics</div>', unsafe_allow_html=True)
st.subheader("🧠 Current model learning status")
current_mask = df["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)
current = df.loc[current_mask].copy()
current_resolved = current.loc[
    current["actual_strikeouts"].notna() | current["actual_hits_allowed"].notna() | current["actual_outs"].notna()
].copy()

k_cal = milestone_calibration_report(df)
h_cal = hits_calibration_report(df)
o_cal = outs_calibration_report(df)

k5_obs = int(k_cal.loc[k_cal["Line"].eq("5+"), "Observations"].iloc[0]) if not k_cal.empty and k_cal["Line"].eq("5+").any() else 0
h55_obs = int(h_cal.loc[pd.to_numeric(h_cal["Line"], errors="coerce").eq(5.5), "Observations"].iloc[0]) if not h_cal.empty and pd.to_numeric(h_cal["Line"], errors="coerce").eq(5.5).any() else 0
o155_obs = int(o_cal.loc[pd.to_numeric(o_cal["Line"], errors="coerce").eq(15.5), "Observations"].iloc[0]) if not o_cal.empty and pd.to_numeric(o_cal["Line"], errors="coerce").eq(15.5).any() else 0

learn1, learn2, learn3, learn4 = st.columns(4)
learn1.metric("Starter-only resolved", len(current_resolved))
learn2.metric("5+ K calibration rows", f"{k5_obs}/30")
learn3.metric("O5.5 Hits calibration rows", f"{h55_obs}/30")
learn4.metric("O15.5 Outs calibration rows", f"{o155_obs}/30")
explain_popover(static_explanation("history_learning"),label="ⓘ EXPLAIN LEARNING STATUS")
st.caption(
    f"Only starter-only model rows tagged {HISTORY_SEMANTICS} feed these learning diagnostics. "
    "Each SIM/MATH blend stays at the protected 50/50 baseline until that exact line has at least 30 compatible resolved observations."
)

with st.expander("Strikeout calibration by milestone"):
    st.dataframe(k_cal, hide_index=True, width="stretch")
with st.expander("Hits Allowed calibration by line"):
    st.dataframe(h_cal, hide_index=True, width="stretch")
with st.expander("Total Outs calibration by line"):
    st.dataframe(o_cal, hide_index=True, width="stretch")

rolling = rolling_learning_frame(df)
if rolling.empty or len(current_resolved) < 3:
    st.info("Rolling current-model accuracy will appear after at least 3 starter-only projections resolve.")
else:
    st.markdown(f"#### Recent accuracy — rolling {ROLLING_WINDOW} starter projections")
    mae_cols = ["K Rolling MAE", "Hits Rolling MAE", "Outs Rolling MAE"]
    hit_cols = ["K Rolling Range Hit Rate", "Hits Rolling Range Hit Rate", "Outs Rolling Range Hit Rate"]
    latest_mae = rolling[mae_cols].dropna(how="all")
    latest_hit = rolling[hit_cols].dropna(how="all")

    m1, m2, m3 = st.columns(3)
    for metric, widget, suffix in (
        ("K Rolling MAE", m1, " K"),
        ("Hits Rolling MAE", m2, " H"),
        ("Outs Rolling MAE", m3, " outs"),
    ):
        values = rolling[metric].dropna()
        widget.metric(f"Recent {metric.replace(' Rolling', '')}", f"{float(values.iloc[-1]):.2f}{suffix}" if not values.empty else "—")

    chart_mae = rolling.set_index("Resolved Start #")[mae_cols].dropna(how="all")
    if not chart_mae.empty:
        st.line_chart(chart_mae)

    chart_hit = rolling.set_index("Resolved Start #")[hit_cols].dropna(how="all")
    if not chart_hit.empty:
        st.caption("Rolling frozen 80% range hit rate. A healthy 80% interval should eventually land near its nominal coverage, not necessarily 100%.")
        st.line_chart(chart_hit)

st.divider()
st.subheader("⚙️ Workload intelligence audit")
explain_popover(Explanation("Workload intelligence audit","This checks whether the pregame workload forecast is accurately estimating the pitch count, batters faced and outs opportunities that drive starter projections.","Frozen expected workload values are compared with later actual MLB BF/pitches/outs using compatible starter-only rows. The audit is separate from sportsbook results."),label="ⓘ EXPLAIN WORKLOAD AUDIT")
st.caption(
    "workload-v1 estimates expected pitches, batters faced, and outs from starter-only pitch/BF/outs history, efficiency, recent trend, and conservative short-rest handling. "
    "Sportsbook data is excluded. Actual BF and pitch count are resolved after games so the exposure model can be validated directly."
)
if "workload_version" not in df.columns:
    st.info("Workload tracking begins with app version 3.7.0; older snapshots remain visible but untagged.")
else:
    workload_rows = df.loc[df["workload_version"].astype(str).eq("workload-v1")].copy()
    if workload_rows.empty:
        st.info("No workload-v1 snapshots have been captured yet.")
    else:
        expected_pitches = pd.to_numeric(workload_rows.get("expected_pitches"), errors="coerce")
        actual_pitches = pd.to_numeric(workload_rows.get("actual_pitches"), errors="coerce")
        expected_bf = pd.to_numeric(workload_rows.get("expected_bf"), errors="coerce")
        actual_bf = pd.to_numeric(workload_rows.get("actual_batters_faced"), errors="coerce")
        expected_outs = pd.to_numeric(workload_rows.get("expected_outs"), errors="coerce")
        actual_outs_w = pd.to_numeric(workload_rows.get("actual_outs"), errors="coerce")
        pitch_ready = expected_pitches.notna() & actual_pitches.notna()
        bf_ready = expected_bf.notna() & actual_bf.notna()
        outs_ready_w = expected_outs.notna() & actual_outs_w.notna()
        wa1,wa2,wa3,wa4 = st.columns(4)
        wa1.metric("workload-v1 snapshots", len(workload_rows), help=metric_help("history_workload_snapshots", current=f"{len(workload_rows)} workload-v1 snapshot row(s)"))
        wa2.metric("Pitch-count MAE", "—" if not pitch_ready.any() else f"{float((actual_pitches[pitch_ready]-expected_pitches[pitch_ready]).abs().mean()):.1f} pitches", help=metric_help("history_pitch_mae", current=f"{int(pitch_ready.sum())} valid expected/actual pitch pair(s)"))
        wa3.metric("BF MAE", "—" if not bf_ready.any() else f"{float((actual_bf[bf_ready]-expected_bf[bf_ready]).abs().mean()):.2f} BF", help=metric_help("history_bf_mae", current=f"{int(bf_ready.sum())} valid expected/actual BF pair(s)"))
        wa4.metric("Workload-outs MAE", "—" if not outs_ready_w.any() else f"{float((actual_outs_w[outs_ready_w]-expected_outs[outs_ready_w]).abs().mean()):.2f} outs", help=metric_help("history_workload_outs_mae", current=f"{int(outs_ready_w.sum())} valid expected/actual workload-outs pair(s)"))
        upgrades = pd.to_numeric(workload_rows.get("workload_projection_delta_k"), errors="coerce") if "workload_projection_delta_k" in workload_rows.columns else pd.Series(dtype=float)
        if upgrades.notna().any():
            st.caption(f"Pregame workload upgrades recorded: {int(upgrades.notna().sum())} · average K projection change {float(upgrades.dropna().mean()):+.2f} K. Started/finished snapshots are never rewritten.")
        audit_cols = [
            "game_date", "player", "expected_pitches", "actual_pitches", "expected_bf", "actual_batters_faced",
            "expected_outs", "actual_outs", "pitches_per_bf", "days_since_last_start", "leash_label", "pitch_trend",
        ]
        audit_cols = [col for col in audit_cols if col in workload_rows.columns]
        audit = workload_rows[audit_cols].sort_values("game_date", ascending=False).head(80).copy()
        st.dataframe(audit, hide_index=True, width="stretch")

st.markdown("#### 🧪 Historical workload validation")
st.caption(
    "Leakage-safe MLB replay over pitchers already tracked by the app. Each 2026 target start is rebuilt from only earlier starter games, with 2025 allowed as prior-season carry. "
    "workload-v1 is compared against rolling-5 and season-to-date baselines, while workload-v2-bias-candidate learns a tightly capped correction from strictly earlier workload-v1 errors. "
    "Sportsbook data is excluded, and this report does not modify live projections. workload-v2 is REPORT ONLY / NOT LIVE and cannot change Ks, Hits, Outs, or Top Plays."
)
_workload_summary_path = ROOT / "data" / "workload_backtest_summary.csv"
_workload_segments_path = ROOT / "data" / "workload_backtest_segments.csv"
if not _workload_summary_path.exists():
    st.info("Historical workload validation has not been generated yet. Run the Historical Workload Validation workflow to create the report.")
else:
    try:
        _validation = pd.read_csv(_workload_summary_path)
    except Exception:
        _validation = pd.DataFrame()
    if _validation.empty:
        st.info("Historical workload validation report is currently empty.")
    else:
        _status = _validation.get("Status", pd.Series(index=_validation.index, dtype=str)).astype(str)
        _n = pd.to_numeric(_validation.get("Evaluated_Starts"), errors="coerce")
        _v1, _v2, _v3, _v4 = st.columns(4)
        _v1.metric("Validated workload targets", int(_n.fillna(0).sum()))
        _v2.metric("workload-v1 HELPING", int(_status.eq("HELPING").sum()))
        _v3.metric("workload-v1 MIXED", int(_status.eq("MIXED").sum()))
        _v4.metric("workload-v1 HURTING", int(_status.eq("HURTING").sum()))

        if "Candidate_Status" in _validation.columns:
            _candidate_status = _validation["Candidate_Status"].astype(str)
            _adjusted = pd.to_numeric(_validation.get("Candidate_Adjusted_Starts"), errors="coerce")
            _c1, _c2, _c3, _c4 = st.columns(4)
            _c1.metric("v2 adjusted target-starts", int(_adjusted.fillna(0).sum()))
            _c2.metric("v2 HELPING metrics", int(_candidate_status.eq("HELPING").sum()))
            _c3.metric("v2 MIXED metrics", int(_candidate_status.eq("MIXED").sum()))
            _c4.metric("v2 HURTING metrics", int(_candidate_status.eq("HURTING").sum()))

        _view = _validation.rename(columns={
            "Evaluated_Starts": "Evaluated Starts",
            "Workload_MAE": "Workload MAE",
            "Workload_RMSE": "Workload RMSE",
            "Workload_Bias": "Workload Bias",
            "Rolling5_MAE": "Rolling-5 MAE",
            "Rolling5_RMSE": "Rolling-5 RMSE",
            "Rolling5_Bias": "Rolling-5 Bias",
            "SeasonToDate_Starts": "Season-to-date Starts",
            "SeasonToDate_MAE": "Season-to-date MAE",
            "Relative_MAE_vs_Rolling5": "MAE Improvement vs Rolling-5",
            "Relative_MAE_vs_SeasonToDate": "MAE Improvement vs Season-to-date",
            "Workload_Win_Share_vs_Rolling5": "Win Share vs Rolling-5",
            "Candidate_Adjusted_Starts": "v2 Adjusted Starts",
            "Candidate_MAE": "v2 MAE",
            "Candidate_RMSE": "v2 RMSE",
            "Candidate_Bias": "v2 Bias",
            "Relative_MAE_vs_Workload": "v2 MAE Improvement vs v1",
            "Candidate_Win_Share_vs_Workload": "v2 Win Share vs v1",
            "Candidate_Status": "v2 Status",
        }).copy()
        for col in ["MAE Improvement vs Rolling-5", "MAE Improvement vs Season-to-date", "Win Share vs Rolling-5", "v2 MAE Improvement vs v1", "v2 Win Share vs v1"]:
            if col in _view.columns:
                _view[col] = _view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if "Improvement" in col else f"{float(x):.1%}")
        for col in ["Workload MAE", "Workload RMSE", "Workload Bias", "Rolling-5 MAE", "Rolling-5 RMSE", "Rolling-5 Bias", "Season-to-date MAE", "v2 MAE", "v2 RMSE", "v2 Bias"]:
            if col in _view.columns:
                _view[col] = _view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.3f}" if "Bias" in col else f"{float(x):.3f}")
        st.dataframe(_view, hide_index=True, width="stretch")
        st.caption(
            "Status stays LEARNING below 30 evaluated starts. workload-v1 HELPING requires at least 3% lower MAE than rolling-5 and a 52%+ individual-start win share. "
            "The v2 candidate is judged separately against workload-v1: it must lower MAE, reduce absolute bias, and win enough actually-adjusted starts. "
            "Candidate status is evidence only; workload-v2 remains REPORT ONLY / NOT LIVE until promotion is explicitly earned and implemented."
        )

        if _workload_segments_path.exists():
            try:
                _segments = pd.read_csv(_workload_segments_path)
            except Exception:
                _segments = pd.DataFrame()
            if not _segments.empty:
                with st.expander("Historical workload segments — descriptive", expanded=False):
                    _seg = _segments.copy()
                    for col in ["Relative MAE vs Rolling5", "Win Share vs Rolling5", "Candidate MAE Improvement vs Workload", "Candidate Win Share vs Workload"]:
                        if col in _seg.columns:
                            _seg[col] = _seg[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if "Relative" in col else f"{float(x):.1%}")
                    for col in ["Workload MAE", "Candidate MAE", "Rolling5 MAE"]:
                        if col in _seg.columns:
                            _seg[col] = _seg[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")
                    st.dataframe(_seg, hide_index=True, width="stretch")
                    st.caption("Segments only appear with at least 15 evaluated starts. They are diagnostic slices, not automatic adjustment rules. Any v2 segment gains or losses remain report-only evidence.")

st.divider()
st.subheader("🧾 Lineup input audit")
st.caption("Confirmed-lineup and active-roster rows stay separately tagged so we can measure whether posted batting orders improve the baseball forecast. Pregame upgrades also retain the old K projection and the lineup-driven delta.")
if "lineup_source" not in df.columns:
    st.info("Lineup-source tracking begins with app version 3.6.0; older rows remain untagged.")
else:
    lineup_audit = df.copy()
    lineup_audit["lineup_source"] = lineup_audit["lineup_source"].fillna("LEGACY/UNKNOWN").astype(str)
    lineup_audit["k_abs_error"] = (pd.to_numeric(lineup_audit.get("actual_strikeouts"), errors="coerce") - pd.to_numeric(lineup_audit.get("projection"), errors="coerce")).abs()
    lineup_audit["hits_abs_error"] = (pd.to_numeric(lineup_audit.get("actual_hits_allowed"), errors="coerce") - pd.to_numeric(lineup_audit.get("hits_projection"), errors="coerce")).abs()
    audit_rows = []
    for source, group in lineup_audit.groupby("lineup_source", dropna=False):
        resolved_k = group["k_abs_error"].dropna()
        resolved_h = group["hits_abs_error"].dropna()
        deltas = pd.to_numeric(group.get("lineup_projection_delta"), errors="coerce").dropna() if "lineup_projection_delta" in group.columns else pd.Series(dtype=float)
        audit_rows.append({
            "Lineup Source": source,
            "Snapshots": int(len(group)),
            "Resolved K": int(len(resolved_k)),
            "K MAE": None if resolved_k.empty else float(resolved_k.mean()),
            "Resolved Hits": int(len(resolved_h)),
            "Hits MAE": None if resolved_h.empty else float(resolved_h.mean()),
            "Pregame Upgrades": int(len(deltas)),
            "Avg K Projection Delta": None if deltas.empty else float(deltas.mean()),
        })
    audit = pd.DataFrame(audit_rows)
    st.dataframe(audit, hide_index=True, width="stretch")

st.divider()
st.subheader("🧪 Signal accountability")
st.caption(
    "Paired upgrade evidence compares the same pitcher/game before and after a pregame feature upgrade, then grades both predictions against the same final result. "
    "That is stronger evidence than comparing unrelated pitcher groups. Sportsbook odds, saved bets, and market prices are excluded. Signals stay LEARNING below 20 resolved pairs."
)
paired_signals = paired_signal_report(df)
if paired_signals.empty:
    st.info("Signal accountability will populate as paired pregame upgrades resolve.")
else:
    helping = int(paired_signals["Status"].eq("HELPING").sum())
    hurting = int(paired_signals["Status"].eq("HURTING").sum())
    learning = int(paired_signals["Status"].eq("LEARNING").sum())
    paired_outcomes = int(pd.to_numeric(paired_signals["Resolved Pairs"], errors="coerce").fillna(0).sum())
    s1,s2,s3,s4 = st.columns(4)
    s1.metric("Paired market outcomes", paired_outcomes, help=metric_help("history_paired_outcomes", current=f"{paired_outcomes} resolved before/after pair(s) across candidate signals"))
    s2.metric("Helping signals", helping, help=metric_help("history_helping_signals", current=f"{helping} paired signal(s) currently meet HELPING"))
    s3.metric("Hurting signals", hurting, help=metric_help("history_hurting_signals", current=f"{hurting} paired signal(s) currently meet HURTING"))
    s4.metric("Still learning", learning, help=metric_help("history_learning_signals", current=f"{learning} paired signal(s) still need more evidence"))
    signal_view = paired_signals.copy()
    for col in ["Relative MAE Improvement", "Improved Share"]:
        signal_view[col] = signal_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if col == "Relative MAE Improvement" else f"{float(x):.1%}")
    for col in ["Pre MAE", "Post MAE", "MAE Improvement", "Pre Bias", "Post Bias"]:
        signal_view[col] = signal_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.3f}" if col in {"MAE Improvement", "Pre Bias", "Post Bias"} else f"{float(x):.3f}")
    st.dataframe(signal_view, hide_index=True, width="stretch")
    st.caption("HELPING requires at least 20 resolved pairs, at least 5% lower post-upgrade MAE, and improvement in at least 55% of paired starts. HURTING uses the symmetric downside guardrail. These labels do not alter Top Plays yet.")

st.markdown("#### 🧭 Team leash candidate · workload backtest")
st.caption(
    "Team/organization starter usage is reconstructed chronologically from resolved frozen starts. For each evaluated game, the candidate adjustment can use only earlier game dates. "
    "It compares candidate pitches/BF/outs against the existing workload-v1 baseline, but remains CONTEXT ONLY and does not change the baseball forecast."
)
team_leash_report = team_leash_walk_forward_report(df, load_observation_history())
if team_leash_report.empty:
    st.info("Team leash validation is waiting for workload-v1 snapshots with resolved workload outcomes.")
else:
    team_view = team_leash_report.copy()
    for col in ["Relative MAE Improvement", "Improved Share"]:
        team_view[col] = team_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if col == "Relative MAE Improvement" else f"{float(x):.1%}")
    for col in ["Baseline MAE", "Candidate MAE", "MAE Improvement", "Baseline Bias", "Candidate Bias"]:
        team_view[col] = team_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.3f}" if col in {"MAE Improvement", "Baseline Bias", "Candidate Bias"} else f"{float(x):.3f}")
    st.dataframe(team_view, hide_index=True, width="stretch")
    st.caption("Team leash needs 12 prior team starts before a candidate adjustment is evaluated, then 20 leakage-safe evaluated starts before HELPING/MIXED/HURTING can be assigned. Until we explicitly promote it later, it has zero projection or Top Plays influence.")

with st.expander("Context performance — descriptive, not causal", expanded=False):
    context_report = context_performance_report(df)
    if context_report.empty:
        st.info("Context buckets will populate as current starter-only snapshots resolve.")
    else:
        context_view = context_report.copy()
        context_view["80% Range Coverage"] = context_view["80% Range Coverage"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")
        context_view["MAE"] = context_view["MAE"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")
        context_view["Bias"] = context_view["Bias"].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.3f}")
        st.dataframe(context_view, hide_index=True, width="stretch")
        st.caption("Lineup, workload, rest, history source, opponent K/contact environments are model inputs. Team Leash Candidate is CONTEXT ONLY and does not modify the baseball forecast. Weather Delay Risk is labeled CONTEXT ONLY because weather still does not modify the baseball forecast.")

st.divider()
st.subheader("🚦 Walk-forward Top 5 model health")
st.caption(
    "Leakage-safe replay: each historical slate is rebuilt from its frozen pregame snapshots while calibration can only use earlier game dates. "
    "Same-day/future results and sportsbook prices are excluded. LEARNING and WATCH markets remain eligible; only BLOCKED markets are removed from Top Plays."
)
walk_forward = walk_forward_top5(df)
health_report = health_from_walk_forward(walk_forward)
settled_walk = walk_forward.loc[walk_forward.get("Hit", pd.Series(index=walk_forward.index, dtype=object)).notna()].copy() if not walk_forward.empty else pd.DataFrame()
all_health = health_report.loc[health_report["Market"].eq("ALL TOP 5")].iloc[0] if not health_report.empty and health_report["Market"].eq("ALL TOP 5").any() else None
blocked_count = int((health_report.loc[health_report["Market"].ne("ALL TOP 5"), "Status"] == "BLOCKED").sum()) if not health_report.empty else 0

wf1, wf2, wf3, wf4 = st.columns(4)
wf1.metric("Settled walk-forward Top 5 legs", len(settled_walk))
wf2.metric("Historical Top 5 hit rate", "—" if all_health is None or pd.isna(all_health["Hit Rate"]) else f"{float(all_health['Hit Rate']):.1%}")
wf3.metric("Avg predicted probability", "—" if all_health is None or pd.isna(all_health["Avg Model Probability"]) else f"{float(all_health['Avg Model Probability']):.1%}")
wf4.metric("Markets currently blocked", blocked_count)

health_view = health_report.copy()
if not health_view.empty:
    for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Recent Hit Rate", "Recent Avg Probability", "Recent Calibration Gap"]:
        health_view[col] = health_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")
    health_view["Brier Score"] = health_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")
    st.dataframe(health_view, hide_index=True, width="stretch")
    st.caption("Health guard activates after 30 settled walk-forward Top 5 legs for that market. Until then the status is LEARNING and the market remains eligible.")

with st.expander("Probability reliability — walk-forward Top 5"):
    reliability = reliability_table(walk_forward)
    if reliability.empty:
        st.info("Reliability buckets will populate as starter-only Top 5 legs resolve.")
    else:
        reliability_view = reliability.copy()
        for col in ["Avg Model Probability", "Observed Hit Rate", "Calibration Gap"]:
            reliability_view[col] = reliability_view[col].map(lambda x: f"{float(x):.1%}")
        st.dataframe(reliability_view, hide_index=True, width="stretch")

with st.expander("Daily historical Top 5 replay"):
    daily = daily_top5_summary(walk_forward)
    if daily.empty:
        st.info("Daily Top 5 replay will populate after current starter-only recommendations resolve.")
    else:
        daily_view = daily.sort_values("Date", ascending=False).head(60).copy()
        daily_view["Hit Rate"] = daily_view["Hit Rate"].map(lambda x: f"{float(x):.1%}")
        daily_view["Avg Model Probability"] = daily_view["Avg Model Probability"].map(lambda x: f"{float(x):.1%}")
        daily_view["Brier Score"] = daily_view["Brier Score"].map(lambda x: f"{float(x):.3f}")
        daily_view["5/5 Sweep"] = daily_view["5/5 Sweep"].map(lambda x: "👑 YES" if bool(x) else "—")
        st.dataframe(daily_view, hide_index=True, width="stretch")

st.divider()
st.subheader("🎯 Decision-learning tiers")
st.caption(
    "This layer studies settled leakage-safe Top 5 legs by market + model-probability band + data-quality band. "
    "Sportsbook odds, sportsbook edge, book choice, and saved bet selections are excluded. These labels are descriptive evidence only and do not change Top 5 ranking."
)
decision_report = decision_tier_report(walk_forward)
if decision_report.empty:
    st.info("Decision-learning segments will populate as current starter-only Top 5 legs settle.")
else:
    decision_settled = int(pd.to_numeric(decision_report["Settled Legs"], errors="coerce").fillna(0).sum())
    decision_supported = int(decision_report["Decision Evidence"].isin(["SUPPORTED", "STRONG EVIDENCE"]).sum())
    decision_strong = int(decision_report["Decision Evidence"].eq("STRONG EVIDENCE").sum())
    decision_under = int(decision_report["Decision Evidence"].eq("UNDERPERFORMING").sum())
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Settled decision legs", decision_settled)
    d2.metric("Supported segments", decision_supported)
    d3.metric("Strong-evidence segments", decision_strong)
    d4.metric("Underperforming segments", decision_under)

    decision_view = decision_report.copy()
    for col in ["Hit Rate", "Avg Model Probability", "Calibration Gap", "Wilson Lower 95%", "Lift vs Top 5"]:
        decision_view[col] = decision_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")
    decision_view["Brier Score"] = decision_view["Brier Score"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")
    st.dataframe(decision_view, hide_index=True, width="stretch")
    st.caption(
        "An exact segment stays LEARNING until it has 20 settled walk-forward legs. STRONG EVIDENCE and UNDERPERFORMING require at least 30, preventing tiny samples from driving decisions."
    )

st.divider()
st.markdown('<div class="history-kicker">Automatic model evidence</div>', unsafe_allow_html=True)
st.subheader("🧪 Automatic Evidence Log")
st.caption("This lower log is populated by scheduled background capture for calibration and diagnostics, so today can appear here even if you never manually ran or archived the slate.")
# Automatic model evidence remains the frozen projection log, with the durable
# manual execution overlay joined only for reporting. Execution lines/sides do
# not feed calibration, model training, or the frozen baseball projection.
_execution_source = user_archive.drop(columns=["_archive_date"], errors="ignore").copy() if not user_archive.empty else df.copy()
display = _execution_source.sort_values(["game_date", "captured_at_utc"], ascending=[False, False]).copy()
for _col in ("manual_outs_line", "manual_hits_allowed_line"):
    if _col in display.columns:
        display[_col] = pd.to_numeric(display[_col], errors="coerce")
for _col in ("manual_outs_side", "manual_hits_allowed_side"):
    if _col not in display.columns:
        display[_col] = ""
display["outs_bet_result"] = display.apply(
    lambda r: grade_frozen_execution(r.get("manual_outs_side"), r.get("manual_outs_line"), r.get("actual_outs")), axis=1
)
display["hits_bet_result"] = display.apply(
    lambda r: grade_frozen_execution(r.get("manual_hits_allowed_side"), r.get("manual_hits_allowed_line"), r.get("actual_hits_allowed")), axis=1
)
display["status"] = display.apply(
    lambda r: "Resolved" if pd.notna(r.get("actual_strikeouts")) or pd.notna(r.get("actual_hits_allowed")) or pd.notna(r.get("actual_outs")) else "Pending",
    axis=1,
)
display["k_error"] = display.apply(
    lambda r: r["actual_strikeouts"] - r["projection"] if pd.notna(r.get("actual_strikeouts")) and pd.notna(r.get("projection")) else None,
    axis=1,
)
display["hits_error"] = display.apply(
    lambda r: r["actual_hits_allowed"] - r["hits_projection"] if pd.notna(r.get("actual_hits_allowed")) and pd.notna(r.get("hits_projection")) else None,
    axis=1,
)
display["outs_error"] = display.apply(
    lambda r: r["actual_outs"] - r["outs_projection"] if pd.notna(r.get("actual_outs")) and pd.notna(r.get("outs_projection")) else None,
    axis=1,
)
display["k_bettable_target_value"] = display["projection"].map(bettable_k_target)
display["k_bettable_target"] = display["projection"].map(bettable_k_label)
display["k_target_margin"] = display.apply(
    lambda r: r["actual_strikeouts"] - r["k_bettable_target_value"] if pd.notna(r.get("actual_strikeouts")) and pd.notna(r.get("k_bettable_target_value")) else None,
    axis=1,
)
display["k_bettable_result"] = display.apply(lambda r: bettable_k_result(r.get("projection"), r.get("actual_strikeouts")), axis=1)
display["k_range_result"] = display.apply(lambda r: range_result(r, "actual_strikeouts", "k_range_low", "k_range_high"), axis=1)
display["hits_result"] = display.apply(lambda r: range_result(r, "actual_hits_allowed", "hits_range_low", "hits_range_high"), axis=1)
display["outs_result"] = display.apply(lambda r: range_result(r, "actual_outs", "outs_range_low", "outs_range_high"), axis=1)

display_columns = [
    "game_date", "player", "team", "opponent",
    "projection", "k_bettable_target", "actual_strikeouts", "k_bettable_result", "k_target_margin", "k_error", "k_range_low", "k_range_high", "k_range_result",
    "hits_projection", "manual_hits_allowed_line", "manual_hits_allowed_side", "actual_hits_allowed", "hits_bet_result", "hits_error", "hits_range_low", "hits_range_high", "hits_result",
    "outs_projection", "manual_outs_line", "manual_outs_side", "actual_outs", "outs_bet_result", "outs_error", "outs_range_low", "outs_range_high", "outs_result",
    "confidence", "data_quality", "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games",
    "status", "history_semantics",
]
display_columns = [col for col in display_columns if col in display.columns]
archive_view = display[display_columns].copy()
# Normalize placeholder strings, then remove genuinely dead archive columns.
for col in archive_view.columns:
    if archive_view[col].dtype == object:
        cleaned = archive_view[col].astype(str).str.strip()
        empty_token = cleaned.str.lower().isin({"", "nan", "none", "null", "nat", "<na>"})
        archive_view.loc[empty_token, col] = pd.NA
archive_populated = [col for col in archive_view.columns if bool(archive_view[col].notna().any())]
archive_view = archive_view[archive_populated]

archive_formats = {}
for col in ["projection", "hits_projection", "outs_projection", "k_target_margin", "k_error", "hits_error", "outs_error"]:
    if col in archive_view.columns:
        archive_formats[col] = "{:+.2f}" if col.endswith("_error") else "{:+.0f}" if col == "k_target_margin" else "{:.2f}"
for col in ["actual_strikeouts", "actual_hits_allowed", "actual_outs", "k_range_low", "k_range_high", "hits_range_low", "hits_range_high", "outs_range_low", "outs_range_high", "starter_history_games", "starter_history_mlb_games", "starter_history_observation_games"]:
    if col in archive_view.columns:
        archive_formats[col] = "{:.0f}"
for col in ["manual_hits_allowed_line", "manual_outs_line"]:
    if col in archive_view.columns:
        archive_formats[col] = "{:.1f}"

archive_column_config = {
    "player": st.column_config.TextColumn("Pitcher"),
    "team": st.column_config.TextColumn("Team"),
    "opponent": st.column_config.TextColumn("Opp"),
    "starter_history_games": st.column_config.NumberColumn("Starts Used", format="%.0f"),
    "starter_history_source": st.column_config.TextColumn("History Source"),
    "starter_history_mlb_games": st.column_config.NumberColumn("MLB Starts", format="%.0f"),
    "starter_history_observation_games": st.column_config.NumberColumn("Observed Starts", format="%.0f"),
    "projection": st.column_config.NumberColumn("Projected K", format="%.2f"),
    "k_range_low": st.column_config.NumberColumn("80% K Low", format="%.0f"),
    "k_range_high": st.column_config.NumberColumn("80% K High", format="%.0f"),
    "actual_strikeouts": st.column_config.NumberColumn("Actual Ks", format="%.0f"),
    "k_bettable_target": st.column_config.TextColumn("K Target"),
    "k_bettable_result": st.column_config.TextColumn("K Result"),
    "k_target_margin": st.column_config.NumberColumn("Vs Target", format="%+.0f"),
    "k_range_result": st.column_config.TextColumn("80% K Range"),
    "k_error": st.column_config.NumberColumn("Vs Projection", format="%+.2f"),
    "hits_projection": st.column_config.NumberColumn("Projected Hits", format="%.2f"),
    "manual_hits_allowed_line": st.column_config.NumberColumn("Hits Line", format="%.1f"),
    "manual_hits_allowed_side": st.column_config.TextColumn("Hits Side"),
    "hits_bet_result": st.column_config.TextColumn("Hits Bet Result"),
    "hits_range_low": st.column_config.NumberColumn("80% H Low", format="%.0f"),
    "hits_range_high": st.column_config.NumberColumn("80% H High", format="%.0f"),
    "actual_hits_allowed": st.column_config.NumberColumn("Actual Hits", format="%.0f"),
    "hits_result": st.column_config.TextColumn("80% Hits Range"),
    "hits_error": st.column_config.NumberColumn("Hits Error", format="%+.2f"),
    "outs_projection": st.column_config.NumberColumn("Projected Outs", format="%.2f"),
    "manual_outs_line": st.column_config.NumberColumn("Outs Line", format="%.1f"),
    "manual_outs_side": st.column_config.TextColumn("Outs Side"),
    "outs_bet_result": st.column_config.TextColumn("Outs Bet Result"),
    "outs_range_low": st.column_config.NumberColumn("80% Outs Low", format="%.0f"),
    "outs_range_high": st.column_config.NumberColumn("80% Outs High", format="%.0f"),
    "actual_outs": st.column_config.NumberColumn("Actual Outs", format="%.0f"),
    "outs_result": st.column_config.TextColumn("80% Outs Range"),
    "outs_error": st.column_config.NumberColumn("Outs Error", format="%+.2f"),
    "history_semantics": st.column_config.TextColumn("History Model"),
}


def style_archive_group(group: pd.DataFrame):
    styled = group.style.format({col: fmt for col, fmt in archive_formats.items() if col in group.columns}, na_rep="—")
    projected_cols = [c for c in ["projection", "hits_projection", "outs_projection"] if c in group.columns]
    actual_cols = [c for c in ["actual_strikeouts", "actual_hits_allowed", "actual_outs"] if c in group.columns]
    target_cols = [c for c in ["k_bettable_target"] if c in group.columns]
    if projected_cols:
        styled = styled.map(lambda _: "color:#22c55e;font-weight:800;", subset=projected_cols)
    if actual_cols:
        styled = styled.map(lambda _: "color:#facc15;font-weight:800;", subset=actual_cols)
    if target_cols:
        styled = styled.map(lambda _: "color:#38bdf8;font-weight:800;", subset=target_cols)
    manual_line_cols = [c for c in ["manual_hits_allowed_line", "manual_outs_line"] if c in group.columns]
    if manual_line_cols:
        styled = styled.map(lambda value: "color:#ff9f1c;font-weight:850;background-color:rgba(255,159,28,.10);" if pd.notna(value) else "", subset=manual_line_cols)
    for result_col in ["hits_bet_result", "outs_bet_result"]:
        if result_col in group.columns:
            styled = styled.map(
                lambda value: "color:#22c55e;font-weight:900;" if "WIN" in str(value) else "color:#ff6379;font-weight:900;" if "LOSS" in str(value) else "color:#ffd166;font-weight:850;" if ("PUSH" in str(value) or "NO BET" in str(value)) else "color:#9fb3c6;font-weight:800;",
                subset=[result_col],
            )
    return styled


st.caption("Click a date to open that slate. Model diagnostics and execution evidence are intentionally separate: 80% K/Hits/Outs Range = frozen interval coverage; K Target/K Result = model-supported K ladder grading; Hits/Outs Line + Side + Bet Result = true execution history only when a real line and a certified pregame side exist. Eligible legacy manual lines can be leakage-safely recovered from their archived pregame timestamp/model snapshot; post-start or ambiguous rows remain UNGRADABLE. Execution evidence never feeds calibration or projection training. Empty None/null/NaN columns are hidden automatically.")
archive_view["_archive_date"] = pd.to_datetime(archive_view.get("game_date"), errors="coerce")
archive_view = archive_view.sort_values(["_archive_date", "player"], ascending=[False, True], na_position="last")
archive_dates = archive_view["_archive_date"].dt.date.drop_duplicates().tolist()
for archive_date in archive_dates:
    date_mask = archive_view["_archive_date"].dt.date.eq(archive_date)
    date_group = archive_view.loc[date_mask].copy()
    date_group = date_group.drop(columns=["game_date", "_archive_date"], errors="ignore")
    date_label = pd.Timestamp(archive_date).strftime("%B %-d, %Y")
    pitcher_count = len(date_group)
    with st.expander(f"📅 {date_label} · {pitcher_count} pitcher{'s' if pitcher_count != 1 else ''}", expanded=False):
        st.dataframe(
            style_archive_group(date_group),
            hide_index=True,
            width="stretch",
            column_config={key: value for key, value in archive_column_config.items() if key in date_group.columns},
        )

undated_group = archive_view.loc[archive_view["_archive_date"].isna()].copy()
if not undated_group.empty:
    undated_group = undated_group.drop(columns=["game_date", "_archive_date"], errors="ignore")
    with st.expander(f"📅 Unknown date · {len(undated_group)} pitcher{'s' if len(undated_group) != 1 else ''}", expanded=False):
        st.dataframe(
            style_archive_group(undated_group),
            hide_index=True,
            width="stretch",
            column_config={key: value for key, value in archive_column_config.items() if key in undated_group.columns},
        )

st.download_button(
    "Download projection history CSV",
    display.to_csv(index=False),
    file_name="projection_history.csv",
    mime="text/csv",
)

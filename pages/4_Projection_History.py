from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from automation.resolve_projection_log import main as resolve_projection_log
from engine.calibration import milestone_calibration_report
from engine.hits_calibration import hits_calibration_report
from engine.outs_calibration import outs_calibration_report
from engine.starter_history import HISTORY_SEMANTICS

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "projection_log.csv"
ROLLING_WINDOW = 20

st.set_page_config(page_title="Projection History", page_icon="📚", layout="wide")
st.markdown(
    """
    <style>
    .block-container { padding-top: 3.25rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("📚 Projection History")
st.caption(
    "Frozen pregame StrikeOut King 9000 projections, resolved against final MLB strikeouts, "
    "total outs, and hits allowed. Current learning diagnostics only use starter-only model rows."
)


def load_projection_history() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(LOG_PATH)
    except Exception:
        return pd.DataFrame()


def range_result(row: pd.Series, actual_col: str, low_col: str, high_col: str) -> str:
    if pd.isna(row.get(actual_col)):
        return "PENDING"
    if pd.isna(row.get(low_col)) or pd.isna(row.get(high_col)):
        return "RESOLVED"
    actual = float(row[actual_col])
    return "✅ HIT" if float(row[low_col]) <= actual <= float(row[high_col]) else "❌ MISS"


def rolling_learning_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    current = frame.loc[frame.get("history_semantics", pd.Series(index=frame.index, dtype=str)).astype(str).eq(HISTORY_SEMANTICS)].copy()
    if current.empty:
        return pd.DataFrame()

    current["game_date_dt"] = pd.to_datetime(current.get("game_date"), errors="coerce")
    current = current.sort_values(["game_date_dt", "captured_at_utc"], na_position="last").reset_index(drop=True)
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


if st.button("Resolve completed games", type="primary"):
    with st.spinner("Checking MLB results and attaching completed pitcher outcomes..."):
        try:
            resolve_projection_log()
            st.success("Completed-game resolution finished. History refreshed below.")
        except Exception as exc:
            st.error(f"Could not resolve completed projection outcomes: {exc}")


df = load_projection_history()
if df.empty:
    st.info("No archived projections yet. Use Daily Projection Run to capture the announced starter slate before first pitch.")
    st.stop()

numeric_cols = [
    "projection", "k_range_low", "k_range_high", "actual_strikeouts",
    "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed",
    "outs_projection", "outs_range_low", "outs_range_high", "actual_outs", "starter_history_games",
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

k_resolved = df["actual_strikeouts"].notna()
k_ready = k_resolved & df["k_range_low"].notna() & df["k_range_high"].notna()
k_hit = k_ready & (df["actual_strikeouts"] >= df["k_range_low"]) & (df["actual_strikeouts"] <= df["k_range_high"])

h_resolved = df["actual_hits_allowed"].notna()
h_ready = h_resolved & df["hits_range_low"].notna() & df["hits_range_high"].notna()
h_hit = h_ready & (df["actual_hits_allowed"] >= df["hits_range_low"]) & (df["actual_hits_allowed"] <= df["hits_range_high"])

o_resolved = df["actual_outs"].notna()
o_ready = o_resolved & df["outs_range_low"].notna() & df["outs_range_high"].notna()
o_hit = o_ready & (df["actual_outs"] >= df["outs_range_low"]) & (df["actual_outs"] <= df["outs_range_high"])

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Archived projections", len(df))
col2.metric("Resolved games", int((k_resolved | h_resolved | o_resolved).sum()))
col3.metric("K range hits", int(k_hit.sum()))
col4.metric("K hit rate", f"{float(k_hit.sum() / k_ready.sum()):.1%}" if k_ready.any() else "—")
col5.metric("Hits range hits", int(h_hit.sum()))
col6.metric("Hits hit rate", f"{float(h_hit.sum() / h_ready.sum()):.1%}" if h_ready.any() else "—")

outs_metrics1, outs_metrics2 = st.columns(2)
outs_metrics1.metric("Outs range hits", int(o_hit.sum()))
outs_metrics2.metric("Outs hit rate", f"{float(o_hit.sum() / o_ready.sum()):.1%}" if o_ready.any() else "—")

mae1, mae2, mae3 = st.columns(3)
if k_resolved.any():
    k_error = df.loc[k_resolved, "actual_strikeouts"] - df.loc[k_resolved, "projection"]
    mae1.metric("Strikeout MAE", f"{float(k_error.abs().mean()):.2f} K")
else:
    mae1.metric("Strikeout MAE", "—")
if h_resolved.any() and df.loc[h_resolved, "hits_projection"].notna().any():
    h_mask = h_resolved & df["hits_projection"].notna()
    h_error = df.loc[h_mask, "actual_hits_allowed"] - df.loc[h_mask, "hits_projection"]
    mae2.metric("Hits Allowed MAE", f"{float(h_error.abs().mean()):.2f} H")
else:
    mae2.metric("Hits Allowed MAE", "—")
if o_resolved.any() and df.loc[o_resolved, "outs_projection"].notna().any():
    o_mask = o_resolved & df["outs_projection"].notna()
    o_error = df.loc[o_mask, "actual_outs"] - df.loc[o_mask, "outs_projection"]
    mae3.metric("Total Outs MAE", f"{float(o_error.abs().mean()):.2f} outs")
else:
    mae3.metric("Total Outs MAE", "—")

st.caption("HIT means the final result landed inside that market's frozen pregame 80% range. MISS means it finished outside the archived range.")

st.divider()
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
st.caption(
    f"Only rows tagged {HISTORY_SEMANTICS} feed these learning diagnostics. "
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
st.subheader("📋 Projection archive")
display = df.sort_values(["game_date", "captured_at_utc"], ascending=[False, False]).copy()
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
display["k_result"] = display.apply(lambda r: range_result(r, "actual_strikeouts", "k_range_low", "k_range_high"), axis=1)
display["hits_result"] = display.apply(lambda r: range_result(r, "actual_hits_allowed", "hits_range_low", "hits_range_high"), axis=1)
display["outs_result"] = display.apply(lambda r: range_result(r, "actual_outs", "outs_range_low", "outs_range_high"), axis=1)

display_columns = [
    "game_date", "player", "team", "opponent", "starter_history_games",
    "projection", "k_range_low", "k_range_high", "actual_strikeouts", "k_result", "k_error",
    "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed", "hits_result", "hits_error",
    "outs_projection", "outs_range_low", "outs_range_high", "actual_outs", "outs_result", "outs_error",
    "status", "confidence", "data_quality", "history_semantics",
]
display_columns = [col for col in display_columns if col in display.columns]

st.dataframe(
    display[display_columns],
    hide_index=True,
    width="stretch",
    column_config={
        "game_date": st.column_config.TextColumn("Game Date"),
        "player": st.column_config.TextColumn("Pitcher"),
        "team": st.column_config.TextColumn("Team"),
        "opponent": st.column_config.TextColumn("Opp"),
        "starter_history_games": st.column_config.NumberColumn("Starts Used", format="%.0f"),
        "projection": st.column_config.NumberColumn("Projected K", format="%.2f"),
        "k_range_low": st.column_config.NumberColumn("80% K Low", format="%.0f"),
        "k_range_high": st.column_config.NumberColumn("80% K High", format="%.0f"),
        "actual_strikeouts": st.column_config.NumberColumn("Actual Ks", format="%.0f"),
        "k_result": st.column_config.TextColumn("K Result"),
        "k_error": st.column_config.NumberColumn("K Error", format="%+.2f"),
        "hits_projection": st.column_config.NumberColumn("Projected Hits", format="%.2f"),
        "hits_range_low": st.column_config.NumberColumn("80% H Low", format="%.0f"),
        "hits_range_high": st.column_config.NumberColumn("80% H High", format="%.0f"),
        "actual_hits_allowed": st.column_config.NumberColumn("Actual Hits", format="%.0f"),
        "hits_result": st.column_config.TextColumn("Hits Result"),
        "hits_error": st.column_config.NumberColumn("Hits Error", format="%+.2f"),
        "outs_projection": st.column_config.NumberColumn("Projected Outs", format="%.2f"),
        "outs_range_low": st.column_config.NumberColumn("80% Outs Low", format="%.0f"),
        "outs_range_high": st.column_config.NumberColumn("80% Outs High", format="%.0f"),
        "actual_outs": st.column_config.NumberColumn("Actual Outs", format="%.0f"),
        "outs_result": st.column_config.TextColumn("Outs Result"),
        "outs_error": st.column_config.NumberColumn("Outs Error", format="%+.2f"),
        "history_semantics": st.column_config.TextColumn("History Model"),
    },
)

st.download_button(
    "Download projection history CSV",
    display.to_csv(index=False),
    file_name="projection_history.csv",
    mime="text/csv",
)

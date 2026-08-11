from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from automation.resolve_projection_log import main as resolve_projection_log

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "projection_log.csv"

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
st.caption("Frozen pregame StrikeOut King 9000 projections, resolved against final MLB strikeouts, total outs, and hits allowed.")


def load_projection_history() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(LOG_PATH)
    except Exception:
        return pd.DataFrame()


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
    "outs_projection", "outs_range_low", "outs_range_high", "actual_outs",
]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

for col in ["actual_strikeouts", "k_range_low", "k_range_high", "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed", "outs_projection", "outs_range_low", "outs_range_high", "actual_outs"]:
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


def range_result(row: pd.Series, actual_col: str, low_col: str, high_col: str) -> str:
    if pd.isna(row.get(actual_col)):
        return "PENDING"
    if pd.isna(row.get(low_col)) or pd.isna(row.get(high_col)):
        return "RESOLVED"
    actual = float(row[actual_col])
    return "✅ HIT" if float(row[low_col]) <= actual <= float(row[high_col]) else "❌ MISS"


display["k_result"] = display.apply(lambda r: range_result(r, "actual_strikeouts", "k_range_low", "k_range_high"), axis=1)
display["hits_result"] = display.apply(lambda r: range_result(r, "actual_hits_allowed", "hits_range_low", "hits_range_high"), axis=1)
display["outs_result"] = display.apply(lambda r: range_result(r, "actual_outs", "outs_range_low", "outs_range_high"), axis=1)

display_columns = [
    "game_date", "player", "team", "opponent",
    "projection", "k_range_low", "k_range_high", "actual_strikeouts", "k_result", "k_error",
    "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed", "hits_result", "hits_error",
    "outs_projection", "outs_range_low", "outs_range_high", "actual_outs", "outs_result", "outs_error",
    "status", "confidence", "data_quality",
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
    },
)

st.download_button(
    "Download projection history CSV",
    display.to_csv(index=False),
    file_name="projection_history.csv",
    mime="text/csv",
)

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
st.caption("Frozen pregame StrikeOut King 9000 projections, resolved against the final MLB strikeout result.")


def load_projection_history() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(LOG_PATH)
    except Exception:
        return pd.DataFrame()


if st.button("Resolve completed games", type="primary"):
    with st.spinner("Checking MLB results and attaching completed strikeout totals..."):
        try:
            resolve_projection_log()
            st.success("Completed-game resolution finished. History refreshed below.")
        except Exception as exc:
            st.error(f"Could not resolve completed projection outcomes: {exc}")


df = load_projection_history()
if df.empty:
    st.info("No archived projections yet. Use Daily Projection Run to capture the announced starter slate before first pitch.")
    st.stop()

for col in ["projection", "k_range_low", "k_range_high", "actual_strikeouts"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

if "actual_strikeouts" not in df.columns:
    df["actual_strikeouts"] = pd.NA
if "k_range_low" not in df.columns:
    df["k_range_low"] = pd.NA
if "k_range_high" not in df.columns:
    df["k_range_high"] = pd.NA

resolved = df["actual_strikeouts"].notna()
range_ready = resolved & df["k_range_low"].notna() & df["k_range_high"].notna()
range_hit = range_ready & (df["actual_strikeouts"] >= df["k_range_low"]) & (df["actual_strikeouts"] <= df["k_range_high"])

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Archived projections", len(df))
col2.metric("Resolved games", int(resolved.sum()))
col3.metric("Projection hits", int(range_hit.sum()))
if range_ready.any():
    col4.metric("Hit rate", f"{float(range_hit.sum() / range_ready.sum()):.1%}")
else:
    col4.metric("Hit rate", "—")
if resolved.any():
    error = df.loc[resolved, "actual_strikeouts"] - df.loc[resolved, "projection"]
    col5.metric("Mean absolute error", f"{float(error.abs().mean()):.2f} K")
else:
    col5.metric("Mean absolute error", "—")

st.caption("HIT means the final strikeout total landed inside the frozen pregame 80% strikeout range. MISS means it finished outside that archived range.")

display = df.sort_values(["game_date", "captured_at_utc"], ascending=[False, False]).copy()
display["status"] = display["actual_strikeouts"].apply(lambda x: "Resolved" if pd.notna(x) else "Pending")
display["error"] = display.apply(
    lambda r: r["actual_strikeouts"] - r["projection"] if pd.notna(r["actual_strikeouts"]) and pd.notna(r["projection"]) else None,
    axis=1,
)

def projection_result(row: pd.Series) -> str:
    if pd.isna(row.get("actual_strikeouts")):
        return "PENDING"
    if pd.isna(row.get("k_range_low")) or pd.isna(row.get("k_range_high")):
        return "RESOLVED"
    actual = float(row["actual_strikeouts"])
    return "✅ HIT" if float(row["k_range_low"]) <= actual <= float(row["k_range_high"]) else "❌ MISS"


display["result"] = display.apply(projection_result, axis=1)

display_columns = [
    "game_date", "player", "team", "opponent", "projection", "k_range_low",
    "k_range_high", "actual_strikeouts", "result", "error", "status", "confidence",
    "data_quality",
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
        "projection": st.column_config.NumberColumn("Projection", format="%.2f K"),
        "k_range_low": st.column_config.NumberColumn("80% K Low", format="%.0f"),
        "k_range_high": st.column_config.NumberColumn("80% K High", format="%.0f"),
        "actual_strikeouts": st.column_config.NumberColumn("Actual Ks", format="%.0f"),
        "result": st.column_config.TextColumn("Result"),
        "error": st.column_config.NumberColumn("Error", format="%+.2f K"),
    },
)

st.download_button(
    "Download projection history CSV",
    display.to_csv(index=False),
    file_name="projection_history.csv",
    mime="text/csv",
)

from __future__ import annotations

import pandas as pd
import streamlit as st

from training.github_projection_store import load_projections, resolve_completed_projections

st.set_page_config(page_title="Projection History", page_icon="📚", layout="wide")
st.title("📚 Projection History")
st.caption("Every frozen StrikeOut King 9000 pitcher projection is archived separately from your Bet Tracker.")

if st.button("Resolve completed games", type="primary"):
    with st.spinner("Checking MLB results and attaching completed strikeout totals..."):
        updated = resolve_completed_projections()
    if updated:
        st.success(f"Updated {updated} completed projection(s).")
    else:
        st.info("No new completed projection outcomes were available yet.")

rows = load_projections()
if not rows:
    st.info("No archived projections yet. Analyze today's pitchers on StrikeOut King 9000 and they will be archived automatically.")
    st.stop()

df = pd.DataFrame(rows)
df["projection"] = pd.to_numeric(df["projection"], errors="coerce")
df["actual_strikeouts"] = pd.to_numeric(df["actual_strikeouts"], errors="coerce")
resolved = df["actual_strikeouts"].notna()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Archived projections", len(df))
col2.metric("Resolved games", int(resolved.sum()))
if resolved.any():
    error = df.loc[resolved, "actual_strikeouts"] - df.loc[resolved, "projection"]
    col3.metric("Mean absolute error", f"{float(error.abs().mean()):.2f} K")
    col4.metric("Average signed error", f"{float(error.mean()):+.2f} K")
else:
    col3.metric("Mean absolute error", "—")
    col4.metric("Average signed error", "—")

display = df.sort_values(["game_date", "captured_at_utc"], ascending=[False, False]).copy()
display["status"] = display["actual_strikeouts"].apply(lambda x: "Resolved" if pd.notna(x) else "Pending")
display["error"] = display.apply(
    lambda r: r["actual_strikeouts"] - r["projection"] if pd.notna(r["actual_strikeouts"]) else None,
    axis=1,
)

display_columns = [
    "game_date", "player", "team", "opponent", "projection", "k_range_low",
    "k_range_high", "actual_strikeouts", "error", "status", "confidence",
    "data_quality",
]

# Use Streamlit's native column formatting instead of pandas Styler. This avoids
# pandas Styler serialization compatibility problems while keeping the table interactive.
st.dataframe(
    display[display_columns],
    hide_index=True,
    width="stretch",
    column_config={
        "projection": st.column_config.NumberColumn("Projection", format="%.2f K"),
        "k_range_low": st.column_config.NumberColumn("80% K low", format="%.0f"),
        "k_range_high": st.column_config.NumberColumn("80% K high", format="%.0f"),
        "actual_strikeouts": st.column_config.NumberColumn("Actual Ks", format="%.0f"),
        "error": st.column_config.NumberColumn("Error", format="%+.2f K"),
    },
)

st.download_button(
    "Download projection history CSV",
    display.to_csv(index=False),
    file_name="projection_history.csv",
    mime="text/csv",
)

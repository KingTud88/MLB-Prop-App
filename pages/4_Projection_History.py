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

st.dataframe(
    display[
        ["game_date", "player", "team", "opponent", "projection", "k_range_low",
         "k_range_high", "actual_strikeouts", "error", "status", "confidence",
         "data_quality"]
    ].style.format({
        "projection": "{:.2f}",
        "k_range_low": "{:.0f}",
        "k_range_high": "{:.0f}",
        "error": "{:+.2f}",
    }),
    hide_index=True,
    use_container_width=True,
)

st.download_button(
    "Download projection history CSV",
    display.to_csv(index=False),
    file_name="projection_history.csv",
    mime="text/csv",
)

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "data" / "ml_shadow_summary.csv"
LIVE_PATH = ROOT / "data" / "ml_shadow_live_candidates.csv"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 1:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _row(summary: pd.DataFrame, name: str) -> pd.Series:
    if summary.empty or "Challenger" not in summary.columns:
        return pd.Series(dtype=object)
    rows = summary.loc[summary["Challenger"].astype(str).eq(name)]
    return rows.iloc[0] if not rows.empty else pd.Series(dtype=object)


def _number(row: pd.Series, name: str, kind: str = "number") -> str:
    value = pd.to_numeric(pd.Series([row.get(name)]), errors="coerce").iloc[0]
    if pd.isna(value):
        return "—"
    if kind == "pct":
        return f"{float(value):+.1%}"
    return f"{float(value):.3f}"


def _integer(row: pd.Series, name: str) -> int:
    value = pd.to_numeric(pd.Series([row.get(name, 0)]), errors="coerce").fillna(0).iloc[0]
    return int(value)


def _render_ml_shadow_content(game: object) -> None:
    st.caption(
        "Gradient-boosted K challenger trained chronologically on earlier resolved starter rows only. "
        "Sportsbook data and postgame features are banned. Nothing here changes SIM, MATH, the headline projection, Top Plays, or bet leans."
    )
    summary = _read_csv(SUMMARY_PATH)
    if summary.empty:
        st.info("ML shadow evidence has not been generated yet. The live two-path projection remains unchanged.")
        return

    ml = _row(summary, "ML_SHADOW")
    three = _row(summary, "SIM_MATH_ML_EQUAL_THIRDS")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("ML shadow", str(ml.get("Status", "LEARNING")))
    m2.metric("ML OOS starts", _integer(ml, "OOS_Starts"))
    m3.metric("ML MAE", _number(ml, "Candidate_MAE"))
    m4.metric("vs current MAE", _number(ml, "Relative_MAE_Improvement", "pct"))

    t1, t2, t3, t4 = st.columns(4)
    t1.metric("3-path research", str(three.get("Status", "LEARNING")))
    t2.metric("3-path OOS starts", _integer(three, "OOS_Starts"))
    t3.metric("3-path MAE", _number(three, "Candidate_MAE"))
    t4.metric("vs current MAE", _number(three, "Relative_MAE_Improvement", "pct"))

    live = _read_csv(LIVE_PATH)
    if not live.empty:
        game_pk = str(getattr(game, "game_pk", "")).replace(".0", "")
        pitcher_id = str(getattr(game, "pitcher_id", "")).replace(".0", "")
        gp = live.get("game_pk", pd.Series(index=live.index, dtype=str)).astype(str).str.replace(r"\.0$", "", regex=True)
        pid = live.get("pitcher_id", pd.Series(index=live.index, dtype=str)).astype(str).str.replace(r"\.0$", "", regex=True)
        match = live.loc[gp.eq(game_pk) & pid.eq(pitcher_id)]
        if not match.empty:
            row = match.iloc[-1]
            st.markdown("#### Current pitcher shadow readout")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current projection", f"{float(row.get('Existing_Projection')):.2f}")
            c2.metric("ML shadow", f"{float(row.get('ML_Shadow_Projection')):.2f}")
            three_value = pd.to_numeric(pd.Series([row.get("Three_Path_Candidate")]), errors="coerce").iloc[0]
            c3.metric("3-path candidate", "—" if pd.isna(three_value) else f"{float(three_value):.2f}")
            c4.metric("Prior training starts", _integer(row, "Training_Resolved_Starts"))
            st.caption(
                "Research readout only. The current projection cards and all betting decisions still use the existing two-path engine."
            )

    display_cols = [
        col
        for col in (
            "Challenger",
            "OOS_Starts",
            "Existing_MAE",
            "Candidate_MAE",
            "Relative_MAE_Improvement",
            "Candidate_Win_Share",
            "Status",
            "Reason",
        )
        if col in summary.columns
    ]
    if display_cols:
        st.dataframe(summary[display_cols], use_container_width=True, hide_index=True)


def render_ml_shadow_dashboard(game: object) -> None:
    """Render report-only ML evidence without importing or training the ML model."""
    with st.expander("Research detail · ML challenger (report only)", expanded=False):
        _render_ml_shadow_content(game)

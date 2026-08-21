from __future__ import annotations

import pandas as pd
import streamlit as st

from engine.projection_crushers import underperformer_report


def render_projection_underperformers(frame: pd.DataFrame) -> None:
    """Render the negative exact-projection residual board; presentation only."""
    underperformers = underperformer_report(frame)
    st.markdown("#### Projection Underperformers · exact frozen projection")
    if underperformers.empty:
        st.info("Underperformer tracking will populate as current starter-only exact frozen K projections resolve.")
        return

    view = underperformers.copy()
    for col in ["Below Projection Rate", "Recent 5 Below Rate"]:
        view[col] = view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.1%}")
    for col in ["Avg K vs Projection", "Median K vs Projection", "Avg Under Margin"]:
        view[col] = view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.2f}")
    if "Total K Below Projection" in view.columns:
        view["Total K Below Projection"] = view["Total K Below Projection"].map(
            lambda x: "—" if pd.isna(x) else f"{float(x):.2f}"
        )

    st.dataframe(view, hide_index=True, width="stretch")
    st.caption(
        "UNDERPERFORMER requires at least 3 resolved current-model exact-projection outcomes, "
        "a below-projection rate of at least 66.7%, and average Actual Ks − Projected Ks below -0.50. "
        "This board is descriptive tracking only and is not sportsbook execution grading."
    )

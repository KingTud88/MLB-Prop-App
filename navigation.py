from __future__ import annotations

import streamlit as st

MASCOT_URL = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/strikeout_king_9000.svg"


def render_sidebar(active: str = "projection") -> None:
    """Render the shared app navigation.

    Odds/market functionality is intentionally part of the Projection command
    center now, so there is no separate Odds API page in the primary workflow.
    """
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"]{width:205px!important;min-width:205px!important}
        [data-testid="stSidebar"]>div:first-child{width:205px!important}
        .sk-nav-mascot{display:flex;justify-content:center;align-items:center;height:118px;margin:-.25rem 0 .15rem}
        .sk-nav-mascot img{width:112px;height:112px;object-fit:contain;display:block}
        .sk-nav-title{text-align:center;font-family:Impact,"Arial Narrow",sans-serif;font-size:1.18rem;line-height:1;color:#fff}
        .sk-nav-title span{color:#e31837}
        .sk-nav-sub{text-align:center;color:#aebed0;font-size:.68rem;line-height:1.35;margin:.45rem 0 .8rem}
        [data-testid="stSidebar"] .sk-page-link a{font-family:Arial,sans-serif!important;font-weight:800!important}
        [data-testid="stSidebar"] .sk-page-link{margin:.08rem 0}
        [data-testid="stSidebar"] .sk-page-link a{border-radius:8px!important;padding:.42rem .55rem!important}
        [data-testid="stSidebar"] .sk-page-link.active a{background:linear-gradient(90deg,#ed1838,#bd0d2b)!important;color:#fff!important}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.markdown(
            f'<div class="sk-nav-mascot"><img src="{MASCOT_URL}" alt="StrikeOut King 9000 mascot"></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sk-nav-title">StrikeOut <span>King 9000</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="sk-nav-sub">CLE-themed distributional MLB starter projections</div>', unsafe_allow_html=True)

        links = [
            ("projection", "streamlit_app.py", "⌂", "Projection"),
            ("top", "pages/6_Top_Plays.py", "👑", "Top Plays"),
            ("bets", "pages/2_Bet_Tracker.py", "♧", "Bet Tracker"),
            ("history", "pages/4_Projection_History.py", "▣", "Projection History"),
            ("daily", "pages/5_Daily_Projection_Run.py", "▤", "Daily Projection Run"),
        ]
        for key, page, icon, label in links:
            cls = "sk-page-link active" if key == active else "sk-page-link"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            st.page_link(page, label=f"{icon}  {label}", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div style="height:.65rem;border-bottom:1px solid #203b57;margin-bottom:.8rem"></div>', unsafe_allow_html=True)

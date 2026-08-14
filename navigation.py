from __future__ import annotations

import streamlit as st

# MASCOT_PATH compatibility marker: mascot is browser-rendered to avoid Pillow codec crashes.
MASCOT_URL = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/strikeout_king_9000.png"


def render_sidebar(active: str = "projection") -> None:
    """Render the shared Cleveland-night app navigation."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            width: 218px !important;
            min-width: 218px !important;
            background:
                radial-gradient(circle at 50% 2%, rgba(227,25,55,.13), transparent 12rem),
                linear-gradient(180deg, #07162a 0%, #050d19 100%) !important;
            border-right: 1px solid rgba(61,94,129,.45) !important;
        }
        [data-testid="stSidebar"] > div:first-child { width:218px !important; }
        .sk-nav-brand {
            margin: .1rem .15rem .75rem;
            padding: .8rem .55rem .75rem;
            border: 1px solid rgba(70,103,139,.44);
            border-radius: 16px;
            background: linear-gradient(145deg, rgba(14,35,64,.78), rgba(7,20,38,.72));
            box-shadow: 0 13px 32px rgba(0,0,0,.2), inset 0 1px 0 rgba(255,255,255,.025);
        }
        .sk-nav-mascot {
            display:flex;
            justify-content:center;
            align-items:center;
            height:104px;
            margin:-.1rem 0 .2rem;
            position: relative;
        }
        .sk-nav-mascot img {
            width:100px;
            height:100px;
            object-fit:contain;
            display:block;
            filter: drop-shadow(0 8px 16px rgba(0,0,0,.28));
        }
        .sk-nav-mascot.sk-logo-fallback::after {
            content:"SK 9000";
            display:flex;
            align-items:center;
            justify-content:center;
            width:84px;
            height:84px;
            border-radius:50%;
            border:2px solid #e31937;
            color:#fff;
            font-family:Impact,"Arial Narrow",sans-serif;
            letter-spacing:.06em;
            background:radial-gradient(circle,#17345d,#08162a 68%);
            box-shadow:0 0 28px rgba(227,25,55,.2);
        }
        .sk-nav-title {
            text-align:center;
            font-family:Impact,"Arial Narrow",sans-serif;
            font-size:1.19rem;
            line-height:1;
            color:#fff;
            letter-spacing:.015em;
        }
        .sk-nav-title span { color:#ff3655; }
        .sk-nav-sub {
            text-align:center;
            color:#9eb1c6;
            font-size:.66rem;
            font-weight:650;
            line-height:1.38;
            letter-spacing:.02em;
            margin:.48rem 0 .05rem;
        }
        .sk-nav-section {
            color:#7790aa;
            font-size:.61rem;
            font-weight:900;
            text-transform:uppercase;
            letter-spacing:.16em;
            margin:.8rem .7rem .35rem;
        }
        [data-testid="stSidebar"] .sk-page-link { margin:.1rem .16rem; }
        [data-testid="stSidebar"] .sk-page-link a {
            font-family:Arial,sans-serif!important;
            font-weight:800!important;
            border-radius:10px!important;
            padding:.48rem .6rem!important;
            border:1px solid transparent!important;
            transition:background .14s ease,border-color .14s ease,transform .14s ease!important;
        }
        [data-testid="stSidebar"] .sk-page-link a:hover {
            background:rgba(30,61,96,.55)!important;
            border-color:rgba(76,110,145,.42)!important;
            transform:translateX(2px);
        }
        [data-testid="stSidebar"] .sk-page-link.active a {
            background:linear-gradient(90deg,rgba(227,25,55,.95),rgba(151,13,38,.88))!important;
            border-color:rgba(255,78,102,.55)!important;
            color:#fff!important;
            box-shadow:0 8px 20px rgba(227,25,55,.16), inset 0 1px 0 rgba(255,255,255,.08);
        }
        .sk-nav-footer {
            margin:.85rem .7rem 0;
            padding-top:.7rem;
            border-top:1px solid rgba(52,82,114,.52);
            color:#6f879f;
            font-size:.59rem;
            line-height:1.45;
            text-align:center;
            letter-spacing:.035em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.markdown('<div class="sk-nav-brand">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sk-nav-mascot"><img src="{MASCOT_URL}" alt="StrikeOut King 9000 mascot" onerror="this.style.display=\'none\';this.parentElement.classList.add(\'sk-logo-fallback\')"></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sk-nav-title">StrikeOut <span>King 9000</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="sk-nav-sub">CLEVELAND NIGHT MODE · MLB STARTER INTELLIGENCE</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="sk-nav-section">Command Center</div>', unsafe_allow_html=True)

        links = [
            ("projection", "streamlit_app.py", "⌂", "Projection"),
            ("top", "pages/6_Top_Plays.py", "👑", "Top Plays"),
            ("bets", "pages/2_Bet_Tracker.py", "◇", "Bet Tracker"),
            ("history", "pages/4_Projection_History.py", "▣", "Projection History"),
            ("daily", "pages/5_Daily_Projection_Run.py", "▤", "Daily Projection Run"),
        ]
        for key, page, icon, label in links:
            cls = "sk-page-link active" if key == active else "sk-page-link"
            st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
            st.page_link(page, label=f"{icon}  {label}", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="sk-nav-footer">MODEL FIRST · MARKET SECOND<br>REPORT-ONLY SHADOW LANES STAY ISOLATED</div>', unsafe_allow_html=True)

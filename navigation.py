from __future__ import annotations

import streamlit as st

# MASCOT_PATH compatibility marker: mascot is browser-rendered to avoid Pillow codec crashes.
MASCOT_URL = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/strikeout_king_9000_sidebar.png?v=9"


def render_sidebar(active: str = "projection") -> None:
    """Render the shared Cleveland-night app navigation."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            width: 252px !important;
            min-width: 252px !important;
            background:
                radial-gradient(circle at 50% 2%, rgba(227,25,55,.13), transparent 12rem),
                linear-gradient(180deg, #07162a 0%, #050d19 100%) !important;
            border-right: 1px solid rgba(61,94,129,.45) !important;
        }
        [data-testid="stSidebar"] > div:first-child { width:252px !important; }
        .sk-nav-brand {
            margin: .1rem .15rem .75rem;
            padding: .72rem .5rem .75rem;
            border: 1px solid rgba(70,103,139,.44);
            border-radius: 16px;
            background: linear-gradient(145deg, rgba(14,35,64,.78), rgba(7,20,38,.72));
            box-shadow: 0 13px 32px rgba(0,0,0,.2), inset 0 1px 0 rgba(255,255,255,.025);
        }
        .sk-nav-brand:empty {
            display:none !important;
            margin:0 !important;
            padding:0 !important;
            border:0 !important;
            background:none !important;
            box-shadow:none !important;
        }
        .sk-nav-mascot {
            display:flex;
            justify-content:center;
            align-items:center;
            height:238px;
            margin:-.48rem 0 -.60rem;
            position: relative;
            overflow:hidden;
        }
        .sk-nav-mascot img {
            width:236px !important;
            height:236px !important;
            object-fit:contain;
            max-width:none !important;
            min-width:236px !important;
            display:block;
            filter: drop-shadow(0 9px 18px rgba(0,0,0,.3));
            transform:scale(1.00) !important;
            transform-origin:50% 50%;
        }
        .sk-nav-mascot.sk-logo-fallback::after {
            content:"SK 9000";
            display:flex;
            align-items:center;
            justify-content:center;
            width:96px;
            height:96px;
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
            font-size:2.18rem;
            line-height:.82;
            color:#fff;
            letter-spacing:.015em;
        }
        .sk-nav-title span { color:#ff2848; font-size:2.28rem; letter-spacing:.035em; white-space:nowrap; }
        .sk-nav-title::after {
            content:"✦";
            display:block;
            width:88%;
            margin:.58rem auto .05rem;
            border-top:2px solid rgba(236,22,56,.88);
            color:#ff2848;
            font-family:Arial,sans-serif;
            font-size:.58rem;
            line-height:0;
            text-shadow:0 0 8px rgba(236,22,56,.7);
        }
        .sk-nav-sub {
            text-align:center;
            color:#9eb1c6;
            font-size:.75rem;
            font-weight:650;
            line-height:1.38;
            letter-spacing:.02em;
            margin:.38rem .28rem 0;
        }
        .sk-nav-section {
            color:#d72b43;
            font-size:.67rem;
            font-weight:900;
            text-transform:uppercase;
            letter-spacing:.16em;
            margin:.42rem .95rem .3rem;
        }
        [data-testid="stSidebar"] .sk-page-link { margin:.11rem .28rem; }
        [data-testid="stSidebar"] .sk-page-link a {
            font-family:Arial,sans-serif!important;
            font-weight:800!important;
            border-radius:10px!important;
            padding:.52rem .72rem!important;
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

    if active == "top":
        st.markdown(
            """
            <style>
            :root {
                --tp-navy:#031327;
                --tp-panel:#081e35;
                --tp-panel-deep:#051628;
                --tp-line:#36526d;
                --tp-red:#ec1638;
                --tp-red-dark:#9f0c25;
                --tp-cream:#f1eee7;
                --tp-green:#32e58d;
                --tp-yellow:#ffd166;
                --tp-muted:#9fb3c6;
                --tp-ui:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
            }

            .stApp {
                background:
                    radial-gradient(ellipse at 52% 3%, rgba(20,55,91,.46), transparent 35rem),
                    radial-gradient(ellipse at 50% 58%, rgba(7,39,70,.26), transparent 42rem),
                    linear-gradient(180deg, rgba(3,16,32,.99), rgba(2,11,22,.99)) !important;
            }
            .stApp,[data-testid="stMarkdownContainer"],[data-testid="stCaptionContainer"],button,input,label {
                font-family:var(--tp-ui)!important;
                -webkit-font-smoothing:antialiased;
                -moz-osx-font-smoothing:grayscale;
                text-rendering:optimizeLegibility;
            }
            .block-container {
                max-width:1520px!important;
                padding-top:2.35rem!important;
                padding-bottom:4rem!important;
            }

            /* Top Plays hero treatment. */
            h1 {
                position:relative;
                margin:.1rem 0 .55rem!important;
                padding:1.05rem 1.25rem 1rem!important;
                border:1px solid rgba(82,108,134,.72)!important;
                border-radius:18px!important;
                color:var(--tp-cream)!important;
                background:
                    linear-gradient(90deg,rgba(4,19,36,.97),rgba(7,31,56,.95) 55%,rgba(4,17,32,.98)),
                    radial-gradient(circle at 18% 0%,rgba(236,22,56,.16),transparent 20rem)!important;
                box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 20px 52px rgba(0,0,0,.33)!important;
                font-family:Impact,"Arial Black","Arial Narrow",sans-serif!important;
                font-size:clamp(2.6rem,5vw,4.9rem)!important;
                line-height:.88!important;
                letter-spacing:.018em!important;
                text-transform:uppercase!important;
                text-shadow:3px 4px 0 #07182b,0 0 24px rgba(236,22,56,.13)!important;
            }
            h1::after {
                content:"MODEL-FIRST DAILY COMMAND BOARD";
                display:block;
                width:max-content;
                max-width:100%;
                margin-top:.7rem;
                padding:.34rem .72rem;
                border-top:1px solid rgba(236,22,56,.7);
                border-bottom:1px solid rgba(236,22,56,.7);
                color:#dce7f0;
                font-family:var(--tp-ui)!important;
                font-size:.72rem;
                font-weight:900;
                letter-spacing:.11em;
                line-height:1.2;
                text-shadow:none!important;
            }
            h1 + [data-testid="stCaptionContainer"] {
                margin:-.1rem .2rem 1.15rem!important;
                padding:.75rem .9rem!important;
                border-left:3px solid var(--tp-red)!important;
                border-radius:0 10px 10px 0!important;
                background:rgba(7,27,49,.66)!important;
                color:#b7c8d7!important;
                font-size:.9rem!important;
                line-height:1.5!important;
            }

            /* Summary scorecard. */
            [data-testid="stMetric"] {
                position:relative;
                overflow:hidden;
                min-height:122px;
                padding:.78rem .8rem!important;
                border:1px solid rgba(77,108,137,.72)!important;
                border-radius:14px!important;
                background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98))!important;
                box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 12px 28px rgba(0,0,0,.25)!important;
            }
            [data-testid="stMetric"]::after {
                content:"";position:absolute;left:9%;right:9%;bottom:0;height:2px;
                background:linear-gradient(90deg,transparent,var(--tp-red),transparent);opacity:.72;
            }
            [data-testid="stMetricLabel"] {
                font-family:var(--tp-ui)!important;
                color:#dce7ef!important;
                font-size:.79rem!important;
                line-height:1.25!important;
                font-weight:850!important;
                letter-spacing:.025em!important;
                text-transform:uppercase!important;
            }
            [data-testid="stMetricValue"] {
                font-family:Impact,"Arial Narrow",sans-serif!important;
                color:#f7f3ec!important;
                font-size:2.15rem!important;
                letter-spacing:.01em!important;
                text-shadow:2px 3px 0 rgba(0,0,0,.28)!important;
            }

            /* Section hierarchy. */
            h2,h3,h4 {
                font-family:var(--tp-ui)!important;
                text-shadow:none!important;
            }
            h4 {
                width:max-content;
                min-width:245px;
                max-width:92%;
                margin:1.25rem auto .8rem!important;
                padding:.48rem 1.8rem!important;
                border:1px solid #ff3151!important;
                border-bottom-color:#790b1d!important;
                border-radius:8px!important;
                color:#fff!important;
                background:linear-gradient(180deg,#f21b3d,#b70d29)!important;
                box-shadow:0 7px 16px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.2)!important;
                font-size:.94rem!important;
                font-weight:900!important;
                line-height:1.15!important;
                letter-spacing:.03em!important;
                text-align:center!important;
                text-transform:uppercase!important;
            }
            h2 {
                margin-top:1.25rem!important;
                color:#f4f0e8!important;
                font-size:1.55rem!important;
                font-weight:900!important;
                letter-spacing:.01em!important;
            }

            /* The five Top Play columns become sportsbook-style command cards. */
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has(button[key^="view_top_play_"]) {
                position:relative;
                min-height:355px;
                padding:.82rem .78rem 1rem!important;
                border:1px solid rgba(82,112,141,.74)!important;
                border-radius:16px!important;
                background:linear-gradient(150deg,rgba(10,34,59,.99),rgba(4,18,33,.99))!important;
                box-shadow:inset 0 1px 0 rgba(255,255,255,.045),0 15px 34px rgba(0,0,0,.29)!important;
                overflow:hidden;
            }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has(button[key^="view_top_play_"])::before {
                content:"";position:absolute;left:0;right:0;top:0;height:3px;
                background:linear-gradient(90deg,transparent,var(--tp-red) 18%,var(--tp-red) 82%,transparent);
                box-shadow:0 0 14px rgba(236,22,56,.35);
            }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has(button[key^="view_top_play_"]) h3 {
                margin:.12rem 0 .25rem!important;
                color:#f7f3ec!important;
                font-size:1.12rem!important;
                line-height:1.15!important;
                font-weight:900!important;
                letter-spacing:.005em!important;
            }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has(button[key^="view_top_play_"]) [data-testid="stCaptionContainer"] {
                color:#9fb3c6!important;
                font-size:.78rem!important;
                line-height:1.35!important;
            }
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has(button[key^="view_top_play_"]) p strong {
                color:#f6f1e9!important;
                font-size:.91rem!important;
                letter-spacing:.02em!important;
                text-transform:uppercase!important;
            }

            /* Override legacy purple projection block while preserving its content. */
            div[style*="#8b4fc7"] {
                border:1px solid rgba(70,105,139,.86)!important;
                border-radius:12px!important;
                background:linear-gradient(145deg,rgba(12,39,67,.98),rgba(6,23,41,.98))!important;
                padding:11px 8px!important;
                margin:10px 0!important;
                box-shadow:inset 0 1px 0 rgba(255,255,255,.035)!important;
            }
            div[style*="#8b4fc7"] span[style*="background:#8b4fc7"],
            div[style*="#8b4fc7"] span[style*="background: #8b4fc7"] {
                background:rgba(77,108,137,.72)!important;
            }

            /* Action controls. */
            div[data-testid="stButton"] button {
                min-height:2.65rem!important;
                border-radius:10px!important;
                border:1px solid rgba(89,123,157,.72)!important;
                background:linear-gradient(180deg,rgba(22,53,88,.98),rgba(9,29,53,.98))!important;
                color:#edf3f8!important;
                font-family:var(--tp-ui)!important;
                font-weight:900!important;
                letter-spacing:.015em!important;
                box-shadow:inset 0 1px 0 rgba(255,255,255,.04)!important;
            }
            div[data-testid="stButton"] button:hover:not(:disabled) {
                border-color:rgba(236,22,56,.72)!important;
                background:linear-gradient(180deg,rgba(34,67,104,.99),rgba(12,35,62,.99))!important;
            }
            div[data-testid="stButton"] button[kind="primary"] {
                background:linear-gradient(180deg,#f21b3d,#b70d29)!important;
                border-color:#ff3b59!important;
                color:#fff!important;
                text-transform:uppercase!important;
                letter-spacing:.04em!important;
            }
            div[data-testid="stButton"] button:disabled {
                opacity:.48!important;
            }

            /* Form controls / parlay builder. */
            [data-testid="stNumberInput"],[data-testid="stSelectbox"],[data-testid="stMultiSelect"] {
                font-family:var(--tp-ui)!important;
            }
            [data-baseweb="input"],[data-baseweb="select"] > div {
                border-color:rgba(75,108,140,.68)!important;
                background:rgba(7,25,45,.94)!important;
            }

            /* Diagnostics / rationale panels. */
            div[data-testid="stExpander"] {
                margin:.5rem 0!important;
                border:1px solid rgba(77,106,135,.72)!important;
                border-radius:13px!important;
                background:linear-gradient(145deg,rgba(8,28,50,.97),rgba(4,17,31,.98))!important;
                box-shadow:inset 0 1px 0 rgba(255,255,255,.035),0 10px 24px rgba(0,0,0,.19)!important;
            }
            div[data-testid="stExpander"] summary {
                font-family:var(--tp-ui)!important;
                font-weight:850!important;
                color:#edf3f8!important;
            }
            [data-testid="stDataFrame"] {
                border:1px solid rgba(75,105,134,.72)!important;
                border-radius:12px!important;
                box-shadow:0 12px 28px rgba(0,0,0,.2)!important;
            }
            [data-testid="stCaptionContainer"] {
                color:#9fb3c6!important;
                font-size:.86rem!important;
                line-height:1.45!important;
                letter-spacing:0!important;
                text-shadow:none!important;
            }
            hr {
                border-color:rgba(70,102,133,.46)!important;
                margin:1.35rem 0!important;
            }

            @media (max-width:1100px) {
                [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has(button[key^="view_top_play_"]) { min-height:0; }
            }
            @media (max-width:760px) {
                .block-container { padding-top:1rem!important; }
                h1 { font-size:2.65rem!important;padding:.9rem!important; }
                h1::after { font-size:.64rem!important;letter-spacing:.07em; }
                h4 { min-width:180px;padding:.42rem 1rem!important;font-size:.86rem!important; }
                [data-testid="stMetric"] { min-height:100px; }
                [data-testid="stMetricValue"] { font-size:1.85rem!important; }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    with st.sidebar:
        st.markdown('<div class="sk-nav-brand">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sk-nav-mascot"><img src="{MASCOT_URL}" alt="StrikeOut King 9000 mascot" style="width:236px !important;height:236px !important;min-width:236px !important;max-width:236px !important;object-fit:contain !important;display:block !important;transform:scale(1.00) !important;transform-origin:50% 50% !important;" onerror="this.style.display=\'none\';this.parentElement.classList.add(\'sk-logo-fallback\')"></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sk-nav-title">STRIKEOUT<br><span>KING 9000</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="sk-nav-sub">CLEVELAND NIGHT MODE · MLB<br>STARTER INTELLIGENCE</div>', unsafe_allow_html=True)
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

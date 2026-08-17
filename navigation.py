from __future__ import annotations

import streamlit as st

from engine.ui_command_center import render_sidebar_brand

# MASCOT_PATH compatibility marker: mascot is browser-rendered to avoid Pillow codec crashes.
MASCOT_URL = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/strikeout_king_9000_sidebar.png?v=9"


def render_sidebar(active: str = "projection") -> None:
    """Render the shared Cleveland-night app navigation."""
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

    # PROJECTION_PARITY_SIDEBAR_V3 · exact Main Projection navigation language.
    st.markdown(
        """
        <style>
        /* Secondary pages deliberately inherit Streamlit's same sidebar width as Main Projection. */
        [data-testid="stSidebar"]{
            background:linear-gradient(180deg,rgba(7,20,38,.99),rgba(4,12,24,.99))!important;
            border-right:1px solid rgba(62,95,130,.48)!important;
            box-shadow:12px 0 42px rgba(0,0,0,.14)!important;
        }
        [data-testid="stSidebar"] > div:first-child{
            width:auto!important;
            min-width:0!important;
        }
        [data-testid="stSidebar"] .cc-sidebar-brand{
            padding:.85rem .7rem .8rem!important;
            margin:.10rem 0 .80rem!important;
            border:1px solid rgba(78,108,137,.66)!important;
            border-radius:14px!important;
            background:linear-gradient(145deg,rgba(8,29,51,.98),rgba(3,16,30,.98))!important;
            text-align:center!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 12px 26px rgba(0,0,0,.20)!important;
        }
        [data-testid="stSidebar"] .cc-sidebar-crown{color:#ec1638!important;font-size:1.2rem!important;line-height:1!important}
        [data-testid="stSidebar"] .cc-sidebar-script{color:#f5f1e9!important;font-family:Georgia,"Times New Roman",serif!important;font-size:1.55rem!important;font-weight:800!important;font-style:italic!important;line-height:.95!important}
        [data-testid="stSidebar"] .cc-sidebar-king{color:#ec1638!important;font-family:Impact,"Arial Narrow",sans-serif!important;font-size:1.42rem!important;letter-spacing:.035em!important;line-height:1!important;text-transform:uppercase!important}
        [data-testid="stSidebar"] .cc-sidebar-tag{margin-top:.38rem!important;color:#9fb3c5!important;font:700 .78rem/1.35 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] > div{gap:.28rem!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label{
            display:flex!important;
            align-items:center!important;
            flex-direction:row!important;
            flex-wrap:nowrap!important;
            position:relative!important;
            gap:.52rem!important;
            min-height:2.42rem!important;
            padding:.26rem .38rem!important;
            border:1px solid transparent!important;
            border-radius:9px!important;
            transition:background .14s ease,border-color .14s ease,box-shadow .14s ease!important;
            font:800 .82rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:hover{
            background:rgba(227,25,55,.07)!important;
            border-color:rgba(227,25,55,.22)!important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:has(input:checked){
            background:linear-gradient(90deg,rgba(227,25,55,.22),rgba(19,43,71,.72))!important;
            border-color:rgba(255,54,85,.44)!important;
            box-shadow:inset 3px 0 0 #ff3655!important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label input[type="radio"]{display:none!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label>div:has(input[type="radio"]){display:none!important;width:0!important;height:0!important;margin:0!important;padding:0!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label [role="radio"]{display:none!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label::before{
            content:""!important;
            display:inline-block!important;
            width:1.72rem!important;
            height:1.72rem!important;
            flex:0 0 1.72rem!important;
            border:1px solid rgba(236,22,56,.68)!important;
            border-radius:7px!important;
            background-color:#0b2038!important;
            background-repeat:no-repeat!important;
            background-position:center!important;
            background-size:1.20rem 1.20rem!important;
            box-shadow:inset 0 0 0 2px rgba(255,255,255,.025),0 4px 10px rgba(0,0,0,.25)!important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:has(input:checked)::before{
            border-color:#ff3553!important;
            background-color:#411225!important;
            box-shadow:inset 0 0 0 2px rgba(255,255,255,.04),0 0 13px rgba(236,22,56,.48)!important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(1)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PGcgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCI+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iMTQiLz48Y2lyY2xlIGN4PSIzMiIgY3k9IjMyIiByPSI0IiBmaWxsPSIjZWMxNjM4IiBzdHJva2U9IiNlYzE2MzgiLz48cGF0aCBkPSJNMzIgNnYxMk0zMiA0NnYxMk02IDMyaDEyTTQ2IDMyaDEyIi8+PC9nPjwvc3ZnPg==")!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(2)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PGcgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTEwIDU0aDQ0Ii8+PHJlY3QgeD0iMTMiIHk9IjM0IiB3aWR0aD0iOCIgaGVpZ2h0PSIxOCIgcng9IjIiLz48cmVjdCB4PSIyOCIgeT0iMjIiIHdpZHRoPSI4IiBoZWlnaHQ9IjMwIiByeD0iMiIgZmlsbD0iI2VjMTYzOCIgc3Ryb2tlPSIjZWMxNjM4Ii8+PHJlY3QgeD0iNDMiIHk9IjEyIiB3aWR0aD0iOCIgaGVpZ2h0PSI0MCIgcng9IjIiLz48L2c+PC9zdmc+")!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(3)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHBhdGggZD0iTTYgMzRoMTJsNi0xNCA5IDI4IDgtMjAgNSA2aDEyIiBmaWxsPSJub25lIiBzdHJva2U9IiNmN2Y3ZmIiIHN0cm9rZS13aWR0aD0iNCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PGNpcmNsZSBjeD0iMzMiIGN5PSIzNCIgcj0iMyIgZmlsbD0iI2VjMTYzOCIvPjwvc3ZnPg==")!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(4)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PGcgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCI+PHJlY3QgeD0iMTciIHk9IjE3IiB3aWR0aD0iMzAiIGhlaWdodD0iMzAiIHJ4PSI2Ii8+PHJlY3QgeD0iMjYiIHk9IjI2IiB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHJ4PSIyIiBmaWxsPSIjZWMxNjM4IiBzdHJva2U9IiNlYzE2MzgiLz48cGF0aCBkPSJNMjQgOHY5TTQwIDh2OU0yNCA0N3Y5TTQwIDQ3djlNOCAyNGg5TTggNDBoOU00NyAyNGg5TTQ3IDQwaDkiLz48L2c+PC9zdmc+")!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(5)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHBhdGggZD0iTTE0IDE0aDM2djEyYTcgNyAwIDAgMCAwIDEydjEySDE0VjM4YTcgNyAwIDAgMCAwLTEyVjE0WiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48cGF0aCBkPSJNMjcgMjJ2MjAiIHN0cm9rZT0iI2VjMTYzOCIgc3Ryb2tlLXdpZHRoPSI0IiBzdHJva2UtZGFzaGFycmF5PSI0IDUiLz48L3N2Zz4=")!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(6)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PGcgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTE4IDIwSDh2LTEwIi8+PHBhdGggZD0iTTEwIDIwYTI0IDI0IDAgMSAxLTIgMjIiLz48Y2lyY2xlIGN4PSIzNCIgY3k9IjM0IiByPSIxNiIvPjxwYXRoIGQ9Ik0zNCAyNHYxMWw4IDUiIHN0cm9rZT0iI2VjMTYzOCIvPjwvZz48L3N2Zz4=")!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(7)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHBhdGggZD0iTTM2IDYgMTYgMzZoMTVsLTMgMjIgMjAtMzFIMzRsMi0yMVoiIGZpbGw9IiNmN2Y3ZmIiIHN0cm9rZT0iI2VjMTYzOCIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+")!important}
        [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(8)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHBhdGggZD0ibTEwIDIyIDEyIDkgMTAtMTcgMTAgMTctOSAyOEgxNUwxMCAyMloiIGZpbGw9Im5vbmUiIHN0cm9rZT0iI2Y3ZjdmYiIgc3Ryb2tlLXdpZHRoPSI0IiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIzOSIgcj0iNCIgZmlsbD0iI2VjMTYzOCIvPjwvc3ZnPg==")!important}
        .sk-nav-footer{
            margin:.85rem .7rem 0!important;
            padding-top:.7rem!important;
            border-top:1px solid rgba(52,82,114,.52)!important;
            color:#6f879f!important;
            font-size:.59rem!important;
            line-height:1.45!important;
            text-align:center!important;
            letter-spacing:.035em!important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    nav_options = [
        "Projection", "Distribution", "Form & Workload", "Model Card",
        "Bet Tracker", "Projection History", "Daily Projection Run", "Top Plays",
    ]
    active_label = {
        "projection": "Projection",
        "bets": "Bet Tracker",
        "history": "Projection History",
        "daily": "Daily Projection Run",
        "top": "Top Plays",
    }.get(active, "Projection")
    page_targets = {
        "Bet Tracker": "pages/2_Bet_Tracker.py",
        "Projection History": "pages/4_Projection_History.py",
        "Daily Projection Run": "pages/5_Daily_Projection_Run.py",
        "Top Plays": "pages/6_Top_Plays.py",
    }

    with st.sidebar:
        render_sidebar_brand()
        selected = st.radio(
            "Navigation",
            nav_options,
            index=nav_options.index(active_label),
            label_visibility="collapsed",
            key=f"secondary_command_nav_{active}",
        )
        if selected != active_label:
            if selected in {"Projection", "Distribution", "Form & Workload", "Model Card"}:
                st.session_state["projection_nav_target"] = selected
                st.switch_page("streamlit_app.py")
            else:
                st.switch_page(page_targets[selected])
        st.markdown(
            '<div class="sk-nav-footer">MODEL FIRST · MARKET SECOND<br>REPORT-ONLY SHADOW LANES STAY ISOLATED</div>',
            unsafe_allow_html=True,
        )

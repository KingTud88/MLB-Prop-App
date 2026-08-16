from __future__ import annotations

import streamlit as st

# Shared presentation-only normalization for secondary pages.
# This module must never own projection, sportsbook, grading, archive, or model logic.
COMMAND_CENTER_UI_VERSION = "command-center-consistency-v1"
SUPPORTED_PAGES = {"bet_tracker", "projection_history", "daily_run", "top_plays"}


def apply_command_center_consistency(page: str) -> None:
    """Normalize secondary pages to the latest Projection-page visual language."""
    if page not in SUPPORTED_PAGES:
        return

    st.markdown(
        """
        <style>
        /* COMMAND_CENTER_CONSISTENCY_V1 · presentation only */
        .stApp .block-container{
            max-width:1540px!important;
            padding-top:1.75rem!important;
            padding-bottom:4.5rem!important;
        }

        /* One premium hero language across every command page. */
        .stApp .bt-hero,
        .stApp .ph-command-hero,
        .stApp .daily-command-hero,
        .stApp .tp-page-hero{
            position:relative!important;
            overflow:hidden!important;
            margin:.08rem 0 .82rem!important;
            padding:1.05rem 1.2rem 1.08rem!important;
            border:1px solid rgba(80,108,136,.78)!important;
            border-radius:18px!important;
            background:
                radial-gradient(circle at 82% 0%,rgba(236,22,56,.08),transparent 18rem),
                linear-gradient(112deg,rgba(8,28,50,.99),rgba(5,19,35,.99))!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.045),0 18px 42px rgba(0,0,0,.30)!important;
        }
        .stApp .bt-hero::before,
        .stApp .ph-command-hero::before,
        .stApp .daily-command-hero::before,
        .stApp .tp-page-hero::before{
            content:""!important;
            position:absolute!important;
            left:0!important;
            top:0!important;
            bottom:0!important;
            width:4px!important;
            background:linear-gradient(#ff3655,#a60c29)!important;
            box-shadow:0 0 18px rgba(236,22,56,.20)!important;
        }
        .stApp .bt-kicker,
        .stApp .ph-command-kicker,
        .stApp .daily-command-kicker,
        .stApp .tp-page-kicker{
            color:#ff6a7d!important;
            font:900 .70rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;
            letter-spacing:.13em!important;
            text-transform:uppercase!important;
        }
        .stApp .bt-title,
        .stApp .ph-command-title,
        .stApp .daily-command-title,
        .stApp .tp-page-title{
            margin:.22rem 0 .28rem!important;
            color:#f5f1e9!important;
            font-family:Impact,"Arial Black","Arial Narrow",sans-serif!important;
            font-size:clamp(2.75rem,5vw,4.85rem)!important;
            font-weight:900!important;
            line-height:.86!important;
            letter-spacing:.012em!important;
            text-transform:uppercase!important;
            text-shadow:3px 4px 0 #07182b,0 0 22px rgba(236,22,56,.08)!important;
        }
        .stApp .bt-title span,
        .stApp .ph-command-title span,
        .stApp .daily-command-title span,
        .stApp .tp-page-title span{
            color:#ec1638!important;
            -webkit-text-stroke:1px #f1eee7!important;
            paint-order:stroke fill!important;
        }
        .stApp .bt-sub,
        .stApp .ph-command-sub,
        .stApp .daily-command-sub,
        .stApp .tp-page-sub{
            max-width:1180px!important;
            color:#c0ceda!important;
            font:650 .90rem/1.48 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;
        }
        .stApp .bt-rule,
        .stApp .ph-command-rule,
        .stApp .daily-command-rule,
        .stApp .tp-page-rule{
            width:max-content!important;
            max-width:100%!important;
            margin-top:.58rem!important;
            padding:.25rem .58rem!important;
            border-top:1px solid rgba(236,22,56,.65)!important;
            border-bottom:1px solid rgba(236,22,56,.65)!important;
            color:#edf3f7!important;
            font:900 .67rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;
            letter-spacing:.09em!important;
            text-transform:uppercase!important;
        }

        /* Projection-page red ribbon hierarchy, reused without changing content. */
        .stApp .bt-section,
        .stApp .history-section-head,
        .stApp .daily-section-head,
        .stApp .tp-section-ribbon{
            width:max-content!important;
            min-width:245px!important;
            max-width:92%!important;
            margin:1.05rem auto .62rem!important;
            padding:.44rem 1.65rem!important;
            border:1px solid #ff3151!important;
            border-bottom-color:#790b1d!important;
            border-radius:8px!important;
            background:linear-gradient(180deg,#f21b3d,#b70d29)!important;
            box-shadow:0 7px 16px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.22)!important;
            color:#fff!important;
            font:900 .90rem/1.15 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;
            letter-spacing:.04em!important;
            text-align:center!important;
            text-transform:uppercase!important;
        }

        /* Shared command-card depth and type scale. */
        .stApp [data-testid="stMetric"]{
            position:relative!important;
            overflow:hidden!important;
            min-height:110px!important;
            padding:.72rem .78rem!important;
            border:1px solid rgba(77,108,137,.72)!important;
            border-radius:14px!important;
            background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98))!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 12px 28px rgba(0,0,0,.24)!important;
        }
        .stApp [data-testid="stMetric"]::after{
            content:""!important;
            position:absolute!important;
            left:9%!important;
            right:9%!important;
            bottom:0!important;
            height:2px!important;
            background:linear-gradient(90deg,transparent,#ec1638,transparent)!important;
            opacity:.72!important;
        }
        .stApp [data-testid="stMetricLabel"]{
            color:#eef4f8!important;
            font-size:.80rem!important;
            font-weight:900!important;
            line-height:1.18!important;
            letter-spacing:.035em!important;
            text-transform:uppercase!important;
        }
        .stApp [data-testid="stMetricValue"]{
            color:#fff!important;
            font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;
            font-size:1.72rem!important;
            font-weight:900!important;
            line-height:1.08!important;
            letter-spacing:.005em!important;
        }
        .stApp [data-testid="stMetricDelta"]{font-weight:850!important}

        .stApp div[data-testid="stDataFrame"]{
            border:1px solid rgba(77,108,137,.64)!important;
            border-radius:14px!important;
            overflow:hidden!important;
            background:rgba(5,18,33,.78)!important;
            box-shadow:0 12px 28px rgba(0,0,0,.20)!important;
        }
        .stApp div[data-testid="stExpander"]{
            margin:.52rem 0!important;
            border:1px solid rgba(77,106,135,.68)!important;
            border-radius:14px!important;
            background:linear-gradient(145deg,rgba(8,28,50,.97),rgba(4,17,31,.98))!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.035),0 12px 28px rgba(0,0,0,.21)!important;
        }
        .stApp div[data-testid="stExpander"] summary{
            color:#f5f8fb!important;
            font-size:.93rem!important;
            font-weight:900!important;
            letter-spacing:.01em!important;
        }
        .stApp div[data-testid="stExpander"] [data-testid="stExpanderDetails"]{
            border-top:1px solid rgba(66,101,137,.34)!important;
        }

        .stApp div[data-testid="stButton"] button,
        .stApp div[data-testid="stDownloadButton"] button{
            min-height:2.7rem!important;
            border:1px solid rgba(87,120,154,.64)!important;
            border-radius:10px!important;
            background:linear-gradient(180deg,rgba(21,48,82,.96),rgba(12,30,56,.96))!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 7px 18px rgba(0,0,0,.15)!important;
            font-weight:900!important;
        }
        .stApp div[data-testid="stButton"] button:hover,
        .stApp div[data-testid="stDownloadButton"] button:hover{
            border-color:#ff3655!important;
            box-shadow:0 0 0 1px rgba(227,25,55,.12),0 9px 26px rgba(227,25,55,.12)!important;
        }
        .stApp div[data-testid="stButton"] button[kind="primary"]{
            border-color:#ff4560!important;
            background:linear-gradient(180deg,#f31b3d,#bc0d2b)!important;
            letter-spacing:.025em!important;
            text-transform:uppercase!important;
        }

        .stApp [data-testid="stForm"]{
            border:1px solid rgba(68,103,139,.56)!important;
            border-radius:15px!important;
            background:linear-gradient(145deg,rgba(10,28,52,.76),rgba(6,18,35,.76))!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.025),0 10px 28px rgba(0,0,0,.14)!important;
        }
        .stApp [data-testid="stSelectbox"] > div > div,
        .stApp [data-testid="stNumberInput"] input,
        .stApp [data-testid="stTextInput"] input,
        .stApp [data-testid="stDateInput"] input,
        .stApp [data-testid="stMultiSelect"] > div > div{
            border-color:rgba(68,103,139,.68)!important;
            border-radius:10px!important;
            background:rgba(8,23,43,.94)!important;
        }
        .stApp [data-testid="stCaptionContainer"]{
            color:#b8c8d6!important;
            font-size:.80rem!important;
            line-height:1.44!important;
        }
        .stApp div[data-testid="stMarkdownContainer"] p{
            color:#d7e1e9;
            line-height:1.48!important;
        }

        .stApp .stTabs [data-baseweb="tab-list"]{
            gap:.4rem!important;
            border-bottom-color:rgba(64,95,129,.5)!important;
        }
        .stApp .stTabs [data-baseweb="tab"]{
            border-radius:9px 9px 0 0!important;
            background:rgba(13,32,58,.56)!important;
            font-weight:850!important;
        }
        .stApp .stTabs [aria-selected="true"]{
            color:#fff!important;
            border-bottom-color:#ff3655!important;
            background:linear-gradient(180deg,rgba(227,25,55,.18),rgba(13,32,58,.72))!important;
        }

        /* Semantic status language mirrors the Projection page. */
        .stApp .bt-ticket-state.win .status,
        .stApp .tp-status.model{
            color:#58efad!important;
            border-color:rgba(50,229,141,.55)!important;
            background:rgba(8,79,52,.38)!important;
        }
        .stApp .bt-ticket-state.loss .status,
        .stApp .daily-run-status.error{
            color:#ff7085!important;
            border-color:rgba(255,71,98,.58)!important;
            background:rgba(125,13,36,.34)!important;
        }
        .stApp .bt-ticket-state.live .status{
            color:#8eddf4!important;
            border-color:rgba(74,191,230,.55)!important;
            background:rgba(10,65,83,.38)!important;
        }
        .stApp .bt-ticket-state.pending .status,
        .stApp .tp-status.watch{
            color:#ffe08a!important;
            border-color:rgba(255,209,102,.52)!important;
            background:rgba(98,71,8,.28)!important;
        }
        .stApp .daily-run-status.ok{
            border-color:rgba(50,229,141,.55)!important;
            box-shadow:0 0 0 1px rgba(50,229,141,.06)!important;
        }
        .stApp .history-primary-note,
        .stApp .daily-note{
            border:1px solid rgba(73,111,151,.56)!important;
            border-left:3px solid #ff3655!important;
            border-radius:13px!important;
            background:linear-gradient(110deg,rgba(10,34,59,.90),rgba(5,22,40,.92))!important;
            color:#d2dde6!important;
        }
        .stApp .daily-note.paid{
            border-color:rgba(250,204,21,.42)!important;
            border-left-color:#facc15!important;
            background:linear-gradient(110deg,rgba(88,65,8,.24),rgba(29,29,16,.52))!important;
            color:#e9dfb4!important;
        }

        /* Keep the shared current sidebar mascot/wordmark on every page. */
        .stApp [data-testid="stSidebar"] .sk-nav-mascot img{
            display:block!important;
            width:236px!important;
            height:236px!important;
            min-width:236px!important;
            object-fit:contain!important;
        }
        .stApp [data-testid="stSidebar"] .sk-nav-mascot::before{
            content:none!important;
            display:none!important;
        }

        /* Top Plays keeps its page-specific cards, normalized to the same depth. */
        .stApp [class*="st-key-top_play_card_"]{
            border-color:rgba(82,112,141,.78)!important;
            border-radius:16px!important;
            background:linear-gradient(150deg,rgba(10,34,59,.99),rgba(4,18,33,.99))!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.045),0 13px 30px rgba(0,0,0,.27)!important;
        }

        @media (max-width:1050px){
            .stApp .bt-title,
            .stApp .ph-command-title,
            .stApp .daily-command-title,
            .stApp .tp-page-title{font-size:3.25rem!important}
        }
        @media (max-width:760px){
            .stApp .block-container{
                padding-top:1rem!important;
                padding-left:.78rem!important;
                padding-right:.78rem!important;
            }
            .stApp .bt-hero,
            .stApp .ph-command-hero,
            .stApp .daily-command-hero,
            .stApp .tp-page-hero{padding:.82rem!important;border-radius:15px!important}
            .stApp .bt-title,
            .stApp .ph-command-title,
            .stApp .daily-command-title,
            .stApp .tp-page-title{font-size:2.65rem!important}
            .stApp .bt-rule,
            .stApp .ph-command-rule,
            .stApp .daily-command-rule,
            .stApp .tp-page-rule{font-size:.61rem!important;letter-spacing:.055em!important}
            .stApp .bt-section,
            .stApp .history-section-head,
            .stApp .daily-section-head,
            .stApp .tp-section-ribbon{min-width:180px!important;padding:.4rem 1rem!important;font-size:.82rem!important}
            .stApp [data-testid="stMetric"]{min-height:96px!important;padding:.62rem .68rem!important}
            .stApp [data-testid="stMetricValue"]{font-size:1.55rem!important}
            .stApp .bt-ticket-state{align-items:flex-start!important;flex-direction:column!important}
            .stApp .tp-market-row{align-items:flex-start!important;flex-direction:column!important}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

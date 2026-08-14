from __future__ import annotations

import streamlit as st

# Shared presentation layer only. This module must never own modeling logic,
# sportsbook calls, projection inputs, or grading semantics.
APP_UI_VERSION = "ui-cleveland-future-v3"


def apply_page_theme() -> None:
    """Apply the shared Cleveland-night futuristic presentation system."""
    st.markdown(
        """
        <style>
        :root {
            --sk-bg: #050d1a;
            --sk-bg-2: #08162a;
            --sk-panel: rgba(10, 27, 51, .86);
            --sk-panel-strong: rgba(12, 34, 64, .96);
            --sk-panel-soft: rgba(15, 39, 70, .62);
            --sk-border: rgba(72, 111, 153, .48);
            --sk-border-hot: rgba(227, 25, 55, .72);
            --sk-red: #e31937;
            --sk-red-bright: #ff3655;
            --sk-blue: #6fb7ff;
            --sk-text: #f7fbff;
            --sk-muted: #9db0c5;
            --sk-green: #24e69b;
            --sk-yellow: #facc15;
            --sk-shadow: 0 18px 50px rgba(0, 0, 0, .28);
        }

        html, body, [class*="css"] {
            font-feature-settings: "tnum" 1, "ss01" 1;
        }
        .stApp {
            background:
                radial-gradient(circle at 82% -8%, rgba(227,25,55,.12), transparent 30rem),
                radial-gradient(circle at 8% 18%, rgba(57,126,197,.09), transparent 28rem),
                linear-gradient(180deg, #071428 0%, var(--sk-bg) 38%, #040a14 100%) !important;
            color: var(--sk-text) !important;
        }
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: .14;
            background-image:
                linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px);
            background-size: 34px 34px;
            mask-image: linear-gradient(to bottom, black, transparent 72%);
        }

        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 5rem !important;
            max-width: 1480px !important;
        }
        h1 {
            letter-spacing: -0.045em !important;
            font-weight: 950 !important;
            margin-bottom: .18rem !important;
            line-height: 1.02 !important;
            text-shadow: 0 0 28px rgba(227,25,55,.11);
        }
        h1::after {
            content: "";
            display: block;
            width: 64px;
            height: 3px;
            margin-top: .55rem;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--sk-red-bright), rgba(227,25,55,0));
            box-shadow: 0 0 18px rgba(227,25,55,.42);
        }
        h2, h3 {
            letter-spacing: -0.022em !important;
            font-weight: 880 !important;
        }
        h2 { margin-top: 1.15rem !important; }

        [data-testid="stCaptionContainer"] {
            color: var(--sk-muted) !important;
            font-size: .91rem !important;
            line-height: 1.5 !important;
        }
        [data-testid="stMarkdownContainer"] p { line-height: 1.58; }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(7,20,38,.99), rgba(4,12,24,.99)) !important;
            border-right: 1px solid rgba(62,95,130,.48) !important;
            box-shadow: 12px 0 42px rgba(0,0,0,.14);
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] > div {
            gap: .28rem !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            border: 1px solid transparent;
            border-radius: 10px;
            padding: .42rem .55rem !important;
            transition: background .14s ease, border-color .14s ease;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
            background: rgba(227,25,55,.07);
            border-color: rgba(227,25,55,.22);
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
            background: linear-gradient(90deg, rgba(227,25,55,.22), rgba(19,43,71,.72));
            border-color: rgba(255,54,85,.44);
            box-shadow: inset 3px 0 0 var(--sk-red-bright);
        }

        [data-testid="stMetric"] {
            position: relative;
            background: linear-gradient(145deg, rgba(13,35,65,.96), rgba(7,22,42,.94)) !important;
            border: 1px solid var(--sk-border) !important;
            border-radius: 16px !important;
            padding: .88rem 1rem !important;
            min-height: 106px !important;
            box-shadow: 0 10px 30px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.025);
            overflow: hidden;
        }
        [data-testid="stMetric"]::before {
            content: "";
            position: absolute;
            left: 0; top: 0; bottom: 0;
            width: 3px;
            background: linear-gradient(180deg, var(--sk-red-bright), rgba(227,25,55,.12));
        }
        [data-testid="stMetricLabel"] {
            font-weight: 800 !important;
            color: #b8c9dc !important;
            letter-spacing: .015em;
        }
        [data-testid="stMetricValue"] {
            font-weight: 950 !important;
            letter-spacing: -.035em !important;
        }
        [data-testid="stMetricDelta"] { font-weight: 800 !important; }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--sk-border) !important;
            border-radius: 14px !important;
            overflow: hidden !important;
            box-shadow: 0 12px 28px rgba(0,0,0,.16);
            background: rgba(5,15,29,.58) !important;
        }
        [data-testid="stDataFrame"] [role="columnheader"] {
            font-weight: 850 !important;
            color: #e8f1fb !important;
        }

        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button {
            border-radius: 11px !important;
            min-height: 2.72rem !important;
            font-weight: 850 !important;
            border: 1px solid rgba(87,120,154,.6) !important;
            background: linear-gradient(180deg, rgba(21,48,82,.96), rgba(12,30,56,.96)) !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.05), 0 7px 18px rgba(0,0,0,.15);
            transition: transform .14s ease, border-color .14s ease, box-shadow .14s ease !important;
        }
        div[data-testid="stButton"] button:hover,
        div[data-testid="stDownloadButton"] button:hover {
            border-color: var(--sk-red-bright) !important;
            box-shadow: 0 0 0 1px rgba(227,25,55,.12), 0 9px 26px rgba(227,25,55,.12) !important;
            transform: translateY(-1px);
        }
        div[data-testid="stButton"] button[kind="primary"] {
            background: linear-gradient(135deg, #f02847, #b90f2b) !important;
            border-color: #ff4b66 !important;
            box-shadow: 0 10px 28px rgba(227,25,55,.22) !important;
        }

        div[data-testid="stExpander"] {
            border: 1px solid var(--sk-border) !important;
            border-radius: 14px !important;
            overflow: hidden !important;
            background: linear-gradient(145deg, rgba(10,28,52,.86), rgba(6,19,37,.84)) !important;
            box-shadow: 0 10px 28px rgba(0,0,0,.14);
        }
        div[data-testid="stExpander"] summary {
            font-weight: 850 !important;
            min-height: 3.1rem;
        }
        div[data-testid="stExpander"] summary:hover {
            color: #fff !important;
            background: rgba(227,25,55,.045) !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: .42rem !important;
            border-bottom-color: rgba(64,95,129,.5) !important;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 10px 10px 0 0 !important;
            font-weight: 850 !important;
            padding: .65rem 1rem !important;
            background: rgba(13,32,58,.55) !important;
        }
        .stTabs [aria-selected="true"] {
            color: #fff !important;
            background: linear-gradient(180deg, rgba(227,25,55,.18), rgba(13,32,58,.72)) !important;
            border-bottom-color: var(--sk-red-bright) !important;
        }

        [data-testid="stSelectbox"] > div > div,
        [data-testid="stNumberInput"] input,
        [data-testid="stTextInput"] input,
        [data-testid="stDateInput"] input,
        [data-testid="stMultiSelect"] > div > div {
            background: rgba(8,23,43,.92) !important;
            border-color: rgba(68,103,139,.68) !important;
            border-radius: 10px !important;
        }
        [data-testid="stTextInput"] input:focus,
        [data-testid="stNumberInput"] input:focus {
            border-color: var(--sk-red-bright) !important;
            box-shadow: 0 0 0 1px rgba(227,25,55,.18) !important;
        }

        [data-testid="stAlert"] {
            border-radius: 13px !important;
            border-width: 1px !important;
            box-shadow: 0 8px 22px rgba(0,0,0,.12);
        }
        [data-testid="stProgress"] > div > div > div { border-radius: 999px !important; }

        hr {
            border-color: rgba(49,82,116,.58) !important;
            margin: 1.5rem 0 !important;
        }

        .sok-callout, .sk-panel {
            background: linear-gradient(145deg, rgba(13,35,65,.93), rgba(7,22,42,.91));
            border: 1px solid var(--sk-border);
            border-radius: 16px;
            padding: 1rem 1.08rem;
            margin: .55rem 0 1rem 0;
            box-shadow: var(--sk-shadow);
        }
        .sk-panel-hot {
            border-color: rgba(227,25,55,.52);
            box-shadow: 0 14px 38px rgba(227,25,55,.09);
        }
        .sk-eyebrow {
            color: #b7c9dc;
            font-size: .72rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: .12em;
        }
        .sk-chip {
            display: inline-flex;
            align-items: center;
            gap: .3rem;
            padding: .25rem .55rem;
            border-radius: 999px;
            border: 1px solid rgba(84,116,151,.6);
            background: rgba(10,29,54,.85);
            color: #dce9f6;
            font-size: .75rem;
            font-weight: 800;
        }
        .sk-chip-hot {
            border-color: rgba(227,25,55,.58);
            color: #fff;
            background: rgba(227,25,55,.10);
        }

        /* Legacy Main Projection components are normalized here so the page
           follows the same hierarchy without altering projection behavior. */
        .king-title {
            font-size: clamp(2.6rem, 6vw, 4.4rem) !important;
            font-weight: 950 !important;
            line-height: .88 !important;
            letter-spacing: -.055em !important;
            text-align: left !important;
            margin: .35rem 0 .15rem !important;
            text-shadow: 0 0 34px rgba(227,25,55,.16) !important;
        }
        .king-red { color: var(--sk-red-bright) !important; }
        .subline {
            text-align: left !important;
            color: #aebfd2 !important;
            border: 0 !important;
            border-left: 3px solid var(--sk-red-bright) !important;
            padding: .3rem 0 .3rem .72rem !important;
            margin-bottom: 1rem !important;
            font-size: .74rem !important;
            font-weight: 850 !important;
            letter-spacing: .105em !important;
        }
        .pitcher-card {
            position: relative;
            background: linear-gradient(120deg, rgba(16,42,76,.96), rgba(7,22,42,.94)) !important;
            border: 1px solid rgba(76,112,151,.55) !important;
            border-radius: 18px !important;
            padding: 1rem 1.18rem !important;
            margin: .6rem 0 1rem !important;
            box-shadow: 0 16px 42px rgba(0,0,0,.20), inset 0 1px 0 rgba(255,255,255,.025) !important;
            overflow: hidden;
        }
        .pitcher-card::after {
            content: "";
            position: absolute;
            right: -36px;
            top: -36px;
            width: 130px;
            height: 130px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(227,25,55,.14), transparent 68%);
            pointer-events: none;
        }
        .pitcher-card h2 {
            margin: 0 0 .15rem !important;
            font-size: clamp(1.55rem, 3vw, 2.1rem) !important;
        }
        .section-head {
            background: transparent !important;
            border: 0 !important;
            border-bottom: 1px solid rgba(70,105,142,.52) !important;
            border-radius: 0 !important;
            padding: .55rem 0 .5rem !important;
            margin: 1.15rem 0 .75rem !important;
            text-align: left !important;
            font-size: .76rem !important;
            font-weight: 950 !important;
            letter-spacing: .115em !important;
            color: #dbe7f3 !important;
            position: relative;
        }
        .section-head::after {
            content: "";
            position: absolute;
            left: 0;
            bottom: -1px;
            width: 74px;
            height: 2px;
            background: linear-gradient(90deg, var(--sk-red-bright), rgba(227,25,55,0));
            box-shadow: 0 0 13px rgba(227,25,55,.3);
        }
        .metric-card, .reco-card, .panel {
            background: linear-gradient(145deg, rgba(13,35,65,.95), rgba(7,21,40,.94)) !important;
            border: 1px solid rgba(73,108,145,.54) !important;
            border-radius: 16px !important;
            box-shadow: 0 12px 32px rgba(0,0,0,.17), inset 0 1px 0 rgba(255,255,255,.025) !important;
        }
        .metric-card {
            padding: 1rem !important;
            min-height: 138px !important;
            text-align: left !important;
            border-top-color: rgba(227,25,55,.48) !important;
        }
        .metric-label, .reco-label {
            color: #aebfd2 !important;
            font-size: .73rem !important;
            font-weight: 900 !important;
            letter-spacing: .095em !important;
            text-transform: uppercase !important;
        }
        .metric-value {
            font-size: clamp(2.35rem, 5vw, 3.25rem) !important;
            font-weight: 950 !important;
            line-height: 1 !important;
            margin: .3rem 0 .55rem !important;
            letter-spacing: -.05em !important;
        }
        .reco-card {
            padding: 1rem !important;
            min-height: 138px !important;
            text-align: left !important;
        }
        .reco-side {
            font-size: clamp(1.65rem, 3.8vw, 2.3rem) !important;
            font-weight: 950 !important;
            margin-top: .35rem !important;
            line-height: 1 !important;
            letter-spacing: -.035em !important;
        }
        .reco-line { font-size: .94rem !important; margin-top: .42rem !important; }
        .reco-meta { color: #9fb3c7 !important; font-size: .76rem !important; margin-top: .35rem !important; }
        .reco-good { color: var(--sk-green) !important; }
        .reco-under { color: #ff5870 !important; }
        .reco-warn { color: var(--sk-yellow) !important; }
        .badge, .alt-k-badge {
            display: inline-flex !important;
            align-items: center !important;
            width: auto !important;
            max-width: 100% !important;
            border-radius: 999px !important;
            padding: .28rem .55rem !important;
            font-size: .68rem !important;
            font-weight: 900 !important;
            letter-spacing: .035em !important;
        }
        .badge {
            background: rgba(36,230,155,.075) !important;
            border: 1px solid rgba(36,230,155,.28) !important;
            color: #74efbd !important;
        }
        .alt-k-badge {
            margin: .45rem .25rem 0 0 !important;
            background: rgba(111,183,255,.075) !important;
            border: 1px solid rgba(111,183,255,.25) !important;
            color: #cce6ff !important;
        }
        .search-note { color: var(--sk-muted) !important; font-size: .79rem !important; }
        .market-ok { color: var(--sk-green) !important; font-weight: 850 !important; }
        .market-empty { color: var(--sk-muted) !important; }

        .sok-projection { color: var(--sk-green) !important; font-weight: 950 !important; }
        .sok-actual { color: var(--sk-yellow) !important; font-weight: 950 !important; }
        .sok-muted { color: var(--sk-muted) !important; }

        ::-webkit-scrollbar { width: 9px; height: 9px; }
        ::-webkit-scrollbar-track { background: #07101e; }
        ::-webkit-scrollbar-thumb {
            background: #294767;
            border-radius: 999px;
            border: 2px solid #07101e;
        }
        ::-webkit-scrollbar-thumb:hover { background: #405f7f; }

        @media (max-width: 900px) {
            .block-container {
                padding-top: 1.25rem !important;
                padding-left: .9rem !important;
                padding-right: .9rem !important;
            }
            [data-testid="stMetric"] { min-height: 94px !important; }
            h1 { font-size: 2.05rem !important; }
            h2 { font-size: 1.45rem !important; }
            .king-title { font-size: 2.8rem !important; }
            .metric-card, .reco-card { min-height: 118px !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

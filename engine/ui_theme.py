from __future__ import annotations

import streamlit as st

# Shared presentation layer only. This module must never own modeling logic,
# sportsbook calls, projection inputs, or grading semantics.
APP_UI_VERSION = "ui-cleveland-future-v2"


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
                linear-gradient(180deg, #071428 0%, var(--sk-bg) 38%, #040a14 100%);
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
        [data-testid="stMarkdownContainer"] p {
            line-height: 1.58;
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
            left: 0;
            top: 0;
            bottom: 0;
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
        [data-testid="stProgress"] > div > div > div {
            border-radius: 999px !important;
        }

        hr {
            border-color: rgba(49,82,116,.58) !important;
            margin: 1.5rem 0 !important;
        }

        .sok-callout,
        .sk-panel {
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
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

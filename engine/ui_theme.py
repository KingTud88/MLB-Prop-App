from __future__ import annotations

import streamlit as st

# Shared presentation layer only. This module must never own modeling logic,
# sportsbook calls, projection inputs, or grading semantics.
APP_UI_VERSION = "ui-readability-v1"


def apply_page_theme() -> None:
    """Apply a consistent high-contrast, projection-first visual hierarchy."""
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2.35rem !important;
            padding-bottom: 4rem !important;
            max-width: 1520px !important;
        }
        h1 {
            letter-spacing: -0.035em !important;
            font-weight: 900 !important;
            margin-bottom: .2rem !important;
        }
        h2, h3 {
            letter-spacing: -0.02em !important;
            font-weight: 850 !important;
        }
        [data-testid="stCaptionContainer"] {
            color: #9fb3c3 !important;
            font-size: .92rem !important;
            line-height: 1.45 !important;
        }
        [data-testid="stMetric"] {
            background: rgba(9, 27, 44, .90) !important;
            border: 1px solid #20425f !important;
            border-radius: 14px !important;
            padding: .8rem .95rem !important;
            min-height: 104px !important;
        }
        [data-testid="stMetricLabel"] {
            font-weight: 800 !important;
            color: #b9cddd !important;
        }
        [data-testid="stMetricValue"] {
            font-weight: 900 !important;
            letter-spacing: -.025em !important;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid #1e3b54 !important;
            border-radius: 12px !important;
            overflow: hidden !important;
        }
        [data-testid="stDataFrame"] [role="columnheader"] {
            font-weight: 850 !important;
        }
        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button {
            border-radius: 10px !important;
            min-height: 2.65rem !important;
            font-weight: 800 !important;
        }
        div[data-testid="stExpander"] {
            border: 1px solid #1d3b54 !important;
            border-radius: 12px !important;
            overflow: hidden !important;
        }
        div[data-testid="stExpander"] summary {
            font-weight: 800 !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: .35rem !important;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 9px 9px 0 0 !important;
            font-weight: 800 !important;
            padding-left: .9rem !important;
            padding-right: .9rem !important;
        }
        hr {
            border-color: #1b3851 !important;
            margin-top: 1.45rem !important;
            margin-bottom: 1.45rem !important;
        }
        .sok-callout {
            background: rgba(9, 27, 44, .90);
            border: 1px solid #20425f;
            border-radius: 14px;
            padding: .85rem 1rem;
            margin: .5rem 0 1rem 0;
        }
        .sok-projection {
            color: #24e69b !important;
            font-weight: 900 !important;
        }
        .sok-actual {
            color: #facc15 !important;
            font-weight: 900 !important;
        }
        .sok-muted {
            color: #8fa5b7 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

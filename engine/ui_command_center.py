from __future__ import annotations

import streamlit as st


COMMAND_CENTER_UI_VERSION = "cle-command-center-v1"


def apply_command_center_theme() -> None:
    """Layer the CLE command-center visual language on top of the shared theme.

    Presentation only: no projection inputs, market data, grading, or model logic.
    """
    st.markdown(
        """
        <style>
        :root {
            --cc-navy:#031327;
            --cc-navy-2:#071d35;
            --cc-panel:#0a2037;
            --cc-panel-2:#07182b;
            --cc-red:#ec1638;
            --cc-red-dark:#9f0c25;
            --cc-cream:#f1eee7;
            --cc-line:#36526d;
            --cc-green:#32e58d;
        }

        .stApp {
            background:
                radial-gradient(ellipse at 52% 4%, rgba(20,55,91,.48), transparent 36rem),
                linear-gradient(180deg, rgba(3,16,32,.98), rgba(2,11,22,.99)) !important;
        }
        .stApp::before {
            opacity:.22 !important;
            background-image:
                linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px),
                radial-gradient(ellipse at 50% 34%, transparent 0 36%, rgba(0,0,0,.22) 64%, rgba(0,0,0,.54) 100%) !important;
            background-size:32px 32px,32px 32px,100% 100% !important;
        }
        .block-container { max-width:1520px !important; }

        h1,h2,h3,.section-head,.metric-label,.reco-label {
            font-family:Impact,"Arial Narrow",Haettenschweiler,sans-serif !important;
            text-transform:uppercase;
        }
        h1 { color:var(--cc-cream)!important; text-shadow:2px 3px 0 rgba(0,0,0,.38),0 0 22px rgba(236,22,56,.12)!important; }

        .king-title {
            font-size:clamp(3.4rem,7vw,6.5rem)!important;
            line-height:.78!important;
            letter-spacing:.01em!important;
            color:var(--cc-cream)!important;
            text-transform:uppercase!important;
            text-shadow:3px 4px 0 #07182b,0 0 26px rgba(236,22,56,.12)!important;
        }
        .king-title .king-red,.king-red { color:var(--cc-red)!important; }
        .subline {
            border-left:0!important;
            border-top:1px solid rgba(236,22,56,.6)!important;
            border-bottom:1px solid rgba(236,22,56,.6)!important;
            text-align:center!important;
            padding:.45rem .7rem!important;
            font-family:Impact,"Arial Narrow",sans-serif!important;
            font-size:.86rem!important;
            letter-spacing:.16em!important;
            color:#f3f6f9!important;
            background:linear-gradient(90deg,transparent,rgba(236,22,56,.08),transparent)!important;
        }

        .pitcher-card,.panel,.metric-card,.reco-card,[data-testid="stMetric"],div[data-testid="stExpander"] {
            background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98))!important;
            border:1px solid rgba(80,108,136,.72)!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 14px 32px rgba(0,0,0,.28)!important;
        }
        .pitcher-card {
            border-radius:18px!important;
            border-color:rgba(93,119,146,.78)!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 16px 36px rgba(0,0,0,.3)!important;
        }

        .section-head {
            position:relative;
            width:max-content;
            min-width:250px;
            max-width:90%;
            margin:0 auto -2px!important;
            padding:.45rem 2.2rem!important;
            color:#fff!important;
            background:linear-gradient(180deg,#f21b3d,#b70d29)!important;
            border:1px solid #ff3151!important;
            border-bottom-color:#790b1d!important;
            border-radius:8px 8px 2px 2px!important;
            box-shadow:0 7px 16px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.22)!important;
            letter-spacing:.055em!important;
            text-align:center!important;
        }
        .section-head::before,.section-head::after {
            content:"";
            position:absolute;
            top:7px;
            width:18px;
            height:calc(100% - 8px);
            background:linear-gradient(180deg,#c70f2f,#8b091f);
            border:1px solid #ff3151;
            z-index:-1;
        }
        .section-head::before { left:-13px; transform:skewX(-18deg); }
        .section-head::after { right:-13px; transform:skewX(18deg); }

        .metric-card,.reco-card {
            border-radius:15px!important;
            min-height:168px!important;
            position:relative;
            overflow:hidden;
        }
        .metric-card::after,.reco-card::after,[data-testid="stMetric"]::after {
            content:"";
            position:absolute;
            left:0;right:0;bottom:0;height:2px;
            background:linear-gradient(90deg,transparent,var(--cc-red),transparent);
            opacity:.72;
        }
        .metric-label,.reco-label {
            color:#eef3f7!important;
            letter-spacing:.035em!important;
            font-size:1rem!important;
        }
        .metric-value,.reco-side,[data-testid="stMetricValue"] {
            font-family:Impact,"Arial Narrow",sans-serif!important;
            color:#f5f1e9!important;
            text-shadow:2px 3px 0 rgba(0,0,0,.3)!important;
            letter-spacing:.015em!important;
        }
        .metric-value { font-size:3.7rem!important; }
        .badge {
            background:#073b27!important;
            border-color:#0d7650!important;
            color:#4bf0a7!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.05)!important;
        }

        [data-testid="stDataFrame"] {
            border-radius:12px!important;
            border-color:rgba(74,101,128,.72)!important;
            box-shadow:0 15px 34px rgba(0,0,0,.23)!important;
        }
        [data-testid="stDataFrame"] [role="columnheader"] {
            font-family:Impact,"Arial Narrow",sans-serif!important;
            text-transform:uppercase!important;
            letter-spacing:.04em!important;
            background:#0b2139!important;
        }

        div[data-testid="stButton"] button[kind="primary"] {
            background:linear-gradient(180deg,#f21b3d,#b70d29)!important;
            border-color:#ff3b59!important;
            font-family:Impact,"Arial Narrow",sans-serif!important;
            text-transform:uppercase!important;
            letter-spacing:.045em!important;
        }

        .sk-panel,.sok-callout {
            border-color:rgba(78,106,133,.72)!important;
            background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98))!important;
        }
        .sk-panel-hot { border-color:rgba(236,22,56,.9)!important; }

        @media (max-width:900px) {
            .king-title { font-size:3.15rem!important; line-height:.84!important; }
            .section-head { min-width:190px; padding:.4rem 1.45rem!important; }
            .metric-value { font-size:3rem!important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

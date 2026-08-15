from __future__ import annotations

from datetime import datetime
from pathlib import Path
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st


COMMAND_CENTER_UI_VERSION = "cle-command-center-v7"
ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
MASCOT_PATH = ASSET_DIR / "strikeout_king_9000_clean.png"
EASTERN = ZoneInfo("America/New_York")


def _safe(value: object) -> str:
    return escape(str(value if value is not None else "—"))


def _game_time_text(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Time TBD"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(EASTERN)
        return parsed.strftime("%I:%M %p ET").lstrip("0")
    except Exception:
        return raw


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
            --cc-yellow:#ffd166;
            --cc-muted:#92a9bd;
            --cc-ui-font:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
        }

        .stApp {
            background:
                radial-gradient(ellipse at 52% 4%, rgba(20,55,91,.48), transparent 36rem),
                radial-gradient(ellipse at 50% 54%, rgba(7,39,70,.30), transparent 42rem),
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

        .stApp,[data-testid="stSidebar"],[data-testid="stMarkdownContainer"],
        [data-testid="stCaptionContainer"],button,input,label {
            font-family:var(--cc-ui-font)!important;
            -webkit-font-smoothing:antialiased;
            -moz-osx-font-smoothing:grayscale;
            text-rendering:optimizeLegibility;
        }
        [data-testid="stCaptionContainer"],.reco-meta,.search-note {
            font-family:var(--cc-ui-font)!important;
            font-size:.86rem!important;
            line-height:1.45!important;
            letter-spacing:0!important;
            text-shadow:none!important;
        }

        h1,.section-head,.cc-hero-title,.cc-team-mark {
            font-family:Impact,"Arial Narrow",Haettenschweiler,sans-serif !important;
            text-transform:uppercase;
        }
        h2,h3,.metric-label,.reco-label,.cc-status-label,.cc-matchup-name,
        .cc-matchup-status-label,[data-testid="stDataFrame"] [role="columnheader"] {
            font-family:var(--cc-ui-font) !important;
            text-transform:uppercase;
            font-weight:800 !important;
            letter-spacing:.025em !important;
            text-shadow:none !important;
        }
        h1 { color:var(--cc-cream)!important; text-shadow:2px 3px 0 rgba(0,0,0,.38),0 0 22px rgba(236,22,56,.12)!important; }

        .st-key-cc_hero_shell {
            position:relative;
            min-height:245px;
            padding:1.25rem 1.4rem!important;
            margin:.15rem 0 1.1rem;
            overflow:hidden;
            border:1px solid rgba(82,108,134,.74)!important;
            border-radius:18px!important;
            background:
                linear-gradient(90deg,rgba(4,19,36,.96),rgba(6,29,53,.94) 52%,rgba(4,17,32,.97)),
                radial-gradient(circle at 30% 0%,rgba(236,22,56,.13),transparent 22rem)!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 20px 52px rgba(0,0,0,.34);
        }
        .st-key-cc_hero_shell::before {
            content:"";
            position:absolute;
            inset:auto 0 0;
            height:3px;
            background:linear-gradient(90deg,transparent,var(--cc-red) 18%,var(--cc-red) 82%,transparent);
            box-shadow:0 0 18px rgba(236,22,56,.42);
        }
        .st-key-cc_hero_shell::after {
            content:"";
            position:absolute;
            inset:0;
            pointer-events:none;
            opacity:.20;
            background:
                repeating-linear-gradient(90deg,transparent 0 46px,rgba(255,255,255,.025) 47px,transparent 48px),
                linear-gradient(0deg,rgba(255,255,255,.015),transparent 45%);
            mask-image:linear-gradient(to bottom,transparent,black 28%,black 100%);
        }
        .st-key-cc_hero_shell [data-testid="stImage"] { display:flex;align-items:center;justify-content:center; }
        .st-key-cc_hero_shell [data-testid="stImage"] img {
            display:block;
            max-height:218px;
            object-fit:contain;
            filter:drop-shadow(0 14px 18px rgba(0,0,0,.42)) drop-shadow(0 0 18px rgba(236,22,56,.12));
        }
        .cc-hero-fallback {
            width:180px;
            height:180px;
            margin:auto;
            display:flex;
            flex-direction:column;
            align-items:center;
            justify-content:center;
            border-radius:50%;
            border:3px solid rgba(236,22,56,.78);
            background:radial-gradient(circle at 35% 30%,#173e69,#07182b 68%);
            box-shadow:inset 0 0 0 6px rgba(255,255,255,.025),0 14px 28px rgba(0,0,0,.38),0 0 20px rgba(236,22,56,.15);
            color:#fff;
            font-family:Impact,"Arial Narrow",Haettenschweiler,sans-serif;
            font-size:2.55rem;
            line-height:.9;
            letter-spacing:.035em;
            text-align:center;
        }
        .cc-hero-fallback span {
            margin-top:.35rem;
            color:var(--cc-red);
            font-family:var(--cc-ui-font);
            font-size:.68rem;
            font-weight:900;
            letter-spacing:.12em;
        }
        .cc-hero-copy { position:relative;z-index:1;min-width:0; }
        .cc-hero-kicker {
            color:#d8e3ed;
            font-family:var(--cc-ui-font);
            font-size:.78rem;
            font-weight:900;
            letter-spacing:.18em;
            text-transform:uppercase;
            margin-bottom:.35rem;
        }
        .cc-hero-title {
            color:var(--cc-cream);
            font-size:clamp(3.25rem,6vw,6.55rem);
            line-height:.78;
            letter-spacing:.01em;
            text-shadow:3px 4px 0 #07182b,0 0 26px rgba(236,22,56,.12);
            white-space:nowrap;
        }
        .cc-hero-title span { color:var(--cc-red);display:block; }
        .cc-hero-sub {
            display:inline-flex;
            align-items:center;
            gap:.45rem;
            margin-top:.8rem;
            padding:.4rem .75rem;
            border-top:1px solid rgba(236,22,56,.58);
            border-bottom:1px solid rgba(236,22,56,.58);
            color:#f3f6f9;
            background:linear-gradient(90deg,transparent,rgba(236,22,56,.08),transparent);
            font-family:var(--cc-ui-font);
            font-weight:800;
            font-size:.84rem;
            letter-spacing:.08em;
            text-transform:uppercase;
        }
        .cc-hero-status { position:relative;z-index:1;display:grid;gap:.7rem; }
        .cc-status-card {
            padding:.78rem .85rem;
            border:1px solid rgba(91,119,146,.68);
            border-radius:13px;
            background:linear-gradient(145deg,rgba(10,33,57,.95),rgba(5,20,36,.96));
            box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 10px 24px rgba(0,0,0,.22);
        }
        .cc-status-label { color:#e8eef4;font-size:.80rem;letter-spacing:.045em; }
        .cc-status-value { margin-top:.18rem;color:#fff;font-weight:900;font-size:1rem; }
        .cc-status-value.live { color:var(--cc-green); }
        .cc-status-meta { margin-top:.18rem;color:#a8bacb;font-family:var(--cc-ui-font);font-size:.82rem;line-height:1.42; }
        .cc-quality-track { height:5px;margin-top:.55rem;border-radius:999px;background:rgba(45,70,95,.7);overflow:hidden; }
        .cc-quality-fill { height:100%;border-radius:999px;background:linear-gradient(90deg,var(--cc-red),#ff4762);box-shadow:0 0 12px rgba(236,22,56,.35); }

        .cc-matchup-strip {
            display:grid;
            grid-template-columns:auto 1fr minmax(185px,260px);
            gap:1.05rem;
            align-items:center;
            padding:1rem 1.15rem;
            margin:.2rem 0 1.3rem;
            border:1px solid rgba(80,108,136,.76);
            border-radius:16px;
            background:linear-gradient(110deg,rgba(8,28,50,.98),rgba(5,20,37,.98));
            box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 14px 34px rgba(0,0,0,.28);
        }
        .cc-team-mark {
            display:flex;
            align-items:center;
            justify-content:center;
            width:78px;
            height:78px;
            border-radius:50%;
            color:#fff;
            font-size:1.55rem;
            letter-spacing:.035em;
            border:2px solid rgba(236,22,56,.72);
            background:radial-gradient(circle at 35% 30%,#173e69,#07182b 66%);
            box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 10px 22px rgba(0,0,0,.28);
        }
        .cc-matchup-name { color:var(--cc-cream);font-size:clamp(1.7rem,3vw,2.55rem);line-height:.95;letter-spacing:.015em; }
        .cc-matchup-vs { margin-top:.38rem;color:#fff;font-weight:900;font-size:1rem; }
        .cc-matchup-vs strong { color:var(--cc-red); }
        .cc-matchup-meta { margin-top:.32rem;color:#b7c6d3;font-family:var(--cc-ui-font);font-size:.90rem; }
        .cc-matchup-status {
            padding-left:1.05rem;
            border-left:1px solid rgba(76,104,132,.54);
        }
        .cc-matchup-status-label { color:var(--cc-green);font-family:var(--cc-ui-font);font-size:.86rem;font-weight:800;letter-spacing:.025em;text-transform:uppercase; }
        .cc-matchup-status-time { margin-top:.32rem;color:#fff;font-weight:900;font-size:1rem; }
        .cc-matchup-status-meta { margin-top:.28rem;color:#afc0cf;font-family:var(--cc-ui-font);font-size:.84rem; }
        .cc-lock-pill {
            display:inline-flex;
            align-items:center;
            margin-top:.48rem;
            padding:.23rem .52rem;
            border-radius:999px;
            border:1px solid rgba(82,115,148,.62);
            background:rgba(10,30,52,.82);
            color:#dce7f0;
            font-size:.76rem;
            font-weight:800;
            letter-spacing:.02em;
            text-transform:uppercase;
        }
        .cc-lock-pill.locked { border-color:rgba(50,229,141,.42);color:#73f1b4;background:rgba(9,64,44,.38); }

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
            font-family:var(--cc-ui-font)!important;
            font-size:.92rem!important;
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

        .cc-card-top { display:flex;align-items:center;justify-content:center;gap:.72rem;margin-bottom:.32rem; }
        .cc-card-icon {
            width:48px;height:48px;flex:0 0 48px;border-radius:50%;display:flex;align-items:center;justify-content:center;
            border:2px solid rgba(236,22,56,.72);background:radial-gradient(circle at 35% 30%,#183e68,#07182b 68%);
            color:#fff;font-family:Impact,"Arial Narrow",sans-serif;font-size:1.18rem;letter-spacing:.02em;
            box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 8px 18px rgba(0,0,0,.28);
        }
        .cc-card-icon.ball { font-family:var(--cc-ui-font);font-size:1.4rem; }
        .cc-card-icon.hit { color:#ff6a7d; }
        .cc-team-logo { overflow:hidden;background:radial-gradient(circle at 35% 30%,#122e50,#061426 72%); }
        .cc-team-logo img { width:66px;height:66px;object-fit:contain;display:block;filter:drop-shadow(0 5px 10px rgba(0,0,0,.28)); }

        .cc-sidebar-brand {
            padding:.85rem .7rem .8rem;margin:.1rem 0 .8rem;border:1px solid rgba(78,108,137,.66);border-radius:14px;
            background:linear-gradient(145deg,rgba(8,29,51,.98),rgba(3,16,30,.98));text-align:center;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 12px 26px rgba(0,0,0,.20);
        }
        .cc-sidebar-crown { color:var(--cc-red);font-size:1.2rem;line-height:1; }
        .cc-sidebar-script { color:#f5f1e9;font-family:Georgia,"Times New Roman",serif;font-size:1.55rem;font-weight:800;font-style:italic;line-height:.95; }
        .cc-sidebar-king { color:var(--cc-red);font-family:Impact,"Arial Narrow",sans-serif;font-size:1.42rem;letter-spacing:.035em;line-height:1.0;text-transform:uppercase; }
        .cc-sidebar-tag { margin-top:.38rem;color:#9fb3c5;font-family:var(--cc-ui-font);font-size:.78rem;line-height:1.35; }
        .cc-sidebar-pitcher {
            display:flex;align-items:center;gap:.65rem;padding:.58rem .62rem;margin:.45rem 0 .62rem;border:1px solid rgba(63,100,134,.72);
            border-radius:12px;background:linear-gradient(145deg,rgba(9,31,55,.96),rgba(5,19,35,.96));
        }
        .cc-sidebar-pitcher-logo { width:42px;height:42px;flex:0 0 42px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#07182b;overflow:hidden; }
        .cc-sidebar-pitcher-logo img { width:38px;height:38px;object-fit:contain; }
        .cc-sidebar-pitcher-name { color:#f4f7fa;font-family:var(--cc-ui-font);font-size:.86rem;font-weight:800;line-height:1.15; }
        .cc-sidebar-pitcher-meta { margin-top:.15rem;color:#9fb2c4;font-family:var(--cc-ui-font);font-size:.74rem;line-height:1.25; }

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
            letter-spacing:.02em!important;
            font-size:.92rem!important;
            line-height:1.30!important;
            font-family:var(--cc-ui-font)!important;
            font-weight:800!important;
            text-shadow:none!important;
        }

        /* Lower command-center modules: presentation only. */
        .st-key-cc_bet_action_panel,
        .st-key-cc_market_command_row,
        .st-key-cc_parlay_panel {
            position:relative;
            padding:1rem 1.05rem!important;
            border:1px solid rgba(76,111,145,.78)!important;
            border-radius:16px!important;
            background:linear-gradient(145deg,rgba(8,29,52,.98),rgba(4,17,32,.98))!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.045),0 16px 34px rgba(0,0,0,.27)!important;
        }
        .st-key-cc_bet_action_panel { margin-bottom:1rem;border-color:rgba(236,22,56,.46)!important; }
        .st-key-cc_bet_action_panel::after,
        .st-key-cc_market_command_row::after,
        .st-key-cc_parlay_panel::after {
            content:"";position:absolute;left:10%;right:10%;bottom:0;height:2px;
            background:linear-gradient(90deg,transparent,var(--cc-red),transparent);opacity:.65;pointer-events:none;
        }
        .st-key-cc_bet_action_panel [data-testid="stNumberInput"] { max-width:100%; }
        .st-key-cc_bet_action_panel div[data-testid="stButton"] button {
            min-height:3rem!important;border-color:rgba(97,132,166,.72)!important;
            background:linear-gradient(180deg,rgba(22,53,88,.98),rgba(10,30,55,.98))!important;font-weight:900!important;
        }
        .st-key-cc_market_command_row { margin-top:.2rem;margin-bottom:1.15rem; }
        .st-key-cc_market_command_row [data-testid="stDataFrame"] { border-color:rgba(69,103,139,.82)!important;box-shadow:none!important; }
        .st-key-cc_market_command_row [data-testid="stCaptionContainer"] { color:#9fb2c5!important; }
        .st-key-cc_parlay_panel { margin-bottom:1rem; }
        @media (max-width:760px) {
            .st-key-cc_bet_action_panel,.st-key-cc_market_command_row,.st-key-cc_parlay_panel { padding:.8rem!important; }
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
            font-family:var(--cc-ui-font)!important;
            font-weight:800!important;
            text-transform:uppercase!important;
            letter-spacing:.02em!important;
            background:#0b2139!important;
        }

        div[data-testid="stButton"] button[kind="primary"] {
            background:linear-gradient(180deg,#f21b3d,#b70d29)!important;
            border-color:#ff3b59!important;
            font-family:var(--cc-ui-font)!important;
            text-transform:uppercase!important;
            letter-spacing:.045em!important;
        }

        .sk-panel,.sok-callout {
            border-color:rgba(78,106,133,.72)!important;
            background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98))!important;
        }
        .sk-panel-hot { border-color:rgba(236,22,56,.9)!important; }

        @media (max-width:1050px) {
            .st-key-cc_hero_shell [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
            .cc-hero-status { grid-template-columns:repeat(3,1fr); }
            .cc-hero-title { white-space:normal; }
        }
        @media (max-width:900px) {
            .king-title { font-size:3.15rem!important; line-height:.84!important; }
            .section-head { min-width:190px; padding:.4rem 1.45rem!important; }
            .metric-value { font-size:3rem!important; }
            .st-key-cc_hero_shell { min-height:0;padding:1rem!important; }
            .st-key-cc_hero_shell [data-testid="stImage"] img { max-height:135px; }
            .cc-hero-title { font-size:3rem; }
            .cc-hero-status { grid-template-columns:1fr; }
            .cc-matchup-strip { grid-template-columns:auto 1fr; }
            .cc-matchup-status { grid-column:1 / -1;border-left:0;border-top:1px solid rgba(76,104,132,.54);padding:.75rem 0 0; }
        }
        @media (max-width:620px) {
            .st-key-cc_hero_shell { text-align:center; }
            .cc-hero-fallback { width:140px;height:140px;font-size:2rem; }
            .cc-hero-sub { justify-content:center; }
            .cc-matchup-strip { grid-template-columns:1fr;text-align:center; }
            .cc-team-mark { margin:0 auto; }
            .cc-matchup-status { text-align:center; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _team_logo_url(team_id: int | None) -> str:
    try:
        value = int(team_id or 0)
    except (TypeError, ValueError):
        value = 0
    return f"https://www.mlbstatic.com/team-logos/{value}.svg" if value > 0 else ""


def render_sidebar_brand() -> None:
    st.markdown(
        '<div class="cc-sidebar-brand"><div class="cc-sidebar-crown">♛</div>'
        '<div class="cc-sidebar-script">StrikeOut</div><div class="cc-sidebar-king">King 9000</div>'
        '<div class="cc-sidebar-tag">CLE-themed MLB starter projection engine</div></div>',
        unsafe_allow_html=True,
    )


def render_sidebar_pitcher_identity(*, pitcher_name: str, team: str, opponent: str, team_id: int = 0) -> None:
    logo = _team_logo_url(team_id)
    logo_html = (
        f'<img src="{logo}" alt="{_safe(team)} logo" loading="lazy">'
        if logo else f'<span>{_safe(team)}</span>'
    )
    st.markdown(
        f'<div class="cc-sidebar-pitcher"><div class="cc-sidebar-pitcher-logo">{logo_html}</div>'
        f'<div><div class="cc-sidebar-pitcher-name">{_safe(pitcher_name)}</div>'
        f'<div class="cc-sidebar-pitcher-meta">{_safe(team)} vs {_safe(opponent)}</div></div></div>',
        unsafe_allow_html=True,
    )


def render_command_center_hero(*, confidence: str, quality: int, locked: bool, app_version: str) -> None:
    """Render the branded top-of-page hero/status board for Main Projection."""
    safe_confidence = _safe(confidence or "Unknown")
    safe_version = _safe(app_version)
    quality_value = max(0, min(100, int(quality or 0)))
    lock_text = "Projection locked" if locked else "Ready to lock"
    lock_meta = "Frozen pitcher snapshot" if locked else "Use the left rail to freeze outputs"

    with st.container(border=False, key="cc_hero_shell"):
        mascot_col, copy_col, status_col = st.columns([1.15, 3.25, 1.45], gap="medium", vertical_alignment="center")
        with mascot_col:
            try:
                st.image(str(MASCOT_PATH), width=190)
            except Exception:
                st.markdown(
                    '<div class="cc-hero-fallback" aria-label="StrikeOut King 9000">SK9K<span>STRIKEOUT KING</span></div>',
                    unsafe_allow_html=True,
                )
        with copy_col:
            st.markdown(
                """
                <div class="cc-hero-copy">
                  <div class="cc-hero-kicker">Built for CLE baseball · two-path starter intelligence</div>
                  <div class="cc-hero-title">StrikeOut <span>King 9000</span></div>
                  <div class="cc-hero-sub">★ MLB Pitcher Projection Engine ★ Two-Path Analytics ★</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with status_col:
            st.markdown(
                f"""
                <div class="cc-hero-status">
                  <div class="cc-status-card">
                    <div class="cc-status-label">Data Status</div>
                    <div class="cc-status-value live">● Live</div>
                    <div class="cc-status-meta">{safe_confidence} confidence · model quality {quality_value}/100</div>
                    <div class="cc-quality-track"><div class="cc-quality-fill" style="width:{quality_value}%"></div></div>
                  </div>
                  <div class="cc-status-card">
                    <div class="cc-status-label">Pitcher State</div>
                    <div class="cc-status-value">{_safe(lock_text)}</div>
                    <div class="cc-status-meta">{_safe(lock_meta)}</div>
                  </div>
                  <div class="cc-status-card">
                    <div class="cc-status-label">Engine</div>
                    <div class="cc-status-value">v{safe_version}</div>
                    <div class="cc-status-meta">Model first · market second</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_matchup_strip(
    *,
    pitcher_name: str,
    team: str,
    opponent: str,
    venue: str,
    side: str,
    status: str,
    game_time: object,
    locked: bool,
    weather_icon: str = "",
    team_id: int = 0,
) -> None:
    """Render the matchup strip without changing any projection state."""
    lock_class = "cc-lock-pill locked" if locked else "cc-lock-pill"
    lock_label = "🔒 Locked" if locked else "◇ Unlocked"
    weather = f" {_safe(weather_icon)}" if weather_icon else ""
    logo = _team_logo_url(team_id)
    team_mark = (
        f'<div class="cc-team-mark cc-team-logo"><img src="{logo}" alt="{_safe(team)} logo" loading="lazy"></div>'
        if logo else f'<div class="cc-team-mark">{_safe(team)}</div>'
    )
    st.markdown(
        f"""
        <div class="cc-matchup-strip">
          {team_mark}
          <div>
            <div class="cc-matchup-name">{_safe(pitcher_name)}{weather}</div>
            <div class="cc-matchup-vs">{_safe(team)} <strong>vs</strong> {_safe(opponent)}</div>
            <div class="cc-matchup-meta">⚾ {_safe(venue)} · {_safe(side)}</div>
          </div>
          <div class="cc-matchup-status">
            <div class="cc-matchup-status-label">Game Status</div>
            <div class="cc-matchup-status-time">◫ {_safe(_game_time_text(game_time))}</div>
            <div class="cc-matchup-status-meta">{_safe(status)} · {_safe(side)}</div>
            <div class="{lock_class}">{_safe(lock_label)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

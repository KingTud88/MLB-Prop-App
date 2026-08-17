from __future__ import annotations
import hashlib, math, os, re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

from engine.ui_theme import apply_page_theme
from engine.explainability_ui import (
    Explanation, apply_explainability_theme, explain_popover, leg_explanation,
    projection_metric_explanation, recommendation_explanation, static_explanation,
    ticket_explanation, top_play_explanation, weather_explanation,
)
from engine.ui_command_center import (
    apply_command_center_theme,
    render_command_center_hero,
    render_matchup_strip,
)
try:
    from engine.ui_command_center import render_sidebar_brand, render_sidebar_pitcher_identity
except ImportError:
    # Streamlit Cloud can briefly run a new page file beside a cached older UI
    # helper during deploy. Keep the app bootable until the worker fully syncs.
    def render_sidebar_brand() -> None:
        st.markdown("## StrikeOut King 9000")
        st.caption("CLE-themed MLB starter projection engine")

    def render_sidebar_pitcher_identity(*, pitcher_name: str, team: str, opponent: str, team_id: int = 0) -> None:
        st.caption(f"{pitcher_name} · {team} vs {opponent}")

from engine.calibration import PROBABILITY_SEMANTICS, calibrate_blend, calibration_summary, milestone_calibration_report
from engine.projection_engine import ProjectionEngine, ProjectionResult
from engine.hits_allowed import project_hits_allowed
from engine.hits_calibration import calibrate_hits_blend
from engine.outs_projection import project_total_outs, OutsProjection
from engine.outs_calibration import calibrate_outs_blend
from engine.starter_history import TARGET_STARTER_HISTORY, combine_starter_history, starter_only
from engine.opposing_batters import get_opposing_batters, matchup_summary
from engine.lineup_context import LINEUP_CONFIRMED, get_confirmed_lineup
from engine.weather_risk import WeatherDelayRisk, apply_roof_protection, fetch_weather_delay_risk
from engine.workload_context import WorkloadContext, build_workload_context
from engine.role_workload_gate import build_role_workload_decision
from engine.team_leash import build_team_leash_context, candidate_workload_fields
from engine.ml_shadow_ui import render_ml_shadow_dashboard
from engine.bet_lean import aligned_bet_lean
from engine.alt_k import best_alt_k
from engine.odds_snapshot import load_pitcher_strikeout_odds
from engine.bet_tracker import make_bet_record, make_parlay_record
from training.bet_storage import append_bet
from training.projection_storage import load_projection_archive, overlay_manual_market_lines

APP_VERSION = "3.7.0"
EASTERN = ZoneInfo("America/New_York")
MLB_API = "https://statsapi.mlb.com/api/v1"
APP_DIR = Path(__file__).resolve().parent
BET_LOG = APP_DIR / "data" / "bet_log.csv"
ARCHIVE_PATH = APP_DIR / "data" / "projection_archive.csv"
OBS_LOG = APP_DIR / "data" / "starter_observation_log.csv"
TEAM_ABBR = {108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSH",121:"NYM",133:"ATH",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",147:"NYY",158:"MIL"}
TEAM_ID_BY_ABBR = {abbr: team_id for team_id, abbr in TEAM_ABBR.items()}
PARK_K_FACTOR = {"Coors Field":.94,"T-Mobile Park":1.05,"Petco Park":1.03,"Oracle Park":1.02,"Dodger Stadium":1.01,"Yankee Stadium":.99,"Fenway Park":.98,"Wrigley Field":1.00}

st.set_page_config(page_title="StrikeOut King 9000", page_icon="⚾", layout="wide", initial_sidebar_state="expanded")
apply_page_theme()
apply_command_center_theme()
apply_explainability_theme()
st.markdown("""<style>
:root{--bg:#06111d;--panel:#0b1c2e;--line:#1b3851;--red:#f0193c;--green:#24e69b;--ink:#f2f6fa;--muted:#8fa5b7}
.stApp{background:linear-gradient(145deg,#04101b,#091a2a);color:var(--ink)}
[data-testid="stSidebar"]{background:#071727;border-right:1px solid #18334b}
.block-container{padding-top:3.25rem;max-width:1500px}
h1,h2,h3{letter-spacing:-.02em}
.king-title{font-size:4rem;font-weight:900;line-height:.9;text-align:center}.king-red{color:var(--red)}
.subline{text-align:center;color:#fff;border-bottom:2px solid var(--red);padding-bottom:10px;font-weight:800;letter-spacing:.12em}
.pitcher-card,.metric-card,.panel{background:rgba(9,27,44,.94);border:1px solid #20425f;border-radius:16px}.pitcher-card{padding:18px 24px}
.section-head{background:linear-gradient(90deg,#ed1236,#f0193c);padding:9px 16px;border-radius:14px 14px 0 0;text-align:center;font-weight:900;letter-spacing:.08em}
.metric-card{padding:16px;text-align:center;min-height:150px}.metric-label{font-weight:800;color:#d8e5ef;letter-spacing:.05em}.metric-value{font-size:3.0rem;font-weight:900;line-height:1.05}
.reco-card{padding:14px 12px;text-align:center;min-height:150px;background:rgba(9,27,44,.94);border:1px solid #20425f;border-radius:16px}.reco-label{font-weight:900;color:#d8e5ef;letter-spacing:.05em;font-size:.92rem}.reco-side{font-size:2.15rem;font-weight:900;line-height:1.0;margin-top:8px}.reco-line{font-size:1.05rem;font-weight:900;margin-top:6px}.reco-meta{color:#9fb3c3;font-size:.78rem;margin-top:6px}.reco-good{color:#49efb0}.reco-under{color:#ff4b5f}.reco-neutral{color:#f2f6fa}.reco-warn{color:#ffd166}
.badge{display:inline-block;background:#073d2c;border:1px solid #087c59;color:#49efb0;border-radius:999px;padding:5px 10px;font-weight:800;font-size:.82rem}
.alt-k-badge{display:block;width:max-content;max-width:95%;margin:9px auto 0;background:#102d49;border:1px solid #2f6590;color:#dff3ff;border-radius:999px;padding:5px 11px;font-weight:900;font-size:.78rem;letter-spacing:.03em}
.search-note{color:var(--muted);font-size:.82rem}
.market-ok{color:#49efb0;font-weight:800}.market-empty{color:#8fa5b7}
/* PROJECTION_EMBLEMS_V2 · corrected placement + vector artwork only */
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label{
    display:flex!important;align-items:center!important;flex-direction:row!important;flex-wrap:nowrap!important;
    position:relative!important;gap:.52rem!important;min-height:2.42rem!important;padding:.26rem .38rem!important;
    border-radius:9px!important;transition:background .14s ease,border-color .14s ease,box-shadow .14s ease!important;
}
/* Remove Streamlit's native radio circle completely. The custom icon occupies that exact leading slot. */
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label input[type="radio"]{display:none!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label>div:has(input[type="radio"]){display:none!important;width:0!important;height:0!important;margin:0!important;padding:0!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label [role="radio"]{display:none!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label::before{
    content:""!important;display:inline-block!important;width:1.72rem!important;height:1.72rem!important;flex:0 0 1.72rem!important;
    border:1px solid rgba(236,22,56,.68)!important;border-radius:7px!important;background-color:#0b2038!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:1.20rem 1.20rem!important;
    box-shadow:inset 0 0 0 2px rgba(255,255,255,.025),0 4px 10px rgba(0,0,0,.25)!important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:has(input:checked)::before{
    border-color:#ff3553!important;background-color:#411225!important;
    box-shadow:inset 0 0 0 2px rgba(255,255,255,.04),0 0 13px rgba(236,22,56,.48)!important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(1)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PGcgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCI+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iMTQiLz48Y2lyY2xlIGN4PSIzMiIgY3k9IjMyIiByPSI0IiBmaWxsPSIjZWMxNjM4IiBzdHJva2U9IiNlYzE2MzgiLz48cGF0aCBkPSJNMzIgNnYxMk0zMiA0NnYxMk02IDMyaDEyTTQ2IDMyaDEyIi8+PC9nPjwvc3ZnPg==")!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(2)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PGcgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTEwIDU0aDQ0Ii8+PHJlY3QgeD0iMTMiIHk9IjM0IiB3aWR0aD0iOCIgaGVpZ2h0PSIxOCIgcng9IjIiLz48cmVjdCB4PSIyOCIgeT0iMjIiIHdpZHRoPSI4IiBoZWlnaHQ9IjMwIiByeD0iMiIgZmlsbD0iI2VjMTYzOCIgc3Ryb2tlPSIjZWMxNjM4Ii8+PHJlY3QgeD0iNDMiIHk9IjEyIiB3aWR0aD0iOCIgaGVpZ2h0PSI0MCIgcng9IjIiLz48L2c+PC9zdmc+")!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(3)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHBhdGggZD0iTTYgMzRoMTJsNi0xNCA5IDI4IDgtMjAgNSA2aDEyIiBmaWxsPSJub25lIiBzdHJva2U9IiNmN2Y3ZmIiIHN0cm9rZS13aWR0aD0iNCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PGNpcmNsZSBjeD0iMzMiIGN5PSIzNCIgcj0iMyIgZmlsbD0iI2VjMTYzOCIvPjwvc3ZnPg==")!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(4)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PGcgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCI+PHJlY3QgeD0iMTciIHk9IjE3IiB3aWR0aD0iMzAiIGhlaWdodD0iMzAiIHJ4PSI2Ii8+PHJlY3QgeD0iMjYiIHk9IjI2IiB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHJ4PSIyIiBmaWxsPSIjZWMxNjM4IiBzdHJva2U9IiNlYzE2MzgiLz48cGF0aCBkPSJNMjQgOHY5TTQwIDh2OU0yNCA0N3Y5TTQwIDQ3djlNOCAyNGg5TTggNDBoOU00NyAyNGg5TTQ3IDQwaDkiLz48L2c+PC9zdmc+")!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(5)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHBhdGggZD0iTTE0IDE0aDM2djEyYTcgNyAwIDAgMCAwIDEydjEySDE0VjM4YTcgNyAwIDAgMCAwLTEyVjE0WiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48cGF0aCBkPSJNMjcgMjJ2MjAiIHN0cm9rZT0iI2VjMTYzOCIgc3Ryb2tlLXdpZHRoPSI0IiBzdHJva2UtZGFzaGFycmF5PSI0IDUiLz48L3N2Zz4=")!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(6)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PGcgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTE4IDIwSDh2LTEwIi8+PHBhdGggZD0iTTEwIDIwYTI0IDI0IDAgMSAxLTIgMjIiLz48Y2lyY2xlIGN4PSIzNCIgY3k9IjM0IiByPSIxNiIvPjxwYXRoIGQ9Ik0zNCAyNHYxMWw4IDUiIHN0cm9rZT0iI2VjMTYzOCIvPjwvZz48L3N2Zz4=")!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(7)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHBhdGggZD0iTTM2IDYgMTYgMzZoMTVsLTMgMjIgMjAtMzFIMzRsMi0yMVoiIGZpbGw9IiNmN2Y3ZmIiIHN0cm9rZT0iI2VjMTYzOCIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+")!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(8)::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHBhdGggZD0ibTEwIDIyIDEyIDkgMTAtMTcgMTAgMTcgMTItOS01IDI4SDE1TDEwIDIyWiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZjdmN2ZiIiBzdHJva2Utd2lkdGg9IjQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48Y2lyY2xlIGN4PSIzMiIgY3k9IjM5IiByPSI0IiBmaWxsPSIjZWMxNjM4Ii8+PC9zdmc+")!important}

/* True vector baseball emblems inside the existing 48px circular card slot. */
.cc-card-icon.cc-emblem{position:relative!important;overflow:hidden!important;font-size:0!important}
.cc-card-icon.cc-emblem::before{
    content:""!important;position:absolute!important;inset:2px!important;display:block!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:42px 42px!important;
    filter:drop-shadow(0 3px 4px rgba(0,0,0,.30));pointer-events:none!important;
}
.cc-card-icon.cc-emblem::after{display:none!important;content:none!important}
.cc-card-icon.cc-emblem.whiff::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA5NiA5NiI+PGcgZmlsbD0ibm9uZSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNNjcgMTYgMzQgNDkiIHN0cm9rZT0iI2QwOGE0NSIgc3Ryb2tlLXdpZHRoPSIxMCIvPjxwYXRoIGQ9Ik03MiAxMSA2NCAyMCIgc3Ryb2tlPSIjZjNiZjc3IiBzdHJva2Utd2lkdGg9IjUiLz48cGF0aCBkPSJNMzEgNTIgMjUgNTgiIHN0cm9rZT0iIzdhM2IxOCIgc3Ryb2tlLXdpZHRoPSI4Ii8+PGNpcmNsZSBjeD0iMjUiIGN5PSI3MiIgcj0iMTMiIGZpbGw9IiNmN2YyZTgiIHN0cm9rZT0iI2Q0ZDlkZiIgc3Ryb2tlLXdpZHRoPSIyIi8+PHBhdGggZD0iTTE4IDY0YzUgMyA3IDggNyAxNk0zMiA2NGMtNSAzLTcgOC03IDE2IiBzdHJva2U9IiNkODIxM2YiIHN0cm9rZS13aWR0aD0iMi41Ii8+PHBhdGggZD0iTTEwIDM4YzExLTEwIDIzLTEzIDM1LTExTTkgNTBjMTAtNiAyMC03IDMwLTUiIHN0cm9rZT0iIzUzYTdmZiIgc3Ryb2tlLXdpZHRoPSIzIiBvcGFjaXR5PSIuODUiLz48cGF0aCBkPSJNNDMgNTljNSAyIDkgNiAxMiAxMCIgc3Ryb2tlPSIjZWMxNjM4IiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1kYXNoYXJyYXk9IjMgNiIvPjwvZz48L3N2Zz4=")!important}
.cc-card-icon.cc-emblem.glove::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA5NiA5NiI+PGcgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMjIgNzBjLTctMTAtNC0yMCA0LTI0bC0xLTE5YzAtNSA3LTYgOS0xbDMgMTQtMS0yM2MwLTUgOC02IDkgMGwyIDIxIDEtMjRjMC01IDgtNSA5IDBsMSAyNSA0LTE5YzEtNSA5LTMgOCAzbC00IDI1YzgtMiAxNCA2IDEwIDEzLTUgOS0xNiAxOS0yOCAyMC0xMiAxLTIxLTMtMjYtMTFaIiBmaWxsPSIjOGI0YTI4IiBzdHJva2U9IiNmMmE0NWIiIHN0cm9rZS13aWR0aD0iMyIvPjxwYXRoIGQ9Ik0zMyA0NWM3IDcgMTggMTEgMzEgOU0zOSAyN2wxIDIwTTUwIDE5bDEgMzFNNjEgMjVsLTIgMjciIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzViMmExNyIgc3Ryb2tlLXdpZHRoPSIzIi8+PGNpcmNsZSBjeD0iNTgiIGN5PSI2MCIgcj0iMTMiIGZpbGw9IiNmN2YyZTgiIHN0cm9rZT0iI2Q0ZDlkZiIgc3Ryb2tlLXdpZHRoPSIyIi8+PHBhdGggZD0iTTUxIDUyYzUgMyA3IDggNyAxNk02NSA1MmMtNSAzLTcgOC03IDE2IiBmaWxsPSJub25lIiBzdHJva2U9IiNkODIxM2YiIHN0cm9rZS13aWR0aD0iMi41Ii8+PC9nPjwvc3ZnPg==")!important}
.cc-card-icon.cc-emblem.contact::before{background-image:url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA5NiA5NiI+PGcgZmlsbD0ibm9uZSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTggNzYgNTggMzgiIHN0cm9rZT0iI2QwOGE0NSIgc3Ryb2tlLXdpZHRoPSIxMSIvPjxwYXRoIGQ9Ik0xMyA4MSAyMiA3MiIgc3Ryb2tlPSIjZjNiZjc3IiBzdHJva2Utd2lkdGg9IjUiLz48cGF0aCBkPSJNNTggMzggNjUgMzEiIHN0cm9rZT0iIzdhM2IxOCIgc3Ryb2tlLXdpZHRoPSI4Ii8+PGNpcmNsZSBjeD0iNjYiIGN5PSIzMCIgcj0iMTMiIGZpbGw9IiNmN2YyZTgiIHN0cm9rZT0iI2Q0ZDlkZiIgc3Ryb2tlLXdpZHRoPSIyIi8+PHBhdGggZD0iTTU5IDIyYzUgMyA3IDggNyAxNk03MyAyMmMtNSAzLTcgOC03IDE2IiBzdHJva2U9IiNkODIxM2YiIHN0cm9rZS13aWR0aD0iMi41Ii8+PHBhdGggZD0ibTY2IDcgMyAxME04NCAxNGwtOCA4TTkxIDMxSDgwTTgzIDQ4bC04LTgiIHN0cm9rZT0iI2ZmYjM0NyIgc3Ryb2tlLXdpZHRoPSI0Ii8+PHBhdGggZD0iTTQ0IDQ5YzQgNiA4IDEwIDE0IDE0IiBzdHJva2U9IiNlYzE2MzgiIHN0cm9rZS13aWR0aD0iMyIgb3BhY2l0eT0iLjg1Ii8+PC9nPjwvc3ZnPg==")!important}
.active-market-line{padding:.72rem .78rem;border:1px solid #20425f;border-radius:12px;background:rgba(9,27,44,.94);text-align:center}.active-market-line .label{color:#9fb3c3;font-size:.72rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase}.active-market-line .value{margin-top:.18rem;color:#f2f6fa;font-size:1.5rem;font-weight:950}.active-market-line .source{margin-top:.14rem;color:#8fa5b7;font-size:.68rem;font-weight:850;letter-spacing:.04em}.active-market-line.manual{border-color:rgba(255,159,28,.66);background:rgba(255,159,28,.07)}.active-market-line.manual .value,.active-market-line.manual .source{color:#ff9f1c}.reco-line.manual-active{color:#ff9f1c;text-shadow:0 0 15px rgba(255,159,28,.18)}

/* PROJECTION_ARTWORK_V1 · actual illustrated mockup badges */
.cc-card-icon.cc-emblem{
    width:64px!important;
    height:64px!important;
    flex:0 0 64px!important;
    border:0!important;
    border-radius:0!important;
    background-color:transparent!important;
    background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_summary_emblems_v2.webp?v=2")!important;
    background-repeat:no-repeat!important;
    background-size:600% 100%!important;
    box-shadow:none!important;
    overflow:visible!important;
    filter:drop-shadow(0 4px 8px rgba(0,0,0,.32)) drop-shadow(0 0 5px rgba(236,22,56,.18));
}
.cc-card-icon.cc-emblem::before,
.cc-card-icon.cc-emblem::after{display:none!important;content:none!important}
.metric-card .cc-emblem.whiff{background-position:0% 50%!important}
.reco-card .cc-emblem.whiff{background-position:20% 50%!important}
.metric-card .cc-emblem.glove{background-position:40% 50%!important}
.reco-card .cc-emblem.glove{background-position:60% 50%!important}
.metric-card .cc-emblem.contact{background-position:80% 50%!important}
.reco-card .cc-emblem.contact{background-position:100% 50%!important}


/* PROJECTION_ARTWORK_INDIVIDUAL_V5 · one real image per Summary emblem, no runtime sprite */
.cc-card-icon.cc-emblem{
    width:74px!important;height:74px!important;flex:0 0 74px!important;
    display:block!important;visibility:visible!important;opacity:1!important;
    border:0!important;border-radius:0!important;background-color:transparent!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:contain!important;
    box-shadow:none!important;overflow:visible!important;
    filter:drop-shadow(0 3px 5px rgba(0,0,0,.28)) drop-shadow(0 0 3px rgba(236,22,56,.16))!important;
}
.cc-card-icon.cc-emblem::before,.cc-card-icon.cc-emblem::after{display:none!important;content:none!important}
.metric-card .cc-emblem.whiff{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_k.webp?v=6")!important}
.reco-card .cc-emblem.whiff{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_k_plus.webp?v=6")!important}
.metric-card .cc-emblem.glove{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_outs.webp?v=6")!important}
.reco-card .cc-emblem.glove{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_outs_plus.webp?v=6")!important}
.metric-card .cc-emblem.contact{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_hits.webp?v=6")!important}
.reco-card .cc-emblem.contact{background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_hits_plus.webp?v=6")!important}
@media (max-width:900px){.cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{width:66px!important;height:66px!important;flex-basis:66px!important}}

/* PROJECTION_BADGE_POLISH_V6 · larger, tighter cleaned artwork only */
.cc-card-top{gap:.72rem!important}

/* PROJECTION_BADGE_POLISH_V7 · tighter fill + reduced blur */
.cc-card-icon.cc-emblem{background-size:72px 72px!important}
@media (max-width:900px){.cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{background-size:64px 64px!important}}

/* PROJECTION_SUMMARY_LAYOUT_V8 · title top, value left, large emblem right */
.metric-card,.reco-card{
    position:relative!important;
    min-height:184px!important;
    padding:16px 108px 16px 16px!important;
    text-align:left!important;
    overflow:hidden!important;
}
.metric-card .cc-card-top,.reco-card .cc-card-top{
    display:block!important;
    margin:0 0 .55rem!important;
    min-height:1.3rem!important;
}
.metric-card .metric-label,.reco-card .reco-label{
    display:block!important;
    width:100%!important;
    margin:0!important;
    padding:0!important;
    text-align:left!important;
    white-space:normal!important;
    position:relative!important;
    z-index:2!important;
}
.metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{
    position:absolute!important;
    right:14px!important;
    top:50px!important;
    width:88px!important;
    height:88px!important;
    min-width:88px!important;
    flex:0 0 88px!important;
    margin:0!important;
    background-size:86px 86px!important;
    background-position:center!important;
    z-index:1!important;
}
.metric-card .metric-value{
    margin:.05rem 0 .38rem!important;
    text-align:left!important;
    position:relative!important;
    z-index:2!important;
}
.metric-card .badge,.metric-card .alt-k-badge{
    margin-left:0!important;
    margin-right:0!important;
    position:relative!important;
    z-index:2!important;
}
.reco-card .reco-side{
    margin:.08rem 0 .30rem!important;
    position:relative!important;
    z-index:2!important;
}
.reco-card .reco-line,.reco-card .reco-meta{
    text-align:left!important;
    position:relative!important;
    z-index:2!important;
}
@media (max-width:900px){
    .metric-card,.reco-card{padding-right:92px!important;min-height:176px!important}
    .metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{
        right:10px!important;top:52px!important;width:76px!important;height:76px!important;min-width:76px!important;flex-basis:76px!important;background-size:74px 74px!important
    }
}
@media (max-width:620px){
    .metric-card,.reco-card{padding:14px 82px 14px 14px!important;min-height:166px!important}
    .metric-card .cc-card-icon.cc-emblem,.reco-card .cc-card-icon.cc-emblem{
        right:8px!important;top:50px!important;width:68px!important;height:68px!important;min-width:68px!important;flex-basis:68px!important;background-size:66px 66px!important
    }
}


/* PROJECTION_EMBLEM_MASTER_V9 · 128px master tiles rendered down for sharper edges */
.cc-card-icon.cc-emblem{
    background-image:url("https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_summary_emblems_v2.webp?v=9")!important;
    background-size:600% 100%!important;
    background-repeat:no-repeat!important;
    filter:drop-shadow(0 2px 2px rgba(0,0,0,.28)) drop-shadow(0 0 2px rgba(236,22,56,.12))!important;
    image-rendering:auto!important;
}
.metric-card .cc-emblem.whiff{background-position:0% 50%!important}
.reco-card .cc-emblem.whiff{background-position:20% 50%!important}
.metric-card .cc-emblem.glove{background-position:40% 50%!important}
.reco-card .cc-emblem.glove{background-position:60% 50%!important}
.metric-card .cc-emblem.contact{background-position:80% 50%!important}
.reco-card .cc-emblem.contact{background-position:100% 50%!important}


/* PROJECTION_SUMMARY_NO_LINE_V14 · compact no-market state; approved emblem geometry untouched */
.reco-card.reco-neutral .reco-side{
    font-size:1.82rem!important;
    line-height:1.04!important;
    letter-spacing:-.02em!important;
    white-space:nowrap!important;
}
.reco-card.reco-neutral .reco-line{margin-top:.36rem!important}
.reco-card.reco-neutral .reco-meta{max-width:100%!important;line-height:1.35!important}
@media (max-width:900px){.reco-card.reco-neutral .reco-side{font-size:1.65rem!important}}

/* PROJECTION_WEATHER_SUMMARY_V10 · compact Hits pair + game delay-risk command card */
.game-weather-card{
    position:relative!important;
    min-height:184px!important;
    padding:16px 18px!important;
    border:1px solid rgba(80,108,136,.72)!important;
    border-radius:15px!important;
    background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98))!important;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 14px 32px rgba(0,0,0,.28)!important;
    overflow:hidden!important;
}
.game-weather-card::after{
    content:"";position:absolute;left:0;right:0;bottom:0;height:2px;
    background:linear-gradient(90deg,transparent,#ec1638,transparent);opacity:.72;
}
.game-weather-card.weather-none{border-color:rgba(36,230,155,.58)!important}
.game-weather-card.weather-low{border-color:rgba(85,170,255,.62)!important}
.game-weather-card.weather-elevated{border-color:rgba(255,190,78,.72)!important}
.game-weather-card.weather-high{border-color:rgba(255,71,98,.80)!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 0 24px rgba(236,22,56,.12),0 14px 32px rgba(0,0,0,.28)!important}
.game-weather-card.weather-unknown{border-color:rgba(122,143,164,.58)!important}
/* WEATHER_CARD_HERO_V13 · large state-aware weather symbol */
.game-weather-head{
    display:grid;
    grid-template-columns:minmax(0,1fr) 100px;
    gap:1rem;
    align-items:start;
    margin-bottom:.26rem;
}
.game-weather-title{color:#eef3f7;font-size:.92rem;line-height:1.3;font-weight:900;letter-spacing:.035em}
.game-weather-icon{
    width:92px;
    height:92px;
    justify-self:end;
    display:flex;
    align-items:center;
    justify-content:center;
    border-radius:50%;
    font-size:3.55rem;
    line-height:1;
    border:1px solid rgba(91,119,146,.68);
    background:radial-gradient(circle at 35% 28%,rgba(30,67,103,.94),rgba(5,22,39,.98) 68%);
    box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 24px rgba(71,126,174,.16);
    filter:drop-shadow(0 3px 5px rgba(0,0,0,.28));
}
.weather-high .game-weather-icon{
    border-color:rgba(255,78,101,.82);
    background:radial-gradient(circle at 35% 28%,rgba(125,24,47,.96),rgba(35,7,18,.98) 70%);
    box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 28px rgba(236,22,56,.36);
}
.weather-elevated .game-weather-icon{
    border-color:rgba(255,209,102,.78);
    background:radial-gradient(circle at 35% 28%,rgba(108,77,14,.94),rgba(35,24,5,.98) 70%);
    box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 28px rgba(255,209,102,.24);
}
.weather-low .game-weather-icon{
    border-color:rgba(91,178,230,.74);
    background:radial-gradient(circle at 35% 28%,rgba(20,76,112,.94),rgba(5,24,39,.98) 70%);
    box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 26px rgba(91,178,230,.22);
}
.weather-none .game-weather-icon{
    border-color:rgba(50,229,141,.66);
    background:radial-gradient(circle at 35% 28%,rgba(16,88,62,.88),rgba(5,30,24,.98) 70%);
    box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 26px rgba(50,229,141,.20);
}
.weather-unknown .game-weather-icon{
    color:#9cb0c1;
    border-color:rgba(91,119,146,.55);
    background:radial-gradient(circle at 35% 28%,rgba(35,54,73,.88),rgba(7,20,34,.98) 70%);
}
.game-weather-risk{font-family:Impact,"Arial Narrow",sans-serif;font-size:2.15rem;line-height:1;color:#f5f1e9;letter-spacing:.02em;margin:.08rem 0 .34rem}
.game-weather-action{display:inline-flex;align-items:center;border:1px solid rgba(93,126,158,.68);border-radius:999px;padding:.25rem .58rem;background:rgba(12,38,65,.82);color:#dce9f5;font-size:.76rem;font-weight:900;letter-spacing:.035em;text-transform:uppercase}
.weather-high .game-weather-action{border-color:rgba(255,71,98,.58);color:#ff7f91;background:rgba(121,15,37,.30)}
.weather-elevated .game-weather-action{border-color:rgba(255,190,78,.58);color:#ffd36f;background:rgba(101,73,11,.30)}
.weather-none .game-weather-action{border-color:rgba(36,230,155,.48);color:#5ceeb0;background:rgba(8,80,54,.30)}
.game-weather-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem;margin-top:.62rem}
.game-weather-stat{padding:.38rem .52rem;border:1px solid rgba(65,96,128,.58);border-radius:9px;background:rgba(4,18,33,.55)}
.game-weather-stat span{display:block;color:#8fa5b7;font-size:.68rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
.game-weather-stat strong{display:block;margin-top:.08rem;color:#f4f7fa;font-size:1rem;font-weight:900}
.game-weather-reason{margin-top:.5rem;color:#a9bdce;font-size:.76rem;line-height:1.28}
.game-weather-note{margin-top:.32rem;color:#7690a6;font-size:.67rem;line-height:1.2}
@media (max-width:900px){.game-weather-card{min-height:176px!important}}
@media (max-width:620px){.game-weather-card{min-height:166px!important;padding:14px!important}.game-weather-grid{grid-template-columns:1fr}.game-weather-risk{font-size:1.85rem}.game-weather-head{grid-template-columns:minmax(0,1fr) 76px}.game-weather-icon{width:72px;height:72px;font-size:2.75rem}}
</style>""", unsafe_allow_html=True)

@dataclass(frozen=True)
class GamePitcher:
    key:str; pitcher_id:int; pitcher_name:str; team:str; opponent:str; side:str; venue_id:int; venue:str; game_pk:int; game_time:str; status:str; venue_latitude:float|None=None; venue_longitude:float|None=None

@dataclass
class Projection:
    mean_k:float; mean_outs:float; k_sd:float; outs_sd:float; k_probs:np.ndarray; outs_probs:np.ndarray; k_samples:np.ndarray; outs_samples:np.ndarray; confidence:str; quality:int; factors:list[tuple[str,float]]; engine:ProjectionResult; outs_engine:OutsProjection

class MLBClient:
    def __init__(self):
        self.session=requests.Session(); self.session.headers.update({"Accept":"application/json","User-Agent":f"StrikeOutKing9000/{APP_VERSION}"})
    def get(self,endpoint,params):
        r=self.session.get(f"{MLB_API}/{endpoint}",params=params,timeout=20); r.raise_for_status(); data=r.json()
        if not isinstance(data,dict): raise ValueError("Unexpected MLB response")
        return data

def get_schedule(day):
    try:p=MLBClient().get("schedule",{"sportId":1,"date":day,"hydrate":"probablePitcher,team,venue(location)"})
    except Exception as e:return [],str(e)
    rows=[]
    for block in p.get("dates",[]):
        for game in block.get("games",[]):
            teams=game.get("teams",{}); pk=int(game.get("gamePk",0)); venue_node=game.get("venue",{}) or {}; venue=venue_node.get("name","Unknown"); venue_id=int(venue_node.get("id",0) or 0)
            venue_location=venue_node.get("location",{}) or {}; venue_coords=venue_location.get("defaultCoordinates",{}) or {}
            venue_latitude=pd.to_numeric(pd.Series([venue_coords.get("latitude")]),errors="coerce").iloc[0]; venue_longitude=pd.to_numeric(pd.Series([venue_coords.get("longitude")]),errors="coerce").iloc[0]
            venue_latitude=None if pd.isna(venue_latitude) else float(venue_latitude); venue_longitude=None if pd.isna(venue_longitude) else float(venue_longitude)
            for side,other in (("away","home"),("home","away")):
                node=teams.get(side,{}) or {}; opp=teams.get(other,{}) or {}; pit=node.get("probablePitcher") or {}
                if not pit.get("id"): continue
                tn=node.get("team",{}); on=opp.get("team",{})
                team=TEAM_ABBR.get(tn.get("id"),tn.get("abbreviation","UNK")); opponent=TEAM_ABBR.get(on.get("id"),on.get("abbreviation","UNK"))
                rows.append(GamePitcher(f"{pk}:{pit['id']}",int(pit["id"]),pit.get("fullName","Unknown"),team,opponent,side.title(),venue_id,venue,pk,game.get("gameDate",""),game.get("status",{}).get("detailedState","Scheduled"),venue_latitude=venue_latitude,venue_longitude=venue_longitude))
    return rows,None

def parse_ip(v):
    try:
        whole,frac=str(v).split("."); return int(whole)+int(frac)/3
    except Exception: return 0.0

@st.cache_data(ttl=1800,show_spinner=False)
def get_log(pid,season):
    try:p=MLBClient().get(f"people/{pid}/stats",{"stats":"gameLog","group":"pitching","season":season,"gameType":"R"})
    except Exception as e:return pd.DataFrame(),str(e)
    rec=[]
    for sb in p.get("stats",[]):
        for sp in sb.get("splits",[]):
            s=sp.get("stat",{}); bf=float(s.get("battersFaced",0) or 0)
            rec.append({"date":pd.to_datetime(sp.get("date"),errors="coerce"),"opponent":sp.get("opponent",{}).get("name",""),"bf":bf,"k":float(s.get("strikeOuts",0) or 0),"hits":float(s.get("hits",0) or 0),"pitches":float(s.get("numberOfPitches",0) or 0),"outs":parse_ip(s.get("inningsPitched","0.0"))*3,"games_started":int(float(s.get("gamesStarted",0) or 0))})
    df=pd.DataFrame(rec); starts=starter_only(df); return (starts,None) if not starts.empty else (starts,"No regular-season starter game log returned.")

def weighted(s,half,fallback):
    x=pd.to_numeric(s,errors="coerce").dropna().to_numpy(float)
    if not len(x): return fallback
    age=np.arange(len(x)-1,-1,-1); w=.5**(age/half); return float(np.average(x,weights=w))

def shrink(rate,opp,prior=.224,weight=120): return (rate*opp+prior*weight)/max(opp+weight,1)

@st.cache_data(ttl=1800,show_spinner=False)
def get_pitcher_hand(pid):
    try:
        payload=MLBClient().get(f"people/{int(pid)}",{})
        people=payload.get("people") or []
        if not people:
            return ""
        # MLB Person uses `pitchHand`; retain the legacy key only as a defensive fallback.
        hand=people[0].get("pitchHand") or people[0].get("pitchingHand") or {}
        return str(hand.get("code") or "").upper()
    except Exception:
        return ""

@st.cache_data(ttl=21600,show_spinner=False)
def get_venue_coordinates(venue_id):
    if not venue_id: return None
    target_id=int(venue_id)

    # Primary fallback: ask MLB's venue endpoint explicitly for location data.
    try:
        payload=MLBClient().get(f"venues/{target_id}",{"hydrate":"location"})
        venues=payload.get("venues") or []
        coords=((venues[0].get("location") or {}).get("defaultCoordinates") or {}) if venues else {}
        lat=coords.get("latitude"); lon=coords.get("longitude")
        if lat is not None and lon is not None:
            return float(lat),float(lon)
    except Exception:
        pass

    # Secondary fallback for current MLB home parks: resolve the same venue ID
    # through the live team directory with hydrated venue location data. This
    # avoids a stale hard-coded stadium table when parks/names change.
    try:
        payload=MLBClient().get("teams",{"sportId":1,"hydrate":"venue(location)"})
        for team_node in payload.get("teams",[]) or []:
            venue_node=team_node.get("venue",{}) or {}
            if int(venue_node.get("id",0) or 0) != target_id:
                continue
            coords=((venue_node.get("location") or {}).get("defaultCoordinates") or {})
            lat=coords.get("latitude"); lon=coords.get("longitude")
            if lat is not None and lon is not None:
                return float(lat),float(lon)
    except Exception:
        pass
    return None

@st.cache_data(ttl=21600,show_spinner=False)
def get_venue_roof_type(venue_id):
    if not venue_id:
        return ""
    target_id=int(venue_id)
    try:
        payload=MLBClient().get(f"venues/{target_id}",{"hydrate":"fieldInfo"})
        venues=payload.get("venues") or []
        field_info=(venues[0].get("fieldInfo") or {}) if venues else {}
        roof=str(field_info.get("roofType") or "").strip()
        if roof:
            return roof
    except Exception:
        pass
    try:
        payload=MLBClient().get("teams",{"sportId":1,"hydrate":"venue(fieldInfo)"})
        for team_node in payload.get("teams",[]) or []:
            venue_node=team_node.get("venue",{}) or {}
            if int(venue_node.get("id",0) or 0) != target_id:
                continue
            roof=str(((venue_node.get("fieldInfo") or {}).get("roofType")) or "").strip()
            if roof:
                return roof
    except Exception:
        pass
    return ""

@st.cache_data(ttl=900,show_spinner=False)
def get_game_weather(venue_id,game_time,latitude=None,longitude=None):
    coords=None
    try:
        if latitude is not None and longitude is not None and pd.notna(latitude) and pd.notna(longitude):
            coords=(float(latitude),float(longitude))
    except (TypeError,ValueError):
        coords=None
    if not coords:
        coords=get_venue_coordinates(venue_id)
    if not coords:
        return WeatherDelayRisk("UNKNOWN","",None,None,None,"Venue coordinates unavailable for weather risk.",False)
    risk=fetch_weather_delay_risk(coords[0],coords[1],game_time)
    return apply_roof_protection(risk,get_venue_roof_type(venue_id))

def load_projection_history():
    try:return pd.read_csv(APP_DIR / "data" / "projection_log.csv")
    except Exception:return pd.DataFrame()

def load_observation_history():
    try:return pd.read_csv(OBS_LOG)
    except Exception:return pd.DataFrame()

def load_role_runtime_state():
    try:return pd.read_csv(APP_DIR / "data" / "starter_role_runtime_state.csv")
    except Exception:return pd.DataFrame()

def calibrated_weights(history): return {line:calibrate_blend(history,line) for line in range(3,11)}

def build_engine_features(log,game,opponent_k_pct=.224,lineup_batters=0,workload_context:WorkloadContext|None=None):
    starts=log.tail(35).copy(); total_bf=float(starts.bf.sum()); raw_k=float(starts.k.sum()/max(total_bf,1)); pitcher_k=float(np.clip(shrink(raw_k,total_bf),.05,.45)); workload_context=workload_context or build_workload_context(starts,game.game_time)
    return {"pitcher_k_pct":pitcher_k,"opponent_k_pct":float(np.clip(opponent_k_pct,.08,.45)),"handedness_factor":1.0,"arsenal_factor":1.0,"park_factor":PARK_K_FACTOR.get(game.venue,1.0),"umpire_factor":1.0,"weather_factor":1.0,"expected_bf":float(workload_context.expected_bf),"bf_sd":float(workload_context.bf_sd),"rest_factor":1.0,"historical_k_sd":float(np.clip(starts.k.std(ddof=1) if len(starts)>2 else 2.0,.75,4.5)),"historical_games":int(len(starts)),"lineup_batters":int(lineup_batters),"arsenal_sample_size":0,"weather_available":0,"umpire_available":0}

def calculate_projection(log,game,simulations,opponent_k_pct=.224,lineup_batters=0,workload_context:WorkloadContext|None=None):
    history=load_projection_history(); cal=calibrated_weights(history); workload_context=workload_context or build_workload_context(log,game.game_time); seed=int(hashlib.sha256(f"{game.key}|{game.game_time}|{APP_VERSION}".encode()).hexdigest()[:8],16); features=build_engine_features(log,game,opponent_k_pct,lineup_batters,workload_context); engine=ProjectionEngine(simulation_weight=.5,seed=seed); result=engine.project(features,draws=simulations,lines=tuple(float(x) for x in range(3,13))); global_w=float(np.mean([r.weight_simulation for r in cal.values()])) if cal else .5; mean_k=global_w*result.simulation_mean+(1-global_w)*result.mathematical_mean; outs_seed=int(hashlib.sha256(f"outs|{game.key}|{APP_VERSION}".encode()).hexdigest()[:8],16); outs_model=project_total_outs(log,expected_outs=workload_context.expected_outs,workload_sd=workload_context.outs_sd,seed=outs_seed,draws=simulations,lines=(13.5,14.5,15.5,16.5,17.5,18.5)); mean_outs=outs_model.ensemble_mean; osd=outs_model.ensemble_sd; outs_samples=outs_model.simulation_samples; outs_probs=np.array([float(np.mean(outs_samples==i)) for i in range(28)]); quality=int(round(result.data_quality)); confidence="High" if result.confidence>=.75 else "Medium" if result.confidence>=.60 else "Low"; return Projection(mean_k,mean_outs,result.ensemble_sd,osd,result.mathematical_pmf,outs_probs,result.simulation_samples,outs_samples,confidence,quality,[(n,v) for n,v,_ in result.drivers],result,outs_model)

def american(p):
    p=float(np.clip(p,.001,.999)); o=-100*p/(1-p) if p>=.5 else 100*(1-p)/p; return f"{o:+.0f}"

def implied_prob(price):
    try:
        p=float(price); return 100/(p+100) if p>0 else abs(p)/(abs(p)+100)
    except Exception:return None

def best_market_offer(odds_rows, market_keys, line, side):
    wanted=str(side).lower(); candidates=[]
    for row in odds_rows:
        if row.get("market") not in set(market_keys): continue
        if str(row.get("name","")).lower()!=wanted: continue
        try:
            if abs(float(row.get("point"))-float(line))>1e-9: continue
            float(row.get("price"))
        except Exception: continue
        candidates.append(row)
    return max(candidates,key=lambda row:float(row.get("price"))) if candidates else None

PROJECTION_PARLAY_KEY="projection_page_parlay_legs"
PROJECTION_PARLAY_BOOKS=[
    "Not tracked","FanDuel","DraftKings","BetMGM","Caesars Sportsbook",
    "Fanatics Sportsbook","bet365","ESPN BET","Hard Rock Bet","BetRivers","Other / Not listed",
]

def projection_parlay_leg(game,game_date,market,line,side,projection,model_probability,data_quality):
    return {
        "player":game.pitcher_name,"market":market,"game_date":str(game_date)[:10],
        "line":float(line),"side":str(side).title(),"american_odds":None,
        "game_pk":int(game.game_pk),"pitcher_id":int(game.pitcher_id),
        "projection":float(projection),"model_probability":float(model_probability),
        "data_quality":float(data_quality),"app_version":APP_VERSION,
        "probability_semantics":PROBABILITY_SEMANTICS,"snapshot_captured_at_utc":"",
    }

def _projection_leg_key(leg):
    return (
        str(leg.get("game_date","")),str(leg.get("game_pk","")),str(leg.get("pitcher_id","")),
        str(leg.get("market","")),str(leg.get("side","")),float(leg.get("line",0.0)),
    )

def queue_projection_parlay_leg(leg):
    legs=list(st.session_state.get(PROJECTION_PARLAY_KEY,[]))
    if legs and str(legs[0].get("game_date","")) != str(leg.get("game_date","")):
        return False,"The Projection Parlay Builder already contains a different slate date. Save or clear it first."
    key=_projection_leg_key(leg)
    if any(_projection_leg_key(existing)==key for existing in legs):
        return False,"That exact leg is already in the Projection Parlay Builder."
    legs.append(dict(leg)); st.session_state[PROJECTION_PARLAY_KEY]=legs
    return True,f"Added to Projection Parlay Builder ({len(legs)} leg" + ("" if len(legs)==1 else "s") + ")."

def save_projection_straight(*,game,game_date,market,line,side,projection,model_probability,stake,confidence,data_quality,offer,source):
    price=float(offer.get("price")) if offer is not None and offer.get("price") is not None else None
    implied=implied_prob(price) if price is not None else None
    record=make_bet_record(
        player=game.pitcher_name,market=market,game_date=game_date,line=float(line),side=side,
        american_odds=price,stake=float(stake),book=str(offer.get("book","")) if offer is not None else "",
        projection=float(projection),model_probability=float(model_probability),implied_probability=implied,
        edge=None if implied is None else float(model_probability)-implied,confidence=confidence,
        game_pk=game.game_pk,pitcher_id=game.pitcher_id,source=source,data_quality=float(data_quality),
        app_version=APP_VERSION,probability_semantics=PROBABILITY_SEMANTICS,
    )
    append_bet(BET_LOG,record,st.secrets)
    return price

def render_add_bet_button(container,reco,market_label,market_keys,projection_mean,stake,game,game_date,odds_rows,confidence,data_quality,key):
    side=str(reco.get("side","NO LINE")).upper()
    no_line=reco.get("line") is None or side=="NO LINE"
    tradable=side in {"OVER","UNDER"} and not no_line
    offer=best_market_offer(odds_rows,market_keys,reco.get("line"),side) if tradable else None
    with container:
        if offer is not None:
            st.caption(f"Best posted: {offer.get('book','')} {float(offer.get('price')):+.0f}")
        elif no_line:
            st.caption("Projection shown · add an active sportsbook line on Daily Projection Run to quick-add this market")
        elif side=="PASS":
            st.caption("Active line exists, but the model does not have an aligned play")
        else:
            st.caption("Active line loaded · sportsbook price optional")
        straight_col,parlay_col=st.columns(2)
        straight_clicked=straight_col.button("➕ Straight",key=f"{key}_straight",use_container_width=True,disabled=not tradable)
        parlay_clicked=parlay_col.button("🎟️ Parlay",key=f"{key}_parlay",use_container_width=True,disabled=not tradable)
        if straight_clicked:
            try:
                price=save_projection_straight(
                    game=game,game_date=game_date,market=market_label,line=float(reco.get("line")),side=side,
                    projection=projection_mean,model_probability=float(reco.get("model")),stake=stake,
                    confidence=confidence,data_quality=data_quality,offer=offer,source="Projection Recommendation",
                )
                st.success("Added to Bet Tracker" if price is not None else "Added unpriced model straight to Bet Tracker · result will grade, P/L stays blank because no sportsbook price was assumed.")
            except Exception as exc:
                st.error(f"Could not add bet: {exc}")
        if parlay_clicked:
            leg=projection_parlay_leg(
                game,game_date,market_label,float(reco.get("line")),side,projection_mean,float(reco.get("model")),data_quality
            )
            added,message=queue_projection_parlay_leg(leg)
            (st.success if added else st.info)(message)

def render_projection_parlay_builder():
    legs=list(st.session_state.get(PROJECTION_PARLAY_KEY,[]))
    with st.expander(f"🎟️ Projection Parlay Builder · {len(legs)} leg" + ("" if len(legs)==1 else "s"),expanded=bool(legs)):
        st.caption(
            "Add model legs from recommendations or the Strikeout Ladder, then move between pitchers on the same slate. "
            "Sportsbook availability never gates this builder; saved model parlays are unpriced and the sportsbook label is recordkeeping only."
        )
        if not legs:
            st.info("No parlay legs queued yet. Use any 🎟️ Parlay button on this Projection page.")
            return
        rows=[]
        for idx,leg in enumerate(legs,1):
            milestone=""
            if str(leg.get("market"))=="Strikeouts" and str(leg.get("side")).lower()=="over":
                line=float(leg.get("line",0.0)); milestone=f" ({int(line+0.5)}+ K)" if abs((line+0.5)-round(line+0.5))<1e-9 else ""
            rows.append({
                "#":idx,"Pitcher":leg.get("player",""),"Market":leg.get("market",""),
                "Bet":f"{leg.get('side','')} {float(leg.get('line',0.0)):g}{milestone}",
                "Projection":leg.get("projection",""),"Model Probability":leg.get("model_probability",""),
            })
        builder_view=pd.DataFrame(rows)
        builder_view["Projection"]=pd.to_numeric(builder_view["Projection"],errors="coerce").map(lambda x:"—" if pd.isna(x) else f"{x:.2f}")
        builder_view["Model Probability"]=pd.to_numeric(builder_view["Model Probability"],errors="coerce").map(lambda x:"—" if pd.isna(x) else f"{x:.1%}")
        st.dataframe(builder_view,hide_index=True,use_container_width=True)
        remove_col,clear_col=st.columns([2,1])
        remove_idx=remove_col.selectbox("Remove leg",range(len(legs)),format_func=lambda i:f"#{i+1} {legs[i].get('player','')} · {legs[i].get('market','')} · {legs[i].get('side','')} {float(legs[i].get('line',0.0)):g}",key="projection_parlay_remove")
        if clear_col.button("🗑️ Remove selected",use_container_width=True,key="projection_parlay_remove_button"):
            legs.pop(int(remove_idx)); st.session_state[PROJECTION_PARLAY_KEY]=legs; st.rerun()
        if st.button("Clear Projection Parlay Builder",use_container_width=True,key="projection_parlay_clear"):
            st.session_state[PROJECTION_PARLAY_KEY]=[]; st.rerun()
        if len(legs)>=10:
            st.warning(f"🎰 {len(legs)}-leg lotto · very high variance. The app grades every leg but does not multiply model probabilities or claim the legs are independent.")
        duplicate_pitchers=pd.Series([str(leg.get("player","")) for leg in legs]).value_counts()
        correlated=duplicate_pitchers[duplicate_pitchers>1]
        if not correlated.empty:
            st.warning("Multiple legs for the same pitcher can be correlated: "+", ".join(correlated.index.tolist())+". The app does not treat parlay probability as independent.")
        parlay_stake=st.number_input("Parlay stake (units)",min_value=0.0,value=1.0,step=0.5,key="projection_parlay_stake")
        parlay_book=st.selectbox("Sportsbook (recordkeeping only)",PROJECTION_PARLAY_BOOKS,key="projection_parlay_book")
        if len(legs)>=2:
            if st.button(f"🎟️ Save {len(legs)}-leg model parlay to Bet Tracker",type="primary",use_container_width=True,key="projection_parlay_save"):
                try:
                    record=make_parlay_record(
                        legs=legs,stake=float(parlay_stake),game_date=str(legs[0].get("game_date",""))[:10],
                        book="" if parlay_book=="Not tracked" else parlay_book,source="Projection Page Model Parlay",
                    )
                    append_bet(BET_LOG,record,st.secrets)
                    st.session_state[PROJECTION_PARLAY_KEY]=[]
                    st.success(f"Saved {len(legs)}-leg model parlay to Bet Tracker · no sportsbook price was assumed.")
                except Exception as exc:
                    st.error(f"Could not save parlay: {exc}")
        else:
            st.info("Add at least one more leg to save a parlay ticket.")

def market_recommendation(proj,odds_rows,market_key,default_line,kind):
    base_key=market_key.replace("_alternate",""); allowed={market_key,base_key}; rows=[r for r in odds_rows if r.get("market") in allowed and r.get("point") is not None]
    line=default_line; over_price=under_price=None
    if rows:
        points=[]
        for r in rows:
            try: points.append(float(r["point"]))
            except Exception: pass
        if points: line=min(points,key=lambda x:abs(x-default_line))
        chosen=[r for r in rows if abs(float(r.get("point"))-line)<1e-9]
        over_offers=[r for r in chosen if str(r.get("name","")).lower()=="over" and r.get("price") is not None]
        under_offers=[r for r in chosen if str(r.get("name","")).lower()=="under" and r.get("price") is not None]
        if over_offers: over_price=max(float(r.get("price")) for r in over_offers)
        if under_offers: under_price=max(float(r.get("price")) for r in under_offers)
    history=load_projection_history(); cutoff=int(math.floor(line)+1)
    if kind=="k":
        sim=float(proj.engine.simulation_probabilities.get(float(cutoff),np.mean(proj.k_samples>=cutoff)))
        math_p=float(proj.engine.mathematical_probabilities.get(float(cutoff),0.0))
        cal=calibrate_blend(history,cutoff)
        over_model=cal.weight_simulation*sim+cal.weight_math*math_p
        projection_mean=proj.mean_k
    else:
        sim=float(proj.outs_engine.simulation_probabilities.get(float(line),np.mean(proj.outs_samples>=cutoff)))
        math_p=float(proj.outs_engine.mathematical_probabilities.get(float(line),0.0))
        cal=calibrate_outs_blend(history,float(line))
        over_model=cal.weight_simulation*sim+cal.weight_math*math_p
        projection_mean=proj.mean_outs
    decision=aligned_bet_lean(
        projection_mean,
        line,
        over_model,
        over_implied=implied_prob(over_price) if over_price is not None else None,
        under_implied=implied_prob(under_price) if under_price is not None else None,
        has_market=bool(rows),
    )
    confidence=abs(decision.model_probability-.5)*2
    return {"side":decision.side,"line":line,"model":decision.model_probability,"edge":decision.edge,"confidence":confidence,"has_market":bool(rows),"reason":decision.reason,"projection_mean":projection_mean,"over_model":over_model}

def apply_active_line_to_recommendation(reco,proj,market_key,line,hits_proj=None,source="MANUAL"):
    if line is None:
        return dict(reco)
    line=float(line)
    over_model=float(market_model_probability(proj,market_key,line,hits_proj))
    projection_mean=float(reco.get("projection_mean",0.0))
    decision=aligned_bet_lean(projection_mean,line,over_model,has_market=False)
    updated=dict(reco)
    updated.update({
        "side":decision.side,"line":line,"model":decision.model_probability,"edge":decision.edge,
        "confidence":abs(decision.model_probability-.5)*2,"has_market":True,"reason":decision.reason,
        "projection_mean":projection_mean,"over_model":over_model,"active_line":True,"active_line_source":str(source or "MANUAL").upper(),
    })
    return updated

def no_active_line_recommendation(label, projection_mean):
    return {
        "side":"NO LINE","line":None,"model":None,"edge":None,"confidence":0.0,
        "has_market":False,"reason":"no_active_market_line","projection_mean":float(projection_mean),
        "over_model":None,"label":label,"active_line":False,"active_line_source":"",
    }


def render_reco(card,reco):
    side=str(reco.get("side","NO LINE")).upper()
    line=reco.get("line")
    no_line=line is None or side=="NO LINE"
    projection_mean=pd.to_numeric(pd.Series([reco.get("projection_mean")]),errors="coerce").iloc[0]
    projection_text="—" if pd.isna(projection_mean) else f"{float(projection_mean):.2f}"
    active_source=str(reco.get("active_line_source","") or "").strip().upper()
    if no_line:
        cls="reco-neutral"
        side_text=f"{projection_text} PROJ"
        line_text="NO ACTIVE LINE"
        meta="Bet lean waits for a Daily Projection Run sportsbook line"
        line_class="reco-line"
    else:
        cls="reco-warn" if side=="PASS" else "reco-under" if side=="UNDER" else "reco-good"
        side_text=side
        line_text=f"{float(line):g} LINE"
        line_class="reco-line manual-active" if active_source=="MANUAL" else "reco-line"
        reason_labels={
            "no_positive_aligned_edge":"EDGE BELOW 2%",
            "probability_conflicts_with_projection":"PROJECTION / PROBABILITY DISAGREE",
            "projection_on_line":"PROJECTION ON LINE",
            "insufficient_model_confidence":"MODEL CONFIDENCE BELOW 58%",
            "model_direction":"MODEL LEAN",
            "aligned_positive_edge":"POSITIVE ALIGNED EDGE",
        }
        model=reco.get("model")
        edge=reco.get("edge")
        if side=="PASS":
            meta=f"Proj {projection_text} vs {float(line):g} · {reason_labels.get(reco.get('reason'),'NO BET')}"
        else:
            model_text="—" if model is None else f"{float(model):.1%}"
            edge_text="MODEL LEAN" if edge is None else f"EDGE {float(edge):+.1%}"
            meta=f"Model {model_text} · {edge_text}"
        if active_source=="MANUAL":
            meta += " · MANUAL · DAILY RUN"
        elif active_source:
            meta += f" · {active_source}"
    emblem_class=("whiff" if "STRIKEOUT" in str(reco.get("label","")) else "glove" if "OUTS" in str(reco.get("label","")) else "contact")
    with card:
        st.markdown(f'<div class="reco-card {cls}"><div class="cc-card-top"><div class="cc-card-icon cc-emblem {emblem_class}" aria-hidden="true"></div><div class="reco-label">{reco["label"]}</div></div><div class="reco-side {cls}">{side_text}</div><div class="{line_class}">{line_text}</div><div class="reco-meta">{meta}</div></div>',unsafe_allow_html=True)


def render_calibration_dashboard():
    st.markdown("### Milestone Calibration Dashboard"); st.caption("Resolved pregame projections only. Sportsbook prices are excluded from training.")
    history=load_projection_history(); report=milestone_calibration_report(history,range(3,13),min_observations=30); display=report.copy()
    for col in ["Simulation Brier","Math Brier","Calibrated Brier"]: display[col]=display[col].map(lambda x:"—" if pd.isna(x) else f"{x:.4f}")
    for col in ["Simulation Weight","Math Weight","Actual Hit Rate"]: display[col]=display[col].map(lambda x:"—" if pd.isna(x) else f"{x:.1%}")
    st.dataframe(display,use_container_width=True,hide_index=True); resolved=int(pd.to_numeric(history.get("actual_strikeouts"),errors="coerce").notna().sum()) if not history.empty and "actual_strikeouts" in history.columns else 0; st.info(f"{resolved} resolved projections currently available. Each milestone learns independently after 30 valid observations; until then it stays at a 50/50 simulation/math baseline.")

def ladder(proj,max_line=10):
    history=load_projection_history(); rows=[]
    for line in range(3,max_line+1):
        cal=calibrate_blend(history,line); sim=proj.engine.simulation_probabilities.get(float(line),0.0); analytic=proj.engine.mathematical_probabilities.get(float(line),0.0); w=cal.weight_simulation; blended=w*sim+(1-w)*analytic; rows.append({"Line":f"{line}+","Probability":blended,"Fair Odds":american(blended),"Simulation":sim,"Math":analytic,"Sim Weight":w})
    return pd.DataFrame(rows)

def market_model_probability(proj,market,line,hits_proj=None):
    line=float(line); cutoff=int(math.floor(line)+1); history=load_projection_history()
    if market in ("pitcher_strikeouts","pitcher_strikeouts_alternate"):
        sim=float(proj.engine.simulation_probabilities.get(float(cutoff),np.mean(proj.k_samples>=cutoff))); math_p=float(proj.engine.mathematical_probabilities.get(float(cutoff),0.0)); cal=calibrate_blend(history,cutoff); return cal.weight_simulation*sim+cal.weight_math*math_p
    if market in ("pitcher_hits_allowed","pitcher_hits_allowed_alternate") and hits_proj is not None:
        sim=float(hits_proj.simulation_probabilities.get(line,np.mean(hits_proj.simulation_samples>=cutoff))); math_p=float(hits_proj.mathematical_probabilities.get(line,0.0)); cal=calibrate_hits_blend(history,line); return cal.weight_simulation*sim+cal.weight_math*math_p
    sim=float(proj.outs_engine.simulation_probabilities.get(line,np.mean(proj.outs_samples>=cutoff))); math_p=float(proj.outs_engine.mathematical_probabilities.get(line,0.0)); cal=calibrate_outs_blend(history,line); return cal.weight_simulation*sim+cal.weight_math*math_p

def build_market_table(proj,odds_rows,hits_proj=None):
    grouped={}
    for r in odds_rows:
        try: line=float(r["point"])
        except Exception: continue
        key=(r["book"],r["market"],line); grouped.setdefault(key,{})[str(r.get("name","")).lower()]=r.get("price")
    rows=[]
    for (book,market,line),prices in grouped.items():
        model=market_model_probability(proj,market,line,hits_proj); over=prices.get("over"); under=prices.get("under"); op=implied_prob(over) if over is not None else None; up=implied_prob(under) if under is not None else None; oe=model-op if op is not None else None; ue=(1-model)-up if up is not None else None; best=max([e for e in (oe,ue) if e is not None],default=None)
        rows.append({"Market":"K" if "strikeouts" in market else "HITS" if "hits_allowed" in market else "OUTS","Type":"ALT" if market.endswith("_alternate") else "MAIN","Book":book,"Line":f"{line:g}","Over":over,"Under":under,"Model":model,"Over Edge":oe,"Under Edge":ue,"Best Edge":best})
    return pd.DataFrame(rows).sort_values(["Market","Line","Book"]) if rows else pd.DataFrame()

with st.sidebar:
    render_sidebar_brand()
    _nav_options=["Projection","Distribution","Form & Workload","Model Card","Bet Tracker","Projection History","Daily Projection Run","Top Plays"]
    _nav_target=st.session_state.pop("projection_nav_target",None)
    if _nav_target in _nav_options:
        st.session_state["main_projection_navigation"]=_nav_target
    if st.session_state.get("main_projection_navigation") not in _nav_options:
        st.session_state["main_projection_navigation"]="Projection"
    nav=st.radio("Navigation",_nav_options,label_visibility="collapsed",key="main_projection_navigation")
    if nav == "Bet Tracker":
        st.switch_page("pages/2_Bet_Tracker.py")
    if nav == "Daily Projection Run":
        st.switch_page("pages/5_Daily_Projection_Run.py")
    if nav == "Projection History":
        st.switch_page("pages/4_Projection_History.py")
    if nav == "Top Plays":
        st.switch_page("pages/6_Top_Plays.py")
    st.divider(); selected_date=st.date_input("Slate date",value=datetime.now(EASTERN).date()); st.markdown("### PITCHER")
    locked_key=st.session_state.get("locked_pitcher"); st.caption("Select a probable starter, then lock the projection 🔒")

schedule,err=get_schedule(selected_date.isoformat())
if err: st.error(err)
if not schedule: st.warning("No announced probable pitchers are available for this date."); st.stop()
locked_game=next((g for g in schedule if g.key==locked_key),None) if locked_key else None
if locked_key and locked_game is None: st.session_state["locked_pitcher"]=None; locked_key=None
matches=schedule if locked_game is None else [locked_game]
if not matches: st.info("No probable pitchers are available for this slate."); st.stop()
names=[f"{g.pitcher_name} · {g.team} vs {g.opponent}" for g in matches]
with st.sidebar:
    default_index=names.index(f"{locked_game.pitcher_name} · {locked_game.team} vs {locked_game.opponent}") if locked_game else 0
    choice=st.selectbox("Matching pitchers",names,index=default_index,label_visibility="collapsed",key="pitcher_selector",disabled=bool(locked_game))
game=matches[names.index(choice)]; locked=st.session_state.get("locked_pitcher")==game.key
with st.sidebar:
    render_sidebar_pitcher_identity(
        pitcher_name=game.pitcher_name, team=game.team, opponent=game.opponent,
        team_id=TEAM_ID_BY_ABBR.get(game.team,0),
    )
    if st.button("🔒 LOCK PITCHER" if not locked else "🔓 UNLOCK PITCHER",use_container_width=True): st.session_state["locked_pitcher"]=None if locked else game.key; st.rerun()

log,herr=get_log(game.pitcher_id,selected_date.year)
if len(log) < TARGET_STARTER_HISTORY:
    prior,prior_err=get_log(game.pitcher_id,selected_date.year-1)
    log=combine_starter_history(log,prior)
    herr=herr or prior_err
if log.empty: st.error(herr or "Pitcher starter history unavailable."); st.stop()
pitcher_hand=get_pitcher_hand(game.pitcher_id)
opponent_team_id=TEAM_ID_BY_ABBR.get(game.opponent,0)
lineup_context=get_confirmed_lineup(game.game_pk,opponent_team_id)
opposing_batters=get_opposing_batters(
    game.opponent,pitcher_hand,selected_date.year,opponent_team_id,
    lineup_context.player_ids if lineup_context.confirmed else (),
    lineup_context.spots if lineup_context.confirmed else (),
)
opponent_matchup=matchup_summary(opposing_batters,confirmed_lineup=lineup_context.confirmed)
weather_risk=get_game_weather(game.venue_id,game.game_time,game.venue_latitude,game.venue_longitude)
confirmed_count=lineup_context.batter_count if lineup_context.confirmed else 0
workload_ctx=build_workload_context(log,game.game_time)
role_workload_decision=build_role_workload_decision(
    log,workload_ctx,load_role_runtime_state(),game.game_time,
    mode=os.getenv("STRIKEOUT_ROLE_WORKLOAD_MODE","shadow"),
)
effective_workload_ctx=role_workload_decision.effective
team_leash_ctx=build_team_leash_context(load_projection_history(),load_observation_history(),game.team,game.game_time)
team_leash_candidate=candidate_workload_fields(team_leash_ctx,workload_ctx.expected_pitches,workload_ctx.expected_bf,workload_ctx.expected_outs)
proj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count,effective_workload_ctx); kdf=ladder(proj,12)
features_for_hits=build_engine_features(log,game,float(opponent_matchup["k_rate"]),confirmed_count,effective_workload_ctx)
hits_seed=int(hashlib.sha256(f"hits|{game.key}|{game.game_time}|{APP_VERSION}".encode()).hexdigest()[:8],16)
hits_proj=project_hits_allowed(log,expected_bf=features_for_hits["expected_bf"],bf_sd=workload_ctx.bf_sd,opponent_hit_rate=float(opponent_matchup.get("hit_rate",.235)),seed=hits_seed,draws=25000,lines=(3.5,4.5,5.5,6.5,7.5,8.5))
# MAIN_PROJECTION_DURABLE_LINES_V1
durable_archive=load_projection_archive(ARCHIVE_PATH,st.secrets)
_manual_probe=pd.DataFrame([{"game_pk":game.game_pk,"pitcher_id":game.pitcher_id}])
_manual_probe=overlay_manual_market_lines(_manual_probe,durable_archive)
_manual_row=_manual_probe.iloc[0] if not _manual_probe.empty else pd.Series(dtype=object)
def _durable_line(col):
    value=pd.to_numeric(pd.Series([_manual_row.get(col)]),errors="coerce").iloc[0]
    return None if pd.isna(value) else float(value)
def _durable_source(col):
    value=_manual_row.get(col,"")
    return "" if pd.isna(value) else str(value).strip().upper()
manual_k_line=_durable_line("active_strikeout_line")
manual_outs_line=_durable_line("active_outs_line")
manual_hits_line=_durable_line("active_hits_allowed_line")
manual_k_source=_durable_source("active_strikeout_line_source")
manual_outs_source=_durable_source("active_outs_line_source")
manual_hits_source=_durable_source("active_hits_allowed_line_source")
odds_rows=load_pitcher_strikeout_odds(game.pitcher_name,selected_date.isoformat())
odds_err=("" if odds_rows else "No saved strikeout odds for this pitcher/slate yet. Use the paid manual button on Daily Projection Run; this page never calls the Odds API.")
k_reco=market_recommendation(proj,odds_rows,"pitcher_strikeouts_alternate",5.5,"k"); k_reco["label"]="STRIKEOUT BET LEAN"
out_reco=market_recommendation(proj,odds_rows,"pitcher_outs_alternate",15.5,"outs"); out_reco["label"]="TOTAL OUTS BET LEAN"
hit_rows=[r for r in odds_rows if r.get("market") in {"pitcher_hits_allowed","pitcher_hits_allowed_alternate"} and r.get("point") is not None]
hit_line=min([float(r["point"]) for r in hit_rows],key=lambda x:abs(x-5.5)) if hit_rows else 5.5
hit_sim=float(hits_proj.simulation_probabilities.get(float(hit_line),0.0)); hit_math=float(hits_proj.mathematical_probabilities.get(float(hit_line),0.0))
hit_cal=calibrate_hits_blend(load_projection_history(),float(hit_line)); hit_over=hit_cal.weight_simulation*hit_sim+hit_cal.weight_math*hit_math
hit_over_offer=best_market_offer(odds_rows,{"pitcher_hits_allowed","pitcher_hits_allowed_alternate"},hit_line,"OVER")
hit_under_offer=best_market_offer(odds_rows,{"pitcher_hits_allowed","pitcher_hits_allowed_alternate"},hit_line,"UNDER")
hit_over_price=hit_over_offer.get("price") if hit_over_offer else None
hit_under_price=hit_under_offer.get("price") if hit_under_offer else None
hit_decision=aligned_bet_lean(hits_proj.ensemble_mean,hit_line,hit_over,over_implied=implied_prob(hit_over_price) if hit_over_price is not None else None,under_implied=implied_prob(hit_under_price) if hit_under_price is not None else None,has_market=bool(hit_rows))
hit_reco={"side":hit_decision.side,"line":hit_line,"model":hit_decision.model_probability,"edge":hit_decision.edge,"confidence":abs(hit_decision.model_probability-.5)*2,"has_market":bool(hit_rows),"label":"HITS ALLOWED BET LEAN","reason":hit_decision.reason,"projection_mean":hits_proj.ensemble_mean,"over_model":hit_over}

if manual_k_line is not None:
    k_reco=apply_active_line_to_recommendation(k_reco,proj,"pitcher_strikeouts",manual_k_line,hits_proj,manual_k_source or "MANUAL")
elif k_reco.get("has_market"):
    k_reco["active_line_source"]="PAID API · SAVED SNAPSHOT"
else:
    k_reco=no_active_line_recommendation("STRIKEOUT BET LEAN",proj.mean_k)

if manual_outs_line is not None:
    out_reco=apply_active_line_to_recommendation(out_reco,proj,"pitcher_outs",manual_outs_line,hits_proj,manual_outs_source or "MANUAL")
elif out_reco.get("has_market"):
    out_reco["active_line_source"]="SAVED SNAPSHOT"
else:
    out_reco=no_active_line_recommendation("TOTAL OUTS BET LEAN",proj.mean_outs)

if manual_hits_line is not None:
    hit_reco=apply_active_line_to_recommendation(hit_reco,proj,"pitcher_hits_allowed",manual_hits_line,hits_proj,manual_hits_source or "MANUAL")
elif hit_reco.get("has_market"):
    hit_reco["active_line_source"]="SAVED SNAPSHOT"
else:
    hit_reco=no_active_line_recommendation("HITS ALLOWED BET LEAN",hits_proj.ensemble_mean)

def _active_line(reco):
    value=pd.to_numeric(pd.Series([reco.get("line")]),errors="coerce").iloc[0]
    return None if pd.isna(value) else float(value)

active_k_line=_active_line(k_reco)
active_outs_line=_active_line(out_reco)
active_hits_line=_active_line(hit_reco)
active_k_source=str(k_reco.get("active_line_source","") or "").strip().upper()
active_outs_source=str(out_reco.get("active_line_source","") or "").strip().upper()
active_hits_source=str(hit_reco.get("active_line_source","") or "").strip().upper()

if nav=="Distribution":
    st.markdown('<div class="section-head">DISTRIBUTION</div>',unsafe_allow_html=True); st.caption(f"{game.pitcher_name} · {game.team} vs {game.opponent}"); a,b=st.columns(2)
    with a:
        st.markdown("### Strikeout probability distribution")
        st.bar_chart(pd.DataFrame({"Probability":proj.k_probs},index=np.arange(len(proj.k_probs))))
        explain_popover(static_explanation("distribution_k"),label="ⓘ EXPLAIN K DISTRIBUTION")
    with b:
        st.markdown("### Outs probability distribution")
        st.bar_chart(pd.DataFrame({"Probability":proj.outs_probs},index=np.arange(len(proj.outs_probs))))
        explain_popover(static_explanation("distribution_outs"),label="ⓘ EXPLAIN OUTS DISTRIBUTION")
    st.stop()
elif nav=="Form & Workload":
    st.markdown('<div class="section-head">FORM & WORKLOAD</div>',unsafe_allow_html=True); st.caption(f"{game.pitcher_name} · workload-v1 uses starter history only; sportsbook data is not an input.")
    w1,w2,w3,w4,w5,w6=st.columns(6)
    w1.metric("Expected pitches",f"{workload_ctx.expected_pitches:.1f}")
    w2.metric("Expected BF",f"{workload_ctx.expected_bf:.1f}")
    w3.metric("Expected outs",f"{workload_ctx.expected_outs:.1f}")
    w4.metric("Pitches / BF",f"{workload_ctx.pitches_per_bf:.2f}")
    w5.metric("Days since last start","—" if workload_ctx.days_since_last_start is None else workload_ctx.days_since_last_start)
    w6.metric("Recent leash",workload_ctx.leash_label)
    explain_popover(static_explanation("workload_primary"),label="ⓘ EXPLAIN WORKLOAD BLOCK")
    st.caption(f"Pitch trend {workload_ctx.pitch_trend:+.1%} · BF trend {workload_ctx.bf_trend:+.1%} · outs trend {workload_ctx.outs_trend:+.1%} · short-rest exposure multiplier {workload_ctx.rest_multiplier:.3f}.")
    role_name="LOW_RECENT_EXPOSURE" if role_workload_decision.role=="RESTRICTED" else role_workload_decision.role
    st.markdown("#### 🧪 Starter role workload · SHADOW / FEATURE GATED")
    r1,r2,r3,r4,r5=st.columns(5)
    r1.metric("Role",role_name)
    r2.metric("Gate mode",role_workload_decision.mode.upper())
    r3.metric("Candidate pitches",f"{role_workload_decision.candidate.expected_pitches:.1f}")
    r4.metric("Candidate BF",f"{role_workload_decision.candidate.expected_bf:.1f}")
    r5.metric("Candidate outs",f"{role_workload_decision.candidate.expected_outs:.1f}")
    explain_popover(static_explanation("role_shadow"),label="ⓘ EXPLAIN ROLE SHADOW")
    st.caption(f"Applied to projection: {'YES' if role_workload_decision.applied else 'NO'} · {role_workload_decision.reason} · corrections {role_workload_decision.correction_pitches:+.2f} pitches / {role_workload_decision.correction_bf:+.2f} BF / {role_workload_decision.correction_outs:+.2f} outs.")
    st.markdown("#### 🧭 Team leash candidate · CONTEXT ONLY")
    t1,t2,t3,t4,t5,t6=st.columns(6)
    t1.metric("Team starts tracked",team_leash_ctx.starts_used)
    t2.metric("Team avg pitches",f"{team_leash_ctx.team_avg_pitches:.1f}")
    t3.metric("Team avg BF",f"{team_leash_ctx.team_avg_bf:.1f}")
    t4.metric("TTO reached",f"{team_leash_ctx.tto_reach_rate:.1%}")
    t5.metric("90+ pitches",f"{team_leash_ctx.pitch_90_rate:.1%}")
    t6.metric("Team leash",team_leash_ctx.label)
    explain_popover(static_explanation("team_leash"),label="ⓘ EXPLAIN TEAM LEASH")
    st.caption(
        f"Status {team_leash_ctx.status} · candidate-only multipliers: pitches {team_leash_ctx.pitch_multiplier_candidate:.3f}, "
        f"BF {team_leash_ctx.bf_multiplier_candidate:.3f}, outs {team_leash_ctx.outs_multiplier_candidate:.3f}. "
        "These values do not alter Ks, Hits Allowed, Outs, or Top Plays until leakage-safe validation earns that right."
    )
    d=log.tail(15).copy(); st.line_chart(d.set_index("date")[["pitches","bf","outs","k"]]); st.dataframe(d.sort_values("date",ascending=False),use_container_width=True,hide_index=True); explain_popover(static_explanation("form_history"),label="ⓘ EXPLAIN RECENT STARTS"); st.stop()
elif nav=="Model Card":
    st.markdown('<div class="section-head">MODEL CARD</div>',unsafe_allow_html=True); st.write("Two independent paths: (1) plate-appearance Monte Carlo game simulation with workload uncertainty; (2) independent mathematical Negative-Binomial probability model. Milestone probabilities are calibrated from resolved pregame projections when enough observations exist. Sportsbook prices are used only for edge display, never to create the baseball forecast."); st.markdown("### Path comparison"); path_df=pd.DataFrame([{"Path":"Simulation","Mean K":proj.engine.simulation_mean,"SD":proj.engine.simulation_sd},{"Path":"Mathematical","Mean K":proj.engine.mathematical_mean,"SD":proj.engine.mathematical_sd},{"Path":"Ensemble","Mean K":proj.mean_k,"SD":proj.k_sd}]); path_df["Mean K"]=path_df["Mean K"].map(lambda v:f"{v:.2f}"); path_df["SD"]=path_df["SD"].map(lambda v:f"{v:.2f}"); st.dataframe(path_df,use_container_width=True,hide_index=True); explain_popover(static_explanation("model_paths"),label="ⓘ EXPLAIN MODEL PATHS"); model_view=kdf[["Line","Probability","Simulation","Math","Sim Weight"]].copy()
    for c in ("Probability","Simulation","Math","Sim Weight"): model_view[c]=model_view[c].map(lambda v:f"{v:.1%}")
    st.dataframe(model_view,use_container_width=True,hide_index=True); explain_popover(static_explanation("model_ladder"),label="ⓘ EXPLAIN MILESTONE TABLE"); st.markdown("### Calibration diagnostics"); render_calibration_dashboard(); st.dataframe(calibration_summary(load_projection_history()),use_container_width=True,hide_index=True); explain_popover(static_explanation("calibration"),label="ⓘ EXPLAIN CALIBRATION"); render_ml_shadow_dashboard(game); explain_popover(static_explanation("ml_shadow"),label="ⓘ EXPLAIN ML SHADOW"); st.stop()
elif nav=="Bet Tracker":
    st.markdown('<div class="section-head">BET TRACKER</div>',unsafe_allow_html=True); st.caption("Current pitcher markets available from the Odds API are shown here when posted.")
    if odds_err: st.info(odds_err)
    if odds_rows: st.dataframe(pd.DataFrame(odds_rows),use_container_width=True,hide_index=True)
    else: st.info("No live player-prop markets are currently available for this game.")
    st.stop()
elif nav=="Projection History":
    st.markdown('<div class="section-head">PROJECTION HISTORY</div>',unsafe_allow_html=True); history=st.session_state.get("projection_history",[]); current={"Date":selected_date.isoformat(),"Pitcher":game.pitcher_name,"Matchup":f"{game.team} vs {game.opponent}","Projected K":round(proj.mean_k,2),"3+":f"{kdf.iloc[0].Probability:.1%}","5+":f"{kdf.iloc[2].Probability:.1%}"}
    if st.button("Save current projection"): history.append(current); st.session_state["projection_history"]=history; st.rerun()
    st.dataframe(pd.DataFrame(history) if history else pd.DataFrame([current]),use_container_width=True,hide_index=True); st.stop()
elif nav=="Daily Projection Run":
    st.markdown('<div class="section-head">DAILY PROJECTION RUN</div>',unsafe_allow_html=True); st.write(f"Slate: {selected_date.isoformat()} · {len(matches)} probable pitcher entries loaded."); st.dataframe(pd.DataFrame([{"Pitcher":g.pitcher_name,"Team":g.team,"Opponent":g.opponent,"Status":g.status} for g in matches]),use_container_width=True,hide_index=True); st.info("Select a pitcher from the left-rail dropdown to run the full two-path projection for that pitcher."); st.stop()

if not locked: st.info("Lock the pitcher in the left rail to freeze all projection outputs for this pitcher.")
weather_marker=f" {weather_risk.icon}" if weather_risk.icon else ""
_weather_level=str(weather_risk.level or "UNKNOWN").upper()
_weather_icon=weather_risk.icon or ("☀️" if str(weather_risk.level or "").upper()=="NONE" else "✓" if weather_risk.available else "—")
_weather_label={"HIGH":"DELAY RISK","ELEVATED":"RAIN WATCH","LOW":"LOW RAIN RISK","NONE":"CLEAR","ROOF":"ROOF PROTECTED","UNKNOWN":"UNAVAILABLE"}.get(_weather_level,_weather_level)
_weather_action={"HIGH":"AVOID · DELAY RISK","ELEVATED":"CAUTION · RECHECK","LOW":"MONITOR NEAR FIRST PITCH","NONE":"NO DELAY SIGNAL","ROOF":"RAIN DELAY MITIGATED · VERIFY ROOF","UNKNOWN":"VERIFY WEATHER"}.get(_weather_level,"VERIFY WEATHER")
_weather_class={"HIGH":"weather-high","ELEVATED":"weather-elevated","LOW":"weather-low","NONE":"weather-none","ROOF":"weather-none"}.get(_weather_level,"weather-unknown")
_weather_prob="—" if weather_risk.precip_probability is None else f"{weather_risk.precip_probability:.0f}%"
_weather_peak="—" if weather_risk.precipitation_mm is None else f"{weather_risk.precipitation_mm:.1f} mm/h"
_weather_summary=re.sub(r"[<>]","",str(weather_risk.summary or "Weather forecast unavailable for this game window."))
render_command_center_hero(
    confidence=proj.confidence,
    quality=proj.quality,
    locked=locked,
    app_version=APP_VERSION,
)
render_matchup_strip(
    pitcher_name=game.pitcher_name,
    team=game.team,
    opponent=game.opponent,
    venue=game.venue,
    side=game.side,
    status=game.status,
    game_time=game.game_time,
    locked=locked,
    weather_icon=weather_risk.icon or "",
    weather_level=_weather_level,
    team_id=TEAM_ID_BY_ABBR.get(game.team,0),
)
st.markdown('<div class="section-head">ACTIVE SPORTSBOOK LINES</div>',unsafe_allow_html=True)
_line_cols=st.columns(3)
for _col,_label,_line,_source in zip(
    _line_cols,("STRIKEOUTS","TOTAL OUTS","HITS ALLOWED"),
    (active_k_line,active_outs_line,active_hits_line),(active_k_source,active_outs_source,active_hits_source),
):
    _manual=str(_source or "").upper()=="MANUAL"
    _cls="active-market-line manual" if _manual else "active-market-line"
    _value="—" if _line is None else f"{float(_line):g}"
    _source_text="MANUAL · DAILY RUN" if _manual else (str(_source) if _source else "NO ACTIVE LINE")
    with _col:
        st.markdown(f'<div class="{_cls}"><div class="label">{_label}</div><div class="value">{_value}</div><div class="source">{_source_text}</div></div>',unsafe_allow_html=True)
explain_popover(static_explanation("active_lines"),label="ⓘ EXPLAIN ACTIVE LINES")
st.caption("Manual Daily Run lines appear in orange; a saved paid K snapshot appears with its source label. No active line means the projection still shows, but the app will not manufacture a bet lean. Execution lines never alter the baseball projection.")
st.markdown('<div class="section-head">PROJECTION SUMMARY</div>',unsafe_allow_html=True)
alt_k_choice=best_alt_k([(int(str(row["Line"]).rstrip("+")),float(row["Probability"])) for _,row in kdf.iterrows()])
alt_k_html=(f'<div class="alt-k-badge">BEST ALT K · {alt_k_choice.milestone}+ · {alt_k_choice.probability:.0%} HIT</div>' if alt_k_choice else '<div class="alt-k-badge">BEST ALT K · NO 70%+ ALT</div>')
c1,c2,c3,c4=st.columns(4)
with c1:
    st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon cc-emblem whiff" aria-hidden="true"></div><div class="metric-label">PROJECTED STRIKEOUTS</div></div><div class="metric-value">{proj.mean_k:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.k_samples,.1))}-{int(np.quantile(proj.k_samples,.9))}</span>{alt_k_html}</div>',unsafe_allow_html=True)
    explain_popover(projection_metric_explanation("Strikeouts",proj.mean_k,int(np.quantile(proj.k_samples,.1)),int(np.quantile(proj.k_samples,.9)),extra=(f"Best supported alt K: {alt_k_choice.milestone}+ at {alt_k_choice.probability:.0%}" if alt_k_choice else "No 70%+ alt K milestone",)),label="ⓘ WHY THIS K PROJECTION?")
render_reco(c2,k_reco)
with c2:
    explain_popover(recommendation_explanation(k_reco,"Strikeouts"),label="ⓘ WHY THIS K DECISION?")
with c3:
    st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon cc-emblem glove" aria-hidden="true"></div><div class="metric-label">PROJECTED OUTS</div></div><div class="metric-value">{proj.mean_outs:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.outs_samples,.1))}-{int(np.quantile(proj.outs_samples,.9))}</span></div>',unsafe_allow_html=True)
    explain_popover(projection_metric_explanation("Total Outs",proj.mean_outs,int(np.quantile(proj.outs_samples,.1)),int(np.quantile(proj.outs_samples,.9))),label="ⓘ WHY THIS OUTS PROJECTION?")
render_reco(c4,out_reco)
with c4:
    explain_popover(recommendation_explanation(out_reco,"Total Outs"),label="ⓘ WHY THIS OUTS DECISION?")
h1,h2,h3=st.columns([1,1,2])
with h1:
    st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon cc-emblem contact" aria-hidden="true"></div><div class="metric-label">PROJECTED HITS ALLOWED</div></div><div class="metric-value">{hits_proj.ensemble_mean:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(hits_proj.simulation_samples,.1))}-{int(np.quantile(hits_proj.simulation_samples,.9))}</span></div>',unsafe_allow_html=True)
    explain_popover(projection_metric_explanation("Hits Allowed",hits_proj.ensemble_mean,int(np.quantile(hits_proj.simulation_samples,.1)),int(np.quantile(hits_proj.simulation_samples,.9))),label="ⓘ WHY THIS HITS PROJECTION?")
render_reco(h2,hit_reco)
with h2:
    explain_popover(recommendation_explanation(hit_reco,"Hits Allowed"),label="ⓘ WHY THIS HITS DECISION?")
with h3:
    st.markdown(
        f'<div class="game-weather-card {_weather_class}"><div class="game-weather-head"><div><div class="game-weather-title">GAME WEATHER · DELAY RISK</div><div class="game-weather-risk">{_weather_label}</div><div class="game-weather-action">{_weather_action}</div></div><div class="game-weather-icon" aria-hidden="true">{_weather_icon}</div></div><div class="game-weather-grid"><div class="game-weather-stat"><span>Precip chance</span><strong>{_weather_prob}</strong></div><div class="game-weather-stat"><span>Peak precip</span><strong>{_weather_peak}</strong></div></div><div class="game-weather-reason">{_weather_summary}</div><div class="game-weather-note">Game window: 2h before first pitch → 4h after · Roof-capable parks suppress false exterior-rain avoid signals; verify retractable-roof status near first pitch. Weather does not modify the projection.</div></div>',
        unsafe_allow_html=True,
    )
    explain_popover(weather_explanation(level=weather_risk.level,precip_probability=weather_risk.precip_probability,precipitation_mm=weather_risk.precipitation_mm,summary=weather_risk.summary),label="ⓘ WHY THIS WEATHER STATUS?")

st.markdown('<div class="section-head">OPPOSING BATTER BOX</div>',unsafe_allow_html=True)
lineup_label="✅ CONFIRMED BATTING ORDER" if lineup_context.confirmed else "ACTIVE ROSTER FALLBACK · lineup not posted yet"
st.caption(f"{lineup_label} · {game.opponent} hitters vs a {pitcher_hand or 'unknown-hand'} pitcher. Pitcher-hand K% and H/PA feed the baseball matchup; incomplete hitter splits shrink safely toward league rates.")
if opposing_batters.empty:
    st.info("Opposing batter split data is not available yet. The projection falls back to protected league opponent baselines.")
else:
    b1,b2,b3,b4,b5=st.columns(5)
    b1.metric("Matchup K%",f"{float(opponent_matchup['k_rate']):.1%}")
    b2.metric("Matchup H/PA",f"{float(opponent_matchup.get('hit_rate',.235)):.1%}")
    b3.metric("Split PA",int(opponent_matchup["pa"]))
    b4.metric("HIGH K hitters",int(opponent_matchup["high"]))
    b5.metric("ELEVATED K hitters",int(opponent_matchup["elevated"]))
    explain_popover(static_explanation("opposing_batters"),label="ⓘ EXPLAIN BATTER MATCHUP")
    batter_display=opposing_batters.copy()
    batter_display["K% vs Pitcher"]=pd.to_numeric(batter_display["K% vs Pitcher"],errors="coerce")*100.0
    batter_display["H/PA vs Pitcher"]=pd.to_numeric(batter_display["H/PA vs Pitcher"],errors="coerce")*100.0
    batter_display["Risk"]=batter_display["Risk"].map({"HIGH":"🔥 HIGH","ELEVATED":"⚠️ ELEVATED","NORMAL":"NORMAL"}).fillna(batter_display["Risk"])
    batter_display["Split Available"]=batter_display["Split Available"].map({True:"MLB split",False:"League fallback"}).fillna("League fallback")
    columns=["Lineup Spot","Batter","Hand","K% vs Pitcher","H/PA vs Pitcher","PA","Risk","Split Available"] if lineup_context.confirmed else ["Batter","Hand","K% vs Pitcher","H/PA vs Pitcher","PA","Risk","Split Available"]
    st.dataframe(
        batter_display[columns],
        hide_index=True,
        width="stretch",
        column_config={
            "Lineup Spot":st.column_config.NumberColumn("Order",format="%.0f"),
            "Batter":st.column_config.TextColumn("Batter"),
            "Hand":st.column_config.TextColumn("Bats"),
            "K% vs Pitcher":st.column_config.NumberColumn(f"K% vs {pitcher_hand or 'Pitcher'}",format="%.1f%%"),
            "H/PA vs Pitcher":st.column_config.NumberColumn(f"H/PA vs {pitcher_hand or 'Pitcher'}",format="%.1f%%"),
            "PA":st.column_config.NumberColumn("Split PA",format="%.0f"),
            "Risk":st.column_config.TextColumn("K Risk"),
            "Split Available":st.column_config.TextColumn("Data"),
        },
    )

st.markdown('<div class="section-head">BET TRACKER / PARLAY ACTIONS</div>',unsafe_allow_html=True)
action_panel=st.container(border=True,key="cc_bet_action_panel")
action_panel.caption("Quick-add uses the real active line shown above. A sportsbook price may remain unpriced, but the app will not quick-add a fabricated/default market line.")
with action_panel:
    explain_popover(static_explanation("projection_actions"),label="ⓘ EXPLAIN BET ACTIONS")
quick_add_stake=action_panel.number_input("Quick-add stake",min_value=0.0,value=1.0,step=0.5,key=f"projection_quick_stake_{game.key}")
add1,add2,add3=action_panel.columns(3,gap="medium")
render_add_bet_button(add1,k_reco,"Strikeouts",{"pitcher_strikeouts","pitcher_strikeouts_alternate"},proj.mean_k,quick_add_stake,game,selected_date.isoformat(),odds_rows,proj.confidence,proj.quality,f"add_k_{game.key}")
render_add_bet_button(add2,out_reco,"Total Outs",{"pitcher_outs","pitcher_outs_alternate"},proj.mean_outs,quick_add_stake,game,selected_date.isoformat(),odds_rows,proj.confidence,proj.quality,f"add_outs_{game.key}")
render_add_bet_button(add3,hit_reco,"Hits Allowed",{"pitcher_hits_allowed","pitcher_hits_allowed_alternate"},hits_proj.ensemble_mean,quick_add_stake,game,selected_date.isoformat(),odds_rows,proj.confidence,proj.quality,f"add_hits_{game.key}")
with st.expander(f"🔎 Why this projection? · {game.pitcher_name}", expanded=False):
    st.caption("Live single-pitcher rationale using the same model paths shown in the projection cards. Sportsbook prices are comparison inputs only; they do not create the forecast.")
    x1,x2,x3,x4=st.columns(4)
    x1.metric("Projected Ks",f"{proj.mean_k:.2f}")
    x2.metric("Projected outs",f"{proj.mean_outs:.2f}")
    x3.metric("Projected hits allowed",f"{hits_proj.ensemble_mean:.2f}")
    x4.metric("Data quality",f"{proj.quality}/100")
    why_left,why_right=st.columns(2)
    with why_left:
        st.markdown("#### Strikeouts · 5+")
        k_cal=calibrate_blend(load_projection_history(),5)
        k_sim=float(proj.engine.simulation_probabilities.get(5.0,np.mean(proj.k_samples>=5)))
        k_math=float(proj.engine.mathematical_probabilities.get(5.0,0.0))
        k_blend=k_cal.weight_simulation*k_sim+k_cal.weight_math*k_math
        k_paths=pd.DataFrame([{"Path":"Simulation","Probability":k_sim,"Weight":k_cal.weight_simulation},{"Path":"Mathematical","Probability":k_math,"Weight":k_cal.weight_math}])
        for c in ("Probability","Weight"): k_paths[c]=k_paths[c].map(lambda v:f"{v:.1%}")
        st.dataframe(k_paths,use_container_width=True,hide_index=True)
        st.write(f"**Blended 5+ probability:** {k_blend:.1%}")
        st.caption(f"Calibration: {'learned' if k_cal.calibrated else '50/50 baseline'} · {k_cal.observations} compatible resolved observations.")
        st.write(f"Opponent K input: **{features_for_hits['opponent_k_pct']:.1%}**")
        st.write(f"Expected batters faced: **{features_for_hits['expected_bf']:.1f}**")
        st.write(f"Expected pitches: **{workload_ctx.expected_pitches:.1f}** · expected outs: **{workload_ctx.expected_outs:.1f}**")
        st.write(f"Pitch efficiency: **{workload_ctx.pitches_per_bf:.2f} pitches/BF** · recent leash: **{workload_ctx.leash_label}**")
        st.write(f"Days since last start: **{'—' if workload_ctx.days_since_last_start is None else workload_ctx.days_since_last_start}** · pitch trend: **{workload_ctx.pitch_trend:+.1%}**")
        st.write(f"Park K factor: **{features_for_hits['park_factor']:.3f}**")
    with why_right:
        st.markdown("#### Hits Allowed · Over 5.5")
        h_cal=calibrate_hits_blend(load_projection_history(),5.5)
        h_sim=float(hits_proj.simulation_probabilities.get(5.5,0.0))
        h_math=float(hits_proj.mathematical_probabilities.get(5.5,0.0))
        h_blend=h_cal.weight_simulation*h_sim+h_cal.weight_math*h_math
        h_paths=pd.DataFrame([{"Path":"Simulation","Probability":h_sim,"Weight":h_cal.weight_simulation},{"Path":"Mathematical","Probability":h_math,"Weight":h_cal.weight_math}])
        for c in ("Probability","Weight"): h_paths[c]=h_paths[c].map(lambda v:f"{v:.1%}")
        st.dataframe(h_paths,use_container_width=True,hide_index=True)
        st.write(f"**Blended O5.5 probability:** {h_blend:.1%}")
        st.caption(f"Calibration: {'learned' if h_cal.calibrated else '50/50 baseline'} · {h_cal.observations} resolved hit observations.")
        st.write(f"Pitcher hit rate: **{hits_proj.pitcher_hit_rate:.1%}**")
        st.write(f"Opponent hit-rate input: **{hits_proj.opponent_hit_rate:.1%}**")
        st.write(f"Matchup hit rate: **{hits_proj.matchup_hit_rate:.1%}**")
    st.markdown("#### Total Outs · Over 15.5")
    o_cal=calibrate_outs_blend(load_projection_history(),15.5)
    o_sim=float(proj.outs_engine.simulation_probabilities.get(15.5,0.0)); o_math=float(proj.outs_engine.mathematical_probabilities.get(15.5,0.0))
    o_blend=o_cal.weight_simulation*o_sim+o_cal.weight_math*o_math
    o_paths=pd.DataFrame([{"Path":"Simulation","Probability":o_sim,"Weight":o_cal.weight_simulation},{"Path":"Mathematical","Probability":o_math,"Weight":o_cal.weight_math}])
    for c in ("Probability","Weight"): o_paths[c]=o_paths[c].map(lambda v:f"{v:.1%}")
    st.dataframe(o_paths,use_container_width=True,hide_index=True)
    st.write(f"**Blended O15.5 probability:** {o_blend:.1%}")
    st.caption(f"Projected outs {proj.mean_outs:.2f} · SD {proj.outs_sd:.2f} · calibration {'learned' if o_cal.calibrated else '50/50 baseline'} · {o_cal.observations} resolved outs observations.")
    drivers=pd.DataFrame(proj.factors,columns=["Driver","Impact"]) if proj.factors else pd.DataFrame()
    if not drivers.empty:
        st.markdown("#### Leading model drivers")
        st.dataframe(drivers,use_container_width=True,hide_index=True)
market_command_row=st.container(border=True,key="cc_market_command_row")
left,right=market_command_row.columns([1.35,1],gap="large")
with left:
    st.markdown('<div class="section-head">STRIKEOUT MILESTONE LADDER</div>',unsafe_allow_html=True)
    view=kdf[["Line","Probability","Fair Odds","Simulation","Math","Sim Weight"]].copy()
    view["Probability"]=view["Probability"].map(lambda x:f"{x:.1%}")
    view["Simulation"]=view["Simulation"].map(lambda x:f"{x:.1%}")
    view["Math"]=view["Math"].map(lambda x:f"{x:.1%}")
    view["Sim Weight"]=view["Sim Weight"].map(lambda x:f"{x:.1%}")
    ladder_event=st.dataframe(
        view,use_container_width=True,hide_index=True,on_select="rerun",selection_mode="single-row",key=f"projection_k_ladder_{game.key}"
    )
    st.caption("Click any 3+ through 12+ milestone to add it as a straight or parlay leg. A milestone like 5+ is tracked as Over 4.5 so Bet Tracker grading matches K ≥ 5. Fair Odds are model-only and are never saved as a sportsbook price.")
    try:
        ladder_selected=list(ladder_event.selection.rows)
    except Exception:
        ladder_selected=list((ladder_event.get("selection",{}) or {}).get("rows",[])) if isinstance(ladder_event,dict) else []
    if ladder_selected:
        ladder_idx=int(ladder_selected[0])
        if 0<=ladder_idx<len(kdf):
            ladder_row=kdf.iloc[ladder_idx]
            milestone=int(str(ladder_row["Line"]).replace("+",""))
            tracker_line=float(milestone)-0.5
            model_probability=float(ladder_row["Probability"])
            ladder_offer=best_market_offer(odds_rows,{"pitcher_strikeouts","pitcher_strikeouts_alternate"},tracker_line,"OVER")
            offer_text=f" · exact posted {ladder_offer.get('book','')} {float(ladder_offer.get('price')):+.0f}" if ladder_offer is not None else " · no sportsbook price required"
            st.markdown(f"**Selected: {milestone}+ Ks · model {model_probability:.1%} · fair {ladder_row['Fair Odds']}**{offer_text}")
            ladder_straight,ladder_parlay=st.columns(2)
            if ladder_straight.button("➕ Add selected as straight",use_container_width=True,key=f"ladder_straight_{game.key}_{milestone}"):
                try:
                    price=save_projection_straight(
                        game=game,game_date=selected_date.isoformat(),market="Strikeouts",line=tracker_line,side="OVER",
                        projection=proj.mean_k,model_probability=model_probability,stake=quick_add_stake,
                        confidence=proj.confidence,data_quality=proj.quality,offer=ladder_offer,source="Projection Strikeout Ladder",
                    )
                    st.success(f"Added {milestone}+ K as Over {tracker_line:g} to Bet Tracker"+("" if price is not None else " · unpriced model straight"))
                except Exception as exc:
                    st.error(f"Could not add ladder straight: {exc}")
            if ladder_parlay.button("🎟️ Add selected to parlay",use_container_width=True,key=f"ladder_parlay_{game.key}_{milestone}"):
                leg=projection_parlay_leg(game,selected_date.isoformat(),"Strikeouts",tracker_line,"OVER",proj.mean_k,model_probability,proj.quality)
                added,message=queue_projection_parlay_leg(leg)
                (st.success if added else st.info)(message)
with right:
    st.markdown('<div class="section-head">MARKET ODDS / EDGE</div>',unsafe_allow_html=True)
    if odds_err: st.caption(odds_err)
    market_df=build_market_table(proj,odds_rows,hits_proj)
    if not market_df.empty:
        for c in ("Model","Over Edge","Under Edge","Best Edge"): market_df[c]=market_df[c].map(lambda x:"—" if pd.isna(x) else f"{x:.1%}")
        st.dataframe(market_df,use_container_width=True,hide_index=True)
        st.caption("Live sportsbook prices are shown for strikeouts, total outs, and hits allowed markets. Edge compares the independent model probability with implied probability; market prices never feed the forecast.")
    else: st.info("Live market data will populate here when the Odds API returns the pitcher props.")
st.markdown('<div class="section-head">PROJECTION PARLAY BUILDER</div>',unsafe_allow_html=True)
with st.container(border=True,key="cc_parlay_panel"):
    render_projection_parlay_builder()
st.markdown(f'<div class="search-note">Data status: {proj.confidence} confidence · quality {proj.quality}/100 · locked: {locked} · engine v{APP_VERSION}</div>',unsafe_allow_html=True)

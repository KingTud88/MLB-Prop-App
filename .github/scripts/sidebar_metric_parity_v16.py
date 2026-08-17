from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Target not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1) Secondary pages: use the same radio/nav language as Main Projection.
# ---------------------------------------------------------------------------
nav_path = ROOT / "navigation.py"
nav = nav_path.read_text(encoding="utf-8")
if "from engine.ui_command_center import render_sidebar_brand" not in nav:
    nav = nav.replace(
        "import streamlit as st\n",
        "import streamlit as st\n\nfrom engine.ui_command_center import render_sidebar_brand\n",
        1,
    )

marker = "    # SECONDARY_COMPACT_SIDEBAR_V2 · mirrors the Projection command-center rail.\n"
if marker not in nav:
    raise SystemExit("Secondary sidebar marker not found")
start = nav.index(marker)
new_tail = r'''    # PROJECTION_PARITY_SIDEBAR_V3 · exact Main Projection navigation language.
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
        [data-testid="stSidebar"] .cc-sidebar-brand{margin:.10rem 0 .80rem!important}
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
'''
nav = nav[:start] + new_tail
nav_path.write_text(nav, encoding="utf-8")


# ---------------------------------------------------------------------------
# 2) Main Projection: allow secondary pages to deep-link into internal tabs.
# ---------------------------------------------------------------------------
main_path = ROOT / "streamlit_app.py"
main = main_path.read_text(encoding="utf-8")
old_main_nav = '''with st.sidebar:\n    render_sidebar_brand()\n    nav=st.radio("Navigation",["Projection","Distribution","Form & Workload","Model Card","Bet Tracker","Projection History","Daily Projection Run","Top Plays"],label_visibility="collapsed")\n'''
new_main_nav = '''with st.sidebar:\n    render_sidebar_brand()\n    _nav_options=["Projection","Distribution","Form & Workload","Model Card","Bet Tracker","Projection History","Daily Projection Run","Top Plays"]\n    _nav_target=st.session_state.pop("projection_nav_target",None)\n    if _nav_target in _nav_options:\n        st.session_state["main_projection_navigation"]=_nav_target\n    if st.session_state.get("main_projection_navigation") not in _nav_options:\n        st.session_state["main_projection_navigation"]="Projection"\n    nav=st.radio("Navigation",_nav_options,label_visibility="collapsed",key="main_projection_navigation")\n'''
if old_main_nav not in main:
    raise SystemExit("Main Projection navigation anchor not found")
main = main.replace(old_main_nav, new_main_nav, 1)
main_path.write_text(main, encoding="utf-8")


# ---------------------------------------------------------------------------
# 3) Metric help v3: each box explains meaning, math, conclusion, limitation.
# ---------------------------------------------------------------------------
explain_path = ROOT / "engine" / "explainability_ui.py"
explain = explain_path.read_text(encoding="utf-8")
explain = explain.replace('METRIC_HELP_VERSION = "metric-help-v2"', 'METRIC_HELP_VERSION = "metric-help-v3"', 1)
explain = explain.replace('def metric_help(key: str) -> str:', 'def metric_help(key: str, *, current: str = "") -> str:', 1)

insert_anchor = '''        # Bet Tracker summary.\n'''
if insert_anchor not in explain:
    raise SystemExit("Metric help insertion anchor not found")
extra_specs = '''        # Projection History archive + actionable K scorecards.\n        "history_archived_slates": "What it is: the number of different slate dates preserved in the durable Projection Archive.\\n\\nHow it is calculated: count of unique non-null game_date values in the user-facing frozen archive.\\n\\nHow to read it: this tells you how many daily slates are represented, not how many pitchers or bets were recorded.",\n        "history_archived_pitchers": "What it is: the number of archived pitcher-game rows currently shown in the Projection Archive.\\n\\nHow it is calculated: count of rows in the durable user archive after archive-source filtering. The same pitcher can appear on multiple dates.\\n\\nHow to read it: this is evidence volume, not the number of unique MLB pitchers.",\n        "history_manual_lines": "What it is: sportsbook execution lines you manually attached to archived pitcher rows.\\n\\nHow it is calculated: count of non-null manual K lines + manual Outs lines + manual Hits Allowed lines. One pitcher row can contribute up to three attached lines.\\n\\nHow to read it: these lines are execution overlays only and never rewrite the frozen projection.",\n        "history_latest_slate": "What it is: the most recent game date represented in the Projection Archive.\\n\\nHow it is calculated: maximum non-null archived game_date.\\n\\nHow to read it: use this as a freshness check for the archive, not as proof that every game on that date is resolved.",\n        "history_ladder_calls": "What it is: resolved strikeout projections that produced a supported whole-K ladder target inside the 3+–12+ ladder.\\n\\nHow it is calculated: rows with both frozen projected Ks and final actual Ks, where floor(Projected K) maps to a supported milestone.\\n\\nHow to read it: this is the denominator for ladder win rate; it is not sportsbook bet count.",\n        "history_ladder_wins": "What it is: resolved ladder calls where final Ks reached or exceeded the model-supported whole-K target.\\n\\nHow it is calculated: count(actual Ks ≥ floor(Projected K)) for valid 3+–12+ targets.\\n\\nHow to read it: this grades model-supported milestones, not an OVER/UNDER sportsbook ticket unless that exact milestone was actually bet.",\n        "history_ladder_win_rate": "What it is: the share of resolved model-supported K targets that were reached.\\n\\nFormula: ladder wins ÷ resolved ladder calls.\\n\\nHow to read it: higher is better for this descriptive ladder test, but it is different from MAE, calibration, and sportsbook ROI.",\n        "history_crushers": "What it is: pitchers meeting the existing repeat-Crusher tracking rule in the descriptive history board.\\n\\nHow it is calculated: the current crusher_report rule requires enough resolved calls plus the existing win-rate and average-margin thresholds.\\n\\nHow to read it: Crushers identify repeated historical target clearing; they do not automatically become a live Top Play rule.",\n        "history_workload_snapshots": "What it is: frozen rows tagged with the workload-v1 workload model.\\n\\nHow it is calculated: count(workload_version == workload-v1) in the current evidence archive.\\n\\nHow to read it: this is the sample available for workload-v1 auditing.",\n        "history_pitch_mae": "What it is: average absolute error of expected pitch count.\\n\\nFormula: mean(|actual pitches − expected pitches|) where both values exist.\\n\\nHow to read it: lower is better; it measures typical pitch-count miss size, not directional bias.",\n        "history_bf_mae": "What it is: average absolute error of expected batters faced.\\n\\nFormula: mean(|actual BF − expected BF|) where both values exist.\\n\\nHow to read it: lower is better; it measures workload exposure accuracy rather than strikeout accuracy.",\n        "history_workload_outs_mae": "What it is: average absolute error of the workload layer's expected starter outs.\\n\\nFormula: mean(|actual outs − expected workload outs|) where both values exist.\\n\\nHow to read it: lower is better; this audits workload opportunity separately from the full outs projection model.",\n        "history_paired_outcomes": "What it is: total resolved before/after feature-upgrade pairs available for signal accountability.\\n\\nHow it is calculated: sum of Resolved Pairs across the paired-signal report.\\n\\nHow to read it: this is the evidence sample used to judge candidate signals; it is not a count of live bets.",\n        "history_helping_signals": "What it is: paired candidate signals currently meeting the report's HELPING gate.\\n\\nHow it is calculated: count(Status == HELPING) after the existing minimum-sample, MAE-improvement and improved-share requirements.\\n\\nHow to read it: HELPING is evidence for further research, not automatic production authority.",\n        "history_hurting_signals": "What it is: paired candidate signals currently meeting the symmetric HURTING guardrail.\\n\\nHow it is calculated: count(Status == HURTING) in the paired-signal report.\\n\\nHow to read it: these are signals the evidence says are making paired forecasts worse and should not be promoted.",\n        "history_learning_signals": "What it is: paired candidate signals that do not yet have enough evidence for a HELPING/HURTING conclusion.\\n\\nHow it is calculated: count(Status == LEARNING).\\n\\nHow to read it: LEARNING means wait for more leakage-safe resolved pairs; it is not a neutral vote for promotion.",\n\n'''
explain = explain.replace(insert_anchor, extra_specs + insert_anchor, 1)

old_return = '''    return specs.get(\n        key,\n        "What it is: a StrikeOut King scorecard metric.\\n\\nHow it is calculated: the value comes from the page's existing read-only data path.\\n\\nHow to read it: this help layer explains the displayed value and does not change model state.",\n    )\n'''
new_return = '''    text = specs.get(\n        key,\n        "What it is: a StrikeOut King scorecard metric.\\n\\nHow it is calculated: the value comes from the page's existing read-only data path.\\n\\nHow to read it: this help layer explains the displayed value and does not change model state.",\n    )\n    if current:\n        text += f"\\n\\nThis box right now: {current}"\n    text += (\n        "\\n\\nWhat not to conclude: this metric is one diagnostic/accountability signal. "\n        "By itself it does not rewrite a frozen projection, create a sportsbook bet, or guarantee future performance."\n    )\n    return text\n'''
if old_return not in explain:
    raise SystemExit("Metric help return block not found")
explain = explain.replace(old_return, new_return, 1)
explain_path.write_text(explain, encoding="utf-8")


# ---------------------------------------------------------------------------
# 4) Projection History: every visible scorecard box gets its own specific help.
# ---------------------------------------------------------------------------
history_path = ROOT / "pages" / "4_Projection_History.py"
history = history_path.read_text(encoding="utf-8")
replacements = {
    'a1.metric("Archived slates", archived_slates)': 'a1.metric("Archived slates", archived_slates, help=metric_help("history_archived_slates", current=f"{archived_slates} unique slate date(s)"))',
    'a2.metric("Archived pitchers", len(user_archive))': 'a2.metric("Archived pitchers", len(user_archive), help=metric_help("history_archived_pitchers", current=f"{len(user_archive)} archived pitcher-game row(s)"))',
    'a3.metric("Manual lines attached", manual_lines)': 'a3.metric("Manual lines attached", manual_lines, help=metric_help("history_manual_lines", current=f"{manual_lines} saved manual market line(s)"))',
    'a4.metric("Latest slate", latest_archive_date)': 'a4.metric("Latest slate", latest_archive_date, help=metric_help("history_latest_slate", current=f"Most recent archive date: {latest_archive_date}"))',
    'col1.metric("Automatic evidence rows", len(df), help=metric_help("history_evidence_rows"))': 'col1.metric("Automatic evidence rows", len(df), help=metric_help("history_evidence_rows", current=f"{len(df)} frozen evidence row(s) loaded"))',
    'col2.metric("Resolved games", resolved_any_count, help=metric_help("history_resolved_games"))': 'col2.metric("Resolved games", resolved_any_count, help=metric_help("history_resolved_games", current=f"{resolved_any_count}/{len(df)} evidence row(s) have at least one final MLB stat"))',
    'col3.metric("K range hits", k_hit_count, help=metric_help("history_k_range_hits"))': 'col3.metric("K range hits", k_hit_count, help=metric_help("history_k_range_hits", current=f"{k_hit_count}/{k_ready_count} eligible K intervals contained the final Ks"))',
    'col4.metric("K hit rate", f"{k_hit_rate:.1%}" if k_hit_rate is not None else "—", help=metric_help("history_k_hit_rate"))': 'col4.metric("K hit rate", f"{k_hit_rate:.1%}" if k_hit_rate is not None else "—", help=metric_help("history_k_hit_rate", current=(f"{k_hit_count}/{k_ready_count} = {k_hit_rate:.1%}" if k_hit_rate is not None else "No eligible resolved K intervals yet")))',
    'col5.metric("Hits range hits", h_hit_count, help=metric_help("history_hits_range_hits"))': 'col5.metric("Hits range hits", h_hit_count, help=metric_help("history_hits_range_hits", current=f"{h_hit_count}/{h_ready_count} eligible Hits intervals contained the final result"))',
    'col6.metric("Hits hit rate", f"{h_hit_rate:.1%}" if h_hit_rate is not None else "—", help=metric_help("history_hits_hit_rate"))': 'col6.metric("Hits hit rate", f"{h_hit_rate:.1%}" if h_hit_rate is not None else "—", help=metric_help("history_hits_hit_rate", current=(f"{h_hit_count}/{h_ready_count} = {h_hit_rate:.1%}" if h_hit_rate is not None else "No eligible resolved Hits intervals yet")))',
    'outs_metrics1.metric("Outs range hits", o_hit_count, help=metric_help("history_outs_range_hits"))': 'outs_metrics1.metric("Outs range hits", o_hit_count, help=metric_help("history_outs_range_hits", current=f"{o_hit_count}/{o_ready_count} eligible Outs intervals contained the final result"))',
    'outs_metrics2.metric("Outs hit rate", f"{o_hit_rate:.1%}" if o_hit_rate is not None else "—", help=metric_help("history_outs_hit_rate"))': 'outs_metrics2.metric("Outs hit rate", f"{o_hit_rate:.1%}" if o_hit_rate is not None else "—", help=metric_help("history_outs_hit_rate", current=(f"{o_hit_count}/{o_ready_count} = {o_hit_rate:.1%}" if o_hit_rate is not None else "No eligible resolved Outs intervals yet")))',
    'mae1.metric("Strikeout MAE", f"{k_mae_value:.2f} K" if k_mae_value is not None else "—", help=metric_help("history_k_mae"))': 'mae1.metric("Strikeout MAE", f"{k_mae_value:.2f} K" if k_mae_value is not None else "—", help=metric_help("history_k_mae", current=(f"{k_mae_value:.2f} K average absolute miss across {k_mae_n} valid pair(s)" if k_mae_value is not None else "No valid resolved K pairs yet")))',
    'mae2.metric("Hits Allowed MAE", f"{h_mae_value:.2f} H" if h_mae_value is not None else "—", help=metric_help("history_hits_mae"))': 'mae2.metric("Hits Allowed MAE", f"{h_mae_value:.2f} H" if h_mae_value is not None else "—", help=metric_help("history_hits_mae", current=(f"{h_mae_value:.2f} H average absolute miss across {h_mae_n} valid pair(s)" if h_mae_value is not None else "No valid resolved Hits pairs yet")))',
    'mae3.metric("Total Outs MAE", f"{o_mae_value:.2f} outs" if o_mae_value is not None else "—", help=metric_help("history_outs_mae"))': 'mae3.metric("Total Outs MAE", f"{o_mae_value:.2f} outs" if o_mae_value is not None else "—", help=metric_help("history_outs_mae", current=(f"{o_mae_value:.2f} outs average absolute miss across {o_mae_n} valid pair(s)" if o_mae_value is not None else "No valid resolved Outs pairs yet")))',
    'kw1.metric("Resolved ladder calls", len(_bettable))': 'kw1.metric("Resolved ladder calls", len(_bettable), help=metric_help("history_ladder_calls", current=f"{len(_bettable)} valid resolved whole-K target call(s)"))',
    'kw2.metric("Ladder wins", _wins)': 'kw2.metric("Ladder wins", _wins, help=metric_help("history_ladder_wins", current=f"{_wins}/{len(_bettable)} resolved ladder call(s) reached target"))',
    'kw3.metric("Ladder win rate", f"{_win_rate:.1%}")': 'kw3.metric("Ladder win rate", f"{_win_rate:.1%}", help=metric_help("history_ladder_win_rate", current=f"{_wins}/{len(_bettable)} = {_win_rate:.1%}"))',
    'kw4.metric("Consistent crushers", _crusher_count)': 'kw4.metric("Consistent crushers", _crusher_count, help=metric_help("history_crushers", current=f"{_crusher_count} pitcher(s) currently meet the existing Crusher tracking rule"))',
    'wa1.metric("workload-v1 snapshots", len(workload_rows))': 'wa1.metric("workload-v1 snapshots", len(workload_rows), help=metric_help("history_workload_snapshots", current=f"{len(workload_rows)} workload-v1 snapshot row(s)"))',
    'wa2.metric("Pitch-count MAE", "—" if not pitch_ready.any() else f"{float((actual_pitches[pitch_ready]-expected_pitches[pitch_ready]).abs().mean()):.1f} pitches")': 'wa2.metric("Pitch-count MAE", "—" if not pitch_ready.any() else f"{float((actual_pitches[pitch_ready]-expected_pitches[pitch_ready]).abs().mean()):.1f} pitches", help=metric_help("history_pitch_mae", current=f"{int(pitch_ready.sum())} valid expected/actual pitch pair(s)"))',
    'wa3.metric("BF MAE", "—" if not bf_ready.any() else f"{float((actual_bf[bf_ready]-expected_bf[bf_ready]).abs().mean()):.2f} BF")': 'wa3.metric("BF MAE", "—" if not bf_ready.any() else f"{float((actual_bf[bf_ready]-expected_bf[bf_ready]).abs().mean()):.2f} BF", help=metric_help("history_bf_mae", current=f"{int(bf_ready.sum())} valid expected/actual BF pair(s)"))',
    'wa4.metric("Workload-outs MAE", "—" if not outs_ready_w.any() else f"{float((actual_outs_w[outs_ready_w]-expected_outs[outs_ready_w]).abs().mean()):.2f} outs")': 'wa4.metric("Workload-outs MAE", "—" if not outs_ready_w.any() else f"{float((actual_outs_w[outs_ready_w]-expected_outs[outs_ready_w]).abs().mean()):.2f} outs", help=metric_help("history_workload_outs_mae", current=f"{int(outs_ready_w.sum())} valid expected/actual workload-outs pair(s)"))',
    's1.metric("Paired market outcomes", paired_outcomes)': 's1.metric("Paired market outcomes", paired_outcomes, help=metric_help("history_paired_outcomes", current=f"{paired_outcomes} resolved before/after pair(s) across candidate signals"))',
    's2.metric("Helping signals", helping)': 's2.metric("Helping signals", helping, help=metric_help("history_helping_signals", current=f"{helping} paired signal(s) currently meet HELPING"))',
    's3.metric("Hurting signals", hurting)': 's3.metric("Hurting signals", hurting, help=metric_help("history_hurting_signals", current=f"{hurting} paired signal(s) currently meet HURTING"))',
    's4.metric("Still learning", learning)': 's4.metric("Still learning", learning, help=metric_help("history_learning_signals", current=f"{learning} paired signal(s) still need more evidence"))',
}
for old, new in replacements.items():
    if old not in history:
        raise SystemExit(f"History metric anchor missing: {old}")
    history = history.replace(old, new, 1)
history_path.write_text(history, encoding="utf-8")


# ---------------------------------------------------------------------------
# 5) Update/add contracts for exact sidebar parity + deeper metric help.
# ---------------------------------------------------------------------------
test_path = ROOT / "tests" / "test_sidebar_metric_explainability_v2.py"
test = test_path.read_text(encoding="utf-8")
test = test.replace('assert METRIC_HELP_VERSION == "metric-help-v2"', 'assert METRIC_HELP_VERSION == "metric-help-v3"', 1)
old_sidebar_test = '''def test_secondary_sidebar_uses_compact_projection_language():\n    source = (ROOT / "navigation.py").read_text(encoding="utf-8")\n    assert "SECONDARY_COMPACT_SIDEBAR_V2" in source\n    assert "sk-nav-compact-crown" in source\n    assert "sk-nav-compact-script" in source\n    assert "sk-nav-compact-king" in source\n    rendered = source[source.index("with st.sidebar:"):]\n    assert "sk-nav-mascot" not in rendered\n    assert "CLE-themed MLB starter projection engine" in rendered\n\n\n'''
new_sidebar_test = '''def test_secondary_sidebar_uses_exact_projection_navigation_language():\n    source = (ROOT / "navigation.py").read_text(encoding="utf-8")\n    assert "PROJECTION_PARITY_SIDEBAR_V3" in source\n    assert "render_sidebar_brand()" in source\n    assert 'st.radio(' in source\n    assert '"Projection", "Distribution", "Form & Workload", "Model Card"' in source\n    assert '"Bet Tracker", "Projection History", "Daily Projection Run", "Top Plays"' in source\n    assert 'label:nth-child(8)::before' in source\n    rendered = source[source.index("# PROJECTION_PARITY_SIDEBAR_V3"):]\n    assert "st.page_link" not in rendered\n    assert "👑" not in rendered\n    assert "▣" not in rendered\n\n\n'''
if old_sidebar_test not in test:
    raise SystemExit("Old sidebar contract block not found")
test = test.replace(old_sidebar_test, new_sidebar_test, 1)

append = '''\n\ndef test_main_projection_accepts_secondary_internal_tab_target():\n    source = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")\n    assert 'st.session_state.pop("projection_nav_target",None)' in source\n    assert 'key="main_projection_navigation"' in source\n\n\ndef test_history_archive_and_actionable_scorecards_have_individual_help():\n    source = (ROOT / "pages" / "4_Projection_History.py").read_text(encoding="utf-8")\n    for key in (\n        "history_archived_slates", "history_archived_pitchers", "history_manual_lines", "history_latest_slate",\n        "history_ladder_calls", "history_ladder_wins", "history_ladder_win_rate", "history_crushers",\n        "history_workload_snapshots", "history_pitch_mae", "history_bf_mae", "history_workload_outs_mae",\n        "history_paired_outcomes", "history_helping_signals", "history_hurting_signals", "history_learning_signals",\n    ):\n        assert f'metric_help("{key}"' in source\n\n\ndef test_metric_help_v3_includes_current_value_and_limitation():\n    text = metric_help("history_k_hit_rate", current="180/209 = 86.1%")\n    assert "This box right now:" in text\n    assert "180/209 = 86.1%" in text\n    assert "What not to conclude:" in text\n'''
if "test_metric_help_v3_includes_current_value_and_limitation" not in test:
    test += append

test_path.write_text(test, encoding="utf-8")

print("sidebar_metric_parity_v16 applied")

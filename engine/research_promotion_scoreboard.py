from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from training.research_promotion_command_center import build_promotion_command_center

SCOREBOARD_VERSION = "research-promotion-scoreboard-v2-all-lanes"

COLUMNS = [
    "Lane",
    "Status",
    "Sample",
    "Gate Progress",
    "Signal",
    "Recommended Action",
    "Production Authority",
    "Reason",
    "Source",
    "Scoreboard Version",
]


def _text(value: object, default: str = "—") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    return text if text else default


def _int_or_none(value: object) -> int | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else int(parsed)


def _progress_piece(label: str, current: object, required: object) -> str:
    current_i = _int_or_none(current)
    required_i = _int_or_none(required)
    if current_i is None and required_i is None:
        return ""
    if required_i is None:
        return f"{label} {current_i if current_i is not None else '—'}"
    return f"{label} {current_i if current_i is not None else '—'}/{required_i}"


def _sample(row: pd.Series) -> str:
    pieces: list[str] = []
    starts = _int_or_none(row.get("Current_Starts"))
    days = _int_or_none(row.get("Current_Days"))
    breadth = _int_or_none(row.get("Current_Breadth"))
    breadth_label = _text(row.get("Breadth_Label"), "breadth").lower()
    if starts is not None:
        pieces.append(f"{starts} starts/calls")
    if days is not None:
        pieces.append(f"{days} days")
    if breadth is not None:
        pieces.append(f"{breadth} {breadth_label}")
    return " · ".join(pieces) if pieces else "No mature evidence loaded"


def _gate_progress(row: pd.Series) -> str:
    pieces = [
        _progress_piece("starts", row.get("Current_Starts"), row.get("Required_Starts")),
        _progress_piece("days", row.get("Current_Days"), row.get("Required_Days")),
    ]
    breadth_label = _text(row.get("Breadth_Label"), "breadth").lower()
    pieces.append(_progress_piece(breadth_label, row.get("Current_Breadth"), row.get("Required_Breadth")))
    secondary = _text(row.get("Secondary_Progress"), "")
    pieces = [piece for piece in pieces if piece]
    if secondary:
        pieces.append(secondary)
    return " · ".join(pieces) if pieces else "Source-owned gate; see reason"


def build_research_promotion_scoreboard(root: Path) -> pd.DataFrame:
    """Display every registered report-only research lane without re-grading it."""
    data = Path(root) / "data"
    command_center = build_promotion_command_center(data)
    rows: list[dict[str, object]] = []
    for _, source in command_center.iterrows():
        rows.append({
            "Lane": _text(source.get("Lane"), "UNKNOWN LANE"),
            "Status": _text(source.get("Status"), "UNKNOWN"),
            "Sample": _sample(source),
            "Gate Progress": _gate_progress(source),
            "Signal": _text(source.get("Evidence_Direction")),
            "Recommended Action": _text(source.get("Recommended_Action"), "KEEP LEARNING"),
            "Production Authority": _text(source.get("Production_Authority"), "NONE"),
            "Reason": _text(source.get("Source_Reason"), ""),
            "Source": _text(source.get("Source_Path"), ""),
            "Scoreboard Version": SCOREBOARD_VERSION,
        })
    return pd.DataFrame(rows, columns=COLUMNS).reset_index(drop=True)


def _status_class(status: str) -> str:
    key = str(status).strip().upper()
    if key in {
        "PASS", "SUPPORTED", "STRONG EVIDENCE", "PROMOTE", "HELPING",
        "LEAN_SUPPORTED", "LEAN_CONSISTENT", "READY_FOR_MANUAL_RESEARCH_REVIEW",
    }:
        return "research-good"
    if key in {"FAIL", "HURTING", "HURTING_BOTH", "REJECT", "CAUTION"}:
        return "research-bad"
    if key in {"HOLD", "LEARNING", "INCONCLUSIVE", "MIXED", "SOURCE_MISSING"}:
        return "research-watch"
    return "research-neutral"


def render_research_promotion_scoreboard(root: Path) -> None:
    board = build_research_promotion_scoreboard(root)
    st.markdown(
        """
        <style>
        /* RESEARCH_PROMOTION_SCOREBOARD_V2_ALL_LANES · presentation/reporting only */
        .research-board-head{margin:1.1rem 0 .25rem;padding:.88rem 1rem;border:1px solid rgba(73,111,151,.62);border-left:4px solid #ff3655;border-radius:14px;background:linear-gradient(110deg,rgba(10,34,59,.95),rgba(5,20,37,.97));}
        .research-board-kicker{color:#ff6a7d;font:900 .66rem/1.2 system-ui;letter-spacing:.11em;text-transform:uppercase}
        .research-board-title{margin:.16rem 0;color:#f5f1e9;font:900 1.28rem/1.15 system-ui}
        .research-board-copy{color:#aebfd2;font:650 .80rem/1.42 system-ui}
        .research-card{min-height:198px;margin:.24rem 0;padding:.64rem .76rem .58rem;border:1px solid rgba(77,108,137,.68);border-radius:14px;background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98));box-shadow:0 10px 24px rgba(0,0,0,.18)}
        .research-card-top{display:flex;gap:.6rem;align-items:center;justify-content:space-between;margin-bottom:.10rem}
        .research-card-lane{color:#f3f7fa;font:900 .90rem/1.2 system-ui;text-transform:uppercase;letter-spacing:.035em}
        .research-pill{padding:.20rem .46rem;border-radius:999px;font:900 .62rem/1.2 system-ui;letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}
        .research-good{color:#86efac;border:1px solid rgba(34,197,94,.55);background:rgba(34,197,94,.13)}
        .research-bad{color:#ff8a9a;border:1px solid rgba(255,54,85,.58);background:rgba(227,25,55,.14)}
        .research-watch{color:#ffd166;border:1px solid rgba(250,204,21,.48);background:rgba(250,204,21,.10)}
        .research-neutral{color:#9fb3c6;border:1px solid rgba(159,179,198,.38);background:rgba(159,179,198,.08)}
        .research-label{margin-top:.38rem;color:#7fa4c2;font:900 .57rem/1.15 system-ui;letter-spacing:.09em;text-transform:uppercase}
        .research-value{margin-top:.06rem;color:#dfe9f0;font:720 .73rem/1.30 system-ui}
        .research-label-sample{color:#6f93b0}
        .research-value-sample{color:#b8c8d5;font-weight:680}
        .research-label-gate{margin-top:.40rem;color:#91c6eb}
        .research-value-gate{margin-top:.09rem;padding:.26rem .36rem;border-left:2px solid #38bdf8;border-radius:7px;background:rgba(56,189,248,.055);color:#f4f8fb;font:900 .78rem/1.30 system-ui}
        .research-label-action{color:#7899b4}
        .research-value-action{color:#c8d5df;font-weight:760}
        .research-authority-strip{display:flex;align-items:center;justify-content:space-between;gap:.6rem;margin-top:.48rem;padding:.30rem .42rem;border-top:1px solid rgba(255,54,85,.30);border-radius:7px;background:rgba(105,14,33,.10)}
        .research-authority-label{color:#7595ae;font:900 .56rem/1.15 system-ui;letter-spacing:.085em;text-transform:uppercase}
        .research-authority{color:#ff8a9a;font:900 .68rem/1.15 system-ui;letter-spacing:.035em;text-transform:uppercase}
        @media(max-width:700px){.research-card{min-height:0}.research-card-top{align-items:flex-start;flex-direction:column}.research-authority-strip{align-items:flex-start}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="research-board-head">'
        '<div class="research-board-kicker">Research command center · report only · all lanes</div>'
        '<div class="research-board-title">Research Promotion Command Center</div>'
        '<div class="research-board-copy">Every registered research lane is shown. Native verdicts remain source-owned; this board never re-grades, auto-promotes, or activates a model feature.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    statuses = board["Status"].astype(str).str.upper()
    authority = board["Production Authority"].astype(str).str.upper()
    ready = statuses.eq("READY_FOR_MANUAL_RESEARCH_REVIEW")
    a, b, c, d = st.columns(4)
    a.metric("Research lanes", len(board), help="All registered report-only research lanes; there is no fixed card ceiling.")
    b.metric("Still learning", int(statuses.isin({"LEARNING", "INCONCLUSIVE", "MIXED"}).sum()), help="Lanes still accumulating or resolving evidence.")
    c.metric("Manual review ready", int(ready.sum()), help="Maturity gate reached; still requires explicit manual review before any production proposal.")
    d.metric("Production authority", int(authority.ne("NONE").sum()), help="Research-only lanes should remain zero until an explicitly approved production change is implemented.")

    for start in range(0, len(board), 2):
        cols = st.columns(2)
        for col, (_, row) in zip(cols, board.iloc[start:start + 2].iterrows()):
            status = _text(row["Status"], "UNKNOWN")
            with col:
                st.markdown(
                    '<div class="research-card">'
                    f'<div class="research-card-top"><div class="research-card-lane">{escape(_text(row["Lane"]))}</div>'
                    f'<div class="research-pill {_status_class(status)}">{escape(status)}</div></div>'
                    '<div class="research-label research-label-sample">Sample</div>'
                    f'<div class="research-value research-value-sample">{escape(_text(row["Sample"]))}</div>'
                    '<div class="research-label research-label-gate">Gate progress</div>'
                    f'<div class="research-value research-value-gate">{escape(_text(row["Gate Progress"]))}</div>'
                    '<div class="research-label">Current signal</div>'
                    f'<div class="research-value">{escape(_text(row["Signal"]))}</div>'
                    '<div class="research-label research-label-action">Action</div>'
                    f'<div class="research-value research-value-action">{escape(_text(row["Recommended Action"]))}</div>'
                    '<div class="research-authority-strip">'
                    '<span class="research-authority-label">Production authority</span>'
                    f'<span class="research-authority">{escape(_text(row["Production Authority"]))}</span>'
                    '</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

    with st.expander("ⓘ How to read the Research Promotion Command Center", expanded=False):
        st.markdown(
            "**Status is source-owned.** Native research verdicts are displayed as written by each validator. The scoreboard does not recalculate them."
        )
        st.markdown(
            "**Gate Progress shows the evidence bottleneck.** Starts alone are not enough; time diversity, pitcher/opponent/catcher/umpire breadth, probability coverage, seasons, or other source-owned requirements can keep a lane in learning."
        )
        st.markdown(
            "**Current Signal is descriptive evidence, not activation.** Positive movement can justify a later frozen challenger, but same-sample research does not authorize a live adjustment."
        )
        st.markdown(
            "**Production Authority is the hard boundary.** NONE means the lane cannot change the live baseball projection, probabilities, Top Plays ranking, recommendation thresholds, or sportsbook execution."
        )
        detail = board[["Lane", "Status", "Reason", "Source", "Production Authority"]].copy()
        st.dataframe(detail, hide_index=True, width="stretch")

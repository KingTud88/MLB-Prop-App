from __future__ import annotations

from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from engine.decision_learning import MIN_DECISION_OBSERVATIONS
from training.calibration_shadow_gate import MIN_OOS_STARTS as CALIBRATION_MIN_OOS
from training.catcher_context_validation import (
    MIN_EVAL_CATCHERS as CATCHER_MIN_CATCHERS,
    MIN_EVAL_DAYS as CATCHER_MIN_DAYS,
    MIN_EVAL_STARTS as CATCHER_MIN_STARTS,
)
from training.lineup_k_walkforward import (
    MIN_EVAL_DAYS as LINEUP_MIN_DAYS,
    MIN_EVAL_OPPONENTS as LINEUP_MIN_OPPONENTS,
    MIN_EVAL_STARTS as LINEUP_MIN_STARTS,
)
from training.live_role_shadow_gate import MIN_RESOLVED_STARTS as ROLE_MIN_STARTS
from training.ml_shadow_report import MIN_OOS_RESOLVED as ML_MIN_OOS
from training.umpire_k_live_validation import (
    MIN_EVAL_DAYS as UMPIRE_MIN_DAYS,
    MIN_EVAL_STARTS as UMPIRE_MIN_STARTS,
    MIN_EVAL_UMPIRES as UMPIRE_MIN_UMPIRES,
)
from training.workload_promotion_report import REQUIRED_SEASONS as WORKLOAD_REQUIRED_SEASONS

SCOREBOARD_VERSION = "research-promotion-scoreboard-v1"
LANE_ORDER = (
    "Confirmed Lineup",
    "Umpire Context",
    "Catcher Context",
    "Starter Role",
    "ML Challenger",
    "Calibration Shadow",
    "Workload Candidates",
    "Top Plays Accountability",
)

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


def _read(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _int(value: object) -> int:
    number = _num(value)
    return 0 if number is None else int(number)


def _pct(value: object, *, signed: bool = False) -> str:
    number = _num(value)
    if number is None:
        return "—"
    return f"{number:+.1%}" if signed else f"{number:.1%}"


def _f(value: object, digits: int = 3, *, signed: bool = False) -> str:
    number = _num(value)
    if number is None:
        return "—"
    return f"{number:+.{digits}f}" if signed else f"{number:.{digits}f}"


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


def _row(
    lane: str,
    *,
    status: str,
    sample: str,
    progress: str,
    signal: str,
    action: str,
    authority: str = "NONE",
    reason: str = "",
    source: str,
) -> dict[str, object]:
    return {
        "Lane": lane,
        "Status": status,
        "Sample": sample,
        "Gate Progress": progress,
        "Signal": signal,
        "Recommended Action": action,
        "Production Authority": authority,
        "Reason": reason,
        "Source": source,
        "Scoreboard Version": SCOREBOARD_VERSION,
    }


def _missing(lane: str, source: str) -> dict[str, object]:
    return _row(
        lane,
        status="NO DATA",
        sample="No report loaded",
        progress="Waiting for report",
        signal="—",
        action="WAIT FOR EVIDENCE",
        authority="NONE",
        reason=f"{source} is missing or unreadable.",
        source=source,
    )


def _lineup(data: Path) -> dict[str, object]:
    source = "lineup_k_walkforward_gate.csv"
    frame = _read(data / source)
    if frame.empty:
        return _missing("Confirmed Lineup", source)
    row = frame.iloc[0]
    oos = _int(row.get("OOS_Paired_Starts"))
    days = _int(row.get("Observed_Days"))
    opponents = _int(row.get("Distinct_Opponents"))
    return _row(
        "Confirmed Lineup",
        status=_text(row.get("Evidence_Status"), "UNKNOWN"),
        sample=f"{oos} OOS pairs · {days} days · {opponents} opponents",
        progress=f"starts {oos}/{LINEUP_MIN_STARTS} · days {days}/{LINEUP_MIN_DAYS} · opponents {opponents}/{LINEUP_MIN_OPPONENTS}",
        signal=(
            f"MAE {_pct(row.get('Relative_MAE_Improvement'), signed=True)} · "
            f"wins {_pct(row.get('Confirmed_Win_Share'))} · "
            f"bias {_f(row.get('Preconfirm_Bias'), signed=True)}→{_f(row.get('Confirmed_Bias'), signed=True)}"
        ),
        action=_text(row.get("Recommended_Action"), "KEEP_LEARNING"),
        authority=_text(row.get("Production_Authority"), "NONE"),
        reason=_text(row.get("Reason"), ""),
        source=source,
    )


def _umpire(data: Path) -> dict[str, object]:
    source = "umpire_k_live_validation_gate.csv"
    frame = _read(data / source)
    if frame.empty:
        return _missing("Umpire Context", source)
    row = frame.iloc[0]
    oos = _int(row.get("OOS_Eligible_Starts"))
    days = _int(row.get("Observed_Days"))
    umpires = _int(row.get("Distinct_Umpires"))
    return _row(
        "Umpire Context",
        status=_text(row.get("Evidence_Status"), "UNKNOWN"),
        sample=f"{oos} live OOS starts · {days} days · {umpires} umpires",
        progress=f"starts {oos}/{UMPIRE_MIN_STARTS} · days {days}/{UMPIRE_MIN_DAYS} · umpires {umpires}/{UMPIRE_MIN_UMPIRES}",
        signal=(
            f"MAE {_pct(row.get('Relative_MAE_Improvement'), signed=True)} · "
            f"wins {_pct(row.get('Candidate_Win_Share'))} · "
            f"factor Δ {_pct(row.get('Mean_Absolute_Factor_Delta'))}"
        ),
        action=_text(row.get("Recommended_Action"), "KEEP_LEARNING"),
        authority=_text(row.get("Production_Authority"), "NONE"),
        reason=_text(row.get("Reason"), ""),
        source=source,
    )


def _catcher(data: Path) -> dict[str, object]:
    source = "catcher_context_validation_gate.csv"
    frame = _read(data / source)
    if frame.empty:
        return _missing("Catcher Context", source)
    row = frame.iloc[0]
    auditable = _int(row.get("Auditable_Starts"))
    days = _int(row.get("Observed_Days"))
    catchers = _int(row.get("Distinct_Catchers"))
    authentic = _int(row.get("Authentic_Pregame_Resolved"))
    signal = "Waiting for auditable catcher histories"
    if auditable:
        signal = (
            f"MAE {_pct(row.get('Relative_MAE_Improvement'), signed=True)} · "
            f"wins {_pct(row.get('Candidate_Win_Share'))} · "
            f"alignment {_pct(row.get('Signal_Alignment'))}"
        )
    return _row(
        "Catcher Context",
        status=_text(row.get("Evidence_Status"), "UNKNOWN"),
        sample=f"{authentic} authentic pregame resolved · {auditable} auditable",
        progress=f"starts {auditable}/{CATCHER_MIN_STARTS} · days {days}/{CATCHER_MIN_DAYS} · catchers {catchers}/{CATCHER_MIN_CATCHERS}",
        signal=signal,
        action="KEEP_LEARNING" if not bool(row.get("Recommended_Activation")) else "MANUAL REVIEW",
        authority=_text(row.get("Production_Authority"), "NONE"),
        reason=_text(row.get("Reason"), ""),
        source=source,
    )


def _starter_role(data: Path) -> dict[str, object]:
    source = "live_role_shadow_gate.csv"
    frame = _read(data / source)
    if frame.empty:
        return _missing("Starter Role", source)
    statuses = frame.get("Live_Gate_Status", pd.Series(dtype=object)).fillna("UNKNOWN").astype(str).str.strip()
    status_set = set(statuses)
    if "FAIL" in status_set:
        status = "FAIL"
    elif "LEARNING" in status_set:
        status = "LEARNING"
    elif status_set == {"PASS"}:
        status = "PASS"
    else:
        status = "MIXED"
    starts = pd.to_numeric(frame.get("Resolved_Starts"), errors="coerce").fillna(0).astype(int)
    min_starts = int(starts.min()) if len(starts) else 0
    max_starts = int(starts.max()) if len(starts) else 0
    passed = int(statuses.eq("PASS").sum())
    return _row(
        "Starter Role",
        status=status,
        sample=f"{len(frame)} required role/metric cells · {min_starts}–{max_starts} resolved per cell",
        progress=f"slowest cell {min_starts}/{ROLE_MIN_STARTS} · {passed}/{len(frame)} cells PASS",
        signal=f"{int(statuses.eq('LEARNING').sum())} LEARNING · {int(statuses.eq('FAIL').sum())} FAIL · {passed} PASS",
        action="KEEP LEARNING" if status == "LEARNING" else "MANUAL REVIEW" if status in {"FAIL", "MIXED"} else "PROMOTION REVIEW",
        authority="NONE",
        reason="All required role × workload-metric cells must clear their own live gate; the scoreboard does not combine them into a new model rule.",
        source=source,
    )


def _ml(data: Path) -> dict[str, object]:
    source = "ml_shadow_summary.csv"
    frame = _read(data / source)
    if frame.empty:
        return _missing("ML Challenger", source)
    primary = frame.loc[frame.get("Challenger", pd.Series(dtype=object)).astype(str).eq("ML_SHADOW")]
    if primary.empty:
        return _missing("ML Challenger", source)
    row = primary.iloc[0]
    thirds = frame.loc[frame.get("Challenger", pd.Series(dtype=object)).astype(str).eq("SIM_MATH_ML_EQUAL_THIRDS")]
    thirds_n = _int(thirds.iloc[0].get("OOS_Starts")) if not thirds.empty else 0
    oos = _int(row.get("OOS_Starts"))
    return _row(
        "ML Challenger",
        status=_text(row.get("Status"), "UNKNOWN"),
        sample=f"{oos} ML OOS starts · three-path blend {thirds_n} OOS",
        progress=f"ML evaluation sample {oos}/{ML_MIN_OOS} · authentic SIM+MATH+ML history {thirds_n} OOS",
        signal=(
            f"MAE {_pct(row.get('Relative_MAE_Improvement'), signed=True)} · "
            f"wins {_pct(row.get('Candidate_Win_Share'))} · "
            f"candidate bias {_f(row.get('Candidate_Bias'), signed=True)}"
        ),
        action="KEEP SHADOW / DO NOT PROMOTE" if _text(row.get("Status")) == "HURTING" else "KEEP LEARNING",
        authority="NONE",
        reason=_text(row.get("Reason"), ""),
        source=source,
    )


def _calibration(data: Path) -> dict[str, object]:
    source = "calibration_shadow_gate.csv"
    frame = _read(data / source)
    if frame.empty:
        return _missing("Calibration Shadow", source)
    statuses = frame.get("Promotion_Gate_Status", pd.Series(dtype=object)).fillna("UNKNOWN").astype(str).str.strip()
    if statuses.eq("FAIL").any():
        status = "FAIL"
    elif statuses.eq("LEARNING").any():
        status = "LEARNING"
    elif len(statuses) and statuses.eq("PASS").all():
        status = "PASS"
    else:
        status = "MIXED"
    starts = pd.to_numeric(frame.get("OOS_Starts"), errors="coerce").fillna(0).astype(int)
    min_starts = int(starts.min()) if len(starts) else 0
    passed = int(statuses.eq("PASS").sum())
    rel = pd.to_numeric(frame.get("Relative_Brier_Improvement"), errors="coerce")
    best = float(rel.max()) if rel.notna().any() else np.nan
    return _row(
        "Calibration Shadow",
        status=status,
        sample=f"{len(frame)} K milestones · {min_starts} OOS starts each",
        progress=f"sample {min_starts}/{CALIBRATION_MIN_OOS} · {passed}/{len(frame)} milestones PASS",
        signal=f"best Brier improvement {_pct(best, signed=True)} · {int(statuses.eq('FAIL').sum())} FAIL",
        action="KEEP BASELINE CALIBRATION" if status == "FAIL" else "KEEP LEARNING" if status == "LEARNING" else "PROMOTION REVIEW",
        authority="NONE",
        reason="Each 3+–10+ milestone keeps its own Brier, calibration-gap, and win-share gate; no aggregate score overrides those cells.",
        source=source,
    )


def _workload(data: Path) -> dict[str, object]:
    source = "workload_promotion_decisions.csv"
    frame = _read(data / source)
    if frame.empty:
        return _missing("Workload Candidates", source)
    decisions = frame.get("Decision", pd.Series(dtype=object)).fillna("UNKNOWN").astype(str).str.strip()
    unique = set(decisions)
    status = next(iter(unique)) if len(unique) == 1 else "MIXED"
    passing = pd.to_numeric(frame.get("Passing_Seasons"), errors="coerce").fillna(0).astype(int)
    required = pd.to_numeric(frame.get("Required_Seasons"), errors="coerce").fillna(len(WORKLOAD_REQUIRED_SEASONS)).astype(int)
    signals: list[str] = []
    for _, row in frame.iterrows():
        signals.append(f"{_text(row.get('Metric'))} {_pct(row.get('Pooled_Relative_MAE'), signed=True)}")
    return _row(
        "Workload Candidates",
        status=status,
        sample=f"{len(frame)} workload metrics · {len(WORKLOAD_REQUIRED_SEASONS)} historical seasons",
        progress=" · ".join(
            f"{_text(row.get('Metric'))} {_int(row.get('Passing_Seasons'))}/{_int(row.get('Required_Seasons'))} seasons PASS"
            for _, row in frame.iterrows()
        ),
        signal=" · ".join(signals),
        action="HOLD / NO PRODUCTION CHANGE" if status == "HOLD" else "MANUAL REVIEW",
        authority="NONE" if frame.get("Production_Authority") is None else _text(frame.iloc[0].get("Production_Authority"), "NONE"),
        reason="; ".join(_text(value, "") for value in frame.get("Reasons", pd.Series(dtype=object)).tolist() if _text(value, "")),
        source=source,
    )


def _top_plays(data: Path) -> dict[str, object]:
    source = "top_plays_accountability_findings.csv"
    frame = _read(data / source)
    if frame.empty:
        return _missing("Top Plays Accountability", source)
    overall = frame.loc[frame.get("Finding", pd.Series(dtype=object)).astype(str).eq("OVERALL ACCOUNTABILITY STATE")]
    if overall.empty:
        return _missing("Top Plays Accountability", source)
    row = overall.iloc[0]
    evidence = _text(row.get("Evidence"), "")
    settled = 0
    try:
        settled = int(evidence.split(" settled", 1)[0].strip())
    except Exception:
        settled = 0
    conclusion = _text(row.get("Conclusion"), "")
    signal = conclusion.split("Current sample", 1)[0].strip().rstrip(".") if conclusion else "—"
    return _row(
        "Top Plays Accountability",
        status=_text(row.get("Status"), "UNKNOWN"),
        sample=evidence or f"{settled} settled real-line Top Plays",
        progress=f"settled real-line Top Plays {settled}/{int(MIN_DECISION_OBSERVATIONS)} minimum per trusted segment",
        signal=signal,
        action="KEEP LEARNING / DO NOT CHANGE RANKING",
        authority=_text(row.get("Production Authority"), "NONE"),
        reason=conclusion,
        source=source,
    )


def build_research_promotion_scoreboard(root: Path) -> pd.DataFrame:
    """Normalize existing research reports without re-grading their native verdicts."""
    data = Path(root) / "data"
    rows = [
        _lineup(data),
        _umpire(data),
        _catcher(data),
        _starter_role(data),
        _ml(data),
        _calibration(data),
        _workload(data),
        _top_plays(data),
    ]
    frame = pd.DataFrame(rows, columns=COLUMNS)
    order = {name: index for index, name in enumerate(LANE_ORDER)}
    frame["_order"] = frame["Lane"].map(order).fillna(999)
    return frame.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)


def _status_class(status: str) -> str:
    key = str(status).strip().upper()
    if key in {"PASS", "SUPPORTED", "STRONG EVIDENCE", "PROMOTE", "HELPING"}:
        return "research-good"
    if key in {"FAIL", "HURTING", "REJECT", "CAUTION"}:
        return "research-bad"
    if key in {"HOLD", "LEARNING"}:
        return "research-watch"
    return "research-neutral"


def render_research_promotion_scoreboard(root: Path) -> None:
    board = build_research_promotion_scoreboard(root)
    st.markdown(
        """
        <style>
        /* RESEARCH_PROMOTION_SCOREBOARD_V1 · presentation/reporting only */
        .research-board-head{margin:1.1rem 0 .25rem;padding:.88rem 1rem;border:1px solid rgba(73,111,151,.62);border-left:4px solid #ff3655;border-radius:14px;background:linear-gradient(110deg,rgba(10,34,59,.95),rgba(5,20,37,.97));}
        .research-board-kicker{color:#ff6a7d;font:900 .66rem/1.2 system-ui;letter-spacing:.11em;text-transform:uppercase}
        .research-board-title{margin:.16rem 0;color:#f5f1e9;font:900 1.28rem/1.15 system-ui}
        .research-board-copy{color:#aebfd2;font:650 .80rem/1.42 system-ui}
        .research-card{min-height:245px;margin:.32rem 0;padding:.78rem .84rem;border:1px solid rgba(77,108,137,.68);border-radius:14px;background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98));box-shadow:0 10px 24px rgba(0,0,0,.18)}
        .research-card-top{display:flex;gap:.6rem;align-items:center;justify-content:space-between}
        .research-card-lane{color:#f3f7fa;font:900 .90rem/1.2 system-ui;text-transform:uppercase;letter-spacing:.035em}
        .research-pill{padding:.20rem .46rem;border-radius:999px;font:900 .62rem/1.2 system-ui;letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}
        .research-good{color:#86efac;border:1px solid rgba(34,197,94,.55);background:rgba(34,197,94,.13)}
        .research-bad{color:#ff8a9a;border:1px solid rgba(255,54,85,.58);background:rgba(227,25,55,.14)}
        .research-watch{color:#ffd166;border:1px solid rgba(250,204,21,.48);background:rgba(250,204,21,.10)}
        .research-neutral{color:#9fb3c6;border:1px solid rgba(159,179,198,.38);background:rgba(159,179,198,.08)}
        .research-label{margin-top:.56rem;color:#7fa4c2;font:900 .59rem/1.2 system-ui;letter-spacing:.09em;text-transform:uppercase}
        .research-value{margin-top:.09rem;color:#dfe9f0;font:720 .76rem/1.38 system-ui}
        .research-authority{color:#ff8a9a;font-weight:900}
        @media(max-width:700px){.research-card{min-height:0}.research-card-top{align-items:flex-start;flex-direction:column}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="research-board-head">'
        '<div class="research-board-kicker">Research command center · report only</div>'
        '<div class="research-board-title">Research Promotion Scoreboard</div>'
        '<div class="research-board-copy">One view of the existing gates. Native research verdicts are displayed as written by each validator; this board never promotes, re-grades, or activates a model feature.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    statuses = board["Status"].astype(str).str.upper()
    authority = board["Production Authority"].astype(str).str.upper()
    a, b, c, d = st.columns(4)
    a.metric("Research lanes", len(board), help="Number of independent research/report lanes summarized here.")
    b.metric("Still learning", int(statuses.eq("LEARNING").sum()), help="Native gate status is LEARNING; more authentic evidence is required.")
    c.metric("Hold / fail / hurting", int(statuses.isin({"HOLD", "FAIL", "HURTING", "REJECT", "CAUTION"}).sum()), help="Lanes whose current native report says hold, fail, hurting, reject, or caution.")
    d.metric("Production authority", int(authority.ne("NONE").sum()), help="Count of research lanes with production authority. Research-only lanes should remain at zero unless promotion is explicitly implemented later.")

    for start in range(0, len(board), 2):
        cols = st.columns(2)
        for col, (_, row) in zip(cols, board.iloc[start:start + 2].iterrows()):
            status = _text(row["Status"], "UNKNOWN")
            with col:
                st.markdown(
                    '<div class="research-card">'
                    f'<div class="research-card-top"><div class="research-card-lane">{escape(_text(row["Lane"]))}</div>'
                    f'<div class="research-pill {_status_class(status)}">{escape(status)}</div></div>'
                    '<div class="research-label">Sample</div>'
                    f'<div class="research-value">{escape(_text(row["Sample"]))}</div>'
                    '<div class="research-label">Gate progress</div>'
                    f'<div class="research-value">{escape(_text(row["Gate Progress"]))}</div>'
                    '<div class="research-label">Current signal</div>'
                    f'<div class="research-value">{escape(_text(row["Signal"]))}</div>'
                    '<div class="research-label">Action</div>'
                    f'<div class="research-value">{escape(_text(row["Recommended Action"]))}</div>'
                    '<div class="research-label">Production authority</div>'
                    f'<div class="research-value research-authority">{escape(_text(row["Production Authority"]))}</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

    with st.expander("ⓘ How to read the Research Promotion Scoreboard", expanded=False):
        st.markdown(
            "**Status is source-owned.** LEARNING, HOLD, FAIL, HURTING, SUPPORTED, PASS, and other labels come from the lane's existing validator/report. The scoreboard does not recalculate them."
        )
        st.markdown(
            "**Gate Progress shows the evidence bottleneck.** A lane can have plenty of starts and still remain LEARNING because it lacks time diversity, catcher/umpire diversity, required seasons, or enough evidence in every required cell."
        )
        st.markdown(
            "**Current Signal is descriptive evidence, not activation.** Positive MAE or win-share movement can be interesting while the native gate still says LEARNING or FAIL."
        )
        st.markdown(
            "**Production Authority is the hard boundary.** NONE means the research lane cannot change the live baseball projection, Top Plays ranking, recommendation thresholds, or market logic."
        )
        detail = board[["Lane", "Status", "Reason", "Source", "Production Authority"]].copy()
        st.dataframe(detail, hide_index=True, width="stretch")

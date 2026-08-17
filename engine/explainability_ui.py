from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd
import streamlit as st


EXPLAINABILITY_UI_VERSION = "explainability-popovers-v1"
METRIC_HELP_VERSION = "metric-help-v2"


@dataclass(frozen=True)
class Explanation:
    title: str
    meaning: str
    method: str
    decision: str = ""
    inputs: tuple[str, ...] = ()
    current: tuple[str, ...] = ()
    note: str = ""


def _clean(value: object) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass
    return str(value)


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _pct(value: object) -> str:
    parsed = _num(value)
    return "—" if parsed is None else f"{parsed:.1%}"


def _f(value: object, digits: int = 2) -> str:
    parsed = _num(value)
    return "—" if parsed is None else f"{parsed:.{digits}f}"


def apply_explainability_theme() -> None:
    st.markdown(
        """
        <style>
        /* EXPLAINABILITY_POPOVERS_V1 · presentation only */
        .stApp [data-testid="stPopover"] button,
        .stApp div[data-testid="stPopover"] button{
            min-height:2rem!important;
            padding:.26rem .58rem!important;
            border:1px solid rgba(73,111,151,.68)!important;
            border-radius:999px!important;
            background:linear-gradient(180deg,rgba(18,48,78,.92),rgba(8,27,49,.94))!important;
            color:#cfe3f1!important;
            font-size:.70rem!important;
            font-weight:900!important;
            letter-spacing:.045em!important;
            text-transform:uppercase!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 5px 13px rgba(0,0,0,.16)!important;
        }
        .stApp [data-testid="stPopover"] button:hover,
        .stApp div[data-testid="stPopover"] button:hover{
            border-color:#ff3655!important;
            color:#fff!important;
            box-shadow:0 0 0 1px rgba(236,22,56,.08),0 7px 18px rgba(236,22,56,.12)!important;
        }
        .stApp .explain-title{
            color:#f5f1e9;
            font:900 1.05rem/1.15 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
            letter-spacing:.01em;
        }
        .stApp .explain-kicker{
            margin-bottom:.18rem;
            color:#ff6a7d;
            font:900 .62rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
            letter-spacing:.10em;
            text-transform:uppercase;
        }
        .stApp .explain-rule{
            height:1px;
            margin:.5rem 0 .58rem;
            background:linear-gradient(90deg,#ec1638,rgba(73,111,151,.35),transparent);
        }
        .stApp .explain-label{
            margin:.48rem 0 .12rem;
            color:#91b7d4;
            font:900 .64rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
            letter-spacing:.08em;
            text-transform:uppercase;
        }
        .stApp .explain-copy{
            color:#dce6ee;
            font:650 .82rem/1.45 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
        }
        .stApp .explain-current{
            margin:.20rem 0;
            padding:.34rem .46rem;
            border:1px solid rgba(72,106,137,.52);
            border-radius:8px;
            background:rgba(8,29,52,.72);
            color:#eef5fa;
            font:760 .78rem/1.35 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
        }
        .stApp .explain-note{
            margin-top:.55rem;
            padding:.42rem .5rem;
            border-left:3px solid #ff3655;
            background:rgba(105,14,33,.18);
            color:#c8d6e1;
            font:650 .74rem/1.4 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
        }
        @media (max-width:640px){
            .stApp [data-testid="stPopover"] button,
            .stApp div[data-testid="stPopover"] button{width:100%!important;min-height:2.45rem!important}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def explain_popover(
    explanation: Explanation,
    *,
    label: str = "ⓘ WHY?",
    use_container_width: bool = True,
) -> None:
    """Render a read-only Streamlit popover. Never computes or changes model state."""
    with st.popover(label, help=f"Explain {explanation.title}", use_container_width=use_container_width):
        st.markdown(
            f'<div class="explain-kicker">StrikeOut King 9000 · Explain</div>'
            f'<div class="explain-title">{explanation.title}</div>'
            '<div class="explain-rule"></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="explain-label">What it means</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="explain-copy">{explanation.meaning}</div>', unsafe_allow_html=True)
        st.markdown('<div class="explain-label">How we get it</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="explain-copy">{explanation.method}</div>', unsafe_allow_html=True)
        if explanation.inputs:
            st.markdown('<div class="explain-label">Inputs that matter</div>', unsafe_allow_html=True)
            for item in explanation.inputs:
                st.markdown(f'<div class="explain-current">{item}</div>', unsafe_allow_html=True)
        if explanation.current:
            st.markdown('<div class="explain-label">This block right now</div>', unsafe_allow_html=True)
            for item in explanation.current:
                st.markdown(f'<div class="explain-current">{item}</div>', unsafe_allow_html=True)
        if explanation.decision:
            st.markdown('<div class="explain-label">Why the app says this</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="explain-copy">{explanation.decision}</div>', unsafe_allow_html=True)
        if explanation.note:
            st.markdown(f'<div class="explain-note">{explanation.note}</div>', unsafe_allow_html=True)


def metric_help(key: str) -> str:
    """Return formula-level help for compact scorecard metrics.

    This text is presentation-only. It explains values already computed by the
    page and never recalculates projections, grades, rankings, or market logic.
    """
    specs = {
        # Projection History evidence scoreboard.
        "history_evidence_rows": (
            "What it is: every frozen evidence row currently loaded into Projection History.\n\n"
            "How it is calculated: count of rows in the durable projection evidence table (len(df)). Resolved and unresolved rows are both included.\n\n"
            "How to read it: this is the size of the evidence archive, not the number of completed games."
        ),
        "history_resolved_games": (
            "What it is: evidence rows where MLB has attached at least one final pitcher result.\n\n"
            "How it is calculated: count(actual Ks available OR actual Hits Allowed available OR actual Outs available). A row is counted once even when all three results exist.\n\n"
            "How to read it: this is the pool that can contribute to resolved diagnostics."
        ),
        "history_k_range_hits": (
            "What it is: resolved strikeout results that landed inside the frozen pregame K interval.\n\n"
            "How it is calculated: actual Ks must exist, both saved K range bounds must exist, and K range low ≤ actual Ks ≤ K range high.\n\n"
            "How to read it: this measures interval coverage, not whether an OVER/UNDER bet won."
        ),
        "history_k_hit_rate": (
            "What it is: the share of eligible resolved K intervals that contained the final strikeout total.\n\n"
            "Formula: K range hits ÷ resolved rows with actual Ks + both frozen K range bounds.\n\n"
            "How to read it: the saved interval is the model's central 80% range, so long-run coverage near 80% is the calibration target—not 100%."
        ),
        "history_hits_range_hits": (
            "What it is: resolved Hits Allowed results inside the frozen pregame Hits interval.\n\n"
            "How it is calculated: actual hits allowed and both saved Hits range bounds must exist, then low ≤ actual ≤ high.\n\n"
            "How to read it: it evaluates interval coverage only; it is not sportsbook grading."
        ),
        "history_hits_hit_rate": (
            "What it is: the share of eligible Hits Allowed intervals that contained the final result.\n\n"
            "Formula: Hits range hits ÷ resolved rows with actual Hits Allowed + both frozen Hits range bounds.\n\n"
            "How to read it: the central 80% interval should trend toward roughly 80% coverage over a large, stable sample."
        ),
        "history_outs_range_hits": (
            "What it is: resolved starter-outs results inside the frozen pregame Outs interval.\n\n"
            "How it is calculated: actual outs and both saved Outs range bounds must exist, then low ≤ actual ≤ high.\n\n"
            "How to read it: it measures whether uncertainty was sized correctly, not a betting win/loss."
        ),
        "history_outs_hit_rate": (
            "What it is: the share of eligible Outs intervals that contained the final starter-outs total.\n\n"
            "Formula: Outs range hits ÷ resolved rows with actual Outs + both frozen Outs range bounds.\n\n"
            "How to read it: compare it with the nominal 80% interval target; materially low coverage means the interval may be too narrow."
        ),
        "history_k_mae": (
            "What it is: average absolute strikeout projection error.\n\n"
            "Formula: mean(|final Ks − frozen projected Ks|) across resolved projection/result pairs. Positive and negative misses do not cancel.\n\n"
            "How to read it: lower is better; 0.00 would be perfect. A value of 1.81 K means the model missed by about 1.81 strikeouts on average, regardless of direction."
        ),
        "history_hits_mae": (
            "What it is: average absolute Hits Allowed projection error.\n\n"
            "Formula: mean(|final Hits Allowed − frozen projected Hits Allowed|) across rows where both values exist.\n\n"
            "How to read it: lower is better; this measures typical error size, not over/under bias."
        ),
        "history_outs_mae": (
            "What it is: average absolute Total Outs projection error.\n\n"
            "Formula: mean(|final starter outs − frozen projected outs|) across rows where both values exist.\n\n"
            "How to read it: lower is better; divide by 3 if you want to think of the typical error in innings."
        ),

        # Bet Tracker summary.
        "tracker_bets": "What it is: all saved tickets currently loaded into Bet Tracker.\n\nHow it is calculated: count of resolved tracker display rows, including straight bets and parlays.\n\nHow to read it: this is tracking volume, not a performance score.",
        "tracker_record": "What it is: finalized WIN-LOSS-PUSH record.\n\nHow it is calculated: counts the tracker grading states WIN, LOSS, and PUSH/PUSH LEG after MLB results are checked. Pending/live and INVALID LINE tickets are excluded.\n\nHow to read it: this is result grading only and never trains the projection model.",
        "tracker_pending": "What it is: saved tickets still waiting for a final grade, including live games.\n\nHow it is calculated: count of result states that are not final WIN/LOSS/PUSH/PUSH LEG/INVALID LINE.\n\nHow to read it: these tickets can still change and are not part of the finalized record.",
        "tracker_net": "What it is: total tracked profit/loss in units from tickets with calculable P/L.\n\nHow it is calculated: sum of each saved ticket's Profit/Loss value produced from its final grade, saved stake, and saved American odds. Missing P/L values do not create assumed profit.\n\nHow to read it: positive is profit; negative is loss. This is tracker accounting only.",
        "tracker_roi": "What it is: return on the stake counted by the tracker for finalized tickets.\n\nFormula: Net P/L ÷ total saved stake on final WIN/LOSS/PUSH rows with stake data.\n\nHow to read it: positive means profit relative to units risked; it is not a model probability or projection input.",

        # Daily Projection Run summary.
        "daily_projected": "What it is: starters returned in the current Daily Projection Run slate.\n\nHow it is calculated: number of projection rows in the selected-date slate after the batch capture/recovery path.\n\nHow to read it: these are the starters with a usable frozen model row on this run.",
        "daily_new": "What it is: first-time frozen snapshots created by this run.\n\nHow it is calculated: count returned by the batch runner for eligible starters that did not already have the durable pregame snapshot.\n\nHow to read it: these are new archive writes, not duplicate projections.",
        "daily_refreshed": "What it is: starters whose durable row already existed or was legally refreshed while still pregame.\n\nHow it is calculated: the batch runner's skipped/refreshed count. Frozen post-first-pitch model outputs are preserved.\n\nHow to read it: a high number is normal when rerunning the same slate.",
        "daily_history_only": "What it is: starters tracked for history/context but without an eligible model snapshot in this batch.\n\nHow it is calculated: length of the runner's history-only list.\n\nHow to read it: these rows are not silently promoted into a projection.",
        "daily_errors": "What it is: capture failures returned by the current batch run.\n\nHow it is calculated: number of error messages produced while loading/projecting the selected starter slate.\n\nHow to read it: 0 means the batch completed without recorded capture failures.",
        "daily_confirmed": "What it is: frozen slate rows using MLB's posted batting order instead of the active-roster fallback.\n\nHow it is calculated: count(lineup_source == CONFIRMED_LINEUP) in the current slate.\n\nHow to read it: more confirmed lineups means more specific matchup context; it does not mean a bet is automatically better.",

        # Top Plays summary.
        "top_highest_probability": "What it is: the largest model hit probability among today's already-ranked Top 5 legs.\n\nHow it is calculated: max(Model Probability) across the five model-ranked real-line legs.\n\nHow to read it: it is a model probability at that exact market/line, not a guarantee and not sportsbook implied probability.",
        "top_actionable": "What it is: Top 5 legs that clear the current straight-action gate.\n\nFormula: Model Probability ≥ 55% AND Data Quality ≥ 60/100.\n\nHow to read it: legs below either threshold stay WATCH even if they remain highly ranked.",
        "top_decision_supported": "What it is: Top 5 legs whose settled decision-learning segment has enough favorable evidence to be labeled SUPPORTED or STRONG EVIDENCE.\n\nHow it is calculated: count of Decision Evidence labels in {SUPPORTED, STRONG EVIDENCE}.\n\nHow to read it: this is supporting accountability evidence; it does not create or reorder the projection.",
        "top_signal_supported": "What it is: Top 5 legs with a pregame signal profile currently labeled SUPPORTED.\n\nHow it is calculated: count(Signal Evidence == SUPPORTED) after the board is ranked.\n\nHow to read it: signal evidence is descriptive safety context and cannot move today's rank by itself.",
        "top_live_prices": "What it is: how many Top 5 legs were matched to an exact current sportsbook offer.\n\nHow it is calculated: count(Live Offer == True) ÷ number of ranked plays.\n\nHow to read it: live price availability affects execution/add-to-tracker controls, not the model-first ranking.",
    }
    return specs.get(
        key,
        "What it is: a StrikeOut King scorecard metric.\n\nHow it is calculated: the value comes from the page's existing read-only data path.\n\nHow to read it: this help layer explains the displayed value and does not change model state.",
    )


def static_explanation(key: str) -> Explanation:
    specs: dict[str, Explanation] = {
        "active_lines": Explanation(
            "Active sportsbook lines",
            "These are the real execution lines currently attached to this pitcher for Strikeouts, Total Outs, and Hits Allowed.",
            "Daily Projection Run stores manual lines persistently. A saved paid strikeout snapshot can also supply the K line. Main Projection only reads those saved execution lines; it does not invent missing markets.",
            note="Sportsbook lines never create or move the baseball projection. They only give the model a real line to compare against.",
        ),
        "opposing_batters": Explanation(
            "Opposing Batter Box",
            "This summarizes how the expected opposing hitters have performed against the pitcher's handedness.",
            "Confirmed batting order is preferred. When MLB has not posted it, active-roster hitters are used. Hitter K% and H/PA splits shrink toward protected league rates when samples are incomplete.",
            inputs=("Pitcher handedness", "Confirmed lineup or active-roster fallback", "Hitter handedness splits", "Split plate appearances"),
            note="This is baseball matchup context. Sportsbook data is not an input.",
        ),
        "projection_actions": Explanation(
            "Bet Tracker / Parlay Actions",
            "These controls save the model's current real-line recommendation to Bet Tracker or queue it for a model parlay.",
            "Quick-add becomes available only when a real active line exists and the model side is OVER or UNDER. The listed stake and sportsbook price are tracking/execution information only.",
            note="Saving a bet never changes the projection or future ranking.",
        ),
        "distribution_k": Explanation(
            "Strikeout probability distribution",
            "The bars show how often each strikeout total occurred in the strikeout simulation path for this start.",
            "The model simulates the start repeatedly using pregame pitcher ability, opponent strikeout context, park/context and workload uncertainty. The chart is the distribution of those simulated outcomes.",
            note="This is the simulation path, not a sportsbook probability chart.",
        ),
        "distribution_outs": Explanation(
            "Outs probability distribution",
            "The bars show the simulated probability mass across possible total outs recorded by the starter.",
            "The independent outs model uses starter-only workload history and its own simulation/math paths. The displayed distribution comes from its simulation samples.",
            note="Outs are projected independently from strikeouts; they are not derived by multiplying the K projection.",
        ),
        "workload_primary": Explanation(
            "Primary workload forecast",
            "Expected pitches, batters faced and outs describe how much opportunity the starter is expected to receive before being removed.",
            "The workload layer uses starter-only history, recent pitches/BF/outs, rest and recent leash patterns. It produces exposure inputs before the strikeout/hits/outs models run.",
            inputs=("Starter-only recent games", "Pitches per batter faced", "Recent pitch/BF/outs trend", "Days since last start", "Recent leash"),
            note="Sportsbook data is excluded from workload estimation.",
        ),
        "role_shadow": Explanation(
            "Starter role workload shadow",
            "This is a feature-gated candidate adjustment for pitchers whose recent exposure may indicate a restricted or changed role.",
            "The role gate compares recent starter exposure with the normal workload context, creates candidate pitch/BF/outs values, and records whether the gate is allowed to apply them.",
            note="If the card says SHADOW or not applied, the candidate values are diagnostic only and do not change the live projection.",
        ),
        "team_leash": Explanation(
            "Team leash candidate",
            "This measures how the pitcher's team has recently handled starter workload, such as average pitches and how often starters reach later lineup turns.",
            "Resolved starter evidence for the same team is summarized into candidate workload multipliers and a leash label.",
            note="The team-leash layer remains context-only until leakage-safe validation earns promotion.",
        ),
        "form_history": Explanation(
            "Recent starter form table",
            "This is the recent starter-only game history used to understand workload and form context.",
            "The chart/table shows the raw recent pitches, batters faced, outs and strikeouts that existed before the selected game.",
            note="Relief appearances are excluded from the starter-history semantics used by the projection engine.",
        ),
        "model_paths": Explanation(
            "SIM vs MATH vs Ensemble",
            "StrikeOut King deliberately uses independent projection paths so one method cannot silently dominate without evidence.",
            "SIM is the Monte Carlo game path. MATH is the independent Negative-Binomial probability path. The live ensemble blends the two using calibration rules that only learn from resolved pregame evidence.",
            note="The ML challenger is separate and report-only unless it earns promotion through out-of-sample testing.",
        ),
        "model_ladder": Explanation(
            "Strikeout milestone ladder",
            "Each row estimates the chance the pitcher reaches a specific strikeout milestone such as 5+ or 7+.",
            "For every milestone, the simulation and mathematical probabilities are blended using that milestone's leakage-safe calibration weight. If there is not enough history, the protected baseline remains 50/50.",
        ),
        "calibration": Explanation(
            "Calibration diagnostics",
            "Calibration checks whether stated model probabilities have matched real outcomes over resolved pregame projections.",
            "Brier score and observed hit rates are computed from frozen historical probabilities and later MLB results. Each milestone/market learns independently after its minimum evidence threshold.",
            note="Sportsbook odds are excluded from calibration training.",
        ),
        "ml_shadow": Explanation(
            "ML shadow challenger",
            "The gradient-boosted model is a challenger that is allowed to report predictions but has zero live authority.",
            "It trains only on earlier resolved starter rows with a fixed pregame-only feature whitelist, then makes walk-forward out-of-sample predictions. Its MAE is compared with the current live projection.",
            note="It cannot affect SIM, MATH, the headline projection, Top Plays or bet recommendations until a future promotion decision explicitly changes that.",
        ),
        "tracker_summary": Explanation(
            "Bet Tracker summary",
            "These five counters separate tracking volume, finalized record, open/live tickets, unit profit/loss and return on risked stake.",
            "Each saved ticket is resolved against MLB pitching results. Record counts final WIN/LOSS/PUSH states; Pending/Live counts non-final tickets; Net P/L sums calculable ticket profit/loss; ROI divides that net result by the tracker's graded stake denominator.",
            inputs=("Saved side + exact line", "Final/live MLB pitcher stat", "Saved American odds when available", "Saved stake when available"),
            decision="These are accounting and grading conclusions about tickets you saved. They never feed back into pitcher projections or Top Plays ranking.",
            note="Use the individual metric ⓘ icons for the exact formula behind each counter.",
        ),
        "daily_capture": Explanation(
            "Projection Capture",
            "This is the batch action that freezes the announced starter slate into the durable pregame projection log.",
            "Each eligible starter is projected with the same model logic used by Main Projection. Existing frozen rows are preserved; only permitted pregame context refreshes before first pitch.",
            note="Running the slate does not require or consume sportsbook data.",
        ),
        "daily_status": Explanation(
            "Daily slate output status",
            "These counters audit exactly what the selected-date batch capture returned and what kind of durable evidence was produced.",
            "Projected starters = rows in the current slate; New snapshots = first-time durable captures; Already captured/refreshed = existing rows reused or legally refreshed while still pregame; History-only = tracked starters without an eligible projection snapshot; Errors = runner failures; Confirmed lineups = rows whose lineup_source is CONFIRMED_LINEUP.",
            decision="The counters describe capture integrity, not projection quality. Re-running a slate can legitimately increase the already-captured/refreshed count without creating duplicate model evidence.",
            note="Use each metric's ⓘ icon for its exact counting rule.",
        ),
        "manual_lines": Explanation(
            "Manual sportsbook lines",
            "This is the single persistent place to attach the real K, Outs and Hits Allowed lines you actually see at the sportsbook.",
            "The entered lines are saved as a durable execution overlay on top of the frozen projection row. Main Projection and Top Plays read this overlay later.",
            note="Entering a line never changes the underlying projection. Blank markets remain excluded from real-line recommendations.",
        ),
        "daily_table": Explanation(
            "Daily projection table",
            "This is the full frozen starter slate: model projections first, then execution lines and supporting context/audit fields.",
            "Projection, ranges and SIM/MATH probabilities come from the frozen pregame engine. Line/source fields come from the durable market overlay. Weather, lineup, workload and history fields document the context available at capture time.",
            note="The table intentionally preserves model-first / market-second separation.",
        ),
        "odds_credits": Explanation(
            "Odds API credits remaining",
            "This shows the quota value returned by the most recent paid strikeout-line request.",
            "The paid Daily Run button saves the API response headers locally. This display reads that saved quota snapshot and does not make another paid request just to show the number.",
        ),
        "history_archive": Explanation(
            "Projection Archive",
            "The archive is the durable user-facing record of frozen pregame projections, any attached real sportsbook lines, and later MLB outcomes.",
            "Daily Projection Run writes projection rows and the manual-line overlay. The resolver later attaches actual results. K Target is derived from the established model-supported milestone rule and K Result grades that target after resolution.",
            note="Historical sportsbook lines are execution overlays; they never retroactively alter the frozen model projection.",
        ),
        "history_learning": Explanation(
            "Learning diagnostics",
            "These reports measure how the frozen model has behaved after real games resolve.",
            "Rolling error, range coverage, calibration, Top 5 walk-forward results, decision segments and signal audits are computed only from compatible resolved pregame evidence.",
            note="Diagnostics can label evidence as learning/helping/hurting without automatically promoting a feature into the live model.",
        ),
        "top_summary": Explanation(
            "Top Plays summary",
            "These counters separate the strongest probability on today's Top 5, how many legs clear the straight-action gate, how much independent decision/signal evidence supports them, and whether an exact live price was found.",
            "The Top 5 is already ranked model-first from frozen pregame projections. Actionable Model Plays require Model Probability ≥55% and Data Quality ≥60/100. Decision/signal support is attached accountability evidence. Exact live prices affect execution only.",
            decision="A leg can be highly ranked but still remain WATCH if it misses the action gate. A missing live price can prevent one-click tracking without lowering the model rank.",
            note="Sportsbook odds never create the baseball forecast or rank the board. Use each metric's ⓘ icon for its exact rule.",
        ),
        "top_parlay": Explanation(
            "Top Plays parlay builder",
            "This lets you intentionally combine 2–5 already-ranked model legs into one tracked ticket.",
            "The builder does not multiply the displayed model probabilities or assume legs are independent. It warns when multiple legs use the same pitcher and saves the sportsbook label only for recordkeeping.",
        ),
        "top_diagnostics": Explanation(
            "Top Plays diagnostics",
            "These expandable reports show the evidence behind calibration, model-health blocks, decision tiers and feature accountability.",
            "All reports use settled leakage-safe pregame evidence. They retain their existing safety roles and do not reorder today's board after the fact.",
        ),
    }
    if key not in specs:
        return Explanation(
            key.replace("_", " ").title(),
            "This block displays a saved or computed StrikeOut King metric.",
            "The value comes from the page's existing data path. The explanation layer is read-only and does not recalculate it.",
        )
    return specs[key]


def recommendation_explanation(reco: Mapping[str, object], market: str) -> Explanation:
    side = str(reco.get("side", "NO LINE") or "NO LINE").upper()
    line = _num(reco.get("line"))
    projection = _num(reco.get("projection_mean"))
    model = _num(reco.get("model"))
    edge = _num(reco.get("edge"))
    reason = str(reco.get("reason", "") or "").strip()
    source = str(reco.get("active_line_source", "") or "").strip()
    reason_map = {
        "no_active_market_line": "There is no real active sportsbook line, so StrikeOut King refuses to manufacture an OVER/UNDER call.",
        "no_positive_aligned_edge": "The projection direction and probability do not clear the positive-edge action rule at this active line.",
        "probability_conflicts_with_projection": "The projection direction and calibrated probability disagree, so the safety rule returns PASS.",
        "projection_on_line": "The projection is effectively on the listed line, leaving no directional cushion.",
        "insufficient_model_confidence": "The model-side probability is below the current action confidence threshold.",
        "model_direction": "The active line has a model directional lean, but no priced market edge was required for this manual-line comparison.",
        "aligned_positive_edge": "Projection direction and calibrated probability agree, and the priced edge is positive enough to support the displayed side.",
    }
    if side == "NO LINE" or line is None:
        decision = reason_map["no_active_market_line"]
    elif side == "PASS":
        decision = reason_map.get(reason, "The current active line did not satisfy the model's aligned-action rules, so the card stays PASS.")
    else:
        decision = reason_map.get(reason, f"The calibrated model supports {side} at the real active line.")
    current = [f"Frozen projection: {_f(projection)}"]
    if line is not None:
        current.append(f"Active line: {line:g}" + (f" · {source}" if source else ""))
    if model is not None:
        current.append(f"Model probability for displayed side: {model:.1%}")
    if edge is not None:
        current.append(f"Price-relative edge: {edge:+.1%}")
    return Explanation(
        f"{market} decision",
        "This card compares the independent baseball projection with the real active sportsbook line and returns OVER, UNDER, PASS, or projection-only.",
        "The displayed side comes from the existing aligned-bet-lean safety logic. It checks projection direction, calibrated model probability and—when a real price is available—implied probability/edge.",
        decision=decision,
        inputs=("Frozen baseball projection", "Real active market line", "Calibrated SIM/MATH probability", "Sportsbook implied probability only when a saved price exists"),
        current=tuple(current),
        note="The market line is comparison/execution data only; it never feeds back into the baseball forecast.",
    )


def projection_metric_explanation(
    market: str,
    projection: object,
    low: object,
    high: object,
    *,
    extra: Iterable[str] = (),
) -> Explanation:
    market_key = market.lower()
    if "strike" in market_key:
        meaning = "Expected strikeouts for this starter before the game begins."
        method = "StrikeOut King blends an independent Monte Carlo strikeout path with an independent mathematical Negative-Binomial path, using leakage-safe calibration when enough compatible history exists."
    elif "out" in market_key:
        meaning = "Expected total outs recorded by this starter."
        method = "The independent outs model combines starter-only workload uncertainty with separate simulation and mathematical probability paths."
    else:
        meaning = "Expected hits allowed by this starter."
        method = "The hits-allowed model uses expected batters faced, opponent hit context and independent simulation/math paths with its own calibration history."
    current = [f"Projection: {_f(projection)}", f"Central 80% simulated range: {_clean(low)}–{_clean(high)}"]
    current.extend(str(item) for item in extra)
    return Explanation(
        f"Projected {market}",
        meaning,
        method,
        inputs=("Starter-only history", "Expected workload/exposure", "Pregame opponent context", "Model-specific uncertainty"),
        current=tuple(current),
        note="A projection is an expected average, not a guarantee and not a sportsbook line.",
    )


def weather_explanation(
    *, level: object, precip_probability: object, precipitation_mm: object, summary: object, roof_type: object = ""
) -> Explanation:
    level_text = str(level or "UNKNOWN").upper()
    decision = {
        "HIGH": "Open-air exterior conditions meet the current high delay-risk thresholds, so the UI flags DELAY RISK / AVOID.",
        "ELEVATED": "Rain/thunder indicators meet the elevated thresholds, so the UI says CAUTION / RECHECK.",
        "LOW": "There is some rain signal, but it remains below the elevated-delay thresholds.",
        "NONE": "The game-window forecast does not currently meet a rain-delay warning threshold.",
        "ROOF": "The venue is roof-capable, so exterior rain is not treated as an automatic pitcher-avoid delay signal. Roof status still needs a near-game check.",
        "UNKNOWN": "The weather feed or venue context is not sufficient for a reliable warning state.",
    }.get(level_text, "The displayed weather state comes directly from the existing weather-risk classifier.")
    return Explanation(
        "Game weather / delay risk",
        "This is an informational game-window rain/delay warning designed to keep a good pitcher projection from becoming a bad bet because of interruption risk.",
        "The weather engine checks the forecast window from two hours before first pitch through four hours after, using precipitation probability, precipitation intensity and weather codes. Roof-capable venues get a separate protected state.",
        decision=decision,
        current=(
            f"Risk state: {level_text}",
            f"Peak precipitation probability: {_clean(precip_probability)}%" if _num(precip_probability) is not None else "Peak precipitation probability: —",
            f"Peak precipitation: {_f(precipitation_mm, 1)} mm/h" if _num(precipitation_mm) is not None else "Peak precipitation: —",
            f"Roof metadata: {_clean(roof_type) or '—'}",
            f"Reason: {_clean(summary)}",
        ),
        note="Weather is informational and does not modify the baseball projection.",
    )


def top_play_explanation(play: Mapping[str, object]) -> Explanation:
    probability = _num(play.get("Model Probability"))
    quality = _num(play.get("Data Quality"))
    side = str(play.get("Side", "") or "").upper()
    line = _num(play.get("Line"))
    projection = _num(play.get("Projection"))
    rank = _num(play.get("Rank"))
    model_ok = probability is not None and probability >= 0.55 and quality is not None and quality >= 60
    status = "MODEL PLAY" if model_ok else "WATCH"
    decision = (
        "This leg clears the current straight-action gate: model hit probability is at least 55% and data quality is at least 60/100."
        if model_ok else
        "This leg remains in the ranked Top 5, but it does not clear the current straight-action probability/data-quality gate, so it is labeled WATCH."
    )
    return Explanation(
        f"Top Play #{int(rank) if rank is not None else '—'} · {_clean(play.get('Pitcher'))}",
        "A Top Play is one of the five real-line pitcher-prop legs with the strongest model-first ranking for the slate.",
        "The board is built from frozen pregame projections, calibrated model probability and data quality. Market line availability is required for execution integrity; sportsbook odds do not rank the board.",
        decision=decision,
        inputs=("Frozen projection snapshot", "Real active sportsbook line", "Calibrated model probability", "Data quality", "Model-health safety blocks"),
        current=(
            f"Market: {_clean(play.get('Market'))} · {side} {line:g}" if line is not None else f"Market: {_clean(play.get('Market'))}",
            f"Projection: {_f(projection)}",
            f"Model hit probability: {_pct(probability)}",
            f"Data quality: {int(quality) if quality is not None else '—'}/100",
            f"Action state: {status}",
            f"Line source: {_clean(play.get('Line Source'))}",
            f"Decision evidence: {_clean(play.get('Decision Evidence'))}",
        ),
        note="A higher rank is a model preference among today's eligible real-line legs, not a guarantee of winning.",
    )


def ticket_explanation(ticket: Mapping[str, object]) -> Explanation:
    result = str(ticket.get("Result", "PENDING") or "PENDING").upper()
    profit = _num(ticket.get("Profit/Loss"))
    stake = _num(ticket.get("Stake"))
    meaning = "This ticket is a saved tracking record. Its status is graded from MLB pitching results against the line and side you saved."
    method = "For straight bets, the tracker resolves the pitcher's actual market statistic and applies the saved OVER/UNDER grading rule. Parlays grade each leg first, then combine leg states. P/L is calculated only when usable stake and odds were saved."
    decision = {
        "WIN": "The final MLB statistic satisfied the saved side/line rule.",
        "LOSS": "The final MLB statistic did not satisfy the saved side/line rule.",
        "LIVE AHEAD": "The game is still live and the current statistic is presently on the winning side of the saved line.",
        "LIVE BEHIND": "The game is still live and the current statistic is presently on the losing side of the saved line.",
        "PENDING": "The tracker is still waiting for a final/live MLB statistic that can grade the ticket.",
        "INVALID LINE": "This legacy ticket used a synthetic/default line and is intentionally excluded from the real-line record.",
    }.get(result, "The displayed status comes from the existing Bet Tracker grading state machine.")
    return Explanation(
        f"Tracked ticket · {_clean(ticket.get('Pitcher'))}",
        meaning,
        method,
        decision=decision,
        current=(
            f"Market: {_clean(ticket.get('Market'))}",
            f"Bet: {_clean(ticket.get('Bet'))}",
            f"Game status: {_clean(ticket.get('Game Status'))}",
            f"Result: {result}",
            f"Stake: {_f(stake)}u" if stake is not None else "Stake: —",
            f"P/L: {profit:+.2f}u" if profit is not None else "P/L: —",
        ),
        note="Bet Tracker data never feeds back into the pitcher projection model.",
    )


def leg_explanation(leg: Mapping[str, object]) -> Explanation:
    side = str(leg.get("Side", "") or "").upper()
    line = _num(leg.get("Line"))
    actual = _num(leg.get("Actual"))
    projection = _num(leg.get("Projection"))
    probability = _num(leg.get("Model Probability"))
    return Explanation(
        f"Ticket leg · {_clean(leg.get('Player'))}",
        "This is one individual pitcher-prop leg inside the saved ticket.",
        "Current/final MLB pitching stats are compared with the exact saved side and line. Projection and model probability are the pregame values saved with the ticket when available.",
        current=(
            f"Bet: {_clean(leg.get('Market'))} · {side} {line:g}" if line is not None else f"Market: {_clean(leg.get('Market'))}",
            f"Current/final actual: {_clean(actual)}",
            f"Pregame projection: {_f(projection)}",
            f"Saved model probability: {_pct(probability)}",
            f"Grade: {_clean(leg.get('Result'))}",
        ),
        note="The progress display is tracking only; live game stats never alter the frozen pregame projection.",
    )

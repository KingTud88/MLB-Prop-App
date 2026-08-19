from __future__ import annotations

from html import escape
import re
from typing import Iterable, Mapping, Sequence

import pandas as pd
import streamlit as st

from engine.explainability_ui import Explanation


CARD_EXPLAINABILITY_VERSION = "card-info-v3"


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _f(value: object, digits: int = 2) -> str:
    parsed = _num(value)
    return "—" if parsed is None else f"{parsed:.{digits}f}"


def _pct(value: object, digits: int = 1) -> str:
    parsed = _num(value)
    return "—" if parsed is None else f"{parsed:.{digits}%}"


def _american(value: object) -> str:
    parsed = _num(value)
    return "—" if parsed is None else f"{parsed:+.0f}"


def _clean(value: object) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass
    text = str(value).strip()
    return text or "—"


def apply_card_info_theme() -> None:
    """Make keyed card popovers render as compact top-right info icons."""
    st.markdown(
        """
        <style>
        /* CARD_INFO_V2 · compact, read-only explainability controls */
        .stApp div[data-testid="stColumn"]:has([class*="st-key-card-info-"]),
        .stApp div[data-testid="stVerticalBlockBorderWrapper"]:has([class*="st-key-card-info-"]){
            position:relative!important;
        }
        .stApp [class*="st-key-card-info-"]{
            position:absolute!important;
            top:.42rem!important;
            right:.46rem!important;
            z-index:40!important;
            width:2.06rem!important;
            min-height:0!important;
            margin:0!important;
            padding:0!important;
        }
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"]{
            width:2.06rem!important;
            min-width:2.06rem!important;
            margin:0!important;
            padding:0!important;
        }
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button{
            width:2.06rem!important;
            min-width:2.06rem!important;
            height:2.06rem!important;
            min-height:2.06rem!important;
            padding:0 0 .06rem!important;
            display:flex!important;
            align-items:center!important;
            justify-content:center!important;
            border-radius:999px!important;
            border:1.5px solid rgba(151,192,222,.88)!important;
            background:linear-gradient(145deg,rgba(12,39,63,.98),rgba(5,20,35,.98))!important;
            color:#f3f9fd!important;
            font:900 1.04rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;
            letter-spacing:0!important;
            text-transform:none!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 5px 13px rgba(0,0,0,.28),0 0 0 1px rgba(77,135,179,.08)!important;
        }
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button:hover{
            border-color:#ff3655!important;
            color:#fff!important;
            background:linear-gradient(145deg,#451327,#281020)!important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 0 0 2px rgba(236,22,56,.12),0 7px 17px rgba(236,22,56,.22)!important;
        }
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button svg{display:none!important}
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button p,
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button [data-testid="stMarkdownContainer"] p{
            margin:0!important;
            padding:0!important;
            font:900 1.04rem/1 system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;
            transform:translateY(-.015rem)!important;
        }
        .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button:focus-visible{
            outline:none!important;
            border-color:#fff!important;
            box-shadow:0 0 0 2px rgba(236,22,56,.34),0 7px 17px rgba(0,0,0,.30)!important;
        }
        @media (max-width:640px){
            .stApp [class*="st-key-card-info-"] [data-testid="stPopover"] button{
                width:1.86rem!important;
                min-width:1.86rem!important;
                height:1.86rem!important;
                min-height:1.86rem!important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render(explanation: Explanation) -> None:
    st.markdown(
        f'<div class="explain-kicker">StrikeOut King 9000 · Card Detail</div>'
        f'<div class="explain-title">{escape(explanation.title)}</div>'
        '<div class="explain-rule"></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="explain-label">What this box tells you</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="explain-copy">{escape(explanation.meaning)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="explain-label">How this value is built</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="explain-copy">{escape(explanation.method)}</div>', unsafe_allow_html=True)
    if explanation.inputs:
        st.markdown('<div class="explain-label">Today\'s inputs & models</div>', unsafe_allow_html=True)
        for item in explanation.inputs:
            st.markdown(f'<div class="explain-current">{escape(str(item))}</div>', unsafe_allow_html=True)
    if explanation.current:
        st.markdown('<div class="explain-label">Current calculation</div>', unsafe_allow_html=True)
        for item in explanation.current:
            st.markdown(f'<div class="explain-current">{escape(str(item))}</div>', unsafe_allow_html=True)
    if explanation.decision:
        st.markdown('<div class="explain-label">Why this conclusion</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="explain-copy">{escape(explanation.decision)}</div>', unsafe_allow_html=True)
    if explanation.note:
        st.markdown(f'<div class="explain-note">{escape(explanation.note)}</div>', unsafe_allow_html=True)


def card_info_popover(explanation: Explanation, *, key: str) -> None:
    """Render a small top-right ⓘ for a card/metric. Read-only; never changes model state."""
    safe_key = re.sub(r"[^A-Za-z0-9_-]+", "-", str(key)).strip("-") or "detail"
    with st.popover(
        "i",
        help=f"Explain {explanation.title}",
        type="tertiary",
        width="content",
        key=f"card-info-{safe_key}",
    ):
        _render(explanation)


def active_market_explanation(
    market_label: str,
    line: object,
    source: object,
    offers: Sequence[Mapping[str, object]],
    *,
    market_names: Iterable[str],
) -> Explanation:
    point = _num(line)
    source_text = _clean(source)
    selected_book = source_text.split("·", 1)[1].strip() if "·" in source_text else ""
    aliases = {str(value) for value in market_names}
    matching: list[Mapping[str, object]] = []
    if point is not None:
        for offer in offers or ():
            if str(offer.get("market", "")) not in aliases:
                continue
            offer_point = _num(offer.get("point"))
            if offer_point is None or abs(offer_point - point) > 1e-9:
                continue
            if selected_book and str(offer.get("book", "")).strip().lower() != selected_book.lower():
                continue
            matching.append(offer)
    over = next((row for row in matching if str(row.get("name", row.get("side", ""))).lower() == "over"), None)
    under = next((row for row in matching if str(row.get("name", row.get("side", ""))).lower() == "under"), None)
    fetched = next((str(row.get("fetched_at_utc", "")).strip() for row in matching if row.get("fetched_at_utc")), "")
    current = [
        f"Active line: {point:g}" if point is not None else "Active line: none",
        f"Provider / book: {source_text}",
    ]
    if point is not None:
        current.extend((
            f"OVER price: {_american(over.get('price')) if over else '—'}",
            f"UNDER price: {_american(under.get('price')) if under else '—'}",
            f"Snapshot captured: {fetched or '—'}",
        ))
    decision = (
        "A complete real pregame Over/Under pair exists on one sportsbook at the same number, so this line is allowed to become the execution comparison line."
        if point is not None
        else "No eligible fresh complete Over/Under pair is attached for this pitcher/market, so the app fails closed and shows NO ACTIVE LINE."
    )
    return Explanation(
        f"{market_label} active sportsbook line",
        "The real sportsbook number StrikeOut King uses only to compare the independent baseball projection with an executable market.",
        "SportsGameOdds is read from the saved disk snapshot. ESPN BET is preferred; a fallback sportsbook is allowed only when both Over and Under exist on the exact same number. Snapshot data older than six hours is rejected, and consensus/fair lines are never invented.",
        inputs=("SportsGameOdds saved snapshot", "Same-book Over + Under pair", "Pregame capture timestamp", "Book priority: ESPN BET → FanDuel → DraftKings → BetMGM → Caesars"),
        current=tuple(current),
        decision=decision,
        note="This market input never changes the pitcher projection itself.",
    )


def pitcher_projection_explanation(
    market: str,
    projection: object,
    low: object,
    high: object,
    context: Mapping[str, object],
) -> Explanation:
    key = market.strip().lower()
    history_games = int(_num(context.get("history_games")) or 0)
    workload = (
        f"Starter history used: {history_games} starts · expected workload {_f(context.get('expected_pitches'), 1)} pitches / "
        f"{_f(context.get('expected_bf'), 1)} BF / {_f(context.get('expected_outs'), 1)} outs"
    )
    lineup = (
        f"Opponent context: {_clean(context.get('lineup_source'))} · {_clean(context.get('lineup_batters'))} hitters · "
        f"{_clean(context.get('split_pa'))} historical split PA vs {_clean(context.get('pitcher_hand'))}-handed pitching"
    )
    quality = f"Data quality: {_clean(context.get('data_quality'))}/100 · confidence {_clean(context.get('confidence'))}"
    draws = f"Simulation draws: {int(_num(context.get('draws')) or 0):,}"

    if "strike" in key:
        meaning = "The expected strikeout total for this starter before first pitch, plus the model's central simulated uncertainty range."
        method = (
            "The K forecast uses two independent paths. SIM runs plate-appearance Monte Carlo games with workload uncertainty. "
            "MATH uses a Negative-Binomial strikeout model. Both use pitcher K skill and the opponent's handedness-specific matchup K rate; "
            "the headline mean blends the paths using the existing leakage-safe calibration weights from resolved pregame history."
        )
        inputs = (
            workload,
            lineup,
            f"Pitcher K skill: {_pct(context.get('pitcher_k_pct'))} · matchup K%: {_pct(context.get('matchup_k_pct'))}",
            f"Park K factor: {_f(context.get('park_factor'), 3)} · {draws}",
            quality,
        )
        current = (
            f"SIM path: {_f(context.get('sim_mean'))} K · SD {_f(context.get('sim_sd'))}",
            f"MATH path: {_f(context.get('math_mean'))} K · SD {_f(context.get('math_sd'))}",
            f"Headline blend: SIM {_pct(context.get('sim_weight'))} / MATH {_pct(1.0 - float(_num(context.get('sim_weight')) or 0.5))}",
            f"Final projection: {_f(projection)} K · ensemble SD {_f(context.get('ensemble_sd'))}",
            f"Central 80% simulation range: {_clean(low)}–{_clean(high)} K",
        )
        decision = "The displayed K number is the blended expected value from the independent SIM and MATH paths after the current workload and opponent matchup inputs are frozen."
    elif "out" in key:
        meaning = "The expected number of outs this starter records before leaving the game, with a central simulated workload range."
        method = (
            "The Outs model is independent from the K model. SIM bootstraps recent real starter workloads, shifts them toward today's workload target, "
            "and adds game-level noise. MATH uses a bounded beta-binomial model centered on the same pregame workload target. "
            "The headline mean is the protected 50/50 SIM/MATH ensemble; line-specific probabilities can use their own calibration weights."
        )
        inputs = (
            workload,
            f"Outs history: {int(_num(context.get('starts_used')) or 0)} starts · recent weighted mean {_f(context.get('recent_mean_outs'))} · recent SD {_f(context.get('recent_sd_outs'))}",
            f"Workload uncertainty SD: {_f(context.get('workload_outs_sd'))} outs · {draws}",
            quality,
        )
        current = (
            f"SIM path: {_f(context.get('sim_mean'))} outs · SD {_f(context.get('sim_sd'))}",
            f"MATH path: {_f(context.get('math_mean'))} outs · SD {_f(context.get('math_sd'))}",
            f"Headline blend: 50% SIM / 50% MATH",
            f"Final projection: {_f(projection)} outs · ensemble SD {_f(context.get('ensemble_sd'))}",
            f"Central 80% simulation range: {_clean(low)}–{_clean(high)} outs",
        )
        decision = "The displayed Outs number is the independent workload ensemble centered on today's expected starter exposure, not a conversion from the strikeout projection."
    else:
        meaning = "The expected hits this starter allows before leaving the game, with a central simulated uncertainty range."
        method = (
            "The Hits Allowed model is independent from Ks and Outs. SIM samples today's expected batters faced and a game-level hit rate, then simulates hits batter by batter. "
            "MATH uses an over-dispersed Negative-Binomial model built from starter hit history, the opponent hit context, park factor and workload. "
            "The headline mean is a protected 50/50 SIM/MATH ensemble; line-specific probabilities use the existing hits calibration layer."
        )
        inputs = (
            workload,
            lineup,
            f"Pitcher H/PA: {_pct(context.get('pitcher_hit_rate'))} · opponent H/PA: {_pct(context.get('opponent_hit_rate'))} · matchup H/PA: {_pct(context.get('matchup_hit_rate'))}",
            f"Park factor: {_f(context.get('park_factor'), 3)} · {draws}",
            quality,
        )
        current = (
            f"SIM path: {_f(context.get('sim_mean'))} hits · SD {_f(context.get('sim_sd'))}",
            f"MATH path: {_f(context.get('math_mean'))} hits · SD {_f(context.get('math_sd'))}",
            "Headline blend: 50% SIM / 50% MATH",
            f"Final projection: {_f(projection)} hits · ensemble SD {_f(context.get('ensemble_sd'))}",
            f"Central 80% simulation range: {_clean(low)}–{_clean(high)} hits",
        )
        decision = "The displayed Hits Allowed number is the independent hit-rate/workload ensemble after the current opposing lineup context is frozen."

    return Explanation(
        f"Projected {market}",
        meaning,
        method,
        inputs=tuple(inputs),
        current=tuple(current),
        decision=decision,
        note="Sportsbook lines and prices are execution/comparison data only and are not inputs to this projection.",
    )


def market_decision_explanation(
    reco: Mapping[str, object],
    market: str,
    detail: Mapping[str, object],
) -> Explanation:
    side = str(reco.get("side", "NO LINE") or "NO LINE").upper()
    line = _num(reco.get("line"))
    projection = _num(reco.get("projection_mean"))
    model = _num(reco.get("model"))
    edge = _num(reco.get("edge"))
    reason = str(reco.get("reason", "") or "").strip()
    source = _clean(reco.get("active_line_source"))
    sim = _num(detail.get("sim_probability"))
    math_p = _num(detail.get("math_probability"))
    sim_w = _num(detail.get("sim_weight"))
    math_w = _num(detail.get("math_weight"))
    over_price = detail.get("over_price")
    under_price = detail.get("under_price")

    reason_map = {
        "no_active_market_line": "There is no eligible real active sportsbook line, so the app refuses to manufacture an OVER/UNDER call.",
        "no_positive_aligned_edge": "Projection direction and model probability do not clear the positive-edge action rule at this exact line/price.",
        "probability_conflicts_with_projection": "Projection direction and calibrated probability disagree, so the safety rule returns PASS.",
        "projection_on_line": "The projection is effectively on the listed line, so there is not enough directional cushion.",
        "insufficient_model_confidence": "The model-side probability is below the current action confidence threshold.",
        "model_direction": "Projection direction and calibrated probability support the displayed side at the real active line.",
        "aligned_positive_edge": "Projection direction and calibrated probability agree, and the price-relative edge clears the positive-edge rule.",
    }
    decision = reason_map.get(reason, "The existing aligned-bet-lean safety logic produced the displayed state from the frozen projection, calibrated probability and real market line.")
    if side == "NO LINE" or line is None:
        decision = reason_map["no_active_market_line"]

    current = [
        f"Frozen projection: {_f(projection)}",
        f"Active line: {line:g} · {source}" if line is not None else "Active line: none",
    ]
    if sim is not None or math_p is not None:
        current.append(f"At this line: SIM {_pct(sim)} · MATH {_pct(math_p)}")
    if sim_w is not None or math_w is not None:
        current.append(f"Calibration blend: SIM {_pct(sim_w)} · MATH {_pct(math_w)}")
    if model is not None:
        current.append(f"Model probability for displayed side: {_pct(model)}")
    current.append(f"Sportsbook prices: OVER {_american(over_price)} · UNDER {_american(under_price)}")
    if edge is not None:
        current.append(f"Price-relative edge: {edge:+.1%}")

    return Explanation(
        f"{market} decision",
        "The betting/execution card compares the frozen baseball projection with the exact real sportsbook line and returns OVER, UNDER, PASS, or projection-only.",
        "The app first determines projection direction. It then gets SIM and MATH hit probabilities at this exact line, applies the existing leakage-safe line-specific calibration blend, and—when prices exist—compares the model probability with sportsbook implied probability. The established aligned-bet-lean safety rules make the final call.",
        inputs=("Frozen projection", "Exact real active line", "SIM probability at that line", "MATH probability at that line", "Line-specific calibration weights", "Saved Over/Under sportsbook prices"),
        current=tuple(current),
        decision=decision,
        note="The recommendation layer never feeds sportsbook information back into the baseball forecast.",
    )


def matchup_metric_explanation(
    metric: str,
    matchup: Mapping[str, object],
    *,
    lineup_source: object,
    pitcher_hand: object,
) -> Explanation:
    key = str(metric).lower()
    confirmed = bool(matchup.get("confirmed"))
    batters = int(_num(matchup.get("batters")) or 0)
    split_pa = int(_num(matchup.get("pa")) or 0)
    source = _clean(lineup_source)
    hand = _clean(pitcher_hand)
    base_inputs = (
        f"Lineup source: {source} · confirmed {'YES' if confirmed else 'NO'}",
        f"Hitters represented: {batters} · total historical split PA: {split_pa}",
        f"Pitcher hand used for hitter splits: {hand}",
    )

    if key == "k_rate":
        return Explanation(
            "Matchup K%",
            "The opponent strikeout rate used by the K projection for this pitcher/lineup matchup.",
            "For a confirmed lineup, each hitter's K% versus this pitcher's handedness is independently shrunk toward the 22.4% league K baseline with a 60-PA prior, then all lineup hitters are averaged equally. Before a lineup is posted, available active-roster splits are PA-weighted. The final value is clipped to the protected model range.",
            inputs=base_inputs + ("Confirmed-lineup prior: 60 PA per hitter", "League K baseline: 22.4%"),
            current=(f"Matchup K% used by model: {_pct(matchup.get('k_rate'))}",),
            decision="This number becomes the opponent_k_pct input used by both strikeout projection paths.",
            note="It is not a sportsbook number and is based only on pregame baseball data.",
        )
    if key == "hit_rate":
        return Explanation(
            "Matchup H/PA",
            "The opponent hit-per-plate-appearance rate used by the Hits Allowed projection.",
            "For a confirmed lineup, each hitter's H/PA versus the pitcher's handedness is shrunk toward the 23.5% league hit baseline with a 60-PA prior, then hitters are averaged equally. Before the lineup is posted, available active-roster splits are PA-weighted.",
            inputs=base_inputs + ("Confirmed-lineup prior: 60 PA per hitter", "League H/PA baseline: 23.5%"),
            current=(f"Matchup H/PA used by model: {_pct(matchup.get('hit_rate'))}",),
            decision="This value is combined with the pitcher's own hit-allowed rate inside the independent Hits Allowed model.",
            note="It does not change the strikeout or outs projection directly.",
        )
    if key == "pa":
        return Explanation(
            "Split PA",
            "The total historical plate appearances found for the displayed hitters against the selected pitcher's handedness.",
            "The batter box loads same-season hitter splits versus right- or left-handed pitching and sums the available PA. A confirmed hitter with no usable split stays in the lineup with a league-baseline fallback and contributes 0 historical split PA.",
            inputs=base_inputs,
            current=(f"Historical split PA available: {split_pa}",),
            decision="More split PA means more direct hitter evidence is available; the confirmed-lineup shrinkage still protects the model from letting one veteran's large sample dominate the nine-man matchup.",
        )
    if key == "high":
        return Explanation(
            "HIGH K hitters",
            "How many displayed hitters have a raw handedness-specific strikeout split of at least 30%.",
            "Each batter is classified from the raw K% vs this pitcher's hand before the lineup-summary shrinkage: HIGH is K% ≥ 30%, ELEVATED is 25%–29.9%, otherwise NORMAL.",
            inputs=base_inputs + ("HIGH threshold: 30.0% K",),
            current=(f"HIGH K hitters: {int(_num(matchup.get('high')) or 0)}",),
            decision="This count is descriptive matchup context. The projection uses the summarized Matchup K% rather than adding a separate bonus for the count.",
        )
    return Explanation(
        "ELEVATED K hitters",
        "How many displayed hitters have a raw handedness-specific strikeout split from 25.0% through 29.9%.",
        "Each batter is classified from the raw K% vs this pitcher's hand before the lineup-summary shrinkage: HIGH is K% ≥ 30%, ELEVATED is 25%–29.9%, otherwise NORMAL.",
        inputs=base_inputs + ("ELEVATED range: 25.0% ≤ K% < 30.0%",),
        current=(f"ELEVATED K hitters: {int(_num(matchup.get('elevated')) or 0)}",),
        decision="This count is descriptive context; it does not independently boost the projection beyond the Matchup K% input.",
    )

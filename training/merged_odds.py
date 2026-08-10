from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from training.odds_api import (
    OddsAPIError,
    flatten_pitcher_strikeouts,
    get_api_key,
    get_event_pitcher_strikeouts,
    get_events,
    usage_summary,
)

_TEAM_NAMES = {
    "LAA":"Los Angeles Angels","ARI":"Arizona Diamondbacks","BAL":"Baltimore Orioles",
    "BOS":"Boston Red Sox","CHC":"Chicago Cubs","CIN":"Cincinnati Reds",
    "CLE":"Cleveland Guardians","COL":"Colorado Rockies","DET":"Detroit Tigers",
    "HOU":"Houston Astros","KCR":"Kansas City Royals","LAD":"Los Angeles Dodgers",
    "WSH":"Washington Nationals","NYM":"New York Mets","ATH":"Athletics",
    "PIT":"Pittsburgh Pirates","SDP":"San Diego Padres","SEA":"Seattle Mariners",
    "SFG":"San Francisco Giants","STL":"St. Louis Cardinals","TBR":"Tampa Bay Rays",
    "TEX":"Texas Rangers","TOR":"Toronto Blue Jays","MIN":"Minnesota Twins",
    "PHI":"Philadelphia Phillies","ATL":"Atlanta Braves","CHW":"Chicago White Sox",
    "MIA":"Miami Marlins","NYY":"New York Yankees","MIL":"Milwaukee Brewers",
}


def _team_matches(abbr: str, api_name: str) -> bool:
    target = _TEAM_NAMES.get(str(abbr).upper(), str(abbr)).lower()
    actual = str(api_name or "").lower()
    return target == actual or target in actual or actual in target


def _find_event(events: list[dict[str, Any]], game: Any) -> dict[str, Any] | None:
    for event in events:
        away = event.get("away_team", "")
        home = event.get("home_team", "")
        if (_team_matches(game.team, away) and _team_matches(game.opponent, home)) or (
            _team_matches(game.team, home) and _team_matches(game.opponent, away)
        ):
            return event
    return None


def _implied_probability(american_odds: float) -> float:
    odds = float(american_odds)
    if odds >= 0:
        return 100.0 / (odds + 100.0)
    return (-odds) / ((-odds) + 100.0)


def _fair_american(probability: float) -> int:
    p = float(np.clip(probability, 1e-6, 1 - 1e-6))
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _market_edge(model_probability: float, american_odds: float) -> float:
    """Simple model-vs-market probability edge, before vig removal."""
    return float(model_probability - _implied_probability(american_odds))


def _model_probability(projection: Any, threshold: int, side: str = "Over") -> float:
    samples = np.asarray(projection.k_samples, dtype=float)
    p_over = float(np.mean(samples >= threshold))
    return p_over if str(side).title() == "Over" else 1.0 - p_over


def _ladder_market_rows(rows: list[dict[str, Any]], projection: Any, thresholds: list[int]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        try:
            line = float(row.get("line"))
            price = int(row.get("american_odds"))
        except (TypeError, ValueError):
            continue
        side = str(row.get("side", "")).title()
        if side not in {"Over", "Under"}:
            continue
        # A sportsbook 2.5 line corresponds to the model's 3+ milestone;
        # 3.5 corresponds to 4+, etc.
        threshold = int(round(line + 0.5)) if side == "Over" else int(round(line + 0.5))
        if threshold not in thresholds:
            continue
        model_p = _model_probability(projection, threshold, side)
        implied = _implied_probability(price)
        output.append({
            "Milestone": f"{threshold}+" if side == "Over" else f"< {threshold}",
            "Book": row.get("bookmaker", "Unknown"),
            "Side": side,
            "Line": line,
            "Odds": price,
            "Model": model_p,
            "Fair": _fair_american(model_p),
            "Implied": implied,
            "Edge": _market_edge(model_p, price),
            "market": row.get("market", ""),
        })
    return output


def render_merged_odds(game: Any, selected_date: Any, projection: Any) -> None:
    """Render live odds, model ladder, fair odds, and market edge on Projection."""
    st.markdown(
        '<div class="section-frame"><div class="section-ribbon">LIVE ODDS + STRIKEOUT LADDER</div>',
        unsafe_allow_html=True,
    )
    api_key = get_api_key(st.secrets)
    if not api_key:
        st.info("Odds API is not connected. Add ODDS_API_KEY to Streamlit Secrets to enable live sportsbook lines.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    thresholds = list(range(3, 11))
    labels = [f"{n}+" for n in thresholds]
    label_to_threshold = dict(zip(labels, thresholds))
    c1, c2 = st.columns([1.4, 1.0])
    with c1:
        current_label = st.session_state.get("odds_model_ladder_label", "5+")
        if current_label not in labels:
            current_label = "5+"
        selected_label = st.selectbox("Model strikeout ladder", labels, index=labels.index(current_label), key="odds_model_ladder_choice")
        selected_threshold = label_to_threshold[selected_label]
    with c2:
        probability = _model_probability(projection, selected_threshold, "Over")
        st.metric(f"Model probability {selected_label}", f"{probability:.1%}")

    if st.button(f"Use model {selected_label} in StrikeOut King", type="primary", key="use_model_ladder"):
        st.session_state["odds_selected_side"] = "Over"
        st.session_state["odds_selected_line"] = float(selected_threshold) - 0.5
        st.session_state["odds_selected_display_line"] = f"OVER {selected_label}"
        st.session_state["odds_model_ladder_label"] = selected_label
        st.rerun()

    ladder_rows = []
    for threshold in thresholds:
        p = _model_probability(projection, threshold, "Over")
        ladder_rows.append({"Milestone": f"{threshold}+", "Model probability": f"{p:.1%}", "Fair odds": f"{_fair_american(p):+d}"})
    st.dataframe(pd.DataFrame(ladder_rows), hide_index=True, width="stretch")

    with st.expander(f"Live sportsbook lines for {game.pitcher_name}"):
        game_key = f"{selected_date.isoformat()}:{game.game_pk}:{game.pitcher_id}"
        if st.button("Fetch live sportsbook odds", key="fetch_main_odds"):
            try:
                events, _ = get_events(api_key, selected_date)
                event = _find_event(events, game)
                if event is None:
                    st.session_state["main_odds_error"] = "Could not match this game to an Odds API event."
                    st.session_state.pop("main_odds_rows", None)
                else:
                    payload, headers = get_event_pitcher_strikeouts(api_key, str(event["id"]), "us", include_alternate=True)
                    rows = flatten_pitcher_strikeouts(payload)
                    rows = [row for row in rows if str(row.get("player", "")).strip().lower() == game.pitcher_name.strip().lower()]
                    st.session_state["main_odds_rows"] = rows
                    st.session_state["main_odds_headers"] = headers
                    st.session_state["main_odds_game_key"] = game_key
                    st.session_state.pop("main_odds_error", None)
            except OddsAPIError as exc:
                st.session_state["main_odds_error"] = str(exc)

        if st.session_state.get("main_odds_error"):
            st.error(st.session_state["main_odds_error"])
        rows = st.session_state.get("main_odds_rows", [])
        if st.session_state.get("main_odds_game_key") == game_key and rows:
            market_rows = _ladder_market_rows(rows, projection, thresholds)
            if market_rows:
                frame = pd.DataFrame(market_rows)
                display = frame[["Milestone","Book","Side","Line","Odds","Model","Fair","Implied","Edge"]].copy()
                display["Model"] = display["Model"].map(lambda x: f"{x:.1%}")
                display["Implied"] = display["Implied"].map(lambda x: f"{x:.1%}")
                display["Edge"] = display["Edge"].map(lambda x: f"{x:+.1%}")
                display["Odds"] = display["Odds"].map(lambda x: f"{int(x):+d}")
                display["Fair"] = display["Fair"].map(lambda x: f"{int(x):+d}")
                st.markdown("**LIVE MARKET → MODEL VALUE**")
                st.dataframe(display, hide_index=True, width="stretch")
                best = max(market_rows, key=lambda r: r["Edge"])
                if best["Edge"] > 0:
                    st.success(f"Best current model edge: {best['Milestone']} · {best['Book']} · {best['Edge']:+.1%} vs {int(best['Odds']):+d} market odds. Fair price {int(best['Fair']):+d}.")
                else:
                    st.info("No positive model-vs-market edge found in the currently returned alternate strikeout markets.")
            else:
                st.info("Live odds returned, but no alternate strikeout milestone could be matched to the 3+ through 10+ ladder yet.")

            frame = pd.DataFrame(rows)
            frame["label"] = frame.apply(lambda r: f"{r['bookmaker']} · {r['side']} {r['line']} @ {int(r['american_odds']):+d}", axis=1)
            choice = st.selectbox("Sportsbook line", frame.index, format_func=lambda i: frame.loc[i, "label"], key="main_odds_choice")
            selected = frame.loc[choice]
            if st.button("Use this sportsbook line in StrikeOut King", key="use_main_odds"):
                side = str(selected["side"]).title()
                line = float(selected["line"])
                st.session_state["odds_selected_side"] = side
                st.session_state["odds_selected_line"] = line
                st.session_state["odds_selected_display_line"] = f"{side.upper()} {line:g}"
                st.session_state["odds_selected_odds"] = int(selected["american_odds"])
                st.session_state["odds_selected_pitcher"] = game.pitcher_name
                st.session_state["odds_selected_date"] = selected_date.isoformat()
                st.session_state["odds_selected_event_id"] = game_key
                st.rerun()
            usage = usage_summary(st.session_state.get("main_odds_headers", {}))
            st.caption(f"Odds API usage · remaining {usage['remaining']} · used {usage['used']} · last request {usage['last_cost']}")
        elif not st.session_state.get("main_odds_error"):
            st.caption("Fetch once to see every sportsbook's current pitcher strikeout line, including alternate milestone markets. The model ladder does not consume Odds API credits.")

    st.markdown("</div>", unsafe_allow_html=True)

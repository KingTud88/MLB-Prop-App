from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

old = '''def render_reco(card,reco):
    side=reco["side"]
    cls="reco-warn" if side=="PASS" else "reco-good"
    reason_labels={"no_positive_aligned_edge":"NO POSITIVE ALIGNED EDGE","probability_conflicts_with_projection":"PROJECTION / PROBABILITY DISAGREE","projection_on_line":"PROJECTION ON LINE","model_direction":"MODEL LEAN","aligned_positive_edge":"POSITIVE ALIGNED EDGE"}
    if side=="PASS":
        meta=f"Proj {reco.get('projection_mean',float('nan')):.2f} vs {reco['line']:g} · {reason_labels.get(reco.get('reason'),'NO BET')}"
    else:
        edge=f"EDGE {reco['edge']:+.1%}" if reco["edge"] is not None else "MODEL LEAN"
        meta=f"Model {reco['model']:.1%} · {edge}"
    with card: st.markdown(f'<div class="reco-card"><div class="reco-label">{reco["label"]}</div><div class="reco-side {cls}">{side}</div><div class="reco-line">{reco["line"]:g} LINE</div><div class="reco-meta">{meta}</div></div>',unsafe_allow_html=True)
'''

new = '''def _manual_line_options(market_key):
    if "outs" in str(market_key):
        return tuple(x + 0.5 for x in range(13, 19))
    if "hits_allowed" in str(market_key):
        return tuple(x + 0.5 for x in range(3, 9))
    return tuple(x + 0.5 for x in range(2, 12))


def _american_odds_options():
    return tuple(list(range(-300, -99, 5)) + list(range(100, 305, 5)))


def manual_market_recommendation(reco, key_prefix, market_key, proj, hits_proj=None):
    if not st.session_state.get(f"{key_prefix}:enabled", False):
        return dict(reco)
    line=float(st.session_state.get(f"{key_prefix}:line", reco["line"]))
    side=str(st.session_state.get(f"{key_prefix}:side", reco.get("side") if reco.get("side") in {"OVER","UNDER"} else "OVER")).upper()
    odds=float(st.session_state.get(f"{key_prefix}:odds", -110))
    over_model=float(market_model_probability(proj, market_key, line, hits_proj))
    model_probability=over_model if side=="OVER" else 1.0-over_model
    sportsbook_implied=implied_prob(odds)
    edge=model_probability-sportsbook_implied if sportsbook_implied is not None else None
    updated=dict(reco)
    updated.update({
        "side":side,
        "line":line,
        "model":model_probability,
        "edge":edge,
        "has_market":True,
        "reason":"manual_market",
        "manual":True,
        "manual_odds":odds,
        "manual_implied":sportsbook_implied,
        "over_model":over_model,
    })
    return updated


def render_reco(card,reco,*,key_prefix=None,market_key=None,proj=None,hits_proj=None):
    effective=(manual_market_recommendation(reco,key_prefix,market_key,proj,hits_proj)
               if key_prefix and market_key and proj is not None else dict(reco))
    side=effective["side"]
    cls="reco-warn" if side=="PASS" else "reco-good"
    reason_labels={"no_positive_aligned_edge":"NO POSITIVE ALIGNED EDGE","probability_conflicts_with_projection":"PROJECTION / PROBABILITY DISAGREE","projection_on_line":"PROJECTION ON LINE","model_direction":"MODEL LEAN","aligned_positive_edge":"POSITIVE ALIGNED EDGE","manual_market":"MANUAL MARKET"}
    if side=="PASS":
        meta=f"Proj {effective.get('projection_mean',float('nan')):.2f} vs {effective['line']:g} · {reason_labels.get(effective.get('reason'),'NO BET')}"
    elif effective.get("manual"):
        edge=f"EDGE {effective['edge']:+.1%}" if effective.get("edge") is not None else "EDGE —"
        meta=f"Model {effective['model']:.1%} · {effective['manual_odds']:+.0f} · {edge}"
    else:
        edge=f"EDGE {effective['edge']:+.1%}" if effective["edge"] is not None else "MODEL LEAN"
        meta=f"Model {effective['model']:.1%} · {edge}"
    with card:
        st.markdown(f'<div class="reco-card"><div class="reco-label">{effective["label"]}</div><div class="reco-side {cls}">{side}</div><div class="reco-line">{effective["line"]:g} LINE</div><div class="reco-meta">{meta}</div></div>',unsafe_allow_html=True)
        if key_prefix and market_key and proj is not None:
            with st.expander("✍️ MANUAL LINE / ODDS", expanded=False):
                enabled=st.checkbox("Use manual market",key=f"{key_prefix}:enabled")
                lines=_manual_line_options(market_key)
                current_line=float(st.session_state.get(f"{key_prefix}:line", effective.get("line",reco["line"])))
                default_line=min(lines,key=lambda x:abs(float(x)-current_line))
                line=st.selectbox("Line",lines,index=lines.index(default_line),key=f"{key_prefix}:line",disabled=not enabled)
                default_side=effective.get("side") if effective.get("side") in {"OVER","UNDER"} else "OVER"
                side_options=("OVER","UNDER")
                side=st.selectbox("Side",side_options,index=side_options.index(default_side),key=f"{key_prefix}:side",disabled=not enabled)
                odds_options=_american_odds_options()
                current_odds=int(st.session_state.get(f"{key_prefix}:odds",-110))
                default_odds=min(odds_options,key=lambda x:abs(int(x)-current_odds))
                odds=st.selectbox("American odds",odds_options,index=odds_options.index(default_odds),key=f"{key_prefix}:odds",disabled=not enabled,format_func=lambda x:f"{int(x):+d}")
                if enabled:
                    over_model=float(market_model_probability(proj,market_key,float(line),hits_proj))
                    model_p=over_model if side=="OVER" else 1.0-over_model
                    implied_p=implied_prob(float(odds))
                    edge=model_p-implied_p if implied_p is not None else None
                    st.markdown(f"**Model:** {model_p:.1%} &nbsp; · &nbsp; **Sportsbook implied:** {implied_p:.1%} &nbsp; · &nbsp; **Edge:** {edge:+.1%}")
                    st.caption("Manual market is execution-only. It changes the displayed line/price comparison, never the baseball projection.")
'''

if old not in text:
    raise SystemExit("render_reco block not found")
text = text.replace(old, new, 1)

replacements = {
    'render_reco(c2,k_reco)': 'render_reco(c2,k_reco,key_prefix=f"manual_k:{game.key}",market_key="pitcher_strikeouts",proj=proj,hits_proj=hits_proj)',
    'render_reco(c4,out_reco)': 'render_reco(c4,out_reco,key_prefix=f"manual_outs:{game.key}",market_key="pitcher_outs",proj=proj,hits_proj=hits_proj)',
    'render_reco(h2,hit_reco)': 'render_reco(h2,hit_reco,key_prefix=f"manual_hits:{game.key}",market_key="pitcher_hits_allowed",proj=proj,hits_proj=hits_proj)',
}
for before, after in replacements.items():
    if before not in text:
        raise SystemExit(f"expected call not found: {before}")
    text = text.replace(before, after, 1)

path.write_text(text, encoding="utf-8")
print("manual market controls applied")

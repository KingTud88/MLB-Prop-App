from pathlib import Path
import re

APP = Path("streamlit_app.py")
text = APP.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 match, found {count}")
    text = text.replace(old, new, 1)


replace_once(
'''from engine.explainability_ui import (
    Explanation, apply_explainability_theme, explain_popover, leg_explanation,
    projection_metric_explanation, recommendation_explanation, static_explanation,
    ticket_explanation, top_play_explanation, weather_explanation,
)
''',
'''from engine.explainability_ui import (
    Explanation, apply_explainability_theme, explain_popover, leg_explanation,
    projection_metric_explanation, recommendation_explanation, static_explanation,
    ticket_explanation, top_play_explanation, weather_explanation,
)
from engine.card_explainability import (
    active_market_explanation,
    apply_card_info_theme,
    card_info_popover,
    market_decision_explanation,
    matchup_metric_explanation,
    pitcher_projection_explanation,
)
''',
"card explainability import",
)

replace_once(
'''apply_explainability_theme()
st.markdown("""<style>''',
'''apply_explainability_theme()
apply_card_info_theme()
st.markdown("""<style>''',
"card explainability theme",
)

marker = '''st.markdown('<div class="section-head">ACTIVE SPORTSBOOK LINES</div>',unsafe_allow_html=True)'''
if text.count(marker) != 1:
    raise SystemExit("active sportsbook section marker missing or duplicated")
context_block = r'''_explain_history=load_projection_history()
_k_mean_cals=calibrated_weights(_explain_history)
_k_mean_sim_weight=float(np.mean([cal.weight_simulation for cal in _k_mean_cals.values()])) if _k_mean_cals else .5
_lineup_source_for_explain="CONFIRMED BATTING ORDER" if lineup_context.confirmed else "ACTIVE ROSTER FALLBACK"
_common_projection_explain={
    "history_games":int(len(log.tail(35))),
    "expected_pitches":float(effective_workload_ctx.expected_pitches),
    "expected_bf":float(effective_workload_ctx.expected_bf),
    "expected_outs":float(effective_workload_ctx.expected_outs),
    "lineup_source":_lineup_source_for_explain,
    "lineup_batters":int(opponent_matchup.get("batters",0)),
    "split_pa":int(opponent_matchup.get("pa",0)),
    "pitcher_hand":pitcher_hand or "UNKNOWN",
    "data_quality":proj.quality,
    "confidence":proj.confidence,
    "draws":25000,
}
_k_projection_explain={**_common_projection_explain,
    "pitcher_k_pct":features_for_hits.get("pitcher_k_pct"),
    "matchup_k_pct":opponent_matchup.get("k_rate"),
    "park_factor":features_for_hits.get("park_factor",1.0),
    "sim_mean":proj.engine.simulation_mean,"sim_sd":proj.engine.simulation_sd,
    "math_mean":proj.engine.mathematical_mean,"math_sd":proj.engine.mathematical_sd,
    "ensemble_sd":proj.k_sd,"sim_weight":_k_mean_sim_weight,
}
_outs_projection_explain={**_common_projection_explain,
    "sim_mean":proj.outs_engine.simulation_mean,"sim_sd":proj.outs_engine.simulation_sd,
    "math_mean":proj.outs_engine.mathematical_mean,"math_sd":proj.outs_engine.mathematical_sd,
    "ensemble_sd":proj.outs_engine.ensemble_sd,
    "starts_used":proj.outs_engine.starts_used,"recent_mean_outs":proj.outs_engine.recent_mean_outs,
    "recent_sd_outs":proj.outs_engine.recent_sd_outs,"workload_outs_sd":effective_workload_ctx.outs_sd,
}
_hits_projection_explain={**_common_projection_explain,
    "sim_mean":hits_proj.simulation_mean,"sim_sd":hits_proj.simulation_sd,
    "math_mean":hits_proj.mathematical_mean,"math_sd":hits_proj.mathematical_sd,
    "ensemble_sd":hits_proj.ensemble_sd,"pitcher_hit_rate":hits_proj.pitcher_hit_rate,
    "opponent_hit_rate":hits_proj.opponent_hit_rate,"matchup_hit_rate":hits_proj.matchup_hit_rate,
    "park_factor":1.0,
}

def _decision_explain_detail(market_key,reco):
    line=_active_line(reco)
    if line is None:return {}
    cutoff=int(math.floor(float(line))+1)
    if market_key=="pitcher_strikeouts":
        sim=float(proj.engine.simulation_probabilities.get(float(cutoff),np.mean(proj.k_samples>=cutoff)))
        math_p=float(proj.engine.mathematical_probabilities.get(float(cutoff),0.0))
        cal=calibrate_blend(_explain_history,cutoff)
        aliases={"pitcher_strikeouts","pitcher_strikeouts_alternate"}
    elif market_key=="pitcher_hits_allowed":
        sim=float(hits_proj.simulation_probabilities.get(float(line),np.mean(hits_proj.simulation_samples>=cutoff)))
        math_p=float(hits_proj.mathematical_probabilities.get(float(line),0.0))
        cal=calibrate_hits_blend(_explain_history,float(line))
        aliases={"pitcher_hits_allowed","pitcher_hits_allowed_alternate"}
    else:
        sim=float(proj.outs_engine.simulation_probabilities.get(float(line),np.mean(proj.outs_samples>=cutoff)))
        math_p=float(proj.outs_engine.mathematical_probabilities.get(float(line),0.0))
        cal=calibrate_outs_blend(_explain_history,float(line))
        aliases={"pitcher_outs","pitcher_outs_alternate"}
    over_offer=best_market_offer(odds_rows,aliases,float(line),"OVER")
    under_offer=best_market_offer(odds_rows,aliases,float(line),"UNDER")
    return {
        "sim_probability":sim,"math_probability":math_p,
        "sim_weight":cal.weight_simulation,"math_weight":cal.weight_math,
        "over_price":over_offer.get("price") if over_offer else None,
        "under_price":under_offer.get("price") if under_offer else None,
    }

'''
text = text.replace(marker, context_block + marker, 1)

active_pattern = re.compile(
    r'''st\.markdown\('<div class="section-head">ACTIVE SPORTSBOOK LINES</div>',unsafe_allow_html=True\)\n'''
    r'''_line_cols=st\.columns\(3\)\n'''
    r'''for _col,_label,_line,_source in zip\(.*?'''
    r'''st\.caption\("Automated real sportsbook lines show their provider/book source\. Legacy MANUAL lines remain orange for historical clarity\. No active line means the projection still shows, but the app will not manufacture a bet lean\. Execution lines never alter the baseball projection\."\)''',
    re.S,
)
active_replacement = r'''st.markdown('<div class="section-head">ACTIVE SPORTSBOOK LINES</div>',unsafe_allow_html=True)
_line_cols=st.columns(3)
_active_specs=(
    ("STRIKEOUTS",active_k_line,active_k_source,("pitcher_strikeouts","pitcher_strikeouts_alternate")),
    ("TOTAL OUTS",active_outs_line,active_outs_source,("pitcher_outs","pitcher_outs_alternate")),
    ("HITS ALLOWED",active_hits_line,active_hits_source,("pitcher_hits_allowed","pitcher_hits_allowed_alternate")),
)
for _idx,(_col,(_label,_line,_source,_markets)) in enumerate(zip(_line_cols,_active_specs)):
    _manual=str(_source or "").upper()=="MANUAL"
    _cls="active-market-line manual" if _manual else "active-market-line"
    _value="—" if _line is None else f"{float(_line):g}"
    _source_text="MANUAL · DAILY RUN" if _manual else (str(_source) if _source else "NO ACTIVE LINE")
    with _col:
        card_info_popover(
            active_market_explanation(_label,_line,_source_text,odds_rows,market_names=_markets),
            key=f"active-market-{_idx}",
        )
        st.markdown(f'<div class="{_cls}"><div class="label">{_label}</div><div class="value">{_value}</div><div class="source">{_source_text}</div></div>',unsafe_allow_html=True)
st.caption("Automated real sportsbook lines show their provider/book source. Legacy MANUAL lines remain orange for historical clarity. No active line means the projection still shows, but the app will not manufacture a bet lean. Execution lines never alter the baseball projection.")'''
text, n = active_pattern.subn(active_replacement, text, count=1)
if n != 1:
    raise SystemExit(f"active sportsbook block replacement failed: {n}")

summary_pattern = re.compile(
    r'''st\.markdown\('<div class="section-head">PROJECTION SUMMARY</div>',unsafe_allow_html=True\).*?'''
    r'''st\.markdown\('<div class="section-head">OPPOSING BATTER BOX</div>',unsafe_allow_html=True\)''',
    re.S,
)
summary_replacement = r'''st.markdown('<div class="section-head">PROJECTION SUMMARY</div>',unsafe_allow_html=True)
alt_k_choice=best_alt_k([(int(str(row["Line"]).rstrip("+")),float(row["Probability"])) for _,row in kdf.iterrows()])
alt_k_html=(f'<div class="alt-k-badge">BEST ALT K · {alt_k_choice.milestone}+ · {alt_k_choice.probability:.0%} HIT</div>' if alt_k_choice else '<div class="alt-k-badge">BEST ALT K · NO 70%+ ALT</div>')
c1,c2,c3,c4=st.columns(4)
with c1:
    card_info_popover(
        pitcher_projection_explanation("Strikeouts",proj.mean_k,int(np.quantile(proj.k_samples,.1)),int(np.quantile(proj.k_samples,.9)),_k_projection_explain),
        key="projection-k",
    )
    st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon cc-emblem whiff" aria-hidden="true"></div><div class="metric-label">PROJECTED STRIKEOUTS</div></div><div class="metric-value">{proj.mean_k:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.k_samples,.1))}-{int(np.quantile(proj.k_samples,.9))}</span>{alt_k_html}</div>',unsafe_allow_html=True)
with c2:
    card_info_popover(market_decision_explanation(k_reco,"Strikeouts",_decision_explain_detail("pitcher_strikeouts",k_reco)),key="decision-k")
render_reco(c2,k_reco)
with c3:
    card_info_popover(
        pitcher_projection_explanation("Total Outs",proj.mean_outs,int(np.quantile(proj.outs_samples,.1)),int(np.quantile(proj.outs_samples,.9)),_outs_projection_explain),
        key="projection-outs",
    )
    st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon cc-emblem glove" aria-hidden="true"></div><div class="metric-label">PROJECTED OUTS</div></div><div class="metric-value">{proj.mean_outs:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.outs_samples,.1))}-{int(np.quantile(proj.outs_samples,.9))}</span></div>',unsafe_allow_html=True)
with c4:
    card_info_popover(market_decision_explanation(out_reco,"Total Outs",_decision_explain_detail("pitcher_outs",out_reco)),key="decision-outs")
render_reco(c4,out_reco)
h1,h2,h3=st.columns([1,1,2])
with h1:
    card_info_popover(
        pitcher_projection_explanation("Hits Allowed",hits_proj.ensemble_mean,int(np.quantile(hits_proj.simulation_samples,.1)),int(np.quantile(hits_proj.simulation_samples,.9)),_hits_projection_explain),
        key="projection-hits",
    )
    st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon cc-emblem contact" aria-hidden="true"></div><div class="metric-label">PROJECTED HITS ALLOWED</div></div><div class="metric-value">{hits_proj.ensemble_mean:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(hits_proj.simulation_samples,.1))}-{int(np.quantile(hits_proj.simulation_samples,.9))}</span></div>',unsafe_allow_html=True)
with h2:
    card_info_popover(market_decision_explanation(hit_reco,"Hits Allowed",_decision_explain_detail("pitcher_hits_allowed",hit_reco)),key="decision-hits")
render_reco(h2,hit_reco)
with h3:
    card_info_popover(
        weather_explanation(level=weather_risk.level,precip_probability=weather_risk.precip_probability,precipitation_mm=weather_risk.precipitation_mm,summary=weather_risk.summary,roof_type=getattr(weather_risk,"roof_type","")),
        key="weather",
    )
    st.markdown(
        f'<div class="game-weather-card {_weather_class}"><div class="game-weather-head"><div><div class="game-weather-title">GAME WEATHER · DELAY RISK</div><div class="game-weather-risk">{_weather_label}</div><div class="game-weather-action">{_weather_action}</div></div><div class="game-weather-icon" aria-hidden="true">{_weather_icon}</div></div><div class="game-weather-grid"><div class="game-weather-stat"><span>Precip chance</span><strong>{_weather_prob}</strong></div><div class="game-weather-stat"><span>Peak precip</span><strong>{_weather_peak}</strong></div></div><div class="game-weather-reason">{_weather_summary}</div><div class="game-weather-note">Game window: 2h before first pitch → 4h after · Roof-capable parks suppress false exterior-rain avoid signals; verify retractable-roof status near first pitch. Weather does not modify the projection.</div></div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-head">OPPOSING BATTER BOX</div>',unsafe_allow_html=True)'''
text, n = summary_pattern.subn(summary_replacement, text, count=1)
if n != 1:
    raise SystemExit(f"projection summary replacement failed: {n}")

batter_old = '''    b1,b2,b3,b4,b5=st.columns(5)
    b1.metric("Matchup K%",f"{float(opponent_matchup['k_rate']):.1%}")
    b2.metric("Matchup H/PA",f"{float(opponent_matchup.get('hit_rate',.235)):.1%}")
    b3.metric("Split PA",int(opponent_matchup["pa"]))
    b4.metric("HIGH K hitters",int(opponent_matchup["high"]))
    b5.metric("ELEVATED K hitters",int(opponent_matchup["elevated"]))
    explain_popover(static_explanation("opposing_batters"),label="ⓘ EXPLAIN BATTER MATCHUP")
'''
batter_new = '''    b1,b2,b3,b4,b5=st.columns(5)
    with b1:
        card_info_popover(matchup_metric_explanation("k_rate",opponent_matchup,lineup_source=lineup_label,pitcher_hand=pitcher_hand),key="matchup-k-rate")
        st.metric("Matchup K%",f"{float(opponent_matchup['k_rate']):.1%}")
    with b2:
        card_info_popover(matchup_metric_explanation("hit_rate",opponent_matchup,lineup_source=lineup_label,pitcher_hand=pitcher_hand),key="matchup-hit-rate")
        st.metric("Matchup H/PA",f"{float(opponent_matchup.get('hit_rate',.235)):.1%}")
    with b3:
        card_info_popover(matchup_metric_explanation("pa",opponent_matchup,lineup_source=lineup_label,pitcher_hand=pitcher_hand),key="matchup-split-pa")
        st.metric("Split PA",int(opponent_matchup["pa"]))
    with b4:
        card_info_popover(matchup_metric_explanation("high",opponent_matchup,lineup_source=lineup_label,pitcher_hand=pitcher_hand),key="matchup-high-k")
        st.metric("HIGH K hitters",int(opponent_matchup["high"]))
    with b5:
        card_info_popover(matchup_metric_explanation("elevated",opponent_matchup,lineup_source=lineup_label,pitcher_hand=pitcher_hand),key="matchup-elevated-k")
        st.metric("ELEVATED K hitters",int(opponent_matchup["elevated"]))
'''
replace_once(batter_old, batter_new, "batter metric explainers")

replace_once(
'''action_panel=st.container(border=True,key="cc_bet_action_panel")
action_panel.caption("Quick-add uses the real active line shown above. A sportsbook price may remain unpriced, but the app will not quick-add a fabricated/default market line.")
with action_panel:
    explain_popover(static_explanation("projection_actions"),label="ⓘ EXPLAIN BET ACTIONS")
''',
'''action_panel=st.container(border=True,key="cc_bet_action_panel")
with action_panel:
    card_info_popover(static_explanation("projection_actions"),key="bet-actions")
action_panel.caption("Quick-add uses the real active line shown above. A sportsbook price may remain unpriced, but the app will not quick-add a fabricated/default market line.")
''',
"bet action info icon",
)

why_pattern = re.compile(
    r'''with st\.expander\(f"🔎 Why this projection\? · \{game\.pitcher_name\}", expanded=False\):.*?\nmarket_command_row=st\.container\(border=True,key="cc_market_command_row"\)''',
    re.S,
)
text, n = why_pattern.subn('market_command_row=st.container(border=True,key="cc_market_command_row")', text, count=1)
if n != 1:
    raise SystemExit(f"old why projection expander removal failed: {n}")

text = text.replace(
    'else: st.info("Live market data will populate here when the Odds API returns the pitcher props.")',
    'else: st.info("Live market data will populate here when the saved SportsGameOdds snapshot contains an eligible pregame pitcher prop pair.")',
)

obsolete_labels = (
    "ⓘ EXPLAIN ACTIVE LINES",
    "ⓘ WHY THIS K PROJECTION?",
    "ⓘ WHY THIS K DECISION?",
    "ⓘ WHY THIS OUTS PROJECTION?",
    "ⓘ WHY THIS OUTS DECISION?",
    "ⓘ WHY THIS HITS PROJECTION?",
    "ⓘ WHY THIS HITS DECISION?",
    "ⓘ WHY THIS WEATHER STATUS?",
    "ⓘ EXPLAIN BATTER MATCHUP",
    "ⓘ EXPLAIN BET ACTIONS",
)
for label in obsolete_labels:
    if label in text:
        raise SystemExit(f"obsolete Projection-page explainer survived: {label}")

APP.write_text(text, encoding="utf-8")

Path("tests/test_card_level_explainability.py").write_text(r'''from engine.card_explainability import (
    active_market_explanation,
    market_decision_explanation,
    matchup_metric_explanation,
    pitcher_projection_explanation,
)
from pathlib import Path


def test_projection_page_uses_compact_card_info_controls():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "apply_card_info_theme()" in source
    assert "card_info_popover(" in source
    assert "matchup_metric_explanation(\"k_rate\"" in source
    assert "matchup_metric_explanation(\"hit_rate\"" in source
    assert "matchup_metric_explanation(\"pa\"" in source
    assert "matchup_metric_explanation(\"high\"" in source
    assert "matchup_metric_explanation(\"elevated\"" in source
    for old in (
        "ⓘ EXPLAIN ACTIVE LINES","ⓘ WHY THIS K PROJECTION?","ⓘ WHY THIS K DECISION?",
        "ⓘ WHY THIS OUTS PROJECTION?","ⓘ WHY THIS OUTS DECISION?","ⓘ WHY THIS HITS PROJECTION?",
        "ⓘ WHY THIS HITS DECISION?","ⓘ WHY THIS WEATHER STATUS?","ⓘ EXPLAIN BATTER MATCHUP",
        "ⓘ EXPLAIN BET ACTIONS","🔎 Why this projection?",
    ):
        assert old not in source


def test_active_market_detail_reports_real_pair_and_prices():
    offers = [
        {"market":"pitcher_strikeouts","name":"Over","point":5.5,"price":-120,"book":"ESPN BET","fetched_at_utc":"2026-08-19T21:00:00+00:00"},
        {"market":"pitcher_strikeouts","name":"Under","point":5.5,"price":-110,"book":"ESPN BET","fetched_at_utc":"2026-08-19T21:00:00+00:00"},
    ]
    exp = active_market_explanation("STRIKEOUTS",5.5,"SPORTSGAMEODDS · ESPN BET",offers,market_names=("pitcher_strikeouts",))
    joined = " | ".join(exp.current)
    assert "5.5" in joined
    assert "ESPN BET" in joined
    assert "-120" in joined
    assert "-110" in joined
    assert "complete real pregame Over/Under pair" in exp.decision


def test_projection_detail_contains_models_workload_and_matchup():
    context = {
        "history_games":25,"expected_pitches":92.5,"expected_bf":23.4,"expected_outs":16.2,
        "lineup_source":"CONFIRMED BATTING ORDER","lineup_batters":9,"split_pa":1800,"pitcher_hand":"R",
        "data_quality":79,"confidence":"High","draws":25000,"pitcher_k_pct":.26,"matchup_k_pct":.245,
        "park_factor":1.03,"sim_mean":5.4,"sim_sd":2.0,"math_mean":5.1,"math_sd":2.1,
        "ensemble_sd":2.05,"sim_weight":.55,
    }
    exp = pitcher_projection_explanation("Strikeouts",5.25,3,8,context)
    text = " | ".join(exp.inputs + exp.current)
    assert "25 starts" in text
    assert "23.4 BF" in text
    assert "CONFIRMED BATTING ORDER" in text
    assert "SIM path" in text
    assert "MATH path" in text
    assert "25,000" in text


def test_matchup_k_detail_describes_exact_confirmed_lineup_formula():
    exp = matchup_metric_explanation(
        "k_rate",{"confirmed":True,"batters":9,"pa":1600,"k_rate":.247,"hit_rate":.231,"high":2,"elevated":3},
        lineup_source="CONFIRMED BATTING ORDER",pitcher_hand="R",
    )
    assert "60-PA prior" in exp.method
    assert "22.4% league K baseline" in exp.method
    assert "24.7%" in " | ".join(exp.current)


def test_decision_detail_exposes_path_probabilities_calibration_and_price_edge():
    reco = {"side":"OVER","line":5.5,"projection_mean":6.2,"model":.61,"edge":.07,"reason":"aligned_positive_edge","active_line_source":"SPORTSGAMEODDS · ESPN BET"}
    exp = market_decision_explanation(reco,"Strikeouts",{"sim_probability":.64,"math_probability":.58,"sim_weight":.5,"math_weight":.5,"over_price":-115,"under_price":-105})
    text = " | ".join(exp.current)
    assert "SIM 64.0%" in text
    assert "MATH 58.0%" in text
    assert "OVER -115" in text
    assert "+7.0%" in text
    assert "positive-edge rule" in exp.decision
''', encoding="utf-8")

print("card explainability refactor applied")

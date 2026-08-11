from pathlib import Path
import re

# 1) Strikeout half-lines must use the calibration weight of the winning integer milestone.
path = Path("engine/projection_engine.py")
text = path.read_text(encoding="utf-8")
old = "weight=learned_weights.get(int(math.floor(line)),mean_weight)"
new = "weight=learned_weights.get(self._line_cutoff(line),mean_weight)"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("projection engine calibration-weight anchor not found")
path.write_text(text, encoding="utf-8")

# 2) Main Projection page: aligned lean policy + calibrated sportsbook-line probabilities.
path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

import_anchor = "from engine.outs_calibration import calibrate_outs_blend\n"
if "from engine.bet_lean import aligned_bet_lean" not in text:
    if import_anchor not in text:
        raise SystemExit("main import anchor missing")
    text = text.replace(import_anchor, import_anchor + "from engine.bet_lean import aligned_bet_lean\n", 1)

new_market_reco = '''def market_recommendation(proj,odds_rows,market_key,default_line,kind):
    base_key=market_key.replace("_alternate",""); allowed={market_key,base_key}; rows=[r for r in odds_rows if r.get("market") in allowed and r.get("point") is not None]
    line=default_line; over_price=under_price=None
    if rows:
        points=[]
        for r in rows:
            try: points.append(float(r["point"]))
            except Exception: pass
        if points: line=min(points,key=lambda x:abs(x-default_line))
        chosen=[r for r in rows if abs(float(r.get("point"))-line)<1e-9]
        for r in chosen:
            name=str(r.get("name","")).lower()
            if name=="over": over_price=r.get("price")
            elif name=="under": under_price=r.get("price")
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

'''
text, n = re.subn(r"def market_recommendation\(proj,odds_rows,market_key,default_line,kind\):[\s\S]*?\ndef render_reco\(card,reco\):\n", new_market_reco + "def render_reco(card,reco):\n", text, count=1)
if n != 1:
    raise SystemExit("market_recommendation replacement failed")

old_render = '''    side=reco["side"]; cls="reco-good" if side=="OVER" and reco["model"]>=.5 or side=="UNDER" and reco["model"]<.5 else "reco-neutral"; edge=f"EDGE {reco['edge']:+.1%}" if reco["edge"] is not None else "MODEL LEAN"; meta=f"Model {reco['model']:.1%} · {edge}"
    with card: st.markdown(f'<div class="reco-card"><div class="reco-label">{reco["label"]}</div><div class="reco-side {cls}">{side}</div><div class="reco-line">{reco["line"]:g} LINE</div><div class="reco-meta">{meta}</div></div>',unsafe_allow_html=True)
'''
new_render = '''    side=reco["side"]
    cls="reco-warn" if side=="PASS" else "reco-good"
    reason_labels={"no_positive_aligned_edge":"NO POSITIVE ALIGNED EDGE","probability_conflicts_with_projection":"PROJECTION / PROBABILITY DISAGREE","projection_on_line":"PROJECTION ON LINE","model_direction":"MODEL LEAN","aligned_positive_edge":"POSITIVE ALIGNED EDGE"}
    if side=="PASS":
        meta=f"Proj {reco.get('projection_mean',float('nan')):.2f} vs {reco['line']:g} · {reason_labels.get(reco.get('reason'),'NO BET')}"
    else:
        edge=f"EDGE {reco['edge']:+.1%}" if reco["edge"] is not None else "MODEL LEAN"
        meta=f"Model {reco['model']:.1%} · {edge}"
    with card: st.markdown(f'<div class="reco-card"><div class="reco-label">{reco["label"]}</div><div class="reco-side {cls}">{side}</div><div class="reco-line">{reco["line"]:g} LINE</div><div class="reco-meta">{meta}</div></div>',unsafe_allow_html=True)
'''
if old_render not in text:
    raise SystemExit("render_reco body anchor missing")
text = text.replace(old_render, new_render, 1)

old_hit = '''hit_over=float(hits_proj.over_probabilities.get(float(hit_line),0.5))
hit_over_price=next((r.get("price") for r in hit_rows if abs(float(r.get("point"))-hit_line)<1e-9 and str(r.get("name","")).lower()=="over"),None)
hit_under_price=next((r.get("price") for r in hit_rows if abs(float(r.get("point"))-hit_line)<1e-9 and str(r.get("name","")).lower()=="under"),None)
hit_over_edge=hit_over-(implied_prob(hit_over_price) or 0) if hit_over_price is not None else None
hit_under_edge=(1-hit_over)-(implied_prob(hit_under_price) or 0) if hit_under_price is not None else None
if (hit_over_edge if hit_over_edge is not None else -999) >= (hit_under_edge if hit_under_edge is not None else -999): hit_side="OVER"; hit_edge=hit_over_edge; hit_model=hit_over
else: hit_side="UNDER"; hit_edge=hit_under_edge; hit_model=1-hit_over
hit_reco={"side":hit_side,"line":hit_line,"model":hit_model,"edge":hit_edge,"confidence":abs(hit_model-.5)*2,"has_market":bool(hit_rows),"label":"HITS ALLOWED BET LEAN"}
'''
new_hit = '''hit_sim=float(hits_proj.simulation_probabilities.get(float(hit_line),0.0)); hit_math=float(hits_proj.mathematical_probabilities.get(float(hit_line),0.0))
hit_cal=calibrate_hits_blend(load_projection_history(),float(hit_line)); hit_over=hit_cal.weight_simulation*hit_sim+hit_cal.weight_math*hit_math
hit_over_price=next((r.get("price") for r in hit_rows if abs(float(r.get("point"))-hit_line)<1e-9 and str(r.get("name","")).lower()=="over"),None)
hit_under_price=next((r.get("price") for r in hit_rows if abs(float(r.get("point"))-hit_line)<1e-9 and str(r.get("name","")).lower()=="under"),None)
hit_decision=aligned_bet_lean(hits_proj.ensemble_mean,hit_line,hit_over,over_implied=implied_prob(hit_over_price) if hit_over_price is not None else None,under_implied=implied_prob(hit_under_price) if hit_under_price is not None else None,has_market=bool(hit_rows))
hit_reco={"side":hit_decision.side,"line":hit_line,"model":hit_decision.model_probability,"edge":hit_decision.edge,"confidence":abs(hit_decision.model_probability-.5)*2,"has_market":bool(hit_rows),"label":"HITS ALLOWED BET LEAN","reason":hit_decision.reason,"projection_mean":hits_proj.ensemble_mean,"over_model":hit_over}
'''
if old_hit not in text:
    raise SystemExit("hits lean anchor missing")
text = text.replace(old_hit, new_hit, 1)

old_market_model = '''def market_model_probability(proj,market,line,hits_proj=None):
    cutoff=int(math.floor(float(line))+1)
    if market in ("pitcher_strikeouts","pitcher_strikeouts_alternate"):
        sim=proj.engine.simulation_probabilities.get(float(line),float(np.mean(proj.k_samples>=cutoff))); math_p=proj.engine.mathematical_probabilities.get(float(line),0.0); return .5*sim+.5*math_p
    if market in ("pitcher_hits_allowed","pitcher_hits_allowed_alternate") and hits_proj is not None:
        return float(hits_proj.over_probabilities.get(float(line),np.mean(hits_proj.simulation_samples>=cutoff)))
    return float(np.mean(proj.outs_samples>=cutoff))
'''
new_market_model = '''def market_model_probability(proj,market,line,hits_proj=None):
    line=float(line); cutoff=int(math.floor(line)+1); history=load_projection_history()
    if market in ("pitcher_strikeouts","pitcher_strikeouts_alternate"):
        sim=float(proj.engine.simulation_probabilities.get(float(cutoff),np.mean(proj.k_samples>=cutoff))); math_p=float(proj.engine.mathematical_probabilities.get(float(cutoff),0.0)); cal=calibrate_blend(history,cutoff); return cal.weight_simulation*sim+cal.weight_math*math_p
    if market in ("pitcher_hits_allowed","pitcher_hits_allowed_alternate") and hits_proj is not None:
        sim=float(hits_proj.simulation_probabilities.get(line,np.mean(hits_proj.simulation_samples>=cutoff))); math_p=float(hits_proj.mathematical_probabilities.get(line,0.0)); cal=calibrate_hits_blend(history,line); return cal.weight_simulation*sim+cal.weight_math*math_p
    sim=float(proj.outs_engine.simulation_probabilities.get(line,np.mean(proj.outs_samples>=cutoff))); math_p=float(proj.outs_engine.mathematical_probabilities.get(line,0.0)); cal=calibrate_outs_blend(history,line); return cal.weight_simulation*sim+cal.weight_math*math_p
'''
if old_market_model not in text:
    raise SystemExit("market_model_probability anchor missing")
text = text.replace(old_market_model, new_market_model, 1)
path.write_text(text, encoding="utf-8")

# 3) Top Plays: never rank a side that contradicts its frozen point projection.
path = Path("pages/6_Top_Plays.py")
text = path.read_text(encoding="utf-8")
import_anchor = "from engine.outs_calibration import calibrate_outs_blend, outs_calibration_report\n"
if "from engine.bet_lean import projection_side" not in text:
    if import_anchor not in text:
        raise SystemExit("Top Plays import anchor missing")
    text = text.replace(import_anchor, import_anchor + "from engine.bet_lean import projection_side\n", 1)

old_candidates = '''        candidates = [
            ("OVER", over_model, fair_over, prices["over"]),
            ("UNDER", 1.0 - over_model, fair_under, prices["under"]),
        ]
'''
new_candidates = '''        if market.startswith("pitcher_strikeouts"):
            projection_mean = numeric(row.get("projection"))
        elif market.startswith("pitcher_hits_allowed"):
            projection_mean = numeric(row.get("hits_projection"))
        else:
            projection_mean = numeric(row.get("outs_projection"))
        if projection_mean is None:
            continue
        direction = projection_side(projection_mean, point)
        if direction == "OVER":
            candidates = [("OVER", over_model, fair_over, prices["over"])]
        elif direction == "UNDER":
            candidates = [("UNDER", 1.0 - over_model, fair_under, prices["under"])]
        else:
            continue
'''
if old_candidates not in text:
    raise SystemExit("Top Plays candidate anchor missing")
text = text.replace(old_candidates, new_candidates, 1)
path.write_text(text, encoding="utf-8")

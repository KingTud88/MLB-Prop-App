from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "from engine.projection_engine import ProjectionEngine, ProjectionResult\n",
        "from engine.projection_engine import ProjectionEngine, ProjectionResult\nfrom engine.hits_allowed import project_hits_allowed\n",
    ),
    (
        '"k":float(s.get("strikeOuts",0) or 0),"pitches":float(s.get("numberOfPitches",0) or 0),',
        '"k":float(s.get("strikeOuts",0) or 0),"hits":float(s.get("hits",0) or 0),"pitches":float(s.get("numberOfPitches",0) or 0),',
    ),
    (
        '"markets":"pitcher_strikeouts,pitcher_strikeouts_alternate,pitcher_outs,pitcher_outs_alternate"',
        '"markets":"pitcher_strikeouts,pitcher_strikeouts_alternate,pitcher_outs,pitcher_outs_alternate,pitcher_hits_allowed,pitcher_hits_allowed_alternate"',
    ),
    (
        'allowed={"pitcher_strikeouts","pitcher_strikeouts_alternate","pitcher_outs","pitcher_outs_alternate"}',
        'allowed={"pitcher_strikeouts","pitcher_strikeouts_alternate","pitcher_outs","pitcher_outs_alternate","pitcher_hits_allowed","pitcher_hits_allowed_alternate"}',
    ),
    (
        'nav=st.radio("Navigation",["Projection","Distribution","Form & Workload","Model Card","Bet Tracker","Projection History","Daily Projection Run"],label_visibility="collapsed")\n    if nav == "Daily Projection Run":\n        st.switch_page("pages/5_Daily_Projection_Run.py")',
        'nav=st.radio("Navigation",["Projection","Distribution","Form & Workload","Model Card","Bet Tracker","Projection History","Daily Projection Run","Top Plays"],label_visibility="collapsed")\n    if nav == "Daily Projection Run":\n        st.switch_page("pages/5_Daily_Projection_Run.py")\n    if nav == "Projection History":\n        st.switch_page("pages/4_Projection_History.py")\n    if nav == "Top Plays":\n        st.switch_page("pages/6_Top_Plays.py")',
    ),
    (
        'proj=calculate_projection(log,game,25000); kdf=ladder(proj,10)\n',
        'proj=calculate_projection(log,game,25000); kdf=ladder(proj,10)\nfeatures_for_hits=build_engine_features(log,game)\nhits_seed=int(hashlib.sha256(f"hits|{game.key}|{game.game_time}|{APP_VERSION}".encode()).hexdigest()[:8],16)\nhits_proj=project_hits_allowed(log,expected_bf=features_for_hits["expected_bf"],seed=hits_seed,draws=25000,lines=(3.5,4.5,5.5,6.5,7.5,8.5))\n',
    ),
    (
        'out_reco=market_recommendation(proj,odds_rows,"pitcher_outs_alternate",15.5,"outs"); out_reco["label"]="TOTAL OUTS BET LEAN"\n',
        'out_reco=market_recommendation(proj,odds_rows,"pitcher_outs_alternate",15.5,"outs"); out_reco["label"]="TOTAL OUTS BET LEAN"\nhit_rows=[r for r in odds_rows if r.get("market") in {"pitcher_hits_allowed","pitcher_hits_allowed_alternate"} and r.get("point") is not None]\nhit_line=min([float(r["point"]) for r in hit_rows],key=lambda x:abs(x-5.5)) if hit_rows else 5.5\nhit_over=float(hits_proj.over_probabilities.get(float(hit_line),0.5))\nhit_over_price=next((r.get("price") for r in hit_rows if abs(float(r.get("point"))-hit_line)<1e-9 and str(r.get("name","")).lower()=="over"),None)\nhit_under_price=next((r.get("price") for r in hit_rows if abs(float(r.get("point"))-hit_line)<1e-9 and str(r.get("name","")).lower()=="under"),None)\nhit_over_edge=hit_over-(implied_prob(hit_over_price) or 0) if hit_over_price is not None else None\nhit_under_edge=(1-hit_over)-(implied_prob(hit_under_price) or 0) if hit_under_price is not None else None\nif (hit_over_edge if hit_over_edge is not None else -999) >= (hit_under_edge if hit_under_edge is not None else -999): hit_side="OVER"; hit_edge=hit_over_edge; hit_model=hit_over\nelse: hit_side="UNDER"; hit_edge=hit_under_edge; hit_model=1-hit_over\nhit_reco={"side":hit_side,"line":hit_line,"model":hit_model,"edge":hit_edge,"confidence":abs(hit_model-.5)*2,"has_market":bool(hit_rows),"label":"HITS ALLOWED BET LEAN"}\n',
    ),
    (
        'def market_model_probability(proj,market,line):\n',
        'def market_model_probability(proj,market,line,hits_proj=None):\n',
    ),
    (
        '    if market in ("pitcher_strikeouts","pitcher_strikeouts_alternate"):\n        sim=proj.engine.simulation_probabilities.get(float(line),float(np.mean(proj.k_samples>=cutoff))); math_p=proj.engine.mathematical_probabilities.get(float(line),0.0); return .5*sim+.5*math_p\n    return float(np.mean(proj.outs_samples>=cutoff))',
        '    if market in ("pitcher_strikeouts","pitcher_strikeouts_alternate"):\n        sim=proj.engine.simulation_probabilities.get(float(line),float(np.mean(proj.k_samples>=cutoff))); math_p=proj.engine.mathematical_probabilities.get(float(line),0.0); return .5*sim+.5*math_p\n    if market in ("pitcher_hits_allowed","pitcher_hits_allowed_alternate") and hits_proj is not None:\n        return float(hits_proj.over_probabilities.get(float(line),np.mean(hits_proj.simulation_samples>=cutoff)))\n    return float(np.mean(proj.outs_samples>=cutoff))',
    ),
    (
        'def build_market_table(proj,odds_rows):\n',
        'def build_market_table(proj,odds_rows,hits_proj=None):\n',
    ),
    (
        'model=market_model_probability(proj,market,line);',
        'model=market_model_probability(proj,market,line,hits_proj);',
    ),
    (
        'rows.append({"Market":"K" if "strikeouts" in market else "OUTS",',
        'rows.append({"Market":"K" if "strikeouts" in market else "HITS" if "hits_allowed" in market else "OUTS",',
    ),
    (
        'c1,c2,c3,c4=st.columns(4)\nwith c1: st.markdown(f\'<div class="metric-card"><div class="metric-label">PROJECTED STRIKEOUTS</div><div class="metric-value">{proj.mean_k:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.k_samples,.1))}-{int(np.quantile(proj.k_samples,.9))}</span></div>\',unsafe_allow_html=True)\nrender_reco(c2,k_reco)\nwith c3: st.markdown(f\'<div class="metric-card"><div class="metric-label">PROJECTED OUTS</div><div class="metric-value">{proj.mean_outs:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.outs_samples,.1))}-{int(np.quantile(proj.outs_samples,.9))}</span></div>\',unsafe_allow_html=True)\nrender_reco(c4,out_reco)\n',
        'c1,c2,c3,c4=st.columns(4)\nwith c1: st.markdown(f\'<div class="metric-card"><div class="metric-label">PROJECTED STRIKEOUTS</div><div class="metric-value">{proj.mean_k:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.k_samples,.1))}-{int(np.quantile(proj.k_samples,.9))}</span></div>\',unsafe_allow_html=True)\nrender_reco(c2,k_reco)\nwith c3: st.markdown(f\'<div class="metric-card"><div class="metric-label">PROJECTED OUTS</div><div class="metric-value">{proj.mean_outs:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.outs_samples,.1))}-{int(np.quantile(proj.outs_samples,.9))}</span></div>\',unsafe_allow_html=True)\nrender_reco(c4,out_reco)\nh1,h2=st.columns(2)\nwith h1: st.markdown(f\'<div class="metric-card"><div class="metric-label">PROJECTED HITS ALLOWED</div><div class="metric-value">{hits_proj.ensemble_mean:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(hits_proj.simulation_samples,.1))}-{int(np.quantile(hits_proj.simulation_samples,.9))}</span></div>\',unsafe_allow_html=True)\nrender_reco(h2,hit_reco)\n',
    ),
    (
        'market_df=build_market_table(proj,odds_rows)',
        'market_df=build_market_table(proj,odds_rows,hits_proj)',
    ),
    (
        'Live sportsbook prices are shown for both strikeout and total-outs markets.',
        'Live sportsbook prices are shown for strikeouts, total outs, and hits allowed markets.',
    ),
]

for old, new in replacements:
    if old not in text:
        raise SystemExit(f"Expected patch target not found: {old[:120]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Hits allowed UI patch applied.")

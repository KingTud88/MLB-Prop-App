from pathlib import Path

p = Path("streamlit_app.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
    "import streamlit as st\n",
    "import streamlit as st\nfrom engine.calibration import calibrate_blend, calibration_summary\nfrom engine.projection_engine import ProjectionEngine, ProjectionResult\n",
    1,
)
s = s.replace('APP_VERSION="3.0.1"', 'APP_VERSION="3.1.0"', 1)

old_projection = '''def calculate_projection(log,game,simulations):
    starts=log.tail(35).copy(); bf=weighted(starts.bf,5,22); outs=weighted(starts.outs,5,16); pitches=weighted(starts.pitches,5,88); total_bf=float(starts.bf.sum())
    raw=float(starts.k.sum()/max(total_bf,1)); kr=shrink(raw,total_bf); park=PARK_K_FACTOR.get(game.venue,1); workload=float(np.clip(92/max(pitches,75),.78,1.12))
    mean_bf=bf*workload; mean_outs=float(np.clip(outs*workload,3,24)); mean_k=float(np.clip(.78*(mean_bf*kr*park)+.22*weighted(starts.k,5,5),.5,13.5))
    var=float(starts.k.var(ddof=1)) if len(starts)>2 else mean_k*1.25; disp=max((var-mean_k)/max(mean_k**2,.1),.08); kp=nb_pmf(mean_k,disp)
    osd=float(np.clip(starts.outs.std(ddof=1) if len(starts)>2 else 4,2.5,6.5)); op=norm_probs(mean_outs,osd)
    seed=int(hashlib.sha256(f"{game.key}|{date.today()}|{APP_VERSION}".encode()).hexdigest()[:8],16); rng=np.random.default_rng(seed)
    ks=rng.choice(np.arange(len(kp)),simulations,p=kp); os=rng.choice(np.arange(len(op)),simulations,p=op); q=min(100,35+len(starts)*2+(15 if total_bf>=250 else 0)); conf="High" if q>=85 else "Medium" if q>=65 else "Low"
    factors=[("Opponent strikeout profile",0),("Recent workload / pitch limit",workload-1),("Park",park-1),("Umpire",0),("Weather",0),("Rest",0)]
    return Projection(mean_k,mean_outs,math.sqrt(max(var,.1)),osd,kp,op,ks,os,conf,q,factors)
'''

new_projection = '''def load_projection_history():
    try:
        return pd.read_csv(APP_DIR / "data" / "projection_log.csv")
    except Exception:
        return pd.DataFrame()


def calibrated_weights(history):
    return {line: calibrate_blend(history, line) for line in range(3, 11)}


def build_engine_features(log, game):
    starts=log.tail(35).copy()
    total_bf=float(starts.bf.sum())
    raw_k=float(starts.k.sum()/max(total_bf,1))
    pitcher_k=float(np.clip(shrink(raw_k,total_bf),.05,.45))
    bf=weighted(starts.bf,5,22)
    pitches=weighted(starts.pitches,5,88)
    workload=float(np.clip(92/max(pitches,75),.78,1.12))
    return {
        "pitcher_k_pct":pitcher_k,
        "opponent_k_pct":.224,
        "handedness_factor":1.0,
        "arsenal_factor":1.0,
        "park_factor":PARK_K_FACTOR.get(game.venue,1.0),
        "umpire_factor":1.0,
        "weather_factor":1.0,
        "expected_bf":float(np.clip(bf*workload,10,35)),
        "bf_sd":float(np.clip(starts.bf.std(ddof=1) if len(starts)>2 else 3.5,1,7)),
        "rest_factor":1.0,
        "historical_k_sd":float(np.clip(starts.k.std(ddof=1) if len(starts)>2 else 2.0,.75,4.5)),
        "historical_games":int(len(starts)),
        "lineup_batters":0,
        "arsenal_sample_size":0,
        "weather_available":0,
        "umpire_available":0,
    }


def calculate_projection(log,game,simulations):
    history=load_projection_history()
    cal=calibrated_weights(history)
    seed=int(hashlib.sha256(f"{game.key}|{game.game_time}|{APP_VERSION}".encode()).hexdigest()[:8],16)
    features=build_engine_features(log,game)
    engine=ProjectionEngine(simulation_weight=.5,seed=seed)
    result=engine.project(features,draws=simulations,lines=tuple(float(x) for x in range(3,11)))
    global_w=float(np.mean([r.weight_simulation for r in cal.values()])) if cal else .5
    mean_k=global_w*result.simulation_mean+(1-global_w)*result.mathematical_mean
    mean_outs=weighted(log.tail(35).outs,5,16)
    osd=float(np.clip(log.tail(35).outs.std(ddof=1) if len(log)>2 else 4,2.5,6.5))
    outs_seed=int(hashlib.sha256(f"outs|{game.key}|{APP_VERSION}".encode()).hexdigest()[:8],16)
    outs_rng=np.random.default_rng(outs_seed)
    outs_samples=np.clip(np.rint(outs_rng.normal(mean_outs,osd,simulations)),0,27).astype(int)
    quality=int(round(result.data_quality))
    confidence="High" if result.confidence>=.75 else "Medium" if result.confidence>=.60 else "Low"
    return Projection(mean_k,mean_outs,result.ensemble_sd,osd,result.mathematical_pmf,result.mathematical_pmf,result.simulation_samples,outs_samples,confidence,quality,[(n,v) for n,v,_ in result.drivers],result)
'''

if old_projection not in s:
    raise SystemExit("calculate_projection block not found")
s=s.replace(old_projection,new_projection,1)

old_ladder='''def ladder(proj,max_line=10):
    rows=[]
    for line in range(3,max_line+1):
        sim=sim_prob(proj.k_samples,line); analytic=math_prob_from_pmf(proj.k_probs,line); blended=.5*sim+.5*analytic; rows.append({"Line":f"{line}+","Probability":blended,"Fair Odds":american(blended),"Simulation":sim,"Math":analytic})
    return pd.DataFrame(rows)
'''
new_ladder='''def ladder(proj,max_line=10):
    history=load_projection_history()
    rows=[]
    for line in range(3,max_line+1):
        cal=calibrate_blend(history,line)
        sim=proj.engine.simulation_probabilities.get(float(line),0.0)
        analytic=proj.engine.mathematical_probabilities.get(float(line),0.0)
        w=cal.weight_simulation
        blended=w*sim+(1-w)*analytic
        rows.append({"Line":f"{line}+","Probability":blended,"Fair Odds":american(blended),"Simulation":sim,"Math":analytic,"Sim Weight":w})
    return pd.DataFrame(rows)
'''
if old_ladder not in s:
    raise SystemExit("ladder block not found")
s=s.replace(old_ladder,new_ladder,1)

# Make the pitcher lock actually freeze the selector/search.
s=s.replace(
    'search=st.text_input("Search pitcher...",placeholder="Search pitcher...",label_visibility="collapsed"); st.caption("Search and select a pitcher to lock the projection 🔒")',
    'locked_key=st.session_state.get("locked_pitcher")\n    search=st.text_input("Search pitcher...",placeholder="Search pitcher...",label_visibility="collapsed",disabled=bool(locked_key)); st.caption("Search and select a pitcher to lock the projection 🔒")',
    1,
)
old_selector='''matches=[g for g in schedule if not search or search.lower() in g.pitcher_name.lower() or search.lower() in g.team.lower()]
if not matches:st.info("No pitchers match that search."); st.stop()
names=[f"{g.pitcher_name} · {g.team} vs {g.opponent}" for g in matches]
with st.sidebar:
    choice=st.selectbox("Matching pitchers",names,label_visibility="collapsed",key="pitcher_selector")
game=matches[names.index(choice)]
locked=st.session_state.get("locked_pitcher")==game.key
'''
new_selector='''locked_game=next((g for g in schedule if g.key==locked_key),None) if locked_key else None
if locked_key and locked_game is None:
    st.session_state["locked_pitcher"]=None; locked_key=None
matches=schedule if locked_game else [g for g in schedule if not search or search.lower() in g.pitcher_name.lower() or search.lower() in g.team.lower()]
if not matches:st.info("No pitchers match that search."); st.stop()
names=[f"{g.pitcher_name} · {g.team} vs {g.opponent}" for g in matches]
with st.sidebar:
    default_index=names.index(f"{locked_game.pitcher_name} · {locked_game.team} vs {locked_game.opponent}") if locked_game else 0
    choice=st.selectbox("Matching pitchers",names,index=default_index,label_visibility="collapsed",key="pitcher_selector",disabled=bool(locked_game))
game=matches[names.index(choice)]
locked=st.session_state.get("locked_pitcher")==game.key
'''
if old_selector not in s:
    raise SystemExit("selector block not found")
s=s.replace(old_selector,new_selector,1)

# Main metric and ladder expose the independent paths and calibrated weight.
s=s.replace('f"{proj.mean_k:.2f}"', 'f"{proj.mean_k:.2f}"', 1)
s=s.replace('view=kdf[["Line","Probability","Fair Odds","Simulation","Math"]].copy()', 'view=kdf[["Line","Probability","Fair Odds","Simulation","Math","Sim Weight"]].copy()', 1)
s=s.replace('view["Math"]=view["Math"].map(lambda x:f"{x:.1%}")', 'view["Math"]=view["Math"].map(lambda x:f"{x:.1%}"); view["Sim Weight"]=view["Sim Weight"].map(lambda x:f"{x:.1%}")', 1)
s=s.replace('st.caption("Each X+ probability blends the Monte Carlo path with the analytical distribution path. This is a model estimate, not a guarantee.")', 'st.caption("3+ through 10+ are calculated from independent plate-appearance simulation + mathematical paths, then calibrated from resolved history when enough observations exist.")', 1)

# Model Card becomes auditable.
old_model='''    st.write("Two-path architecture: (1) Monte Carlo game simulation draws from the fitted strikeout/outs distributions; (2) analytical Negative Binomial / bounded-normal probabilities. Milestone probabilities blend both paths. Sportsbook prices are used only for edge display, not to create the baseball forecast.")
    st.markdown("### Current model outputs")
    st.dataframe(kdf[["Line","Probability","Simulation","Math","Fair Odds"]].assign(Probability=lambda x:x.Probability.map(lambda v:f"{v:.1%}"),Simulation=lambda x:x.Simulation.map(lambda v:f"{v:.1%}"),Math=lambda x:x.Math.map(lambda v:f"{v:.1%}")),use_container_width=True,hide_index=True)
'''
new_model='''    st.write("Two independent paths: (1) plate-appearance Monte Carlo game simulation with workload uncertainty; (2) independent mathematical Negative-Binomial probability model. Milestone probabilities are calibrated from resolved historical projections when enough observations exist. Sportsbook prices are used only for edge display, never to create the baseball forecast.")
    st.markdown("### Path comparison")
    path_df=pd.DataFrame([{\"Path\":\"Simulation\",\"Mean K\":proj.engine.simulation_mean,\"SD\":proj.engine.simulation_sd},{\"Path\":\"Mathematical\",\"Mean K\":proj.engine.mathematical_mean,\"SD\":proj.engine.mathematical_sd},{\"Path\":\"Ensemble\",\"Mean K\":proj.mean_k,\"SD\":proj.k_sd}])
    path_df[\"Mean K\"]=path_df[\"Mean K\"].map(lambda v:f\"{v:.2f}\"); path_df[\"SD\"]=path_df[\"SD\"].map(lambda v:f\"{v:.2f}\")
    st.dataframe(path_df,use_container_width=True,hide_index=True)
    model_view=kdf[[\"Line\",\"Probability\",\"Simulation\",\"Math\",\"Sim Weight\"]].copy()
    for c in (\"Probability\",\"Simulation\",\"Math\",\"Sim Weight\"): model_view[c]=model_view[c].map(lambda v:f\"{v:.1%}\")
    st.dataframe(model_view,use_container_width=True,hide_index=True)
    st.markdown("### Calibration diagnostics")
    st.dataframe(calibration_summary(load_projection_history()),use_container_width=True,hide_index=True)
'''
if old_model not in s:
    raise SystemExit("model card block not found")
s=s.replace(old_model,new_model,1)

s=s.replace('f"Data status: {proj.confidence} confidence · quality {proj.quality}/100 · locked: {locked} · engine v{APP_VERSION}"', 'f"Data status: {proj.confidence} confidence · quality {proj.quality}/100 · paths independent: {proj.engine.metadata.get(\'paths_independent\',False)} · locked: {locked} · engine v{APP_VERSION}"', 1)

p.write_text(s, encoding="utf-8")
print("patched streamlit_app.py")

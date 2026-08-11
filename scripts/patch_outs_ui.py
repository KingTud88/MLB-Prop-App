from pathlib import Path
import re

# Daily Projection Run
path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")
if "from engine.outs_calibration import calibrate_outs_blend" not in text:
    text = text.replace("from engine.hits_calibration import calibrate_hits_blend\n", "from engine.hits_calibration import calibrate_hits_blend\nfrom engine.outs_calibration import calibrate_outs_blend\n", 1)
text = text.replace("immutable pregame strikeout + hits-allowed snapshot", "immutable pregame strikeout + total-outs + hits-allowed snapshot")
text = text.replace('for col in ("actual_strikeouts", "actual_hits_allowed"):', 'for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs"):')
text = text.replace('    c1, c2, c3, c4 = st.columns(4)\n    c1.metric("Projected Ks", "—" if k_mean is None else f"{k_mean:.2f}")\n    c2.metric("Projected hits allowed", "—" if hits_mean is None else f"{hits_mean:.2f}")\n    c3.metric("Data quality", "—" if quality is None else f"{quality:.0f}/100")\n    c4.metric("Opponent K%", "—" if opp_k is None else f"{opp_k:.1f}%")\n', '    outs_mean = _num(row, "outs_projection")\n    c1, c2, c3, c4, c5 = st.columns(5)\n    c1.metric("Projected Ks", "—" if k_mean is None else f"{k_mean:.2f}")\n    c2.metric("Projected outs", "—" if outs_mean is None else f"{outs_mean:.2f}")\n    c3.metric("Projected hits allowed", "—" if hits_mean is None else f"{hits_mean:.2f}")\n    c4.metric("Data quality", "—" if quality is None else f"{quality:.0f}/100")\n    c5.metric("Opponent K%", "—" if opp_k is None else f"{opp_k:.1f}%")\n', 1)
if '#### Total outs path · Over 15.5' not in text:
    anchor = '    facts = {\n'
    insert = '''    st.markdown("#### Total outs path · Over 15.5")
    outs_sim = _num(row, "outs_sim_over_15_5")
    outs_math = _num(row, "outs_math_over_15_5")
    outs_cal = calibrate_outs_blend(history, 15.5)
    outs_blended = None if outs_sim is None or outs_math is None else outs_cal.weight_simulation * outs_sim + outs_cal.weight_math * outs_math
    detail = pd.DataFrame([
        {"Component": "Simulation", "Probability": outs_sim, "Weight": outs_cal.weight_simulation},
        {"Component": "Mathematical", "Probability": outs_math, "Weight": outs_cal.weight_math},
    ])
    for col in ("Probability", "Weight"):
        detail[col] = detail[col].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
    st.dataframe(detail, hide_index=True, use_container_width=True)
    st.write("**Blended O15.5 probability:**", "—" if outs_blended is None else f"{outs_blended:.1%}")
    st.caption(f"Calibration: {'learned' if outs_cal.calibrated else '50/50 baseline'} · {outs_cal.observations} resolved outs observations.")

'''
    if anchor not in text: raise SystemExit("daily facts anchor missing")
    text = text.replace(anchor, insert + anchor, 1)
text = text.replace('        "Hits 80% range": f"{row.get(\'hits_range_low\', \'—\')}–{row.get(\'hits_range_high\', \'—\')}",\n', '        "Hits 80% range": f"{row.get(\'hits_range_low\', \'—\')}–{row.get(\'hits_range_high\', \'—\')}",\n        "Outs 80% range": f"{row.get(\'outs_range_low\', \'—\')}–{row.get(\'outs_range_high\', \'—\')}",\n', 1)
text = text.replace('"Strikeouts and hits allowed use independent simulation + mathematical paths. Total outs is currently workload/distribution based and is not presented here as a calibrated two-path model."', '"Strikeouts, total outs, and hits allowed each use independent simulation + mathematical paths with protected calibration baselines until enough resolved observations exist."')
text = text.replace('            "hits_projection", "hits_range_low", "hits_range_high",\n', '            "hits_projection", "hits_range_low", "hits_range_high",\n            "outs_projection", "outs_range_low", "outs_range_high",\n', 1)
text = text.replace('            "hits_sim_over_5_5", "hits_math_over_5_5", "probability_semantics",\n            "actual_strikeouts", "actual_hits_allowed",\n', '            "hits_sim_over_5_5", "hits_math_over_5_5", "outs_sim_over_15_5", "outs_math_over_15_5", "probability_semantics",\n            "actual_strikeouts", "actual_hits_allowed", "actual_outs",\n', 1)
text = text.replace('                "hits_range_high": "Hits 80% High",\n', '                "hits_range_high": "Hits 80% High",\n                "outs_projection": "Projection Outs",\n                "outs_range_low": "Outs 80% Low",\n                "outs_range_high": "Outs 80% High",\n', 1)
text = text.replace('                "hits_math_over_5_5": "MATH O5.5 Hits",\n', '                "hits_math_over_5_5": "MATH O5.5 Hits",\n                "outs_sim_over_15_5": "SIM O15.5 Outs",\n                "outs_math_over_15_5": "MATH O15.5 Outs",\n', 1)
text = text.replace('                "actual_hits_allowed": "Actual Hits Allowed",\n', '                "actual_hits_allowed": "Actual Hits Allowed",\n                "actual_outs": "Actual Outs",\n', 1)
text = text.replace('with st.spinner("Checking MLB results and attaching actual strikeouts + hits allowed..."):', 'with st.spinner("Checking MLB results and attaching actual strikeouts + hits allowed + outs..."):')
text = text.replace('                actual_k, actual_hits, resolved = resolve_row(frame.loc[idx])\n', '                actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])\n', 1)
text = text.replace('                if pd.notna(actual_hits) and pd.isna(frame.loc[idx].get("actual_hits_allowed")):\n                    frame.at[idx, "actual_hits_allowed"] = actual_hits\n                    changed = True\n', '                if pd.notna(actual_hits) and pd.isna(frame.loc[idx].get("actual_hits_allowed")):\n                    frame.at[idx, "actual_hits_allowed"] = actual_hits\n                    changed = True\n                if pd.notna(actual_outs) and pd.isna(frame.loc[idx].get("actual_outs")):\n                    frame.at[idx, "actual_outs"] = actual_outs\n                    changed = True\n', 1)
text = text.replace('        actual_hits = pd.to_numeric(day_rows.get("actual_hits_allowed"), errors="coerce")\n', '        actual_hits = pd.to_numeric(day_rows.get("actual_hits_allowed"), errors="coerce")\n        actual_outs = pd.to_numeric(day_rows.get("actual_outs"), errors="coerce")\n', 1)
text = text.replace('            f"{int(actual_hits.notna().sum())} have resolved hits allowed."\n', '            f"{int(actual_hits.notna().sum())} have resolved hits allowed and "\n            f"{int(actual_outs.notna().sum())} have resolved outs."\n', 1)
path.write_text(text, encoding="utf-8")

# Top Plays
path = Path("pages/6_Top_Plays.py")
text = path.read_text(encoding="utf-8")
if "from engine.outs_calibration import calibrate_outs_blend, outs_calibration_report" not in text:
    text = text.replace("from engine.hits_calibration import calibrate_hits_blend, hits_calibration_report\n", "from engine.hits_calibration import calibrate_hits_blend, hits_calibration_report\nfrom engine.outs_calibration import calibrate_outs_blend, outs_calibration_report\n", 1)
new_outs = '''def outs_projection_details(row: pd.Series, line: float, history: pd.DataFrame) -> dict[str, float] | None:
    key = str(float(line)).replace(".", "_")
    sim = numeric(row.get(f"outs_sim_over_{key}"))
    math_p = numeric(row.get(f"outs_math_over_{key}"))
    if sim is None or math_p is None:
        return None
    cal = calibrate_outs_blend(history, float(line))
    return {
        "probability": float(cal.weight_simulation * sim + cal.weight_math * math_p),
        "sim": sim,
        "math": math_p,
        "sim_weight": cal.weight_simulation,
        "observations": float(cal.observations),
        "calibrated": float(cal.calibrated),
        "mean": numeric(row.get("outs_projection")) or 0.0,
        "sd": numeric(row.get("outs_sd")) or 0.0,
        "low": numeric(row.get("outs_range_low")) or 0.0,
        "high": numeric(row.get("outs_range_high")) or 0.0,
    }


def outs_over_probability(row: pd.Series, line: float, history: pd.DataFrame) -> float | None:
    details = outs_projection_details(row, line, history)
    return None if details is None else details["probability"]


def model_over_probability(row: pd.Series, market: str, line: float, history: pd.DataFrame) -> float | None:
    if market.startswith("pitcher_strikeouts"):
        return strikeout_over_probability(row, line, history)
    if market.startswith("pitcher_hits_allowed"):
        return hits_over_probability(row, line, history)
    if market.startswith("pitcher_outs"):
        return outs_over_probability(row, line, history)
    return None
'''
text, n = re.subn(r"def outs_projection_details\([\s\S]*?\n\ndef collect_legs", new_outs + "\n\ndef collect_legs", text, count=1)
if n != 1: raise SystemExit("top plays outs function patch failed")
old_else = '''    else:
        details = outs_projection_details(snapshot, line)
        if details is not None:
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Projected outs", f"{details['mean']:.2f}")
            p2.metric("Workload SD", f"{details['sd']:.2f}")
            p3.metric("Last 5 avg outs", f"{details['last5']:.2f}")
            p4.metric("Starts used", int(details["starts"]))
        st.info("Projection basis: recency-weighted pitcher workload and recent outs distribution. Total Outs does **not** yet have the same independent SIM/MATH calibration layer as Strikeouts and Hits Allowed, so the app labels it separately instead of overstating model depth.")
'''
new_else = '''    else:
        details = outs_projection_details(snapshot, line, history)
        if details is not None:
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("SIM over", f"{details['sim']:.1%}")
            p2.metric("MATH over", f"{details['math']:.1%}")
            p3.metric("SIM weight", f"{details['sim_weight']:.0%}")
            p4.metric("Calibration sample", int(details["observations"]))
            st.write(f"Frozen pregame outs forecast: **{details['mean']:.2f} outs**, 80% simulation range **{int(details['low'])}–{int(details['high'])}**.")
            st.info("Projection basis: recency-weighted empirical workload simulation · independent bounded Beta-Binomial mathematical path · " + ("learned calibration" if details["calibrated"] else "protected 50/50 calibration baseline"))
'''
if old_else not in text: raise SystemExit("top plays rationale anchor missing")
text = text.replace(old_else, new_else, 1)
if 'with st.expander("Total Outs calibration status"' not in text:
    anchor = 'events = odds_events(api_key)\n'
    insert = '''with st.expander("Total Outs calibration status", expanded=False):
    outs_report = outs_calibration_report(history)
    st.dataframe(outs_report, hide_index=True, use_container_width=True)
    outs_ready = int((outs_report["Status"] == "Calibrated").sum()) if not outs_report.empty else 0
    st.caption(f"{outs_ready}/{len(outs_report)} tracked outs lines currently have learned SIM/MATH weights. Until a line reaches 30 resolved frozen observations, Top Plays uses the protected 50/50 baseline.")

'''
    if anchor not in text: raise SystemExit("top plays events anchor missing")
    text = text.replace(anchor, insert + anchor, 1)
path.write_text(text, encoding="utf-8")

# Projection History
path = Path("pages/4_Projection_History.py")
text = path.read_text(encoding="utf-8")
text = text.replace("resolved against final MLB strikeouts and hits allowed.", "resolved against final MLB strikeouts, total outs, and hits allowed.")
text = text.replace('    "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed",\n', '    "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed",\n    "outs_projection", "outs_range_low", "outs_range_high", "actual_outs",\n', 1)
text = text.replace('for col in ["actual_strikeouts", "k_range_low", "k_range_high", "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed"]:', 'for col in ["actual_strikeouts", "k_range_low", "k_range_high", "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed", "outs_projection", "outs_range_low", "outs_range_high", "actual_outs"]:')
if 'o_resolved = df["actual_outs"].notna()' not in text:
    anchor = 'h_hit = h_ready & (df["actual_hits_allowed"] >= df["hits_range_low"]) & (df["actual_hits_allowed"] <= df["hits_range_high"])\n'
    insert = anchor + '\no_resolved = df["actual_outs"].notna()\no_ready = o_resolved & df["outs_range_low"].notna() & df["outs_range_high"].notna()\no_hit = o_ready & (df["actual_outs"] >= df["outs_range_low"]) & (df["actual_outs"] <= df["outs_range_high"])\n'
    if anchor not in text: raise SystemExit("history outs anchor missing")
    text = text.replace(anchor, insert, 1)
text = text.replace('col2.metric("Resolved games", int((k_resolved | h_resolved).sum()))', 'col2.metric("Resolved games", int((k_resolved | h_resolved | o_resolved).sum()))')
if 'outs_metrics1, outs_metrics2 = st.columns(2)' not in text:
    anchor = 'col6.metric("Hits hit rate", f"{float(h_hit.sum() / h_ready.sum()):.1%}" if h_ready.any() else "—")\n'
    insert = anchor + '\nouts_metrics1, outs_metrics2 = st.columns(2)\nouts_metrics1.metric("Outs range hits", int(o_hit.sum()))\nouts_metrics2.metric("Outs hit rate", f"{float(o_hit.sum() / o_ready.sum()):.1%}" if o_ready.any() else "—")\n'
    text = text.replace(anchor, insert, 1)
text = text.replace('mae1, mae2 = st.columns(2)', 'mae1, mae2, mae3 = st.columns(3)')
if 'mae3.metric("Total Outs MAE"' not in text:
    anchor = 'else:\n    mae2.metric("Hits Allowed MAE", "—")\n\nst.caption('
    insert = '''else:
    mae2.metric("Hits Allowed MAE", "—")
if o_resolved.any() and df.loc[o_resolved, "outs_projection"].notna().any():
    o_mask = o_resolved & df["outs_projection"].notna()
    o_error = df.loc[o_mask, "actual_outs"] - df.loc[o_mask, "outs_projection"]
    mae3.metric("Total Outs MAE", f"{float(o_error.abs().mean()):.2f} outs")
else:
    mae3.metric("Total Outs MAE", "—")

st.caption('''
    if anchor not in text: raise SystemExit("history mae anchor missing")
    text = text.replace(anchor, insert, 1)
text = text.replace('lambda r: "Resolved" if pd.notna(r.get("actual_strikeouts")) or pd.notna(r.get("actual_hits_allowed")) else "Pending",', 'lambda r: "Resolved" if pd.notna(r.get("actual_strikeouts")) or pd.notna(r.get("actual_hits_allowed")) or pd.notna(r.get("actual_outs")) else "Pending",')
if 'display["outs_error"]' not in text:
    anchor = 'display["hits_error"] = display.apply(\n    lambda r: r["actual_hits_allowed"] - r["hits_projection"] if pd.notna(r.get("actual_hits_allowed")) and pd.notna(r.get("hits_projection")) else None,\n    axis=1,\n)\n'
    insert = anchor + 'display["outs_error"] = display.apply(\n    lambda r: r["actual_outs"] - r["outs_projection"] if pd.notna(r.get("actual_outs")) and pd.notna(r.get("outs_projection")) else None,\n    axis=1,\n)\n'
    text = text.replace(anchor, insert, 1)
text = text.replace('display["hits_result"] = display.apply(lambda r: range_result(r, "actual_hits_allowed", "hits_range_low", "hits_range_high"), axis=1)\n', 'display["hits_result"] = display.apply(lambda r: range_result(r, "actual_hits_allowed", "hits_range_low", "hits_range_high"), axis=1)\ndisplay["outs_result"] = display.apply(lambda r: range_result(r, "actual_outs", "outs_range_low", "outs_range_high"), axis=1)\n', 1)
text = text.replace('    "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed", "hits_result", "hits_error",\n', '    "hits_projection", "hits_range_low", "hits_range_high", "actual_hits_allowed", "hits_result", "hits_error",\n    "outs_projection", "outs_range_low", "outs_range_high", "actual_outs", "outs_result", "outs_error",\n', 1)
if '"outs_projection": st.column_config.NumberColumn' not in text:
    anchor = '        "hits_error": st.column_config.NumberColumn("Hits Error", format="%+.2f"),\n'
    insert = anchor + '        "outs_projection": st.column_config.NumberColumn("Projected Outs", format="%.2f"),\n        "outs_range_low": st.column_config.NumberColumn("80% Outs Low", format="%.0f"),\n        "outs_range_high": st.column_config.NumberColumn("80% Outs High", format="%.0f"),\n        "actual_outs": st.column_config.NumberColumn("Actual Outs", format="%.0f"),\n        "outs_result": st.column_config.TextColumn("Outs Result"),\n        "outs_error": st.column_config.NumberColumn("Outs Error", format="%+.2f"),\n'
    text = text.replace(anchor, insert, 1)
path.write_text(text, encoding="utf-8")

# Main Projection page
path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
if "from engine.outs_projection import project_total_outs, OutsProjection" not in text:
    text = text.replace("from engine.hits_calibration import calibrate_hits_blend\n", "from engine.hits_calibration import calibrate_hits_blend\nfrom engine.outs_projection import project_total_outs, OutsProjection\nfrom engine.outs_calibration import calibrate_outs_blend\n", 1)
text = text.replace('class Projection:\n    mean_k:float; mean_outs:float; k_sd:float; outs_sd:float; k_probs:np.ndarray; outs_probs:np.ndarray; k_samples:np.ndarray; outs_samples:np.ndarray; confidence:str; quality:int; factors:list[tuple[str,float]]; engine:ProjectionResult\n', 'class Projection:\n    mean_k:float; mean_outs:float; k_sd:float; outs_sd:float; k_probs:np.ndarray; outs_probs:np.ndarray; k_samples:np.ndarray; outs_samples:np.ndarray; confidence:str; quality:int; factors:list[tuple[str,float]]; engine:ProjectionResult; outs_engine:OutsProjection\n', 1)
old_calc = 'mean_outs=weighted(log.tail(35).outs,5,16); osd=float(np.clip(log.tail(35).outs.std(ddof=1) if len(log)>2 else 4,2.5,6.5)); outs_seed=int(hashlib.sha256(f"outs|{game.key}|{APP_VERSION}".encode()).hexdigest()[:8],16); outs_rng=np.random.default_rng(outs_seed); outs_samples=np.clip(np.rint(outs_rng.normal(mean_outs,osd,simulations)),0,27).astype(int); outs_probs=np.array([float(np.mean(outs_samples==i)) for i in range(28)]); quality=int(round(result.data_quality)); confidence="High" if result.confidence>=.75 else "Medium" if result.confidence>=.60 else "Low"; return Projection(mean_k,mean_outs,result.ensemble_sd,osd,result.mathematical_pmf,outs_probs,result.simulation_samples,outs_samples,confidence,quality,[(n,v) for n,v,_ in result.drivers],result)'
new_calc = 'outs_seed=int(hashlib.sha256(f"outs|{game.key}|{APP_VERSION}".encode()).hexdigest()[:8],16); outs_model=project_total_outs(log,seed=outs_seed,draws=simulations,lines=(13.5,14.5,15.5,16.5,17.5,18.5)); mean_outs=outs_model.ensemble_mean; osd=outs_model.ensemble_sd; outs_samples=outs_model.simulation_samples; outs_probs=np.array([float(np.mean(outs_samples==i)) for i in range(28)]); quality=int(round(result.data_quality)); confidence="High" if result.confidence>=.75 else "Medium" if result.confidence>=.60 else "Low"; return Projection(mean_k,mean_outs,result.ensemble_sd,osd,result.mathematical_pmf,outs_probs,result.simulation_samples,outs_samples,confidence,quality,[(n,v) for n,v,_ in result.drivers],result,outs_model)'
if old_calc not in text: raise SystemExit("main outs calc anchor missing")
text = text.replace(old_calc, new_calc, 1)
text = text.replace('    else: model=float(np.mean(proj.outs_samples>=cutoff))\n', '    else:\n        sim=float(proj.outs_engine.simulation_probabilities.get(float(line),np.mean(proj.outs_samples>=cutoff))); math_p=float(proj.outs_engine.mathematical_probabilities.get(float(line),0.0)); cal=calibrate_outs_blend(load_projection_history(),float(line)); model=cal.weight_simulation*sim+cal.weight_math*math_p\n', 1)
old_transparency = '    st.markdown("#### Total Outs transparency")\n    st.caption(f"Projected outs {proj.mean_outs:.2f} with SD {proj.outs_sd:.2f}. Outs is currently workload/distribution based; it does not yet use an independently calibrated SIM/MATH blend like strikeouts and hits allowed.")\n'
new_transparency = '''    st.markdown("#### Total Outs · Over 15.5")
    o_cal=calibrate_outs_blend(load_projection_history(),15.5)
    o_sim=float(proj.outs_engine.simulation_probabilities.get(15.5,0.0)); o_math=float(proj.outs_engine.mathematical_probabilities.get(15.5,0.0))
    o_blend=o_cal.weight_simulation*o_sim+o_cal.weight_math*o_math
    o_paths=pd.DataFrame([{"Path":"Simulation","Probability":o_sim,"Weight":o_cal.weight_simulation},{"Path":"Mathematical","Probability":o_math,"Weight":o_cal.weight_math}])
    for c in ("Probability","Weight"): o_paths[c]=o_paths[c].map(lambda v:f"{v:.1%}")
    st.dataframe(o_paths,use_container_width=True,hide_index=True)
    st.write(f"**Blended O15.5 probability:** {o_blend:.1%}")
    st.caption(f"Projected outs {proj.mean_outs:.2f} · SD {proj.outs_sd:.2f} · calibration {'learned' if o_cal.calibrated else '50/50 baseline'} · {o_cal.observations} resolved outs observations.")
'''
if old_transparency not in text: raise SystemExit("main transparency anchor missing")
text = text.replace(old_transparency, new_transparency, 1)
path.write_text(text, encoding="utf-8")

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor not found: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Daily projection runner: shared workload context, pregame upgrade audit,
# and actual BF/pitch resolution.
# ---------------------------------------------------------------------------
path = Path("automation/daily_projection_runner.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from engine.weather_risk import WeatherDelayRisk, fetch_weather_delay_risk\n',
    'from engine.weather_risk import WeatherDelayRisk, fetch_weather_delay_risk\nfrom engine.workload_context import WORKLOAD_VERSION, WorkloadContext, build_workload_context\n',
    "daily workload import",
)
text = replace_once(text, 'APP_VERSION = "3.6.0"', 'APP_VERSION = "3.7.0"', "daily app version")

old_features = '''def features(log: pd.DataFrame, venue: str, opponent_k_pct: float = .224, lineup_batters: int = 0, matchup_source: str = LINEUP_ACTIVE_ROSTER) -> dict[str, float]:\n    starts = log.tail(35).copy()\n    total_bf = float(starts.bf.sum())\n    raw_k = float(starts.k.sum() / max(total_bf, 1))\n    pitcher_k = float(np.clip(shrink(raw_k, total_bf), .05, .45))\n    bf = weighted(starts.bf, 5, 22)\n    pitches = weighted(starts.pitches, 5, 88)\n    workload = float(np.clip(92 / max(pitches, 75), .78, 1.12))\n    return {\n        "pitcher_k_pct": pitcher_k,\n        "opponent_k_pct": float(np.clip(opponent_k_pct, .08, .45)),\n        "handedness_factor": 1.0,\n        "arsenal_factor": 1.0,\n        "park_factor": PARK_K_FACTOR.get(venue, 1.0),\n        "umpire_factor": 1.0,\n        "weather_factor": 1.0,\n        "expected_bf": float(np.clip(bf * workload, 10, 35)),\n        "bf_sd": float(np.clip(starts.bf.std(ddof=1) if len(starts) > 2 else 3.5, 1, 7)),\n        "rest_factor": 1.0,\n        "historical_k_sd": float(np.clip(starts.k.std(ddof=1) if len(starts) > 2 else 2.0, .75, 4.5)),\n        "historical_games": int(len(starts)),\n        "lineup_batters": int(lineup_batters),\n        "matchup_source": str(matchup_source),\n        "arsenal_sample_size": 0,\n        "weather_available": 0,\n        "umpire_available": 0,\n    }\n'''
new_features = '''def features(\n    log: pd.DataFrame,\n    venue: str,\n    opponent_k_pct: float = .224,\n    lineup_batters: int = 0,\n    matchup_source: str = LINEUP_ACTIVE_ROSTER,\n    workload: WorkloadContext | None = None,\n) -> dict[str, float]:\n    starts = log.tail(35).copy()\n    total_bf = float(starts.bf.sum())\n    raw_k = float(starts.k.sum() / max(total_bf, 1))\n    pitcher_k = float(np.clip(shrink(raw_k, total_bf), .05, .45))\n    workload = workload or build_workload_context(starts)\n    return {\n        "pitcher_k_pct": pitcher_k,\n        "opponent_k_pct": float(np.clip(opponent_k_pct, .08, .45)),\n        "handedness_factor": 1.0,\n        "arsenal_factor": 1.0,\n        "park_factor": PARK_K_FACTOR.get(venue, 1.0),\n        "umpire_factor": 1.0,\n        "weather_factor": 1.0,\n        "expected_bf": float(workload.expected_bf),\n        "bf_sd": float(workload.bf_sd),\n        # Short-rest handling is already baked into expected exposure. Keep the\n        # engine-level factor neutral so the same rest signal is not counted twice.\n        "rest_factor": 1.0,\n        "historical_k_sd": float(np.clip(starts.k.std(ddof=1) if len(starts) > 2 else 2.0, .75, 4.5)),\n        "historical_games": int(len(starts)),\n        "lineup_batters": int(lineup_batters),\n        "matchup_source": str(matchup_source),\n        "arsenal_sample_size": 0,\n        "weather_available": 0,\n        "umpire_available": 0,\n    }\n'''
text = replace_once(text, old_features, new_features, "daily features workload")

text = replace_once(
    text,
    '''    if log.empty:\n        record_history_only(row, history_games=0)\n        return None\n    matchup = matchup_context(\n''',
    '''    if log.empty:\n        record_history_only(row, history_games=0)\n        return None\n    workload = build_workload_context(log, row.get("game_time") or row.get("game_date"))\n    matchup = matchup_context(\n''',
    "daily workload build",
)
text = replace_once(
    text,
    '''        lineup_batters=int(matchup["lineup_batters"]),\n        matchup_source=str(matchup["source"]),\n    )\n''',
    '''        lineup_batters=int(matchup["lineup_batters"]),\n        matchup_source=str(matchup["source"]),\n        workload=workload,\n    )\n''',
    "daily features workload argument",
)
text = replace_once(
    text,
    '''        expected_bf=f["expected_bf"],\n        opponent_hit_rate=float(matchup.get("hit_rate", .235)),\n''',
    '''        expected_bf=f["expected_bf"],\n        bf_sd=workload.bf_sd,\n        opponent_hit_rate=float(matchup.get("hit_rate", .235)),\n''',
    "daily hits workload sd",
)
text = replace_once(
    text,
    '''    outs = project_total_outs(\n        log,\n        seed=seed ^ 0x0A75,\n''',
    '''    outs = project_total_outs(\n        log,\n        expected_outs=workload.expected_outs,\n        workload_sd=workload.outs_sd,\n        seed=seed ^ 0x0A75,\n''',
    "daily outs workload target",
)
text = replace_once(
    text,
    '''        "starter_history_observation_games": int(history_provenance["observation_games"]),\n        "projection": result.ensemble_mean, "k_sd": result.ensemble_sd,\n''',
    '''        "starter_history_observation_games": int(history_provenance["observation_games"]),\n        **workload.snapshot_fields(),\n        "workload_preupgrade_projection": np.nan, "workload_preupgrade_hits_projection": np.nan,\n        "workload_preupgrade_outs_projection": np.nan, "workload_preupgrade_expected_bf": np.nan,\n        "workload_projection_delta_k": np.nan, "workload_projection_delta_hits": np.nan,\n        "workload_projection_delta_outs": np.nan,\n        "projection": result.ensemble_mean, "k_sd": result.ensemble_sd,\n''',
    "daily workload snapshot fields",
)
text = replace_once(
    text,
    '''        **weather,\n        "actual_strikeouts": np.nan, "actual_hits_allowed": np.nan, "actual_outs": np.nan, "resolved_at_utc": "",\n''',
    '''        **weather,\n        "actual_strikeouts": np.nan, "actual_hits_allowed": np.nan, "actual_outs": np.nan,\n        "actual_batters_faced": np.nan, "actual_pitches": np.nan, "resolved_at_utc": "",\n''',
    "daily actual workload columns",
)

old_fill_head = '''        needs_hits = pd.isna(row.get("hits_projection"))\n        needs_outs = pd.isna(row.get("outs_projection"))\n        if ((row_has_complete_paths(row) and row_has_current_semantics(row) and not needs_hits and not needs_outs) or not row_is_pregame(row, now)):\n            continue\n'''
new_fill_head = '''        needs_hits = pd.isna(row.get("hits_projection"))\n        needs_outs = pd.isna(row.get("outs_projection"))\n        needs_workload = str(row.get("workload_version", "")) != WORKLOAD_VERSION\n        if ((row_has_complete_paths(row) and row_has_current_semantics(row) and not needs_hits and not needs_outs and not needs_workload) or not row_is_pregame(row, now)):\n            continue\n'''
text = replace_once(text, old_fill_head, new_fill_head, "pregame workload refresh need")
old_fill_write = '''        if not projected:\n            continue\n        for key, value in projected.items():\n            if key.startswith("sim_") or key.startswith("math_") or key.startswith("hits_") or key.startswith("outs_") or key in {"probability_semantics"}:\n                frame.at[idx, key] = value\n        updated += 1\n'''
new_fill_write = '''        if not projected:\n            continue\n        if needs_workload:\n            old_k = pd.to_numeric(pd.Series([row.get("projection")]), errors="coerce").iloc[0]\n            old_hits = pd.to_numeric(pd.Series([row.get("hits_projection")]), errors="coerce").iloc[0]\n            old_outs = pd.to_numeric(pd.Series([row.get("outs_projection")]), errors="coerce").iloc[0]\n            old_bf = pd.to_numeric(pd.Series([row.get("expected_bf")]), errors="coerce").iloc[0]\n            protected = {\n                "actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches", "resolved_at_utc",\n                "lineup_preconfirm_projection", "lineup_preconfirm_opponent_k_pct", "lineup_projection_delta", "lineup_opponent_k_delta",\n            }\n            for key, value in projected.items():\n                if key not in protected:\n                    frame.at[idx, key] = value\n            frame.at[idx, "workload_preupgrade_projection"] = old_k\n            frame.at[idx, "workload_preupgrade_hits_projection"] = old_hits\n            frame.at[idx, "workload_preupgrade_outs_projection"] = old_outs\n            frame.at[idx, "workload_preupgrade_expected_bf"] = old_bf\n            for old_value, new_key, delta_key in (\n                (old_k, "projection", "workload_projection_delta_k"),\n                (old_hits, "hits_projection", "workload_projection_delta_hits"),\n                (old_outs, "outs_projection", "workload_projection_delta_outs"),\n            ):\n                new_value = pd.to_numeric(pd.Series([projected.get(new_key)]), errors="coerce").iloc[0]\n                frame.at[idx, delta_key] = np.nan if pd.isna(old_value) or pd.isna(new_value) else float(new_value - old_value)\n        else:\n            for key, value in projected.items():\n                if key.startswith("sim_") or key.startswith("math_") or key.startswith("hits_") or key.startswith("outs_") or key in {"probability_semantics"}:\n                    frame.at[idx, key] = value\n        updated += 1\n'''
text = replace_once(text, old_fill_write, new_fill_write, "pregame workload refresh write")

resolve_anchor = '''def resolve_row(row: pd.Series) -> tuple[object, object, object, str]:\n'''
resolve_helper = '''def resolve_workload_actuals(row: pd.Series) -> tuple[object, object]:\n    if pd.notna(row.get("actual_batters_faced")) and pd.notna(row.get("actual_pitches")):\n        return row.get("actual_batters_faced"), row.get("actual_pitches")\n    if pd.isna(row.get("game_pk")) or pd.isna(row.get("pitcher_id")):\n        return np.nan, np.nan\n    try:\n        data = get_json(f"game/{int(row['game_pk'])}/boxscore", {})\n        status = data.get("gameData", {}).get("status", {})\n        if status.get("abstractGameState") != "Final":\n            return np.nan, np.nan\n        player = data.get("teams", {}).get("away", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")\n        if not player:\n            player = data.get("teams", {}).get("home", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")\n        pitching = (player or {}).get("stats", {}).get("pitching", {})\n        bf = pitching.get("battersFaced")\n        pitches = pitching.get("numberOfPitches")\n        return (int(bf) if bf is not None else np.nan), (int(pitches) if pitches is not None else np.nan)\n    except (requests.RequestException, ValueError, TypeError):\n        return np.nan, np.nan\n\n\n'''
if resolve_anchor not in text:
    raise SystemExit("daily resolve workload anchor missing")
text = text.replace(resolve_anchor, resolve_helper + resolve_anchor, 1)
text = replace_once(
    text,
    '''            actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])\n            if pd.notna(actual_k):\n''',
    '''            actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])\n            actual_bf, actual_pitches = resolve_workload_actuals(frame.loc[idx])\n            if pd.notna(actual_k):\n''',
    "daily main resolve workload call",
)
text = replace_once(
    text,
    '''            if pd.notna(actual_outs):\n                frame.at[idx, "actual_outs"] = actual_outs\n            if resolved:\n''',
    '''            if pd.notna(actual_outs):\n                frame.at[idx, "actual_outs"] = actual_outs\n            if pd.notna(actual_bf):\n                frame.at[idx, "actual_batters_faced"] = actual_bf\n            if pd.notna(actual_pitches):\n                frame.at[idx, "actual_pitches"] = actual_pitches\n            if resolved:\n''',
    "daily main store workload actuals",
)
text = replace_once(
    text,
    '''    for col in ["actual_strikeouts", "actual_hits_allowed", "actual_outs", "resolved_at_utc"]:\n''',
    '''    for col in ["actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches", "resolved_at_utc"]:\n''',
    "daily main workload actual schema",
)
text = text.replace(
    'protected = {"actual_strikeouts", "actual_hits_allowed", "actual_outs", "resolved_at_utc"}',
    'protected = {"actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches", "resolved_at_utc"}',
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main Projection page: same workload context for K, Hits, and Outs, plus a
# real workload panel and rationale.
# ---------------------------------------------------------------------------
path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from engine.weather_risk import WeatherDelayRisk, fetch_weather_delay_risk\n',
    'from engine.weather_risk import WeatherDelayRisk, fetch_weather_delay_risk\nfrom engine.workload_context import WorkloadContext, build_workload_context\n',
    "main workload import",
)
text = replace_once(text, 'APP_VERSION = "3.6.0"', 'APP_VERSION = "3.7.0"', "main app version")
old_builder = '''def build_engine_features(log,game,opponent_k_pct=.224,lineup_batters=0):\n    starts=log.tail(35).copy(); total_bf=float(starts.bf.sum()); raw_k=float(starts.k.sum()/max(total_bf,1)); pitcher_k=float(np.clip(shrink(raw_k,total_bf),.05,.45)); bf=weighted(starts.bf,5,22); pitches=weighted(starts.pitches,5,88); workload=float(np.clip(92/max(pitches,75),.78,1.12))\n    return {"pitcher_k_pct":pitcher_k,"opponent_k_pct":float(np.clip(opponent_k_pct,.08,.45)),"handedness_factor":1.0,"arsenal_factor":1.0,"park_factor":PARK_K_FACTOR.get(game.venue,1.0),"umpire_factor":1.0,"weather_factor":1.0,"expected_bf":float(np.clip(bf*workload,10,35)),"bf_sd":float(np.clip(starts.bf.std(ddof=1) if len(starts)>2 else 3.5,1,7)),"rest_factor":1.0,"historical_k_sd":float(np.clip(starts.k.std(ddof=1) if len(starts)>2 else 2.0,.75,4.5)),"historical_games":int(len(starts)),"lineup_batters":int(lineup_batters),"arsenal_sample_size":0,"weather_available":0,"umpire_available":0}\n\ndef calculate_projection(log,game,simulations,opponent_k_pct=.224,lineup_batters=0):\n    history=load_projection_history(); cal=calibrated_weights(history); seed=int(hashlib.sha256(f"{game.key}|{game.game_time}|{APP_VERSION}".encode()).hexdigest()[:8],16); features=build_engine_features(log,game,opponent_k_pct,lineup_batters); engine=ProjectionEngine(simulation_weight=.5,seed=seed); result=engine.project(features,draws=simulations,lines=tuple(float(x) for x in range(3,11))); global_w=float(np.mean([r.weight_simulation for r in cal.values()])) if cal else .5; mean_k=global_w*result.simulation_mean+(1-global_w)*result.mathematical_mean; outs_seed=int(hashlib.sha256(f"outs|{game.key}|{APP_VERSION}".encode()).hexdigest()[:8],16); outs_model=project_total_outs(log,seed=outs_seed,draws=simulations,lines=(13.5,14.5,15.5,16.5,17.5,18.5)); mean_outs=outs_model.ensemble_mean; osd=outs_model.ensemble_sd; outs_samples=outs_model.simulation_samples; outs_probs=np.array([float(np.mean(outs_samples==i)) for i in range(28)]); quality=int(round(result.data_quality)); confidence="High" if result.confidence>=.75 else "Medium" if result.confidence>=.60 else "Low"; return Projection(mean_k,mean_outs,result.ensemble_sd,osd,result.mathematical_pmf,outs_probs,result.simulation_samples,outs_samples,confidence,quality,[(n,v) for n,v,_ in result.drivers],result,outs_model)\n'''
new_builder = '''def build_engine_features(log,game,opponent_k_pct=.224,lineup_batters=0,workload_context:WorkloadContext|None=None):\n    starts=log.tail(35).copy(); total_bf=float(starts.bf.sum()); raw_k=float(starts.k.sum()/max(total_bf,1)); pitcher_k=float(np.clip(shrink(raw_k,total_bf),.05,.45)); workload_context=workload_context or build_workload_context(starts,game.game_time)\n    return {"pitcher_k_pct":pitcher_k,"opponent_k_pct":float(np.clip(opponent_k_pct,.08,.45)),"handedness_factor":1.0,"arsenal_factor":1.0,"park_factor":PARK_K_FACTOR.get(game.venue,1.0),"umpire_factor":1.0,"weather_factor":1.0,"expected_bf":float(workload_context.expected_bf),"bf_sd":float(workload_context.bf_sd),"rest_factor":1.0,"historical_k_sd":float(np.clip(starts.k.std(ddof=1) if len(starts)>2 else 2.0,.75,4.5)),"historical_games":int(len(starts)),"lineup_batters":int(lineup_batters),"arsenal_sample_size":0,"weather_available":0,"umpire_available":0}\n\ndef calculate_projection(log,game,simulations,opponent_k_pct=.224,lineup_batters=0,workload_context:WorkloadContext|None=None):\n    history=load_projection_history(); cal=calibrated_weights(history); workload_context=workload_context or build_workload_context(log,game.game_time); seed=int(hashlib.sha256(f"{game.key}|{game.game_time}|{APP_VERSION}".encode()).hexdigest()[:8],16); features=build_engine_features(log,game,opponent_k_pct,lineup_batters,workload_context); engine=ProjectionEngine(simulation_weight=.5,seed=seed); result=engine.project(features,draws=simulations,lines=tuple(float(x) for x in range(3,11))); global_w=float(np.mean([r.weight_simulation for r in cal.values()])) if cal else .5; mean_k=global_w*result.simulation_mean+(1-global_w)*result.mathematical_mean; outs_seed=int(hashlib.sha256(f"outs|{game.key}|{APP_VERSION}".encode()).hexdigest()[:8],16); outs_model=project_total_outs(log,expected_outs=workload_context.expected_outs,workload_sd=workload_context.outs_sd,seed=outs_seed,draws=simulations,lines=(13.5,14.5,15.5,16.5,17.5,18.5)); mean_outs=outs_model.ensemble_mean; osd=outs_model.ensemble_sd; outs_samples=outs_model.simulation_samples; outs_probs=np.array([float(np.mean(outs_samples==i)) for i in range(28)]); quality=int(round(result.data_quality)); confidence="High" if result.confidence>=.75 else "Medium" if result.confidence>=.60 else "Low"; return Projection(mean_k,mean_outs,result.ensemble_sd,osd,result.mathematical_pmf,outs_probs,result.simulation_samples,outs_samples,confidence,quality,[(n,v) for n,v,_ in result.drivers],result,outs_model)\n'''
text = replace_once(text, old_builder, new_builder, "main workload feature builder")
text = replace_once(
    text,
    '''confirmed_count=lineup_context.batter_count if lineup_context.confirmed else 0\nproj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count); kdf=ladder(proj,10)\nfeatures_for_hits=build_engine_features(log,game,float(opponent_matchup["k_rate"]),confirmed_count)\n''',
    '''confirmed_count=lineup_context.batter_count if lineup_context.confirmed else 0\nworkload_ctx=build_workload_context(log,game.game_time)\nproj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count,workload_ctx); kdf=ladder(proj,10)\nfeatures_for_hits=build_engine_features(log,game,float(opponent_matchup["k_rate"]),confirmed_count,workload_ctx)\n''',
    "main workload build selected pitcher",
)
text = replace_once(
    text,
    '''hits_proj=project_hits_allowed(log,expected_bf=features_for_hits["expected_bf"],opponent_hit_rate=float(opponent_matchup.get("hit_rate",.235)),seed=hits_seed,draws=25000,lines=(3.5,4.5,5.5,6.5,7.5,8.5))\n''',
    '''hits_proj=project_hits_allowed(log,expected_bf=features_for_hits["expected_bf"],bf_sd=workload_ctx.bf_sd,opponent_hit_rate=float(opponent_matchup.get("hit_rate",.235)),seed=hits_seed,draws=25000,lines=(3.5,4.5,5.5,6.5,7.5,8.5))\n''',
    "main hits workload sd",
)
old_form = '''elif nav=="Form & Workload":\n    st.markdown('<div class="section-head">FORM & WORKLOAD</div>',unsafe_allow_html=True); st.caption(f"{game.pitcher_name} · last 15 starts"); d=log.tail(15).copy(); st.line_chart(d.set_index("date")[["k","outs"]]); st.dataframe(d.sort_values("date",ascending=False),use_container_width=True,hide_index=True); st.stop()\n'''
new_form = '''elif nav=="Form & Workload":\n    st.markdown('<div class="section-head">FORM & WORKLOAD</div>',unsafe_allow_html=True); st.caption(f"{game.pitcher_name} · workload-v1 uses starter history only; sportsbook data is not an input.")\n    w1,w2,w3,w4,w5,w6=st.columns(6)\n    w1.metric("Expected pitches",f"{workload_ctx.expected_pitches:.1f}")\n    w2.metric("Expected BF",f"{workload_ctx.expected_bf:.1f}")\n    w3.metric("Expected outs",f"{workload_ctx.expected_outs:.1f}")\n    w4.metric("Pitches / BF",f"{workload_ctx.pitches_per_bf:.2f}")\n    w5.metric("Days since last start","—" if workload_ctx.days_since_last_start is None else workload_ctx.days_since_last_start)\n    w6.metric("Recent leash",workload_ctx.leash_label)\n    st.caption(f"Pitch trend {workload_ctx.pitch_trend:+.1%} · BF trend {workload_ctx.bf_trend:+.1%} · outs trend {workload_ctx.outs_trend:+.1%} · short-rest exposure multiplier {workload_ctx.rest_multiplier:.3f}.")\n    d=log.tail(15).copy(); st.line_chart(d.set_index("date")[["pitches","bf","outs","k"]]); st.dataframe(d.sort_values("date",ascending=False),use_container_width=True,hide_index=True); st.stop()\n'''
text = replace_once(text, old_form, new_form, "main form workload panel")
text = replace_once(
    text,
    '''        st.write(f"Expected batters faced: **{features_for_hits['expected_bf']:.1f}**")\n        st.write(f"Park K factor: **{features_for_hits['park_factor']:.3f}**")\n''',
    '''        st.write(f"Expected batters faced: **{features_for_hits['expected_bf']:.1f}**")\n        st.write(f"Expected pitches: **{workload_ctx.expected_pitches:.1f}** · expected outs: **{workload_ctx.expected_outs:.1f}**")\n        st.write(f"Pitch efficiency: **{workload_ctx.pitches_per_bf:.2f} pitches/BF** · recent leash: **{workload_ctx.leash_label}**")\n        st.write(f"Days since last start: **{'—' if workload_ctx.days_since_last_start is None else workload_ctx.days_since_last_start}** · pitch trend: **{workload_ctx.pitch_trend:+.1%}**")\n        st.write(f"Park K factor: **{features_for_hits['park_factor']:.3f}**")\n''',
    "main rationale workload",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Projection resolver: save actual BF/pitches for workload validation while
# preserving the existing resolve_row public contract.
# ---------------------------------------------------------------------------
path = Path("automation/resolve_projection_log.py")
text = path.read_text(encoding="utf-8")
text = replace_once(text, '"User-Agent": "StrikeOutKing9000/3.5.0"', '"User-Agent": "StrikeOutKing9000/3.7.0"', "resolver UA")
anchor = '''def resolve_row(row: pd.Series) -> tuple[int | None, int | None, int | None, str | None, str | None]:\n'''
helper = '''def _pitcher_workload_from_boxscore(data: dict, player_id: str) -> tuple[int | None, int | None]:\n    for side in ("away", "home"):\n        player = data.get("teams", {}).get(side, {}).get("players", {}).get(player_id)\n        pitching = (player or {}).get("stats", {}).get("pitching", {})\n        if pitching:\n            bf = pitching.get("battersFaced")\n            pitches = pitching.get("numberOfPitches")\n            return (int(bf) if bf is not None else None, int(pitches) if pitches is not None else None)\n    return None, None\n\n\ndef resolve_workload_row(row: pd.Series) -> tuple[int | None, int | None]:\n    have_bf = not is_missing(row.get("actual_batters_faced"))\n    have_pitches = not is_missing(row.get("actual_pitches"))\n    if have_bf and have_pitches:\n        return int(float(row["actual_batters_faced"])), int(float(row["actual_pitches"]))\n    if is_missing(row.get("game_pk")) or is_missing(row.get("pitcher_id")):\n        return None, None\n    try:\n        game_pk = int(float(row["game_pk"]))\n        player_id = f"ID{int(float(row['pitcher_id']))}"\n        boxscore = get_json(f"game/{game_pk}/boxscore")\n        if boxscore.get("gameData", {}).get("status", {}).get("abstractGameState") != "Final":\n            return None, None\n        return _pitcher_workload_from_boxscore(boxscore, player_id)\n    except (requests.RequestException, ValueError, TypeError, KeyError):\n        return None, None\n\n\n'''
if anchor not in text:
    raise SystemExit("resolver workload helper anchor missing")
text = text.replace(anchor, helper + anchor, 1)
text = replace_once(
    text,
    '''    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs"):\n''',
    '''    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches"):\n''',
    "resolver workload columns",
)
text = replace_once(
    text,
    '''        strikeouts, hits, outs, timestamp, reason = resolve_row(frame.loc[idx])\n        changed = False\n''',
    '''        strikeouts, hits, outs, timestamp, reason = resolve_row(frame.loc[idx])\n        actual_bf, actual_pitches = resolve_workload_row(frame.loc[idx])\n        changed = False\n''',
    "resolver workload call",
)
text = replace_once(
    text,
    '''        if outs is not None:\n            frame.at[idx, "actual_outs"] = outs\n            changed = True\n        if changed:\n''',
    '''        if outs is not None:\n            frame.at[idx, "actual_outs"] = outs\n            changed = True\n        if actual_bf is not None:\n            frame.at[idx, "actual_batters_faced"] = actual_bf\n            changed = True\n        if actual_pitches is not None:\n            frame.at[idx, "actual_pitches"] = actual_pitches\n            changed = True\n        if changed:\n''',
    "resolver workload store",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Daily page: workload fields in rationale/slate and manual workload resolution.
# ---------------------------------------------------------------------------
path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    project,\n    resolve_row,\n    schedule,\n''',
    '''    project,\n    resolve_row,\n    resolve_workload_actuals,\n    schedule,\n''',
    "daily page resolve workload import",
)
text = replace_once(
    text,
    '''    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs"):\n''',
    '''    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches"):\n''',
    "daily page load workload actual columns",
)
text = replace_once(
    text,
    '''    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs"):\n        if col not in frame.columns:\n            frame[col] = np.nan\n''',
    '''    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches"):\n        if col not in frame.columns:\n            frame[col] = np.nan\n''',
    "daily page save workload actual columns",
)
text = replace_once(
    text,
    '''        "Observed starts used": int(_num(row, "starter_history_observation_games") or 0),\n    }\n''',
    '''        "Observed starts used": int(_num(row, "starter_history_observation_games") or 0),\n        "Workload version": row.get("workload_version", "—"),\n        "Expected pitches": _num(row, "expected_pitches"),\n        "Expected BF": _num(row, "expected_bf"),\n        "Expected outs workload": _num(row, "expected_outs"),\n        "Pitches / BF": _num(row, "pitches_per_bf"),\n        "Days since last start": _num(row, "days_since_last_start"),\n        "Recent leash": row.get("leash_label", "—"),\n        "Pitch trend": _num(row, "pitch_trend"),\n    }\n''',
    "daily page rationale workload facts",
)
text = replace_once(
    text,
    '''            "player", "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games", "weather_icon", "weather_delay_risk", "weather_precip_probability", "lineup_source", "lineup_batters", "lineup_projection_delta", "team", "opponent", "projection", "k_range_low", "k_range_high",\n''',
    '''            "player", "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games", "workload_version", "expected_pitches", "expected_bf", "expected_outs", "pitches_per_bf", "days_since_last_start", "leash_label", "pitch_trend", "weather_icon", "weather_delay_risk", "weather_precip_probability", "lineup_source", "lineup_batters", "lineup_projection_delta", "team", "opponent", "projection", "k_range_low", "k_range_high",\n''',
    "daily page workload display columns",
)
text = replace_once(
    text,
    '''                "starter_history_observation_games": "Observed Starts",\n                "weather_delay_risk": "Weather Risk",\n''',
    '''                "starter_history_observation_games": "Observed Starts",\n                "workload_version": "Workload",\n                "expected_pitches": "Exp Pitches",\n                "expected_bf": "Exp BF",\n                "expected_outs": "Exp Outs",\n                "pitches_per_bf": "Pitches/BF",\n                "days_since_last_start": "Days Since Start",\n                "leash_label": "Leash",\n                "pitch_trend": "Pitch Trend",\n                "weather_delay_risk": "Weather Risk",\n''',
    "daily page workload display labels",
)
text = replace_once(
    text,
    '''                actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])\n                changed = False\n''',
    '''                actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])\n                actual_bf, actual_pitches = resolve_workload_actuals(frame.loc[idx])\n                changed = False\n''',
    "daily page manual workload resolve call",
)
text = replace_once(
    text,
    '''                if pd.notna(actual_outs) and pd.isna(frame.loc[idx].get("actual_outs")):\n                    frame.at[idx, "actual_outs"] = actual_outs\n                    changed = True\n                if changed:\n''',
    '''                if pd.notna(actual_outs) and pd.isna(frame.loc[idx].get("actual_outs")):\n                    frame.at[idx, "actual_outs"] = actual_outs\n                    changed = True\n                if pd.notna(actual_bf) and pd.isna(frame.loc[idx].get("actual_batters_faced")):\n                    frame.at[idx, "actual_batters_faced"] = actual_bf\n                    changed = True\n                if pd.notna(actual_pitches) and pd.isna(frame.loc[idx].get("actual_pitches")):\n                    frame.at[idx, "actual_pitches"] = actual_pitches\n                    changed = True\n                if changed:\n''',
    "daily page manual workload actual store",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Projection History: workload validation audit and fix rolling indexes so
# pending rows cannot shift resolved-only learning charts.
# ---------------------------------------------------------------------------
path = Path("pages/4_Projection_History.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    current["game_date_dt"] = pd.to_datetime(current.get("game_date"), errors="coerce")\n    current = current.sort_values(["game_date_dt", "captured_at_utc"], na_position="last").reset_index(drop=True)\n    current["Resolved Start #"] = np.arange(1, len(current) + 1)\n\n    specs = (\n''',
    '''    current["game_date_dt"] = pd.to_datetime(current.get("game_date"), errors="coerce")\n    current = current.sort_values(["game_date_dt", "captured_at_utc"], na_position="last").reset_index(drop=True)\n    resolved_any = (\n        pd.to_numeric(current.get("actual_strikeouts"), errors="coerce").notna()\n        | pd.to_numeric(current.get("actual_hits_allowed"), errors="coerce").notna()\n        | pd.to_numeric(current.get("actual_outs"), errors="coerce").notna()\n    )\n    current = current.loc[resolved_any].reset_index(drop=True)\n    if current.empty:\n        return current\n    current["Resolved Start #"] = np.arange(1, len(current) + 1)\n\n    specs = (\n''',
    "history resolved-only rolling index",
)
text = replace_once(
    text,
    '''    "outs_projection", "outs_range_low", "outs_range_high", "actual_outs", "starter_history_games",\n''',
    '''    "outs_projection", "outs_range_low", "outs_range_high", "actual_outs", "starter_history_games",\n    "expected_pitches", "expected_bf", "expected_outs", "actual_batters_faced", "actual_pitches",\n    "pitches_per_bf", "days_since_last_start", "pitch_trend", "bf_trend", "outs_trend",\n''',
    "history workload numeric columns",
)
lineup_anchor = '''st.divider()\nst.subheader("🧾 Lineup input audit")\n'''
workload_section = '''st.divider()\nst.subheader("⚙️ Workload intelligence audit")\nst.caption(\n    "workload-v1 estimates expected pitches, batters faced, and outs from starter-only pitch/BF/outs history, efficiency, recent trend, and conservative short-rest handling. "\n    "Sportsbook data is excluded. Actual BF and pitch count are resolved after games so the exposure model can be validated directly."\n)\nif "workload_version" not in df.columns:\n    st.info("Workload tracking begins with app version 3.7.0; older snapshots remain visible but untagged.")\nelse:\n    workload_rows = df.loc[df["workload_version"].astype(str).eq("workload-v1")].copy()\n    if workload_rows.empty:\n        st.info("No workload-v1 snapshots have been captured yet.")\n    else:\n        expected_pitches = pd.to_numeric(workload_rows.get("expected_pitches"), errors="coerce")\n        actual_pitches = pd.to_numeric(workload_rows.get("actual_pitches"), errors="coerce")\n        expected_bf = pd.to_numeric(workload_rows.get("expected_bf"), errors="coerce")\n        actual_bf = pd.to_numeric(workload_rows.get("actual_batters_faced"), errors="coerce")\n        expected_outs = pd.to_numeric(workload_rows.get("expected_outs"), errors="coerce")\n        actual_outs_w = pd.to_numeric(workload_rows.get("actual_outs"), errors="coerce")\n        pitch_ready = expected_pitches.notna() & actual_pitches.notna()\n        bf_ready = expected_bf.notna() & actual_bf.notna()\n        outs_ready_w = expected_outs.notna() & actual_outs_w.notna()\n        wa1,wa2,wa3,wa4 = st.columns(4)\n        wa1.metric("workload-v1 snapshots", len(workload_rows))\n        wa2.metric("Pitch-count MAE", "—" if not pitch_ready.any() else f"{float((actual_pitches[pitch_ready]-expected_pitches[pitch_ready]).abs().mean()):.1f} pitches")\n        wa3.metric("BF MAE", "—" if not bf_ready.any() else f"{float((actual_bf[bf_ready]-expected_bf[bf_ready]).abs().mean()):.2f} BF")\n        wa4.metric("Workload-outs MAE", "—" if not outs_ready_w.any() else f"{float((actual_outs_w[outs_ready_w]-expected_outs[outs_ready_w]).abs().mean()):.2f} outs")\n        upgrades = pd.to_numeric(workload_rows.get("workload_projection_delta_k"), errors="coerce") if "workload_projection_delta_k" in workload_rows.columns else pd.Series(dtype=float)\n        if upgrades.notna().any():\n            st.caption(f"Pregame workload upgrades recorded: {int(upgrades.notna().sum())} · average K projection change {float(upgrades.dropna().mean()):+.2f} K. Started/finished snapshots are never rewritten.")\n        audit_cols = [\n            "game_date", "player", "expected_pitches", "actual_pitches", "expected_bf", "actual_batters_faced",\n            "expected_outs", "actual_outs", "pitches_per_bf", "days_since_last_start", "leash_label", "pitch_trend",\n        ]\n        audit_cols = [col for col in audit_cols if col in workload_rows.columns]\n        audit = workload_rows[audit_cols].sort_values("game_date", ascending=False).head(80).copy()\n        st.dataframe(audit, hide_index=True, width="stretch")\n\nst.divider()\nst.subheader("🧾 Lineup input audit")\n'''
text = replace_once(text, lineup_anchor, workload_section, "history workload audit section")
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Regression tests for cross-market workload behavior and UI contracts.
# ---------------------------------------------------------------------------
Path("tests/test_workload_integration.py").write_text('''import pandas as pd\n\nfrom engine.hits_allowed import project_hits_allowed\nfrom engine.outs_projection import project_total_outs\n\n\ndef _log():\n    return pd.DataFrame({\n        "bf": [21, 22, 23, 24, 25, 26, 25, 24],\n        "hits": [4, 5, 5, 6, 5, 6, 7, 5],\n        "outs": [15, 16, 17, 18, 18, 19, 18, 17],\n        "pitches": [82, 86, 89, 93, 96, 99, 97, 94],\n    })\n\n\ndef test_hits_projection_increases_with_workload_exposure():\n    log = _log()\n    low = project_hits_allowed(log, expected_bf=19, bf_sd=2.5, opponent_hit_rate=.235, seed=11, draws=12000)\n    high = project_hits_allowed(log, expected_bf=27, bf_sd=2.5, opponent_hit_rate=.235, seed=11, draws=12000)\n    assert high.ensemble_mean > low.ensemble_mean\n    assert high.over_probabilities[5.5] > low.over_probabilities[5.5]\n\n\ndef test_outs_projection_increases_with_workload_target():\n    log = _log()\n    low = project_total_outs(log, expected_outs=14.5, workload_sd=3.5, seed=22, draws=12000)\n    high = project_total_outs(log, expected_outs=19.5, workload_sd=3.5, seed=22, draws=12000)\n    assert high.ensemble_mean > low.ensemble_mean\n    assert high.over_probabilities[15.5] > low.over_probabilities[15.5]\n\n\ndef test_outs_old_call_signature_still_works():\n    result = project_total_outs(_log(), seed=1, draws=2000)\n    assert 0 <= result.ensemble_mean <= 27\n''', encoding="utf-8")

Path("tests/test_workload_ui_contract.py").write_text('''from pathlib import Path\n\n\ndef test_daily_runner_uses_shared_workload_for_all_three_markets():\n    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")\n    assert "build_workload_context(log" in source\n    assert '"expected_bf": float(workload.expected_bf)' in source\n    assert "bf_sd=workload.bf_sd" in source\n    assert "expected_outs=workload.expected_outs" in source\n    assert "**workload.snapshot_fields()" in source\n    assert "needs_workload" in source\n\n\ndef test_projection_page_surfaces_workload_intelligence():\n    source = Path("streamlit_app.py").read_text(encoding="utf-8")\n    assert "workload_ctx=build_workload_context" in source\n    assert 'w1.metric("Expected pitches"' in source\n    assert 'w2.metric("Expected BF"' in source\n    assert 'w3.metric("Expected outs"' in source\n    assert "bf_sd=workload_ctx.bf_sd" in source\n\n\ndef test_history_has_direct_workload_validation_and_resolved_only_rolling():\n    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")\n    assert "⚙️ Workload intelligence audit" in source\n    assert "Pitch-count MAE" in source\n    assert "BF MAE" in source\n    assert "resolved_any" in source\n    assert 'current = current.loc[resolved_any]' in source\n\n\ndef test_workload_pages_compile():\n    for path in ["streamlit_app.py", "pages/4_Projection_History.py", "pages/5_Daily_Projection_Run.py"]:\n        source = Path(path).read_text(encoding="utf-8")\n        compile(source, path, "exec")\n''', encoding="utf-8")

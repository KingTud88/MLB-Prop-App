from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


# --- Daily runner ---
path = Path("automation/daily_projection_runner.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from engine.workload_context import WORKLOAD_VERSION, WorkloadContext, build_workload_context\n',
    'from engine.workload_context import WORKLOAD_VERSION, WorkloadContext, build_workload_context\nfrom engine.team_leash import build_team_leash_context, candidate_workload_fields\n',
    "daily runner team leash import",
)
text = replace_once(
    text,
    '''def save_observation_log(frame: pd.DataFrame) -> None:\n    OBS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)\n    out = frame.copy()\n    for col in OBS_COLUMNS:\n        if col not in out.columns:\n            out[col] = np.nan if col.startswith("actual_") or col == "history_games_available_at_capture" else ""\n    out[OBS_COLUMNS].to_csv(OBS_LOG_PATH, index=False)\n\n\n''',
    '''def save_observation_log(frame: pd.DataFrame) -> None:\n    OBS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)\n    out = frame.copy()\n    for col in OBS_COLUMNS:\n        if col not in out.columns:\n            out[col] = np.nan if col.startswith("actual_") or col == "history_games_available_at_capture" else ""\n    out[OBS_COLUMNS].to_csv(OBS_LOG_PATH, index=False)\n\n\ndef load_projection_context_log() -> pd.DataFrame:\n    if not LOG_PATH.exists():\n        return pd.DataFrame()\n    try:\n        return pd.read_csv(LOG_PATH)\n    except Exception:\n        return pd.DataFrame()\n\n\n''',
    "projection context loader",
)
text = replace_once(
    text,
    '''                    "team": TEAM_ABBR.get(tn.get("id"), tn.get("abbreviation", "UNK")),\n                    "opponent": TEAM_ABBR.get(on.get("id"), on.get("abbreviation", "UNK")),\n''',
    '''                    "team": TEAM_ABBR.get(tn.get("id"), tn.get("abbreviation", "UNK")),\n                    "team_id": int(tn.get("id")) if tn.get("id") else None,\n                    "opponent": TEAM_ABBR.get(on.get("id"), on.get("abbreviation", "UNK")),\n''',
    "schedule team id",
)
text = replace_once(
    text,
    '''    workload = build_workload_context(log, row.get("game_time") or row.get("game_date"))\n    matchup = matchup_override or matchup_context(\n''',
    '''    workload = build_workload_context(log, row.get("game_time") or row.get("game_date"))\n    team_leash = build_team_leash_context(\n        load_projection_context_log(), load_observation_log(), str(row.get("team", "UNK")),\n        row.get("game_time") or row.get("game_date"),\n    )\n    team_leash_candidate = candidate_workload_fields(\n        team_leash, workload.expected_pitches, workload.expected_bf, workload.expected_outs\n    )\n    matchup = matchup_override or matchup_context(\n''',
    "project team leash context",
)
text = replace_once(
    text,
    '''        "player": row["player"], "team": row["team"], "opponent": row["opponent"], "opponent_team_id": row.get("opponent_team_id"), "venue_id": row.get("venue_id", 0), "venue": row["venue"],\n''',
    '''        "player": row["player"], "team": row["team"], "team_id": row.get("team_id"), "opponent": row["opponent"], "opponent_team_id": row.get("opponent_team_id"), "venue_id": row.get("venue_id", 0), "venue": row["venue"],\n''',
    "snapshot team id",
)
text = replace_once(
    text,
    '''        **workload.snapshot_fields(),\n        "workload_preupgrade_projection": np.nan, "workload_preupgrade_hits_projection": np.nan,\n''',
    '''        **workload.snapshot_fields(),\n        **team_leash.snapshot_fields(),\n        **team_leash_candidate,\n        "workload_preupgrade_projection": np.nan, "workload_preupgrade_hits_projection": np.nan,\n''',
    "snapshot team leash fields",
)
text = replace_once(
    text,
    '''def attach_pregame_weather(frame: pd.DataFrame, announced: list[dict]) -> int:\n''',
    '''def attach_pregame_team_leash(frame: pd.DataFrame) -> int:\n    """Refresh context-only team leash metadata for still-pregame snapshots.\n\n    The baseball projection fields are never rewritten here. Team context is\n    reconstructed from strictly earlier resolved starts, so same-day outcomes\n    cannot leak into the current slate.\n    """\n    if frame.empty:\n        return 0\n    now = datetime.now(timezone.utc)\n    observations = load_observation_log()\n    updated = 0\n    for idx in frame.index:\n        row = frame.loc[idx]\n        if not row_is_pregame(row, now):\n            continue\n        context = build_team_leash_context(\n            frame, observations, str(row.get("team", "UNK")), row.get("game_time") or row.get("game_date")\n        )\n        fields = context.snapshot_fields()\n        expected_pitches = pd.to_numeric(pd.Series([row.get("expected_pitches")]), errors="coerce").iloc[0]\n        expected_bf = pd.to_numeric(pd.Series([row.get("expected_bf")]), errors="coerce").iloc[0]\n        expected_outs = pd.to_numeric(pd.Series([row.get("expected_outs")]), errors="coerce").iloc[0]\n        if pd.notna(expected_pitches) and pd.notna(expected_bf) and pd.notna(expected_outs):\n            fields.update(candidate_workload_fields(context, float(expected_pitches), float(expected_bf), float(expected_outs)))\n        changed = False\n        for name, value in fields.items():\n            old = row.get(name)\n            if pd.isna(value):\n                same = pd.isna(old)\n            elif isinstance(value, float):\n                old_num = pd.to_numeric(pd.Series([old]), errors="coerce").iloc[0]\n                same = pd.notna(old_num) and abs(float(old_num) - value) < 1e-12\n            else:\n                same = str(old) == str(value)\n            if not same:\n                frame.at[idx, name] = value\n                changed = True\n        if changed:\n            updated += 1\n    return updated\n\n\ndef attach_pregame_weather(frame: pd.DataFrame, announced: list[dict]) -> int:\n''',
    "pregame team leash refresh",
)
text = replace_once(
    text,
    '''    weather_refreshes = attach_pregame_weather(frame, rows)\n    lineup_refreshes = 0\n''',
    '''    weather_refreshes = attach_pregame_weather(frame, rows)\n    team_leash_refreshes = attach_pregame_team_leash(frame)\n    lineup_refreshes = 0\n''',
    "main initial team leash refresh",
)
text = replace_once(
    text,
    '''    if new_rows:\n        frame = pd.concat([frame, pd.DataFrame(new_rows)], ignore_index=True)\n\n    if "probability_semantics" not in frame.columns:\n''',
    '''    if new_rows:\n        frame = pd.concat([frame, pd.DataFrame(new_rows)], ignore_index=True)\n        team_leash_refreshes += attach_pregame_team_leash(frame)\n\n    if "probability_semantics" not in frame.columns:\n''',
    "main post-new team leash refresh",
)
text = replace_once(
    text,
    '''        f"projection log rows={len(frame)} new={len(new_rows)} pregame_path_refreshes={refreshed} weather_refreshes={weather_refreshes} lineup_refreshes={lineup_refreshes} "\n''',
    '''        f"projection log rows={len(frame)} new={len(new_rows)} pregame_path_refreshes={refreshed} weather_refreshes={weather_refreshes} team_leash_refreshes={team_leash_refreshes} lineup_refreshes={lineup_refreshes} "\n''',
    "main team leash log",
)
path.write_text(text, encoding="utf-8")


# --- Daily Projection page ---
path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    attach_pregame_weather,\n    refresh_pregame_lineups,\n''',
    '''    attach_pregame_weather,\n    attach_pregame_team_leash,\n    refresh_pregame_lineups,\n''',
    "daily page team leash import",
)
text = replace_once(
    text,
    '''    refreshed = fill_missing_pregame_paths(frame)\n    weather_refreshed = attach_pregame_weather(frame, announced)\n    lineup_refreshed = refresh_pregame_lineups(frame, announced)\n    save_log(frame)\n\n    slate = frame.loc[frame.get("game_date", pd.Series(dtype=str)).astype(str).eq(day)].copy() if not frame.empty else pd.DataFrame()\n    return slate, len(new_rows), skipped + refreshed + weather_refreshed + lineup_refreshed, history_only, errors\n''',
    '''    refreshed = fill_missing_pregame_paths(frame)\n    weather_refreshed = attach_pregame_weather(frame, announced)\n    team_leash_refreshed = attach_pregame_team_leash(frame)\n    lineup_refreshed = refresh_pregame_lineups(frame, announced)\n    save_log(frame)\n\n    slate = frame.loc[frame.get("game_date", pd.Series(dtype=str)).astype(str).eq(day)].copy() if not frame.empty else pd.DataFrame()\n    return slate, len(new_rows), skipped + refreshed + weather_refreshed + team_leash_refreshed + lineup_refreshed, history_only, errors\n''',
    "daily page run refresh",
)
text = replace_once(
    text,
    '''        "Pitch trend": _num(row, "pitch_trend"),\n    }\n''',
    '''        "Pitch trend": _num(row, "pitch_trend"),\n        "Team leash role": row.get("team_leash_role", "—"),\n        "Team leash status": row.get("team_leash_status", "—"),\n        "Team leash label": row.get("team_leash_label", "—"),\n        "Team starts tracked": int(_num(row, "team_leash_starts") or 0),\n        "Team avg pitches": _num(row, "team_leash_avg_pitches"),\n        "Team TTO reach rate": _num(row, "team_leash_tto_reach_rate"),\n        "Team 90+ pitch rate": _num(row, "team_leash_90_pitch_rate"),\n        "Candidate pitch multiplier": _num(row, "team_leash_pitch_multiplier_candidate"),\n    }\n''',
    "daily rationale team leash",
)
text = replace_once(
    text,
    '''            "workload_version", "expected_pitches", "expected_bf", "expected_outs", "pitches_per_bf", "days_since_last_start", "leash_label", "pitch_trend",\n            "probability_semantics", "actual_strikeouts", "actual_hits_allowed", "actual_outs",\n''',
    '''            "workload_version", "expected_pitches", "expected_bf", "expected_outs", "pitches_per_bf", "days_since_last_start", "leash_label", "pitch_trend",\n            "team_leash_label", "team_leash_status", "team_leash_starts", "team_leash_avg_pitches", "team_leash_tto_reach_rate", "team_leash_90_pitch_rate", "team_leash_pitch_multiplier_candidate", "team_leash_role",\n            "probability_semantics", "actual_strikeouts", "actual_hits_allowed", "actual_outs",\n''',
    "daily display team leash cols",
)
text = replace_once(
    text,
    '''                "pitch_trend": "Pitch Trend",\n                "weather_delay_risk": "Weather Risk",\n''',
    '''                "pitch_trend": "Pitch Trend",\n                "team_leash_label": "Team Leash",\n                "team_leash_status": "Team Leash Status",\n                "team_leash_starts": "Team Starts",\n                "team_leash_avg_pitches": "Team Avg Pitches",\n                "team_leash_tto_reach_rate": "TTO Reach Rate",\n                "team_leash_90_pitch_rate": "90+ Pitch Rate",\n                "team_leash_pitch_multiplier_candidate": "Pitch Adj Candidate",\n                "team_leash_role": "Team Leash Role",\n                "weather_delay_risk": "Weather Risk",\n''',
    "daily display team leash rename",
)
path.write_text(text, encoding="utf-8")


# --- Single-pitcher app ---
path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from engine.workload_context import WorkloadContext, build_workload_context\n',
    'from engine.workload_context import WorkloadContext, build_workload_context\nfrom engine.team_leash import build_team_leash_context, candidate_workload_fields\n',
    "app team leash import",
)
text = replace_once(
    text,
    'BET_LOG = APP_DIR / "data" / "bet_log.csv"\n',
    'BET_LOG = APP_DIR / "data" / "bet_log.csv"\nOBS_LOG = APP_DIR / "data" / "starter_observation_log.csv"\n',
    "app observation path",
)
text = replace_once(
    text,
    '''def load_projection_history():\n    try:return pd.read_csv(APP_DIR / "data" / "projection_log.csv")\n    except Exception:return pd.DataFrame()\n\ndef calibrated_weights(history): return {line:calibrate_blend(history,line) for line in range(3,11)}\n''',
    '''def load_projection_history():\n    try:return pd.read_csv(APP_DIR / "data" / "projection_log.csv")\n    except Exception:return pd.DataFrame()\n\ndef load_observation_history():\n    try:return pd.read_csv(OBS_LOG)\n    except Exception:return pd.DataFrame()\n\ndef calibrated_weights(history): return {line:calibrate_blend(history,line) for line in range(3,11)}\n''',
    "app observation loader",
)
text = replace_once(
    text,
    '''workload_ctx=build_workload_context(log,game.game_time)\nproj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count,workload_ctx); kdf=ladder(proj,10)\n''',
    '''workload_ctx=build_workload_context(log,game.game_time)\nteam_leash_ctx=build_team_leash_context(load_projection_history(),load_observation_history(),game.team,game.game_time)\nteam_leash_candidate=candidate_workload_fields(team_leash_ctx,workload_ctx.expected_pitches,workload_ctx.expected_bf,workload_ctx.expected_outs)\nproj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count,workload_ctx); kdf=ladder(proj,10)\n''',
    "app team leash context",
)
text = replace_once(
    text,
    '''    st.caption(f"Pitch trend {workload_ctx.pitch_trend:+.1%} · BF trend {workload_ctx.bf_trend:+.1%} · outs trend {workload_ctx.outs_trend:+.1%} · short-rest exposure multiplier {workload_ctx.rest_multiplier:.3f}.")\n    d=log.tail(15).copy(); st.line_chart(d.set_index("date")[["pitches","bf","outs","k"]]); st.dataframe(d.sort_values("date",ascending=False),use_container_width=True,hide_index=True); st.stop()\n''',
    '''    st.caption(f"Pitch trend {workload_ctx.pitch_trend:+.1%} · BF trend {workload_ctx.bf_trend:+.1%} · outs trend {workload_ctx.outs_trend:+.1%} · short-rest exposure multiplier {workload_ctx.rest_multiplier:.3f}.")\n    st.markdown("#### 🧭 Team leash candidate · CONTEXT ONLY")\n    t1,t2,t3,t4,t5,t6=st.columns(6)\n    t1.metric("Team starts tracked",team_leash_ctx.starts_used)\n    t2.metric("Team avg pitches",f"{team_leash_ctx.team_avg_pitches:.1f}")\n    t3.metric("Team avg BF",f"{team_leash_ctx.team_avg_bf:.1f}")\n    t4.metric("TTO reached",f"{team_leash_ctx.tto_reach_rate:.1%}")\n    t5.metric("90+ pitches",f"{team_leash_ctx.pitch_90_rate:.1%}")\n    t6.metric("Team leash",team_leash_ctx.label)\n    st.caption(\n        f"Status {team_leash_ctx.status} · candidate-only multipliers: pitches {team_leash_ctx.pitch_multiplier_candidate:.3f}, "\n        f"BF {team_leash_ctx.bf_multiplier_candidate:.3f}, outs {team_leash_ctx.outs_multiplier_candidate:.3f}. "\n        "These values do not alter Ks, Hits Allowed, Outs, or Top Plays until leakage-safe validation earns that right."\n    )\n    d=log.tail(15).copy(); st.line_chart(d.set_index("date")[["pitches","bf","outs","k"]]); st.dataframe(d.sort_values("date",ascending=False),use_container_width=True,hide_index=True); st.stop()\n''',
    "app workload team leash UI",
)
path.write_text(text, encoding="utf-8")


# --- Signal validation context bucket ---
path = Path("engine/signal_validation.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    if "weather_delay_risk" in current.columns:\n        dimensions.append(("Weather Delay Risk", current["weather_delay_risk"].fillna("UNKNOWN").astype(str), "CONTEXT ONLY"))\n''',
    '''    if "team_leash_label" in current.columns:\n        dimensions.append(("Team Leash Candidate", current["team_leash_label"].fillna("UNKNOWN").astype(str), "CONTEXT ONLY"))\n    if "weather_delay_risk" in current.columns:\n        dimensions.append(("Weather Delay Risk", current["weather_delay_risk"].fillna("UNKNOWN").astype(str), "CONTEXT ONLY"))\n''',
    "signal context team leash",
)
path.write_text(text, encoding="utf-8")


# --- Projection History ---
path = Path("pages/4_Projection_History.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from engine.signal_validation import context_performance_report, paired_signal_report\n',
    'from engine.signal_validation import context_performance_report, paired_signal_report\nfrom engine.team_leash import team_leash_walk_forward_report\n',
    "history team leash import",
)
text = replace_once(
    text,
    'LOG_PATH = ROOT / "data" / "projection_log.csv"\n',
    'LOG_PATH = ROOT / "data" / "projection_log.csv"\nOBS_LOG_PATH = ROOT / "data" / "starter_observation_log.csv"\n',
    "history observation path",
)
text = replace_once(
    text,
    '''def load_projection_history() -> pd.DataFrame:\n    if not LOG_PATH.exists():\n        return pd.DataFrame()\n    try:\n        return pd.read_csv(LOG_PATH)\n    except Exception:\n        return pd.DataFrame()\n\n\n''',
    '''def load_projection_history() -> pd.DataFrame:\n    if not LOG_PATH.exists():\n        return pd.DataFrame()\n    try:\n        return pd.read_csv(LOG_PATH)\n    except Exception:\n        return pd.DataFrame()\n\n\ndef load_observation_history() -> pd.DataFrame:\n    if not OBS_LOG_PATH.exists():\n        return pd.DataFrame()\n    try:\n        return pd.read_csv(OBS_LOG_PATH)\n    except Exception:\n        return pd.DataFrame()\n\n\n''',
    "history observation loader",
)
text = replace_once(
    text,
    '''    st.caption("HELPING requires at least 20 resolved pairs, at least 5% lower post-upgrade MAE, and improvement in at least 55% of paired starts. HURTING uses the symmetric downside guardrail. These labels do not alter Top Plays yet.")\n\nwith st.expander("Context performance — descriptive, not causal", expanded=False):\n''',
    '''    st.caption("HELPING requires at least 20 resolved pairs, at least 5% lower post-upgrade MAE, and improvement in at least 55% of paired starts. HURTING uses the symmetric downside guardrail. These labels do not alter Top Plays yet.")\n\nst.markdown("#### 🧭 Team leash candidate · workload backtest")\nst.caption(\n    "Team/organization starter usage is reconstructed chronologically from resolved frozen starts. For each evaluated game, the candidate adjustment can use only earlier game dates. "\n    "It compares candidate pitches/BF/outs against the existing workload-v1 baseline, but remains CONTEXT ONLY and does not change the baseball forecast."\n)\nteam_leash_report = team_leash_walk_forward_report(df, load_observation_history())\nif team_leash_report.empty:\n    st.info("Team leash validation is waiting for workload-v1 snapshots with resolved workload outcomes.")\nelse:\n    team_view = team_leash_report.copy()\n    for col in ["Relative MAE Improvement", "Improved Share"]:\n        team_view[col] = team_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if col == "Relative MAE Improvement" else f"{float(x):.1%}")\n    for col in ["Baseline MAE", "Candidate MAE", "MAE Improvement", "Baseline Bias", "Candidate Bias"]:\n        team_view[col] = team_view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.3f}" if col in {"MAE Improvement", "Baseline Bias", "Candidate Bias"} else f"{float(x):.3f}")\n    st.dataframe(team_view, hide_index=True, width="stretch")\n    st.caption("Team leash needs 12 prior team starts before a candidate adjustment is evaluated, then 20 leakage-safe evaluated starts before HELPING/MIXED/HURTING can be assigned. Until we explicitly promote it later, it has zero projection or Top Plays influence.")\n\nwith st.expander("Context performance — descriptive, not causal", expanded=False):\n''',
    "history team leash report",
)
text = replace_once(
    text,
    '''        st.caption("Lineup, workload, rest, history source, opponent K/contact environments are model inputs. Weather Delay Risk is labeled CONTEXT ONLY because weather still does not modify the baseball forecast.")\n''',
    '''        st.caption("Lineup, workload, rest, history source, opponent K/contact environments are model inputs. Team Leash Candidate and Weather Delay Risk are CONTEXT ONLY and do not modify the baseball forecast.")\n''',
    "history context caption",
)
path.write_text(text, encoding="utf-8")


# --- Tests ---
Path("tests/test_team_leash.py").write_text(r'''import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS
from engine.team_leash import (
    MIN_TEAM_STARTS,
    build_team_leash_context,
    candidate_workload_fields,
    team_leash_walk_forward_report,
)


def _history(days=50):
    rows = []
    pk = 1000
    for i in range(days):
        day = pd.Timestamp("2026-04-01") + pd.Timedelta(days=i)
        for team, pitches, bf, outs in (("AAA", 80.0, 20.0, 14.0), ("BBB", 100.0, 24.0, 18.0)):
            rows.append({
                "game_pk": pk,
                "pitcher_id": pk + 5000,
                "game_date": day.date().isoformat(),
                "team": team,
                "history_semantics": HISTORY_SEMANTICS,
                "workload_version": "workload-v1",
                "expected_pitches": 90.0,
                "expected_bf": 22.0,
                "expected_outs": 16.0,
                "actual_pitches": pitches,
                "actual_batters_faced": bf,
                "actual_outs": outs,
            })
            pk += 1
    return pd.DataFrame(rows)


def test_small_team_sample_is_neutral_and_context_only():
    frame = _history(MIN_TEAM_STARTS - 1)
    target = (pd.Timestamp("2026-04-01") + pd.Timedelta(days=MIN_TEAM_STARTS)).date().isoformat()
    ctx = build_team_leash_context(frame, pd.DataFrame(), "AAA", target)
    assert ctx.status == "LEARNING"
    assert ctx.role == "CONTEXT_ONLY"
    assert ctx.pitch_multiplier_candidate == 1.0
    assert ctx.bf_multiplier_candidate == 1.0
    assert ctx.outs_multiplier_candidate == 1.0


def test_same_day_and_future_outcomes_cannot_leak_into_context():
    frame = _history(30)
    target = "2026-04-20"
    before = build_team_leash_context(frame, pd.DataFrame(), "AAA", target).snapshot_fields()
    changed = frame.copy()
    changed.loc[pd.to_datetime(changed["game_date"]) >= pd.Timestamp(target), ["actual_pitches", "actual_batters_faced", "actual_outs"]] = [120.0, 35.0, 27.0]
    after = build_team_leash_context(changed, pd.DataFrame(), "AAA", target).snapshot_fields()
    assert before == after


def test_sportsbook_fields_do_not_change_team_leash_context():
    frame = _history(30)
    target = "2026-05-05"
    clean = build_team_leash_context(frame, pd.DataFrame(), "AAA", target).snapshot_fields()
    noisy = frame.copy()
    noisy["Odds"] = -110
    noisy["Book"] = "ExampleBook"
    noisy["Edge"] = 0.99
    altered = build_team_leash_context(noisy, pd.DataFrame(), "AAA", target).snapshot_fields()
    assert clean == altered


def test_candidate_fields_do_not_mutate_baseline_workload():
    frame = _history(30)
    ctx = build_team_leash_context(frame, pd.DataFrame(), "AAA", "2026-05-10")
    baseline = (90.0, 22.0, 16.0)
    fields = candidate_workload_fields(ctx, *baseline)
    assert baseline == (90.0, 22.0, 16.0)
    assert fields["team_leash_candidate_expected_pitches"] < baseline[0]
    assert fields["team_leash_candidate_expected_bf"] < baseline[1]
    assert fields["team_leash_candidate_expected_outs"] < baseline[2]


def test_walk_forward_candidate_detects_helpful_team_usage_signal():
    frame = _history(55)
    report = team_leash_walk_forward_report(frame, pd.DataFrame())
    assert set(report["Target"]) == {"Pitches", "Batters Faced", "Outs"}
    assert (report["Evaluated Starts"] >= 20).all()
    assert (report["Candidate MAE"] < report["Baseline MAE"]).all()
    assert (report["Status"] == "HELPING").all()


def test_walk_forward_report_ignores_sportsbook_columns():
    frame = _history(55)
    clean = team_leash_walk_forward_report(frame, pd.DataFrame())
    noisy = frame.copy()
    noisy["sportsbook_price"] = 12345
    noisy["saved_bet"] = True
    altered = team_leash_walk_forward_report(noisy, pd.DataFrame())
    pd.testing.assert_frame_equal(clean, altered)
''', encoding="utf-8")

Path("tests/test_team_leash_ui_contract.py").write_text(r'''from pathlib import Path


def test_team_leash_is_context_only_in_live_projection_ui():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "Team leash candidate · CONTEXT ONLY" in source
    assert "These values do not alter Ks, Hits Allowed, Outs, or Top Plays" in source
    build_pos = source.index("workload_ctx=build_workload_context")
    leash_pos = source.index("team_leash_ctx=build_team_leash_context")
    projection_pos = source.index("proj=calculate_projection", leash_pos)
    assert build_pos < leash_pos < projection_pos
    # The live projection still receives the unmodified workload context.
    assert "confirmed_count,workload_ctx" in source[projection_pos:projection_pos + 250]


def test_daily_snapshot_logs_candidate_without_using_it_as_expected_bf():
    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    assert "**team_leash.snapshot_fields()" in source
    assert "**team_leash_candidate" in source
    assert 'expected_bf=f["expected_bf"]' in source
    assert "team_leash_candidate_expected_bf" not in source[source.index("hits = project_hits_allowed"):source.index("outs = project_total_outs")]


def test_projection_history_explicitly_keeps_team_leash_out_of_forecast():
    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    assert "Team leash candidate · workload backtest" in source
    assert "remains CONTEXT ONLY and does not change the baseball forecast" in source
    assert "zero projection or Top Plays influence" in source
''', encoding="utf-8")

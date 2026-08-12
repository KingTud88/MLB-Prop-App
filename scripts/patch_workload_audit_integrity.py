from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor not found: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Workload date handling: MLB game_time is UTC-aware while game-log dates are
# typically date-only. Compare calendar dates so the live slate cannot fail on
# tz-aware vs tz-naive timestamps.
# ---------------------------------------------------------------------------
path = Path("engine/workload_context.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    target = pd.to_datetime(game_date, errors="coerce") if game_date is not None else pd.NaT\n    if pd.notna(target):\n        target_day = pd.Timestamp(target).normalize()\n        dated = starts["date"].notna()\n        starts = starts.loc[~dated | (starts["date"].dt.normalize() < target_day)].copy()\n''',
    '''    target = pd.to_datetime(game_date, errors="coerce", utc=True) if game_date is not None else pd.NaT\n    if pd.notna(target):\n        target_day = pd.Timestamp(target).date()\n        dated = starts["date"].notna()\n        start_days = starts["date"].dt.date\n        starts = starts.loc[~dated | (start_days < target_day)].copy()\n''',
    "workload timezone-safe pregame filter",
)
text = replace_once(
    text,
    '''    target = pd.to_datetime(game_date, errors="coerce") if game_date is not None else pd.NaT\n    dated = starts["date"].dropna()\n    if pd.notna(target) and not dated.empty:\n        delta = pd.Timestamp(target).normalize() - pd.Timestamp(dated.iloc[-1]).normalize()\n        days_since_last_start = max(int(delta.days), 0)\n''',
    '''    target = pd.to_datetime(game_date, errors="coerce", utc=True) if game_date is not None else pd.NaT\n    dated = starts["date"].dropna()\n    if pd.notna(target) and not dated.empty:\n        last_start = pd.to_datetime(dated.iloc[-1], errors="coerce", utc=True)\n        if pd.notna(last_start):\n            delta = pd.Timestamp(target).date() - pd.Timestamp(last_start).date()\n            days_since_last_start = max(int(delta.days), 0)\n''',
    "workload timezone-safe rest days",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Daily runner: isolate workload-v1 upgrade from lineup changes and seed drift.
# ---------------------------------------------------------------------------
path = Path("automation/daily_projection_runner.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''def project(row: dict) -> dict | None:\n''',
    '''def project(row: dict, matchup_override: dict[str, object] | None = None) -> dict | None:\n''',
    "project matchup override signature",
)
text = replace_once(
    text,
    '''    matchup = matchup_context(\n        row["game_pk"], row["opponent"], row["pitcher_id"], season, row.get("opponent_team_id")\n    )\n''',
    '''    matchup = matchup_override or matchup_context(\n        row["game_pk"], row["opponent"], row["pitcher_id"], season, row.get("opponent_team_id")\n    )\n''',
    "project matchup override use",
)
text = replace_once(
    text,
    '''    seed = int(hashlib.sha256(f"{row['game_pk']}:{row['pitcher_id']}|{row['game_time']}|{APP_VERSION}".encode()).hexdigest()[:8], 16)\n''',
    '''    seed_version = str(row.get("seed_version") or APP_VERSION)\n    seed = int(hashlib.sha256(f"{row['game_pk']}:{row['pitcher_id']}|{row['game_time']}|{seed_version}".encode()).hexdigest()[:8], 16)\n''',
    "stable workload comparison seed",
)
text = replace_once(
    text,
    '''        "workload_projection_delta_k": np.nan, "workload_projection_delta_hits": np.nan,\n        "workload_projection_delta_outs": np.nan,\n''',
    '''        "workload_projection_delta_k": np.nan, "workload_projection_delta_hits": np.nan,\n        "workload_projection_delta_outs": np.nan, "workload_preupgrade_app_version": "",\n        "workload_upgraded_at_utc": "",\n''',
    "workload audit metadata fields",
)
text = replace_once(
    text,
    '''        "pitch_limit": 92, "umpire_k_factor": 1.0,\n''',
    '''        "pitch_limit": float(workload.expected_pitches), "umpire_k_factor": 1.0,\n''',
    "compat pitch limit reflects workload",
)

# Preserve workload audit evidence when a later confirmed-lineup refresh rewrites
# the current pregame projection fields.
old_protected = '''        protected = {"actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches", "resolved_at_utc"}\n'''
new_protected = '''        protected = {\n            "actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches", "resolved_at_utc",\n            "workload_preupgrade_projection", "workload_preupgrade_hits_projection", "workload_preupgrade_outs_projection",\n            "workload_preupgrade_expected_bf", "workload_projection_delta_k", "workload_projection_delta_hits",\n            "workload_projection_delta_outs", "workload_preupgrade_app_version", "workload_upgraded_at_utc",\n        }\n'''
text = replace_once(text, old_protected, new_protected, "lineup protects workload audit")

# Helper reconstructs the matchup inputs already frozen on an older snapshot.
anchor = '''def fill_missing_pregame_paths(frame: pd.DataFrame) -> int:\n'''
helper = '''def snapshot_matchup_override(row: pd.Series) -> dict[str, object]:\n    def _rate(name: str, fallback: float) -> float:\n        value = pd.to_numeric(pd.Series([row.get(name)]), errors="coerce").iloc[0]\n        if pd.isna(value):\n            return float(fallback)\n        value = float(value)\n        return value / 100.0 if value > 1.0 else value\n\n    confirmed_text = str(row.get("lineup_confirmed", "")).strip().lower()\n    confirmed = confirmed_text in {"true", "1", "yes"}\n    return {\n        "k_rate": float(np.clip(_rate("opponent_k_pct", .224), .08, .45)),\n        "hit_rate": float(np.clip(_rate("opponent_hit_rate", .235), .12, .36)),\n        "pa": int(pd.to_numeric(pd.Series([row.get("matchup_pa")]), errors="coerce").fillna(0).iloc[0]),\n        "batters": int(pd.to_numeric(pd.Series([row.get("matchup_batters")]), errors="coerce").fillna(0).iloc[0]),\n        "lineup_batters": int(pd.to_numeric(pd.Series([row.get("lineup_batters")]), errors="coerce").fillna(0).iloc[0]),\n        "source": str(row.get("lineup_source", LINEUP_ACTIVE_ROSTER) or LINEUP_ACTIVE_ROSTER),\n        "confirmed": confirmed,\n        "lineup_hash": str(row.get("lineup_hash", "") or ""),\n    }\n\n\n'''
if anchor not in text:
    raise SystemExit("snapshot matchup override anchor missing")
text = text.replace(anchor, helper + anchor, 1)

old_project_call = '''            projected = project({\n                "game_pk": int(row["game_pk"]),\n                "game_date": str(row["game_date"]),\n                "pitcher_id": int(row["pitcher_id"]),\n                "player": row.get("player", "Unknown"),\n                "team": row.get("team", "UNK"),\n                "opponent": row.get("opponent", "UNK"),\n                "opponent_team_id": int(row["opponent_team_id"]) if pd.notna(row.get("opponent_team_id")) else None,\n                "venue_id": int(row["venue_id"]) if pd.notna(row.get("venue_id")) else 0,\n                "venue": row.get("venue", "Unknown"),\n                "game_time": row.get("game_time", ""),\n                "status": row.get("status", "Scheduled"),\n            })\n'''
new_project_call = '''            refresh_row = {\n                "game_pk": int(row["game_pk"]),\n                "game_date": str(row["game_date"]),\n                "pitcher_id": int(row["pitcher_id"]),\n                "player": row.get("player", "Unknown"),\n                "team": row.get("team", "UNK"),\n                "opponent": row.get("opponent", "UNK"),\n                "opponent_team_id": int(row["opponent_team_id"]) if pd.notna(row.get("opponent_team_id")) else None,\n                "venue_id": int(row["venue_id"]) if pd.notna(row.get("venue_id")) else 0,\n                "venue": row.get("venue", "Unknown"),\n                "game_time": row.get("game_time", ""),\n                "status": row.get("status", "Scheduled"),\n                # Preserve the original deterministic seed during a workload-only\n                # comparison so app-version seed drift is not mislabeled as workload impact.\n                "seed_version": row.get("app_version", APP_VERSION) if needs_workload else APP_VERSION,\n            }\n            projected = project(\n                refresh_row,\n                matchup_override=snapshot_matchup_override(row) if needs_workload else None,\n            )\n'''
text = replace_once(text, old_project_call, new_project_call, "isolated workload refresh project call")
text = replace_once(
    text,
    '''            protected = {\n                "actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches", "resolved_at_utc",\n                "lineup_preconfirm_projection", "lineup_preconfirm_opponent_k_pct", "lineup_projection_delta", "lineup_opponent_k_delta",\n            }\n''',
    '''            protected = {\n                "actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches", "resolved_at_utc",\n                "lineup_preconfirm_projection", "lineup_preconfirm_opponent_k_pct", "lineup_projection_delta", "lineup_opponent_k_delta",\n            }\n''',
    "workload refresh protected anchor",
)
text = replace_once(
    text,
    '''            frame.at[idx, "workload_preupgrade_expected_bf"] = old_bf\n            for old_value, new_key, delta_key in (\n''',
    '''            frame.at[idx, "workload_preupgrade_expected_bf"] = old_bf\n            frame.at[idx, "workload_preupgrade_app_version"] = str(row.get("app_version", "") or "")\n            frame.at[idx, "workload_upgraded_at_utc"] = datetime.now(timezone.utc).isoformat()\n            for old_value, new_key, delta_key in (\n''',
    "workload upgrade timestamp/version",
)

# Scheduled automation must perform workload/path refresh before confirmed-lineup
# refresh so the two audit deltas remain separable.
text = replace_once(
    text,
    '''    weather_refreshes = attach_pregame_weather(frame, rows)\n    lineup_refreshes = refresh_pregame_lineups(frame, rows)\n    existing = set()\n''',
    '''    weather_refreshes = attach_pregame_weather(frame, rows)\n    lineup_refreshes = 0\n    existing = set()\n''',
    "defer scheduled lineup refresh",
)
text = replace_once(
    text,
    '''    refreshed = fill_missing_pregame_paths(frame)\n\n    for line in range(3, 11):\n''',
    '''    refreshed = fill_missing_pregame_paths(frame)\n    lineup_refreshes = refresh_pregame_lineups(frame, rows)\n\n    for line in range(3, 11):\n''',
    "scheduled lineup after workload refresh",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: live UTC game_time date compatibility and audit separation contracts.
# ---------------------------------------------------------------------------
path = Path("tests/test_workload_context.py")
text = path.read_text(encoding="utf-8")
text = text.replace('last = pd.to_datetime(history["date"].iloc[-1])', 'last = pd.Timestamp(history["date"].iloc[-1])')
text += '''\n\ndef test_utc_game_time_works_with_date_only_game_log():\n    history = _log(\n        [88, 91, 94, 96, 97, 99],\n        [22, 23, 24, 24, 25, 25],\n        [15, 16, 17, 17, 18, 18],\n        dates=["2026-07-01", "2026-07-07", "2026-07-13", "2026-07-19", "2026-07-25", "2026-08-06"],\n    )\n    ctx = build_workload_context(history, "2026-08-12T23:10:00Z")\n    assert ctx.starts_used == 6\n    assert ctx.days_since_last_start == 6\n    assert 60 <= ctx.expected_pitches <= 112\n'''
path.write_text(text, encoding="utf-8")

path = Path("tests/test_workload_ui_contract.py")
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_workload_upgrade_isolated_from_lineup_and_seed_drift():\n    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")\n    assert "snapshot_matchup_override(row) if needs_workload else None" in source\n    assert '"seed_version": row.get("app_version", APP_VERSION) if needs_workload else APP_VERSION' in source\n    assert '"workload_preupgrade_app_version"' in source\n    assert '"workload_upgraded_at_utc"' in source\n    assert '"workload_projection_delta_k"' in source\n    assert 'lineup_refreshes = 0' in source\n    assert 'lineup_refreshes = refresh_pregame_lineups(frame, rows)' in source\n\n\ndef test_lineup_refresh_preserves_workload_upgrade_audit():\n    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")\n    assert '"workload_preupgrade_projection"' in source\n    assert '"workload_projection_delta_outs"' in source\n    assert '"workload_upgraded_at_utc"' in source\n'''
path.write_text(text, encoding="utf-8")

path = Path("tests/test_matchup_weather_integrity.py")
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_snapshot_matchup_override_preserves_frozen_rates():\n    row = pd.Series({\n        "opponent_k_pct": 27.5, "opponent_hit_rate": 22.0, "matchup_pa": 321,\n        "matchup_batters": 9, "lineup_batters": 0, "lineup_source": "ACTIVE_ROSTER",\n        "lineup_confirmed": False, "lineup_hash": "",\n    })\n    context = runner.snapshot_matchup_override(row)\n    assert abs(context["k_rate"] - .275) < 1e-9\n    assert abs(context["hit_rate"] - .22) < 1e-9\n    assert context["source"] == "ACTIVE_ROSTER"\n    assert context["confirmed"] is False\n'''
path.write_text(text, encoding="utf-8")

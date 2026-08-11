from pathlib import Path
import re

path = Path("automation/daily_projection_runner.py")
text = path.read_text(encoding="utf-8")

if "from engine.outs_projection import project_total_outs" not in text:
    text = text.replace(
        "from engine.hits_allowed import project_hits_allowed\n",
        "from engine.hits_allowed import project_hits_allowed\nfrom engine.outs_projection import project_total_outs\n",
        1,
    )

if "outs = project_total_outs(" not in text:
    pattern = r"(    hits = project_hits_allowed\([\s\S]*?\n    \)\n)(    now = datetime\.now\(timezone\.utc\)\.isoformat\(\)\n)"
    repl = r'''\1    outs = project_total_outs(
        log,
        seed=seed ^ 0x0A75,
        draws=25000,
        lines=(13.5, 14.5, 15.5, 16.5, 17.5, 18.5),
    )
\2'''
    text, n = re.subn(pattern, repl, text, count=1)
    if n != 1:
        raise SystemExit("could not insert outs projection")

if '"outs_projection": outs.ensemble_mean' not in text:
    anchor = '        "hits_range_high": int(np.quantile(hits.simulation_samples, .90)),\n'
    insert = anchor + '        "outs_projection": outs.ensemble_mean, "outs_sd": outs.ensemble_sd,\n        "outs_range_low": int(np.quantile(outs.simulation_samples, .10)),\n        "outs_range_high": int(np.quantile(outs.simulation_samples, .90)),\n'
    if anchor not in text:
        raise SystemExit("outs snapshot anchor missing")
    text = text.replace(anchor, insert, 1)

text = text.replace(
    '        "actual_strikeouts": np.nan, "actual_hits_allowed": np.nan, "resolved_at_utc": "",\n',
    '        "actual_strikeouts": np.nan, "actual_hits_allowed": np.nan, "actual_outs": np.nan, "resolved_at_utc": "",\n',
    1,
)

if 'out[f"outs_sim_over_{key}"]' not in text:
    anchor = '''    for line in (3.5, 4.5, 5.5, 6.5, 7.5, 8.5):
        key = str(line).replace(".", "_")
        out[f"hits_sim_over_{key}"] = hits.simulation_probabilities.get(line, np.nan)
        out[f"hits_math_over_{key}"] = hits.mathematical_probabilities.get(line, np.nan)
        out[f"hits_over_{key}"] = hits.over_probabilities.get(line, np.nan)
'''
    insert = anchor + '''    for line in (13.5, 14.5, 15.5, 16.5, 17.5, 18.5):
        key = str(line).replace(".", "_")
        out[f"outs_sim_over_{key}"] = outs.simulation_probabilities.get(line, np.nan)
        out[f"outs_math_over_{key}"] = outs.mathematical_probabilities.get(line, np.nan)
        out[f"outs_over_{key}"] = outs.over_probabilities.get(line, np.nan)
'''
    if anchor not in text:
        raise SystemExit("outs path loop anchor missing")
    text = text.replace(anchor, insert, 1)

text = text.replace(
    '        needs_hits = pd.isna(row.get("hits_projection"))\n        if ((row_has_complete_paths(row) and row_has_current_semantics(row) and not needs_hits) or not row_is_pregame(row, now)):\n',
    '        needs_hits = pd.isna(row.get("hits_projection"))\n        needs_outs = pd.isna(row.get("outs_projection"))\n        if ((row_has_complete_paths(row) and row_has_current_semantics(row) and not needs_hits and not needs_outs) or not row_is_pregame(row, now)):\n',
    1,
)
text = text.replace(
    '            if key.startswith("sim_") or key.startswith("math_") or key.startswith("hits_") or key in {"probability_semantics"}:\n',
    '            if key.startswith("sim_") or key.startswith("math_") or key.startswith("hits_") or key.startswith("outs_") or key in {"probability_semantics"}:\n',
    1,
)

new_resolver = '''def resolve_row(row: pd.Series) -> tuple[object, object, object, str]:
    if pd.notna(row.get("actual_strikeouts")) and pd.notna(row.get("actual_hits_allowed")) and pd.notna(row.get("actual_outs")):
        return row.get("actual_strikeouts"), row.get("actual_hits_allowed"), row.get("actual_outs"), str(row.get("resolved_at_utc") or "")
    if pd.isna(row.get("game_pk")) or pd.isna(row.get("pitcher_id")):
        return np.nan, np.nan, np.nan, ""
    try:
        data = get_json(f"game/{int(row['game_pk'])}/boxscore", {})
        status = data.get("gameData", {}).get("status", {})
        if status.get("abstractGameState") != "Final":
            return np.nan, np.nan, np.nan, ""
        player = data.get("teams", {}).get("away", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")
        if not player:
            player = data.get("teams", {}).get("home", {}).get("players", {}).get(f"ID{int(row['pitcher_id'])}")
        pitching = (player or {}).get("stats", {}).get("pitching", {})
        ks = pitching.get("strikeOuts")
        hits = pitching.get("hits")
        innings = pitching.get("inningsPitched")
        outs = int(round(parse_ip(innings) * 3)) if innings is not None else np.nan
        if ks is None and hits is None and pd.isna(outs):
            return np.nan, np.nan, np.nan, ""
        return (int(ks) if ks is not None else np.nan), (int(hits) if hits is not None else np.nan), outs, datetime.now(timezone.utc).isoformat()
    except (requests.RequestException, ValueError, TypeError):
        return np.nan, np.nan, np.nan, ""


'''
text, n = re.subn(r"def resolve_row\(row: pd\.Series\)[\s\S]*?\n\ndef main\(\) -> None:\n", new_resolver + "def main() -> None:\n", text, count=1)
if n != 1:
    raise SystemExit("resolver replacement failed")

text = text.replace(
    '            actual_k, actual_hits, resolved = resolve_row(frame.loc[idx])\n',
    '            actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])\n',
    1,
)
text = text.replace(
    '            if pd.notna(actual_hits):\n                frame.at[idx, "actual_hits_allowed"] = actual_hits\n            if resolved:\n',
    '            if pd.notna(actual_hits):\n                frame.at[idx, "actual_hits_allowed"] = actual_hits\n            if pd.notna(actual_outs):\n                frame.at[idx, "actual_outs"] = actual_outs\n            if resolved:\n',
    1,
)

path.write_text(text, encoding="utf-8")

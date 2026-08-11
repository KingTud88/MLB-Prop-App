from pathlib import Path

# Daily runner
path = Path("automation/daily_projection_runner.py")
s = path.read_text(encoding="utf-8")
s = s.replace("from engine.outs_projection import project_total_outs\n", "from engine.outs_projection import project_total_outs\nfrom engine.starter_history import HISTORY_SEMANTICS, TARGET_STARTER_HISTORY, combine_starter_history, starter_only\n", 1)
s = s.replace('APP_VERSION = "3.3.0"', 'APP_VERSION = "3.5.0"', 1)
s = s.replace('                "outs": parse_ip(s.get("inningsPitched", "0.0")) * 3,\n', '                "outs": parse_ip(s.get("inningsPitched", "0.0")) * 3,\n                "games_started": int(float(s.get("gamesStarted", 0) or 0)),\n', 1)
s = s.replace('    return frame.sort_values("date")\n', '    return starter_only(frame)\n', 1)
old = '''def project(row: dict) -> dict | None:\n    log = game_log(row["pitcher_id"], datetime.fromisoformat(row["game_date"]).year)\n    if log.empty:\n        log = game_log(row["pitcher_id"], datetime.fromisoformat(row["game_date"]).year - 1)\n    if log.empty:\n        return None\n    season = datetime.fromisoformat(row["game_date"]).year\n'''
new = '''def project(row: dict) -> dict | None:\n    season = datetime.fromisoformat(row["game_date"]).year\n    current_log = game_log(row["pitcher_id"], season)\n    prior_log = pd.DataFrame()\n    if len(current_log) < TARGET_STARTER_HISTORY:\n        prior_log = game_log(row["pitcher_id"], season - 1)\n    log = combine_starter_history(current_log, prior_log)\n    if log.empty:\n        return None\n'''
if old not in s: raise SystemExit("daily project anchor missing")
s = s.replace(old, new, 1)
s = s.replace('        "probability_semantics": PROBABILITY_SEMANTICS,\n', '        "probability_semantics": PROBABILITY_SEMANTICS,\n        "history_semantics": HISTORY_SEMANTICS, "starter_history_games": int(len(log)),\n', 1)
s = s.replace('    return str(row.get("probability_semantics", "")) == PROBABILITY_SEMANTICS\n', '    return (\n        str(row.get("probability_semantics", "")) == PROBABILITY_SEMANTICS\n        and str(row.get("history_semantics", "")) == HISTORY_SEMANTICS\n    )\n', 1)
path.write_text(s, encoding="utf-8")

# Main projection page
path = Path("streamlit_app.py")
s = path.read_text(encoding="utf-8")
s = s.replace("from engine.outs_calibration import calibrate_outs_blend\n", "from engine.outs_calibration import calibrate_outs_blend\nfrom engine.starter_history import TARGET_STARTER_HISTORY, combine_starter_history, starter_only\n", 1)
s = s.replace('APP_VERSION = "3.4.0"', 'APP_VERSION = "3.5.0"', 1)
s = s.replace('"outs":parse_ip(s.get("inningsPitched","0.0"))*3})', '"outs":parse_ip(s.get("inningsPitched","0.0"))*3,"games_started":int(float(s.get("gamesStarted",0) or 0))})', 1)
s = s.replace('df=pd.DataFrame(rec); return (df.sort_values("date"),None) if not df.empty else (df,"No regular-season game log returned.")', 'df=pd.DataFrame(rec); starts=starter_only(df); return (starts,None) if not starts.empty else (starts,"No regular-season starter game log returned.")', 1)
old = '''log,herr=get_log(game.pitcher_id,selected_date.year)\nif log.empty: log,herr=get_log(game.pitcher_id,selected_date.year-1)\nif log.empty: st.error(herr or "Pitcher history unavailable."); st.stop()\n'''
new = '''log,herr=get_log(game.pitcher_id,selected_date.year)\nif len(log) < TARGET_STARTER_HISTORY:\n    prior,prior_err=get_log(game.pitcher_id,selected_date.year-1)\n    log=combine_starter_history(log,prior)\n    herr=herr or prior_err\nif log.empty: st.error(herr or "Pitcher starter history unavailable."); st.stop()\n'''
if old not in s: raise SystemExit("main history anchor missing")
s = s.replace(old, new, 1)
path.write_text(s, encoding="utf-8")

# Daily page compatibility + transparency
path = Path("pages/5_Daily_Projection_Run.py")
s = path.read_text(encoding="utf-8")
s = s.replace('    if "probability_semantics" not in frame.columns:\n        frame["probability_semantics"] = ""\n', '    if "probability_semantics" not in frame.columns:\n        frame["probability_semantics"] = ""\n    if "history_semantics" not in frame.columns:\n        frame["history_semantics"] = ""\n    if "starter_history_games" not in frame.columns:\n        frame["starter_history_games"] = np.nan\n', 1)
s = s.replace('        "Probability semantics": row.get("probability_semantics", "—"),\n', '        "Probability semantics": row.get("probability_semantics", "—"),\n        "History semantics": row.get("history_semantics", "—"),\n        "Starter appearances used": int(_num(row, "starter_history_games") or 0),\n', 1)
path.write_text(s, encoding="utf-8")

# Top Plays: show starter sample and correlated same-pitcher warning.
path = Path("pages/6_Top_Plays.py")
s = path.read_text(encoding="utf-8")
s = s.replace('view = plays[["Rank", "Status", "Pitcher", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Book", "Odds"]].copy()', 'view = plays[["Rank", "Status", "Pitcher", "Market", "Side", "Line", "Projection", "Model Probability", "Data Quality", "Starter History", "Book", "Odds"]].copy()', 1)
needle = '''if len(selected) >= 2:\n    watch_count = int((selected["Status"].astype(str) == "WATCH").sum())\n'''
repl = '''if len(selected) >= 2:\n    watch_count = int((selected["Status"].astype(str) == "WATCH").sum())\n    duplicate_pitchers = selected["Pitcher"].astype(str).value_counts()\n    correlated = duplicate_pitchers[duplicate_pitchers > 1]\n    if not correlated.empty:\n        st.warning("This parlay contains multiple props for the same pitcher (" + ", ".join(correlated.index.tolist()) + "). Those legs can be correlated; the app does not treat the parlay probability as independent.")\n'''
if needle not in s: raise SystemExit("parlay warning anchor missing")
s = s.replace(needle, repl, 1)
path.write_text(s, encoding="utf-8")

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
history_path = ROOT / "pages" / "4_Projection_History.py"
source = history_path.read_text(encoding="utf-8")

source = source.replace(
    "from engine.execution_history import grade_frozen_execution\n",
    "from engine.execution_history import backfill_legacy_execution_sides, grade_frozen_execution\n",
    1,
)

old_loader = '''def load_user_archive(evidence: pd.DataFrame) -> pd.DataFrame:
    # PROJECTION_HISTORY_DURABLE_ARCHIVE_V1
    durable_manual = load_projection_archive(ARCHIVE_PATH, st.secrets)
    return build_projection_archive_view(evidence, durable_manual)
'''
new_loader = '''def load_user_archive(evidence: pd.DataFrame) -> pd.DataFrame:
    # PROJECTION_HISTORY_DURABLE_ARCHIVE_V1
    durable_manual = load_projection_archive(ARCHIVE_PATH, st.secrets)
    durable_manual, _ = backfill_legacy_execution_sides(durable_manual, evidence)
    return build_projection_archive_view(evidence, durable_manual)
'''
if old_loader not in source:
    raise SystemExit("load_user_archive anchor missing")
source = source.replace(old_loader, new_loader, 1)

old_display = '''display = df.sort_values(["game_date", "captured_at_utc"], ascending=[False, False]).copy()
'''
new_display = '''# Automatic model evidence remains the frozen projection log, with the durable
# manual execution overlay joined only for reporting. Execution lines/sides do
# not feed calibration, model training, or the frozen baseball projection.
_execution_source = user_archive.drop(columns=["_archive_date"], errors="ignore").copy() if not user_archive.empty else df.copy()
display = _execution_source.sort_values(["game_date", "captured_at_utc"], ascending=[False, False]).copy()
for _col in ("manual_outs_line", "manual_hits_allowed_line"):
    if _col in display.columns:
        display[_col] = pd.to_numeric(display[_col], errors="coerce")
for _col in ("manual_outs_side", "manual_hits_allowed_side"):
    if _col not in display.columns:
        display[_col] = ""
display["outs_bet_result"] = display.apply(
    lambda r: grade_frozen_execution(r.get("manual_outs_side"), r.get("manual_outs_line"), r.get("actual_outs")), axis=1
)
display["hits_bet_result"] = display.apply(
    lambda r: grade_frozen_execution(r.get("manual_hits_allowed_side"), r.get("manual_hits_allowed_line"), r.get("actual_hits_allowed")), axis=1
)
'''
if old_display not in source:
    raise SystemExit("automatic evidence display anchor missing")
source = source.replace(old_display, new_display, 1)

old_columns = '''    "hits_projection", "actual_hits_allowed", "hits_error", "hits_range_low", "hits_range_high", "hits_result",
    "outs_projection", "actual_outs", "outs_error", "outs_range_low", "outs_range_high", "outs_result",
'''
new_columns = '''    "hits_projection", "manual_hits_allowed_line", "manual_hits_allowed_side", "actual_hits_allowed", "hits_bet_result", "hits_error", "hits_range_low", "hits_range_high", "hits_result",
    "outs_projection", "manual_outs_line", "manual_outs_side", "actual_outs", "outs_bet_result", "outs_error", "outs_range_low", "outs_range_high", "outs_result",
'''
if old_columns not in source:
    raise SystemExit("display_columns anchor missing")
source = source.replace(old_columns, new_columns, 1)

old_format_loop = '''for col in ["actual_strikeouts", "actual_hits_allowed", "actual_outs", "k_range_low", "k_range_high", "hits_range_low", "hits_range_high", "outs_range_low", "outs_range_high", "starter_history_games", "starter_history_mlb_games", "starter_history_observation_games"]:
'''
new_format_loop = '''for col in ["actual_strikeouts", "actual_hits_allowed", "actual_outs", "k_range_low", "k_range_high", "hits_range_low", "hits_range_high", "outs_range_low", "outs_range_high", "starter_history_games", "starter_history_mlb_games", "starter_history_observation_games"]:
'''
# Keep the existing actual/range formatter and add manual-line formatting after it.
if old_format_loop not in source:
    raise SystemExit("format loop anchor missing")
source = source.replace(old_format_loop, new_format_loop, 1)
format_anchor = '''    if col in archive_view.columns:
        archive_formats[col] = "{:.0f}"

archive_column_config = {
'''
format_replacement = '''    if col in archive_view.columns:
        archive_formats[col] = "{:.0f}"
for col in ["manual_hits_allowed_line", "manual_outs_line"]:
    if col in archive_view.columns:
        archive_formats[col] = "{:.1f}"

archive_column_config = {
'''
if format_anchor not in source:
    raise SystemExit("archive format insertion anchor missing")
source = source.replace(format_anchor, format_replacement, 1)

config_anchor = '''    "hits_projection": st.column_config.NumberColumn("Projected Hits", format="%.2f"),
    "hits_range_low": st.column_config.NumberColumn("80% H Low", format="%.0f"),
'''
config_replacement = '''    "hits_projection": st.column_config.NumberColumn("Projected Hits", format="%.2f"),
    "manual_hits_allowed_line": st.column_config.NumberColumn("Hits Line", format="%.1f"),
    "manual_hits_allowed_side": st.column_config.TextColumn("Hits Side"),
    "hits_bet_result": st.column_config.TextColumn("Hits Bet Result"),
    "hits_range_low": st.column_config.NumberColumn("80% H Low", format="%.0f"),
'''
if config_anchor not in source:
    raise SystemExit("hits config anchor missing")
source = source.replace(config_anchor, config_replacement, 1)

config_anchor = '''    "outs_projection": st.column_config.NumberColumn("Projected Outs", format="%.2f"),
    "outs_range_low": st.column_config.NumberColumn("80% Outs Low", format="%.0f"),
'''
config_replacement = '''    "outs_projection": st.column_config.NumberColumn("Projected Outs", format="%.2f"),
    "manual_outs_line": st.column_config.NumberColumn("Outs Line", format="%.1f"),
    "manual_outs_side": st.column_config.TextColumn("Outs Side"),
    "outs_bet_result": st.column_config.TextColumn("Outs Bet Result"),
    "outs_range_low": st.column_config.NumberColumn("80% Outs Low", format="%.0f"),
'''
if config_anchor not in source:
    raise SystemExit("outs config anchor missing")
source = source.replace(config_anchor, config_replacement, 1)

style_anchor = '''    if target_cols:
        styled = styled.map(lambda _: "color:#38bdf8;font-weight:800;", subset=target_cols)
    return styled
'''
style_replacement = '''    if target_cols:
        styled = styled.map(lambda _: "color:#38bdf8;font-weight:800;", subset=target_cols)
    manual_line_cols = [c for c in ["manual_hits_allowed_line", "manual_outs_line"] if c in group.columns]
    if manual_line_cols:
        styled = styled.map(lambda value: "color:#ff9f1c;font-weight:850;background-color:rgba(255,159,28,.10);" if pd.notna(value) else "", subset=manual_line_cols)
    for result_col in ["hits_bet_result", "outs_bet_result"]:
        if result_col in group.columns:
            styled = styled.map(
                lambda value: "color:#22c55e;font-weight:900;" if "WIN" in str(value) else "color:#ff6379;font-weight:900;" if "LOSS" in str(value) else "color:#ffd166;font-weight:850;" if ("PUSH" in str(value) or "NO BET" in str(value)) else "color:#9fb3c6;font-weight:800;",
                subset=[result_col],
            )
    return styled
'''
if style_anchor not in source:
    raise SystemExit("style archive anchor missing")
source = source.replace(style_anchor, style_replacement, 1)

old_caption = '''st.caption("Click a date to open that slate. K Target / K Result is the only WIN/MISS lane in this automatic evidence table. The 80% K, Hits, and Outs Range columns only show whether the final MLB result landed inside the frozen model interval; they are not sportsbook bet grades. Hits/Outs are never graded as bets here without a saved sportsbook line + side. Empty None/null/NaN columns are hidden automatically.")
'''
new_caption = '''st.caption("Click a date to open that slate. Model diagnostics and execution evidence are intentionally separate: 80% K/Hits/Outs Range = frozen interval coverage; K Target/K Result = model-supported K ladder grading; Hits/Outs Line + Side + Bet Result = true execution history only when a real line and a certified pregame side exist. Eligible legacy manual lines can be leakage-safely recovered from their archived pregame timestamp/model snapshot; post-start or ambiguous rows remain UNGRADABLE. Execution evidence never feeds calibration or projection training. Empty None/null/NaN columns are hidden automatically.")
'''
if old_caption not in source:
    raise SystemExit("automatic evidence caption anchor missing")
source = source.replace(old_caption, new_caption, 1)

history_path.write_text(source, encoding="utf-8")
print("execution_evidence_v21 applied")

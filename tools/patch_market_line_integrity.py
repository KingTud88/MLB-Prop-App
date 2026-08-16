from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        return text
    return text.replace(old, new, 1)


# 1) Current Top Plays may require real/active market lines while historical
# walk-forward diagnostics retain the legacy synthetic model grid.
p = Path("engine/model_top_plays.py")
s = p.read_text()
if "MARKET_LINE_COLUMNS = {" not in s:
    anchor = '''PROJECTION_COLUMNS = {
    MARKET_STRIKEOUTS: "projection",
    MARKET_OUTS: "outs_projection",
    MARKET_HITS: "hits_projection",
}
'''
    repl = anchor + '''
MARKET_LINE_COLUMNS = {
    MARKET_STRIKEOUTS: "active_strikeout_line",
    MARKET_OUTS: "active_outs_line",
    MARKET_HITS: "active_hits_allowed_line",
}

MARKET_LINE_SOURCE_COLUMNS = {
    MARKET_STRIKEOUTS: "active_strikeout_line_source",
    MARKET_OUTS: "active_outs_line_source",
    MARKET_HITS: "active_hits_allowed_line_source",
}
'''
    if anchor not in s:
        raise SystemExit("model_top_plays projection anchor missing")
    s = s.replace(anchor, repl, 1)

s = replace_once(
    s,
    '''def build_model_candidate(
    row: Mapping[str, object],
    market: str,
    history: pd.DataFrame,
    market_health: Mapping[str, str] | None = None,
) -> dict[str, object] | None:''',
    '''def build_model_candidate(
    row: Mapping[str, object],
    market: str,
    history: pd.DataFrame,
    market_health: Mapping[str, str] | None = None,
    *,
    require_market_line: bool = False,
) -> dict[str, object] | None:''',
    "candidate signature",
)
s = replace_once(
    s,
    '''    line = target_line(market, projection)
    if abs(float(projection) - float(line)) > MAX_TARGET_DISTANCE[market]:
        return None
    over_p = over_probability(row, market, line, history)''',
    '''    if require_market_line:
        line = _num(row.get(MARKET_LINE_COLUMNS[market]))
        if line is None:
            return None
        line_source = str(row.get(MARKET_LINE_SOURCE_COLUMNS[market], "") or "").strip() or "ACTIVE MARKET LINE"
    else:
        line = target_line(market, projection)
        if abs(float(projection) - float(line)) > MAX_TARGET_DISTANCE[market]:
            return None
        line_source = "MODEL GRID · DIAGNOSTIC ONLY"
    over_p = over_probability(row, market, line, history)''',
    "candidate line selection",
)
if '"Line Source": line_source,' not in s:
    anchor = '''        "Line": line,
        "Projection": projection,'''
    if anchor not in s:
        raise SystemExit("model_top_plays line output anchor missing")
    s = s.replace(anchor, '''        "Line": line,
        "Line Source": line_source,
        "Projection": projection,''', 1)
s = replace_once(
    s,
    '''def build_model_board(
    slate: pd.DataFrame,
    history: pd.DataFrame,
    limit: int = 5,
    market_health: Mapping[str, str] | None = None,
) -> pd.DataFrame:''',
    '''def build_model_board(
    slate: pd.DataFrame,
    history: pd.DataFrame,
    limit: int = 5,
    market_health: Mapping[str, str] | None = None,
    *,
    require_market_lines: bool = False,
) -> pd.DataFrame:''',
    "board signature",
)
s = s.replace(
    "candidate = build_model_candidate(row, market, history, market_health=market_health)",
    "candidate = build_model_candidate(row, market, history, market_health=market_health, require_market_line=require_market_lines)",
    1,
)
p.write_text(s)


# 2) Daily Run writes manual/paid lines directly onto the frozen current rows.
p = Path("pages/5_Daily_Projection_Run.py")
s = p.read_text()
if "def apply_active_market_lines(" not in s:
    anchor = "\n\ndef run_full_slate(day: str)"
    helper = '''

def apply_active_market_lines(slate_day: str, manual_lines: dict[str, dict[str, float]]) -> int:
    """Apply user-entered sportsbook lines to frozen rows used by current Top Plays."""
    frame = load_log()
    if frame.empty or "game_date" not in frame.columns:
        return 0
    for col in (
        "active_strikeout_line", "active_outs_line", "active_hits_allowed_line",
        "active_strikeout_line_source", "active_outs_line_source", "active_hits_allowed_line_source",
    ):
        if col not in frame.columns:
            frame[col] = np.nan if col.endswith("_line") else ""

    applied = 0
    day_mask = frame["game_date"].astype(str).eq(str(slate_day))
    for idx in frame.index[day_mask]:
        row = frame.loc[idx]
        values = manual_lines.get(_archive_row_key(row), {})
        for key, line_col, source_col in (
            ("k", "active_strikeout_line", "active_strikeout_line_source"),
            ("outs", "active_outs_line", "active_outs_line_source"),
            ("hits", "active_hits_allowed_line", "active_hits_allowed_line_source"),
        ):
            value = values.get(key, np.nan)
            if pd.notna(value):
                frame.at[idx, line_col] = float(value)
                frame.at[idx, source_col] = "MANUAL"
                applied += 1
    save_log(frame)
    return applied


def apply_paid_strikeout_lines(odds_snapshot: pd.DataFrame, slate_day: str) -> int:
    """Apply saved paid K lines without overwriting a deliberate manual line."""
    if odds_snapshot.empty:
        return 0
    frame = load_log()
    if frame.empty or "game_date" not in frame.columns:
        return 0
    for col, default in (("active_strikeout_line", np.nan), ("active_strikeout_line_source", "")):
        if col not in frame.columns:
            frame[col] = default

    snap = odds_snapshot.copy()
    snap["point"] = pd.to_numeric(snap.get("point"), errors="coerce")
    snap = snap.dropna(subset=["point"])
    snap["_name"] = snap.get("pitcher", pd.Series(index=snap.index, dtype=str)).fillna("").astype(str).map(lambda x: " ".join(x.lower().split()))
    snap["_book"] = snap.get("book", pd.Series(index=snap.index, dtype=str)).fillna("").astype(str).str.lower()

    applied = 0
    day_mask = frame["game_date"].astype(str).eq(str(slate_day))
    for idx in frame.index[day_mask]:
        if str(frame.at[idx, "active_strikeout_line_source"] or "").upper() == "MANUAL":
            continue
        name = " ".join(str(frame.at[idx, "player"]).lower().split())
        offers = snap.loc[snap["_name"].eq(name)]
        if offers.empty:
            continue
        fanduel = offers.loc[offers["_book"].str.contains("fanduel", na=False)]
        chosen = fanduel if not fanduel.empty else offers
        mode = chosen["point"].mode()
        if mode.empty:
            continue
        frame.at[idx, "active_strikeout_line"] = float(mode.iloc[0])
        frame.at[idx, "active_strikeout_line_source"] = "PAID API · FANDUEL" if not fanduel.empty else "PAID API · CONSENSUS"
        applied += 1
    save_log(frame)
    return applied
'''
    if anchor not in s:
        raise SystemExit("Daily run function anchor missing")
    s = s.replace(anchor, helper + anchor, 1)

s = replace_once(
    s,
    '''                archived = commit_projection_archive(slate, parsed_lines, slate_date.isoformat())
                st.session_state["daily_archive_saved_at"] = datetime.now(EASTERN).strftime("%b %d, %Y · %I:%M:%S %p ET")
                st.success(f"Applied {filled_lines} manual market line(s) and added {archived} pitcher projection(s) to the Projection Archive.")''',
    '''                applied = apply_active_market_lines(slate_date.isoformat(), parsed_lines)
                archived = commit_projection_archive(slate, parsed_lines, slate_date.isoformat())
                refreshed_log = load_log()
                st.session_state["daily_slate"] = refreshed_log.loc[refreshed_log.get("game_date", pd.Series(dtype=str)).astype(str).eq(slate_date.isoformat())].copy()
                st.session_state["daily_archive_saved_at"] = datetime.now(EASTERN).strftime("%b %d, %Y · %I:%M:%S %p ET")
                st.success(f"Applied {applied} active sportsbook line(s) to Top Plays and added {archived} pitcher projection(s) to the Projection Archive.")''',
    "manual apply",
)
s = replace_once(
    s,
    '''        pitchers=int(odds_snapshot.get("pitcher",pd.Series(dtype=str)).nunique()) if not odds_snapshot.empty else 0
        st.success(f"Saved {len(odds_snapshot)} strikeout offers for {pitchers} pitchers. Main Projections will reuse this snapshot for free.")''',
    '''        pitchers=int(odds_snapshot.get("pitcher",pd.Series(dtype=str)).nunique()) if not odds_snapshot.empty else 0
        active_lines = apply_paid_strikeout_lines(odds_snapshot, slate_date.isoformat())
        st.success(f"Saved {len(odds_snapshot)} strikeout offers for {pitchers} pitchers and applied {active_lines} active K line(s) for Top Plays. Manual K lines override these paid lines.")''',
    "paid apply",
)
s = s.replace(
    "Open each pitcher bar and enter the sportsbook lines you want attached to this frozen projection. Half-lines such as 4.5, 15.5, and 5.5 are supported. Blank markets are allowed.",
    "Open each pitcher bar and enter the real sportsbook lines you want Top Plays to evaluate. Manual values override paid API lines. Half-lines such as 4.5, 15.5, and 5.5 are supported; a blank market is excluded from Top Plays unless a paid active line already exists.",
    1,
)
p.write_text(s)


# 3) Current Top Plays requires those active lines and saves their provenance.
p = Path("pages/6_Top_Plays.py")
s = p.read_text()
s = s.replace(
    "plays = build_model_board(slate, history, limit=5, market_health=health_map)",
    "plays = build_model_board(slate, history, limit=5, market_health=health_map, require_market_lines=True)",
    1,
)
s = s.replace(
    "No current market passed the starter-history, probability-path, and model-health eligibility guards. The app will not manufacture a Top Play when the validated board is empty.",
    "No current market has both a valid model path and an active sportsbook line. Enter manual K / outs / hits lines on Daily Projection Run (or load the saved paid K snapshot) before Top Plays can rank a real bet.",
    1,
)
marker = "# The board exists before any paid sportsbook request. Credit Saver keeps paid"
if "TOP_PLAYS_REAL_LINE_GUARD_V1" not in s and marker in s:
    s = s.replace(
        marker,
        '# TOP_PLAYS_REAL_LINE_GUARD_V1\nst.caption("Line integrity: every ranked leg below uses an active sportsbook line from Daily Run. MANUAL overrides the saved paid K snapshot; markets with no active line are excluded. Model-grid/default lines are diagnostics only and cannot become current Top Plays.")\n\n' + marker,
        1,
    )
if 'line_source = str(play_row.get("Line Source"' not in s:
    anchor = '    matchup_text = " · ".join(v for v in [team, f"vs {opponent}" if opponent else "", weather_icon] if v)\n'
    if anchor not in s:
        raise SystemExit("Top Plays matchup anchor missing")
    s = s.replace(anchor, anchor + '    line_source = str(play_row.get("Line Source", "ACTIVE MARKET LINE") or "ACTIVE MARKET LINE")\n', 1)
market_html = '''                <div class="tp-market-row">
                  <div class="tp-market">{play_row['Market']}</div>
                  <div class="tp-side {side_class}">{side} {float(play_row['Line']):g}</div>
                </div>'''
if market_html in s and '<strong>Line source:</strong>' not in s:
    s = s.replace(market_html, market_html + '\n                <div class="tp-card-note"><strong>Line source:</strong> {line_source}</div>', 1)
if '"line_source": str(leg.get("Line Source", "")),' not in s:
    anchor = '''                "line": float(leg["Line"]),
                "side": str(leg["Side"]),'''
    if anchor not in s:
        raise SystemExit("Top Plays parlay leg anchor missing")
    s = s.replace(anchor, '''                "line": float(leg["Line"]),
                "line_source": str(leg.get("Line Source", "")),
                "side": str(leg["Side"]),''', 1)
p.write_text(s)


# 4) Canonical parlay persistence keeps the verified line source.
p = Path("engine/bet_tracker.py")
s = p.read_text()
if '"line_source": str(leg.get("line_source", "")),' not in s:
    anchor = '''            "line": float(leg.get("line")),
            "side": side,'''
    if anchor not in s:
        raise SystemExit("bet_tracker cleaned leg anchor missing")
    s = s.replace(anchor, '''            "line": float(leg.get("line")),
            "line_source": str(leg.get("line_source", "")),
            "side": side,''', 1)
p.write_text(s)


# 5) Legacy model-grid parlays remain visible but no longer contaminate real record.
p = Path("pages/2_Bet_Tracker.py")
s = p.read_text()
s = replace_once(
    s,
    '''            grade = grade_parlay(leg_grades)
            profit = profit_for(stake, odds, grade)
            resolved_rows.append({''',
    '''            grade = grade_parlay(leg_grades)
            source_text = str(row.get("source", "") or "").strip()
            legacy_model_line_ticket = (
                source_text in {"Top Plays Model Parlay", "Projection Page Model Parlay"}
                and bool(legs)
                and all(not str(leg.get("line_source", "") or "").strip() for leg in legs)
            )
            result_text = "INVALID LINE" if legacy_model_line_ticket else grade.result
            profit = None if legacy_model_line_ticket else profit_for(stake, odds, grade)
            resolved_rows.append({''',
    "legacy quarantine",
)
# Only the parlay result occurrence immediately after the new block should change.
legacy_anchor = '            result_text = "INVALID LINE" if legacy_model_line_ticket else grade.result\n            profit = None if legacy_model_line_ticket else profit_for(stake, odds, grade)\n            resolved_rows.append({'
if legacy_anchor in s:
    pos = s.index(legacy_anchor)
    before, after = s[:pos], s[pos:]
    after = after.replace('                "Result": grade.result,\n                "Profit/Loss": profit,', '                "Result": result_text,\n                "Profit/Loss": profit,', 1)
    s = before + after
if '"INVALID LINE": 3,' not in s:
    s = s.replace('    "PUSH LEG": 2,\n}', '    "PUSH LEG": 2,\n    "INVALID LINE": 3,\n}', 1)
s = s.replace(
    'pending = int((~results["Result"].isin(["WIN", "LOSS", "PUSH", "PUSH LEG"])).sum())',
    'invalid = int((results["Result"] == "INVALID LINE").sum())\npending = int((~results["Result"].isin(["WIN", "LOSS", "PUSH", "PUSH LEG", "INVALID LINE"])).sum())',
    1,
)
if "legacy model-only ticket(s) are marked INVALID LINE" not in s:
    anchor = "if stake_series.isna().any():\n"
    if anchor not in s:
        raise SystemExit("Bet Tracker caption anchor missing")
    note = 'if invalid:\n    st.warning(f"{invalid} legacy model-only ticket(s) are marked INVALID LINE and excluded from the real win/loss record because their saved legs used synthetic/default lines rather than verified sportsbook lines.")\n'
    s = s.replace(anchor, note + anchor, 1)
if 'if state == "INVALID LINE":' not in s:
    anchor = '    if state in {"PUSH", "PUSH LEG"}:\n        return "🟡"\n'
    if anchor not in s:
        raise SystemExit("Bet Tracker ticket icon anchor missing")
    s = s.replace(anchor, anchor + '    if state == "INVALID LINE":\n        return "⚠️"\n', 1)
p.write_text(s)

print("market-line integrity patch applied")

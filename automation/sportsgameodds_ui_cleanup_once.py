from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def save(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def remove_top_level_functions(text: str, names: set[str]) -> str:
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    ranges: list[tuple[int, int, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
            end = int(node.end_lineno or node.lineno)
            ranges.append((start, end, node.name))
    found = {name for _, _, name in ranges}
    missing = names - found
    if missing:
        raise RuntimeError(f"Missing functions for removal: {sorted(missing)}")
    for start, end, _ in sorted(ranges, reverse=True):
        del lines[start:end]
    return "".join(lines)


def remove_top_level_assignments(text: str, names: set[str]) -> str:
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    ranges: list[tuple[int, int, str]] = []
    for node in tree.body:
        target_names: set[str] = set()
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    target_names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_names.add(node.target.id)
        hit = target_names & names
        if hit:
            start = node.lineno - 1
            end = int(node.end_lineno or node.lineno)
            for name in hit:
                ranges.append((start, end, name))
    found = {name for _, _, name in ranges}
    missing = names - found
    if missing:
        raise RuntimeError(f"Missing assignments for removal: {sorted(missing)}")
    unique_ranges = {(start, end) for start, end, _ in ranges}
    for start, end in sorted(unique_ranges, reverse=True):
        del lines[start:end]
    return "".join(lines)


def cleanup_daily() -> None:
    path = "pages/5_Daily_Projection_Run.py"
    text = load(path)
    text = replace_once(
        text,
        "from engine.execution_history import freeze_execution_decision, is_pregame_execution_window\n",
        "",
        "daily execution-history import",
    )
    text = replace_once(text, "from engine.model_top_plays import MARKET_HITS, MARKET_OUTS\n", "", "daily market constants import")
    text = replace_once(
        text,
        "from engine.odds_snapshot import load_quota_status, refresh_strikeout_snapshot, resolve_api_key\n",
        "",
        "daily Odds API import",
    )
    text = replace_once(
        text,
        "from training.projection_storage import load_projection_archive, overlay_manual_market_lines, save_projection_archive\n",
        "from training.projection_storage import load_projection_archive, overlay_manual_market_lines\n",
        "daily projection storage import",
    )
    for css in (
        "    /* daily-control-deck-v2: presentation only. */\n",
        "    .daily-hero { margin:.25rem 0 1.15rem; padding:.9rem 1rem; border:1px solid rgba(73,111,151,.48); border-left:3px solid #ff3655; border-radius:16px; background:linear-gradient(120deg,rgba(227,25,55,.08),rgba(10,29,54,.76) 42%,rgba(6,18,35,.78)); box-shadow:0 14px 34px rgba(0,0,0,.16); }\n",
        "    .daily-hero strong { color:#f8fbff; font-size:1rem; }\n",
        "    .daily-hero span { display:block; color:#9db0c5; font-size:.84rem; margin-top:.2rem; }\n",
        "    .daily-kicker { margin:1.35rem 0 .42rem; color:#aebfd2; font-size:.72rem; font-weight:900; letter-spacing:.13em; text-transform:uppercase; }\n",
        "    .daily-kicker::before { content:''; display:inline-block; width:22px; height:2px; margin-right:.5rem; vertical-align:middle; background:#ff3655; box-shadow:0 0 11px rgba(227,25,55,.42); }\n",
        "    .daily-paid-note { margin:.35rem 0 .8rem; padding:.72rem .85rem; border-radius:13px; border:1px solid rgba(250,204,21,.32); background:rgba(120,79,8,.08); color:#c9d7e5; font-size:.86rem; }\n",
        "    .daily-note.paid{border-color:rgba(250,204,21,.42);background:linear-gradient(110deg,rgba(88,65,8,.24),rgba(29,29,16,.52));color:#e9dfb4}\n",
        "    @media (max-width:900px) { .daily-hero { padding:.78rem .85rem; } .daily-kicker { margin-top:1rem; } }\n",
    ):
        if css in text:
            text = text.replace(css, "", 1)

    text = remove_top_level_functions(
        text,
        {
            "_archive_row_key",
            "_parse_market_line",
            "_manual_input_default",
            "_same_market_line",
            "commit_projection_archive",
            "apply_active_market_lines",
            "apply_paid_strikeout_lines",
        },
    )

    start_marker = "st.markdown('<div class=\"daily-section-head\">Backup Paid Data</div>', unsafe_allow_html=True)"
    end_marker = "st.markdown('<div class=\"daily-section-head\">📚 Persistent history-only starter tracker</div>', unsafe_allow_html=True)"
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError("Daily backup-paid section markers not found")
    text = text[:start] + text[end:]

    forbidden = (
        "Backup Paid Data",
        "LOAD STRIKEOUT LINES · BACKUP API",
        "Odds API credits remaining",
        "refresh_strikeout_snapshot",
        "commit_projection_archive(",
        "apply_active_market_lines(",
        "apply_paid_strikeout_lines(",
    )
    for token in forbidden:
        if token in text:
            raise RuntimeError(f"Daily cleanup left obsolete token: {token}")
    save(path, text)


def cleanup_top_plays() -> None:
    path = "pages/6_Top_Plays.py"
    text = load(path)
    text = replace_once(text, "import os\n", "", "top plays os import")
    text = replace_once(text, "import requests\n", "", "top plays requests import")
    text = replace_once(
        text,
        "from engine.model_top_plays import build_model_board\n",
        "from engine.model_top_plays import build_model_board\nfrom engine.sportsgameodds import load_pitcher_market_odds\n",
        "top plays SportsGameOdds import",
    )
    text = remove_top_level_assignments(text, {"ODDS_API", "TEAM_NAMES", "api_key"})
    text = remove_top_level_functions(
        text,
        {
            "secret",
            "normalize_team",
            "odds_events",
            "event_props",
            "match_event",
            "strikeout_over_probability",
            "hits_over_probability",
            "outs_over_probability",
            "model_over_probability",
            "collect_legs",
        },
    )

    helper = '''\n\ndef attach_sportsgameodds_prices(plays: pd.DataFrame, slate_date: str) -> pd.DataFrame:\n    """Attach exact saved SportsGameOdds prices without making an API call or changing rank."""\n    enriched = plays.copy()\n    for col, default in (\n        ("Book", ""),\n        ("Odds", np.nan),\n        ("No-Vig Implied", np.nan),\n        ("Edge", np.nan),\n        ("Live Offer", False),\n    ):\n        enriched[col] = default\n\n    cache: dict[str, list[dict[str, object]]] = {}\n    for idx, play in enriched.iterrows():\n        pitcher = str(play.get("Pitcher", "") or "").strip()\n        market_key = MAIN_MARKET_KEYS.get(str(play.get("Market", "") or ""))\n        line = numeric(play.get("Line"))\n        side = str(play.get("Side", "") or "").strip().lower()\n        if not pitcher or not market_key or line is None or side not in {"over", "under"}:\n            continue\n\n        if pitcher not in cache:\n            cache[pitcher] = load_pitcher_market_odds(pitcher, slate_date)\n        offers = [\n            row for row in cache[pitcher]\n            if str(row.get("market", "")) == market_key\n            and numeric(row.get("point")) is not None\n            and abs(float(row.get("point")) - line) <= 1e-9\n        ]\n        if not offers:\n            continue\n\n        target = next((row for row in offers if str(row.get("name", "")).lower() == side), None)\n        if target is None:\n            continue\n        book = str(target.get("book", "") or "").strip()\n        same_book = [row for row in offers if str(row.get("book", "") or "").strip() == book]\n        over = next((row for row in same_book if str(row.get("name", "")).lower() == "over"), None)\n        under = next((row for row in same_book if str(row.get("name", "")).lower() == "under"), None)\n        price = numeric(target.get("price"))\n        if price is None:\n            continue\n\n        enriched.at[idx, "Book"] = book\n        enriched.at[idx, "Odds"] = price\n        enriched.at[idx, "Live Offer"] = True\n        over_price = numeric(over.get("price")) if over else None\n        under_price = numeric(under.get("price")) if under else None\n        if over_price is not None and under_price is not None:\n            po = implied(over_price)\n            pu = implied(under_price)\n            total = po + pu\n            if total > 0:\n                fair_over = po / total\n                fair_side = fair_over if side == "over" else 1.0 - fair_over\n                enriched.at[idx, "No-Vig Implied"] = fair_side\n                model_p = numeric(play.get("Model Probability"))\n                if model_p is not None:\n                    enriched.at[idx, "Edge"] = model_p - fair_side\n    return enriched\n'''
    marker = "\ndef find_snapshot(history: pd.DataFrame, play: pd.Series) -> pd.Series | None:\n"
    if marker not in text:
        raise RuntimeError("Top Plays find_snapshot marker not found")
    text = text.replace(marker, helper + marker, 1)

    text = replace_once(
        text,
        '    st.warning("No current market has both a valid model path and an active sportsbook line. Enter manual K / outs / hits lines on Daily Projection Run (or load the saved paid K snapshot) before Top Plays can rank a real bet.")',
        '    st.warning("No current market has both a valid model path and an authentic active sportsbook line yet. SportsGameOdds capture must supply a real pregame line before Top Plays can rank a bet.")',
        "top plays empty-board warning",
    )
    text = replace_once(
        text,
        'st.caption("Line integrity: every ranked leg below uses an active sportsbook line from Daily Run. MANUAL overrides the saved paid K snapshot; markets with no active line are excluded. Model-grid/default lines are diagnostics only and cannot become current Top Plays.")',
        'st.caption("Line integrity: every ranked leg below uses an authentic active sportsbook line. SportsGameOdds is primary; legacy MANUAL or backup rows keep their explicit source labels. Markets with no real line are excluded, and model-grid/default lines can never become Top Plays.")',
        "top plays line-integrity caption",
    )

    runtime_start = text.find("# The board exists before any paid sportsbook request.")
    runtime_end = text.find("model_plays = int(", runtime_start)
    if runtime_start < 0 or runtime_end < 0:
        raise RuntimeError("Top Plays paid runtime markers not found")
    text = text[:runtime_start] + "# Exact SportsGameOdds prices are read from the saved disk snapshot only.\n# This overlay cannot change the model-first Top 5 order.\nplays = attach_sportsgameodds_prices(plays, today)\n\n" + text[runtime_end:]
    text = text.replace(
        "Model play · waiting for exact live line/price",
        "Model play · active real line captured · current price unavailable",
    )

    forbidden = (
        "api.the-odds-api.com",
        "odds_events(",
        "event_props(",
        "load_top_plays_live_prices",
        "Odds API usage from the last manual Top 5 load",
        "Paid Odds API",
        "Credit Saver",
        "import requests",
    )
    for token in forbidden:
        if token in text:
            raise RuntimeError(f"Top Plays cleanup left obsolete token: {token}")
    required = ("load_pitcher_market_odds", "attach_sportsgameodds_prices", "SportsGameOdds is primary")
    for token in required:
        if token not in text:
            raise RuntimeError(f"Top Plays cleanup missing required token: {token}")
    save(path, text)


def cleanup_main_projection() -> None:
    path = "streamlit_app.py"
    text = load(path)
    replacements = {
        "_manual_probe": "_active_probe",
        "_manual_row": "_active_row",
        "manual_k_line": "active_k_line",
        "manual_outs_line": "active_outs_line",
        "manual_hits_line": "active_hits_line",
        "manual_k_source": "active_k_source",
        "manual_outs_source": "active_outs_source",
        "manual_hits_source": "active_hits_source",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = replace_once(
        text,
        'odds_err=("" if odds_rows else "No saved strikeout odds for this pitcher/slate yet. Use the paid manual button on Daily Projection Run; this page never calls the Odds API.")',
        'odds_err=("" if odds_rows else "No current automated sportsbook line has been captured for this pitcher/slate yet.")',
        "main projection no-odds message",
    )

    source_helper = '''\ndef _saved_market_source(rows, market):\n    for row in rows:\n        if str(row.get("market", "")) != market:\n            continue\n        book = str(row.get("book", "") or "").strip()\n        provider = str(row.get("provider", "") or "").strip().upper()\n        if provider == "SPORTSGAMEODDS":\n            return f"SPORTSGAMEODDS · {book}" if book else "SPORTSGAMEODDS"\n        return f"ODDS API · {book}" if book else "ODDS API · SAVED BACKUP"\n    return "SAVED SNAPSHOT"\n'''
    marker = "k_reco=market_recommendation(proj,odds_rows,\"pitcher_strikeouts_alternate\",5.5,\"k\"); k_reco[\"label\"]=\"STRIKEOUT BET LEAN\"\n"
    if marker not in text:
        raise RuntimeError("Main Projection recommendation marker not found")
    text = text.replace(marker, source_helper + marker, 1)

    text = replace_once(
        text,
        'elif k_reco.get("has_market"):\n    k_reco["active_line_source"]="PAID API · SAVED SNAPSHOT"',
        'elif k_reco.get("has_market"):\n    k_reco["active_line_source"]=_saved_market_source(odds_rows,"pitcher_strikeouts")',
        "main K source label",
    )
    text = replace_once(
        text,
        'elif out_reco.get("has_market"):\n    out_reco["active_line_source"]="SAVED SNAPSHOT"',
        'elif out_reco.get("has_market"):\n    out_reco["active_line_source"]=_saved_market_source(odds_rows,"pitcher_outs")',
        "main outs source label",
    )
    text = replace_once(
        text,
        'elif hit_reco.get("has_market"):\n    hit_reco["active_line_source"]="SAVED SNAPSHOT"',
        'elif hit_reco.get("has_market"):\n    hit_reco["active_line_source"]=_saved_market_source(odds_rows,"pitcher_hits_allowed")',
        "main hits source label",
    )
    text = replace_once(
        text,
        'st.caption("Manual Daily Run lines appear in orange; a saved paid K snapshot appears with its source label. No active line means the projection still shows, but the app will not manufacture a bet lean. Execution lines never alter the baseball projection.")',
        'st.caption("Automated real sportsbook lines show their provider/book source. Legacy MANUAL lines remain orange for historical clarity. No active line means the projection still shows, but the app will not manufacture a bet lean. Execution lines never alter the baseball projection.")',
        "main active-lines caption",
    )

    forbidden = ("Use the paid manual button", "PAID API · SAVED SNAPSHOT")
    for token in forbidden:
        if token in text:
            raise RuntimeError(f"Main Projection cleanup left obsolete token: {token}")
    save(path, text)


def cleanup_history() -> None:
    path = "pages/4_Projection_History.py"
    text = load(path)
    text = replace_once(
        text,
        "Your manually approved Projection Archive stays first. Frozen model evidence, resolved MLB outcomes, calibration, workload audits, and learning diagnostics remain underneath for deeper review.",
        "Your durable Projection Archive stays first. Frozen model evidence, authentic sportsbook lines, resolved MLB outcomes, calibration, workload audits, and learning diagnostics remain underneath for deeper review.",
        "history hero copy",
    )
    text = replace_once(
        text,
        "Every frozen daily projection slate appears here automatically. Your sportsbook lines are a durable execution overlay saved separately, so a reboot cannot remove the slate or detach previously saved manual lines.",
        "Every frozen daily projection slate appears here automatically. Authentic sportsbook lines are preserved as execution evidence, while legacy MANUAL rows remain intact for historical accountability.",
        "history archive note",
    )
    old_counter = '''    line_cols = [col for col in ("manual_strikeout_line", "manual_outs_line", "manual_hits_allowed_line") if col in user_archive.columns]\n    manual_lines = int(sum(user_archive[col].notna().sum() for col in line_cols))\n'''
    new_counter = '''    line_cols = [col for col in ("active_strikeout_line", "active_outs_line", "active_hits_allowed_line") if col in user_archive.columns]\n    real_lines = int(sum(user_archive[col].notna().sum() for col in line_cols))\n'''
    text = replace_once(text, old_counter, new_counter, "history line counter")
    text = replace_once(
        text,
        '    a3.metric("Manual lines attached", manual_lines, help=metric_help("history_manual_lines", current=f"{manual_lines} saved manual market line(s)"))',
        '    a3.metric("Real lines attached", real_lines, help=metric_help("history_real_lines", current=f"{real_lines} authentic sportsbook market line(s) attached"))',
        "history line metric",
    )
    old_columns = '''    archive_columns = [\n        "player", "team", "opponent",\n        "projection", "archive_k_target", "actual_strikeouts", "archive_k_result", "manual_strikeout_line",\n        "outs_projection", "manual_outs_line", "manual_outs_side", "actual_outs", "archive_outs_bet_result",\n        "hits_projection", "manual_hits_allowed_line", "manual_hits_allowed_side", "actual_hits_allowed", "archive_hits_bet_result",\n        "confidence", "data_quality", "archive_source", "archive_committed_at_utc",\n    ]\n'''
    new_columns = '''    archive_columns = [\n        "player", "team", "opponent",\n        "projection", "archive_k_target", "actual_strikeouts", "archive_k_result", "active_strikeout_line", "active_strikeout_line_source",\n        "outs_projection", "active_outs_line", "active_outs_line_source", "manual_outs_side", "actual_outs", "archive_outs_bet_result",\n        "hits_projection", "active_hits_allowed_line", "active_hits_allowed_line_source", "manual_hits_allowed_side", "actual_hits_allowed", "archive_hits_bet_result",\n        "confidence", "data_quality", "archive_source", "archive_committed_at_utc",\n    ]\n'''
    text = replace_once(text, old_columns, new_columns, "history archive columns")
    text = replace_once(
        text,
        '            f"📅 {date_label} · {len(group)} pitcher{\'s\' if len(group) != 1 else \'\'} · {day_line_count} manual lines · {day_resolved} resolved",',
        '            f"📅 {date_label} · {len(group)} pitcher{\'s\' if len(group) != 1 else \'\'} · {day_line_count} real lines · {day_resolved} resolved",',
        "history date label",
    )
    text = text.replace('"manual_strikeout_line": "K Line",', '"active_strikeout_line": "K Line", "active_strikeout_line_source": "K Source",', 1)
    text = text.replace('"manual_outs_line": "Outs Line",', '"active_outs_line": "Outs Line", "active_outs_line_source": "Outs Source",', 1)
    text = text.replace('"manual_hits_allowed_line": "Hits Line",', '"active_hits_allowed_line": "Hits Line", "active_hits_allowed_line_source": "Hits Source",', 1)
    text = replace_once(
        text,
        '                "Projected K", "K Target", "Actual K", "K Result", "K Line",\n                "Projected Outs", "Outs Line", "Outs Side", "Actual Outs", "Outs Bet Result",\n                "Projected Hits", "Hits Line", "Hits Side", "Actual Hits", "Hits Bet Result",',
        '                "Projected K", "K Target", "Actual K", "K Result", "K Line", "K Source",\n                "Projected Outs", "Outs Line", "Outs Source", "Outs Side", "Actual Outs", "Outs Bet Result",\n                "Projected Hits", "Hits Line", "Hits Source", "Hits Side", "Actual Hits", "Hits Bet Result",',
        "history preferred columns",
    )
    old_style = '''            manual_cols = [col for col in ("K Line", "Outs Line", "Hits Line") if col in view.columns]\n            projection_cols = [col for col in ("Projected K", "Projected Outs", "Projected Hits") if col in view.columns]\n            actual_view_cols = [col for col in ("Actual K", "Actual Outs", "Actual Hits") if col in view.columns]\n            target_view_cols = [col for col in ("K Target",) if col in view.columns]\n            if manual_cols:\n                styled = styled.map(lambda value: "color:#ff9f1c;font-weight:850;background-color:rgba(255,159,28,.10);" if pd.notna(value) else "", subset=manual_cols)\n'''
    new_style = '''            projection_cols = [col for col in ("Projected K", "Projected Outs", "Projected Hits") if col in view.columns]\n            actual_view_cols = [col for col in ("Actual K", "Actual Outs", "Actual Hits") if col in view.columns]\n            target_view_cols = [col for col in ("K Target",) if col in view.columns]\n            legacy_styles = pd.DataFrame("", index=view.index, columns=view.columns)\n            for line_col, source_col in (("K Line", "K Source"), ("Outs Line", "Outs Source"), ("Hits Line", "Hits Source")):\n                if line_col not in view.columns or source_col not in view.columns:\n                    continue\n                manual_mask = view[source_col].fillna("").astype(str).str.upper().eq("MANUAL") & view[line_col].notna()\n                legacy_styles.loc[manual_mask, line_col] = "color:#ff9f1c;font-weight:850;background-color:rgba(255,159,28,.10);"\n                legacy_styles.loc[manual_mask, source_col] = "color:#ff9f1c;font-weight:850;"\n            styled = styled.apply(lambda _: legacy_styles, axis=None)\n'''
    text = replace_once(text, old_style, new_style, "history legacy styling")
    text = replace_once(
        text,
        '            st.caption("Green = frozen projection · Blue = model-supported K target · Gold = resolved MLB result. K Result grades the model-supported K ladder target. Outs/Hits Bet Result grades only a real line plus a side that was frozen before first pitch; legacy/post-start lines remain UNGRADABLE, and PASS remains NO BET.")',
        '            st.caption("Green = frozen projection · Blue = model-supported K target · Gold = resolved MLB result. Line Source identifies the authentic provider/book; legacy MANUAL lines remain orange. K Result grades the model-supported K ladder target. Outs/Hits Bet Result grades only a real line plus a side frozen before first pitch; ambiguous/post-start rows remain UNGRADABLE, and PASS remains NO BET.")',
        "history archive caption",
    )
    for token in ("Manual lines attached", " manual lines ·", "history_manual_lines"):
        if token in text:
            raise RuntimeError(f"History cleanup left obsolete token: {token}")
    save(path, text)


def cleanup_explainability() -> None:
    path = "engine/explainability_ui.py"
    text = load(path)
    text = replace_once(
        text,
        '        "history_manual_lines": "What it is: sportsbook execution lines you manually attached to archived pitcher rows.\\n\\nHow it is calculated: count of non-null manual K lines + manual Outs lines + manual Hits Allowed lines. One pitcher row can contribute up to three attached lines.\\n\\nHow to read it: these lines are execution overlays only and never rewrite the frozen projection.",',
        '        "history_real_lines": "What it is: authentic sportsbook execution lines attached to archived pitcher rows.\\n\\nHow it is calculated: count of non-null active K lines + active Outs lines + active Hits Allowed lines. One pitcher row can contribute up to three real market lines.\\n\\nHow to read it: SportsGameOdds is the primary automated source; legacy MANUAL lines remain counted as historical execution evidence. Lines never rewrite the frozen projection.",',
        "history real-line help",
    )
    text = replace_once(
        text,
        '''        "active_lines": Explanation(\n            "Active sportsbook lines",\n            "These are the real execution lines currently attached to this pitcher for Strikeouts, Total Outs, and Hits Allowed.",\n            "Daily Projection Run stores manual lines persistently. A saved paid strikeout snapshot can also supply the K line. Main Projection only reads those saved execution lines; it does not invent missing markets.",\n            note="Sportsbook lines never create or move the baseball projection. They only give the model a real line to compare against.",\n        ),\n''',
        '''        "active_lines": Explanation(\n            "Active sportsbook lines",\n            "These are the authentic execution lines currently attached to this pitcher for Strikeouts, Total Outs, and Hits Allowed.",\n            "SportsGameOdds captures real pregame lines automatically and preserves the provider/book source. Legacy MANUAL or backup rows remain explicitly labeled. Main Projection only reads saved execution lines and never invents a missing market.",\n            note="Sportsbook lines never create or move the baseball projection. They only give the model a real line to compare against.",\n        ),\n''',
        "active-lines explanation",
    )
    text = replace_once(
        text,
        '''        "manual_lines": Explanation(\n            "Manual sportsbook lines",\n            "This is the single persistent place to attach the real K, Outs and Hits Allowed lines you actually see at the sportsbook.",\n            "The entered lines are saved as a durable execution overlay on top of the frozen projection row. Main Projection and Top Plays read this overlay later.",\n            note="Entering a line never changes the underlying projection. Blank markets remain excluded from real-line recommendations.",\n        ),\n''',
        "",
        "obsolete manual-lines explanation",
    )
    text = replace_once(
        text,
        '''        "odds_credits": Explanation(\n            "Odds API credits remaining",\n            "This shows the quota value returned by the most recent paid strikeout-line request.",\n            "The paid Daily Run button saves the API response headers locally. This display reads that saved quota snapshot and does not make another paid request just to show the number.",\n        ),\n''',
        "",
        "obsolete odds-credit explanation",
    )
    text = replace_once(
        text,
        '            "Daily Projection Run writes projection rows and the manual-line overlay. The resolver later attaches actual results. K Target is derived from the established model-supported milestone rule and K Result grades that target after resolution.",',
        '            "Daily Projection Run writes frozen projection rows, while automated sportsbook capture attaches authentic execution lines separately. Legacy MANUAL overlays remain preserved for historical evidence. The resolver later attaches actual results. K Target is derived from the established model-supported milestone rule and K Result grades that target after resolution.",',
        "history archive explanation",
    )
    for token in ('"manual_lines": Explanation(', '"odds_credits": Explanation(', '"history_manual_lines"'):
        if token in text:
            raise RuntimeError(f"Explainability cleanup left obsolete token: {token}")
    save(path, text)


def write_regression_test() -> None:
    path = ROOT / "tests/test_sportsgameodds_ui_cleanup.py"
    path.write_text(
        '''from pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\n\n\ndef _text(path: str) -> str:\n    return (ROOT / path).read_text(encoding="utf-8")\n\n\ndef test_daily_run_has_no_obsolete_manual_or_paid_line_controls():\n    text = _text("pages/5_Daily_Projection_Run.py")\n    for token in (\n        "Backup Paid Data",\n        "LOAD STRIKEOUT LINES · BACKUP API",\n        "Odds API credits remaining",\n        "commit_projection_archive(",\n        "apply_active_market_lines(",\n        "apply_paid_strikeout_lines(",\n        "refresh_strikeout_snapshot",\n    ):\n        assert token not in text\n    assert "Automated sportsbook lines" in text\n\n\ndef test_top_plays_uses_saved_sportsgameodds_prices_without_direct_odds_api_runtime():\n    text = _text("pages/6_Top_Plays.py")\n    for token in (\n        "api.the-odds-api.com",\n        "odds_events(",\n        "event_props(",\n        "load_top_plays_live_prices",\n        "Odds API usage from the last manual Top 5 load",\n        "Paid Odds API",\n        "Credit Saver",\n    ):\n        assert token not in text\n    assert "load_pitcher_market_odds" in text\n    assert "attach_sportsgameodds_prices" in text\n    assert "SportsGameOdds is primary" in text\n\n\ndef test_main_projection_copy_and_source_labels_match_automated_feed():\n    text = _text("streamlit_app.py")\n    assert "Use the paid manual button" not in text\n    assert "PAID API · SAVED SNAPSHOT" not in text\n    assert "Automated real sportsbook lines show their provider/book source" in text\n    assert "SPORTSGAMEODDS" in text\n\n\ndef test_projection_history_counts_real_lines_and_preserves_legacy_manual_context():\n    text = _text("pages/4_Projection_History.py")\n    assert "Real lines attached" in text\n    assert "Manual lines attached" not in text\n    assert " real lines · " in text\n    assert "legacy MANUAL lines remain orange" in text\n    assert "active_strikeout_line_source" in text\n\n\ndef test_explainability_matches_automated_sportsbook_workflow():\n    text = _text("engine/explainability_ui.py")\n    assert '"history_real_lines"' in text\n    assert '"history_manual_lines"' not in text\n    assert '"manual_lines": Explanation(' not in text\n    assert '"odds_credits": Explanation(' not in text\n    assert "SportsGameOdds captures real pregame lines automatically" in text\n''',
        encoding="utf-8",
    )


def cleanup_temp_files() -> None:
    for rel in (
        "automation/sportsgameodds_ui_cleanup_once.py",
        ".github/workflows/sportsgameodds-ui-cleanup-once.yml",
    ):
        target = ROOT / rel
        if target.exists():
            target.unlink()


def main() -> None:
    cleanup_daily()
    cleanup_top_plays()
    cleanup_main_projection()
    cleanup_history()
    cleanup_explainability()
    write_regression_test()
    cleanup_temp_files()
    print("SportsGameOdds UI cleanup applied successfully.")


if __name__ == "__main__":
    main()

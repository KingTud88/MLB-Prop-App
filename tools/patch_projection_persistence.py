from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "pages" / "5_Daily_Projection_Run.py"
HISTORY = ROOT / "pages" / "4_Projection_History.py"
TOP = ROOT / "pages" / "6_Top_Plays.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Missing patch anchor: {label}")
    return text.replace(old, new, 1)


def patch_daily() -> None:
    text = DAILY.read_text(encoding="utf-8")
    if "PROJECTION_RESTART_PERSISTENCE_V1" in text:
        return

    text = replace_once(
        text,
        "from navigation import render_sidebar\n",
        "from navigation import render_sidebar\nfrom training.projection_storage import load_projection_archive, overlay_manual_market_lines, save_projection_archive\n",
        "daily storage import",
    )

    parse_anchor = '''def _parse_market_line(value: object) -> float:\n    text = str(value or "").strip()\n    if not text:\n        return np.nan\n    try:\n        return float(text)\n    except ValueError as exc:\n        raise ValueError(f"Invalid market line: {text}") from exc\n'''
    parse_new = parse_anchor + '''\n\ndef _manual_input_default(row: pd.Series, line_col: str, source_col: str) -> str:\n    if str(row.get(source_col, "") or "").strip().upper() != "MANUAL":\n        return ""\n    value = pd.to_numeric(pd.Series([row.get(line_col)]), errors="coerce").iloc[0]\n    return "" if pd.isna(value) else f"{float(value):g}"\n'''
    text = replace_once(text, parse_anchor, parse_new, "daily manual default helper")

    commit_pattern = re.compile(r"def commit_projection_archive\(.*?\n\ndef apply_active_market_lines", re.S)
    match = commit_pattern.search(text)
    if not match:
        raise RuntimeError("Missing patch anchor: commit_projection_archive")
    commit_new = '''def commit_projection_archive(slate: pd.DataFrame, manual_lines: dict[str, dict[str, float]], slate_day: str) -> int:\n    if slate.empty:\n        return 0\n    snapshot = slate.copy().reset_index(drop=True)\n    snapshot["manual_strikeout_line"] = [manual_lines.get(_archive_row_key(row), {}).get("k", np.nan) for _, row in snapshot.iterrows()]\n    snapshot["manual_outs_line"] = [manual_lines.get(_archive_row_key(row), {}).get("outs", np.nan) for _, row in snapshot.iterrows()]\n    snapshot["manual_hits_allowed_line"] = [manual_lines.get(_archive_row_key(row), {}).get("hits", np.nan) for _, row in snapshot.iterrows()]\n    snapshot["archive_source"] = "DAILY_RUN_MANUAL"\n    snapshot["archive_committed_at_utc"] = datetime.now(ZoneInfo("UTC")).isoformat()\n\n    existing = load_projection_archive(ARCHIVE_PATH, st.secrets)\n    if existing.empty:\n        existing = load_log()\n        if not existing.empty and "game_date" in existing.columns:\n            cutoff = pd.Timestamp(slate_day).date()\n            legacy_dates = pd.to_datetime(existing["game_date"], errors="coerce").dt.date\n            existing = existing.loc[legacy_dates < cutoff].copy()\n            if not existing.empty:\n                existing["manual_strikeout_line"] = np.nan\n                existing["manual_outs_line"] = np.nan\n                existing["manual_hits_allowed_line"] = np.nan\n                existing["archive_source"] = "LEGACY_PRE_MANUAL_ARCHIVE"\n                existing["archive_committed_at_utc"] = existing.get("captured_at_utc", "")\n        else:\n            existing = pd.DataFrame()\n\n    if not existing.empty and {"game_pk", "pitcher_id"}.issubset(existing.columns) and {"game_pk", "pitcher_id"}.issubset(snapshot.columns):\n        new_keys = set(zip(snapshot["game_pk"].astype(str), snapshot["pitcher_id"].astype(str)))\n        keep_mask = [key not in new_keys for key in zip(existing["game_pk"].astype(str), existing["pitcher_id"].astype(str))]\n        existing = existing.loc[keep_mask].copy()\n\n    archive = pd.concat([existing, snapshot], ignore_index=True, sort=False)\n    save_projection_archive(ARCHIVE_PATH, archive, st.secrets)\n    return len(snapshot)\n\n\ndef apply_active_market_lines'''
    text = text[:match.start()] + commit_new + text[match.end():]

    run_old = '''    st.session_state["daily_slate"] = slate\n    st.session_state["daily_added"] = added\n    st.session_state["daily_skipped"] = skipped\n    st.session_state["daily_history_only"] = history_only\n    st.session_state["daily_errors"] = errors\n    st.session_state["daily_run_at"] = datetime.now(EASTERN).strftime("%b %d, %Y · %I:%M:%S %p ET")\n\nst.markdown('<div class="daily-section-head">Slate Output</div>', unsafe_allow_html=True)\nslate = st.session_state.get("daily_slate")\n'''
    run_new = '''    durable_archive = load_projection_archive(ARCHIVE_PATH, st.secrets)\n    slate = overlay_manual_market_lines(slate, durable_archive)\n    st.session_state["daily_slate"] = slate\n    st.session_state["daily_slate_date"] = slate_date.isoformat()\n    st.session_state["daily_added"] = added\n    st.session_state["daily_skipped"] = skipped\n    st.session_state["daily_history_only"] = history_only\n    st.session_state["daily_errors"] = errors\n    st.session_state["daily_run_at"] = datetime.now(EASTERN).strftime("%b %d, %Y · %I:%M:%S %p ET")\n\nst.markdown('<div class="daily-section-head">Slate Output</div>', unsafe_allow_html=True)\n# PROJECTION_RESTART_PERSISTENCE_V1\nif st.session_state.get("daily_slate_date") != slate_date.isoformat():\n    persisted_log = load_log()\n    recovered = persisted_log.loc[\n        persisted_log.get("game_date", pd.Series(index=persisted_log.index, dtype=str)).astype(str).eq(slate_date.isoformat())\n    ].copy() if not persisted_log.empty else pd.DataFrame()\n    if not recovered.empty:\n        durable_archive = load_projection_archive(ARCHIVE_PATH, st.secrets)\n        recovered = overlay_manual_market_lines(recovered, durable_archive)\n        st.session_state["daily_slate"] = recovered\n        st.session_state["daily_added"] = 0\n        st.session_state["daily_skipped"] = len(recovered)\n        st.session_state["daily_history_only"] = []\n        st.session_state["daily_errors"] = []\n        st.session_state["daily_run_at"] = "Recovered from frozen projection log"\n    else:\n        for key in ("daily_slate", "daily_added", "daily_skipped", "daily_history_only", "daily_errors", "daily_run_at"):\n            st.session_state.pop(key, None)\n    st.session_state["daily_slate_date"] = slate_date.isoformat()\n\nslate = st.session_state.get("daily_slate")\n'''
    text = replace_once(text, run_old, run_new, "daily restart rehydrate")

    manual_anchor = '''        st.caption("Open each pitcher bar and enter the real sportsbook lines you want Top Plays to evaluate. Manual values override paid API lines. Half-lines such as 4.5, 15.5, and 5.5 are supported; a blank market is excluded from Top Plays unless a paid active line already exists.")\n        manual_line_values: dict[str, dict[str, str]] = {}\n'''
    manual_new = '''        st.caption("Open each pitcher bar and enter the real sportsbook lines you want Top Plays to evaluate. Manual values override paid API lines. Half-lines such as 4.5, 15.5, and 5.5 are supported; a blank market is excluded from Top Plays unless a paid active line already exists. Saved manual lines reload automatically after an app restart.")\n        durable_archive = load_projection_archive(ARCHIVE_PATH, st.secrets)\n        slate = overlay_manual_market_lines(slate, durable_archive)\n        st.session_state["daily_slate"] = slate\n        manual_line_values: dict[str, dict[str, str]] = {}\n'''
    text = replace_once(text, manual_anchor, manual_new, "daily durable manual overlay")

    inputs_old = '''                k_raw = l1.text_input("Strikeout line", placeholder="e.g. 4.5", key=f"daily_manual_k_{row_key}")\n                outs_raw = l2.text_input("Total outs line", placeholder="e.g. 15.5", key=f"daily_manual_outs_{row_key}")\n                hits_raw = l3.text_input("Hits allowed line", placeholder="e.g. 5.5", key=f"daily_manual_hits_{row_key}")\n'''
    inputs_new = '''                k_raw = l1.text_input("Strikeout line", value=_manual_input_default(manual_row, "active_strikeout_line", "active_strikeout_line_source"), placeholder="e.g. 4.5", key=f"daily_manual_k_{row_key}")\n                outs_raw = l2.text_input("Total outs line", value=_manual_input_default(manual_row, "active_outs_line", "active_outs_line_source"), placeholder="e.g. 15.5", key=f"daily_manual_outs_{row_key}")\n                hits_raw = l3.text_input("Hits allowed line", value=_manual_input_default(manual_row, "active_hits_allowed_line", "active_hits_allowed_line_source"), placeholder="e.g. 5.5", key=f"daily_manual_hits_{row_key}")\n'''
    text = replace_once(text, inputs_old, inputs_new, "daily manual input defaults")

    apply_old = '''                applied = apply_active_market_lines(slate_date.isoformat(), parsed_lines)\n                archived = commit_projection_archive(slate, parsed_lines, slate_date.isoformat())\n                refreshed_log = load_log()\n                st.session_state["daily_slate"] = refreshed_log.loc[refreshed_log.get("game_date", pd.Series(dtype=str)).astype(str).eq(slate_date.isoformat())].copy()\n                st.session_state["daily_archive_saved_at"] = datetime.now(EASTERN).strftime("%b %d, %Y · %I:%M:%S %p ET")\n                st.success(f"Applied {applied} active sportsbook line(s) to Top Plays and added {archived} pitcher projection(s) to the Projection Archive.")\n'''
    apply_new = '''                archived = commit_projection_archive(slate, parsed_lines, slate_date.isoformat())\n                applied = filled_lines\n                refreshed_log = load_log()\n                refreshed_slate = refreshed_log.loc[refreshed_log.get("game_date", pd.Series(dtype=str)).astype(str).eq(slate_date.isoformat())].copy()\n                durable_archive = load_projection_archive(ARCHIVE_PATH, st.secrets)\n                st.session_state["daily_slate"] = overlay_manual_market_lines(refreshed_slate, durable_archive)\n                st.session_state["daily_slate_date"] = slate_date.isoformat()\n                st.session_state["daily_archive_saved_at"] = datetime.now(EASTERN).strftime("%b %d, %Y · %I:%M:%S %p ET")\n                st.success(f"Persisted {applied} manual sportsbook line(s) for Top Plays and saved {archived} pitcher projection row(s) to restart-safe storage.")\n'''
    text = replace_once(text, apply_old, apply_new, "daily durable save")

    DAILY.write_text(text, encoding="utf-8")


def patch_top() -> None:
    text = TOP.read_text(encoding="utf-8")
    if "TOP_PLAYS_DURABLE_MANUAL_LINES_V1" in text:
        return
    text = replace_once(
        text,
        "from training.bet_storage import append_bet\n",
        "from training.bet_storage import append_bet\nfrom training.projection_storage import load_projection_archive, overlay_manual_market_lines\n",
        "top storage import",
    )
    text = replace_once(
        text,
        'BET_LOG = ROOT / "data" / "bet_log.csv"\n',
        'BET_LOG = ROOT / "data" / "bet_log.csv"\nARCHIVE_PATH = ROOT / "data" / "projection_archive.csv"\n',
        "top archive path",
    )
    slate_old = '''slate = history.loc[history.get("game_date", pd.Series(dtype=str)).astype(str).eq(today)].copy()\nif slate.empty:\n'''
    slate_new = '''slate = history.loc[history.get("game_date", pd.Series(dtype=str)).astype(str).eq(today)].copy()\n# TOP_PLAYS_DURABLE_MANUAL_LINES_V1\ndurable_archive = load_projection_archive(ARCHIVE_PATH, st.secrets)\nslate = overlay_manual_market_lines(slate, durable_archive)\nif slate.empty:\n'''
    text = replace_once(text, slate_old, slate_new, "top durable manual overlay")
    TOP.write_text(text, encoding="utf-8")


def patch_history() -> None:
    text = HISTORY.read_text(encoding="utf-8")
    if "PROJECTION_HISTORY_DURABLE_ARCHIVE_V1" in text:
        return
    text = replace_once(
        text,
        "from navigation import render_sidebar\n",
        "from navigation import render_sidebar\nfrom training.projection_storage import build_projection_archive_view, load_projection_archive\n",
        "history storage import",
    )
    pattern = re.compile(r"def load_user_archive\(evidence: pd.DataFrame\) -> pd.DataFrame:.*?\n\ndef load_observation_history", re.S)
    match = pattern.search(text)
    if not match:
        raise RuntimeError("Missing patch anchor: load_user_archive")
    replacement = '''def load_user_archive(evidence: pd.DataFrame) -> pd.DataFrame:\n    # PROJECTION_HISTORY_DURABLE_ARCHIVE_V1\n    durable_manual = load_projection_archive(ARCHIVE_PATH, st.secrets)\n    return build_projection_archive_view(evidence, durable_manual)\n\n\ndef load_observation_history'''
    text = text[:match.start()] + replacement + text[match.end():]
    text = text.replace(
        "This is the day-to-day archive you approve from Daily Projection Run. Your entered sportsbook lines are execution data attached to the frozen projections; automatic background captures stay out of this primary view.",
        "Every frozen daily projection slate appears here automatically. Your sportsbook lines are a durable execution overlay saved separately, so a reboot cannot remove the slate or detach previously saved manual lines.",
        1,
    )
    text = text.replace(
        "No manually committed projection slates yet. Run Daily Projection Run, enter the sportsbook lines, then use Apply Lines + Add to Projection Archive.",
        "No frozen projection slates are available yet. Daily Projection Run or the automatic capture job will populate this archive.",
        1,
    )
    HISTORY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_daily()
    patch_top()
    patch_history()


if __name__ == "__main__":
    main()

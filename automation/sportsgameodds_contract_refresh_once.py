from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def remove_function(text: str, name: str) -> str:
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: expected one top-level function, found {len(matches)}")
    node = matches[0]
    start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
    end = int(node.end_lineno or node.lineno)
    del lines[start:end]
    return "".join(lines)


def refresh_top_plays() -> None:
    path = "pages/6_Top_Plays.py"
    text = read(path)
    text = replace_once(text, "from automation.daily_projection_runner import LOG_PATH, game_log\n", "from automation.daily_projection_runner import LOG_PATH\n", "top plays game_log import")
    text = replace_once(text, "from engine.bet_lean import projection_side\n", "", "top plays projection_side import")
    text = remove_function(text, "weighted")
    write(path, text)


def refresh_history_numeric_lines() -> None:
    path = "pages/4_Projection_History.py"
    text = read(path)
    old = '''    for col in (\n        "manual_strikeout_line", "projection", "actual_strikeouts",\n        "manual_outs_line", "outs_projection", "actual_outs",\n        "manual_hits_allowed_line", "hits_projection", "actual_hits_allowed",\n    ):\n'''
    new = '''    for col in (\n        "manual_strikeout_line", "active_strikeout_line", "projection", "actual_strikeouts",\n        "manual_outs_line", "active_outs_line", "outs_projection", "actual_outs",\n        "manual_hits_allowed_line", "active_hits_allowed_line", "hits_projection", "actual_hits_allowed",\n    ):\n'''
    text = replace_once(text, old, new, "history numeric line normalization")
    write(path, text)


def refresh_app_contract() -> None:
    path = "tests/test_app_contract.py"
    text = read(path)
    old = '''def test_daily_run_owns_paid_odds_workflow_and_projection_reuses_snapshot():\n    source = APP.read_text(encoding="utf-8")\n    daily = (ROOT / "pages" / "5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert "get_event_props" not in source\n    assert "extract_player_odds" not in source\n    assert "load_pitcher_strikeout_odds" in source\n    assert "refresh_strikeout_snapshot" in daily\n    assert "resolve_api_key" in daily\n    assert "pitcher_strikeouts_alternate" in source\n'''
    new = '''def test_automated_odds_workflow_is_background_owned_and_projection_reuses_snapshot():\n    source = APP.read_text(encoding="utf-8")\n    daily = (ROOT / "pages" / "5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    capture = (ROOT / ".github" / "workflows" / "sportsgameodds-capture.yml").read_text(encoding="utf-8")\n    provider = (ROOT / "engine" / "sportsgameodds.py").read_text(encoding="utf-8")\n    assert "get_event_props" not in source\n    assert "extract_player_odds" not in source\n    assert "load_pitcher_strikeout_odds" in source\n    assert "refresh_strikeout_snapshot" not in daily\n    assert "resolve_api_key" not in daily\n    assert "SPORTSGAMEODDS_API_KEY" in capture\n    assert "pitcher_strikeouts" in provider and "pitcher_outs" in provider and "pitcher_hits_allowed" in provider\n    assert "pitcher_strikeouts_alternate" in source\n'''
    text = replace_once(text, old, new, "app odds workflow contract")
    write(path, text)


def refresh_bet_add_contract() -> None:
    path = "tests/test_bet_add_buttons_contract.py"
    text = read(path)
    old = '''    assert "Line integrity: every ranked leg below uses an active sportsbook line" in source\n    assert "Sportsbook lines and odds are execution information only" in source\n    assert "market_health=health_map" in source\n    assert 'plays["Live Offer"] = False' in source\n    assert "api_key = None" in source\n'''
    new = '''    assert "Line integrity: every ranked leg below uses an authentic active sportsbook line" in source\n    assert "Sportsbook lines and odds are execution information only" in source\n    assert "market_health=health_map" in source\n    assert '("Live Offer", False)' in source\n    assert "load_pitcher_market_odds" in source\n    assert "api_key = None" not in source\n    assert "api.the-odds-api.com" not in source\n'''
    text = replace_once(text, old, new, "Top Plays overlay contract")
    write(path, text)


def refresh_daily_ui_contract() -> None:
    path = "tests/test_daily_run_automated_lines_ui.py"
    text = read(path)
    old = '''    # Keep the explicitly labeled K-only emergency backup available without\n    # turning it back into the primary execution-line workflow.\n    assert "LOAD STRIKEOUT LINES · BACKUP API" in source\n    assert "SportsGameOdds remains the primary automated execution-line source." in source\n'''
    new = '''    # The reserve Odds API backend stays in the engine, but the normal Daily Run\n    # surface is now fully automated and exposes no paid/manual line controls.\n    assert "LOAD STRIKEOUT LINES · BACKUP API" not in source\n    assert "refresh_strikeout_snapshot" not in source\n    assert "Odds API credits remaining" not in source\n'''
    text = replace_once(text, old, new, "Daily Run backup UI contract")
    write(path, text)


def refresh_explainability_contract() -> None:
    path = "tests/test_explainability_ui.py"
    text = read(path)
    text = replace_once(
        text,
        '    assert "static_explanation(\\"odds_credits\\")" in daily\n',
        '    assert "static_explanation(\\"odds_credits\\")" not in daily\n    assert "SportsGameOdds captures real pregame lines automatically" in (ROOT / "engine/explainability_ui.py").read_text(encoding="utf-8")\n',
        "explainability odds credits contract",
    )
    write(path, text)


def refresh_frozen_execution_contract() -> None:
    path = "tests/test_frozen_execution_history.py"
    text = read(path)
    old = '''    daily = open("pages/5_Daily_Projection_Run.py", encoding="utf-8").read()\n    history = open("pages/4_Projection_History.py", encoding="utf-8").read()\n    storage = open("training/projection_storage.py", encoding="utf-8").read()\n    assert "manual_outs_side" in daily and "manual_hits_allowed_side" in daily\n    assert "side_not_frozen_pregame" in daily\n'''
    new = '''    daily = open("pages/5_Daily_Projection_Run.py", encoding="utf-8").read()\n    history = open("pages/4_Projection_History.py", encoding="utf-8").read()\n    storage = open("training/projection_storage.py", encoding="utf-8").read()\n    execution = open("engine/execution_history.py", encoding="utf-8").read()\n    assert "manual_outs_side" not in daily and "manual_hits_allowed_side" not in daily\n    assert "manual_outs_side" in storage and "manual_hits_allowed_side" in storage\n    assert "side_not_frozen_pregame" in execution\n'''
    text = replace_once(text, old, new, "frozen execution integration contract")
    write(path, text)


def refresh_manual_market_contract() -> None:
    path = "tests/test_manual_market_controls.py"
    text = read(path)
    old = '''    # Historical MANUAL rows remain readable by Main Projection and durable\n    # storage even though new slates no longer expose hand-entry controls.\n    assert "manual_k_line" in projection\n    assert "manual_outs_line" in projection\n    assert "manual_hits_line" in projection\n    assert "overlay_manual_market_lines" in daily\n    assert "commit_projection_archive" in daily\n'''
    new = '''    # Historical MANUAL rows remain readable through the durable overlay even\n    # though current-page variables now use accurate active-line names.\n    storage = Path("training/projection_storage.py").read_text(encoding="utf-8")\n    assert "active_k_line" in projection\n    assert "active_outs_line" in projection\n    assert "active_hits_line" in projection\n    assert "overlay_manual_market_lines" in daily\n    assert "commit_projection_archive" not in daily\n    assert 'result.at[idx, source_col] = "MANUAL"' in storage\n    assert "manual_strikeout_line" in storage\n    assert "manual_outs_line" in storage\n    assert "manual_hits_allowed_line" in storage\n'''
    text = replace_once(text, old, new, "manual compatibility contract")
    write(path, text)


def refresh_odds_credit_contract() -> None:
    path = "tests/test_odds_credit_saver.py"
    text = read(path)
    old1 = '''def test_top_plays_has_no_paid_odds_runtime():\n    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")\n    assert 'api_key = None  # Paid Odds API access is intentionally restricted to Daily Projection Run.' in source\n    assert 'api_key = secret()' not in source\n'''
    new1 = '''def test_top_plays_has_no_paid_odds_runtime():\n    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")\n    assert 'api_key = secret()' not in source\n    assert 'api_key = None' not in source\n    assert 'api.the-odds-api.com' not in source\n    assert 'load_pitcher_market_odds' in source\n    assert 'attach_sportsgameodds_prices' in source\n'''
    text = replace_once(text, old1, new1, "Top Plays paid runtime test")
    text = replace_once(
        text,
        "    assert 'this page never calls the Odds API' in source\n",
        "    assert 'api.the-odds-api.com' not in source\n    assert 'No current automated sportsbook line has been captured' in source\n",
        "Projection disk-only odds test",
    )
    old3 = '''def test_daily_projection_page_owns_legacy_paid_k_backup_button_only():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert 'LOAD STRIKEOUT LINES · BACKUP API' in source\n    assert 'refresh_strikeout_snapshot' in source\n    assert 'Optional fallback only.' in source\n    assert 'SportsGameOdds remains the primary automated execution-line source.' in source\n'''
    new3 = '''def test_daily_projection_page_has_no_visible_legacy_paid_k_controls():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert 'LOAD STRIKEOUT LINES · BACKUP API' not in source\n    assert 'refresh_strikeout_snapshot' not in source\n    assert 'Odds API credits remaining' not in source\n    assert '📡 Automated sportsbook lines' in source\n'''
    text = replace_once(text, old3, new3, "Daily paid backup visibility test")
    write(path, text)


def refresh_sidebar_metric_contract() -> None:
    path = "tests/test_sidebar_metric_explainability_v2.py"
    text = read(path)
    text = replace_once(text, '"history_archived_slates", "history_archived_pitchers", "history_manual_lines", "history_latest_slate",', '"history_archived_slates", "history_archived_pitchers", "history_real_lines", "history_latest_slate",', "history metric key")
    write(path, text)


def refresh_command_center_contract() -> None:
    path = "tests/test_ui_command_center_contract.py"
    text = read(path)
    old = '    assert "this page never calls the Odds API" in source\n'
    new = '    assert "api.the-odds-api.com" not in source\n    assert "No current automated sportsbook line has been captured" in source\n'
    count = text.count(old)
    if count != 3:
        raise RuntimeError(f"command center Odds API assertions: expected 3, found {count}")
    text = text.replace(old, new)
    write(path, text)


def cleanup_temp_files() -> None:
    for rel in (
        "automation/sportsgameodds_contract_refresh_once.py",
        ".github/workflows/sportsgameodds-contract-refresh-once.yml",
    ):
        target = ROOT / rel
        if target.exists():
            target.unlink()


def main() -> None:
    refresh_top_plays()
    refresh_history_numeric_lines()
    refresh_app_contract()
    refresh_bet_add_contract()
    refresh_daily_ui_contract()
    refresh_explainability_contract()
    refresh_frozen_execution_contract()
    refresh_manual_market_contract()
    refresh_odds_credit_contract()
    refresh_sidebar_metric_contract()
    refresh_command_center_contract()
    cleanup_temp_files()
    print("SportsGameOdds contract refresh applied.")


if __name__ == "__main__":
    main()

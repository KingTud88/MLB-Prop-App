from __future__ import annotations

from pathlib import Path

PATH = Path("automation/daily_projection_runner.py")


def _replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Required source anchor not found: {old[:80]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        "from engine.workload_context import WORKLOAD_VERSION, WorkloadContext, build_workload_context\n",
        "from engine.workload_context import WORKLOAD_VERSION, WorkloadContext, build_workload_context\nfrom engine.role_workload_gate import build_role_workload_decision\n",
    )
    text = _replace_once(
        text,
        'OBS_LOG_PATH = ROOT / "data" / "starter_observation_log.csv"\n',
        'OBS_LOG_PATH = ROOT / "data" / "starter_observation_log.csv"\nROLE_RUNTIME_STATE_PATH = ROOT / "data" / "starter_role_runtime_state.csv"\n',
    )
    anchor = "def record_history_only(row: dict, reason: str = \"no usable starter history\", history_games: int = 0) -> bool:\n"
    loader = '''@lru_cache(maxsize=1)\ndef load_role_runtime_state() -> pd.DataFrame:\n    try:\n        return pd.read_csv(ROLE_RUNTIME_STATE_PATH) if ROLE_RUNTIME_STATE_PATH.exists() else pd.DataFrame()\n    except Exception:\n        return pd.DataFrame()\n\n\n'''
    text = _replace_once(text, anchor, loader + anchor)
    workload_anchor = '    workload = build_workload_context(log, row.get("game_time") or row.get("game_date"))\n'
    role_block = '''    workload = build_workload_context(log, row.get("game_time") or row.get("game_date"))\n    role_workload = build_role_workload_decision(\n        log,\n        workload,\n        load_role_runtime_state(),\n        game_date=row.get("game_time") or row.get("game_date"),\n        mode="shadow",\n    )\n'''
    text = _replace_once(text, workload_anchor, role_block)
    text = _replace_once(
        text,
        "        **workload.snapshot_fields(),\n        **team_leash.snapshot_fields(),\n",
        "        **workload.snapshot_fields(),\n        **role_workload.snapshot_fields(),\n        **team_leash.snapshot_fields(),\n",
    )
    PATH.write_text(text, encoding="utf-8")
    print("Integrated starter-role workload diagnostics into production automation runner in shadow mode")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from training.starter_role_backtest import build_role_backtest

RUNTIME_STATE_VERSION = "starter-role-runtime-state-v1"
KEEP = [
    "game_date", "pitcher_id", "starter_role_label",
    "projected_pitches", "actual_pitches",
    "projected_bf", "actual_bf",
    "projected_outs", "actual_outs",
]


def build_runtime_state(projection_log: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    detail = build_role_backtest(projection_log, seasons)
    if detail.empty:
        return pd.DataFrame(columns=[*KEEP, "runtime_state_version"])
    state = detail.copy()
    for col in KEEP:
        if col not in state.columns:
            state[col] = pd.NA
    state = state[KEEP].copy()
    state["game_date"] = pd.to_datetime(state["game_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    state["runtime_state_version"] = RUNTIME_STATE_VERSION
    state = state.sort_values(["game_date", "pitcher_id"], na_position="first").reset_index(drop=True)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Export production-readable role residual history from the validated MLB replay path.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/starter_role_runtime_state.csv"))
    parser.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    args = parser.parse_args()
    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("Projection log is empty")
    state = build_runtime_state(history, [int(s) for s in args.seasons])
    if state.empty:
        raise SystemExit("No starter role runtime state rows produced")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    state.to_csv(args.output, index=False)
    print(f"runtime_state={RUNTIME_STATE_VERSION} rows={len(state)}")


if __name__ == "__main__":
    main()

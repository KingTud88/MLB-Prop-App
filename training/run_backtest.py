from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .dataset_builder import load_snapshot_dataset
from engine.walk_forward import brier_score, calibration_table, log_loss


TARGET = "actual_strikeouts"


def _feature_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    payload = pd.json_normalize(frame["feature_payload"].apply(json.loads) if frame["feature_payload"].dtype == object else frame["feature_payload"])
    numeric = payload.select_dtypes(include=[np.number]).copy()
    numeric = numeric.replace([np.inf, -np.inf], np.nan).fillna(numeric.median(numeric_only=True)).fillna(0.0)
    return numeric, list(numeric.columns)


def walk_forward_backtest(frame: pd.DataFrame, min_train: int = 500, test_size: int = 100) -> pd.DataFrame:
    frame = frame.sort_values(["game_date", "captured_at_utc"]).reset_index(drop=True)
    X, features = _feature_frame(frame)
    y = pd.to_numeric(frame[TARGET], errors="raise").to_numpy(dtype=float)
    rows: list[dict[str, float | int | str]] = []

    for start in range(min_train, len(frame), test_size):
        stop = min(start + test_size, len(frame))
        if stop <= start:
            break
        model = HistGradientBoostingRegressor(
            loss="poisson",
            learning_rate=0.05,
            max_iter=250,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=42,
        )
        model.fit(X.iloc[:start][features], y[:start])
        pred = np.clip(model.predict(X.iloc[start:stop][features]), 0.0, 15.0)
        actual = y[start:stop]
        rows.append({
            "test_start": str(frame.iloc[start]["game_date"]),
            "test_end": str(frame.iloc[stop - 1]["game_date"]),
            "n_test": int(len(actual)),
            "mae": float(mean_absolute_error(actual, pred)),
            "rmse": float(np.sqrt(mean_squared_error(actual, pred))),
            "mean_error": float(np.mean(pred - actual)),
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/backtest.csv"))
    parser.add_argument("--min-train", type=int, default=500)
    parser.add_argument("--test-size", type=int, default=100)
    args = parser.parse_args()

    frame = load_snapshot_dataset(args.dataset)
    if len(frame) <= args.min_train:
        raise SystemExit(f"Need more than {args.min_train} resolved snapshots; found {len(frame)}")

    results = walk_forward_backtest(frame, args.min_train, args.test_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)

    summary = {
        "snapshots": int(len(frame)),
        "folds": int(len(results)),
        "mae_mean": float(results["mae"].mean()),
        "rmse_mean": float(results["rmse"].mean()),
        "note": "Count-model point metrics are valid only when snapshots contain frozen pregame features.",
        "calibration_available": False,
        "calibration_note": "Line-level probabilities require a defined sportsbook line per snapshot; do not infer a line from the outcome.",
    }
    args.output.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .dataset_builder import load_snapshot_dataset
from .simulation_blend import mathematical_projection, simulate_strikeouts, simulation_distribution

TARGET = "actual_strikeouts"


def _feature_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    prefix = "feature_payload."
    columns = [c for c in frame.columns if c.startswith(prefix)]
    if not columns:
        raise ValueError("No flattened feature_payload.* columns found in snapshot dataset")
    numeric = frame[columns].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.replace([np.inf, -np.inf], np.nan)
    numeric = numeric.fillna(numeric.median(numeric_only=True)).fillna(0.0)
    return numeric, columns


def _math_projection(row: dict[str, object]) -> float:
    return float(mathematical_projection(row))


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
            loss="poisson", learning_rate=0.05, max_iter=250,
            max_leaf_nodes=15, l2_regularization=1.0, random_state=42,
        )
        model.fit(X.iloc[:start][features], y[:start])
        actual = y[start:stop]
        gbm = np.clip(model.predict(X.iloc[start:stop][features]), 0.0, 15.0)

        math_preds: list[float] = []
        sim_preds: list[float] = []
        blend_preds: list[float] = []
        for offset, (_, row) in enumerate(frame.iloc[start:stop].iterrows()):
            math_pred = max(0.0, _math_projection(row.to_dict()))
            samples = simulate_strikeouts(math_pred, simulations=10000, seed=42 + start + offset)
            dist = simulation_distribution(samples)
            sim_pred = dist["sim_mean_ks"]
            math_preds.append(math_pred)
            sim_preds.append(sim_pred)
            blend_preds.append(0.5 * math_pred + 0.5 * sim_pred)

        math_preds = np.asarray(math_preds)
        sim_preds = np.asarray(sim_preds)
        blend_preds = np.asarray(blend_preds)

        def metrics(pred: np.ndarray) -> tuple[float, float]:
            return float(mean_absolute_error(actual, pred)), float(np.sqrt(mean_squared_error(actual, pred)))

        gbm_mae, gbm_rmse = metrics(gbm)
        math_mae, math_rmse = metrics(math_preds)
        sim_mae, sim_rmse = metrics(sim_preds)
        blend_mae, blend_rmse = metrics(blend_preds)
        rows.append({
            "test_start": str(frame.iloc[start]["game_date"]),
            "test_end": str(frame.iloc[stop - 1]["game_date"]),
            "n_test": int(len(actual)),
            "gbm_mae": gbm_mae, "gbm_rmse": gbm_rmse,
            "math_mae": math_mae, "math_rmse": math_rmse,
            "simulation_mae": sim_mae, "simulation_rmse": sim_rmse,
            "blend_mae": blend_mae, "blend_rmse": blend_rmse,
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
        "snapshots": int(len(frame)), "folds": int(len(results)),
        "gbm_mae_mean": float(results["gbm_mae"].mean()),
        "gbm_rmse_mean": float(results["gbm_rmse"].mean()),
        "math_mae_mean": float(results["math_mae"].mean()),
        "math_rmse_mean": float(results["math_rmse"].mean()),
        "simulation_mae_mean": float(results["simulation_mae"].mean()),
        "simulation_rmse_mean": float(results["simulation_rmse"].mean()),
        "blend_mae_mean": float(results["blend_mae"].mean()),
        "blend_rmse_mean": float(results["blend_rmse"].mean()),
        "simulation_count_per_snapshot": 10000,
        "blend_weight": 0.5,
        "calibration_available": False,
        "calibration_note": "Line-level probabilities require a defined sportsbook line per frozen pregame snapshot.",
    }
    args.output.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

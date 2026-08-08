from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from engine.walk_forward import brier_score, calibration_table, chronological_folds, log_loss
from .gbm import WalkForwardGBM


@dataclass(frozen=True)
class FoldMetrics:
    train_end: str
    test_start: str
    test_end: str
    n_train: int
    n_test: int
    mae: float
    rmse: float
    mean_error: float


def evaluate_walk_forward(
    frame: pd.DataFrame,
    feature_columns: list[str],
    target_column: str = "actual_strikeouts",
    min_train_games: int = 500,
    test_games: int = 100,
    step_games: int = 100,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit only on earlier snapshots and score the next unseen block."""
    data = frame.copy().sort_values("game_date").reset_index(drop=True)
    data["game_date"] = pd.to_datetime(data["game_date"], errors="coerce")
    data[target_column] = pd.to_numeric(data[target_column], errors="coerce")
    data = data.dropna(subset=["game_date", target_column])

    rows: list[FoldMetrics] = []
    predictions: list[pd.DataFrame] = []
    folds = list(chronological_folds(data, min_train_games=min_train_games, test_games=test_games, step_games=step_games))
    for fold in folds:
        train_mask = data["game_date"] <= fold.train_end
        test_mask = (data["game_date"] >= fold.test_start) & (data["game_date"] <= fold.test_end)
        train = data.loc[train_mask]
        test = data.loc[test_mask].copy()
        if len(train) < min_train_games or test.empty:
            continue

        model = WalkForwardGBM(feature_columns).fit(train, target_column=target_column)
        pred = model.predict_mean(test)
        actual = test[target_column].to_numpy(dtype=float)
        rows.append(FoldMetrics(
            train_end=str(fold.train_end.date()),
            test_start=str(fold.test_start.date()),
            test_end=str(fold.test_end.date()),
            n_train=len(train),
            n_test=len(test),
            mae=float(np.mean(np.abs(pred - actual))),
            rmse=float(np.sqrt(np.mean((pred - actual) ** 2))),
            mean_error=float(np.mean(pred - actual)),
        ))
        test["gbm_prediction"] = pred
        predictions.append(test)

    return pd.DataFrame([m.__dict__ for m in rows]), pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()


def line_metrics(predictions: pd.DataFrame, line: float) -> dict[str, float]:
    """Evaluate an over probability using a normal approximation to GBM mean.

    This is an evaluation helper only. A future calibrated count distribution
    should replace the normal approximation before production deployment.
    """
    if predictions.empty:
        return {"line": line, "brier": float("nan"), "log_loss": float("nan"), "calibration_error": float("nan")}
    actual_over = (predictions["actual_strikeouts"] > line).astype(float).to_numpy()
    means = predictions["gbm_prediction"].to_numpy(dtype=float)
    sd = np.sqrt(np.maximum(means * 1.15, 1.0))
    z = (line + 0.5 - means) / (sd * np.sqrt(2.0))
    p_over = 0.5 * np.array([math.erfc(value) for value in z])
    p_over = np.clip(p_over, 1e-6, 1 - 1e-6)
    cal = calibration_table(actual_over, p_over)
    error = float(cal["absolute_calibration_error"].mean()) if not cal.empty else float("nan")
    return {"line": float(line), "brier": brier_score(actual_over, p_over), "log_loss": log_loss(actual_over, p_over), "calibration_error": error}

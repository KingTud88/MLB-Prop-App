from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FoldResult:
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    n_train: int
    n_test: int


def chronological_folds(
    frame: pd.DataFrame,
    date_column: str = "game_date",
    min_train_games: int = 500,
    test_games: int = 100,
    step_games: int = 100,
) -> Iterable[FoldResult]:
    """Yield leakage-safe chronological folds for pregame modeling.

    Rows must represent one pregame snapshot per pitcher/game. No random
    shuffling is permitted. Feature generation should be performed using
    information available at snapshot time before calling this splitter.
    """
    if date_column not in frame.columns:
        raise ValueError(f"Missing required date column: {date_column}")

    data = frame.copy()
    data[date_column] = pd.to_datetime(data[date_column], errors="coerce")
    data = data.dropna(subset=[date_column]).sort_values(date_column).reset_index(drop=True)
    if len(data) < min_train_games + test_games:
        return

    for start in range(min_train_games, len(data) - test_games + 1, step_games):
        train = data.iloc[:start]
        test = data.iloc[start : start + test_games]
        yield FoldResult(
            train_end=train[date_column].max(),
            test_start=test[date_column].min(),
            test_end=test[date_column].max(),
            n_train=len(train),
            n_test=len(test),
        )


def brier_score(y_true: np.ndarray, probabilities: np.ndarray) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    if y.shape != p.shape:
        raise ValueError("y_true and probabilities must have the same shape")
    return float(np.mean((p - y) ** 2))


def log_loss(y_true: np.ndarray, probabilities: np.ndarray) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    if y.shape != p.shape:
        raise ValueError("y_true and probabilities must have the same shape")
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def calibration_table(y_true: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Return reliability-bin counts, predicted probability and observed rate."""
    p = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    y = np.asarray(y_true, dtype=float)
    if len(p) != len(y):
        raise ValueError("Inputs must have equal length")
    edges = np.linspace(0.0, 1.0, bins + 1)
    bucket = np.clip(np.digitize(p, edges, right=True) - 1, 0, bins - 1)
    rows = []
    for i in range(bins):
        mask = bucket == i
        if not mask.any():
            continue
        rows.append({
            "bin": i,
            "n": int(mask.sum()),
            "predicted_probability": float(p[mask].mean()),
            "observed_rate": float(y[mask].mean()),
            "absolute_calibration_error": float(abs(p[mask].mean() - y[mask].mean())),
        })
    return pd.DataFrame(rows)

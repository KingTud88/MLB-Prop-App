from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor


@dataclass
class WalkForwardGBM:
    """Gradient-boosted strikeout mean model.

    Training is intentionally separated from prediction. Callers must supply
    only pregame features and use chronological folds for evaluation.
    """

    feature_columns: Sequence[str]
    model: HistGradientBoostingRegressor | None = None

    def fit(self, train: pd.DataFrame, target_column: str = "strikeouts") -> "WalkForwardGBM":
        missing = [c for c in self.feature_columns if c not in train.columns]
        if target_column not in train.columns:
            missing.append(target_column)
        if missing:
            raise ValueError(f"Missing training columns: {missing}")

        X = train[list(self.feature_columns)].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        y = pd.to_numeric(train[target_column], errors="coerce")
        valid = y.notna()
        if valid.sum() < 100:
            raise ValueError("At least 100 valid training rows are required")

        self.model = HistGradientBoostingRegressor(
            loss="poisson",
            learning_rate=0.04,
            max_iter=300,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=42,
        )
        self.model.fit(X.loc[valid], y.loc[valid])
        return self

    def predict_mean(self, frame: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model must be fitted before prediction")
        X = frame[list(self.feature_columns)].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return np.clip(self.model.predict(X), 0.0, 15.0)

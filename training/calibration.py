from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss


def empirical_over_probability(samples: np.ndarray, line: float) -> float:
    """P(K > line) from a simulated pregame distribution."""
    values = np.asarray(samples, dtype=float)
    return float(np.mean(values > float(line))) if values.size else 0.0


def fit_isotonic_calibrator(raw_probabilities: np.ndarray, outcomes: np.ndarray) -> IsotonicRegression:
    """Fit only on prior/fold-training observations to prevent future leakage."""
    calibrator = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
    calibrator.fit(np.asarray(raw_probabilities, dtype=float), np.asarray(outcomes, dtype=float))
    return calibrator


def calibration_metrics(probabilities: np.ndarray, outcomes: np.ndarray) -> dict[str, float]:
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    if not len(p):
        return {"brier_score": 0.0, "mean_predicted_probability": 0.0, "empirical_rate": 0.0}
    return {
        "brier_score": float(brier_score_loss(y, p)),
        "mean_predicted_probability": float(np.mean(p)),
        "empirical_rate": float(np.mean(y)),
    }

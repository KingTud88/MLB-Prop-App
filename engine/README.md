# StrikeOut King 9000 — Projection Engine

The engine is intentionally separated from Streamlit UI code.

## Pipeline

1. `features.py` normalizes pregame pitcher, lineup, and context inputs.
2. `projection_engine.py` runs the independent game simulation and mathematical projection paths.
3. `walk_forward.py` provides chronological folds and probability calibration metrics.
4. A future trained gradient-boosted model will replace the mathematical baseline without changing the `ProjectionResult` interface.

## Leakage rule

Only information available at the saved pregame snapshot may enter a prediction. Postgame statistics, closing lines, final outcomes, and later injury/weather updates must never be used as features for that snapshot.

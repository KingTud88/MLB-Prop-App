from __future__ import annotations

import pandas as pd

from training.workload_v25_metric_gate_backtest import GATE_MIN_CHANGED, _prior_gate


def _prior_rows(n: int, *, actual: float, v23: float, v24: float, metric: str = "pitches") -> pd.DataFrame:
    return pd.DataFrame({
        f"actual_{metric}": [actual] * n,
        f"bias_controlled_{metric}": [v23] * n,
        f"v24_candidate_{metric}": [v24] * n,
    })


def test_metric_gate_requires_enough_prior_changed_rows() -> None:
    prior = _prior_rows(GATE_MIN_CHANGED - 1, actual=90.0, v23=86.0, v24=88.0)
    earned, n, *_rest, gate = _prior_gate(prior, "pitches")
    assert not earned
    assert n == GATE_MIN_CHANGED - 1
    assert gate == "INSUFFICIENT_CHANGED_HISTORY"


def test_metric_gate_can_earn_when_prior_mae_bias_and_win_share_all_improve() -> None:
    prior = _prior_rows(GATE_MIN_CHANGED, actual=90.0, v23=86.0, v24=88.0)
    earned, n, rel, v23_bias, v24_bias, gate = _prior_gate(prior, "pitches")
    assert earned
    assert n == GATE_MIN_CHANGED
    assert rel > 0.0
    assert abs(v24_bias) < abs(v23_bias)
    assert gate == "EARNED"


def test_metric_gate_rejects_mae_gain_when_absolute_bias_worsens() -> None:
    # v23 is unbiased overall with symmetric +/-4 errors. v24 improves MAE by
    # trimming the positive half to +1 but moves the negative half to -5. The
    # mean absolute error improves from 4 to 3, while absolute bias worsens from
    # 0 to 2. Bias guardrail must veto activation.
    rows = []
    half = GATE_MIN_CHANGED // 2
    for i in range(GATE_MIN_CHANGED):
        if i < half:
            rows.append({"actual_pitches": 90.0, "bias_controlled_pitches": 94.0, "v24_candidate_pitches": 91.0})
        else:
            rows.append({"actual_pitches": 90.0, "bias_controlled_pitches": 86.0, "v24_candidate_pitches": 85.0})
    prior = pd.DataFrame(rows)
    earned, _n, rel, v23_bias, v24_bias, gate = _prior_gate(prior, "pitches")
    assert rel > 0.0
    assert abs(v24_bias) > abs(v23_bias)
    assert not earned
    assert "BIAS" in gate

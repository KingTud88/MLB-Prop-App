import pandas as pd

from engine.hits_allowed import project_hits_allowed
from engine.outs_projection import project_total_outs


def _log():
    return pd.DataFrame({
        "bf": [21, 22, 23, 24, 25, 26, 25, 24],
        "hits": [4, 5, 5, 6, 5, 6, 7, 5],
        "outs": [15, 16, 17, 18, 18, 19, 18, 17],
        "pitches": [82, 86, 89, 93, 96, 99, 97, 94],
    })


def test_hits_projection_increases_with_workload_exposure():
    log = _log()
    low = project_hits_allowed(log, expected_bf=19, bf_sd=2.5, opponent_hit_rate=.235, seed=11, draws=12000)
    high = project_hits_allowed(log, expected_bf=27, bf_sd=2.5, opponent_hit_rate=.235, seed=11, draws=12000)
    assert high.ensemble_mean > low.ensemble_mean
    assert high.over_probabilities[5.5] > low.over_probabilities[5.5]


def test_outs_projection_increases_with_workload_target():
    log = _log()
    low = project_total_outs(log, expected_outs=14.5, workload_sd=3.5, seed=22, draws=12000)
    high = project_total_outs(log, expected_outs=19.5, workload_sd=3.5, seed=22, draws=12000)
    assert high.ensemble_mean > low.ensemble_mean
    assert high.over_probabilities[15.5] > low.over_probabilities[15.5]


def test_outs_old_call_signature_still_works():
    result = project_total_outs(_log(), seed=1, draws=2000)
    assert 0 <= result.ensemble_mean <= 27

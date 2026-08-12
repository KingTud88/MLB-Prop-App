import pandas as pd

from engine.decision_learning import (
    attach_decision_profiles,
    decision_profile_for_play,
    decision_tier_report,
    probability_band,
    quality_band,
    wilson_lower_bound,
)


def _walk_forward_rows(n: int, *, market: str = "Strikeouts", probability: float = 0.67, quality: int = 75, hits: int | None = None) -> pd.DataFrame:
    if hits is None:
        hits = int(round(n * probability))
    outcomes = [True] * int(hits) + [False] * max(int(n - hits), 0)
    return pd.DataFrame({
        "Market": [market] * n,
        "Model Probability": [probability] * n,
        "Data Quality": [quality] * n,
        "Hit": outcomes[:n],
    })


def test_probability_and_quality_bands_are_stable_at_boundaries():
    assert probability_band(0.55) == "55–59%"
    assert probability_band(0.65) == "65–69%"
    assert probability_band(0.80) == "80–89%"
    assert quality_band(60) == "60–69"
    assert quality_band(70) == "70–79"
    assert quality_band(90) == "90+"


def test_small_samples_stay_learning_even_when_results_are_perfect():
    report = decision_tier_report(_walk_forward_rows(10, probability=0.67, quality=75, hits=10))
    row = report.iloc[0]
    assert row["Decision Evidence"] == "LEARNING"
    assert row["Settled Legs"] == 10


def test_supported_segment_requires_real_volume_and_reasonable_calibration():
    report = decision_tier_report(_walk_forward_rows(24, probability=0.60, quality=75, hits=15))
    row = report.iloc[0]
    assert row["Decision Evidence"] == "SUPPORTED"
    assert row["Hit Rate"] == 15 / 24
    assert row["Calibration Gap"] < 0.03


def test_materially_bad_segment_becomes_underperforming_only_after_enough_evidence():
    report = decision_tier_report(_walk_forward_rows(35, probability=0.75, quality=85, hits=14))
    row = report.iloc[0]
    assert row["Decision Evidence"] == "UNDERPERFORMING"
    assert row["Settled Legs"] == 35


def test_sportsbook_fields_do_not_change_decision_learning():
    base = _walk_forward_rows(24, probability=0.60, quality=75, hits=15)
    priced = base.copy()
    priced["Book"] = ["Book A" if i % 2 else "Book B" for i in range(len(priced))]
    priced["Odds"] = [5000 - i * 300 for i in range(len(priced))]
    priced["Edge"] = [0.25 if i % 2 else -0.25 for i in range(len(priced))]
    report_a = decision_tier_report(base)
    report_b = decision_tier_report(priced)
    pd.testing.assert_frame_equal(report_a, report_b)


def test_attaching_profiles_never_reorders_or_removes_top_plays():
    report = decision_tier_report(_walk_forward_rows(24, probability=0.60, quality=75, hits=15))
    plays = pd.DataFrame([
        {"Rank": 1, "Pitcher": "A", "Market": "Strikeouts", "Model Probability": 0.60, "Data Quality": 75},
        {"Rank": 2, "Pitcher": "B", "Market": "Hits Allowed", "Model Probability": 0.72, "Data Quality": 88},
    ])
    enriched = attach_decision_profiles(plays, report)
    assert list(enriched["Rank"]) == [1, 2]
    assert list(enriched["Pitcher"]) == ["A", "B"]
    assert len(enriched) == 2
    assert enriched.loc[0, "Decision Evidence"] == "SUPPORTED"
    assert enriched.loc[1, "Decision Evidence"] == "LEARNING"


def test_decision_profile_matches_exact_market_probability_and_quality_segment():
    report = decision_tier_report(_walk_forward_rows(24, market="Strikeouts", probability=0.60, quality=75, hits=15))
    profile = decision_profile_for_play(
        {"Market": "Strikeouts", "Model Probability": 0.61, "Data Quality": 78},
        report,
    )
    assert profile["Decision Evidence"] == "SUPPORTED"
    assert profile["Decision Sample"] == 24
    assert profile["Decision Probability Band"] == "60–64%"
    assert profile["Decision Quality Band"] == "70–79"


def test_wilson_lower_bound_is_conservative():
    lower = wilson_lower_bound(15, 20)
    assert lower is not None
    assert 0.50 < lower < 0.75

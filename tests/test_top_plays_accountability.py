from __future__ import annotations

import pandas as pd

from training.top_plays_accountability import (
    PRODUCTION_AUTHORITY,
    build_accountability_summary,
    build_findings,
    enrich_detail,
    margin_percent,
    margin_percent_band,
)


def _leg(**overrides):
    base = {
        "Rank": 1,
        "Market": "Strikeouts",
        "Side": "OVER",
        "Line": 5.5,
        "Projection": 6.6,
        "Model Probability": 0.70,
        "Data Quality": 75,
        "Status": "STRONG",
        "Probability Band": "70–74%",
        "Quality Band": "70–79",
        "Line Source": "MANUAL",
        "Lineup State": "CONFIRMED",
        "Weather Risk": "NONE",
        "Historical Market Health": "LEARNING",
        "Projection Margin": 1.1,
        "Outcome Margin": 1.5,
        "Postmortem Date": "2026-08-16",
        "Hit": True,
    }
    base.update(overrides)
    return base


def test_margin_percentage_is_market_relative_and_banded() -> None:
    assert margin_percent(6.6, 5.5) == 0.2
    assert margin_percent_band(0.099) == "<10%"
    assert margin_percent_band(0.10) == "10–14%"
    assert margin_percent_band(0.15) == "15–19%"
    assert margin_percent_band(0.20) == "20%+"
    enriched = enrich_detail(pd.DataFrame([_leg()]))
    assert enriched.iloc[0]["Margin % Band"] == "20%+"


def test_tiny_perfect_or_awful_samples_stay_learning() -> None:
    perfect = pd.DataFrame([_leg(Rank=i + 1, **{"Model Probability": 0.60}) for i in range(5)])
    perfect_report = build_accountability_summary(perfect)
    perfect_overall = perfect_report.loc[perfect_report["Dimension"].eq("OVERALL")].iloc[0]
    assert perfect_overall["Hit Rate"] == 1.0
    assert perfect_overall["Evidence"] == "LEARNING"

    awful = pd.DataFrame([_leg(Rank=i + 1, Hit=False, **{"Model Probability": 0.90}) for i in range(5)])
    awful_report = build_accountability_summary(awful)
    awful_overall = awful_report.loc[awful_report["Dimension"].eq("OVERALL")].iloc[0]
    assert awful_overall["Hit Rate"] == 0.0
    assert awful_overall["Evidence"] == "LEARNING"


def test_large_bad_sample_can_be_underperforming_but_never_production_authority() -> None:
    rows = []
    for i in range(30):
        rows.append(
            _leg(
                Rank=(i % 5) + 1,
                Hit=(i < 10),
                **{"Model Probability": 0.80, "Postmortem Date": f"2026-08-{10 + (i // 5):02d}"},
            )
        )
    report = build_accountability_summary(pd.DataFrame(rows))
    overall = report.loc[report["Dimension"].eq("OVERALL")].iloc[0]
    assert overall["Settled Legs"] == 30
    assert overall["Evidence"] == "UNDERPERFORMING"
    assert overall["Production Authority"] == PRODUCTION_AUTHORITY == "NONE"


def test_summary_contains_requested_accountability_dimensions() -> None:
    report = build_accountability_summary(pd.DataFrame([_leg()]))
    dimensions = set(report["Dimension"])
    assert {"RANK", "MARKET", "SIDE", "STATUS", "PROBABILITY BAND", "QUALITY BAND", "MARGIN % BAND", "LINEUP STATE", "WEATHER RISK"}.issubset(dimensions)


def test_findings_call_out_limited_real_line_and_hits_coverage() -> None:
    detail = pd.DataFrame([
        _leg(Market="Strikeouts"),
        _leg(Rank=2, Market="Total Outs", Line=16.5, Projection=14.5, Side="UNDER"),
    ])
    summary = build_accountability_summary(detail)
    coverage = pd.DataFrame([
        {"Date": "2026-08-15", "Rows With Any Persisted Real Line": 0},
        {"Date": "2026-08-16", "Rows With Any Persisted Real Line": 20},
    ])
    findings = build_findings(detail, summary, coverage)
    hits = findings.loc[findings["Finding"].eq("HITS ALLOWED SAMPLE")].iloc[0]
    overall = findings.loc[findings["Finding"].eq("OVERALL ACCOUNTABILITY STATE")].iloc[0]
    coverage_row = findings.loc[findings["Finding"].eq("REAL-LINE COVERAGE")].iloc[0]
    assert hits["Status"] == "LEARNING"
    assert "No persisted real-line Top Play evidence" in hits["Conclusion"]
    assert overall["Status"] == "LEARNING"
    assert "1 observed real-line slate" in overall["Evidence"]
    assert coverage_row["Status"] == "LEARNING"
    assert findings["Production Authority"].eq("NONE").all()

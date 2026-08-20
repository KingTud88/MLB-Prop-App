from __future__ import annotations

from automation.runtime_performance_profile import (
    DIAGNOSTIC_AUTHORITY,
    PROFILE_VERSION,
    build_profile,
    canonical_features,
)


def test_canonical_profile_features_are_market_free_and_weather_neutral() -> None:
    features = canonical_features()
    assert features["weather_factor"] == 1.0
    assert features["weather_available"] == 0.0
    assert "sportsbook" not in " ".join(features).lower()
    assert "line" not in features


def test_profile_reports_existing_cpu_path_without_latency_gate() -> None:
    report = build_profile(draws=1_000, repeats=1, warmups=0, top_hotspots=5)

    assert report["profile_version"] == PROFILE_VERSION
    assert report["diagnostic_authority"] == DIAGNOSTIC_AUTHORITY == "NONE"
    assert report["draws"] == 1_000
    assert report["repeats"] == 1
    assert report["warmups"] == 0
    assert set(report["components"]) == {
        "simulation",
        "mathematical",
        "historical_calibration",
        "total_projection",
    }
    for component in report["components"].values():
        assert component["runs"] == 1
        for field in ("median_ms", "mean_ms", "p95_ms", "min_ms", "max_ms"):
            assert component[field] >= 0.0

    representative = report["representative_projection"]
    assert representative["ensemble_mean"] >= 0.0
    assert representative["simulation_mean"] >= 0.0
    assert representative["mathematical_mean"] >= 0.0
    assert 0.0 <= representative["data_quality"] <= 100.0

    hotspots = report["hotspots"]
    assert 1 <= len(hotspots) <= 5
    assert all(row["cumulative_ms"] >= 0.0 for row in hotspots)
    assert all(row["self_ms"] >= 0.0 for row in hotspots)

    rendered_notes = " ".join(report["notes"]).lower()
    assert "no production activation" in rendered_notes
    assert "no sportsbook" in rendered_notes
    assert "weather" in rendered_notes
    assert "runner-dependent" in rendered_notes
    assert "latency_threshold" not in report
    assert "pass" not in report
    assert "fail" not in report

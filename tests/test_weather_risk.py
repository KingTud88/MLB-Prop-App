from datetime import datetime, timezone

from engine.weather_risk import assess_delay_risk


def _hourly(prob=5, precip=0.0, code=0):
    return {
        "time":["2026-08-12T22:00","2026-08-12T23:00","2026-08-13T00:00","2026-08-13T01:00","2026-08-13T02:00","2026-08-13T03:00"],
        "precipitation_probability":[prob]*6,
        "precipitation":[precip]*6,
        "weather_code":[code]*6,
    }


def test_clear_weather_has_no_badge():
    result=assess_delay_risk(_hourly(),datetime(2026,8,13,0,0,tzinfo=timezone.utc))
    assert result.level == "NONE"
    assert result.icon == ""


def test_thunderstorm_is_high_delay_risk():
    result=assess_delay_risk(_hourly(prob=55,precip=1.0,code=95),datetime(2026,8,13,0,0,tzinfo=timezone.utc))
    assert result.level == "HIGH"
    assert result.icon == "⛈️"
    assert "thunderstorm" in result.summary


def test_moderate_rain_is_elevated_delay_risk():
    result=assess_delay_risk(_hourly(prob=45,precip=.8,code=61),datetime(2026,8,13,0,0,tzinfo=timezone.utc))
    assert result.level == "ELEVATED"
    assert result.icon == "🌩️"

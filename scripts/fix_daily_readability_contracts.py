from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor missing in {path}: {old}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "tests/test_daily_history_ui.py",
    'assert \'"starter_history_games": "Starts Used"\' in source',
    'assert \'"starter_history_games": "Starts"\' in source',
)
replace_once(
    "tests/test_daily_history_ui.py",
    'assert \'"starter_history_source": "History Source"\' in source',
    'assert \'"starter_history_source": "History"\' in source',
)
replace_once(
    "tests/test_daily_projection_highlight.py",
    'assert \'("Projection K", "Projection Hits Allowed", "Projection Outs")\' in source',
    'assert \'("Projection K", "Projection Hits", "Projection Outs")\' in source',
)
replace_once(
    "tests/test_weather_snapshot_ui.py",
    'assert \'"Weather Risk"\' in daily',
    'assert \'"weather_delay_risk": "Weather"\' in daily',
)

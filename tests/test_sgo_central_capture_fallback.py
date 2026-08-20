from __future__ import annotations

import json
import sys
from pathlib import Path

from automation import sportsgameodds_capture as capture


REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVER_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "daily-projection-resolver.yml"
SGO_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "sportsgameodds-capture.yml"


def test_status_covers_slate_only_for_exact_current_slate(tmp_path):
    status = tmp_path / "status.json"
    status.write_text(json.dumps({"slate_date": "2026-08-20"}), encoding="utf-8")

    assert capture.status_covers_slate("2026-08-20", status) is True
    assert capture.status_covers_slate("2026-08-21", status) is False


def test_status_covers_slate_fails_open_to_central_refresh_for_missing_or_bad_status(tmp_path):
    missing = tmp_path / "missing.json"
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")

    assert capture.status_covers_slate("2026-08-20", missing) is False
    assert capture.status_covers_slate("2026-08-20", malformed) is False


def test_skip_if_current_slate_exits_before_api_key_or_provider_access(tmp_path, monkeypatch, capsys):
    status = tmp_path / "status.json"
    status.write_text(json.dumps({"slate_date": "2026-08-20"}), encoding="utf-8")

    def forbidden_api_key_lookup():
        raise AssertionError("current-slate skip must happen before API-key/provider access")

    monkeypatch.setattr(capture, "resolve_api_key", forbidden_api_key_lookup)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sportsgameodds_capture",
            "--slate-date",
            "2026-08-20",
            "--status",
            str(status),
            "--skip-if-current-slate",
        ],
    )

    capture.main()

    assert "capture skipped" in capsys.readouterr().out.lower()


def test_daily_resolver_uses_one_central_skip_gated_fallback_and_stages_snapshot_outputs():
    source = RESOLVER_WORKFLOW.read_text(encoding="utf-8")

    projection_capture = "PYTHONPATH=. python automation/daily_projection_runner.py"
    central_fallback = "PYTHONPATH=. python -m automation.sportsgameodds_capture --skip-if-current-slate"
    assert projection_capture in source
    assert central_fallback in source
    assert source.index(central_fallback) > source.index(projection_capture)
    assert "SPORTSGAMEODDS_API_KEY: ${{ secrets.SPORTSGAMEODDS_API_KEY }}" in source

    for path in (
        "data/sportsgameodds_snapshot.csv",
        "data/sportsbook_line_history.csv",
        "data/sportsgameodds_status.json",
        "data/projection_log.csv",
    ):
        assert path in source


def test_primary_sgo_schedule_remains_four_bounded_central_windows():
    source = SGO_WORKFLOW.read_text(encoding="utf-8")
    expected = {
        '- cron: "5 14 * * *"',
        '- cron: "5 17 * * *"',
        '- cron: "5 20 * * *"',
        '- cron: "35 22 * * *"',
    }

    assert {line.strip() for line in source.splitlines() if "cron:" in line} == expected
    assert "PYTHONPATH=. python -m automation.sportsgameodds_capture" in source

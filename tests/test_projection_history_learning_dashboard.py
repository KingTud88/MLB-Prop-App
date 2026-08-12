from pathlib import Path


def _page_text() -> str:
    return Path("pages/4_Projection_History.py").read_text(encoding="utf-8")


def test_projection_history_page_compiles():
    text = _page_text()
    compile(text, "pages/4_Projection_History.py", "exec")


def test_projection_history_has_current_model_learning_dashboard():
    text = _page_text()
    assert "Current model learning status" in text
    assert "starter-only model rows" in text
    assert "5+ K calibration rows" in text
    assert "O5.5 Hits calibration rows" in text
    assert "O15.5 Outs calibration rows" in text
    assert "milestone_calibration_report" in text
    assert "hits_calibration_report" in text
    assert "outs_calibration_report" in text


def test_projection_history_has_rolling_accuracy_and_starts_used():
    text = _page_text()
    assert "ROLLING_WINDOW = 20" in text
    assert "Rolling MAE" in text
    assert "Rolling Range Hit Rate" in text
    assert '"starter_history_games"' in text
    assert 'NumberColumn("Starts Used"' in text


def test_projection_history_directional_wins_and_clean_archive():
    text = _page_text()
    assert "K Projection Wins & Crushers" in text
    assert "actual strikeouts > the frozen projected K mean" in text
    assert "Projection Crushers" in text
    assert "Directional K Result" in text
    assert "80% Range Result" in text
    assert "archive_populated" in text
    assert "Completely empty columns are hidden automatically" in text
    assert "#22c55e" in text
    assert "#facc15" in text

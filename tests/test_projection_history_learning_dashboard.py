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


def test_projection_history_bettable_wins_and_clean_archive():
    text = _page_text()
    assert "Bettable K Wins & Crushers" in text
    assert "highest whole-K ladder milestone fully supported" in text
    assert "5.07 projects to a 5+ target, so 5 actual Ks = ✅ WIN" in text
    assert "Projection Crushers" in text
    assert 'TextColumn("K Target"' in text
    assert 'TextColumn("K Result"' in text
    assert 'NumberColumn("Vs Target"' in text
    assert 'NumberColumn("Vs Projection"' in text
    assert 'TextColumn("80% K Range")' in text
    assert 'TextColumn("80% Hits Range")' in text
    assert 'TextColumn("80% Outs Range")' in text
    assert "K Target / K Result is the only WIN/MISS lane" in text
    assert "empty_token" in text
    assert '"none", "null", "nat", "<na>"' in text
    assert "#22c55e" in text
    assert "#38bdf8" in text
    assert "#facc15" in text


def test_projection_archive_groups_rows_into_clickable_dates():
    text = _page_text()
    assert 'with st.expander(f"📅 {date_label}' in text
    assert 'archive_view["_archive_date"]' in text
    assert 'date_group = date_group.drop(columns=["game_date", "_archive_date"]' in text
    assert "Click a date to open that slate" in text
    assert 'expanded=False' in text


def test_projection_history_shows_report_only_workload_v2_candidate():
    text = _page_text()
    assert "workload-v2-bias-candidate" in text
    assert "REPORT ONLY / NOT LIVE" in text
    assert '"Candidate_MAE": "v2 MAE"' in text
    assert '"Relative_MAE_vs_Workload": "v2 MAE Improvement vs v1"' in text
    assert '"Candidate_Win_Share_vs_Workload": "v2 Win Share vs v1"' in text
    assert '"Candidate_Status": "v2 Status"' in text
    assert "v2 adjusted target-starts" in text
    assert "cannot change Ks, Hits, Outs, or Top Plays" in text

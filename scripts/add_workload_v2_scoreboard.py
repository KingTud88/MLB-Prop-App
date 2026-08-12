from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


page = Path("pages/4_Projection_History.py")
text = page.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''st.caption(
    "Leakage-safe MLB replay over pitchers already tracked by the app. Each 2026 target start is rebuilt from only earlier starter games, with 2025 allowed as prior-season carry. "
    "workload-v1 is compared against rolling-5 and season-to-date workload baselines. Sportsbook data is excluded, and this report does not modify live projections."
)
''',
    '''st.caption(
    "Leakage-safe MLB replay over pitchers already tracked by the app. Each 2026 target start is rebuilt from only earlier starter games, with 2025 allowed as prior-season carry. "
    "workload-v1 is compared against rolling-5 and season-to-date baselines, while workload-v2-bias-candidate learns a tightly capped correction from strictly earlier workload-v1 errors. "
    "Sportsbook data is excluded, and this report does not modify live projections. workload-v2 is REPORT ONLY / NOT LIVE and cannot change Ks, Hits, Outs, or Top Plays."
)
''',
    "historical workload caption",
)

old_metrics = '''        _v1, _v2, _v3, _v4 = st.columns(4)
        _v1.metric("Validated workload targets", int(_n.fillna(0).sum()))
        _v2.metric("HELPING metrics", int(_status.eq("HELPING").sum()))
        _v3.metric("MIXED metrics", int(_status.eq("MIXED").sum()))
        _v4.metric("HURTING metrics", int(_status.eq("HURTING").sum()))

        _view = _validation.rename(columns={
'''
new_metrics = '''        _v1, _v2, _v3, _v4 = st.columns(4)
        _v1.metric("Validated workload targets", int(_n.fillna(0).sum()))
        _v2.metric("workload-v1 HELPING", int(_status.eq("HELPING").sum()))
        _v3.metric("workload-v1 MIXED", int(_status.eq("MIXED").sum()))
        _v4.metric("workload-v1 HURTING", int(_status.eq("HURTING").sum()))

        if "Candidate_Status" in _validation.columns:
            _candidate_status = _validation["Candidate_Status"].astype(str)
            _adjusted = pd.to_numeric(_validation.get("Candidate_Adjusted_Starts"), errors="coerce")
            _c1, _c2, _c3, _c4 = st.columns(4)
            _c1.metric("v2 adjusted target-starts", int(_adjusted.fillna(0).sum()))
            _c2.metric("v2 HELPING metrics", int(_candidate_status.eq("HELPING").sum()))
            _c3.metric("v2 MIXED metrics", int(_candidate_status.eq("MIXED").sum()))
            _c4.metric("v2 HURTING metrics", int(_candidate_status.eq("HURTING").sum()))

        _view = _validation.rename(columns={
'''
text = replace_once(text, old_metrics, new_metrics, "candidate metric cards")

text = replace_once(
    text,
    '''            "Workload_Win_Share_vs_Rolling5": "Win Share vs Rolling-5",
        }).copy()
        for col in ["MAE Improvement vs Rolling-5", "MAE Improvement vs Season-to-date", "Win Share vs Rolling-5"]:
''',
    '''            "Workload_Win_Share_vs_Rolling5": "Win Share vs Rolling-5",
            "Candidate_Adjusted_Starts": "v2 Adjusted Starts",
            "Candidate_MAE": "v2 MAE",
            "Candidate_RMSE": "v2 RMSE",
            "Candidate_Bias": "v2 Bias",
            "Relative_MAE_vs_Workload": "v2 MAE Improvement vs v1",
            "Candidate_Win_Share_vs_Workload": "v2 Win Share vs v1",
            "Candidate_Status": "v2 Status",
        }).copy()
        for col in ["MAE Improvement vs Rolling-5", "MAE Improvement vs Season-to-date", "Win Share vs Rolling-5", "v2 MAE Improvement vs v1", "v2 Win Share vs v1"]:
''',
    "candidate summary rename",
)

text = replace_once(
    text,
    '''                _view[col] = _view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if "Improvement" in col else f"{float(x):.1%}")
        for col in ["Workload MAE", "Workload RMSE", "Workload Bias", "Rolling-5 MAE", "Rolling-5 RMSE", "Rolling-5 Bias", "Season-to-date MAE"]:
''',
    '''                _view[col] = _view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if "Improvement" in col else f"{float(x):.1%}")
        for col in ["Workload MAE", "Workload RMSE", "Workload Bias", "Rolling-5 MAE", "Rolling-5 RMSE", "Rolling-5 Bias", "Season-to-date MAE", "v2 MAE", "v2 RMSE", "v2 Bias"]:
''',
    "candidate numeric formatting",
)

text = replace_once(
    text,
    '''        st.caption(
            "Status stays LEARNING below 30 evaluated starts. HELPING requires at least 3% lower MAE than rolling-5 and workload-v1 to beat rolling-5 on at least 52% of individual starts. "
            "HURTING uses the symmetric downside guardrail. No status changes the live forecast automatically."
        )
''',
    '''        st.caption(
            "Status stays LEARNING below 30 evaluated starts. workload-v1 HELPING requires at least 3% lower MAE than rolling-5 and a 52%+ individual-start win share. "
            "The v2 candidate is judged separately against workload-v1: it must lower MAE, reduce absolute bias, and win enough actually-adjusted starts. "
            "Candidate status is evidence only; workload-v2 remains REPORT ONLY / NOT LIVE until promotion is explicitly earned and implemented."
        )
''',
    "candidate status caption",
)

text = replace_once(
    text,
    '''                    for col in ["Relative MAE vs Rolling5", "Win Share vs Rolling5"]:
''',
    '''                    for col in ["Relative MAE vs Rolling5", "Win Share vs Rolling5", "Candidate MAE Improvement vs Workload", "Candidate Win Share vs Workload"]:
''',
    "segment percentage formatting",
)

text = replace_once(
    text,
    '''                    for col in ["Workload MAE", "Rolling5 MAE"]:
''',
    '''                    for col in ["Workload MAE", "Candidate MAE", "Rolling5 MAE"]:
''',
    "segment numeric formatting",
)

text = replace_once(
    text,
    '''                    st.caption("Segments only appear with at least 15 evaluated starts. They are diagnostic slices, not automatic adjustment rules.")
''',
    '''                    st.caption("Segments only appear with at least 15 evaluated starts. They are diagnostic slices, not automatic adjustment rules. Any v2 segment gains or losses remain report-only evidence.")
''',
    "segment caption",
)

page.write_text(text, encoding="utf-8")

contract = Path("tests/test_projection_history_learning_dashboard.py")
test = contract.read_text(encoding="utf-8")
addition = '''\n\ndef test_projection_history_shows_report_only_workload_v2_candidate():\n    text = _page_text()\n    assert "workload-v2-bias-candidate" in text\n    assert "REPORT ONLY / NOT LIVE" in text\n    assert '"Candidate_MAE": "v2 MAE"' in text\n    assert '"Relative_MAE_vs_Workload": "v2 MAE Improvement vs v1"' in text\n    assert '"Candidate_Win_Share_vs_Workload": "v2 Win Share vs v1"' in text\n    assert '"Candidate_Status": "v2 Status"' in text\n    assert "v2 adjusted target-starts" in text\n    assert "cannot change Ks, Hits, Outs, or Top Plays" in text\n'''
if "test_projection_history_shows_report_only_workload_v2_candidate" not in test:
    test += addition
contract.write_text(test, encoding="utf-8")

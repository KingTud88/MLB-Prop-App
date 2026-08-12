from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


page = Path("pages/4_Projection_History.py")
text = page.read_text(encoding="utf-8")
anchor = 'st.divider()\nst.subheader("🧾 Lineup input audit")\n'
section = '''st.markdown("#### 🧪 Historical workload validation")
st.caption(
    "Leakage-safe MLB replay over pitchers already tracked by the app. Each 2026 target start is rebuilt from only earlier starter games, with 2025 allowed as prior-season carry. "
    "workload-v1 is compared against rolling-5 and season-to-date workload baselines. Sportsbook data is excluded, and this report does not modify live projections."
)
_workload_summary_path = ROOT / "data" / "workload_backtest_summary.csv"
_workload_segments_path = ROOT / "data" / "workload_backtest_segments.csv"
if not _workload_summary_path.exists():
    st.info("Historical workload validation has not been generated yet. Run the Historical Workload Validation workflow to create the report.")
else:
    try:
        _validation = pd.read_csv(_workload_summary_path)
    except Exception:
        _validation = pd.DataFrame()
    if _validation.empty:
        st.info("Historical workload validation report is currently empty.")
    else:
        _status = _validation.get("Status", pd.Series(index=_validation.index, dtype=str)).astype(str)
        _n = pd.to_numeric(_validation.get("Evaluated_Starts"), errors="coerce")
        _v1, _v2, _v3, _v4 = st.columns(4)
        _v1.metric("Validated workload targets", int(_n.fillna(0).sum()))
        _v2.metric("HELPING metrics", int(_status.eq("HELPING").sum()))
        _v3.metric("MIXED metrics", int(_status.eq("MIXED").sum()))
        _v4.metric("HURTING metrics", int(_status.eq("HURTING").sum()))

        _view = _validation.rename(columns={
            "Evaluated_Starts": "Evaluated Starts",
            "Workload_MAE": "Workload MAE",
            "Workload_RMSE": "Workload RMSE",
            "Workload_Bias": "Workload Bias",
            "Rolling5_MAE": "Rolling-5 MAE",
            "Rolling5_RMSE": "Rolling-5 RMSE",
            "Rolling5_Bias": "Rolling-5 Bias",
            "SeasonToDate_Starts": "Season-to-date Starts",
            "SeasonToDate_MAE": "Season-to-date MAE",
            "Relative_MAE_vs_Rolling5": "MAE Improvement vs Rolling-5",
            "Relative_MAE_vs_SeasonToDate": "MAE Improvement vs Season-to-date",
            "Workload_Win_Share_vs_Rolling5": "Win Share vs Rolling-5",
        }).copy()
        for col in ["MAE Improvement vs Rolling-5", "MAE Improvement vs Season-to-date", "Win Share vs Rolling-5"]:
            if col in _view.columns:
                _view[col] = _view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if "Improvement" in col else f"{float(x):.1%}")
        for col in ["Workload MAE", "Workload RMSE", "Workload Bias", "Rolling-5 MAE", "Rolling-5 RMSE", "Rolling-5 Bias", "Season-to-date MAE"]:
            if col in _view.columns:
                _view[col] = _view[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.3f}" if "Bias" in col else f"{float(x):.3f}")
        st.dataframe(_view, hide_index=True, width="stretch")
        st.caption(
            "Status stays LEARNING below 30 evaluated starts. HELPING requires at least 3% lower MAE than rolling-5 and workload-v1 to beat rolling-5 on at least 52% of individual starts. "
            "HURTING uses the symmetric downside guardrail. No status changes the live forecast automatically."
        )

        if _workload_segments_path.exists():
            try:
                _segments = pd.read_csv(_workload_segments_path)
            except Exception:
                _segments = pd.DataFrame()
            if not _segments.empty:
                with st.expander("Historical workload segments — descriptive", expanded=False):
                    _seg = _segments.copy()
                    for col in ["Relative MAE vs Rolling5", "Win Share vs Rolling5"]:
                        if col in _seg.columns:
                            _seg[col] = _seg[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1%}" if "Relative" in col else f"{float(x):.1%}")
                    for col in ["Workload MAE", "Rolling5 MAE"]:
                        if col in _seg.columns:
                            _seg[col] = _seg[col].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f}")
                    st.dataframe(_seg, hide_index=True, width="stretch")
                    st.caption("Segments only appear with at least 15 evaluated starts. They are diagnostic slices, not automatic adjustment rules.")

st.divider()
st.subheader("🧾 Lineup input audit")
'''
text = replace_once(text, anchor, section, "lineup audit")
page.write_text(text, encoding="utf-8")

contract = Path("tests/test_workload_ui_contract.py")
test = contract.read_text(encoding="utf-8")
addition = '''\n\ndef test_history_surfaces_historical_workload_backtest():\n    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")\n    assert "Historical workload validation" in source\n    assert "workload_backtest_summary.csv" in source\n    assert "MAE Improvement vs Rolling-5" in source\n    assert "Status stays LEARNING below 30 evaluated starts" in source\n    assert "does not modify live projections" in source\n'''
if "test_history_surfaces_historical_workload_backtest" not in test:
    test += addition
contract.write_text(test, encoding="utf-8")

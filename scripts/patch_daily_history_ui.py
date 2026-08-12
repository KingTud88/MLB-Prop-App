from pathlib import Path

PAGE = Path("pages/5_Daily_Projection_Run.py")
TEST = Path("tests/test_daily_history_ui.py")
text = PAGE.read_text(encoding="utf-8")

replacements = [
    (
        'def run_full_slate(day: str) -> tuple[pd.DataFrame, int, int, list[str]]:\n',
        'def run_full_slate(day: str) -> tuple[pd.DataFrame, int, int, list[str], list[str]]:\n',
    ),
    (
        '    errors: list[str] = []\n',
        '    history_only: list[str] = []\n    errors: list[str] = []\n',
    ),
    (
        '        if result is None:\n            errors.append(f"{row.get(\'player\', \'Unknown\')}: no usable pitcher history")\n            continue\n',
        '        if result is None:\n            history_only.append(\n                f"{row.get(\'player\', \'Unknown\')}: no usable starter history — final K / hits / outs / BF / pitches will be tracked"\n            )\n            continue\n',
    ),
    (
        '    return slate, len(new_rows), skipped + refreshed, errors\n',
        '    return slate, len(new_rows), skipped + refreshed, history_only, errors\n',
    ),
    (
        '            slate, added, skipped, errors = run_full_slate(slate_date.isoformat())\n',
        '            slate, added, skipped, history_only, errors = run_full_slate(slate_date.isoformat())\n',
    ),
    (
        '            added = skipped = 0\n            errors = [f"Slate run failed: {type(exc).__name__}: {exc}"]\n',
        '            added = skipped = 0\n            history_only = []\n            errors = [f"Slate run failed: {type(exc).__name__}: {exc}"]\n',
    ),
    (
        '    st.session_state["daily_skipped"] = skipped\n    st.session_state["daily_errors"] = errors\n',
        '    st.session_state["daily_skipped"] = skipped\n    st.session_state["daily_history_only"] = history_only\n    st.session_state["daily_errors"] = errors\n',
    ),
    (
        '    errors = list(st.session_state.get("daily_errors", []))\n    c1, c2, c3, c4 = st.columns(4)\n    c1.metric("Slate pitchers", len(slate))\n    c2.metric("New snapshots", added)\n    c3.metric("Already captured/refreshed", skipped)\n    c4.metric("Errors", len(errors))\n',
        '    history_only = list(st.session_state.get("daily_history_only", []))\n    errors = list(st.session_state.get("daily_errors", []))\n    c1, c2, c3, c4, c5 = st.columns(5)\n    c1.metric("Projected starters", len(slate))\n    c2.metric("New snapshots", added)\n    c3.metric("Already captured/refreshed", skipped)\n    c4.metric("History-only tracked", len(history_only))\n    c5.metric("Errors", len(errors))\n',
    ),
    (
        '    if errors:\n        st.warning("Some announced starters could not be captured:")\n        for error in errors:\n            st.write(f"- {error}")\n',
        '    if history_only:\n        st.info("📚 History-only starters being tracked")\n        st.caption(\n            "These starters were not projected because there was not enough legitimate starter history. "\n            "Their final strikeouts, hits allowed, outs, batters faced, and pitches will still be saved so future starts can use the new data."\n        )\n        for pitcher in history_only:\n            st.write(f"- {pitcher}")\n\n    if errors:\n        st.warning("Some announced starters hit real capture errors:")\n        for error in errors:\n            st.write(f"- {error}")\n',
    ),
]

for old, new in replacements:
    if old not in text:
        raise SystemExit(f"anchor not found:\n{old}")
    text = text.replace(old, new, 1)

PAGE.write_text(text, encoding="utf-8")
TEST.write_text(
    '''from pathlib import Path\n\n\ndef test_daily_page_separates_history_only_from_errors():\n    text = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert "daily_history_only" in text\n    assert "History-only tracked" in text\n    assert "📚 History-only starters being tracked" in text\n    assert "Some announced starters hit real capture errors:" in text\n    assert "no usable starter history — final K / hits / outs / BF / pitches will be tracked" in text\n    assert 'c5.metric("Errors", len(errors))' in text\n\n\ndef test_daily_page_compiles():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    compile(source, "pages/5_Daily_Projection_Run.py", "exec")\n''',
    encoding="utf-8",
)

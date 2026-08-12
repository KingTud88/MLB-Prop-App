from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''def _num(row: pd.Series, key: str) -> float | None:\n    value = pd.to_numeric(pd.Series([row.get(key)]), errors="coerce").iloc[0]\n    return None if pd.isna(value) else float(value)\n\n\n''',
    '''def _num(row: pd.Series, key: str) -> float | None:\n    value = pd.to_numeric(pd.Series([row.get(key)]), errors="coerce").iloc[0]\n    return None if pd.isna(value) else float(value)\n\n\ndef _range_text(low: object, high: object) -> str:\n    """Render a central outcome interval as one compact human-readable value."""\n    lo = pd.to_numeric(pd.Series([low]), errors="coerce").iloc[0]\n    hi = pd.to_numeric(pd.Series([high]), errors="coerce").iloc[0]\n    if pd.isna(lo) or pd.isna(hi):\n        return "—"\n\n    def _endpoint(value: float) -> str:\n        value = float(value)\n        rounded = round(value)\n        return str(int(rounded)) if abs(value - rounded) < 1e-9 else f"{value:.1f}"\n\n    return f"{_endpoint(float(lo))}–{_endpoint(float(hi))}"\n\n\n''',
    "range helper",
)

text = replace_once(
    text,
    '''        if "weather_icon" in display.columns:\n            display["player"] = display.apply(lambda r: f"{r.get('player', 'Unknown')} {str(r.get('weather_icon', '') or '')}".strip(), axis=1)\n            display = display.drop(columns=["weather_icon"])\n        display = display.rename(\n''',
    '''        if "weather_icon" in display.columns:\n            display["player"] = display.apply(lambda r: f"{r.get('player', 'Unknown')} {str(r.get('weather_icon', '') or '')}".strip(), axis=1)\n            display = display.drop(columns=["weather_icon"])\n\n        # Low/high columns are endpoints of ONE central 80% interval. Collapse\n        # them into a single value so nobody reads either endpoint as an 80%\n        # milestone probability. Keep the new range exactly where the old pair\n        # lived so each market scans projection -> range -> SIM -> MATH.\n        for low_col, high_col, label in (\n            ("k_range_low", "k_range_high", "80% K Range"),\n            ("hits_range_low", "hits_range_high", "80% Hits Range"),\n            ("outs_range_low", "outs_range_high", "80% Outs Range"),\n        ):\n            if low_col in display.columns and high_col in display.columns:\n                insert_at = display.columns.get_loc(low_col)\n                values = [\n                    _range_text(low, high)\n                    for low, high in zip(display[low_col], display[high_col])\n                ]\n                display.insert(insert_at, label, values)\n                display = display.drop(columns=[low_col, high_col])\n\n        display = display.rename(\n''',
    "collapse ranges",
)

text = replace_once(
    text,
    '''                "starter_history_games": "Starts Used",\n                "starter_history_source": "History Source",\n''',
    '''                "starter_history_games": "Starts",\n                "starter_history_source": "History",\n''',
    "short history headers",
)
text = replace_once(
    text,
    '''                "days_since_last_start": "Days Since Start",\n''',
    '''                "days_since_last_start": "Rest Days",\n''',
    "short rest header",
)
text = replace_once(
    text,
    '''                "team_leash_tto_reach_rate": "TTO Reach Rate",\n                "team_leash_90_pitch_rate": "90+ Pitch Rate",\n                "team_leash_pitch_multiplier_candidate": "Pitch Adj Candidate",\n''',
    '''                "team_leash_tto_reach_rate": "TTO %",\n                "team_leash_90_pitch_rate": "90+ %",\n                "team_leash_pitch_multiplier_candidate": "Pitch Adj",\n''',
    "short team leash headers",
)
text = replace_once(
    text,
    '''                "weather_delay_risk": "Weather Risk",\n''',
    '''                "weather_delay_risk": "Weather",\n''',
    "short weather header",
)
text = replace_once(
    text,
    '''                "lineup_source": "Lineup Source",\n                "lineup_batters": "Lineup Hitters",\n                "lineup_projection_delta": "K Δ from Lineup",\n''',
    '''                "lineup_source": "Lineup",\n                "lineup_batters": "Hitters",\n                "lineup_projection_delta": "Lineup K Δ",\n''',
    "short lineup headers",
)
text = replace_once(
    text,
    '''                "k_range_low": "K 80% Low",\n                "k_range_high": "K 80% High",\n                "hits_projection": "Projection Hits Allowed",\n                "hits_range_low": "Hits 80% Low",\n                "hits_range_high": "Hits 80% High",\n                "outs_projection": "Projection Outs",\n                "outs_range_low": "Outs 80% Low",\n                "outs_range_high": "Outs 80% High",\n''',
    '''                "hits_projection": "Projection Hits",\n                "outs_projection": "Projection Outs",\n''',
    "remove split range renames",
)
text = replace_once(
    text,
    '''                "data_quality": "Data Quality",\n''',
    '''                "data_quality": "Quality",\n''',
    "short quality header",
)

text = replace_once(
    text,
    '''        projection_highlight_cols = [\n            col for col in ("Projection K", "Projection Hits Allowed", "Projection Outs")\n            if col in display.columns\n        ]\n        styled_display = display.style\n        if projection_highlight_cols:\n            styled_display = styled_display.map(\n                lambda value: "color: #22c55e; font-weight: 700;" if pd.notna(value) else "",\n                subset=projection_highlight_cols,\n            )\n\n        st.subheader(f"{slate_date:%B %d, %Y} starter slate")\n        st.caption("Click any pitcher row to inspect why the model produced that frozen projection. Headline projection numbers are highlighted in green for faster scanning.")\n''',
    '''        projection_highlight_cols = [\n            col for col in ("Projection K", "Projection Hits", "Projection Outs")\n            if col in display.columns\n        ]\n        probability_cols = [\n            col for col in (\n                "SIM 5+ K", "MATH 5+ K", "SIM O5.5 Hits", "MATH O5.5 Hits",\n                "SIM O15.5 Outs", "MATH O15.5 Outs",\n            )\n            if col in display.columns\n        ]\n        formatters: dict[str, str] = {}\n        for col in projection_highlight_cols:\n            formatters[col] = "{:.2f}"\n        for col in probability_cols:\n            formatters[col] = "{:.1%}"\n        for col in ("Exp Pitches", "Exp BF", "Exp Outs", "Team Avg Pitches"):\n            if col in display.columns:\n                formatters[col] = "{:.1f}"\n        for col in ("Pitches/BF",):\n            if col in display.columns:\n                formatters[col] = "{:.2f}"\n        for col in ("Quality", "Starts", "MLB Starts", "Observed Starts", "Rest Days", "Team Starts"):\n            if col in display.columns:\n                formatters[col] = "{:.0f}"\n        if "Opp K%" in display.columns:\n            formatters["Opp K%"] = "{:.1f}%"\n        if "Rain %" in display.columns:\n            formatters["Rain %"] = "{:.0f}%"\n        if "Lineup K Δ" in display.columns:\n            formatters["Lineup K Δ"] = "{:+.2f}"\n        for col in ("Pitch Trend", "TTO %", "90+ %"):\n            if col in display.columns:\n                formatters[col] = "{:.1%}"\n        if "Pitch Adj" in display.columns:\n            formatters["Pitch Adj"] = "{:.3f}"\n        for col in ("Actual K", "Actual Hits Allowed", "Actual Outs"):\n            if col in display.columns:\n                formatters[col] = "{:.0f}"\n\n        styled_display = display.style.format(formatters, na_rep="—")\n        if projection_highlight_cols:\n            styled_display = styled_display.map(\n                lambda value: "color: #22c55e; font-weight: 700;" if pd.notna(value) else "",\n                subset=projection_highlight_cols,\n            )\n\n        st.subheader(f"{slate_date:%B %d, %Y} starter slate")\n        st.caption(\n            "How to read: Projection = expected average outcome · 80% Range = one central simulated interval (10th–90th percentile), not an 80% chance at each endpoint · "\n            "SIM/MATH = the probability from each independent model path. Click a pitcher row for the full breakdown. Headline projections are green."\n        )\n''',
    "human readable formatting",
)

path.write_text(text, encoding="utf-8")


test_path = Path("tests/test_daily_readability.py")
test_path.write_text(
    '''from pathlib import Path\n\n\ndef test_daily_table_collapses_ranges_and_formats_probabilities_for_humans():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert '("k_range_low", "k_range_high", "80% K Range")' in source\n    assert '("hits_range_low", "hits_range_high", "80% Hits Range")' in source\n    assert '("outs_range_low", "outs_range_high", "80% Outs Range")' in source\n    assert 'formatters[col] = "{:.1%}"' in source\n    assert 'formatters[col] = "{:.2f}"' in source\n    assert '80% Range = one central simulated interval' in source\n    assert 'not an 80% chance at each endpoint' in source\n    assert '"k_range_low": "K 80% Low"' not in source\n    assert '"k_range_high": "K 80% High"' not in source\n\n\ndef test_daily_range_text_is_one_interval_not_two_probabilities():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert 'def _range_text(low: object, high: object) -> str:' in source\n    assert 'return f"{_endpoint(float(lo))}–{_endpoint(float(hi))}"' in source\n\ndef test_projection_highlight_survives_readability_rename():\n    source = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")\n    assert '("Projection K", "Projection Hits", "Projection Outs")' in source\n    assert 'color: #22c55e; font-weight: 700;' in source\n''',
    encoding="utf-8",
)

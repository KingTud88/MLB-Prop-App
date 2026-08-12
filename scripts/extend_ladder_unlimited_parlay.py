from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


# Projection page: extend K model/ladder/calibration display through 12+.
path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'lines=tuple(float(x) for x in range(3,11))',
    'lines=tuple(float(x) for x in range(3,13))',
    "projection engine K lines",
)
text = replace_once(
    text,
    'report=milestone_calibration_report(history,range(3,11),min_observations=30)',
    'report=milestone_calibration_report(history,range(3,13),min_observations=30)',
    "calibration dashboard K lines",
)
text = replace_once(text, 'kdf=ladder(proj,10)', 'kdf=ladder(proj,12)', "ladder max")
text = text.replace("3+ through 10+", "3+ through 12+")

# Projection parlay: remove hard leg cap. The ticket remains one parlay record
# regardless of leg count, with no fabricated combined probability/odds.
text = replace_once(
    text,
    '''    if len(legs)>=5:\n        return False,"The Projection Parlay Builder is capped at five legs."\n''',
    '',
    "remove five-leg cap",
)
text = replace_once(
    text,
    'with st.expander(f"🎟️ Projection Parlay Builder · {len(legs)}/5 legs",expanded=bool(legs)):',
    'with st.expander(f"🎟️ Projection Parlay Builder · {len(legs)} leg" + ("" if len(legs)==1 else "s"),expanded=bool(legs)):',
    "builder count label",
)
text = replace_once(
    text,
    '''        duplicate_pitchers=pd.Series([str(leg.get("player","")) for leg in legs]).value_counts()\n''',
    '''        if len(legs)>=10:\n            st.warning(f"🎰 {len(legs)}-leg lotto · very high variance. The app grades every leg but does not multiply model probabilities or claim the legs are independent.")\n        duplicate_pitchers=pd.Series([str(leg.get("player","")) for leg in legs]).value_counts()\n''',
    "large parlay variance warning",
)
path.write_text(text, encoding="utf-8")


# Daily capture: freeze 11+ and 12+ SIM/MATH paths so those ladder milestones
# can accumulate compatible resolved evidence for calibration.
path = Path("automation/daily_projection_runner.py")
text = path.read_text(encoding="utf-8")
old_count = text.count("range(3, 11)")
if old_count < 3:
    raise SystemExit(f"expected at least 3 daily K-range anchors, found {old_count}")
text = text.replace("range(3, 11)", "range(3, 13)")
path.write_text(text, encoding="utf-8")


# Regression contracts.
path = Path("tests/test_bet_add_buttons_contract.py")
text = path.read_text(encoding="utf-8")
anchor = '''    assert ladder_pos < builder_pos\n\n\n'''
replacement = '''    assert ladder_pos < builder_pos\n    assert "kdf=ladder(proj,12)" in source\n    assert "3+ through 12+" in source\n\n\ndef test_projection_parlay_builder_has_no_hard_leg_cap():\n    source = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text(encoding="utf-8")\n    assert "capped at five legs" not in source\n    assert "if len(legs)>=5" not in source\n    assert "very high variance" in source\n    assert "does not multiply model probabilities" in source\n\n\n'''
text = replace_once(text, anchor, replacement, "projection action contracts")
path.write_text(text, encoding="utf-8")

path = Path("tests/test_bet_tracker.py")
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_model_parlay_supports_eighteen_unpriced_legs():\n    legs = [\n        {\n            "player": f"Pitcher {idx}",\n            "market": "Strikeouts",\n            "game_date": "2026-08-12",\n            "line": 4.5 + (idx % 4),\n            "side": "Over",\n            "american_odds": None,\n            "game_pk": 1000 + idx,\n            "pitcher_id": 2000 + idx,\n        }\n        for idx in range(18)\n    ]\n    record = make_parlay_record(legs=legs, stake=0.25, game_date="2026-08-12", source="Projection Page Model Parlay")\n    assert record["bet_type"] == "Parlay"\n    assert record["player"] == "18-leg parlay"\n    parsed = parse_parlay_legs(record["parlay_legs"])\n    assert len(parsed) == 18\n    assert all(leg["american_odds"] == "" for leg in parsed)\n'''
path.write_text(text, encoding="utf-8")

path = Path("tests/test_extended_strikeout_ladder.py")
path.write_text('''from pathlib import Path\n\n\ndef test_projection_and_daily_capture_support_11_and_12_plus():\n    root = Path(__file__).resolve().parents[1]\n    app = (root / "streamlit_app.py").read_text(encoding="utf-8")\n    daily = (root / "automation" / "daily_projection_runner.py").read_text(encoding="utf-8")\n    assert "range(3,13)" in app\n    assert "kdf=ladder(proj,12)" in app\n    assert "range(3, 13)" in daily\n    assert 'out[f"sim_{line}p"]' in daily\n    assert 'out[f"math_{line}p"]' in daily\n    assert 'row.get(f"sim_{line}p")' in daily\n    assert 'row.get(f"math_{line}p")' in daily\n''', encoding="utf-8")

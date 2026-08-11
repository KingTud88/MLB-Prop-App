from pathlib import Path

# --- Top Plays: parlay builder uses model Top 5 only; sportsbook data is optional bookkeeping. ---
top_path = Path("pages/6_Top_Plays.py")
top = top_path.read_text(encoding="utf-8")
top = top.replace("    combined_parlay_odds,\n", "", 1)
start = top.index('st.markdown("---")\nst.subheader("🎟️ Parlay Builder")')
end = top.index('selected_rank = st.session_state.get("top_play_detail_rank")', start)
new_block = '''st.markdown("---")
st.subheader("🎟️ Parlay Builder")
st.caption(
    "Build a parlay directly from our model Top 5. Sportsbook data does not decide which legs can be combined. "
    "Select any 2–5 model legs and use one stake for the entire ticket. Book name and final quoted odds are optional bookkeeping only."
)

option_map = {}
for idx, leg in plays.iterrows():
    label = (
        f"#{int(leg['Rank'])} {leg['Pitcher']} · {leg['Market']} · {leg['Side']} {float(leg['Line']):g} · "
        f"{float(leg['Model Probability']):.1%} · {leg['Status']}"
    )
    option_map[label] = idx

selected_labels = st.multiselect(
    "Parlay legs (2–5)",
    list(option_map),
    default=list(option_map),
    max_selections=5,
    key="top_plays_parlay_legs",
    help="These choices come only from our model Top 5. No sportsbook availability filter is applied.",
)
selected = plays.iloc[[option_map[label] for label in selected_labels]].copy() if selected_labels else plays.iloc[0:0].copy()
parlay_stake = st.number_input("Parlay stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_parlay_stake")

book_note = st.text_input(
    "Sportsbook used (optional)",
    value="",
    key="top_plays_parlay_book_note",
    help="Optional recordkeeping only. This field never changes the model parlay or its ranking.",
)
quoted_odds_text = st.text_input(
    "Actual parlay American odds (optional)",
    value="",
    placeholder="Example: +450",
    key="top_plays_parlay_odds_text",
    help="Leave blank if you only want to track whether the model parlay hits. Add the actual quoted ticket price if you want P/L and ROI calculated.",
)

if len(selected) >= 2:
    watch_count = int((selected["Status"].astype(str) == "WATCH").sum())
    if watch_count:
        st.warning(f"This parlay includes {watch_count} WATCH leg(s). They are in our Top 5 but fall below the straight-bet model/data-quality action threshold.")
    if st.button(f"🎟️ Add {len(selected)}-leg model parlay to Bet Tracker", type="primary", use_container_width=True, key="save_top_plays_parlay"):
        raw_odds = quoted_odds_text.strip().replace(" ", "")
        quoted_odds = None
        odds_error = None
        if raw_odds:
            try:
                quoted_odds = int(round(float(raw_odds)))
                if quoted_odds == 0:
                    raise ValueError("American odds cannot be zero")
            except (TypeError, ValueError):
                odds_error = "Enter valid American odds such as +450 or -110, or leave the field blank."
        if odds_error:
            st.error(odds_error)
        else:
            legs = []
            for _, leg in selected.iterrows():
                game_pk = numeric(leg.get("Game PK")); pitcher_id = numeric(leg.get("Pitcher ID"))
                legs.append({
                    "player": str(leg["Pitcher"]), "market": str(leg["Market"]),
                    "game_date": str(leg.get("Game Date", today))[:10],
                    "line": float(leg["Line"]), "side": str(leg["Side"]), "american_odds": None,
                    "game_pk": None if game_pk is None else int(game_pk),
                    "pitcher_id": None if pitcher_id is None else int(pitcher_id),
                    "projection": numeric(leg.get("Projection")),
                    "model_probability": float(leg.get("Model Probability")),
                    "data_quality": int(leg.get("Data Quality", 0)),
                    "app_version": str(leg.get("App Version", "")),
                    "probability_semantics": str(leg.get("Probability Semantics", "")),
                    "snapshot_captured_at_utc": str(leg.get("Captured At UTC", "")),
                    "status": str(leg.get("Status", "")),
                })
            try:
                record = make_parlay_record(
                    legs=legs,
                    stake=float(parlay_stake),
                    book=book_note.strip(),
                    american_odds=quoted_odds,
                    game_date=today,
                    source="Top Plays Model Parlay",
                )
                append_bet(BET_LOG, record, st.secrets)
                suffix = "" if quoted_odds is not None else " (hit-rate tracking only; no ticket odds saved)"
                st.success(f"Saved {len(legs)}-leg model parlay to Bet Tracker{suffix}")
            except Exception as exc:
                st.error(f"Could not save parlay: {exc}")
else:
    st.info("Select at least two of our Top 5 model legs to build a parlay.")

'''
top = top[:start] + new_block + top[end:]
top_path.write_text(top, encoding="utf-8")

# --- Bet record: allow unpriced/model-only parlays. ---
bet_path = Path("engine/bet_tracker.py")
bet = bet_path.read_text(encoding="utf-8")
old_sig = '''def make_parlay_record(
    *,
    legs: Sequence[Mapping[str, object]],
    stake: float,
    book: str,
    american_odds: int | float,
    game_date: str,
    entered_at_utc: str | None = None,
    source: str = "",
) -> dict[str, object]:'''
new_sig = '''def make_parlay_record(
    *,
    legs: Sequence[Mapping[str, object]],
    stake: float,
    game_date: str,
    book: str = "",
    american_odds: int | float | None = None,
    entered_at_utc: str | None = None,
    source: str = "",
) -> dict[str, object]:'''
if old_sig not in bet:
    raise SystemExit("make_parlay_record signature anchor not found")
bet = bet.replace(old_sig, new_sig, 1)
old_leg_odds = '''            "american_odds": int(round(float(leg.get("american_odds")))),'''
new_leg_odds = '''            "american_odds": "" if leg.get("american_odds") in {None, ""} else int(round(float(leg.get("american_odds")))) ,'''
if old_leg_odds not in bet:
    raise SystemExit("parlay leg odds anchor not found")
bet = bet.replace(old_leg_odds, new_leg_odds, 1)
old_ticket_odds = '''        "american_odds": int(round(float(american_odds))),'''
new_ticket_odds = '''        "american_odds": "" if american_odds is None else int(round(float(american_odds))),'''
# Only change the parlay return, not make_bet_record.
pos = bet.find(old_ticket_odds, bet.find("def make_parlay_record"))
if pos < 0:
    raise SystemExit("parlay ticket odds anchor not found")
bet = bet[:pos] + new_ticket_odds + bet[pos + len(old_ticket_odds):]
bet_path.write_text(bet, encoding="utf-8")

# --- Contracts: protect sportsbook-independent model parlay UX. ---
contract_path = Path("tests/test_bet_add_buttons_contract.py")
contract = contract_path.read_text(encoding="utf-8")
contract = contract.replace('    assert "combined_parlay_odds" in source\n', '')
contract = contract.replace('    assert \'st.selectbox("Parlay sportsbook"\' in source\n', '')
contract = contract.replace(
    '    assert \'st.multiselect("Parlay legs (2–5)"\' in source\n',
    '    assert \'st.multiselect(\\n    "Parlay legs (2–5)"\' in source\n'
    '    assert \'st.text_input(\\n    "Sportsbook used (optional)"\' in source\n'
    '    assert \'st.text_input(\\n    "Actual parlay American odds (optional)"\' in source\n'
    '    assert "candidate_pool.empty" not in source[source.index(\'st.subheader("🎟️ Parlay Builder")\'):]\n'
    '    assert "same sportsbook" not in source[source.index(\'st.subheader("🎟️ Parlay Builder")\'):]\n',
    1,
)
contract = contract.replace(
    "    assert 'WATCH candidates are intentionally excluded from the parlay builder.' in source\n",
    "    assert 'WATCH leg(s)' in source\n",
)
contract_path.write_text(contract, encoding="utf-8")

tracker_test = Path("tests/test_bet_tracker.py")
test = tracker_test.read_text(encoding="utf-8")
insert_anchor = '''def test_parlay_grade_requires_every_leg_to_win():\n'''
new_test = '''def test_model_parlay_can_be_saved_without_sportsbook_or_odds():\n    legs = [\n        {"player":"A","market":"Strikeouts","game_date":"2026-08-11","line":5.5,"side":"Over","american_odds":None,"game_pk":1,"pitcher_id":11},\n        {"player":"B","market":"Total Outs","game_date":"2026-08-11","line":17.5,"side":"Under","american_odds":None,"game_pk":2,"pitcher_id":22},\n    ]\n    record = make_parlay_record(legs=legs, stake=1.0, game_date="2026-08-11", source="Top Plays Model Parlay")\n    assert record["book"] == ""\n    assert record["american_odds"] == ""\n    parsed = parse_parlay_legs(record["parlay_legs"])\n    assert parsed[0]["american_odds"] == ""\n    assert record["source"] == "Top Plays Model Parlay"\n\n\n'''
if insert_anchor not in test:
    raise SystemExit("tracker test insertion anchor not found")
test = test.replace(insert_anchor, new_test + insert_anchor, 1)
tracker_test.write_text(test, encoding="utf-8")

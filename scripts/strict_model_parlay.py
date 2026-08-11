from pathlib import Path

path = Path("pages/6_Top_Plays.py")
source = path.read_text(encoding="utf-8")
start = source.index('st.markdown("---")\nst.subheader("🎟️ Parlay Builder")')
end = source.index('selected_rank = st.session_state.get("top_play_detail_rank")', start)
block = '''st.markdown("---")
st.subheader("🎟️ Parlay Builder")
st.caption(
    "Build a parlay directly from our model Top 5. No sportsbook, live-price, or book-matching data is used here. "
    "Select any 2–5 model legs and choose one stake for the entire tracked model ticket."
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
    help="These choices come only from our model Top 5. Sportsbook availability does not filter the list.",
)
selected = plays.iloc[[option_map[label] for label in selected_labels]].copy() if selected_labels else plays.iloc[0:0].copy()
parlay_stake = st.number_input("Parlay stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_parlay_stake")

if len(selected) >= 2:
    watch_count = int((selected["Status"].astype(str) == "WATCH").sum())
    if watch_count:
        st.warning(f"This parlay includes {watch_count} WATCH leg(s). They are still in our Top 5, but they fall below the straight-bet model/data-quality action threshold.")
    if st.button(f"🎟️ Add {len(selected)}-leg model parlay to Bet Tracker", type="primary", use_container_width=True, key="save_top_plays_parlay"):
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
                game_date=today,
                source="Top Plays Model Parlay",
            )
            append_bet(BET_LOG, record, st.secrets)
            st.success(f"Saved {len(legs)}-leg model parlay to Bet Tracker. This tracks hit/loss results only; no sportsbook price was assumed.")
        except Exception as exc:
            st.error(f"Could not save parlay: {exc}")
else:
    st.info("Select at least two of our Top 5 model legs to build a parlay.")

'''
path.write_text(source[:start] + block + source[end:], encoding="utf-8")

contract_path = Path("tests/test_bet_add_buttons_contract.py")
contract = contract_path.read_text(encoding="utf-8")
contract = contract.replace("    assert 'st.text_input(\\n    \"Sportsbook used (optional)\"' in source\n", "")
contract = contract.replace("    assert 'st.text_input(\\n    \"Actual parlay American odds (optional)\"' in source\n", "")
needle = "    assert \"same sportsbook\" not in source[source.index('st.subheader(\"🎟️ Parlay Builder\")'):]\n"
if needle in contract:
    contract = contract.replace(needle, needle + "    assert 'Sportsbook used (optional)' not in source\n    assert 'Actual parlay American odds (optional)' not in source\n    assert 'book=book_note' not in source\n", 1)
contract_path.write_text(contract, encoding="utf-8")

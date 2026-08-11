from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"{label} anchor not found")
    return text.replace(old, new, 1)


# ---------------- Top Plays ----------------
path = Path("pages/6_Top_Plays.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from engine.bet_tracker import make_bet_record, projection_for_market\n",
    "from engine.bet_tracker import (\n    combined_parlay_odds,\n    make_bet_record,\n    make_parlay_record,\n    projection_for_market,\n)\n",
    "top plays parlay imports",
)
old_filter = '''        for side, model_p, fair_p, price in candidates:
            edge = model_p - fair_p
            if model_p < 0.55 or edge < 0.02 or quality < 60:
                continue
            market_label = "Strikeouts" if "strikeouts" in market else "Total Outs" if "outs" in market else "Hits Allowed"
            score = model_p + 0.5 * edge + 0.001 * quality
            legs.append({
                "Pitcher": row.get("player"), "Market": market_label, "Side": side, "Line": point,
                "Model Probability": model_p, "No-Vig Implied": fair_p, "Edge": edge,
                "Book": book, "Odds": int(price), "Data Quality": int(round(quality)), "Score": score,
                "Game PK": row.get("game_pk"), "Pitcher ID": row.get("pitcher_id"), "Team": row.get("team"),
                "Opponent": row.get("opponent"), "Market Key": market,
            })
'''
new_filter = '''        for side, model_p, fair_p, price in candidates:
            edge = model_p - fair_p
            qualified = model_p >= 0.55 and edge >= 0.02 and quality >= 60
            reasons = []
            if model_p < 0.55:
                reasons.append("probability")
            if edge < 0.02:
                reasons.append("edge")
            if quality < 60:
                reasons.append("quality")
            status = "QUALIFIED" if qualified else "WATCH · " + "/".join(reasons)
            market_label = "Strikeouts" if "strikeouts" in market else "Total Outs" if "outs" in market else "Hits Allowed"
            score = model_p + 0.5 * edge + 0.001 * quality
            legs.append({
                "Pitcher": row.get("player"), "Market": market_label, "Side": side, "Line": point,
                "Model Probability": model_p, "No-Vig Implied": fair_p, "Edge": edge,
                "Book": book, "Odds": int(price), "Data Quality": int(round(quality)), "Score": score,
                "Qualified": qualified, "Status": status,
                "Game PK": row.get("game_pk"), "Pitcher ID": row.get("pitcher_id"), "Team": row.get("team"),
                "Opponent": row.get("opponent"), "Market Key": market,
            })
'''
text = replace_once(text, old_filter, new_filter, "top plays candidate status")

start = '''if not all_legs:
    st.info("No legs currently clear the minimum filters (55% model probability, +2% no-vig edge, data quality 60+), or the sportsbooks have not posted supported pitcher props yet.")
    st.stop()

plays = pd.DataFrame(all_legs)
plays = plays.sort_values(["Score", "Edge", "Model Probability"], ascending=False)
plays = plays.drop_duplicates(["Pitcher", "Market", "Side", "Line"], keep="first")
plays = plays.drop_duplicates(["Pitcher", "Market"], keep="first").head(5).copy().reset_index(drop=True)
plays.insert(0, "Rank", range(1, len(plays) + 1))

c1, c2, c3 = st.columns(3)
c1.metric("Qualified legs", len(all_legs))
c2.metric("Pitchers scanned", len(slate))
c3.metric("Top board edge", f"{plays['Edge'].max():.1%}")

view = plays[["Rank", "Pitcher", "Market", "Side", "Line", "Odds", "Model Probability", "No-Vig Implied", "Edge", "Book", "Data Quality"]].copy()
for col in ("Model Probability", "No-Vig Implied", "Edge"):
    view[col] = view[col].map(lambda x: f"{x:.1%}")
st.subheader("Today's five strongest qualified legs")
st.caption("Click a row to open its projection breakdown.")
'''
replacement = '''if not all_legs:
    st.info("Sportsbooks have not posted enough two-sided supported pitcher props yet to calculate a no-vig Top Plays board. The daily model projections are still available on Daily Projection Run and the main Projection page.")
    st.stop()

candidate_pool = pd.DataFrame(all_legs)
qualified_total = int(candidate_pool["Qualified"].fillna(False).sum())
plays = candidate_pool.sort_values(["Qualified", "Score", "Edge", "Model Probability"], ascending=False)
plays = plays.drop_duplicates(["Pitcher", "Market", "Side", "Line"], keep="first")
plays = plays.drop_duplicates(["Pitcher", "Market"], keep="first").head(5).copy().reset_index(drop=True)
plays.insert(0, "Rank", range(1, len(plays) + 1))

c1, c2, c3 = st.columns(3)
c1.metric("Qualified candidates", qualified_total)
c2.metric("Pitchers scanned", len(slate))
c3.metric("Top board edge", f"{plays['Edge'].max():.1%}")

view = plays[["Rank", "Status", "Pitcher", "Market", "Side", "Line", "Odds", "Model Probability", "No-Vig Implied", "Edge", "Book", "Data Quality"]].copy()
for col in ("Model Probability", "No-Vig Implied", "Edge"):
    view[col] = view[col].map(lambda x: f"{x:.1%}")
st.subheader("Today's five strongest available legs")
if qualified_total == 0:
    st.warning("No current leg clears all betting thresholds. These are the five closest available candidates, shown for review only — not official model bets.")
else:
    st.caption("QUALIFIED legs clear 55% model probability, +2% no-vig edge, and data quality 60+. WATCH legs are shown so the board never goes blank when the slate is thin.")
st.caption("Click a row or use View details to open its projection breakdown.")
'''
text = replace_once(text, start, replacement, "top plays fallback board")

old_actions = '''st.markdown("#### Top Play actions")
st.caption("Quick-add stake is the amount recorded in Bet Tracker for P/L and ROI. It does not place a sportsbook wager and it does not affect the projection model.")
quick_stake = st.number_input("Quick-add stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_quick_stake")
button_cols = st.columns(len(plays))
for button_idx, (_, play_row) in enumerate(plays.iterrows()):
    snapshot = find_snapshot(history, play_row)
    snapshot_dict = snapshot.to_dict() if snapshot is not None else None
    projection_value = projection_for_market(snapshot_dict, play_row.get("Market")) if snapshot_dict else None
    with button_cols[button_idx]:
        rank = int(play_row["Rank"])
        st.caption(f"#{rank} {play_row['Pitcher']} · {play_row['Side']} {float(play_row['Line']):g}")
        if st.button("🔎 View details", key=f"view_top_play_{rank}", use_container_width=True):
            st.session_state["top_play_detail_rank"] = rank
        if st.button("➕ Add as bet", key=f"add_top_play_{rank}", use_container_width=True):
            try:
                game_pk = numeric(play_row.get("Game PK"))
                pitcher_id = numeric(play_row.get("Pitcher ID"))
                record = make_bet_record(
                    player=str(play_row["Pitcher"]),
                    market=play_row["Market"],
                    game_date=str(snapshot.get("game_date", today) if snapshot is not None else today),
                    line=float(play_row["Line"]),
                    side=str(play_row["Side"]),
                    american_odds=float(play_row["Odds"]),
                    stake=float(quick_stake),
                    book=str(play_row.get("Book", "")),
                    projection=projection_value,
                    model_probability=float(play_row["Model Probability"]),
                    implied_probability=float(play_row["No-Vig Implied"]),
                    edge=float(play_row["Edge"]),
                    confidence=(snapshot.get("confidence", "") if snapshot is not None else ""),
                    game_pk=None if game_pk is None else int(game_pk),
                    pitcher_id=None if pitcher_id is None else int(pitcher_id),
                )
                append_bet(BET_LOG, record, st.secrets)
                st.success("Added to Bet Tracker")
            except Exception as exc:
                st.error(f"Could not add bet: {exc}")
'''
new_actions = '''st.markdown("#### Top Play actions")
st.caption("Straight-bet stake is the amount recorded for one individual leg. It does not place a sportsbook wager and it does not affect the projection model.")
quick_stake = st.number_input("Straight-bet stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_quick_stake")
button_cols = st.columns(len(plays))
for button_idx, (_, play_row) in enumerate(plays.iterrows()):
    snapshot = find_snapshot(history, play_row)
    snapshot_dict = snapshot.to_dict() if snapshot is not None else None
    projection_value = projection_for_market(snapshot_dict, play_row.get("Market")) if snapshot_dict else None
    qualified = bool(play_row.get("Qualified", False))
    with button_cols[button_idx]:
        rank = int(play_row["Rank"])
        st.caption(f"#{rank} {play_row['Pitcher']} · {play_row['Side']} {float(play_row['Line']):g}")
        if st.button("🔎 View details", key=f"view_top_play_{rank}", use_container_width=True):
            st.session_state["top_play_detail_rank"] = rank
        if st.button("➕ Add as bet", key=f"add_top_play_{rank}", use_container_width=True, disabled=not qualified):
            try:
                game_pk = numeric(play_row.get("Game PK"))
                pitcher_id = numeric(play_row.get("Pitcher ID"))
                record = make_bet_record(
                    player=str(play_row["Pitcher"]),
                    market=play_row["Market"],
                    game_date=str(snapshot.get("game_date", today) if snapshot is not None else today),
                    line=float(play_row["Line"]),
                    side=str(play_row["Side"]),
                    american_odds=float(play_row["Odds"]),
                    stake=float(quick_stake),
                    book=str(play_row.get("Book", "")),
                    projection=projection_value,
                    model_probability=float(play_row["Model Probability"]),
                    implied_probability=float(play_row["No-Vig Implied"]),
                    edge=float(play_row["Edge"]),
                    confidence=(snapshot.get("confidence", "") if snapshot is not None else ""),
                    game_pk=None if game_pk is None else int(game_pk),
                    pitcher_id=None if pitcher_id is None else int(pitcher_id),
                )
                append_bet(BET_LOG, record, st.secrets)
                st.success("Added to Bet Tracker")
            except Exception as exc:
                st.error(f"Could not add bet: {exc}")
        if not qualified:
            st.caption("WATCH only")

st.markdown("---")
st.subheader("🎟️ Parlay Builder")
st.caption("A parlay uses one stake for the entire ticket. Legs must come from the same sportsbook. The estimated combined odds are only a starting point; enter the actual price quoted by your sportsbook before saving, especially for same-game or correlated props.")
qualified_pool = candidate_pool.loc[candidate_pool["Qualified"].fillna(False)].copy()
qualified_pool = qualified_pool.sort_values(["Score", "Edge", "Model Probability"], ascending=False)
qualified_pool = qualified_pool.drop_duplicates(["Book", "Pitcher", "Market"], keep="first")
book_counts = qualified_pool.groupby("Book").size() if not qualified_pool.empty else pd.Series(dtype=int)
parlay_books = [str(book) for book, count in book_counts.items() if int(count) >= 2]
if not parlay_books:
    st.info("No sportsbook currently has at least two qualified legs available for a model-backed parlay. WATCH candidates are intentionally excluded from the parlay builder.")
else:
    parlay_book = st.selectbox("Parlay sportsbook", parlay_books, key="top_plays_parlay_book")
    same_book = qualified_pool.loc[qualified_pool["Book"].astype(str).eq(parlay_book)].head(5).copy().reset_index(drop=True)
    option_map = {}
    for idx, leg in same_book.iterrows():
        label = f"{leg['Pitcher']} · {leg['Market']} · {leg['Side']} {float(leg['Line']):g} · {int(leg['Odds']):+d}"
        option_map[label] = idx
    selected_labels = st.multiselect("Parlay legs (2–5)", list(option_map), default=list(option_map), max_selections=5, key="top_plays_parlay_legs")
    selected = same_book.iloc[[option_map[label] for label in selected_labels]].copy() if selected_labels else same_book.iloc[0:0].copy()
    parlay_stake = st.number_input("Parlay stake (units)", min_value=0.0, value=1.0, step=0.5, key="top_plays_parlay_stake")
    if len(selected) >= 2:
        estimated_odds = combined_parlay_odds(selected["Odds"].astype(float).tolist())
        st.caption(f"Estimated standard combined price: {estimated_odds:+d}. Use the actual sportsbook quote if it differs.")
        quoted_odds = st.number_input("Sportsbook quoted parlay odds", min_value=-5000, max_value=100000, value=int(estimated_odds), step=5, key="top_plays_parlay_odds")
        save_parlay = st.button(f"🎟️ Add {len(selected)}-leg parlay to Bet Tracker", type="primary", use_container_width=True, key="save_top_plays_parlay")
        if save_parlay:
            legs = []
            for _, leg in selected.iterrows():
                game_pk = numeric(leg.get("Game PK")); pitcher_id = numeric(leg.get("Pitcher ID"))
                legs.append({
                    "player": str(leg["Pitcher"]), "market": str(leg["Market"]), "game_date": today,
                    "line": float(leg["Line"]), "side": str(leg["Side"]), "american_odds": float(leg["Odds"]),
                    "game_pk": None if game_pk is None else int(game_pk),
                    "pitcher_id": None if pitcher_id is None else int(pitcher_id),
                })
            try:
                record = make_parlay_record(legs=legs, stake=float(parlay_stake), book=parlay_book, american_odds=int(quoted_odds), game_date=today)
                append_bet(BET_LOG, record, st.secrets)
                st.success(f"Saved {len(legs)}-leg {parlay_book} parlay to Bet Tracker")
            except Exception as exc:
                st.error(f"Could not save parlay: {exc}")
    else:
        st.info("Select at least two qualified legs from the same sportsbook to build a parlay.")
'''
text = replace_once(text, old_actions, new_actions, "top plays parlay actions")
path.write_text(text, encoding="utf-8")


# ---------------- Bet Tracker ----------------
path = Path("pages/2_Bet_Tracker.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "    grade_bet,\n    normalize_market,\n",
    "    grade_bet,\n    grade_parlay,\n    normalize_market,\n    parse_parlay_legs,\n",
    "tracker parlay imports",
)
old_market_norm = '''if "market" not in tracker.columns:
    tracker["market"] = "Strikeouts"
tracker["market"] = tracker["market"].map(normalize_market)
if "stake" not in tracker.columns:
'''
new_market_norm = '''if "market" not in tracker.columns:
    tracker["market"] = "Strikeouts"
if "bet_type" not in tracker.columns:
    tracker["bet_type"] = "Straight"
tracker["bet_type"] = tracker["bet_type"].fillna("Straight").astype(str)
straight_mask = ~tracker["bet_type"].str.lower().eq("parlay")
tracker.loc[straight_mask, "market"] = tracker.loc[straight_mask, "market"].map(normalize_market)
tracker.loc[~straight_mask, "market"] = "Parlay"
if "parlay_legs" not in tracker.columns:
    tracker["parlay_legs"] = ""
if "stake" not in tracker.columns:
'''
text = replace_once(text, old_market_norm, new_market_norm, "tracker parlay schema")

old_loop = '''with st.spinner("Checking saved bets against MLB pitching stats..."):
    for _, row in ordered.iterrows():
        player = str(row.get("player", "Unknown"))
        market = normalize_market(row.get("market"))
        line = _num(row.get("line")) or 0.0
        side = str(row.get("side", "Over")).title()
        game_date = str(row.get("game_date", ""))[:10]
        actual, status, final = live_pitcher_prop(
            player,
            market,
            game_date,
            _int_or_none(row.get("game_pk")),
            _int_or_none(row.get("pitcher_id")),
        )
        grade = grade_bet(side, line, actual, final)
        stake = _num(row.get("stake"))
        odds = _num(row.get("american_odds"))
        profit = profit_for(stake, odds, grade)
        team = _clean_text(row.get("team"))
        opponent = _clean_text(row.get("opponent"))
        matchup = f"{team} vs {opponent}" if team and opponent else "—"
        resolved_rows.append({
            "Pitcher": player,
            "Matchup": matchup,
            "Date": game_date,
            "Market": market,
            "Bet": f"{side} {line:g}",
            "Odds": _format_odds(odds),
            "Book": str(row.get("book", "") or "—"),
            "Stake": stake,
            "Actual": actual,
            "Game Status": status,
            "Result": grade.result,
            "Profit/Loss": profit,
            "Projection": _num(row.get("projection")),
            "Model Probability": _num(row.get("model_probability")),
            "Edge": _num(row.get("edge")),
        })
'''
new_loop = '''with st.spinner("Checking saved bets against MLB pitching stats..."):
    for _, row in ordered.iterrows():
        bet_type = str(row.get("bet_type", "Straight") or "Straight").title()
        game_date = str(row.get("game_date", ""))[:10]
        stake = _num(row.get("stake"))
        odds = _num(row.get("american_odds"))
        if bet_type == "Parlay":
            legs = parse_parlay_legs(row.get("parlay_legs"))
            leg_grades = []
            leg_summaries = []
            statuses = []
            for leg in legs:
                leg_player = str(leg.get("player", "Unknown"))
                leg_market = normalize_market(leg.get("market"))
                leg_line = _num(leg.get("line")) or 0.0
                leg_side = str(leg.get("side", "Over")).title()
                actual, status, final = live_pitcher_prop(
                    leg_player,
                    leg_market,
                    str(leg.get("game_date", game_date))[:10],
                    _int_or_none(leg.get("game_pk")),
                    _int_or_none(leg.get("pitcher_id")),
                )
                leg_grade = grade_bet(leg_side, leg_line, actual, final)
                leg_grades.append(leg_grade)
                statuses.append(status)
                actual_text = "—" if actual is None else f"{actual:g}"
                leg_summaries.append(f"{leg_player} {leg_side} {leg_line:g} {leg_market} [{actual_text} · {leg_grade.result}]")
            grade = grade_parlay(leg_grades)
            profit = profit_for(stake, odds, grade)
            resolved_rows.append({
                "Pitcher": f"{len(legs)}-leg parlay",
                "Matchup": "Multiple",
                "Date": game_date,
                "Market": "Parlay",
                "Bet": " | ".join(leg_summaries),
                "Odds": _format_odds(odds),
                "Book": str(row.get("book", "") or "—"),
                "Stake": stake,
                "Actual": "—",
                "Game Status": " / ".join(sorted(set(statuses))) if statuses else "Pending",
                "Result": grade.result,
                "Profit/Loss": profit,
                "Projection": None,
                "Model Probability": None,
                "Edge": None,
            })
            continue

        player = str(row.get("player", "Unknown"))
        market = normalize_market(row.get("market"))
        line = _num(row.get("line")) or 0.0
        side = str(row.get("side", "Over")).title()
        actual, status, final = live_pitcher_prop(
            player,
            market,
            game_date,
            _int_or_none(row.get("game_pk")),
            _int_or_none(row.get("pitcher_id")),
        )
        grade = grade_bet(side, line, actual, final)
        profit = profit_for(stake, odds, grade)
        team = _clean_text(row.get("team"))
        opponent = _clean_text(row.get("opponent"))
        matchup = f"{team} vs {opponent}" if team and opponent else "—"
        resolved_rows.append({
            "Pitcher": player,
            "Matchup": matchup,
            "Date": game_date,
            "Market": market,
            "Bet": f"{side} {line:g}",
            "Odds": _format_odds(odds),
            "Book": str(row.get("book", "") or "—"),
            "Stake": stake,
            "Actual": actual,
            "Game Status": status,
            "Result": grade.result,
            "Profit/Loss": profit,
            "Projection": _num(row.get("projection")),
            "Model Probability": _num(row.get("model_probability")),
            "Edge": _num(row.get("edge")),
        })
'''
text = replace_once(text, old_loop, new_loop, "tracker parlay grading")
text = replace_once(
    text,
    'view["Actual"] = view["Actual"].map(lambda x: "—" if pd.isna(x) else f"{x:g}")\n',
    'view["Actual"] = view["Actual"].map(lambda x: "—" if pd.isna(x) else (f"{x:g}" if isinstance(x, (int, float)) else str(x)))\n',
    "tracker mixed actual formatting",
)
text = replace_once(
    text,
    'pushes = int((results["Result"] == "PUSH").sum())\npending = int((~results["Result"].isin(["WIN", "LOSS", "PUSH"])).sum())\n',
    'pushes = int(results["Result"].isin(["PUSH", "PUSH LEG"]).sum())\npending = int((~results["Result"].isin(["WIN", "LOSS", "PUSH", "PUSH LEG"])).sum())\n',
    "tracker parlay push metrics",
)
path.write_text(text, encoding="utf-8")

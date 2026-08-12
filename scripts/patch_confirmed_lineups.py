from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor not found: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Opposing batter engine: add contact rate alongside K rate.
# ---------------------------------------------------------------------------
path = Path("engine/opposing_batters.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'LEAGUE_K_RATE = 0.224\nLINEUP_SPLIT_PRIOR_PA = 60.0\n',
    'LEAGUE_K_RATE = 0.224\nLEAGUE_HIT_RATE = 0.235\nLINEUP_SPLIT_PRIOR_PA = 60.0\n',
    "opposing constants",
)
text = replace_once(
    text,
    'COLUMNS = ["Batter", "Hand", "Lineup Spot", "K% vs Pitcher", "PA", "Risk", "Split Available"]',
    'COLUMNS = ["Batter", "Hand", "Lineup Spot", "K% vs Pitcher", "H/PA vs Pitcher", "PA", "Risk", "Split Available"]',
    "opposing columns",
)
text = replace_once(
    text,
    '                best_pa = -1.0\n                best_rate: float | None = None\n',
    '                best_pa = -1.0\n                best_rate: float | None = None\n                best_hit_rate: float | None = None\n',
    "opposing best split init",
)
text = replace_once(
    text,
    '                        so = float(stat.get("strikeOuts", 0) or 0)\n                        if pa <= 0:\n                            continue\n                        rate = float(np.clip(so / pa, 0.0, 1.0))\n                        if pa > best_pa:\n                            best_pa = pa\n                            best_rate = rate\n',
    '                        so = float(stat.get("strikeOuts", 0) or 0)\n                        hits = float(stat.get("hits", 0) or 0)\n                        if pa <= 0:\n                            continue\n                        rate = float(np.clip(so / pa, 0.0, 1.0))\n                        hit_rate = float(np.clip(hits / pa, 0.0, 1.0))\n                        if pa > best_pa:\n                            best_pa = pa\n                            best_rate = rate\n                            best_hit_rate = hit_rate\n',
    "opposing split rates",
)
text = replace_once(
    text,
    '                        "K% vs Pitcher": best_rate,\n                        "PA": best_pa,\n',
    '                        "K% vs Pitcher": best_rate,\n                        "H/PA vs Pitcher": LEAGUE_HIT_RATE if best_hit_rate is None else best_hit_rate,\n                        "PA": best_pa,\n',
    "opposing row hit rate",
)
text = text.replace(
    '                        "K% vs Pitcher": LEAGUE_K_RATE,\n                        "PA": 0.0,\n',
    '                        "K% vs Pitcher": LEAGUE_K_RATE,\n                        "H/PA vs Pitcher": LEAGUE_HIT_RATE,\n                        "PA": 0.0,\n',
)
text = replace_once(
    text,
    '    rates = pd.to_numeric(batters["K% vs Pitcher"], errors="coerce").fillna(LEAGUE_K_RATE).clip(0.0, 1.0)\n    total_pa = float(pa.sum())\n\n    if confirmed_lineup:\n',
    '    rates = pd.to_numeric(batters["K% vs Pitcher"], errors="coerce").fillna(LEAGUE_K_RATE).clip(0.0, 1.0)\n    hit_rates = pd.to_numeric(batters.get("H/PA vs Pitcher", LEAGUE_HIT_RATE), errors="coerce").fillna(LEAGUE_HIT_RATE).clip(0.0, 1.0)\n    total_pa = float(pa.sum())\n\n    if confirmed_lineup:\n',
    "opposing summary hit rates",
)
text = replace_once(
    text,
    '        adjusted = (rates * pa + LEAGUE_K_RATE * LINEUP_SPLIT_PRIOR_PA) / (pa + LINEUP_SPLIT_PRIOR_PA)\n        rate = float(adjusted.mean()) if len(adjusted) else LEAGUE_K_RATE\n    else:\n        rate = float((rates * pa).sum() / total_pa) if total_pa else LEAGUE_K_RATE\n\n    return {\n        "k_rate": float(np.clip(rate, 0.08, 0.45)),\n',
    '        adjusted = (rates * pa + LEAGUE_K_RATE * LINEUP_SPLIT_PRIOR_PA) / (pa + LINEUP_SPLIT_PRIOR_PA)\n        adjusted_hits = (hit_rates * pa + LEAGUE_HIT_RATE * LINEUP_SPLIT_PRIOR_PA) / (pa + LINEUP_SPLIT_PRIOR_PA)\n        rate = float(adjusted.mean()) if len(adjusted) else LEAGUE_K_RATE\n        hit_rate = float(adjusted_hits.mean()) if len(adjusted_hits) else LEAGUE_HIT_RATE\n    else:\n        rate = float((rates * pa).sum() / total_pa) if total_pa else LEAGUE_K_RATE\n        hit_rate = float((hit_rates * pa).sum() / total_pa) if total_pa else LEAGUE_HIT_RATE\n\n    return {\n        "k_rate": float(np.clip(rate, 0.08, 0.45)),\n        "hit_rate": float(np.clip(hit_rate, 0.12, 0.36)),\n',
    "opposing summary outputs",
)
text = text.replace(
    'return {"k_rate": LEAGUE_K_RATE, "pa": 0, "high": 0, "elevated": 0, "batters": 0, "confirmed": False}',
    'return {"k_rate": LEAGUE_K_RATE, "hit_rate": LEAGUE_HIT_RATE, "pa": 0, "high": 0, "elevated": 0, "batters": 0, "confirmed": False}',
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Daily runner: capture confirmed lineup metadata and pregame upgrades.
# ---------------------------------------------------------------------------
path = Path("automation/daily_projection_runner.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from engine.opposing_batters import get_opposing_batters, matchup_summary\n',
    'from engine.opposing_batters import get_opposing_batters, matchup_summary\nfrom engine.lineup_context import LINEUP_ACTIVE_ROSTER, LINEUP_CONFIRMED, get_confirmed_lineup\n',
    "daily lineup import",
)
text = text.replace('APP_VERSION = "3.5.0"', 'APP_VERSION = "3.6.0"', 1)
old = '''def matchup_k_rate(opponent: str, pitcher_id: int, season: int, opponent_team_id: int | None = None) -> tuple[float, int, int]:
    hand = pitcher_hand(pitcher_id)
    if hand not in {"R", "L"}:
        return .224, 0, 0
    batters = get_opposing_batters(opponent, hand, season, opponent_team_id)
    summary = matchup_summary(batters)
    return float(summary["k_rate"]), int(summary["pa"]), int(len(batters))
'''
new = '''def matchup_context(
    game_pk: int,
    opponent: str,
    pitcher_id: int,
    season: int,
    opponent_team_id: int | None = None,
) -> dict[str, object]:
    hand = pitcher_hand(pitcher_id)
    if hand not in {"R", "L"}:
        return {"k_rate": .224, "hit_rate": .235, "pa": 0, "batters": 0, "lineup_batters": 0, "source": LINEUP_ACTIVE_ROSTER, "confirmed": False, "lineup_hash": ""}
    lineup = get_confirmed_lineup(int(game_pk), int(opponent_team_id or 0))
    batter_ids = lineup.player_ids if lineup.confirmed else ()
    lineup_spots = lineup.spots if lineup.confirmed else ()
    batters = get_opposing_batters(opponent, hand, season, opponent_team_id, batter_ids, lineup_spots)
    summary = matchup_summary(batters, confirmed_lineup=lineup.confirmed)
    return {
        "k_rate": float(summary["k_rate"]),
        "hit_rate": float(summary.get("hit_rate", .235)),
        "pa": int(summary["pa"]),
        "batters": int(len(batters)),
        "lineup_batters": int(lineup.batter_count if lineup.confirmed else 0),
        "source": lineup.source,
        "confirmed": bool(lineup.confirmed),
        "lineup_hash": lineup.fingerprint,
    }


def matchup_k_rate(opponent: str, pitcher_id: int, season: int, opponent_team_id: int | None = None) -> tuple[float, int, int]:
    """Legacy active-roster wrapper retained for callers/tests that do not have a game id."""
    hand = pitcher_hand(pitcher_id)
    if hand not in {"R", "L"}:
        return .224, 0, 0
    batters = get_opposing_batters(opponent, hand, season, opponent_team_id)
    summary = matchup_summary(batters)
    return float(summary["k_rate"]), int(summary["pa"]), int(len(batters))
'''
text = replace_once(text, old, new, "daily matchup context")
text = replace_once(
    text,
    'def features(log: pd.DataFrame, venue: str, opponent_k_pct: float = .224) -> dict[str, float]:',
    'def features(log: pd.DataFrame, venue: str, opponent_k_pct: float = .224, lineup_batters: int = 0, matchup_source: str = LINEUP_ACTIVE_ROSTER) -> dict[str, float]:',
    "daily feature signature",
)
text = replace_once(
    text,
    '        "lineup_batters": 0,\n',
    '        "lineup_batters": int(lineup_batters),\n        "matchup_source": str(matchup_source),\n',
    "daily feature lineup count",
)
old = '''    opponent_k_pct, matchup_pa, matchup_batters = matchup_k_rate(
        row["opponent"], row["pitcher_id"], season, row.get("opponent_team_id")
    )
    f = features(log, row["venue"], opponent_k_pct=opponent_k_pct)
'''
new = '''    matchup = matchup_context(
        row["game_pk"], row["opponent"], row["pitcher_id"], season, row.get("opponent_team_id")
    )
    opponent_k_pct = float(matchup["k_rate"])
    f = features(
        log,
        row["venue"],
        opponent_k_pct=opponent_k_pct,
        lineup_batters=int(matchup["lineup_batters"]),
        matchup_source=str(matchup["source"]),
    )
'''
text = replace_once(text, old, new, "daily project matchup")
text = replace_once(
    text,
    '        expected_bf=f["expected_bf"],\n        seed=seed ^ 0x5A17,\n',
    '        expected_bf=f["expected_bf"],\n        opponent_hit_rate=float(matchup.get("hit_rate", .235)),\n        seed=seed ^ 0x5A17,\n',
    "daily hits lineup contact",
)
text = replace_once(
    text,
    '        "player": row["player"], "team": row["team"], "opponent": row["opponent"], "venue_id": row.get("venue_id", 0), "venue": row["venue"],\n',
    '        "player": row["player"], "team": row["team"], "opponent": row["opponent"], "opponent_team_id": row.get("opponent_team_id"), "venue_id": row.get("venue_id", 0), "venue": row["venue"],\n',
    "daily opponent team id",
)
text = replace_once(
    text,
    '        "opponent_k_pct": opponent_k_pct * 100.0, "matchup_pa": matchup_pa, "matchup_batters": matchup_batters,\n',
    '        "opponent_k_pct": opponent_k_pct * 100.0, "opponent_hit_rate": float(matchup.get("hit_rate", .235)) * 100.0,\n        "matchup_pa": int(matchup["pa"]), "matchup_batters": int(matchup["batters"]),\n        "lineup_source": str(matchup["source"]), "lineup_confirmed": bool(matchup["confirmed"]),\n        "lineup_batters": int(matchup["lineup_batters"]), "lineup_hash": str(matchup["lineup_hash"]),\n        "lineup_captured_at_utc": now if bool(matchup["confirmed"]) else "",\n        "lineup_preconfirm_projection": np.nan, "lineup_preconfirm_opponent_k_pct": np.nan,\n        "lineup_projection_delta": np.nan, "lineup_opponent_k_delta": np.nan,\n',
    "daily lineup snapshot fields",
)
anchor = '''def fill_missing_pregame_paths(frame: pd.DataFrame) -> int:
'''
refresh_fn = '''def refresh_pregame_lineups(frame: pd.DataFrame, announced: list[dict]) -> int:
    """Upgrade roster-fallback snapshots when a confirmed lineup posts pregame.

    Started/finished games are never touched. The old K projection and opponent-K
    input are retained in audit fields so the impact of the lineup can be measured.
    """
    if frame.empty or not announced:
        return 0
    now = datetime.now(timezone.utc)
    lookup = {(int(r["game_pk"]), int(r["pitcher_id"])): r for r in announced}
    updated = 0
    for idx in frame.index:
        row = frame.loc[idx]
        if not row_is_pregame(row, now) or str(row.get("lineup_source", "")) == LINEUP_CONFIRMED:
            continue
        try:
            key = (int(row["game_pk"]), int(row["pitcher_id"]))
        except (TypeError, ValueError):
            continue
        scheduled = lookup.get(key)
        if not scheduled:
            continue
        context = matchup_context(
            int(scheduled["game_pk"]), str(scheduled["opponent"]), int(scheduled["pitcher_id"]),
            datetime.fromisoformat(str(scheduled["game_date"])).year, scheduled.get("opponent_team_id")
        )
        if not bool(context.get("confirmed")):
            continue
        old_projection = pd.to_numeric(pd.Series([row.get("projection")]), errors="coerce").iloc[0]
        old_opp_k = pd.to_numeric(pd.Series([row.get("opponent_k_pct")]), errors="coerce").iloc[0]
        try:
            projected = project(scheduled)
        except Exception as exc:
            print(f"Confirmed-lineup refresh failed for {row.get('player', 'Unknown')} ({row.get('game_pk')}): {exc}")
            continue
        if not projected or str(projected.get("lineup_source", "")) != LINEUP_CONFIRMED:
            continue
        protected = {"actual_strikeouts", "actual_hits_allowed", "actual_outs", "resolved_at_utc"}
        for field, value in projected.items():
            if field not in protected:
                frame.at[idx, field] = value
        frame.at[idx, "lineup_preconfirm_projection"] = old_projection
        frame.at[idx, "lineup_preconfirm_opponent_k_pct"] = old_opp_k
        new_projection = pd.to_numeric(pd.Series([projected.get("projection")]), errors="coerce").iloc[0]
        new_opp_k = pd.to_numeric(pd.Series([projected.get("opponent_k_pct")]), errors="coerce").iloc[0]
        frame.at[idx, "lineup_projection_delta"] = np.nan if pd.isna(old_projection) or pd.isna(new_projection) else float(new_projection - old_projection)
        frame.at[idx, "lineup_opponent_k_delta"] = np.nan if pd.isna(old_opp_k) or pd.isna(new_opp_k) else float(new_opp_k - old_opp_k)
        updated += 1
    return updated


'''
text = replace_once(text, anchor, refresh_fn + anchor, "daily lineup refresh insertion")
text = replace_once(
    text,
    '    weather_refreshes = attach_pregame_weather(frame, rows)\n',
    '    weather_refreshes = attach_pregame_weather(frame, rows)\n    lineup_refreshes = refresh_pregame_lineups(frame, rows)\n',
    "daily main lineup refresh",
)
text = replace_once(
    text,
    '        f"projection log rows={len(frame)} new={len(new_rows)} pregame_path_refreshes={refreshed} weather_refreshes={weather_refreshes} "\n',
    '        f"projection log rows={len(frame)} new={len(new_rows)} pregame_path_refreshes={refreshed} weather_refreshes={weather_refreshes} lineup_refreshes={lineup_refreshes} "\n',
    "daily main print",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main Projection page: use and display confirmed batting order + contact input.
# ---------------------------------------------------------------------------
path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from engine.opposing_batters import get_opposing_batters, matchup_summary\n',
    'from engine.opposing_batters import get_opposing_batters, matchup_summary\nfrom engine.lineup_context import LINEUP_CONFIRMED, get_confirmed_lineup\n',
    "app lineup import",
)
text = text.replace('APP_VERSION = "3.5.0"', 'APP_VERSION = "3.6.0"', 1)
text = replace_once(
    text,
    'TEAM_ABBR = {108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSH",121:"NYM",133:"ATH",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",147:"NYY",158:"MIL"}\n',
    'TEAM_ABBR = {108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSH",121:"NYM",133:"ATH",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",147:"NYY",158:"MIL"}\nTEAM_ID_BY_ABBR = {abbr: team_id for team_id, abbr in TEAM_ABBR.items()}\n',
    "app team inverse",
)
old = '''pitcher_hand=get_pitcher_hand(game.pitcher_id)
opposing_batters=get_opposing_batters(game.opponent,pitcher_hand,selected_date.year)
opponent_matchup=matchup_summary(opposing_batters)
weather_risk=get_game_weather(game.venue_id,game.game_time)
proj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),0); kdf=ladder(proj,10)
features_for_hits=build_engine_features(log,game,float(opponent_matchup["k_rate"]),0)
hits_seed=int(hashlib.sha256(f"hits|{game.key}|{game.game_time}|{APP_VERSION}".encode()).hexdigest()[:8],16)
hits_proj=project_hits_allowed(log,expected_bf=features_for_hits["expected_bf"],seed=hits_seed,draws=25000,lines=(3.5,4.5,5.5,6.5,7.5,8.5))
'''
new = '''pitcher_hand=get_pitcher_hand(game.pitcher_id)
opponent_team_id=TEAM_ID_BY_ABBR.get(game.opponent,0)
lineup_context=get_confirmed_lineup(game.game_pk,opponent_team_id)
opposing_batters=get_opposing_batters(
    game.opponent,pitcher_hand,selected_date.year,opponent_team_id,
    lineup_context.player_ids if lineup_context.confirmed else (),
    lineup_context.spots if lineup_context.confirmed else (),
)
opponent_matchup=matchup_summary(opposing_batters,confirmed_lineup=lineup_context.confirmed)
weather_risk=get_game_weather(game.venue_id,game.game_time)
confirmed_count=lineup_context.batter_count if lineup_context.confirmed else 0
proj=calculate_projection(log,game,25000,float(opponent_matchup["k_rate"]),confirmed_count); kdf=ladder(proj,10)
features_for_hits=build_engine_features(log,game,float(opponent_matchup["k_rate"]),confirmed_count)
hits_seed=int(hashlib.sha256(f"hits|{game.key}|{game.game_time}|{APP_VERSION}".encode()).hexdigest()[:8],16)
hits_proj=project_hits_allowed(log,expected_bf=features_for_hits["expected_bf"],opponent_hit_rate=float(opponent_matchup.get("hit_rate",.235)),seed=hits_seed,draws=25000,lines=(3.5,4.5,5.5,6.5,7.5,8.5))
'''
text = replace_once(text, old, new, "app matchup calculation")
old = '''st.markdown('<div class="section-head">OPPOSING BATTER BOX</div>',unsafe_allow_html=True)
st.caption(f"Active {game.opponent} hitters vs a {pitcher_hand or 'unknown-hand'} pitcher. K% is the same pitcher-hand split used by the matchup input; this box is supplemental and safely degrades when MLB split data is incomplete.")
if opposing_batters.empty:
    st.info("Opposing batter split data is not available yet. The projection falls back to the protected league opponent-K baseline.")
else:
    b1,b2,b3,b4=st.columns(4)
    b1.metric("Matchup K%",f"{float(opponent_matchup['k_rate']):.1%}")
    b2.metric("Split PA",int(opponent_matchup["pa"]))
    b3.metric("HIGH K hitters",int(opponent_matchup["high"]))
    b4.metric("ELEVATED K hitters",int(opponent_matchup["elevated"]))
    batter_display=opposing_batters.copy()
    batter_display["K% vs Pitcher"]=pd.to_numeric(batter_display["K% vs Pitcher"],errors="coerce")*100.0
    batter_display["Risk"]=batter_display["Risk"].map({"HIGH":"🔥 HIGH","ELEVATED":"⚠️ ELEVATED","NORMAL":"NORMAL"}).fillna(batter_display["Risk"])
    st.dataframe(
        batter_display[["Batter","Hand","K% vs Pitcher","PA","Risk"]],
        hide_index=True,
        width="stretch",
        column_config={
            "Batter":st.column_config.TextColumn("Batter"),
            "Hand":st.column_config.TextColumn("Bats"),
            "K% vs Pitcher":st.column_config.NumberColumn(f"K% vs {pitcher_hand or 'Pitcher'}",format="%.1f%%"),
            "PA":st.column_config.NumberColumn("Split PA",format="%.0f"),
            "Risk":st.column_config.TextColumn("K Risk"),
        },
    )
'''
new = '''st.markdown('<div class="section-head">OPPOSING BATTER BOX</div>',unsafe_allow_html=True)
lineup_label="✅ CONFIRMED BATTING ORDER" if lineup_context.confirmed else "ACTIVE ROSTER FALLBACK · lineup not posted yet"
st.caption(f"{lineup_label} · {game.opponent} hitters vs a {pitcher_hand or 'unknown-hand'} pitcher. Pitcher-hand K% and H/PA feed the baseball matchup; incomplete hitter splits shrink safely toward league rates.")
if opposing_batters.empty:
    st.info("Opposing batter split data is not available yet. The projection falls back to protected league opponent baselines.")
else:
    b1,b2,b3,b4,b5=st.columns(5)
    b1.metric("Matchup K%",f"{float(opponent_matchup['k_rate']):.1%}")
    b2.metric("Matchup H/PA",f"{float(opponent_matchup.get('hit_rate',.235)):.1%}")
    b3.metric("Split PA",int(opponent_matchup["pa"]))
    b4.metric("HIGH K hitters",int(opponent_matchup["high"]))
    b5.metric("ELEVATED K hitters",int(opponent_matchup["elevated"]))
    batter_display=opposing_batters.copy()
    batter_display["K% vs Pitcher"]=pd.to_numeric(batter_display["K% vs Pitcher"],errors="coerce")*100.0
    batter_display["H/PA vs Pitcher"]=pd.to_numeric(batter_display["H/PA vs Pitcher"],errors="coerce")*100.0
    batter_display["Risk"]=batter_display["Risk"].map({"HIGH":"🔥 HIGH","ELEVATED":"⚠️ ELEVATED","NORMAL":"NORMAL"}).fillna(batter_display["Risk"])
    batter_display["Split Available"]=batter_display["Split Available"].map({True:"MLB split",False:"League fallback"}).fillna("League fallback")
    columns=["Lineup Spot","Batter","Hand","K% vs Pitcher","H/PA vs Pitcher","PA","Risk","Split Available"] if lineup_context.confirmed else ["Batter","Hand","K% vs Pitcher","H/PA vs Pitcher","PA","Risk","Split Available"]
    st.dataframe(
        batter_display[columns],
        hide_index=True,
        width="stretch",
        column_config={
            "Lineup Spot":st.column_config.NumberColumn("Order",format="%.0f"),
            "Batter":st.column_config.TextColumn("Batter"),
            "Hand":st.column_config.TextColumn("Bats"),
            "K% vs Pitcher":st.column_config.NumberColumn(f"K% vs {pitcher_hand or 'Pitcher'}",format="%.1f%%"),
            "H/PA vs Pitcher":st.column_config.NumberColumn(f"H/PA vs {pitcher_hand or 'Pitcher'}",format="%.1f%%"),
            "PA":st.column_config.NumberColumn("Split PA",format="%.0f"),
            "Risk":st.column_config.TextColumn("K Risk"),
            "Split Available":st.column_config.TextColumn("Data"),
        },
    )
'''
text = replace_once(text, old, new, "app batter box")
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Daily UI: refresh lineups and expose audit fields.
# ---------------------------------------------------------------------------
path = Path("pages/5_Daily_Projection_Run.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '    attach_pregame_weather,\n',
    '    attach_pregame_weather,\n    refresh_pregame_lineups,\n',
    "daily page lineup import",
)
text = replace_once(
    text,
    '    refreshed = fill_missing_pregame_paths(frame)\n    weather_refreshed = attach_pregame_weather(frame, announced)\n    save_log(frame)\n',
    '    refreshed = fill_missing_pregame_paths(frame)\n    weather_refreshed = attach_pregame_weather(frame, announced)\n    lineup_refreshed = refresh_pregame_lineups(frame, announced)\n    save_log(frame)\n',
    "daily page lineup refresh",
)
text = replace_once(
    text,
    '    return slate, len(new_rows), skipped + refreshed + weather_refreshed, history_only, errors\n',
    '    return slate, len(new_rows), skipped + refreshed + weather_refreshed + lineup_refreshed, history_only, errors\n',
    "daily page refresh count",
)
text = replace_once(
    text,
    '        "Matchup batters": int(_num(row, "matchup_batters") or 0),\n',
    '        "Matchup batters": int(_num(row, "matchup_batters") or 0),\n        "Lineup source": row.get("lineup_source", "ACTIVE_ROSTER"),\n        "Confirmed lineup hitters": int(_num(row, "lineup_batters") or 0),\n        "Lineup projection delta": _num(row, "lineup_projection_delta"),\n',
    "daily rationale lineup facts",
)
text = text.replace(
    '"Existing game/pitcher snapshots are not overwritten after capture."',
    '"Existing game/pitcher snapshots stay frozen after first pitch; while still pregame, a roster-fallback row may upgrade once MLB posts a confirmed batting order."',
    1,
)
text = replace_once(
    text,
    '    c1, c2, c3, c4, c5 = st.columns(5)\n',
    '    c1, c2, c3, c4, c5, c6 = st.columns(6)\n',
    "daily metrics columns",
)
text = replace_once(
    text,
    '    c5.metric("Errors", len(errors))\n\n    if not slate.empty:\n',
    '    c5.metric("Errors", len(errors))\n    confirmed_lineups = int(slate.get("lineup_source", pd.Series(index=slate.index, dtype=str)).astype(str).eq("CONFIRMED_LINEUP").sum()) if not slate.empty else 0\n    c6.metric("Confirmed lineups", confirmed_lineups)\n\n    if not slate.empty:\n',
    "daily confirmed metric",
)
text = replace_once(
    text,
    '            "player", "weather_icon", "weather_delay_risk", "weather_precip_probability", "team", "opponent", "projection", "k_range_low", "k_range_high",\n',
    '            "player", "weather_icon", "weather_delay_risk", "weather_precip_probability", "lineup_source", "lineup_batters", "lineup_projection_delta", "team", "opponent", "projection", "k_range_low", "k_range_high",\n',
    "daily display lineup cols",
)
text = replace_once(
    text,
    '                "weather_precip_probability": "Rain %",\n',
    '                "weather_precip_probability": "Rain %",\n                "lineup_source": "Lineup Source",\n                "lineup_batters": "Lineup Hitters",\n                "lineup_projection_delta": "K Δ from Lineup",\n',
    "daily display lineup names",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Projection History: add lineup-source audit to measure the feature over time.
# ---------------------------------------------------------------------------
path = Path("pages/4_Projection_History.py")
text = path.read_text(encoding="utf-8")
anchor = 'st.divider()\nst.subheader("🚦 Walk-forward Top 5 model health")\n'
block = '''st.divider()
st.subheader("🧾 Lineup input audit")
st.caption("Confirmed-lineup and active-roster rows stay separately tagged so we can measure whether posted batting orders improve the baseball forecast. Pregame upgrades also retain the old K projection and the lineup-driven delta.")
if "lineup_source" not in df.columns:
    st.info("Lineup-source tracking begins with app version 3.6.0; older rows remain untagged.")
else:
    lineup_audit = df.copy()
    lineup_audit["lineup_source"] = lineup_audit["lineup_source"].fillna("LEGACY/UNKNOWN").astype(str)
    lineup_audit["k_abs_error"] = (pd.to_numeric(lineup_audit.get("actual_strikeouts"), errors="coerce") - pd.to_numeric(lineup_audit.get("projection"), errors="coerce")).abs()
    lineup_audit["hits_abs_error"] = (pd.to_numeric(lineup_audit.get("actual_hits_allowed"), errors="coerce") - pd.to_numeric(lineup_audit.get("hits_projection"), errors="coerce")).abs()
    audit_rows = []
    for source, group in lineup_audit.groupby("lineup_source", dropna=False):
        resolved_k = group["k_abs_error"].dropna()
        resolved_h = group["hits_abs_error"].dropna()
        deltas = pd.to_numeric(group.get("lineup_projection_delta"), errors="coerce").dropna() if "lineup_projection_delta" in group.columns else pd.Series(dtype=float)
        audit_rows.append({
            "Lineup Source": source,
            "Snapshots": int(len(group)),
            "Resolved K": int(len(resolved_k)),
            "K MAE": None if resolved_k.empty else float(resolved_k.mean()),
            "Resolved Hits": int(len(resolved_h)),
            "Hits MAE": None if resolved_h.empty else float(resolved_h.mean()),
            "Pregame Upgrades": int(len(deltas)),
            "Avg K Projection Delta": None if deltas.empty else float(deltas.mean()),
        })
    audit = pd.DataFrame(audit_rows)
    st.dataframe(audit, hide_index=True, width="stretch")

'''
text = replace_once(text, anchor, block + anchor, "history lineup audit")
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Regression tests.
# ---------------------------------------------------------------------------
Path("tests/test_confirmed_lineups.py").write_text('''from __future__ import annotations\n\nimport pandas as pd\n\nfrom engine.lineup_context import LINEUP_ACTIVE_ROSTER, LINEUP_CONFIRMED, get_confirmed_lineup, lineup_fingerprint\nfrom engine.opposing_batters import LEAGUE_HIT_RATE, LEAGUE_K_RATE, matchup_summary\n\n\nclass FakeResponse:\n    def __init__(self, payload):\n        self._payload = payload\n    def raise_for_status(self):\n        return None\n    def json(self):\n        return self._payload\n\n\nclass FakeSession:\n    def __init__(self, payload):\n        self.payload = payload\n    def get(self, *args, **kwargs):\n        return FakeResponse(self.payload)\n\n\ndef test_confirmed_lineup_parser_keeps_batting_order():\n    ids = list(range(101, 110))\n    payload = {\n        "teams": {\n            "away": {"team": {"id": 142}, "battingOrder": ids},\n            "home": {"team": {"id": 139}, "battingOrder": list(range(201, 210))},\n        }\n    }\n    ctx = get_confirmed_lineup(999, 142, session=FakeSession(payload))\n    assert ctx.source == LINEUP_CONFIRMED\n    assert ctx.confirmed is True\n    assert ctx.player_ids == tuple(ids)\n    assert ctx.spots[0] == (101, 1)\n    assert ctx.spots[-1] == (109, 9)\n    assert ctx.fingerprint == lineup_fingerprint(tuple(ids))\n\n\ndef test_incomplete_lineup_stays_roster_fallback():\n    payload = {"teams": {"away": {"team": {"id": 142}, "battingOrder": [1, 2, 3]}}}\n    ctx = get_confirmed_lineup(999, 142, session=FakeSession(payload))\n    assert ctx.source == LINEUP_ACTIVE_ROSTER\n    assert ctx.confirmed is False\n    assert ctx.player_ids == ()\n\n\ndef test_confirmed_summary_uses_all_hitters_with_split_shrinkage_and_contact():\n    batters = pd.DataFrame({\n        "Batter": [f"B{i}" for i in range(9)],\n        "K% vs Pitcher": [0.40] + [0.20] * 8,\n        "H/PA vs Pitcher": [0.10] + [0.25] * 8,\n        "PA": [1000.0] + [20.0] * 8,\n        "Risk": ["HIGH"] + ["NORMAL"] * 8,\n    })\n    active = matchup_summary(batters, confirmed_lineup=False)\n    confirmed = matchup_summary(batters, confirmed_lineup=True)\n    assert active["k_rate"] > confirmed["k_rate"]\n    assert confirmed["k_rate"] > LEAGUE_K_RATE * 0.8\n    assert 0.12 <= confirmed["hit_rate"] <= 0.36\n    assert confirmed["hit_rate"] != LEAGUE_HIT_RATE\n''', encoding="utf-8")

Path("tests/test_lineup_integration_contract.py").write_text('''from pathlib import Path\n\n\ndef test_daily_runner_logs_and_refreshes_confirmed_lineups():\n    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")\n    compile(source, "automation/daily_projection_runner.py", "exec")\n    assert "get_confirmed_lineup" in source\n    assert '"lineup_source"' in source\n    assert '"lineup_hash"' in source\n    assert '"lineup_projection_delta"' in source\n    assert "refresh_pregame_lineups" in source\n    assert "row_is_pregame" in source\n    assert 'opponent_hit_rate=float(matchup.get("hit_rate", .235))' in source\n\n\ndef test_projection_page_prefers_confirmed_order_and_shows_contact_profile():\n    source = Path("streamlit_app.py").read_text(encoding="utf-8")\n    compile(source, "streamlit_app.py", "exec")\n    assert "get_confirmed_lineup(game.game_pk" in source\n    assert "CONFIRMED BATTING ORDER" in source\n    assert "ACTIVE ROSTER FALLBACK" in source\n    assert '"Lineup Spot"' in source\n    assert '"H/PA vs Pitcher"' in source\n    assert "opponent_hit_rate=float(opponent_matchup.get" in source\n\n\ndef test_history_exposes_lineup_audit():\n    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")\n    compile(source, "pages/4_Projection_History.py", "exec")\n    assert "Lineup input audit" in source\n    assert "Avg K Projection Delta" in source\n''', encoding="utf-8")

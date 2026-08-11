from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"{label} anchor not found")
    return text.replace(old, new, 1)


# Bet Tracker: color the Result text.
path = Path("pages/2_Bet_Tracker.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "    projection_for_market,\n)",
    "    projection_for_market,\n    result_cell_css,\n)",
    "tracker result color import",
)
text = replace_once(
    text,
    'st.dataframe(view, hide_index=True, use_container_width=True)\n',
    'styled_view = view.style.map(result_cell_css, subset=["Result"])\nst.dataframe(styled_view, hide_index=True, use_container_width=True)\n',
    "tracker styled dataframe",
)
path.write_text(text, encoding="utf-8")


# Top Plays: quick-add each ranked leg to the persistent Bet Tracker.
path = Path("pages/6_Top_Plays.py")
text = path.read_text(encoding="utf-8")
text = replace_once(text, "from datetime import datetime\n", "from datetime import datetime\nfrom pathlib import Path\n", "top plays pathlib import")
text = replace_once(
    text,
    "from engine.bet_lean import projection_side\n",
    "from engine.bet_lean import projection_side\nfrom engine.bet_tracker import make_bet_record, projection_for_market\n",
    "top plays bet tracker import",
)
text = replace_once(
    text,
    "from navigation import render_sidebar\n",
    "from navigation import render_sidebar\nfrom training.bet_storage import append_bet\n",
    "top plays storage import",
)
text = replace_once(
    text,
    'MARKETS = "pitcher_strikeouts,pitcher_strikeouts_alternate,pitcher_outs,pitcher_outs_alternate,pitcher_hits_allowed,pitcher_hits_allowed_alternate"\n',
    'MARKETS = "pitcher_strikeouts,pitcher_strikeouts_alternate,pitcher_outs,pitcher_outs_alternate,pitcher_hits_allowed,pitcher_hits_allowed_alternate"\nROOT = Path(__file__).resolve().parents[1]\nBET_LOG = ROOT / "data" / "bet_log.csv"\n',
    "top plays bet log",
)
quick_add = '''st.caption("Ranking requires positive no-vig edge and minimum model/data-quality thresholds. One best leg per pitcher/market is kept so duplicate alternate lines do not crowd out the board.")

st.markdown("#### Add a Top Play to Bet Tracker")
quick_stake = st.number_input("Quick-add stake", min_value=0.0, value=1.0, step=0.5, key="top_plays_quick_stake")
button_cols = st.columns(len(plays))
for button_idx, (_, play_row) in enumerate(plays.iterrows()):
    snapshot = find_snapshot(history, play_row)
    snapshot_dict = snapshot.to_dict() if snapshot is not None else None
    projection_value = projection_for_market(snapshot_dict, play_row.get("Market")) if snapshot_dict else None
    with button_cols[button_idx]:
        st.caption(f"#{int(play_row['Rank'])} {play_row['Pitcher']} · {play_row['Side']} {float(play_row['Line']):g}")
        if st.button("➕ Add as bet", key=f"add_top_play_{int(play_row['Rank'])}", use_container_width=True):
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
                st.success("Added")
            except Exception as exc:
                st.error(f"Could not add bet: {exc}")
'''
text = replace_once(
    text,
    'st.caption("Ranking requires positive no-vig edge and minimum model/data-quality thresholds. One best leg per pitcher/market is kept so duplicate alternate lines do not crowd out the board.")\n',
    quick_add,
    "top plays quick add block",
)
path.write_text(text, encoding="utf-8")


# Main Projection: quick-add each actionable recommendation using the best posted price at its exact line.
path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from engine.bet_lean import aligned_bet_lean\n",
    "from engine.bet_lean import aligned_bet_lean\nfrom engine.bet_tracker import make_bet_record\nfrom training.bet_storage import append_bet\n",
    "main bet tracker imports",
)
text = replace_once(
    text,
    "APP_DIR = Path(__file__).resolve().parent\n",
    "APP_DIR = Path(__file__).resolve().parent\nBET_LOG = APP_DIR / \"data\" / \"bet_log.csv\"\n",
    "main bet log",
)
helper = '''def implied_prob(price):
    try:
        p=float(price); return 100/(p+100) if p>0 else abs(p)/(abs(p)+100)
    except Exception:return None

def best_market_offer(odds_rows, market_keys, line, side):
    wanted=str(side).lower(); candidates=[]
    for row in odds_rows:
        if row.get("market") not in set(market_keys): continue
        if str(row.get("name","")).lower()!=wanted: continue
        try:
            if abs(float(row.get("point"))-float(line))>1e-9: continue
            float(row.get("price"))
        except Exception: continue
        candidates.append(row)
    return max(candidates,key=lambda row:float(row.get("price"))) if candidates else None

def render_add_bet_button(container,reco,market_label,market_keys,projection_mean,stake,game,game_date,odds_rows,confidence,key):
    side=str(reco.get("side","PASS"))
    offer=best_market_offer(odds_rows,market_keys,reco.get("line"),side) if side in {"OVER","UNDER"} else None
    with container:
        if offer is not None:
            st.caption(f"Best posted: {offer.get('book','')} {float(offer.get('price')):+.0f}")
        else:
            st.caption("No actionable posted price" if side=="PASS" else "Matching sportsbook price unavailable")
        clicked=st.button(f"➕ Add {market_label}",key=key,use_container_width=True,disabled=(side=="PASS" or offer is None))
        if clicked:
            try:
                price=float(offer.get("price")); implied=implied_prob(price); model=float(reco.get("model"))
                record=make_bet_record(
                    player=game.pitcher_name,
                    market=market_label,
                    game_date=game_date,
                    line=float(reco.get("line")),
                    side=side,
                    american_odds=price,
                    stake=float(stake),
                    book=str(offer.get("book","")),
                    projection=float(projection_mean),
                    model_probability=model,
                    implied_probability=implied,
                    edge=None if implied is None else model-implied,
                    confidence=confidence,
                    game_pk=game.game_pk,
                    pitcher_id=game.pitcher_id,
                )
                append_bet(BET_LOG,record,st.secrets)
                st.success("Added to Bet Tracker")
            except Exception as exc:
                st.error(f"Could not add bet: {exc}")
'''
old_helper = '''def implied_prob(price):
    try:
        p=float(price); return 100/(p+100) if p>0 else abs(p)/(abs(p)+100)
    except Exception:return None
'''
text = replace_once(text, old_helper, helper, "main quick add helper")

old_price_loop = '''        chosen=[r for r in rows if abs(float(r.get("point"))-line)<1e-9]
        for r in chosen:
            name=str(r.get("name","")).lower()
            if name=="over": over_price=r.get("price")
            elif name=="under": under_price=r.get("price")
'''
new_price_loop = '''        chosen=[r for r in rows if abs(float(r.get("point"))-line)<1e-9]
        over_offers=[r for r in chosen if str(r.get("name","")).lower()=="over" and r.get("price") is not None]
        under_offers=[r for r in chosen if str(r.get("name","")).lower()=="under" and r.get("price") is not None]
        if over_offers: over_price=max(float(r.get("price")) for r in over_offers)
        if under_offers: under_price=max(float(r.get("price")) for r in under_offers)
'''
text = replace_once(text, old_price_loop, new_price_loop, "main recommendation best prices")

old_hit_prices = '''hit_over_price=next((r.get("price") for r in hit_rows if abs(float(r.get("point"))-hit_line)<1e-9 and str(r.get("name","")).lower()=="over"),None)
hit_under_price=next((r.get("price") for r in hit_rows if abs(float(r.get("point"))-hit_line)<1e-9 and str(r.get("name","")).lower()=="under"),None)
'''
new_hit_prices = '''hit_over_offer=best_market_offer(odds_rows,{"pitcher_hits_allowed","pitcher_hits_allowed_alternate"},hit_line,"OVER")
hit_under_offer=best_market_offer(odds_rows,{"pitcher_hits_allowed","pitcher_hits_allowed_alternate"},hit_line,"UNDER")
hit_over_price=hit_over_offer.get("price") if hit_over_offer else None
hit_under_price=hit_under_offer.get("price") if hit_under_offer else None
'''
text = replace_once(text, old_hit_prices, new_hit_prices, "main hit best prices")

quick_main = '''render_reco(h2,hit_reco)
st.markdown("#### Add recommendation to Bet Tracker")
quick_add_stake=st.number_input("Quick-add stake",min_value=0.0,value=1.0,step=0.5,key=f"projection_quick_stake_{game.key}")
add1,add2,add3=st.columns(3)
render_add_bet_button(add1,k_reco,"Strikeouts",{"pitcher_strikeouts","pitcher_strikeouts_alternate"},proj.mean_k,quick_add_stake,game,selected_date.isoformat(),odds_rows,proj.confidence,f"add_k_{game.key}")
render_add_bet_button(add2,out_reco,"Total Outs",{"pitcher_outs","pitcher_outs_alternate"},proj.mean_outs,quick_add_stake,game,selected_date.isoformat(),odds_rows,proj.confidence,f"add_outs_{game.key}")
render_add_bet_button(add3,hit_reco,"Hits Allowed",{"pitcher_hits_allowed","pitcher_hits_allowed_alternate"},hits_proj.ensemble_mean,quick_add_stake,game,selected_date.isoformat(),odds_rows,proj.confidence,f"add_hits_{game.key}")
'''
text = replace_once(text, "render_reco(h2,hit_reco)\n", quick_main, "main quick add buttons")
path.write_text(text, encoding="utf-8")

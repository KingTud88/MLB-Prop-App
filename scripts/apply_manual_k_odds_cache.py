from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "streamlit_app.py"
DAILY = ROOT / "pages" / "5_Daily_Projection_Run.py"
TOP = ROOT / "pages" / "6_Top_Plays.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"patch anchor missing: {label}")
    return text.replace(old, new, 1)


main = MAIN.read_text()
main = replace_once(
    main,
    "from engine.alt_k import best_alt_k\n",
    "from engine.alt_k import best_alt_k\nfrom engine.odds_snapshot import load_pitcher_strikeout_odds\n",
    "main odds snapshot import",
)
old_block = '''odds_events,odds_err=get_odds_events(); odds_event_id=find_odds_event(odds_events,game)\nodds_payload_key=f"projection_live_odds:{game.key}"\nodds_quota_key=f"projection_live_odds_quota:{game.key}"\nodds_payload=st.session_state.get(odds_payload_key,{})\nif odds_event_id:\n    with st.sidebar:\n        st.markdown("#### 💳 Odds API Credit Saver")\n        st.caption("Paid odds are OFF by default. Main Strikeouts + Outs + Hits only; one US region; up to 3 credits when you press load. Alternate markets stay off.")\n        load_live_odds=st.button("LOAD LIVE ODDS · ≤3 credits",key=f"load_live_odds:{game.key}",use_container_width=True)\n    if load_live_odds:\n        loaded_payload,prop_err,quota=get_event_props(odds_event_id)\n        if loaded_payload:\n            odds_payload=loaded_payload\n            st.session_state[odds_payload_key]=loaded_payload\n        if quota:\n            st.session_state[odds_quota_key]=quota\n        odds_err=prop_err if prop_err else odds_err\nelse:\n    odds_payload=[]\n    odds_err=odds_err if odds_err else "No matching Odds API event found for this MLB game."\nquota_view=st.session_state.get(odds_quota_key,{})\nif quota_view:\n    with st.sidebar:\n        st.caption(f"Last paid load: {quota_view.get('last','—')} credit(s) · {quota_view.get('remaining','—')} remaining · {quota_view.get('used','—')} used.")\nif not odds_payload and not odds_err:\n    odds_err="Live sportsbook prices not loaded. Credit Saver is ON; the baseball projection does not need sportsbook data."\nodds_rows=extract_player_odds(odds_payload,game.pitcher_name)'''
new_block = '''odds_rows=load_pitcher_strikeout_odds(game.pitcher_name,selected_date.isoformat())\nodds_err=("" if odds_rows else "No saved strikeout odds for this pitcher/slate yet. Use the paid manual button on Daily Projection Run; this page never calls the Odds API.")'''
main = replace_once(main, old_block, new_block, "main paid odds block")
MAIN.write_text(main)


daily = DAILY.read_text()
daily = replace_once(
    daily,
    "from engine.outs_calibration import calibrate_outs_blend\n",
    "from engine.outs_calibration import calibrate_outs_blend\nfrom engine.odds_snapshot import refresh_strikeout_snapshot, resolve_api_key\n",
    "daily odds snapshot import",
)
anchor = '''if st.button("⚾ RUN ALL TODAY'S PITCHERS", type="primary", use_container_width=True):\n'''
insert = '''st.markdown("### 💳 Paid strikeout lines")\nst.caption("Manual only. This button is the ONLY paid Odds API path and requests pitcher_strikeouts only. The saved snapshot is reused by Main Projections without another API call.")\nif st.button("💳 LOAD STRIKEOUT LINES · PAID API", use_container_width=True, key="daily_paid_k_odds"):\n    api_key=resolve_api_key(st.secrets)\n    with st.spinner("Loading today's main pitcher strikeout lines once and saving the snapshot..."):\n        odds_snapshot,quota,odds_error=refresh_strikeout_snapshot(api_key,slate_date.isoformat())\n    if odds_error:\n        st.error(odds_error)\n    else:\n        pitchers=int(odds_snapshot.get("pitcher",pd.Series(dtype=str)).nunique()) if not odds_snapshot.empty else 0\n        st.success(f"Saved {len(odds_snapshot)} strikeout offers for {pitchers} pitchers. Main Projections will reuse this snapshot for free.")\n        if quota:\n            st.caption(f"Last paid request: {quota.get('last','—')} credit(s) · {quota.get('remaining','—')} remaining · {quota.get('used','—')} used.")\n\n'''
daily = replace_once(daily, anchor, insert + anchor, "daily manual odds button")
DAILY.write_text(daily)


top = TOP.read_text()
top = replace_once(
    top,
    "api_key = secret()\n",
    "api_key = None  # Paid Odds API access is intentionally restricted to Daily Projection Run.\n",
    "top plays paid odds disable",
)
TOP.write_text(top)

print("patched Main Projections, Daily Projection Run, and Top Plays paid-odds ownership")

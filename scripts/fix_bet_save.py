from pathlib import Path

# Bet Tracker live-stat + ticket renderer patch. The live MLB game feed is the
# source of truth while a game is in progress; date-range stats remain a safe
# fallback for settled games or transient live-feed gaps.
page = Path("pages/2_Bet_Tracker.py")
s = page.read_text(encoding="utf-8")

if "# BET_TRACKER_LIVE_BOXSCORE_V1" not in s:
    live_helper = '''\n\n# BET_TRACKER_LIVE_BOXSCORE_V1\ndef _live_pitching_stats(game_pk: int | None, pitcher_id: int | None) -> dict | None:\n    \"\"\"Return the pitcher's current game pitching line from MLB's live boxscore.\"\"\"\n    if not game_pk or not pitcher_id:\n        return None\n    try:\n        r = requests.get(\n            f\"{MLB_LIVE_API}/game/{int(game_pk)}/feed/live\",\n            params=_fresh_params(),\n            headers=MLB_HEADERS,\n            timeout=10,\n        )\n        if not r.ok:\n            return None\n        teams = (((r.json().get(\"liveData\", {}) or {}).get(\"boxscore\", {}) or {}).get(\"teams\", {}) or {})\n        player_key = f\"ID{int(pitcher_id)}\"\n        for side in (\"away\", \"home\"):\n            players = ((teams.get(side, {}) or {}).get(\"players\", {}) or {})\n            player = players.get(player_key) or {}\n            pitching = ((player.get(\"stats\", {}) or {}).get(\"pitching\", {}) or {})\n            if pitching:\n                return pitching\n        return None\n    except Exception:\n        return None\n'''
    anchor = '\n\ndef _live_status(game_pk: int | None, fallback: str) -> tuple[str, bool]:\n'
    if anchor not in s:
        raise SystemExit("Live-status anchor not found")
    s = s.replace(anchor, live_helper + anchor, 1)

    old = '''    if not resolved_id:\n        return None, \"Pitcher could not be resolved\", final\n    stat = _date_pitching_stats(resolved_id, game_date)\n    if not stat:\n        return None, f\"No pitching stats posted yet · {status}\", final\n'''
    new = '''    if not resolved_id:\n        return None, \"Pitcher could not be resolved\", final\n    # MLB's date-range stats endpoint can lag during live games. Read the\n    # current boxscore first so in-progress K / H / outs update promptly, then\n    # fall back to the date-range endpoint for final or transient cases.\n    stat = _live_pitching_stats(found_game_pk, resolved_id)\n    if not stat:\n        stat = _date_pitching_stats(resolved_id, game_date)\n    if not stat:\n        return None, f\"No pitching stats posted yet · {status}\", final\n'''
    if old not in s:
        raise SystemExit("live_pitcher_prop stat-source anchor not found")
    s = s.replace(old, new, 1)

if "# BET_TRACKER_TICKET_CARDS_V1" not in s:
    s = s.replace(
        '            leg_grades = []\n            leg_summaries = []\n            statuses = []',
        '            leg_grades = []\n            leg_summaries = []\n            leg_details = []\n            statuses = []',
        1,
    )
    s = s.replace(
        '                leg_summaries.append(f"{leg_player} {leg_side} {leg_line:g} {leg_market} [{actual_text} · {leg_grade.result}]")',
        '''                leg_summaries.append(f"{leg_player} {leg_side} {leg_line:g} {leg_market} [{actual_text} · {leg_grade.result}]")
                leg_details.append({
                    "Player": leg_player,
                    "Market": leg_market,
                    "Side": leg_side,
                    "Line": leg_line,
                    "Actual": actual,
                    "Game Status": status,
                    "Result": leg_grade.result,
                    "Projection": _num(leg.get("projection")),
                    "Model Probability": _num(leg.get("model_probability")),
                })''',
        1,
    )
    s = s.replace(
        '                "Edge": None,\n            })',
        '                "Edge": None,\n                "_Legs": leg_details,\n            })',
        1,
    )
    straight_anchor = '''            "Projection": _num(row.get("projection")),
            "Model Probability": _num(row.get("model_probability")),
            "Edge": _num(row.get("edge")),
        })'''
    straight_new = '''            "Projection": _num(row.get("projection")),
            "Model Probability": _num(row.get("model_probability")),
            "Edge": _num(row.get("edge")),
            "_Legs": [{
                "Player": player,
                "Market": market,
                "Side": side,
                "Line": line,
                "Actual": actual,
                "Game Status": status,
                "Result": grade.result,
                "Projection": _num(row.get("projection")),
                "Model Probability": _num(row.get("model_probability")),
            }],
        })'''
    if straight_anchor not in s:
        raise SystemExit("Straight-bet result anchor not found")
    s = s.replace(straight_anchor, straight_new, 1)

    table_start = s.index('view = results.drop(columns=["_BetKey"], errors="ignore").copy()')
    download_start = s.index('st.download_button(', table_start)
    ticket_ui = '''# BET_TRACKER_TICKET_CARDS_V1
# The resolver above remains the source of truth. This presentation preserves
# each resolved leg so live progress is visible instead of flattened into one row.

def _ticket_icon(result: object) -> str:
    state = str(result or "").upper()
    if state == "WIN":
        return "✅"
    if state == "LOSS":
        return "❌"
    if state == "LIVE AHEAD":
        return "🟢"
    if state == "LIVE BEHIND":
        return "🟠"
    if state in {"PUSH", "PUSH LEG"}:
        return "🟡"
    return "⏳"


def _progress_value(actual: object, line: object) -> float:
    current = _num(actual)
    target = _num(line)
    if current is None or target is None or target <= 0:
        return 0.0
    return max(0.0, min(float(current) / float(target), 1.0))


st.caption("Open any ticket to see each pitcher leg, live stat progress, line, game status, projection, and current grade.")
for ticket_index, (_, ticket) in enumerate(results.iterrows()):
    ticket_result = str(ticket.get("Result", "PENDING"))
    ticket_pitcher = str(ticket.get("Pitcher", "Unknown"))
    ticket_date = str(ticket.get("Date", ""))
    ticket_market = str(ticket.get("Market", ""))
    label = f"{_ticket_icon(ticket_result)} {ticket_date} · {ticket_pitcher} · {ticket_market} · {ticket_result}"
    with st.expander(label, expanded=ticket_result in {"LIVE AHEAD", "LIVE BEHIND"}):
        h1, h2, h3, h4, h5 = st.columns(5)
        h1.metric("Book", str(ticket.get("Book", "") or "—"))
        stake_value = _num(ticket.get("Stake"))
        h2.metric("Stake", "—" if stake_value is None else f"{stake_value:.2f}u")
        h3.metric("Odds", str(ticket.get("Odds", "—")))
        profit_value = _num(ticket.get("Profit/Loss"))
        h4.metric("P/L", "—" if profit_value is None else f"{profit_value:+.2f}u")
        h5.metric("Ticket", ticket_result)

        legs = ticket.get("_Legs", [])
        if not isinstance(legs, list) or not legs:
            st.caption("No leg detail is available for this older ticket.")
        for leg_number, leg in enumerate(legs, start=1):
            player = str(leg.get("Player", "Unknown"))
            market = str(leg.get("Market", ""))
            side = str(leg.get("Side", ""))
            line = _num(leg.get("Line")) or 0.0
            actual = _num(leg.get("Actual"))
            leg_result = str(leg.get("Result", "PENDING"))
            status = str(leg.get("Game Status", "Pending"))
            projection = _num(leg.get("Projection"))
            model_probability = _num(leg.get("Model Probability"))
            side_color = "#49efb0" if side.upper() == "OVER" else "#ff4b4b"
            st.markdown(
                f'<div style="border:1px solid #294b6c;border-radius:10px;padding:10px 12px;margin:8px 0 5px">'
                f'<div style="font-size:1.05rem;font-weight:900">{leg_number}. {player}</div>'
                f'<div style="margin-top:2px">{market} · <span style="color:{side_color};font-weight:900">{side.upper()}</span> {line:g}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Current", "—" if actual is None else f"{actual:g}")
            p2.metric("Target line", f"{line:g}")
            p3.metric("Projection", "—" if projection is None else f"{projection:.2f}")
            p4.metric("Model %", "—" if model_probability is None else f"{model_probability:.1%}")
            st.progress(_progress_value(actual, line))
            if actual is None:
                progress_text = "Waiting for MLB pitching stats"
            elif side.upper() == "OVER":
                needed = max(0.0, line - actual)
                progress_text = f"{actual:g} current · {needed:g} to the listed line" if needed > 0 else f"{actual:g} current · above the listed line"
            else:
                room = line - actual
                progress_text = f"{actual:g} current · {max(0.0, room):g} below the listed line" if room > 0 else f"{actual:g} current · at/above the listed line"
            st.caption(f"{_ticket_icon(leg_result)} {leg_result} · {status} · {progress_text}")

        st.caption("Live progress comes from MLB pitching stats. Sportsbook prices and stakes remain tracking-only inputs and never feed the projection model.")

'''
    s = s[:table_start] + ticket_ui + s[download_start:]

page.write_text(s, encoding="utf-8")
print("Bet Tracker live boxscore + ticket cards patched.")

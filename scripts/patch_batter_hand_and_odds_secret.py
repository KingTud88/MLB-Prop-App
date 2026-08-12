# one-shot patch helper; remove after successful CI
from pathlib import Path

APP = Path("streamlit_app.py")
RUNNER = Path("automation/daily_projection_runner.py")
BATTERS = Path("engine/opposing_batters.py")
TEST = Path("tests/test_batter_hand_and_odds_secret.py")

app = APP.read_text(encoding="utf-8")
old = '''@st.cache_data(ttl=1800,show_spinner=False)\ndef get_pitcher_hand(pid):\n    try:\n        payload=MLBClient().get(f"people/{int(pid)}",{})\n        people=payload.get("people") or []\n        return str(((people[0].get("pitchingHand") or {}).get("code")) or "").upper() if people else ""\n    except Exception:\n        return ""\n'''
new = '''@st.cache_data(ttl=1800,show_spinner=False)\ndef get_pitcher_hand(pid):\n    try:\n        payload=MLBClient().get(f"people/{int(pid)}",{})\n        people=payload.get("people") or []\n        if not people:\n            return ""\n        # MLB Person uses `pitchHand`; retain the legacy key only as a defensive fallback.\n        hand=people[0].get("pitchHand") or people[0].get("pitchingHand") or {}\n        return str(hand.get("code") or "").upper()\n    except Exception:\n        return ""\n'''
if old not in app:
    raise SystemExit("streamlit pitcher-hand anchor not found")
app = app.replace(old, new, 1)

old = '''@st.cache_data(ttl=60,show_spinner=False)\ndef get_odds_events():\n    key=get_secret()\n    if not key:return [],"Odds API key not found in Streamlit secrets."\n    try:\n        r=requests.get(f"{ODDS_API}/sports/baseball_mlb/events",params={"apiKey":key},timeout=15); r.raise_for_status(); return r.json(),None\n    except Exception as e:return [],f"Odds API unavailable: {e}"\n\n@st.cache_data(ttl=60,show_spinner=False)\ndef get_event_props(event_id):\n    key=get_secret()\n    if not key:return [],"Odds API key not found in Streamlit secrets."\n    params={"apiKey":key,"regions":"us","markets":"pitcher_strikeouts,pitcher_strikeouts_alternate,pitcher_outs,pitcher_outs_alternate,pitcher_hits_allowed,pitcher_hits_allowed_alternate","oddsFormat":"american"}\n    try:\n        r=requests.get(f"{ODDS_API}/sports/baseball_mlb/events/{event_id}/odds",params=params,timeout=15); r.raise_for_status(); return r.json(),None\n    except Exception as e:return [],f"Odds API unavailable: {e}"\n'''
new = '''def safe_odds_error(exc):\n    response=getattr(exc,"response",None)\n    status=getattr(response,"status_code",None)\n    if status==401:\n        return "Odds API unavailable: authentication failed (401). Check or rotate the Odds API key in Streamlit secrets."\n    if status==403:\n        return "Odds API unavailable: request forbidden (403). Check the Odds API account/permissions."\n    if status==429:\n        return "Odds API unavailable: rate or credit limit reached (429)."\n    if status is not None:\n        return f"Odds API unavailable: HTTP {int(status)}."\n    return f"Odds API unavailable: {type(exc).__name__}."\n\n@st.cache_data(ttl=60,show_spinner=False)\ndef get_odds_events():\n    key=get_secret()\n    if not key:return [],"Odds API key not found in Streamlit secrets."\n    try:\n        r=requests.get(f"{ODDS_API}/sports/baseball_mlb/events",params={"apiKey":key},timeout=15); r.raise_for_status(); return r.json(),None\n    except requests.RequestException as e:return [],safe_odds_error(e)\n\n@st.cache_data(ttl=60,show_spinner=False)\ndef get_event_props(event_id):\n    key=get_secret()\n    if not key:return [],"Odds API key not found in Streamlit secrets."\n    params={"apiKey":key,"regions":"us","markets":"pitcher_strikeouts,pitcher_strikeouts_alternate,pitcher_outs,pitcher_outs_alternate,pitcher_hits_allowed,pitcher_hits_allowed_alternate","oddsFormat":"american"}\n    try:\n        r=requests.get(f"{ODDS_API}/sports/baseball_mlb/events/{event_id}/odds",params=params,timeout=15); r.raise_for_status(); return r.json(),None\n    except requests.RequestException as e:return [],safe_odds_error(e)\n'''
if old not in app:
    raise SystemExit("odds error anchor not found")
APP.write_text(app.replace(old, new, 1), encoding="utf-8")

runner = RUNNER.read_text(encoding="utf-8")
old = '''def pitcher_hand(pitcher_id: int) -> str:\n    try:\n        data = get_json(f"people/{int(pitcher_id)}", {})\n        people = data.get("people") or []\n        return str(((people[0].get("pitchingHand") or {}).get("code")) or "").upper() if people else ""\n    except (requests.RequestException, ValueError, TypeError, IndexError):\n        return ""\n'''
new = '''def pitcher_hand(pitcher_id: int) -> str:\n    try:\n        data = get_json(f"people/{int(pitcher_id)}", {})\n        people = data.get("people") or []\n        if not people:\n            return ""\n        hand = people[0].get("pitchHand") or people[0].get("pitchingHand") or {}\n        return str(hand.get("code") or "").upper()\n    except (requests.RequestException, ValueError, TypeError, IndexError):\n        return ""\n'''
if old not in runner:
    raise SystemExit("daily runner pitcher-hand anchor not found")
RUNNER.write_text(runner.replace(old, new, 1), encoding="utf-8")

batters = BATTERS.read_text(encoding="utf-8")
old = '''            for person in response.json().get("people", []):\n                pid = int(person.get("id"))\n                found = False\n                for block in person.get("stats", []):\n'''
new = '''            for person in response.json().get("people", []):\n                pid = int(person.get("id"))\n                person_bat_side = str(((person.get("batSide") or {}).get("code")) or handed.get(pid, ""))\n                found = False\n                for block in person.get("stats", []):\n'''
if old not in batters:
    raise SystemExit("batter person anchor not found")
batters = batters.replace(old, new, 1)
old = 'rows.append({"Batter": names.get(pid, person.get("fullName", "Unknown")), "Hand": handed.get(pid, ""), "K% vs Pitcher": rate, "PA": pa, "Risk": _risk(rate)})'
new = 'rows.append({"Batter": names.get(pid, person.get("fullName", "Unknown")), "Hand": person_bat_side, "K% vs Pitcher": rate, "PA": pa, "Risk": _risk(rate)})'
if old not in batters:
    raise SystemExit("batter hand row anchor not found")
BATTERS.write_text(batters.replace(old, new, 1), encoding="utf-8")

TEST.write_text('''from pathlib import Path\n\n\ndef test_pitcher_hand_uses_mlb_person_pitch_hand_key():\n    app = Path("streamlit_app.py").read_text(encoding="utf-8")\n    runner = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")\n    assert 'get("pitchHand")' in app\n    assert 'get("pitchHand")' in runner\n\n\ndef test_odds_errors_never_render_raw_exception_url_or_key():\n    app = Path("streamlit_app.py").read_text(encoding="utf-8")\n    assert 'safe_odds_error' in app\n    assert 'f"Odds API unavailable: {e}"' not in app\n    assert 'authentication failed (401)' in app\n\n\ndef test_batter_box_reads_bat_side_from_hydrated_person():\n    text = Path("engine/opposing_batters.py").read_text(encoding="utf-8")\n    assert 'person.get("batSide")' in text\n    assert '"Hand": person_bat_side' in text\n''', encoding="utf-8")

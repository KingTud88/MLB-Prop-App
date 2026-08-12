from pathlib import Path

# One-shot patch: route final-game reads through MLB's v1.1 live feed.
RUNNER = Path("automation/daily_projection_runner.py")
RESOLVER = Path("automation/resolve_projection_log.py")

runner = RUNNER.read_text(encoding="utf-8")
old_runner = '''def get_json(endpoint: str, params: dict) -> dict:\n    r = SESSION.get(f"{BASE}/{endpoint}", params=params, timeout=30)\n    r.raise_for_status()\n    data = r.json()\n    if not isinstance(data, dict):\n        raise ValueError("Unexpected MLB response")\n    return data\n'''
new_runner = '''LIVE_BASE = "https://statsapi.mlb.com/api/v1.1"\n\n\ndef get_json(endpoint: str, params: dict) -> dict:\n    # MLB's live-feed endpoint is the reliable source for final game boxscores.\n    # Keep v1 for schedule/people/stats calls, but transparently route game\n    # boxscore reads through v1.1 and return the shape our resolvers expect.\n    if endpoint.startswith("game/") and endpoint.endswith("/boxscore"):\n        live_endpoint = endpoint[:-len("boxscore")] + "feed/live"\n        r = SESSION.get(f"{LIVE_BASE}/{live_endpoint}", params=params, timeout=30)\n        r.raise_for_status()\n        live = r.json()\n        if not isinstance(live, dict):\n            raise ValueError("Unexpected MLB live-feed response")\n        return {\n            "gameData": live.get("gameData", {}),\n            "teams": live.get("liveData", {}).get("boxscore", {}).get("teams", {}),\n        }\n    base = LIVE_BASE if endpoint.startswith("game/") and endpoint.endswith("/feed/live") else BASE\n    r = SESSION.get(f"{base}/{endpoint}", params=params, timeout=30)\n    r.raise_for_status()\n    data = r.json()\n    if not isinstance(data, dict):\n        raise ValueError("Unexpected MLB response")\n    return data\n'''
if old_runner not in runner:
    raise SystemExit("daily runner get_json anchor not found")
RUNNER.write_text(runner.replace(old_runner, new_runner, 1), encoding="utf-8")

resolver = RESOLVER.read_text(encoding="utf-8")
old_resolver = '''def get_json(endpoint: str, params: dict | None = None) -> dict:\n    response = SESSION.get(f"{BASE}/{endpoint}", params=params or {}, timeout=30)\n    response.raise_for_status()\n    data = response.json()\n    if not isinstance(data, dict):\n        raise ValueError("Unexpected MLB response")\n    return data\n'''
new_resolver = '''LIVE_BASE = "https://statsapi.mlb.com/api/v1.1"\n\n\ndef get_json(endpoint: str, params: dict | None = None) -> dict:\n    if endpoint.startswith("game/") and endpoint.endswith("/boxscore"):\n        live_endpoint = endpoint[:-len("boxscore")] + "feed/live"\n        response = SESSION.get(f"{LIVE_BASE}/{live_endpoint}", params=params or {}, timeout=30)\n        response.raise_for_status()\n        live = response.json()\n        if not isinstance(live, dict):\n            raise ValueError("Unexpected MLB live-feed response")\n        return {\n            "gameData": live.get("gameData", {}),\n            "teams": live.get("liveData", {}).get("boxscore", {}).get("teams", {}),\n        }\n    base = LIVE_BASE if endpoint.startswith("game/") and endpoint.endswith("/feed/live") else BASE\n    response = SESSION.get(f"{base}/{endpoint}", params=params or {}, timeout=30)\n    response.raise_for_status()\n    data = response.json()\n    if not isinstance(data, dict):\n        raise ValueError("Unexpected MLB response")\n    return data\n'''
if old_resolver not in resolver:
    raise SystemExit("projection resolver get_json anchor not found")
RESOLVER.write_text(resolver.replace(old_resolver, new_resolver, 1), encoding="utf-8")

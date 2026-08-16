from pathlib import Path

p = Path("tools/patch_market_line_integrity.py")
s = p.read_text()
old = '''    anchor = ''' + "'''" + '''                \"line\": float(leg[\"Line\"]),
                \"side\": str(leg[\"Side\"]),''' + "'''" + '''
    if anchor not in s:
        raise SystemExit(\"Top Plays parlay leg anchor missing\")
    s = s.replace(anchor, ''' + "'''" + '''                \"line\": float(leg[\"Line\"]),
                \"line_source\": str(leg.get(\"Line Source\", \"\")),
                \"side\": str(leg[\"Side\"]),''' + "'''" + ''', 1)'''
new = '''    anchor = ''' + "'''" + '''                \"line\": float(leg[\"Line\"]), \"side\": str(leg[\"Side\"]), \"american_odds\": None,''' + "'''" + '''
    if anchor not in s:
        raise SystemExit(\"Top Plays parlay leg anchor missing\")
    s = s.replace(anchor, ''' + "'''" + '''                \"line\": float(leg[\"Line\"]), \"side\": str(leg[\"Side\"]), \"american_odds\": None,
                \"line_source\": str(leg.get(\"Line Source\", \"\")),''' + "'''" + ''', 1)'''
if old not in s:
    raise SystemExit("patch-script anchor block missing")
p.write_text(s.replace(old, new, 1))
print("patched patch-script anchor")

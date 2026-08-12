from pathlib import Path

page = Path("streamlit_app.py")
text = page.read_text(encoding="utf-8")
old = '    batter_display=opposing_batters.copy()\n    batter_display["Risk"]=batter_display["Risk"].map({"HIGH":"🔥 HIGH","ELEVATED":"⚠️ ELEVATED","NORMAL":"NORMAL"}).fillna(batter_display["Risk"])\n'
new = '    batter_display=opposing_batters.copy()\n    batter_display["K% vs Pitcher"]=pd.to_numeric(batter_display["K% vs Pitcher"],errors="coerce")*100.0\n    batter_display["Risk"]=batter_display["Risk"].map({"HIGH":"🔥 HIGH","ELEVATED":"⚠️ ELEVATED","NORMAL":"NORMAL"}).fillna(batter_display["Risk"])\n'
if old not in text:
    raise SystemExit("batter display anchor not found")
page.write_text(text.replace(old,new,1),encoding="utf-8")

test=Path("tests/test_projection_weather_batter_contract.py")
t=test.read_text(encoding="utf-8")
anchor='    assert "ELEVATED K hitters" in text\n'
replacement=anchor+'    assert \'*100.0\' in text\n'
if anchor not in t:
    raise SystemExit("test anchor not found")
test.write_text(t.replace(anchor,replacement,1),encoding="utf-8")

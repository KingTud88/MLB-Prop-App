from pathlib import Path

APP = Path("streamlit_app.py")
text = APP.read_text(encoding="utf-8")

old_head = '.game-weather-head{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:.26rem}'
new_head = '''/* WEATHER_CARD_HERO_V13 · large state-aware weather symbol */
.game-weather-head{
    display:grid;
    grid-template-columns:minmax(0,1fr) 100px;
    gap:1rem;
    align-items:start;
    margin-bottom:.26rem;
}'''
if old_head in text:
    text = text.replace(old_head, new_head, 1)
elif "WEATHER_CARD_HERO_V13" not in text:
    raise SystemExit("Could not find game-weather-head CSS anchor")

old_icon = '.game-weather-icon{font-size:2.55rem;line-height:1;filter:drop-shadow(0 3px 5px rgba(0,0,0,.30))}'
new_icon = '''.game-weather-icon{
    width:92px;
    height:92px;
    justify-self:end;
    display:flex;
    align-items:center;
    justify-content:center;
    border-radius:50%;
    font-size:3.55rem;
    line-height:1;
    border:1px solid rgba(91,119,146,.68);
    background:radial-gradient(circle at 35% 28%,rgba(30,67,103,.94),rgba(5,22,39,.98) 68%);
    box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 24px rgba(71,126,174,.16);
    filter:drop-shadow(0 3px 5px rgba(0,0,0,.28));
}
.weather-high .game-weather-icon{
    border-color:rgba(255,78,101,.82);
    background:radial-gradient(circle at 35% 28%,rgba(125,24,47,.96),rgba(35,7,18,.98) 70%);
    box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 28px rgba(236,22,56,.36);
}
.weather-elevated .game-weather-icon{
    border-color:rgba(255,209,102,.78);
    background:radial-gradient(circle at 35% 28%,rgba(108,77,14,.94),rgba(35,24,5,.98) 70%);
    box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 28px rgba(255,209,102,.24);
}
.weather-low .game-weather-icon{
    border-color:rgba(91,178,230,.74);
    background:radial-gradient(circle at 35% 28%,rgba(20,76,112,.94),rgba(5,24,39,.98) 70%);
    box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 26px rgba(91,178,230,.22);
}
.weather-none .game-weather-icon{
    border-color:rgba(50,229,141,.66);
    background:radial-gradient(circle at 35% 28%,rgba(16,88,62,.88),rgba(5,30,24,.98) 70%);
    box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 26px rgba(50,229,141,.20);
}
.weather-unknown .game-weather-icon{
    color:#9cb0c1;
    border-color:rgba(91,119,146,.55);
    background:radial-gradient(circle at 35% 28%,rgba(35,54,73,.88),rgba(7,20,34,.98) 70%);
}'''
if old_icon in text:
    text = text.replace(old_icon, new_icon, 1)
elif 'width:92px;\n    height:92px;\n    justify-self:end;' not in text:
    raise SystemExit("Could not find game-weather-icon CSS anchor")

old_mobile = '@media (max-width:620px){.game-weather-card{min-height:166px!important;padding:14px!important}.game-weather-grid{grid-template-columns:1fr}.game-weather-risk{font-size:1.85rem}}'
new_mobile = '@media (max-width:620px){.game-weather-card{min-height:166px!important;padding:14px!important}.game-weather-grid{grid-template-columns:1fr}.game-weather-risk{font-size:1.85rem}.game-weather-head{grid-template-columns:minmax(0,1fr) 76px}.game-weather-icon{width:72px;height:72px;font-size:2.75rem}}'
if old_mobile in text:
    text = text.replace(old_mobile, new_mobile, 1)

old_display = '_weather_icon=weather_risk.icon or ("✓" if weather_risk.available else "—")'
new_display = '_weather_icon=weather_risk.icon or ("☀️" if str(weather_risk.level or "").upper()=="NONE" else "✓" if weather_risk.available else "—")'
if old_display in text:
    text = text.replace(old_display, new_display, 1)
elif new_display not in text:
    raise SystemExit("Could not find weather display icon anchor")

APP.write_text(text, encoding="utf-8")
print("Applied Projection Summary weather-card hero v13")

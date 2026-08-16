from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"{label} anchor missing")
    return text.replace(old, new, 1)


# Presentation-only pass: make the existing Game Status weather signal the
# visual hero of the right-hand status rail. No weather thresholds or model
# behavior are changed.
p = Path("engine/ui_command_center.py")
s = p.read_text(encoding="utf-8")

css_old = '''        .cc-matchup-status {
            padding-left:1.05rem;
            border-left:1px solid rgba(76,104,132,.54);
        }
        .cc-matchup-status-label { color:var(--cc-green);font-family:var(--cc-ui-font);font-size:.86rem;font-weight:800;letter-spacing:.025em;text-transform:uppercase; }
        .cc-matchup-status-time { margin-top:.32rem;color:#fff;font-weight:900;font-size:1rem; }
        .cc-matchup-status-meta { margin-top:.28rem;color:#afc0cf;font-family:var(--cc-ui-font);font-size:.84rem; }
        .cc-weather-status-icon { display:inline-flex;align-items:center;justify-content:center;margin-left:.34rem;min-width:1.25rem;font-size:1rem;line-height:1;filter:drop-shadow(0 2px 3px rgba(0,0,0,.28)); }
        .cc-lock-pill {'''
css_new = '''        .cc-matchup-status {
            display:grid;
            grid-template-columns:minmax(0,1fr) 96px;
            gap:.85rem;
            align-items:center;
            min-height:96px;
            padding-left:1.05rem;
            border-left:1px solid rgba(76,104,132,.54);
        }
        .cc-matchup-status-copy { min-width:0; }
        .cc-matchup-status-label { color:var(--cc-green);font-family:var(--cc-ui-font);font-size:.86rem;font-weight:800;letter-spacing:.025em;text-transform:uppercase; }
        .cc-matchup-status-time { margin-top:.32rem;color:#fff;font-weight:900;font-size:1rem; }
        .cc-matchup-status-meta { margin-top:.28rem;color:#afc0cf;font-family:var(--cc-ui-font);font-size:.84rem; }
        .cc-weather-status-hero {
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
        .cc-weather-status-hero.weather-high {
            border-color:rgba(255,78,101,.82);
            background:radial-gradient(circle at 35% 28%,rgba(125,24,47,.96),rgba(35,7,18,.98) 70%);
            box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 28px rgba(236,22,56,.36);
        }
        .cc-weather-status-hero.weather-elevated {
            border-color:rgba(255,209,102,.78);
            background:radial-gradient(circle at 35% 28%,rgba(108,77,14,.94),rgba(35,24,5,.98) 70%);
            box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 28px rgba(255,209,102,.24);
        }
        .cc-weather-status-hero.weather-low {
            border-color:rgba(91,178,230,.74);
            background:radial-gradient(circle at 35% 28%,rgba(20,76,112,.94),rgba(5,24,39,.98) 70%);
            box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 26px rgba(91,178,230,.22);
        }
        .cc-weather-status-hero.weather-none {
            border-color:rgba(50,229,141,.66);
            background:radial-gradient(circle at 35% 28%,rgba(16,88,62,.88),rgba(5,30,24,.98) 70%);
            box-shadow:inset 0 0 0 5px rgba(255,255,255,.025),0 12px 24px rgba(0,0,0,.30),0 0 26px rgba(50,229,141,.20);
        }
        .cc-weather-status-hero.weather-unknown {
            color:#9cb0c1;
            border-color:rgba(91,119,146,.55);
            background:radial-gradient(circle at 35% 28%,rgba(35,54,73,.88),rgba(7,20,34,.98) 70%);
            font-family:var(--cc-ui-font);
            font-size:2.6rem;
            font-weight:900;
        }
        .cc-lock-pill {'''
s = replace_once(s, css_old, css_new, "game status weather hero css")

mobile_old = '''            .cc-matchup-strip { grid-template-columns:auto 1fr; }
            .cc-matchup-status { grid-column:1 / -1;border-left:0;border-top:1px solid rgba(76,104,132,.54);padding:.75rem 0 0; }
        }
        @media (max-width:620px) {
            .st-key-cc_hero_shell { text-align:center; }
            .cc-hero-fallback { width:140px;height:140px;font-size:2rem; }
            .cc-hero-sub { justify-content:center; }
            .cc-matchup-strip { grid-template-columns:1fr;text-align:center; }
            .cc-team-mark { margin:0 auto; }
            .cc-matchup-status { text-align:center; }
        }'''
mobile_new = '''            .cc-matchup-strip { grid-template-columns:auto 1fr; }
            .cc-matchup-status { grid-column:1 / -1;border-left:0;border-top:1px solid rgba(76,104,132,.54);padding:.75rem 0 0; }
        }
        @media (max-width:620px) {
            .st-key-cc_hero_shell { text-align:center; }
            .cc-hero-fallback { width:140px;height:140px;font-size:2rem; }
            .cc-hero-sub { justify-content:center; }
            .cc-matchup-strip { grid-template-columns:1fr;text-align:center; }
            .cc-team-mark { margin:0 auto; }
            .cc-matchup-status { grid-template-columns:1fr;text-align:center;gap:.7rem; }
            .cc-weather-status-hero { width:80px;height:80px;justify-self:center;font-size:3rem; }
        }'''
s = replace_once(s, mobile_old, mobile_new, "mobile game status layout")

sig_old = '''    locked: bool,
    weather_icon: str = "",
    team_id: int = 0,
) -> None:
    """Render the matchup strip without changing any projection state."""
    lock_class = "cc-lock-pill locked" if locked else "cc-lock-pill"
    lock_label = "🔒 Locked" if locked else "◇ Unlocked"
    weather = f'<span class="cc-weather-status-icon" aria-label="Weather delay risk">{_safe(weather_icon)}</span>' if weather_icon else ""
    logo = _team_logo_url(team_id)'''
sig_new = '''    locked: bool,
    weather_icon: str = "",
    weather_level: str = "UNKNOWN",
    team_id: int = 0,
) -> None:
    """Render the matchup strip without changing any projection state."""
    lock_class = "cc-lock-pill locked" if locked else "cc-lock-pill"
    lock_label = "🔒 Locked" if locked else "◇ Unlocked"
    level = str(weather_level or "UNKNOWN").upper()
    weather_class = {
        "HIGH": "weather-high",
        "ELEVATED": "weather-elevated",
        "LOW": "weather-low",
        "NONE": "weather-none",
    }.get(level, "weather-unknown")
    weather_symbol = str(weather_icon or "").strip() or {
        "HIGH": "⛈️",
        "ELEVATED": "🌩️",
        "LOW": "🌧️",
        "NONE": "☀️",
    }.get(level, "—")
    weather = f'<div class="cc-weather-status-hero {weather_class}" aria-label="Weather delay risk">{_safe(weather_symbol)}</div>'
    logo = _team_logo_url(team_id)'''
s = replace_once(s, sig_old, sig_new, "weather hero function signature")

markup_old = '''          <div class="cc-matchup-status">
            <div class="cc-matchup-status-label">Game Status{weather}</div>
            <div class="cc-matchup-status-time">◫ {_safe(_game_time_text(game_time))}</div>
            <div class="cc-matchup-status-meta">{_safe(status)} · {_safe(side)}</div>
            <div class="{lock_class}">{_safe(lock_label)}</div>
          </div>'''
markup_new = '''          <div class="cc-matchup-status">
            <div class="cc-matchup-status-copy">
              <div class="cc-matchup-status-label">Game Status</div>
              <div class="cc-matchup-status-time">◫ {_safe(_game_time_text(game_time))}</div>
              <div class="cc-matchup-status-meta">{_safe(status)} · {_safe(side)}</div>
              <div class="{lock_class}">{_safe(lock_label)}</div>
            </div>
            {weather}
          </div>'''
s = replace_once(s, markup_old, markup_new, "game status markup")

p.write_text(s, encoding="utf-8")

# Pass the already-computed display risk level into the strip so clear and
# unavailable states can render an honest, distinct hero symbol.
p = Path("streamlit_app.py")
s = p.read_text(encoding="utf-8")
call_old = '''    locked=locked,
    weather_icon=weather_risk.icon or "",
    team_id=TEAM_ID_BY_ABBR.get(game.team,0),
)'''
call_new = '''    locked=locked,
    weather_icon=weather_risk.icon or "",
    weather_level=_weather_level,
    team_id=TEAM_ID_BY_ABBR.get(game.team,0),
)'''
s = replace_once(s, call_old, call_new, "projection matchup weather level")
p.write_text(s, encoding="utf-8")

print("Applied large Game Status weather hero layout v12")

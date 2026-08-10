from __future__ import annotations

import hashlib
from datetime import date

import requests
import streamlit as st

LEGACY = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/f0b28d2a9f91cc145736eb2d3e0c1a72d3275f43/streamlit_app.py"
# Use the approved asset from the current repository so the hero mascot cannot disappear when the legacy engine is pinned.
ASSET_BASE = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets"

try:
    response = requests.get(LEGACY, timeout=20)
    response.raise_for_status()
    source = response.text
except requests.RequestException as exc:
    st.error(f"StrikeOut King 9000 source unavailable: {exc}")
    st.stop()

required = ["class MLBClient:", "def get_schedule(", "def get_pitcher_game_log(", "def calculate_projection(", "def over_probability("]
missing = [item for item in required if item not in source]
if missing:
    st.error("Legacy source validation failed before execution: " + ", ".join(missing))
    st.stop()

BRANDING_FIX_CSS = f"""
<style>
:root{{--sidebar-w:228px}}
[data-testid="stSidebar"]{{width:var(--sidebar-w)!important;min-width:var(--sidebar-w)!important}}
[data-testid="stSidebar"]>div:first-child{{width:var(--sidebar-w)!important}}
[data-testid="stSidebar"] .block-container{{padding:.9rem .72rem 1.2rem!important}}

/* Sidebar: approved wordmark treatment, never the mascot. */
.sok-sidebar-logo{{width:100%!important;height:104px!important;margin:0 0 .55rem!important;display:flex!important;align-items:center!important;justify-content:center!important;border:1px solid #35516d!important;border-radius:14px!important;background:linear-gradient(145deg,#0b203a,#07162b)!important;overflow:hidden!important;position:relative!important}}
.sok-sidebar-logo>*{{display:none!important}}
.sok-sidebar-title,.sok-sidebar-sub{{display:none!important}}
.sok-sidebar-logo::after{{content:"StrikeOut\\A King 9000";white-space:pre;text-align:center;font-family:"Brush Script MT","Segoe Script",cursive!important;font-weight:900;font-size:29px;line-height:.9;color:#fff;text-shadow:2px 2px 0 #132a48}}
.sok-sidebar-logo::before{{content:"♛";position:absolute;color:#e31837;font-size:18px;top:6px;left:50%;transform:translateX(-50%)}}

/* Hero is built as one deterministic flex row so Streamlit columns cannot squeeze it. */
.sok-hero{{display:flex!important;align-items:center!important;gap:22px!important;min-height:205px!important;width:100%!important;padding-top:4px!important}}
.sok-hero .sok-hero-mascot{{flex:0 0 205px!important;width:205px!important;height:190px!important;display:flex!important;align-items:center!important;justify-content:center!important}}
.sok-hero .sok-hero-mascot img{{width:190px!important;height:190px!important;object-fit:contain!important;display:block!important}}
.sok-hero .sok-hero-title{{flex:1 1 auto!important;min-width:0!important}}
.sok-title{{font-size:5rem!important;line-height:.82!important}}
.sok-hero-right{{flex:0 0 335px!important;display:flex!important;align-items:center!important;justify-content:flex-end!important;gap:18px!important}}
.sok-built-badge{{width:105px;height:126px;box-sizing:border-box;border:2px solid #dbe4ee;border-radius:15px;background:linear-gradient(145deg,#0b203a,#07172b);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#fff;font-family:Impact,"Arial Narrow",sans-serif;font-size:15px;line-height:1.02;letter-spacing:.04em;box-shadow:0 8px 18px rgba(0,0,0,.2),inset 0 0 0 3px rgba(227,24,55,.10)}}
.sok-built-badge .cle{{font-size:36px;color:#fff;text-shadow:2px 2px 0 #e31837;margin:4px 0}}
.sok-built-badge .stars{{color:#e31837;font-size:13px;letter-spacing:3px}}
.sok-status{{position:relative!important;margin-left:0!important;z-index:5!important;width:190px!important;box-sizing:border-box!important}}
.proj-card{{min-height:205px!important}}

/* Match the approved reference: the Projection Summary is a red tab, not a giant empty bordered box. */
.section-frame{{border:0!important;border-radius:0!important;padding:0!important;margin-top:1.15rem!important;background:transparent!important;box-shadow:none!important}}
.section-ribbon{{position:relative!important;z-index:5!important;margin:0 auto .72rem!important}}

@media(max-width:1150px){{
  .sok-hero{{gap:12px!important}}
  .sok-hero .sok-hero-mascot{{flex-basis:165px!important;width:165px!important}}
  .sok-hero .sok-hero-mascot img{{width:155px!important;height:155px!important}}
  .sok-title{{font-size:4.25rem!important}}
  .sok-hero-right{{flex-basis:300px!important;gap:10px!important}}
  .sok-built-badge{{width:90px;height:112px;font-size:13px}}
  .sok-built-badge .cle{{font-size:30px}}
  .sok-status{{width:180px!important}}
}}
@media(max-width:900px){{
  .sok-hero{{display:block!important;min-height:0!important}}
  .sok-hero .sok-hero-mascot{{width:180px!important;height:155px!important;margin:0 auto}}
  .sok-hero .sok-hero-mascot img{{width:155px!important;height:155px!important}}
  .sok-hero-title{{text-align:center!important}}
  .sok-title{{font-size:3.6rem!important}}
  .sok-hero-right{{justify-content:center!important;margin-top:16px!important}}
}}
</style>
"""
source = source.replace('st.markdown(r"""', 'st.markdown(BRANDING_FIX_CSS, unsafe_allow_html=True)\n\nst.markdown(r"""', 1)

# Locked sidebar: Odds API is merged into Projection and intentionally absent from navigation.
source = source.replace('<a href="/3_Odds_API">◎ &nbsp; Odds API</a>', '', 1)
source = source.replace(
    '<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>',
    '<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><a href="#distribution">♟ &nbsp; Distribution</a><a href="#form-workload">♟ &nbsp; Form &amp; Workload</a><a href="#model-card">▣ &nbsp; Model Card</a><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>',
    1,
)
source = source.replace(
    'if logo_path.exists():st.markdown(\'<div class="sok-sidebar-logo">\',unsafe_allow_html=True);st.image(str(logo_path),width=130);st.markdown(\'</div>\',unsafe_allow_html=True)',
    'st.markdown(\'<div class="sok-sidebar-logo"></div>\',unsafe_allow_html=True)',
    1,
)

# Replace the fragile Streamlit-column hero with a deterministic HTML hero matching the approved reference.
old_hero = '''st.markdown('<div class="sok-hero">',unsafe_allow_html=True);h1,h2,h3=st.columns([1.15,4.1,1.25])
with h1:
    if logo_path.exists():st.image(str(logo_path),width=175)
with h2:st.markdown('<div class="sok-title">STRIKEOUT<br><span class="red">KING 9000</span></div><div class="sok-ribbon">★ MLB PITCHER PROJECTION ENGINE ★ TWO-PATH ANALYTICS ★</div>',unsafe_allow_html=True)
with h3:
    pct=projection.data_quality;st.markdown(f'<div class="sok-status"><div class="head">DATA STATUS</div><div class="live">● {projection.confidence.upper()}</div><div class="quality">High confidence<br>Data quality {pct}/100</div><div class="bar"><span style="width:{pct}%"></span></div></div>',unsafe_allow_html=True)
st.markdown('</div>',unsafe_allow_html=True)'''
new_hero = """pct=projection.data_quality
st.markdown(f'''<div class="sok-hero">
  <div class="sok-hero-mascot"><img src="{ASSET_BASE}/strikeout_king_9000.png" alt="StrikeOut King 9000 mascot"></div>
  <div class="sok-hero-title"><div class="sok-title">STRIKEOUT<br><span class="red">KING 9000</span></div><div class="sok-ribbon">★ MLB PITCHER PROJECTION ENGINE ★ TWO-PATH ANALYTICS ★</div></div>
  <div class="sok-hero-right">
    <div class="sok-built-badge"><div>BUILT FOR</div><div class="cle">CLE</div><div>BASEBALL</div><div class="stars">★★★</div></div>
    <div class="sok-status"><div class="head">DATA STATUS</div><div class="live">● {projection.confidence.upper()}</div><div class="quality">High confidence<br>Data quality {pct}/100</div><div class="bar"><span style="width:{pct}%"></span></div></div>
  </div>
</div>''',unsafe_allow_html=True)"""
if old_hero not in source:
    st.error("Target hero block was not found; refusing to render a partial redesign.")
    st.stop()
source = source.replace(old_hero, new_hero, 1)

# Keep the two-path projection architecture: mathematical path + 25,000+ simulated games + 50/50 ensemble.
source = source.replace("def calculate_projection(", "def _sok_math_projection(", 1)
TWO_PATH = r'''
TWO_PATH_DETAILS = {}

def _sok_simulated_path(log, game, manual, simulations, seed):
    starts = log[log["games_started"] > 0].copy().tail(35)
    if starts.empty: starts = log.tail(20).copy()
    if starts.empty: raise ValueError("No historical starts available for simulation.")
    starts = starts.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    n = len(starts)
    ages = np.arange(n - 1, -1, -1, dtype=float)
    weights = np.exp(-0.08 * ages); weights /= weights.sum()
    idx = rng.choice(n, size=simulations, p=weights)
    bf = starts["batters_faced"].to_numpy(float)[idx]
    outs = starts["outs"].to_numpy(float)[idx]
    bf_sd = float(starts["batters_faced"].std(ddof=1)) if n > 2 else 3.5
    out_sd = float(starts["outs"].std(ddof=1)) if n > 2 else 3.0
    total_bf = float(starts["batters_faced"].sum())
    total_k = float(starts["strikeouts"].sum())
    alpha = max(0.224 * 120.0 + total_k, 0.5)
    beta = max(0.776 * 120.0 + total_bf - total_k, 0.5)
    rate = rng.beta(alpha, beta, size=simulations)
    opp = manual["opponent_k_pct"] / 22.4
    park = PARK_K_FACTOR.get(game.venue, 1.0)
    ump = manual["umpire_k_factor"]; weather = manual["weather_factor"]; rest = manual["rest_factor"]
    mean_pitch = weighted_mean(starts["pitches"], 5.0, 88.0)
    limit = float(np.clip(manual["pitch_limit"] / max(mean_pitch, 75.0), 0.78, 1.12))
    rate = np.clip(rate * opp * park * ump * weather, 0.02, 0.55)
    sampled_bf = np.clip(np.rint(bf + rng.normal(0, max(bf_sd * 0.35, 1.0), simulations)), 12, 35).astype(int)
    sampled_bf = np.clip(np.rint(sampled_bf * limit * rest), 8, 35).astype(int)
    k = rng.binomial(sampled_bf, rate).astype(float)
    o = np.clip(np.rint(outs + rng.normal(0, max(out_sd * 0.35, 1.0), simulations)), 3, 27)
    o = np.clip(np.rint(o * limit * rest), 3, 27).astype(float)
    return k, o

def calculate_projection(log, game, manual, simulations):
    simulations = max(int(simulations), 25000)
    math_projection = _sok_math_projection(log, game, manual, simulations)
    seed = int(hashlib.sha256(f"{game.key}|{date.today()}|{APP_VERSION}|two-path-v7".encode()).hexdigest()[:8], 16)
    sim_k, sim_outs = _sok_simulated_path(log, game, manual, simulations, seed)
    rng = np.random.default_rng(seed + 1)
    math_k = rng.choice(np.arange(len(math_projection.k_probs)), size=simulations, p=math_projection.k_probs)
    math_outs = rng.choice(np.arange(len(math_projection.outs_probs)), size=simulations, p=math_projection.outs_probs)
    use_sim = rng.random(simulations) < 0.5
    final_k = np.where(use_sim, sim_k, math_k).astype(float)
    final_outs = np.where(use_sim, sim_outs, math_outs).astype(float)
    k_probs = np.bincount(np.clip(np.rint(final_k).astype(int), 0, 18), minlength=19).astype(float); k_probs /= k_probs.sum()
    outs_probs = np.bincount(np.clip(np.rint(final_outs).astype(int), 0, 27), minlength=28).astype(float); outs_probs /= outs_probs.sum()
    TWO_PATH_DETAILS[game.key] = {
        "sim_k": float(sim_k.mean()), "sim_outs": float(sim_outs.mean()),
        "sim_k_sd": float(sim_k.std(ddof=1)), "sim_outs_sd": float(sim_outs.std(ddof=1)),
        "math_k": float(math_projection.mean_k), "math_outs": float(math_projection.mean_outs),
        "math_k_sd": float(math_projection.k_sd), "math_outs_sd": float(math_projection.outs_sd),
        "ensemble_k": float(final_k.mean()), "ensemble_outs": float(final_outs.mean()), "simulations": simulations,
    }
    st.session_state["two_path_last"] = TWO_PATH_DETAILS[game.key]
    return Projection(float(final_k.mean()), float(final_outs.mean()), float(final_k.std(ddof=1)), float(final_outs.std(ddof=1)), k_probs, outs_probs, final_k, final_outs, math_projection.confidence, math_projection.data_quality, math_projection.factors)
'''
source = source.replace("def over_probability(", TWO_PATH + "\ndef over_probability(", 1)
source = source.replace("use_container_width=True", "width=\"stretch\"")

compile(source, LEGACY, "exec")
exec(compile(source, LEGACY, "exec"), globals(), globals())

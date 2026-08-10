from __future__ import annotations

import hashlib
from datetime import date

import requests
import streamlit as st

LEGACY = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/f0b28d2a9f91cc145736eb2d3e0c1a72d3275f43/streamlit_app.py"
ASSET_BASE = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/f0b28d2a9f91cc145736eb2d3e0c1a72d3275f43/assets"

try:
    response = requests.get(LEGACY, timeout=20)
    response.raise_for_status()
    source = response.text
except requests.RequestException as exc:
    st.error(f"StrikeOut King 9000 source unavailable: {exc}")
    st.stop()

required = [
    "class MLBClient:",
    "def get_schedule(",
    "def get_pitcher_game_log(",
    "def calculate_projection(",
    "def over_probability(",
]
missing = [item for item in required if item not in source]
if missing:
    st.error("Legacy source validation failed before execution: " + ", ".join(missing))
    st.stop()

# Locked visual blueprint: mascot + large StrikeOut King 9000 hero, CLE badge,
# sidebar wordmark, search-first pitcher lock flow, and no standalone Odds API item.
BRANDING_FIX_CSS = f"""
<style>
:root{{--sidebar-w:228px}}
[data-testid="stSidebar"]{{width:var(--sidebar-w)!important;min-width:var(--sidebar-w)!important}}
[data-testid="stSidebar"]>div:first-child{{width:var(--sidebar-w)!important}}
[data-testid="stSidebar"] .block-container{{padding:.9rem .72rem 1.2rem!important}}

.sok-sidebar-logo{{
  width:100%!important;height:104px!important;margin:0 0 .55rem!important;
  display:flex!important;align-items:center!important;justify-content:center!important;
  border:1px solid #35516d!important;border-radius:14px!important;
  background:linear-gradient(145deg,#0b203a,#07162b)!important;
  overflow:hidden!important;
}}
.sok-sidebar-logo>*{{display:none!important}}
.sok-sidebar-title,.sok-sidebar-sub{{display:none!important}}
.sok-sidebar-logo::after{{
  content:"StrikeOut\\A King 9000";white-space:pre;text-align:center;
  font-family:"Brush Script MT","Segoe Script",cursive!important;font-weight:900;
  font-size:27px;line-height:.9;color:#fff;text-shadow:2px 2px 0 #132a48;
}}
.sok-sidebar-logo::before{{
  content:"♛";position:absolute;color:#e31837;font-size:18px;transform:translateY(-37px);
}}

.sok-hero{{grid-template-columns:190px 1fr 210px!important;gap:1rem!important;min-height:205px!important;align-items:center!important}}
.sok-hero>div:first-child{{
  min-height:190px!important;display:flex!important;align-items:center!important;justify-content:center!important;
  background:url('{ASSET_BASE}/strikeout_king_9000.svg') center/contain no-repeat!important;
}}
.sok-hero>div:first-child img{{width:175px!important;height:175px!important;object-fit:contain!important;visibility:hidden!important}}
.sok-title{{font-size:5rem!important;line-height:.82!important}}

/* Target reference: dedicated Built for CLE badge immediately before Data Status. */
.sok-status{{position:relative!important;margin-left:112px!important;z-index:5!important}}
.sok-status::before{{
  content:"BUILT FOR\\A CLE\\A BASEBALL";white-space:pre;position:absolute;left:-108px;top:0;
  width:92px;height:112px;box-sizing:border-box;display:flex;align-items:center;justify-content:center;
  text-align:center;padding:10px 6px;border:2px solid #dbe4ee;border-radius:15px;
  background:linear-gradient(145deg,#0b203a,#07172b);color:#fff;
  font-family:Impact,"Arial Narrow",sans-serif;font-size:14px;line-height:1.05;letter-spacing:.04em;
  text-shadow:0 1px 0 #000;box-shadow:0 8px 18px rgba(0,0,0,.2),inset 0 0 0 3px rgba(227,24,55,.10);
}}
.sok-status::after{{
  content:"★★★";position:absolute;left:-99px;top:80px;width:74px;text-align:center;
  color:#e31837;font-size:12px;letter-spacing:3px;z-index:6;
}}

/* Reference proportions for the four summary cards and lower tables. */
.section-frame{{margin-top:1rem!important}}
.proj-card{{min-height:205px!important}}

@media(min-width:1200px){{
  .sok-hero{{grid-template-columns:190px 1fr 210px!important;min-height:205px!important}}
  .sok-title{{font-size:5rem!important}}
}}
@media(max-width:1000px){{
  [data-testid="stSidebar"]{{width:200px!important;min-width:200px!important}}
  [data-testid="stSidebar"]>div:first-child{{width:200px!important}}
  .sok-status{{margin-left:0!important}}
  .sok-status::before,.sok-status::after{{display:none!important}}
}}
</style>
"""
source = source.replace(
    "st.markdown(r\"\"\"",
    "st.markdown(BRANDING_FIX_CSS, unsafe_allow_html=True)\n\nst.markdown(r\"\"\"",
    1,
)

# Remove the standalone Odds API navigation entry. Odds are already merged into
# the Projection command center/production page.
source = source.replace(
    '<a href="/3_Odds_API">◎ &nbsp; Odds API</a>',
    '<a href="#odds">◎ &nbsp; Production Odds</a>',
    1,
)
# Match the locked sidebar order from the reference design.
source = source.replace(
    '<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="#odds">◎ &nbsp; Production Odds</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>',
    '<div class="sok-nav"><a class="active" href="/">⌂ &nbsp; Projection</a><a href="#distribution">♟ &nbsp; Distribution</a><a href="#form-workload">♟ &nbsp; Form &amp; Workload</a><a href="#model-card">▣ &nbsp; Model Card</a><a href="/2_Bet_Tracker">♧ &nbsp; Bet Tracker</a><a href="/4_Projection_History">▣ &nbsp; Projection History</a><a href="/5_Daily_Projection_Run">▤ &nbsp; Daily Projection Run</a></div>',
    1,
)

# Make the sidebar logo itself the target wordmark instead of the mascot duplicate.
source = source.replace(
    'if logo_path.exists():st.markdown(\'<div class="sok-sidebar-logo">\',unsafe_allow_html=True);st.image(str(logo_path),width=130);st.markdown(\'</div>\',unsafe_allow_html=True)',
    'st.markdown(\'<div class="sok-sidebar-logo"></div>\',unsafe_allow_html=True)',
    1,
)

# Replace the hero rendering with the approved visual treatment. The mascot is supplied
# by CSS, so the legacy SVG is not rendered a second time.
old_hero = '''st.markdown('<div class="sok-hero">',unsafe_allow_html=True);h1,h2,h3=st.columns([1.15,4.1,1.25])
with h1:
    if logo_path.exists():st.image(str(logo_path),width=175)
with h2:st.markdown('<div class="sok-title">STRIKEOUT<br><span class="red">KING 9000</span></div><div class="sok-ribbon">★ MLB PITCHER PROJECTION ENGINE ★ TWO-PATH ANALYTICS ★</div>',unsafe_allow_html=True)
with h3:
    pct=projection.data_quality;st.markdown(f'<div class="sok-status"><div class="head">DATA STATUS</div><div class="live">● {projection.confidence.upper()}</div><div class="quality">High confidence<br>Data quality {pct}/100</div><div class="bar"><span style="width:{pct}%"></span></div></div>',unsafe_allow_html=True)
st.markdown('</div>',unsafe_allow_html=True)'''
new_hero = '''st.markdown('<div class="sok-hero">',unsafe_allow_html=True);h1,h2,h3=st.columns([1.15,4.1,1.25])
with h1:
    st.markdown('<div aria-label="StrikeOut King 9000 mascot"></div>',unsafe_allow_html=True)
with h2:st.markdown('<div class="sok-title">STRIKEOUT<br><span class="red">KING 9000</span></div><div class="sok-ribbon">★ MLB PITCHER PROJECTION ENGINE ★ TWO-PATH ANALYTICS ★</div>',unsafe_allow_html=True)
with h3:
    pct=projection.data_quality;st.markdown(f'<div class="sok-status"><div class="head">DATA STATUS</div><div class="live">● {projection.confidence.upper()}</div><div class="quality">High confidence<br>Data quality {pct}/100</div><div class="bar"><span style="width:{pct}%"></span></div></div>',unsafe_allow_html=True)
st.markdown('</div>',unsafe_allow_html=True)'''
if old_hero not in source:
    st.error("Target hero block was not found; refusing to render a partial redesign.")
    st.stop()
source = source.replace(old_hero, new_hero, 1)

# Keep the legacy math path intact under a new name, then inject the independent
# 25,000-game simulation path and a true 50/50 distributional ensemble.
source = source.replace("def calculate_projection(", "def _sok_math_projection(", 1)

TWO_PATH = r'''
TWO_PATH_DETAILS = {}


def _sok_simulated_path(log, game, manual, simulations, seed):
    starts = log[log["games_started"] > 0].copy().tail(35)
    if starts.empty:
        starts = log.tail(20).copy()
    if starts.empty:
        raise ValueError("No historical starts available for simulation.")

    starts = starts.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    n = len(starts)
    ages = np.arange(n - 1, -1, -1, dtype=float)
    weights = np.exp(-0.08 * ages)
    weights /= weights.sum()
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
    ump = manual["umpire_k_factor"]
    weather = manual["weather_factor"]
    rest = manual["rest_factor"]
    mean_pitch = weighted_mean(starts["pitches"], 5.0, 88.0)
    limit = float(np.clip(manual["pitch_limit"] / max(mean_pitch, 75.0), 0.78, 1.12))

    rate = np.clip(rate * opp * park * ump * weather, 0.02, 0.55)
    sampled_bf = np.clip(
        np.rint(bf + rng.normal(0, max(bf_sd * 0.35, 1.0), simulations)),
        12,
        35,
    ).astype(int)
    sampled_bf = np.clip(np.rint(sampled_bf * limit * rest), 8, 35).astype(int)

    k = rng.binomial(sampled_bf, rate).astype(float)
    o = np.clip(
        np.rint(outs + rng.normal(0, max(out_sd * 0.35, 1.0), simulations)),
        3,
        27,
    )
    o = np.clip(np.rint(o * limit * rest), 3, 27).astype(float)
    return k, o


def calculate_projection(log, game, manual, simulations):
    simulations = max(int(simulations), 25000)
    math_projection = _sok_math_projection(log, game, manual, simulations)

    seed = int(
        hashlib.sha256(
            f"{game.key}|{date.today()}|{APP_VERSION}|two-path-v7".encode()
        ).hexdigest()[:8],
        16,
    )
    sim_k, sim_outs = _sok_simulated_path(log, game, manual, simulations, seed)

    rng = np.random.default_rng(seed + 1)
    math_k = rng.choice(
        np.arange(len(math_projection.k_probs)),
        size=simulations,
        p=math_projection.k_probs,
    )
    math_outs = rng.choice(
        np.arange(len(math_projection.outs_probs)),
        size=simulations,
        p=math_projection.outs_probs,
    )

    use_sim = rng.random(simulations) < 0.5
    final_k = np.where(use_sim, sim_k, math_k).astype(float)
    final_outs = np.where(use_sim, sim_outs, math_outs).astype(float)

    k_probs = np.bincount(
        np.clip(np.rint(final_k).astype(int), 0, 18), minlength=19
    ).astype(float)
    k_probs /= k_probs.sum()
    outs_probs = np.bincount(
        np.clip(np.rint(final_outs).astype(int), 0, 27), minlength=28
    ).astype(float)
    outs_probs /= outs_probs.sum()

    TWO_PATH_DETAILS[game.key] = {
        "sim_k": float(sim_k.mean()),
        "sim_outs": float(sim_outs.mean()),
        "sim_k_sd": float(sim_k.std(ddof=1)),
        "sim_outs_sd": float(sim_outs.std(ddof=1)),
        "math_k": float(math_projection.mean_k),
        "math_outs": float(math_projection.mean_outs),
        "math_k_sd": float(math_projection.k_sd),
        "math_outs_sd": float(math_projection.outs_sd),
        "ensemble_k": float(final_k.mean()),
        "ensemble_outs": float(final_outs.mean()),
        "simulations": simulations,
    }
    st.session_state["two_path_last"] = TWO_PATH_DETAILS[game.key]

    return Projection(
        float(final_k.mean()),
        float(final_outs.mean()),
        float(final_k.std(ddof=1)),
        float(final_outs.std(ddof=1)),
        k_probs,
        outs_probs,
        final_k,
        final_outs,
        math_projection.confidence,
        math_projection.data_quality,
        math_projection.factors,
    )
'''
source = source.replace("def over_probability(", TWO_PATH + "\ndef over_probability(", 1)

# Streamlit 1.61+ compatibility.
source = source.replace("use_container_width=True", "width=\"stretch\"")

# Compile before execution so a failed source patch cannot take down the live app.
compile(source, LEGACY, "exec")
exec(compile(source, LEGACY, "exec"), globals(), globals())

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

# Keep the approved target layout from the legacy app, but repair the asset-driven
# branding that was disappearing in the hosted environment.  The current screenshots
# show the underlying layout is correct; the missing pieces are the sidebar logo,
# hero artwork, and CLE badge.
BRANDING_FIX_CSS = f"""
<style>
/* --- StrikeOut King 9000 target-brand restoration --- */
.sok-sidebar-logo{{
  width:100%!important;
  height:92px!important;
  margin:0 0 .55rem!important;
  display:block!important;
  background:url('{ASSET_BASE}/strikeout_king_9000.png') center center/contain no-repeat!important;
}}
.sok-sidebar-logo>*{{display:none!important}}
.sok-sidebar-title,.sok-sidebar-sub{{display:none!important}}

/* The first hero column is the reserved artwork slot in the approved design. */
.sok-hero>div:first-child{{
  min-height:190px!important;
  background:url('{ASSET_BASE}/strikeout_king_9000_hero.webp') center center/contain no-repeat!important;
}}

/* Prevent the old text-only hero treatment from competing with the artwork. */
.sok-hero .sok-title{{
  text-align:left!important;
}}

/* Target reference uses a dedicated CLE badge immediately left of Data Status. */
.sok-status{{position:relative!important;margin-left:112px!important;}}
.sok-status:before{{
  content:'BUILT FOR CLE\\A BASEBALL';
  white-space:pre;
  position:absolute;
  left:-108px;
  top:0;
  width:92px;
  min-height:112px;
  box-sizing:border-box;
  display:flex;
  align-items:center;
  justify-content:center;
  text-align:center;
  padding:10px 7px;
  border:2px solid #dbe4ee;
  border-radius:15px;
  background:linear-gradient(145deg,#0b203a,#07172b);
  color:#fff;
  font-family:Impact,"Arial Narrow",sans-serif;
  font-size:13px;
  line-height:1.05;
  letter-spacing:.045em;
  text-shadow:0 1px 0 #000;
  box-shadow:0 8px 18px rgba(0,0,0,.2),inset 0 0 0 3px rgba(227,24,55,.10);
}}
.sok-status:after{{
  content:'★★★';
  position:absolute;
  left:-99px;
  top:74px;
  width:74px;
  text-align:center;
  color:#e31837;
  font-size:12px;
  letter-spacing:3px;
}}

/* Keep the target page proportions at desktop widths. */
@media(min-width:1200px){{
  .sok-hero{{grid-template-columns:190px 1fr 205px!important;gap:1rem!important;min-height:205px!important;}}
  .sok-title{{font-size:5rem!important;}}
}}
</style>
"""

source = source.replace(
    "st.markdown(r\"\"\"",
    "st.markdown(BRANDING_FIX_CSS, unsafe_allow_html=True)\n\nst.markdown(r\"\"\"",
    1,
)

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
            f"{game.key}|{date.today()}|{APP_VERSION}|two-path-v6".encode()
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

# Streamlit 1.61+ compatibility: replace the deprecated width argument in the
# legacy UI while preserving the target layout.
source = source.replace("use_container_width=True", "width=\"stretch\"")

compile(source, LEGACY, "exec")
exec(compile(source, LEGACY, "exec"), globals(), globals())

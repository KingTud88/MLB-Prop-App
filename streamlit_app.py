from __future__ import annotations

import re
from pathlib import Path

import requests
import streamlit as st

LEGACY = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/d87e181aed527cebd1b902e7cc224aa96b06fbcc/streamlit_app.py"
MASCOT_URL = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/strikeout_king_9000.svg"

_original_markdown_fn = st.markdown
_original_image_fn = st.image

STYLE_OVERRIDE = r'''
<style>
[data-testid="stSidebar"]{width:205px!important;min-width:205px!important}
[data-testid="stSidebar"]>div:first-child{width:205px!important}
[data-testid="stSidebarNav"]{display:none!important}
.block-container{max-width:1540px!important;padding:.75rem 1rem 2rem!important}
.sok-sidebar-logo{display:flex!important;justify-content:center!important;align-items:center!important;min-height:145px!important}
.sok-sidebar-logo .sok-mascot-image{width:140px!important;height:140px!important;object-fit:contain!important;display:block!important}
.sok-hero{min-height:300px!important;grid-template-columns:270px minmax(0,1fr) 220px!important}
.sok-hero .sok-mascot-image{width:255px!important;height:295px!important;max-height:295px!important;object-fit:contain!important;filter:drop-shadow(0 18px 22px rgba(0,0,0,.5))!important}
.sok-title{font-size:clamp(5rem,6.8vw,7.6rem)!important;line-height:.76!important;white-space:nowrap!important}
.section-frame{border-width:2px!important;border-color:#e31837!important;border-radius:17px!important}
.proj-card{min-height:220px!important;border-width:2px!important;border-radius:16px!important}
.proj-value{font-size:3.8rem!important}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]{border-radius:8px!important;padding:.42rem .55rem!important;margin:.08rem 0!important;color:#dce6f0!important;font-weight:800!important}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover{background:#102b4c!important;color:#fff!important}
</style>
'''


def patched_markdown(body=None, *args, **kwargs):
    if isinstance(body, str) and '<style>' in body and '--navy:' in body:
        return _original_markdown_fn(body + STYLE_OVERRIDE, *args, **kwargs)
    return _original_markdown_fn(body, *args, **kwargs)


def patched_image(image, *args, **kwargs):
    image_text = str(image) if isinstance(image, (str, Path)) else ""
    if "strikeout_king_9000" in image_text or image_text.lower().endswith(".svg"):
        width = kwargs.get("width")
        style = f"width:{int(width)}px;" if isinstance(width, (int, float)) else ""
        html = (
            f'<div class="sok-mascot-wrap" style="{style}">'
            f'<img class="sok-mascot-image" src="{MASCOT_URL}" alt="StrikeOut King 9000 mascot">'
            f'</div>'
        )
        return _original_markdown_fn(html, unsafe_allow_html=True)
    return _original_image_fn(image, *args, **kwargs)


st.markdown = patched_markdown
st.image = patched_image

response = requests.get(LEGACY, timeout=20)
response.raise_for_status()
source = response.text
source = source.replace('initial_sidebar_state="expanded"', 'initial_sidebar_state="collapsed"', 1)

# Replace the old href-based sidebar navigation without changing the
# indentation of the surrounding legacy `with st.sidebar:` block. The
# previous patch added its own four spaces on top of the existing indentation,
# which produced the repeated `IndentationError: unexpected indent` failures.
nav_lines = [
    'st.page_link("streamlit_app.py", label="⌂  Projection", use_container_width=True)',
    'st.page_link("pages/2_Bet_Tracker.py", label="♧  Bet Tracker", use_container_width=True)',
    'st.page_link("pages/3_Odds_API.py", label="◎  Odds API", use_container_width=True)',
    'st.page_link("pages/4_Projection_History.py", label="▣  Projection History", use_container_width=True)',
    'st.page_link("pages/5_Daily_Projection_Run.py", label="▤  Daily Projection Run", use_container_width=True)',
]

lines = source.splitlines()
nav_index = next((i for i, line in enumerate(lines) if 'class="sok-nav"' in line and 'st.markdown' in line), None)
if nav_index is None:
    raise RuntimeError("Legacy sidebar navigation block was not found; refusing to deploy a partial patch.")

indent = re.match(r"^\s*", lines[nav_index]).group(0)
lines[nav_index:nav_index + 1] = [indent + nav_line for nav_line in nav_lines]
source = "\n".join(lines) + "\n"

# Validate the generated legacy program before executing it. This catches
# malformed navigation edits during deployment instead of at runtime.
compile(source, LEGACY, "exec")
exec(compile(source, LEGACY, "exec"), globals(), globals())

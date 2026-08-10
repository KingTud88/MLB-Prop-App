from __future__ import annotations

import requests
import streamlit as st

# Surgical runtime wrapper: the production UI lives in the known-good commit below.
# We patch the single malformed validation-list token before compiling it.
SOURCE_URL = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/2f63203addc9dc7f6002fece9b341a4f89d490bb/streamlit_app.py"
BAD = 'required=["class MLBClient:","def get_schedule(","def get_pitcher_game_log(","def calculate_projection(","def over_probability(")]'
GOOD = 'required=["class MLBClient:","def get_schedule(","def get_pitcher_game_log(","def calculate_projection(","def over_probability(")]'.replace('(")]', '("]')

try:
    response = requests.get(SOURCE_URL, timeout=20)
    response.raise_for_status()
    source = response.text
    if BAD not in source:
        st.error("StrikeOut King 9000 source changed: expected syntax marker was not found. Refusing to execute an unknown source.")
        st.stop()
    source = source.replace(BAD, GOOD, 1)
    compile(source, SOURCE_URL, "exec")
except requests.RequestException as exc:
    st.error(f"StrikeOut King 9000 source unavailable: {exc}")
    st.stop()
except SyntaxError as exc:
    st.error(f"StrikeOut King 9000 source still has a syntax error after the surgical fix: {exc}")
    st.stop()

exec(compile(source, SOURCE_URL, "exec"), globals(), globals())

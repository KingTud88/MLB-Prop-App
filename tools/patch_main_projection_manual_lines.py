from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Missing patch anchor: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    if "MAIN_PROJECTION_DURABLE_LINES_V1" in text:
        print("Main Projection durable manual lines already applied")
        return

    text = replace_once(
        text,
        "from training.bet_storage import append_bet\n",
        "from training.bet_storage import append_bet\nfrom training.projection_storage import load_projection_archive, overlay_manual_market_lines\n",
        "projection storage import",
    )

    text = replace_once(
        text,
        'BET_LOG = APP_DIR / "data" / "bet_log.csv"\nOBS_LOG = APP_DIR / "data" / "starter_observation_log.csv"\n',
        'BET_LOG = APP_DIR / "data" / "bet_log.csv"\nARCHIVE_PATH = APP_DIR / "data" / "projection_archive.csv"\nOBS_LOG = APP_DIR / "data" / "starter_observation_log.csv"\n',
        "archive path",
    )

    text = replace_once(
        text,
        '.market-ok{color:#49efb0;font-weight:800}.market-empty{color:#8fa5b7}\n</style>',
        '.market-ok{color:#49efb0;font-weight:800}.market-empty{color:#8fa5b7}\n.active-market-line{padding:.72rem .78rem;border:1px solid #20425f;border-radius:12px;background:rgba(9,27,44,.94);text-align:center}.active-market-line .label{color:#9fb3c3;font-size:.72rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase}.active-market-line .value{margin-top:.18rem;color:#f2f6fa;font-size:1.5rem;font-weight:950}.active-market-line .source{margin-top:.14rem;color:#8fa5b7;font-size:.68rem;font-weight:850;letter-spacing:.04em}.active-market-line.manual{border-color:rgba(255,159,28,.66);background:rgba(255,159,28,.07)}.active-market-line.manual .value,.active-market-line.manual .source{color:#ff9f1c}.reco-line.manual-active{color:#ff9f1c;text-shadow:0 0 15px rgba(255,159,28,.18)}\n</style>',
        "manual line css",
    )

    helper_anchor = '''    return {"side":decision.side,"line":line,"model":decision.model_probability,"edge":decision.edge,"confidence":confidence,"has_market":bool(rows),"reason":decision.reason,"projection_mean":projection_mean,"over_model":over_model}\n\ndef _manual_line_options(market_key):\n'''
    helper_new = '''    return {"side":decision.side,"line":line,"model":decision.model_probability,"edge":decision.edge,"confidence":confidence,"has_market":bool(rows),"reason":decision.reason,"projection_mean":projection_mean,"over_model":over_model}\n\ndef apply_active_line_to_recommendation(reco,proj,market_key,line,hits_proj=None,source="MANUAL"):\n    if line is None:\n        return dict(reco)\n    line=float(line)\n    over_model=float(market_model_probability(proj,market_key,line,hits_proj))\n    projection_mean=float(reco.get("projection_mean",0.0))\n    decision=aligned_bet_lean(projection_mean,line,over_model,has_market=False)\n    updated=dict(reco)\n    updated.update({\n        "side":decision.side,"line":line,"model":decision.model_probability,"edge":decision.edge,\n        "confidence":abs(decision.model_probability-.5)*2,"has_market":True,"reason":decision.reason,\n        "projection_mean":projection_mean,"over_model":over_model,"active_line":True,"active_line_source":str(source or "MANUAL").upper(),\n    })\n    return updated\n\ndef _manual_line_options(market_key):\n'''
    text = replace_once(text, helper_anchor, helper_new, "active line recommendation helper")

    render_old = '''    with card:\n        st.markdown(f'<div class="reco-card {cls}"><div class="cc-card-top"><div class="cc-card-icon">{icon}</div><div class="reco-label">{effective["label"]}</div></div><div class="reco-side {cls}">{side}</div><div class="reco-line">{effective["line"]:g} LINE</div><div class="reco-meta">{meta}</div></div>',unsafe_allow_html=True)\n'''
    render_new = '''    active_source=str(effective.get("active_line_source","") or "").strip().upper()\n    line_class="reco-line manual-active" if active_source=="MANUAL" else "reco-line"\n    if active_source=="MANUAL":\n        meta += " · MANUAL DAILY LINE"\n    with card:\n        st.markdown(f'<div class="reco-card {cls}"><div class="cc-card-top"><div class="cc-card-icon">{icon}</div><div class="reco-label">{effective["label"]}</div></div><div class="reco-side {cls}">{side}</div><div class="{line_class}">{effective["line"]:g} LINE</div><div class="reco-meta">{meta}</div></div>',unsafe_allow_html=True)\n'''
    text = replace_once(text, render_old, render_new, "orange recommendation line")

    hits_anchor = '''hits_proj=project_hits_allowed(log,expected_bf=features_for_hits["expected_bf"],bf_sd=workload_ctx.bf_sd,opponent_hit_rate=float(opponent_matchup.get("hit_rate",.235)),seed=hits_seed,draws=25000,lines=(3.5,4.5,5.5,6.5,7.5,8.5))\nodds_rows=load_pitcher_strikeout_odds(game.pitcher_name,selected_date.isoformat())\n'''
    hits_new = '''hits_proj=project_hits_allowed(log,expected_bf=features_for_hits["expected_bf"],bf_sd=workload_ctx.bf_sd,opponent_hit_rate=float(opponent_matchup.get("hit_rate",.235)),seed=hits_seed,draws=25000,lines=(3.5,4.5,5.5,6.5,7.5,8.5))\n# MAIN_PROJECTION_DURABLE_LINES_V1\ndurable_archive=load_projection_archive(ARCHIVE_PATH,st.secrets)\n_manual_probe=pd.DataFrame([{"game_pk":game.game_pk,"pitcher_id":game.pitcher_id}])\n_manual_probe=overlay_manual_market_lines(_manual_probe,durable_archive)\n_manual_row=_manual_probe.iloc[0] if not _manual_probe.empty else pd.Series(dtype=object)\ndef _durable_line(col):\n    value=pd.to_numeric(pd.Series([_manual_row.get(col)]),errors="coerce").iloc[0]\n    return None if pd.isna(value) else float(value)\ndef _durable_source(col):\n    value=_manual_row.get(col,"")\n    return "" if pd.isna(value) else str(value).strip().upper()\nmanual_k_line=_durable_line("active_strikeout_line")\nmanual_outs_line=_durable_line("active_outs_line")\nmanual_hits_line=_durable_line("active_hits_allowed_line")\nmanual_k_source=_durable_source("active_strikeout_line_source")\nmanual_outs_source=_durable_source("active_outs_line_source")\nmanual_hits_source=_durable_source("active_hits_allowed_line_source")\nodds_rows=load_pitcher_strikeout_odds(game.pitcher_name,selected_date.isoformat())\n'''
    text = replace_once(text, hits_anchor, hits_new, "durable manual line lookup")

    reco_anchor = '''hit_reco={"side":hit_decision.side,"line":hit_line,"model":hit_decision.model_probability,"edge":hit_decision.edge,"confidence":abs(hit_decision.model_probability-.5)*2,"has_market":bool(hit_rows),"label":"HITS ALLOWED BET LEAN","reason":hit_decision.reason,"projection_mean":hits_proj.ensemble_mean,"over_model":hit_over}\n\nif nav=="Distribution":\n'''
    reco_new = '''hit_reco={"side":hit_decision.side,"line":hit_line,"model":hit_decision.model_probability,"edge":hit_decision.edge,"confidence":abs(hit_decision.model_probability-.5)*2,"has_market":bool(hit_rows),"label":"HITS ALLOWED BET LEAN","reason":hit_decision.reason,"projection_mean":hits_proj.ensemble_mean,"over_model":hit_over}\nif manual_k_line is not None:\n    k_reco=apply_active_line_to_recommendation(k_reco,proj,"pitcher_strikeouts",manual_k_line,hits_proj,manual_k_source or "MANUAL")\nif manual_outs_line is not None:\n    out_reco=apply_active_line_to_recommendation(out_reco,proj,"pitcher_outs",manual_outs_line,hits_proj,manual_outs_source or "MANUAL")\nif manual_hits_line is not None:\n    hit_reco=apply_active_line_to_recommendation(hit_reco,proj,"pitcher_hits_allowed",manual_hits_line,hits_proj,manual_hits_source or "MANUAL")\n\nif nav=="Distribution":\n'''
    text = replace_once(text, reco_anchor, reco_new, "apply durable lines to recos")

    strip_anchor = '''render_matchup_strip(\n    pitcher_name=game.pitcher_name,\n    team=game.team,\n    opponent=game.opponent,\n    venue=game.venue,\n    side=game.side,\n    status=game.status,\n    game_time=game.game_time,\n    locked=locked,\n    weather_icon=weather_risk.icon or "",\n    team_id=TEAM_ID_BY_ABBR.get(game.team,0),\n)\nif weather_risk.available and weather_risk.level in {"HIGH","ELEVATED"}:\n'''
    strip_new = '''render_matchup_strip(\n    pitcher_name=game.pitcher_name,\n    team=game.team,\n    opponent=game.opponent,\n    venue=game.venue,\n    side=game.side,\n    status=game.status,\n    game_time=game.game_time,\n    locked=locked,\n    weather_icon=weather_risk.icon or "",\n    team_id=TEAM_ID_BY_ABBR.get(game.team,0),\n)\nst.markdown('<div class="section-head">ACTIVE SPORTSBOOK LINES</div>',unsafe_allow_html=True)\n_line_cols=st.columns(3)\nfor _col,_label,_line,_source in zip(\n    _line_cols,("STRIKEOUTS","TOTAL OUTS","HITS ALLOWED"),\n    (manual_k_line,manual_outs_line,manual_hits_line),(manual_k_source,manual_outs_source,manual_hits_source),\n):\n    _manual=str(_source or "").upper()=="MANUAL"\n    _cls="active-market-line manual" if _manual else "active-market-line"\n    _value="—" if _line is None else f"{float(_line):g}"\n    _source_text="MANUAL · DAILY RUN" if _manual else (str(_source) if _source else "NO MANUAL LINE")\n    with _col:\n        st.markdown(f'<div class="{_cls}"><div class="label">{_label}</div><div class="value">{_value}</div><div class="source">{_source_text}</div></div>',unsafe_allow_html=True)\nst.caption("Orange = the durable sportsbook line you entered on Daily Projection Run. These execution lines do not alter the frozen baseball projection; they set the exact line used for the recommendation comparison.")\nif weather_risk.available and weather_risk.level in {"HIGH","ELEVATED"}:\n'''
    text = replace_once(text, strip_anchor, strip_new, "active sportsbook line strip")

    APP.write_text(text, encoding="utf-8")
    print("Patched Main Projection durable manual lines")


if __name__ == "__main__":
    main()

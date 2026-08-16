from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
MARKER = "PROJECTION_EMBLEMS_V1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Missing emblem patch anchor: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    if MARKER in text:
        print("Projection emblems already applied")
        return

    css_anchor = ".market-ok{color:#49efb0;font-weight:800}.market-empty{color:#8fa5b7}\n"
    css_new = css_anchor + r'''/* PROJECTION_EMBLEMS_V1 · icon-only presentation pass */
/* Replace the Main Projection radio dots with compact command-center glyphs. */
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label{
    position:relative!important;gap:.52rem!important;min-height:2.42rem!important;padding:.26rem .38rem!important;
    border-radius:9px!important;transition:background .14s ease,border-color .14s ease,box-shadow .14s ease!important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label>div:first-child{display:none!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label::before{
    display:inline-flex;align-items:center;justify-content:center;width:1.72rem;height:1.72rem;flex:0 0 1.72rem;
    border:1px solid rgba(236,22,56,.68);border-radius:7px;background:linear-gradient(145deg,#102b49,#061426);
    color:#f6f8fb;font-family:Arial,sans-serif;font-size:1.02rem;font-weight:950;line-height:1;
    box-shadow:inset 0 0 0 2px rgba(255,255,255,.025),0 4px 10px rgba(0,0,0,.25);text-shadow:0 0 8px rgba(236,22,56,.24);
}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:has(input:checked)::before{
    color:#fff;border-color:#ff3553;background:linear-gradient(145deg,#5b1124,#16152a);
    box-shadow:inset 0 0 0 2px rgba(255,255,255,.04),0 0 13px rgba(236,22,56,.42);
}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(1)::before{content:"⌖"}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(2)::before{content:"▥"}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(3)::before{content:"∿"}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(4)::before{content:"⌘"}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(5)::before{content:"▰"}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(6)::before{content:"◷"}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(7)::before{content:"ϟ"}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]>label:nth-child(8)::before{content:"♛"}

/* Baseball emblems occupy the exact existing 48px card-icon slot. */
.cc-card-icon.cc-emblem{position:relative;overflow:visible;font-size:0!important}
.cc-card-icon.cc-emblem::before,.cc-card-icon.cc-emblem::after{position:absolute;display:block;pointer-events:none}
/* K = bat passes above the ball: visible whiff gap. */
.cc-card-icon.cc-emblem.whiff::before{
    content:"";width:31px;height:7px;left:14px;top:13px;border-radius:7px 3px 3px 7px;
    background:linear-gradient(90deg,#7a3b18,#d58a3f 64%,#f0b966);border:1px solid rgba(255,220,160,.32);
    transform:rotate(-38deg);box-shadow:0 2px 6px rgba(0,0,0,.34),7px 7px 0 -5px rgba(255,255,255,.7);
}
.cc-card-icon.cc-emblem.whiff::after{content:"⚾";left:2px;bottom:2px;font-size:21px;line-height:1;filter:drop-shadow(0 3px 4px rgba(0,0,0,.35))}
/* H = bat intersects the baseball; glow reads as contact/impact. */
.cc-card-icon.cc-emblem.contact::before{
    content:"";width:34px;height:8px;left:8px;top:21px;border-radius:8px 3px 3px 8px;
    background:linear-gradient(90deg,#713416,#d88738 62%,#efb96a);border:1px solid rgba(255,220,160,.34);
    transform:rotate(-34deg);box-shadow:0 2px 6px rgba(0,0,0,.34),0 0 9px rgba(255,159,28,.18);
}
.cc-card-icon.cc-emblem.contact::after{content:"⚾";right:2px;top:4px;font-size:22px;line-height:1;filter:drop-shadow(0 0 6px rgba(255,80,70,.62)) drop-shadow(0 3px 4px rgba(0,0,0,.35))}
/* OUT = baseball seated in a glove. */
.cc-card-icon.cc-emblem.glove::before{content:"🧤";left:5px;top:5px;font-size:31px;line-height:1;filter:drop-shadow(0 3px 4px rgba(0,0,0,.34))}
.cc-card-icon.cc-emblem.glove::after{content:"⚾";right:3px;bottom:3px;font-size:17px;line-height:1;filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
'''
    text = replace_once(text, css_anchor, css_new, "emblem CSS")

    render_icon_old = '''    icon=("K+" if "STRIKEOUT" in str(effective.get("label","")) else "OUT" if "OUTS" in str(effective.get("label","")) else "H")\n'''
    render_icon_new = '''    emblem_class=("whiff" if "STRIKEOUT" in str(effective.get("label","")) else "glove" if "OUTS" in str(effective.get("label","")) else "contact")\n'''
    text = replace_once(text, render_icon_old, render_icon_new, "recommendation emblem class")

    render_html_old = '''        st.markdown(f'<div class="reco-card {cls}"><div class="cc-card-top"><div class="cc-card-icon">{icon}</div><div class="reco-label">{effective["label"]}</div></div><div class="reco-side {cls}">{side}</div><div class="{line_class}">{effective["line"]:g} LINE</div><div class="reco-meta">{meta}</div></div>',unsafe_allow_html=True)\n'''
    render_html_new = '''        st.markdown(f'<div class="reco-card {cls}"><div class="cc-card-top"><div class="cc-card-icon cc-emblem {emblem_class}" aria-hidden="true"></div><div class="reco-label">{effective["label"]}</div></div><div class="reco-side {cls}">{side}</div><div class="{line_class}">{effective["line"]:g} LINE</div><div class="reco-meta">{meta}</div></div>',unsafe_allow_html=True)\n'''
    text = replace_once(text, render_html_old, render_html_new, "recommendation emblem HTML")

    k_metric_old = '''with c1: st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon">K</div><div class="metric-label">PROJECTED STRIKEOUTS</div></div><div class="metric-value">{proj.mean_k:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.k_samples,.1))}-{int(np.quantile(proj.k_samples,.9))}</span>{alt_k_html}</div>',unsafe_allow_html=True)\n'''
    k_metric_new = '''with c1: st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon cc-emblem whiff" aria-hidden="true"></div><div class="metric-label">PROJECTED STRIKEOUTS</div></div><div class="metric-value">{proj.mean_k:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.k_samples,.1))}-{int(np.quantile(proj.k_samples,.9))}</span>{alt_k_html}</div>',unsafe_allow_html=True)\n'''
    text = replace_once(text, k_metric_old, k_metric_new, "projected K emblem")

    outs_metric_old = '''with c3: st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon ball">⚾</div><div class="metric-label">PROJECTED OUTS</div></div><div class="metric-value">{proj.mean_outs:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.outs_samples,.1))}-{int(np.quantile(proj.outs_samples,.9))}</span></div>',unsafe_allow_html=True)\n'''
    outs_metric_new = '''with c3: st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon cc-emblem glove" aria-hidden="true"></div><div class="metric-label">PROJECTED OUTS</div></div><div class="metric-value">{proj.mean_outs:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(proj.outs_samples,.1))}-{int(np.quantile(proj.outs_samples,.9))}</span></div>',unsafe_allow_html=True)\n'''
    text = replace_once(text, outs_metric_old, outs_metric_new, "projected outs emblem")

    hits_metric_old = '''with h1: st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon hit">H</div><div class="metric-label">PROJECTED HITS ALLOWED</div></div><div class="metric-value">{hits_proj.ensemble_mean:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(hits_proj.simulation_samples,.1))}-{int(np.quantile(hits_proj.simulation_samples,.9))}</span></div>',unsafe_allow_html=True)\n'''
    hits_metric_new = '''with h1: st.markdown(f'<div class="metric-card"><div class="cc-card-top"><div class="cc-card-icon cc-emblem contact" aria-hidden="true"></div><div class="metric-label">PROJECTED HITS ALLOWED</div></div><div class="metric-value">{hits_proj.ensemble_mean:.2f}</div><span class="badge">↑ 80% RANGE {int(np.quantile(hits_proj.simulation_samples,.1))}-{int(np.quantile(hits_proj.simulation_samples,.9))}</span></div>',unsafe_allow_html=True)\n'''
    text = replace_once(text, hits_metric_old, hits_metric_new, "projected hits emblem")

    APP.write_text(text, encoding="utf-8")
    print("Applied Projection sidebar/card emblem pass")


if __name__ == "__main__":
    main()

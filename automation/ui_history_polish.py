from __future__ import annotations

from pathlib import Path

PAGE = Path("pages/4_Projection_History.py")


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise SystemExit(f"History UI marker missing: {old[:80]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PAGE.read_text(encoding="utf-8")
    if "history-dashboard-v1" in text:
        print("Projection History polish already applied")
        return

    text = replace_once(
        text,
        "    .block-container { padding-top: 3.25rem !important; }\n",
        "    .block-container { padding-top: 3.25rem !important; }\n"
        "    /* history-dashboard-v1: presentation only; no grading/model semantics. */\n"
        "    .history-hero {\n"
        "        margin: .25rem 0 1.2rem; padding: .9rem 1rem; border-radius: 16px;\n"
        "        border: 1px solid rgba(227,25,55,.34);\n"
        "        background: linear-gradient(120deg, rgba(227,25,55,.09), rgba(10,29,54,.72) 42%, rgba(6,18,35,.76));\n"
        "        box-shadow: 0 14px 34px rgba(0,0,0,.16);\n"
        "    }\n"
        "    .history-hero strong { color:#f8fbff; font-size:1rem; letter-spacing:.01em; }\n"
        "    .history-hero span { display:block; color:#9db0c5; font-size:.84rem; margin-top:.18rem; }\n"
        "    .history-kicker {\n"
        "        margin: 1.35rem 0 .45rem; color:#aebfd2; font-size:.72rem; font-weight:900;\n"
        "        letter-spacing:.13em; text-transform:uppercase;\n"
        "    }\n"
        "    .history-kicker::before {\n"
        "        content:''; display:inline-block; width:22px; height:2px; margin-right:.5rem; vertical-align:middle;\n"
        "        background:#ff3655; box-shadow:0 0 11px rgba(227,25,55,.42);\n"
        "    }\n"
        "    @media (max-width: 900px) {\n"
        "        .history-hero { padding:.78rem .85rem; }\n"
        "        .history-kicker { margin-top:1rem; }\n"
        "    }\n",
    )

    caption = (
        'st.caption(\n'
        '    "Frozen pregame StrikeOut King 9000 projections, resolved against final MLB strikeouts, "\n'
        '    "total outs, and hits allowed. Current learning diagnostics only use starter-only model rows."\n'
        ')\n'
    )
    text = replace_once(
        text,
        caption,
        caption
        + 'st.markdown(\n'
        + '    "<div class=\"history-hero\"><strong>Performance archive · frozen pregame evidence</strong>"\n'
        + '    "<span>Scoreboard first, K wins and crushers next, deeper learning diagnostics below.</span></div>",\n'
        + '    unsafe_allow_html=True,\n'
        + ')\n',
    )

    text = replace_once(
        text,
        'col1, col2, col3, col4, col5, col6 = st.columns(6)\n',
        'st.markdown("<div class=\"history-kicker\">Performance scoreboard</div>", unsafe_allow_html=True)\n'
        'col1, col2, col3, col4, col5, col6 = st.columns(6)\n',
    )
    text = replace_once(
        text,
        'st.subheader("🔥 Bettable K Wins & Crushers")\n',
        'st.markdown("<div class=\"history-kicker\">Actionable K results</div>", unsafe_allow_html=True)\n'
        'st.subheader("🔥 Bettable K Wins & Crushers")\n',
    )
    text = replace_once(
        text,
        'st.subheader("🧠 Current model learning status")\n',
        'st.markdown("<div class=\"history-kicker\">Learning diagnostics</div>", unsafe_allow_html=True)\n'
        'st.subheader("🧠 Current model learning status")\n',
    )
    text = replace_once(
        text,
        'st.subheader("📋 Projection archive")\n',
        'st.markdown("<div class=\"history-kicker\">Resolved & pending slates</div>", unsafe_allow_html=True)\n'
        'st.subheader("📋 Projection archive")\n',
    )

    PAGE.write_text(text, encoding="utf-8")
    print("Applied projection history dashboard polish")


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path

TARGETS = (
    Path("streamlit_app.py"),
    Path("pages/2_Bet_Tracker.py"),
    Path("pages/4_Projection_History.py"),
    Path("pages/5_Daily_Projection_Run.py"),
    Path("pages/6_Top_Plays.py"),
)

IMPORT = "from engine.ui_theme import apply_page_theme\n"


def patch(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    if IMPORT not in text:
        marker = "import streamlit as st\n"
        if marker not in text:
            raise RuntimeError(f"Streamlit import not found in {path}")
        text = text.replace(marker, marker + "\n" + IMPORT, 1)

    if "apply_page_theme()" not in text:
        lines = text.splitlines(keepends=True)
        page_config_idx = next((i for i, line in enumerate(lines) if "st.set_page_config(" in line), None)
        if page_config_idx is None:
            raise RuntimeError(f"st.set_page_config not found in {path}")
        # All current app page-config calls are single-line. Keep this migration
        # deliberately strict so a future formatting change fails loudly rather
        # than injecting presentation code into a wrong location.
        lines.insert(page_config_idx + 1, "apply_page_theme()\n")
        text = "".join(lines)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = []
    for path in TARGETS:
        if patch(path):
            changed.append(str(path))
    print("UI readability migration complete")
    for path in changed:
        print(f"changed={path}")


if __name__ == "__main__":
    main()

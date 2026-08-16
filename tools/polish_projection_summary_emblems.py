from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
OLD_ART = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_summary_emblems.webp?v=1"
NEW_ART = "https://raw.githubusercontent.com/KingTud88/MLB-Prop-App/main/assets/projection_summary_emblems_v2.webp?v=2"


def main() -> None:
    text = APP.read_text(encoding="utf-8")

    if NEW_ART in text:
        print("Corrected Projection Summary artwork already active")
        return

    if OLD_ART not in text:
        raise RuntimeError("Could not find the current Projection Summary artwork URL")

    text = text.replace(OLD_ART, NEW_ART, 1)
    APP.write_text(text, encoding="utf-8")
    print("Switched Projection Summary to corrected six-cell artwork sprite")


if __name__ == "__main__":
    main()

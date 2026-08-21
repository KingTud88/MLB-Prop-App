from __future__ import annotations

from pathlib import Path


LEGACY_ENTRYPOINT = Path("build_app.py")
ACTIVE_ENTRYPOINT = Path("streamlit_app.py")


def test_empty_legacy_build_app_stays_retired() -> None:
    assert not LEGACY_ENTRYPOINT.exists()


def test_streamlit_app_remains_the_active_app_entrypoint() -> None:
    assert ACTIVE_ENTRYPOINT.is_file()
    source = ACTIVE_ENTRYPOINT.read_text(encoding="utf-8")
    assert "st.set_page_config(" in source
    assert "APP_VERSION =" in source

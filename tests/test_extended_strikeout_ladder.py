from pathlib import Path


def test_projection_and_daily_capture_support_11_and_12_plus():
    root = Path(__file__).resolve().parents[1]
    app = (root / "streamlit_app.py").read_text(encoding="utf-8")
    daily = (root / "automation" / "daily_projection_runner.py").read_text(encoding="utf-8")
    assert "range(3,13)" in app
    assert "kdf=ladder(proj,12)" in app
    assert "range(3, 13)" in daily
    assert 'out[f"sim_{line}p"]' in daily
    assert 'out[f"math_{line}p"]' in daily
    assert 'row.get(f"sim_{line}p")' in daily
    assert 'row.get(f"math_{line}p")' in daily

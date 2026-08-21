from pathlib import Path

import pandas as pd

from engine import projection_underperformer_ui as underperformer_ui


def test_projection_history_wires_underperformers_after_crushers() -> None:
    text = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    assert "from engine.projection_underperformer_ui import render_projection_underperformers" in text
    crusher = text.index('st.markdown("#### Projection Crushers · exact frozen projection")')
    call = text.index("render_projection_underperformers(df)")
    learning = text.index('st.markdown(\'<div class="history-kicker">Learning diagnostics</div>\'')
    assert crusher < call < learning


def test_underperformer_renderer_preserves_exact_projection_semantics() -> None:
    text = Path("engine/projection_underperformer_ui.py").read_text(encoding="utf-8")
    compile(text, "engine/projection_underperformer_ui.py", "exec")
    assert "underperformer_report" in text
    assert "Projection Underperformers · exact frozen projection" in text
    assert "Below Projection Rate" in text
    assert "Recent 5 Below Rate" in text
    assert "Avg K vs Projection" in text
    assert "Median K vs Projection" in text
    assert "Avg Under Margin" in text
    assert "Total K Below Projection" in text
    assert "at least 66.7%" in text
    assert "below -0.50" in text
    assert "not sportsbook execution grading" in text


def test_underperformer_renderer_formats_backend_report_without_regrading(monkeypatch) -> None:
    backend = pd.DataFrame(
        [
            {
                "Pitcher": "Test Pitcher",
                "Resolved Starts": 4,
                "Below Projection Starts": 3,
                "Below Projection Rate": 0.75,
                "Avg K vs Projection": -0.8,
                "Median K vs Projection": -0.7,
                "Avg Under Margin": -1.1,
                "Total K Below Projection": 3.2,
                "2+ K Under Events": 1,
                "Recent 5 Below Rate": 0.75,
                "Current Below Streak": 2,
                "Underperformer Status": "SOURCE_OWNED_STATUS",
            }
        ]
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(underperformer_ui, "underperformer_report", lambda _: backend.copy())
    monkeypatch.setattr(underperformer_ui.st, "markdown", lambda value: captured.setdefault("markdown", value))
    monkeypatch.setattr(underperformer_ui.st, "info", lambda value: captured.setdefault("info", value))
    monkeypatch.setattr(
        underperformer_ui.st,
        "dataframe",
        lambda frame, **kwargs: captured.setdefault("frame", frame.copy()),
    )
    monkeypatch.setattr(underperformer_ui.st, "caption", lambda value: captured.setdefault("caption", value))

    underperformer_ui.render_projection_underperformers(pd.DataFrame({"projection": [5.8]}))

    view = captured["frame"]
    assert isinstance(view, pd.DataFrame)
    assert view.loc[0, "Below Projection Rate"] == "75.0%"
    assert view.loc[0, "Recent 5 Below Rate"] == "75.0%"
    assert view.loc[0, "Avg K vs Projection"] == "-0.80"
    assert view.loc[0, "Median K vs Projection"] == "-0.70"
    assert view.loc[0, "Avg Under Margin"] == "-1.10"
    assert view.loc[0, "Total K Below Projection"] == "3.20"
    assert view.loc[0, "Underperformer Status"] == "SOURCE_OWNED_STATUS"
    assert "not sportsbook execution grading" in str(captured["caption"])

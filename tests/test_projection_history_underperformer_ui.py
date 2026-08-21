from pathlib import Path


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

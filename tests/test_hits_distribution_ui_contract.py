from pathlib import Path


APP = Path("streamlit_app.py")
EXPLAIN = Path("engine/explainability_ui.py")


def test_distribution_page_has_three_independent_market_charts() -> None:
    text = APP.read_text(encoding="utf-8")
    assert 'a,b,c=st.columns(3)' in text
    assert '### Strikeout probability distribution' in text
    assert '### Outs probability distribution' in text
    assert '### Hits Allowed probability distribution' in text
    assert 'pd.DataFrame({"Probability":proj.k_probs}' in text
    assert 'pd.DataFrame({"Probability":proj.outs_probs}' in text


def test_hits_distribution_uses_existing_simulation_samples_only() -> None:
    text = APP.read_text(encoding="utf-8")
    assert 'np.bincount(np.asarray(hits_proj.simulation_samples,dtype=int))' in text
    assert 'hits_distribution=hits_distribution/hits_distribution.sum()' in text
    assert 'static_explanation("distribution_hits")' in text


def test_hits_distribution_explanation_is_execution_independent() -> None:
    text = EXPLAIN.read_text(encoding="utf-8")
    assert '"distribution_hits": Explanation(' in text
    assert 'already-computed simulation outcomes' in text
    assert 'does not use sportsbook prices' in text
    assert 'does not change the projection or recommendation' in text

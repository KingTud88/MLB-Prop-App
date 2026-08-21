from pathlib import Path


def test_underperformer_shadow_is_report_only_and_cannot_adjust_projection() -> None:
    text = Path("training/projection_underperformer_shadow.py").read_text(encoding="utf-8")
    assert 'REPORT_ONLY = True' in text
    assert 'PRODUCTION_AUTHORITY = "NONE"' in text
    assert 'NO_PROJECTION_ADJUSTMENT = True' in text
    assert 'Below_Projection' in text
    assert 'Material_Underperform_Event' in text
    assert 'MANUAL_RESEARCH_REVIEW_THEN_FREEZE_FORWARD_CHALLENGER' in text


def test_underperformer_shadow_is_routed_before_promotion_milestones() -> None:
    text = Path("automation/research_context_readiness.sh").read_text(encoding="utf-8")
    under = text.index("training.projection_underperformer_shadow")
    promotion = text.index("training.research_promotion_command_center")
    milestone = text.index("training.research_milestone_watch")
    assert under < promotion < milestone


def test_underperformer_outputs_are_not_sportsbook_execution_inputs() -> None:
    training = Path("training/projection_underperformer_shadow.py").read_text(encoding="utf-8")
    assert "sportsbook" not in training.lower()
    assert "active_strikeout_line" not in training
    assert "manual_strikeout_line" not in training

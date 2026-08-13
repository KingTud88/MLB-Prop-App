from __future__ import annotations

import pandas as pd

from training.calibration_lineage import (
    PROBABILITY_SEMANTICS,
    audit_summary,
    classify_rows,
    eligible_rows,
)
from engine.starter_history import HISTORY_SEMANTICS


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "game_date": "2026-08-10",
        "captured_at_utc": "2026-08-10T14:00:00+00:00",
        "probability_semantics": PROBABILITY_SEMANTICS,
        "history_semantics": HISTORY_SEMANTICS,
        "actual_strikeouts": 7,
    }
    row.update(overrides)
    return row


def test_modern_resolved_row_is_eligible() -> None:
    classified = classify_rows(pd.DataFrame([_row()]))
    assert bool(classified.loc[0, "calibration_eligible"]) is True
    assert classified.loc[0, "calibration_exclusion_reason"] == ""


def test_legacy_or_unresolved_rows_are_rejected_without_inference() -> None:
    frame = pd.DataFrame([
        _row(probability_semantics=""),
        _row(history_semantics="legacy"),
        _row(actual_strikeouts=None),
    ])
    classified = classify_rows(frame)
    assert not classified["calibration_eligible"].any()
    assert "probability_semantics" in classified.loc[0, "calibration_exclusion_reason"]
    assert "history_semantics" in classified.loc[1, "calibration_exclusion_reason"]
    assert "unresolved" in classified.loc[2, "calibration_exclusion_reason"]


def test_late_capture_is_not_allowed_into_calibration() -> None:
    classified = classify_rows(pd.DataFrame([_row(captured_at_utc="2026-08-11T00:00:00+00:00")]))
    assert bool(classified.loc[0, "calibration_eligible"]) is False
    assert "late_capture" in classified.loc[0, "calibration_exclusion_reason"]


def test_eligible_rows_filters_and_audit_counts_reasons() -> None:
    frame = pd.DataFrame([
        _row(),
        _row(probability_semantics="legacy"),
        _row(actual_strikeouts=None),
    ])
    eligible = eligible_rows(frame)
    assert len(eligible) == 1
    audit = audit_summary(classify_rows(frame))
    assert set(audit["Exclusion_Reason"]) == {"probability_semantics", "unresolved"}
    assert set(audit["Eligible_Rows"]) == {1}
    assert set(audit["Total_Rows"]) == {3}

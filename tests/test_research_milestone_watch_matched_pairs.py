from __future__ import annotations

import pandas as pd

from training.research_milestone_watch import build_milestone_watch


def _row(*, breadth_label: str) -> dict[str, object]:
    return {
        "Lane": "Input Quality v2 · Strikeouts" if breadth_label == "MATCHED PAIRS" else "Synthetic Breadth Lane",
        "Category": "INPUT_QUALITY" if breadth_label == "MATCHED PAIRS" else "TEST",
        "Status": "LEARNING",
        "Current_Starts": 0,
        "Required_Starts": 20,
        "Starts_Remaining": 20,
        "Required_Days": None,
        "Days_Remaining": None,
        "Breadth_Label": breadth_label,
        "Current_Breadth": 0,
        "Required_Breadth": 20,
        "Breadth_Remaining": 20,
        "Secondary_Progress": "frozen evidence contract",
        "Ready_For_Manual_Review": False,
        "Recommended_Action": "KEEP_LEARNING",
        "Source_Reason": "synthetic reason",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "No_Auto_Promotion": True,
        "Source_Version": "synthetic-v1",
    }


def test_identical_matched_pair_sample_and_breadth_requirement_is_displayed_once() -> None:
    result = build_milestone_watch(pd.DataFrame([_row(breadth_label="MATCHED PAIRS")])).iloc[0]
    assert result["Primary_Gate_State"] == "PRIMARY_DIMENSIONS_BLOCKED"
    assert result["Blocking_Dimensions"] == "MATCHED PAIRS=20"
    assert int(result["Starts_Remaining"]) == 20
    assert int(result["Breadth_Remaining"]) == 20


def test_equal_numeric_requirements_do_not_collapse_other_breadth_dimensions() -> None:
    result = build_milestone_watch(pd.DataFrame([_row(breadth_label="OPPONENTS")])).iloc[0]
    assert result["Primary_Gate_State"] == "PRIMARY_DIMENSIONS_BLOCKED"
    assert result["Blocking_Dimensions"] == "STARTS=20|OPPONENTS=20"

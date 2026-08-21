from __future__ import annotations

import pandas as pd

from training.research_manual_review_packet import build_manual_review_packet

REFRESH = "2026-08-21T22:55:00+00:00"


def _center() -> pd.DataFrame:
    return pd.DataFrame([{
        "Lane": "Example Lane",
        "Source_Path": "data/example_gate.csv",
    }])


def _history(previous_direction: str) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Observed_At_UTC": "2026-08-20T22:55:00+00:00",
            "Event_Type": "BASELINE_CAPTURE",
            "Lane": "Example Lane",
            "Category": "TEST",
            "Status": "INCONCLUSIVE",
            "Evidence_Direction": previous_direction,
            "Current_Starts": 40,
            "Required_Starts": 60,
            "Ready_For_Manual_Review": False,
            "Recommended_Action": "KEEP_LEARNING",
            "Report_Only": True,
            "Production_Authority": "NONE",
            "No_Auto_Promotion": True,
            "Source_Version": "example-v1",
        },
        {
            "Observed_At_UTC": REFRESH,
            "Event_Type": "EVIDENCE_CHANGE",
            "Lane": "Example Lane",
            "Category": "TEST",
            "Status": "INCONCLUSIVE",
            "Evidence_Direction": "HURTING",
            "Current_Starts": 41,
            "Required_Starts": 60,
            "Ready_For_Manual_Review": False,
            "Recommended_Action": "KEEP_LEARNING",
            "Report_Only": True,
            "Production_Authority": "NONE",
            "No_Auto_Promotion": True,
            "Source_Version": "example-v1",
        },
    ])


def _digest(direction: str, *, changed: bool = True) -> pd.DataFrame:
    return pd.DataFrame([{
        "Refresh_At_UTC": REFRESH,
        "Lane": "Example Lane",
        "Category": "TEST",
        "Previous_Status": "INCONCLUSIVE",
        "Status": "INCONCLUSIVE",
        "Status_Changed": False,
        "Evidence_Direction_Changed": changed,
        "Progress_Changed": False,
        "Readiness_Changed": False,
        "Action_Changed": False,
        "Source_Version_Changed": False,
        "Evidence_Direction": direction,
        "Current_Starts": 41,
        "Required_Starts": 60,
        "Starts_Remaining": 19,
        "Current_Days": None,
        "Required_Days": None,
        "Days_Remaining": None,
        "Breadth_Label": "",
        "Current_Breadth": None,
        "Required_Breadth": None,
        "Breadth_Remaining": None,
        "Secondary_Progress": "",
        "Ready_For_Manual_Review": False,
        "Recommended_Action": "KEEP_LEARNING",
        "Source_Reason": "source-owned",
        "Change_Summary": "Evidence_Direction:SUPPORTED->HURTING",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "No_Auto_Promotion": True,
        "Control_Violation": False,
        "Source_Version": "example-v1",
    }])


def test_supportive_to_hurting_direction_flip_opens_manual_review_packet() -> None:
    packet = build_manual_review_packet(_digest("HURTING"), _history("SUPPORTED"), _center(), REFRESH)
    assert len(packet) == 1
    row = packet.iloc[0]
    assert row["Review_Trigger"] == "EVIDENCE_DIRECTION_FLIP"
    assert row["Previous_Evidence_Direction"] == "SUPPORTED"
    assert row["Evidence_Direction"] == "HURTING"
    assert bool(row["Human_Review_Required"])
    assert not bool(row["Automatic_Decision_Allowed"])
    assert row["Production_Authority"] == "NONE"


def test_hurting_to_supportive_direction_flip_is_also_reviewed() -> None:
    history = _history("HURTING")
    history.loc[1, "Evidence_Direction"] = "SUPPORTED"
    packet = build_manual_review_packet(_digest("SUPPORTED"), history, _center(), REFRESH)
    assert len(packet) == 1
    assert packet.iloc[0]["Review_Trigger"] == "EVIDENCE_DIRECTION_FLIP"


def test_numeric_direction_movement_does_not_create_review_spam() -> None:
    history = _history("relative_mae=+1.0%; win_share=53.0%")
    history.loc[1, "Evidence_Direction"] = "relative_mae=+1.2%; win_share=53.5%"
    digest = _digest("relative_mae=+1.2%; win_share=53.5%")
    digest.loc[0, "Change_Summary"] = "Evidence_Direction:relative_mae=+1.0%->relative_mae=+1.2%"
    packet = build_manual_review_packet(digest, history, _center(), REFRESH)
    assert packet.empty


def test_same_polarity_label_change_does_not_trigger_direction_review() -> None:
    history = _history("SUPPORTED")
    history.loc[1, "Evidence_Direction"] = "STRONG EVIDENCE"
    packet = build_manual_review_packet(_digest("STRONG EVIDENCE"), history, _center(), REFRESH)
    assert packet.empty

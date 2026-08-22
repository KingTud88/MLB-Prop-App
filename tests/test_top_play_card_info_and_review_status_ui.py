from pathlib import Path

import pandas as pd

from engine.research_promotion_scoreboard import _closed_human_review_lookup


def test_top_play_cards_use_compact_card_info_control():
    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")
    assert "apply_card_info_theme()" in source
    assert 'card_info_popover(top_play_explanation(play_row), key=f"top-play-{rank}")' in source
    assert 'label=f"ⓘ WHY IS THIS #{rank}?"' not in source
    assert "CARD_INFO_GEOMETRIC_V5" in Path("engine/card_explainability.py").read_text(encoding="utf-8")


def test_closed_human_review_overlay_uses_queue_without_rewriting_source_status(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame(
        [
            {
                "Lane": "Projection Crusher Shadow",
                "Review_Status": "CLOSED_BY_HUMAN",
                "Reviewed_At_UTC": "2026-08-22T05:27:51+00:00",
                "Review_Notes": "Manual review complete: HOLD; preserve negative evidence.",
            },
            {
                "Lane": "Projection Underperformer Shadow",
                "Review_Status": "CLOSED_BY_HUMAN",
                "Reviewed_At_UTC": "2026-08-22T05:27:51+00:00",
                "Review_Notes": "Manual review complete: prospective preregistration candidate only; no production change.",
            },
            {
                "Lane": "K Ladder Reliability Shadow",
                "Review_Status": "CLOSED_BY_HUMAN",
                "Reviewed_At_UTC": "2026-08-22T05:27:51+00:00",
                "Review_Notes": "Manual review complete: retain report-only monitoring; no sportsbook-execution interpretation.",
            },
            {
                "Lane": "Still Pending Lane",
                "Review_Status": "PENDING_MANUAL_REVIEW",
                "Reviewed_At_UTC": "",
                "Review_Notes": "",
            },
        ]
    ).to_csv(data_dir / "research_manual_review_queue.csv", index=False)

    reviews = _closed_human_review_lookup(tmp_path)

    assert reviews["Projection Crusher Shadow"]["status"] == "CLOSED_BY_HUMAN"
    assert reviews["Projection Crusher Shadow"]["disposition"] == "HOLD"
    assert reviews["Projection Underperformer Shadow"]["disposition"] == "PROSPECTIVE PREREGISTRATION ONLY"
    assert reviews["K Ladder Reliability Shadow"]["disposition"] == "RETAIN REPORT-ONLY MONITORING"
    assert "Still Pending Lane" not in reviews

    source = Path("engine/research_promotion_scoreboard.py").read_text(encoding="utf-8")
    assert "Status is source-owned" in source
    assert "Human review · closed" in source
    assert "does not replace the source-owned status badge" in source

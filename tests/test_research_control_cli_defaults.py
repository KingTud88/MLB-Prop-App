from pathlib import Path


ALL_LANE = 'default="data/research_promotion_command_center.csv"'
LEGACY = 'default="data/research_evidence_command_center.csv"'


def test_research_control_cli_defaults_use_all_lane_promotion_center() -> None:
    for path in (
        Path("training/research_milestone_watch.py"),
        Path("training/research_evidence_history.py"),
        Path("training/research_manual_review_packet.py"),
    ):
        text = path.read_text(encoding="utf-8")
        assert ALL_LANE in text, path
        assert LEGACY not in text, path

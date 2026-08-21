from pathlib import Path


PACKET_MODULE = Path("training/research_manual_review_packet.py")


def test_manual_review_packet_cli_defaults_to_all_lane_promotion_center() -> None:
    text = PACKET_MODULE.read_text(encoding="utf-8")
    expected = 'parser.add_argument("--command-center", default="data/research_promotion_command_center.csv")'
    legacy = 'parser.add_argument("--command-center", default="data/research_evidence_command_center.csv")'
    assert expected in text
    assert legacy not in text

from __future__ import annotations

import warnings
from pathlib import Path

from training.research_promotion_command_center import build_promotion_command_center


def test_all_lane_command_center_build_has_no_futurewarning(tmp_path: Path) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        center = build_promotion_command_center(tmp_path)

    assert len(center) == 22
    assert center["Lane"].nunique() == 22
    assert not [item for item in caught if issubclass(item.category, FutureWarning)]

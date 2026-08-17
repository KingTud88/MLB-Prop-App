from __future__ import annotations

import numpy as np
import pandas as pd

from training.top_plays_postmortem import overlay_persisted_active_lines


def test_blank_nan_line_source_is_not_treated_as_real_market_evidence() -> None:
    history = pd.DataFrame({"game_pk": [4], "pitcher_id": [44]})
    archive = pd.DataFrame({
        "game_pk": [4],
        "pitcher_id": [44],
        "active_strikeout_line": [5.5],
        "active_strikeout_line_source": [np.nan],
    })
    out = overlay_persisted_active_lines(history, archive)
    assert pd.isna(out.loc[0, "active_strikeout_line"])
    assert out.loc[0, "active_strikeout_line_source"] == ""

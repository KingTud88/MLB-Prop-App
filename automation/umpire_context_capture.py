from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.umpire_context import (
    OBS_PATH,
    attach_pregame_umpire_context,
    load_observations,
    refresh_resolved_observations,
    save_observations,
)

ROOT = Path(__file__).resolve().parents[1]
PROJECTION_LOG = ROOT / "data" / "projection_log.csv"


def main() -> None:
    if not PROJECTION_LOG.exists():
        raise SystemExit("No projection log available for umpire context capture")
    frame = pd.read_csv(PROJECTION_LOG)
    observations = load_observations(OBS_PATH)
    observations, resolved_added = refresh_resolved_observations(frame, observations)
    save_observations(observations, OBS_PATH)
    pregame_attached = attach_pregame_umpire_context(frame, observations)
    frame.to_csv(PROJECTION_LOG, index=False)
    auditable = 0
    if "umpire_candidate_status" in frame.columns:
        auditable = int(frame["umpire_candidate_status"].fillna("").astype(str).eq("AUDITABLE").sum())
    print(
        f"umpire_observations={len(observations)} resolved_added={resolved_added} "
        f"pregame_attached={pregame_attached} auditable_snapshots={auditable}"
    )


if __name__ == "__main__":
    main()

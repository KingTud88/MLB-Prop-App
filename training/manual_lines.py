from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import csv
import math
from typing import Any

from training.github_bet_store import save_bet


@dataclass
class ManualLine:
    player: str
    game_date: str
    line: float
    side: str
    american_odds: int | None = None
    entered_at_utc: str | None = None


def american_to_implied_probability(odds: int | float | None) -> float | None:
    if odds is None:
        return None
    odds = float(odds)
    if odds == 0:
        return None
    return 100.0 / (odds + 100.0) if odds > 0 else (-odds) / ((-odds) + 100.0)


def analyze_manual_line(
    projection: float,
    simulation_over_probability: float,
    line: float,
    side: str,
    american_odds: int | None = None,
) -> dict[str, Any]:
    side = side.strip().lower()
    if side not in {"over", "under"}:
        raise ValueError("side must be 'over' or 'under'")
    model_probability = simulation_over_probability if side == "over" else 1.0 - simulation_over_probability
    implied = american_to_implied_probability(american_odds)
    edge = model_probability - implied if implied is not None else None
    return {
        "line": float(line),
        "side": side,
        "projection": float(projection),
        "model_probability": float(model_probability),
        "implied_probability": implied,
        "edge": edge,
    }


def confidence_tier(model_probability: float, edge: float | None) -> str:
    """Transparent provisional tier; historical calibration should replace thresholds later."""
    p = float(model_probability)
    e = float(edge) if edge is not None else 0.0
    if p >= 0.80 and e >= 0.05:
        return "High"
    if p >= 0.68 and e >= 0.03:
        return "Medium"
    if p >= 0.58 and e >= 0.01:
        return "Low"
    return "Pass"


def append_bet_log(path: str | Path, line: ManualLine, analysis: dict[str, Any], actual_strikeouts: float | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        **asdict(line),
        "entered_at_utc": line.entered_at_utc or datetime.now(timezone.utc).isoformat(),
        **analysis,
        "confidence": confidence_tier(analysis["model_probability"], analysis.get("edge")),
        "actual_strikeouts": actual_strikeouts,
    }
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(record.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(record)

    # Also persist remotely so bets survive Streamlit restarts/redeploys.
    save_bet(record)

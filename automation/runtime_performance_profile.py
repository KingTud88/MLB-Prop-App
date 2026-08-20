from __future__ import annotations

import argparse
import cProfile
import json
import pstats
import statistics
from pathlib import Path
from time import perf_counter
from typing import Callable

import numpy as np

from engine.projection_engine import ProjectionEngine

PROFILE_VERSION = "runtime-performance-profile-v1"
DIAGNOSTIC_AUTHORITY = "NONE"
DEFAULT_DRAWS = 25_000
DEFAULT_REPEATS = 3
DEFAULT_WARMUPS = 1
DEFAULT_TOP_HOTSPOTS = 12
PROFILE_LINES = tuple(float(x) for x in range(3, 11))


def canonical_features() -> dict[str, float]:
    """Return deterministic, market-free inputs for local CPU profiling only."""
    return {
        "pitcher_k_pct": 0.250,
        "opponent_k_pct": 0.224,
        "handedness_factor": 1.0,
        "arsenal_factor": 1.0,
        "park_factor": 1.0,
        "umpire_factor": 1.0,
        "weather_factor": 1.0,
        "expected_bf": 23.0,
        "bf_sd": 3.5,
        "rest_factor": 1.0,
        "historical_k_sd": 2.0,
        "historical_games": 12.0,
        "lineup_batters": 9.0,
        "arsenal_sample_size": 0.0,
        "weather_available": 0.0,
        "umpire_available": 0.0,
    }


def _measure(call: Callable[[], object], repeats: int) -> dict[str, float | int]:
    samples_ms: list[float] = []
    for _ in range(max(1, int(repeats))):
        started = perf_counter()
        call()
        samples_ms.append((perf_counter() - started) * 1000.0)
    array = np.asarray(samples_ms, dtype=float)
    return {
        "runs": int(len(samples_ms)),
        "median_ms": float(statistics.median(samples_ms)),
        "mean_ms": float(array.mean()),
        "p95_ms": float(np.percentile(array, 95)),
        "min_ms": float(array.min()),
        "max_ms": float(array.max()),
    }


def _profile_hotspots(call: Callable[[], object], top_n: int) -> list[dict[str, object]]:
    profiler = cProfile.Profile()
    profiler.enable()
    call()
    profiler.disable()
    stats = pstats.Stats(profiler)
    rows: list[dict[str, object]] = []
    for (filename, line, function), values in sorted(
        stats.stats.items(),
        key=lambda item: float(item[1][3]),
        reverse=True,
    )[: max(1, int(top_n))]:
        primitive_calls, total_calls, total_time, cumulative_time, _ = values
        rows.append(
            {
                "function": str(function),
                "file": Path(str(filename)).name,
                "line": int(line),
                "primitive_calls": int(primitive_calls),
                "total_calls": int(total_calls),
                "self_ms": float(total_time * 1000.0),
                "cumulative_ms": float(cumulative_time * 1000.0),
            }
        )
    return rows


def build_profile(
    *,
    draws: int = DEFAULT_DRAWS,
    repeats: int = DEFAULT_REPEATS,
    warmups: int = DEFAULT_WARMUPS,
    top_hotspots: int = DEFAULT_TOP_HOTSPOTS,
) -> dict[str, object]:
    """Profile the existing local K projection path without changing it.

    The profiler does not make network requests, does not alter production
    settings, and deliberately defines no pass/fail latency threshold because
    absolute timings depend on runner hardware and current projection-log size.
    """
    draws = max(1_000, int(draws))
    repeats = max(1, int(repeats))
    warmups = max(0, int(warmups))
    top_hotspots = max(1, int(top_hotspots))
    features = canonical_features()
    engine = ProjectionEngine(simulation_weight=0.50, seed=9000)

    project_call = lambda: engine.project(features, draws=draws, lines=PROFILE_LINES)
    simulation_call = lambda: engine.simulate_game(features, draws=draws)
    math_call = lambda: engine.mathematical_projection(features)
    calibration_call = lambda: ProjectionEngine._historical_calibration(PROFILE_LINES)

    for _ in range(warmups):
        project_call()

    components = {
        "simulation": _measure(simulation_call, repeats),
        "mathematical": _measure(math_call, repeats),
        "historical_calibration": _measure(calibration_call, repeats),
        "total_projection": _measure(project_call, repeats),
    }
    representative = project_call()
    hotspots = _profile_hotspots(project_call, top_hotspots)

    return {
        "profile_version": PROFILE_VERSION,
        "diagnostic_authority": DIAGNOSTIC_AUTHORITY,
        "draws": draws,
        "repeats": repeats,
        "warmups": warmups,
        "lines": list(PROFILE_LINES),
        "features": features,
        "components": components,
        "representative_projection": {
            "ensemble_mean": float(representative.ensemble_mean),
            "simulation_mean": float(representative.simulation_mean),
            "mathematical_mean": float(representative.mathematical_mean),
            "data_quality": float(representative.data_quality),
        },
        "hotspots": hotspots,
        "notes": [
            "Diagnostic only; no production activation or optimization authority.",
            "No sportsbook or live market request is part of this profile.",
            "Weather factor is fixed neutral and remains informational-only.",
            "Absolute milliseconds are runner-dependent; compare component share and hotspot shape before proposing optimization.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile the existing local StrikeOut King K projection CPU path.")
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--top-hotspots", type=int, default=DEFAULT_TOP_HOTSPOTS)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = build_profile(
        draws=args.draws,
        repeats=args.repeats,
        warmups=args.warmups,
        top_hotspots=args.top_hotspots,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

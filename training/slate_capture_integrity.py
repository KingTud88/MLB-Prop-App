from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from automation.daily_projection_runner import schedule

ROOT = Path(__file__).resolve().parents[1]
PROJECTION_LOG = ROOT / "data" / "projection_log.csv"
OBSERVATION_LOG = ROOT / "data" / "starter_observation_log.csv"
HANDEDNESS_CONTEXT = ROOT / "data" / "handedness_matchup_effective_context.csv"
PITCH_ARSENAL_CONTEXT = ROOT / "data" / "pitch_arsenal_context_log.csv"
BATTER_WHIFF_CONTEXT = ROOT / "data" / "batter_pitch_whiff_context_log.csv"
PITCH_MIX_SCORE_LOG = ROOT / "data" / "pitch_mix_whiff_score_log.csv"
EASTERN = ZoneInfo("America/New_York")
AUDIT_VERSION = "slate-capture-integrity-v2-research-context"
RESEARCH_LAYERS = (
    "handedness",
    "pitch_arsenal",
    "batter_whiff",
    "pitch_mix_score",
)


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _keys(frame: pd.DataFrame, day: str) -> set[tuple[int, int]]:
    if frame.empty or not {"game_pk", "pitcher_id"}.issubset(frame.columns):
        return set()
    work = frame.copy()
    if "game_date" in work.columns:
        work = work.loc[work["game_date"].astype(str).eq(str(day))].copy()
    game_pk = pd.to_numeric(work["game_pk"], errors="coerce")
    pitcher_id = pd.to_numeric(work["pitcher_id"], errors="coerce")
    ready = game_pk.notna() & pitcher_id.notna()
    return {(int(g), int(p)) for g, p in zip(game_pk[ready], pitcher_id[ready])}


def _score_eligibility(frame: pd.DataFrame, day: str) -> dict[tuple[int, int], str]:
    if frame.empty or not {"game_pk", "pitcher_id"}.issubset(frame.columns):
        return {}
    work = frame.copy()
    if "game_date" in work.columns:
        work = work.loc[work["game_date"].astype(str).eq(str(day))].copy()
    game_pk = pd.to_numeric(work["game_pk"], errors="coerce")
    pitcher_id = pd.to_numeric(work["pitcher_id"], errors="coerce")
    ready = game_pk.notna() & pitcher_id.notna()
    work = work.loc[ready].copy()
    if work.empty:
        return {}

    output: dict[tuple[int, int], str] = {}
    for _, row in work.iterrows():
        key = (int(row["game_pk"]), int(row["pitcher_id"]))
        if "audit_eligible" not in work.columns or pd.isna(row.get("audit_eligible")):
            status = "UNKNOWN"
        else:
            status = "ELIGIBLE" if _truthy(row.get("audit_eligible")) else "INELIGIBLE"
        # Exact-context score capture is append-only. If multiple pregame contexts
        # exist for one starter, keep the strongest informational status for this
        # slate-level coverage audit without changing any evaluation lineage.
        previous = output.get(key)
        if previous == "ELIGIBLE" or status == "ELIGIBLE":
            output[key] = "ELIGIBLE"
        elif previous == "INELIGIBLE" or status == "INELIGIBLE":
            output[key] = "INELIGIBLE"
        else:
            output[key] = "UNKNOWN"
    return output


def build_audit(
    day: str,
    *,
    announced: list[dict[str, object]] | None = None,
    projections: pd.DataFrame | None = None,
    observations: pd.DataFrame | None = None,
    handedness: pd.DataFrame | None = None,
    pitch_arsenal: pd.DataFrame | None = None,
    batter_whiff: pd.DataFrame | None = None,
    pitch_mix_scores: pd.DataFrame | None = None,
) -> pd.DataFrame:
    announced = schedule(day) if announced is None else announced
    projections = _load(PROJECTION_LOG) if projections is None else projections.copy()
    observations = _load(OBSERVATION_LOG) if observations is None else observations.copy()
    handedness = _load(HANDEDNESS_CONTEXT) if handedness is None else handedness.copy()
    pitch_arsenal = _load(PITCH_ARSENAL_CONTEXT) if pitch_arsenal is None else pitch_arsenal.copy()
    batter_whiff = _load(BATTER_WHIFF_CONTEXT) if batter_whiff is None else batter_whiff.copy()
    pitch_mix_scores = _load(PITCH_MIX_SCORE_LOG) if pitch_mix_scores is None else pitch_mix_scores.copy()

    projected_keys = _keys(projections, day)
    observed_keys = _keys(observations, day)
    research_keys = {
        "handedness": _keys(handedness, day),
        "pitch_arsenal": _keys(pitch_arsenal, day),
        "batter_whiff": _keys(batter_whiff, day),
        "pitch_mix_score": _keys(pitch_mix_scores, day),
    }
    score_eligibility = _score_eligibility(pitch_mix_scores, day)

    rows: list[dict[str, object]] = []
    for starter in announced:
        key = (int(starter.get("game_pk", 0) or 0), int(starter.get("pitcher_id", 0) or 0))
        if key in projected_keys:
            capture_status = "PROJECTED"
        elif key in observed_keys:
            capture_status = "HISTORY_ONLY"
        else:
            capture_status = "MISSING"

        research_expected = capture_status == "PROJECTED"
        missing_layers = [layer for layer in RESEARCH_LAYERS if research_expected and key not in research_keys[layer]]
        if not research_expected:
            research_status = "NOT_REQUIRED"
        elif missing_layers:
            research_status = "PARTIAL"
        else:
            research_status = "COMPLETE"

        def layer_status(layer: str) -> str:
            if not research_expected:
                return "NOT_REQUIRED"
            return "CAPTURED" if key in research_keys[layer] else "MISSING"

        rows.append({
            "game_date": day,
            "game_pk": key[0],
            "pitcher_id": key[1],
            "player": starter.get("player", "Unknown"),
            "team": starter.get("team", "UNK"),
            "opponent": starter.get("opponent", "UNK"),
            "game_time": starter.get("game_time", ""),
            "schedule_status": starter.get("status", ""),
            "capture_status": capture_status,
            "research_capture_status": research_status,
            "handedness_capture": layer_status("handedness"),
            "pitch_arsenal_capture": layer_status("pitch_arsenal"),
            "batter_whiff_capture": layer_status("batter_whiff"),
            "pitch_mix_score_capture": layer_status("pitch_mix_score"),
            "pitch_mix_score_eligibility": (
                score_eligibility.get(key, "UNKNOWN") if research_expected and key in research_keys["pitch_mix_score"]
                else ("MISSING" if research_expected else "NOT_REQUIRED")
            ),
            "missing_research_layers": "|".join(missing_layers),
            "audit_version": AUDIT_VERSION,
        })
    return pd.DataFrame(rows)


def _failures(report: pd.DataFrame) -> pd.DataFrame:
    if report.empty:
        return report
    base_missing = report["capture_status"].eq("MISSING")
    research_missing = report["research_capture_status"].eq("PARTIAL")
    return report.loc[base_missing | research_missing].copy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report-only audit of announced starter projection and frozen research-context capture coverage"
    )
    parser.add_argument("--date", default=datetime.now(EASTERN).date().isoformat())
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "slate_capture_integrity.csv")
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args()

    report = build_audit(str(args.date))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)

    if report.empty:
        print(f"date={args.date} announced=0")
        return

    capture_counts = report["capture_status"].value_counts().to_dict()
    research_counts = report["research_capture_status"].value_counts().to_dict()
    failures = _failures(report)
    print(report.to_string(index=False))
    print(
        f"date={args.date} announced={len(report)} "
        f"capture_counts={capture_counts} research_counts={research_counts}"
    )
    if not failures.empty:
        print("capture integrity failures:")
        print(
            failures[
                [
                    "player", "team", "opponent", "game_pk", "pitcher_id",
                    "capture_status", "research_capture_status", "missing_research_layers",
                ]
            ].to_string(index=False)
        )
        if args.fail_on_missing:
            raise SystemExit(2)


if __name__ == "__main__":
    main()

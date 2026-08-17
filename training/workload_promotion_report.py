from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.workload_backtest import build_backtest
from training.workload_bias_controlled_backtest import attach_bias_controlled_tight_candidate
from training.workload_tight_backtest import attach_tight_only_candidate
from training.workload_v24_backtest import attach_v24_candidate
from training.workload_v25_metric_gate_backtest import attach_v25_candidate

REPORT_VERSION = "workload-promotion-report-v1"
PRODUCTION_AUTHORITY = "NONE"
REQUIRED_SEASONS = (2024, 2025, 2026)
METRICS = ("pitches", "bf", "outs")
VERSION_COLUMNS = {
    "global-v2": "candidate_{metric}",
    "tight-v2.2": "tight_candidate_{metric}",
    "tight-v2.3": "bias_controlled_{metric}",
    "tight-v2.4": "v24_candidate_{metric}",
    "tight-v2.5": "v25_candidate_{metric}",
}
VERSION_ORDER = tuple(VERSION_COLUMNS)
MIN_CHANGED_STARTS = 30
PROMOTE_MIN_RELATIVE_MAE = 0.005
PROMOTE_MIN_WIN_SHARE = 0.55
HOLD_MIN_POOLED_RELATIVE_MAE = 0.0025
HOLD_MIN_MAE_BETTER_SEASONS = 2


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def attach_version_chain(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach every report-only workload candidate to the same replay rows."""
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()
    work = attach_tight_only_candidate(frame.copy())
    work = attach_bias_controlled_tight_candidate(work)
    work = attach_v24_candidate(work)
    work = attach_v25_candidate(work)
    return work


def season_metric_evidence(
    frame: pd.DataFrame,
    *,
    season: int,
    metric: str,
    version: str,
) -> dict[str, object]:
    if version not in VERSION_COLUMNS:
        raise ValueError(f"Unknown workload candidate: {version}")
    metric = str(metric).lower()
    actual = _numeric(frame, f"actual_{metric}")
    live = _numeric(frame, f"workload_{metric}")
    candidate = _numeric(frame, VERSION_COLUMNS[version].format(metric=metric))
    ready = actual.notna() & live.notna() & candidate.notna()
    changed = ready & (candidate - live).abs().gt(1e-12)

    if not ready.any():
        return {
            "Season": int(season),
            "Metric": metric.upper(),
            "Version": version,
            "Evaluated_Starts": 0,
            "Changed_Starts": 0,
            "Live_MAE": float("nan"),
            "Candidate_MAE": float("nan"),
            "Relative_MAE_vs_Live": float("nan"),
            "Candidate_Win_Share_vs_Live": float("nan"),
            "Live_Bias": float("nan"),
            "Candidate_Bias": float("nan"),
            "Sample_Gate": False,
            "MAE_Gate": False,
            "Win_Gate": False,
            "Bias_Gate": False,
            "Cell_Result": "FAIL",
            "Reasons": "missing",
            "Report_Version": REPORT_VERSION,
        }

    a = actual[ready].astype(float)
    b = live[ready].astype(float)
    c = candidate[ready].astype(float)
    b_err = b - a
    c_err = c - a
    live_mae = float(b_err.abs().mean())
    cand_mae = float(c_err.abs().mean())
    relative = float((live_mae - cand_mae) / live_mae) if live_mae > 0 else float("nan")
    live_bias = float(b_err.mean())
    cand_bias = float(c_err.mean())
    changed_n = int(changed.sum())
    if changed_n:
        win_share = float(
            (
                (candidate[changed].astype(float) - actual[changed].astype(float)).abs()
                < (live[changed].astype(float) - actual[changed].astype(float)).abs()
            ).mean()
        )
    else:
        win_share = float("nan")

    sample_gate = changed_n >= MIN_CHANGED_STARTS
    mae_gate = bool(np.isfinite(relative) and relative >= PROMOTE_MIN_RELATIVE_MAE)
    win_gate = bool(np.isfinite(win_share) and win_share >= PROMOTE_MIN_WIN_SHARE)
    bias_gate = bool(abs(cand_bias) <= abs(live_bias) + 1e-12)

    reasons: list[str] = []
    if not sample_gate:
        reasons.append("sample")
    if not mae_gate:
        reasons.append("mae")
    if not win_gate:
        reasons.append("win_share")
    if not bias_gate:
        reasons.append("bias")

    return {
        "Season": int(season),
        "Metric": metric.upper(),
        "Version": version,
        "Evaluated_Starts": int(ready.sum()),
        "Changed_Starts": changed_n,
        "Live_MAE": live_mae,
        "Candidate_MAE": cand_mae,
        "Relative_MAE_vs_Live": relative,
        "Candidate_Win_Share_vs_Live": win_share,
        "Live_Bias": live_bias,
        "Candidate_Bias": cand_bias,
        "Sample_Gate": sample_gate,
        "MAE_Gate": mae_gate,
        "Win_Gate": win_gate,
        "Bias_Gate": bias_gate,
        "Cell_Result": "PASS" if not reasons else "FAIL",
        "Reasons": "|".join(reasons),
        "Report_Version": REPORT_VERSION,
    }


def build_evidence(projection_log: pd.DataFrame, seasons: tuple[int, ...] = REQUIRED_SEASONS) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for season in seasons:
        detail = build_backtest(projection_log, target_season=int(season))
        if detail.empty:
            for metric in METRICS:
                for version in VERSION_ORDER:
                    rows.append(
                        season_metric_evidence(
                            pd.DataFrame(),
                            season=int(season),
                            metric=metric,
                            version=version,
                        )
                    )
            continue
        work = attach_version_chain(detail)
        for metric in METRICS:
            for version in VERSION_ORDER:
                rows.append(
                    season_metric_evidence(
                        work,
                        season=int(season),
                        metric=metric,
                        version=version,
                    )
                )
    return pd.DataFrame(rows)


def _weighted_metric(group: pd.DataFrame, value_col: str) -> float:
    values = pd.to_numeric(group.get(value_col), errors="coerce")
    weights = pd.to_numeric(group.get("Evaluated_Starts"), errors="coerce").fillna(0)
    ready = values.notna() & weights.gt(0)
    if not ready.any():
        return float("nan")
    return float(np.average(values[ready].astype(float), weights=weights[ready].astype(float)))


def _version_decision_rows(evidence: pd.DataFrame, metric: str) -> list[dict[str, object]]:
    metric_rows = evidence.loc[evidence["Metric"].astype(str).eq(str(metric).upper())].copy()
    rows: list[dict[str, object]] = []
    for version in VERSION_ORDER:
        group = metric_rows.loc[metric_rows["Version"].astype(str).eq(version)].copy()
        by_season = {int(row["Season"]): row for _, row in group.iterrows()}
        missing = [season for season in REQUIRED_SEASONS if season not in by_season]
        pass_count = int(group["Cell_Result"].astype(str).eq("PASS").sum())
        pooled_live = _weighted_metric(group, "Live_MAE")
        pooled_candidate = _weighted_metric(group, "Candidate_MAE")
        pooled_relative = (
            float((pooled_live - pooled_candidate) / pooled_live)
            if np.isfinite(pooled_live) and pooled_live > 0 and np.isfinite(pooled_candidate)
            else float("nan")
        )
        better_seasons = int(
            (
                pd.to_numeric(group.get("Relative_MAE_vs_Live"), errors="coerce")
                .fillna(-np.inf)
                .gt(0.0)
            ).sum()
        )
        fully_passed = not missing and pass_count == len(REQUIRED_SEASONS)
        rows.append(
            {
                "Version": version,
                "Pooled_Live_MAE": pooled_live,
                "Pooled_Candidate_MAE": pooled_candidate,
                "Pooled_Relative_MAE": pooled_relative,
                "Passing_Seasons": pass_count,
                "MAE_Better_Seasons": better_seasons,
                "Fully_Passed": fully_passed,
            }
        )
    return rows


def build_decisions(evidence: pd.DataFrame) -> pd.DataFrame:
    decisions: list[dict[str, object]] = []
    for metric in (m.upper() for m in METRICS):
        version_rows = _version_decision_rows(evidence, metric)
        qualifiers = [row for row in version_rows if bool(row["Fully_Passed"])]
        if qualifiers:
            chosen = min(
                qualifiers,
                key=lambda row: (
                    float(row["Pooled_Candidate_MAE"])
                    if np.isfinite(float(row["Pooled_Candidate_MAE"]))
                    else float("inf"),
                    VERSION_ORDER.index(str(row["Version"])),
                ),
            )
            decision = "PROMOTE"
            reasons = ""
        else:
            viable = [
                row for row in version_rows
                if np.isfinite(float(row["Pooled_Candidate_MAE"]))
            ]
            chosen = min(
                viable,
                key=lambda row: (
                    float(row["Pooled_Candidate_MAE"]),
                    VERSION_ORDER.index(str(row["Version"])),
                ),
            ) if viable else {
                "Version": "NONE",
                "Pooled_Live_MAE": float("nan"),
                "Pooled_Candidate_MAE": float("nan"),
                "Pooled_Relative_MAE": float("nan"),
                "Passing_Seasons": 0,
                "MAE_Better_Seasons": 0,
                "Fully_Passed": False,
            }
            pooled_relative = float(chosen["Pooled_Relative_MAE"])
            if (
                np.isfinite(pooled_relative)
                and pooled_relative >= HOLD_MIN_POOLED_RELATIVE_MAE
                and int(chosen["MAE_Better_Seasons"]) >= HOLD_MIN_MAE_BETTER_SEASONS
            ):
                decision = "HOLD"
            else:
                decision = "REJECT"

            chosen_rows = evidence.loc[
                evidence["Metric"].astype(str).eq(metric)
                & evidence["Version"].astype(str).eq(str(chosen["Version"]))
            ].copy()
            failures: list[str] = []
            for _, row in chosen_rows.sort_values("Season").iterrows():
                if str(row.get("Cell_Result")) != "PASS":
                    reason = str(row.get("Reasons") or "gate")
                    failures.append(f"{int(row['Season'])}:{reason}")
            missing_seasons = sorted(
                set(REQUIRED_SEASONS)
                - set(pd.to_numeric(chosen_rows.get("Season"), errors="coerce").dropna().astype(int))
            )
            failures.extend(f"{season}:missing" for season in missing_seasons)
            reasons = ";".join(failures)

        decisions.append(
            {
                "Metric": metric,
                "Recommended_Version": str(chosen["Version"]),
                "Decision": decision,
                "Pooled_Live_MAE": float(chosen["Pooled_Live_MAE"]),
                "Pooled_Candidate_MAE": float(chosen["Pooled_Candidate_MAE"]),
                "Pooled_Relative_MAE": float(chosen["Pooled_Relative_MAE"]),
                "Passing_Seasons": int(chosen["Passing_Seasons"]),
                "Required_Seasons": len(REQUIRED_SEASONS),
                "MAE_Better_Seasons": int(chosen["MAE_Better_Seasons"]),
                "Reasons": reasons,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "Report_Only": True,
                "Report_Version": REPORT_VERSION,
            }
        )
    return pd.DataFrame(decisions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Final report-only workload candidate promotion review.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--evidence", type=Path, default=Path("data/workload_promotion_evidence.csv"))
    parser.add_argument("--decisions", type=Path, default=Path("data/workload_promotion_decisions.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("Projection log is missing or empty")

    evidence = build_evidence(history)
    decisions = build_decisions(evidence)
    for path in (args.evidence, args.decisions):
        path.parent.mkdir(parents=True, exist_ok=True)
    evidence.to_csv(args.evidence, index=False)
    decisions.to_csv(args.decisions, index=False)
    print(decisions.to_string(index=False))
    print(f"report={REPORT_VERSION} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import math

import numpy as np
import pandas as pd

MIN_DECISION_OBSERVATIONS = 20
STRONG_DECISION_OBSERVATIONS = 30

PROBABILITY_EDGES = [0.0, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90, 1.000001]
PROBABILITY_LABELS = ["<50%", "50–54%", "55–59%", "60–64%", "65–69%", "70–74%", "75–79%", "80–89%", "90%+"]
QUALITY_EDGES = [0.0, 60.0, 70.0, 80.0, 90.0, 101.0]
QUALITY_LABELS = ["<60", "60–69", "70–79", "80–89", "90+"]

REPORT_COLUMNS = [
    "Market",
    "Probability Band",
    "Quality Band",
    "Settled Legs",
    "Hits",
    "Hit Rate",
    "Avg Model Probability",
    "Calibration Gap",
    "Brier Score",
    "Wilson Lower 95%",
    "Lift vs Top 5",
    "Decision Evidence",
    "Reason",
]


def _number(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def probability_band(value: object) -> str:
    number = _number(value)
    if number is None:
        return "UNKNOWN"
    clipped = float(np.clip(number, 0.0, 1.0))
    band = pd.cut(
        pd.Series([clipped]),
        bins=PROBABILITY_EDGES,
        labels=PROBABILITY_LABELS,
        right=False,
        include_lowest=True,
    ).iloc[0]
    return "UNKNOWN" if pd.isna(band) else str(band)


def quality_band(value: object) -> str:
    number = _number(value)
    if number is None:
        return "UNKNOWN"
    clipped = float(np.clip(number, 0.0, 100.0))
    band = pd.cut(
        pd.Series([clipped]),
        bins=QUALITY_EDGES,
        labels=QUALITY_LABELS,
        right=False,
        include_lowest=True,
    ).iloc[0]
    return "UNKNOWN" if pd.isna(band) else str(band)


def wilson_lower_bound(hits: int, trials: int, z: float = 1.96) -> float | None:
    n = int(trials)
    if n <= 0:
        return None
    p = float(hits) / float(n)
    z2 = float(z) ** 2
    denominator = 1.0 + z2 / n
    center = p + z2 / (2.0 * n)
    margin = float(z) * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    return float(np.clip((center - margin) / denominator, 0.0, 1.0))


def _evidence_label(
    *,
    n: int,
    hit_rate: float,
    avg_probability: float,
    gap: float,
    brier: float,
    lower_bound: float,
    min_observations: int,
    strong_observations: int,
) -> tuple[str, str]:
    if n < int(min_observations):
        return (
            "LEARNING",
            f"Need {int(min_observations)} settled walk-forward legs in this exact market/probability/quality segment; {n} available.",
        )

    underperformance = (
        n >= int(strong_observations)
        and (
            hit_rate < 0.50
            or hit_rate < avg_probability - 0.15
            or brier > 0.30
        )
    )
    if underperformance:
        return (
            "UNDERPERFORMING",
            "Enough segment-level evidence exists and realized results are materially worse than the model probability profile.",
        )

    strong = (
        n >= int(strong_observations)
        and hit_rate >= 0.60
        and gap <= 0.08
        and brier <= 0.23
        and lower_bound >= 0.50
    )
    if strong:
        return (
            "STRONG EVIDENCE",
            "This segment has enough walk-forward volume and strong hit-rate, calibration, Brier, and confidence-bound support.",
        )

    supported = (
        hit_rate >= 0.52
        and hit_rate >= avg_probability - 0.08
        and gap <= 0.10
        and brier <= 0.26
    )
    if supported:
        return (
            "SUPPORTED",
            "This segment has enough walk-forward volume and its realized results broadly support the model probability profile.",
        )

    return (
        "CAUTION",
        "This segment has enough observations to evaluate, but the evidence is not strong enough for a supported label.",
    )


def decision_tier_report(
    walk_forward: pd.DataFrame,
    *,
    min_observations: int = MIN_DECISION_OBSERVATIONS,
    strong_observations: int = STRONG_DECISION_OBSERVATIONS,
) -> pd.DataFrame:
    """Evaluate model-only Top-5 decision segments after outcomes settle.

    Input is expected to come from ``walk_forward_top5``. Sportsbook price, book,
    edge, and user bet selections are intentionally ignored. The report studies
    only the model recommendation, its data quality, and the eventual result.
    """
    if walk_forward.empty:
        return pd.DataFrame(columns=REPORT_COLUMNS)

    data = walk_forward.copy()
    hit_series = data.get("Hit", pd.Series(index=data.index, dtype=object))
    data = data.loc[hit_series.notna()].copy()
    if data.empty:
        return pd.DataFrame(columns=REPORT_COLUMNS)

    data["Model Probability"] = pd.to_numeric(data.get("Model Probability"), errors="coerce")
    data["Data Quality"] = pd.to_numeric(data.get("Data Quality"), errors="coerce")
    data = data.dropna(subset=["Model Probability", "Data Quality"])
    if data.empty:
        return pd.DataFrame(columns=REPORT_COLUMNS)

    data["Model Probability"] = data["Model Probability"].clip(0.0, 1.0)
    data["Data Quality"] = data["Data Quality"].clip(0.0, 100.0)
    data["Probability Band"] = pd.cut(
        data["Model Probability"],
        bins=PROBABILITY_EDGES,
        labels=PROBABILITY_LABELS,
        right=False,
        include_lowest=True,
    )
    data["Quality Band"] = pd.cut(
        data["Data Quality"],
        bins=QUALITY_EDGES,
        labels=QUALITY_LABELS,
        right=False,
        include_lowest=True,
    )
    data = data.dropna(subset=["Probability Band", "Quality Band"])
    if data.empty:
        return pd.DataFrame(columns=REPORT_COLUMNS)

    overall_hit_rate = float(data["Hit"].astype(float).mean())
    rows: list[dict[str, object]] = []
    group_columns = ["Market", "Probability Band", "Quality Band"]
    for (market, prob_band, dq_band), group in data.groupby(group_columns, observed=True, sort=False):
        y = group["Hit"].astype(float).to_numpy()
        p = group["Model Probability"].to_numpy(float)
        n = int(len(group))
        hits = int(y.sum())
        hit_rate = float(y.mean())
        avg_probability = float(p.mean())
        gap = float(abs(hit_rate - avg_probability))
        brier = float(np.mean((p - y) ** 2))
        lower = float(wilson_lower_bound(hits, n) or 0.0)
        evidence, reason = _evidence_label(
            n=n,
            hit_rate=hit_rate,
            avg_probability=avg_probability,
            gap=gap,
            brier=brier,
            lower_bound=lower,
            min_observations=int(min_observations),
            strong_observations=int(strong_observations),
        )
        rows.append({
            "Market": str(market),
            "Probability Band": str(prob_band),
            "Quality Band": str(dq_band),
            "Settled Legs": n,
            "Hits": hits,
            "Hit Rate": hit_rate,
            "Avg Model Probability": avg_probability,
            "Calibration Gap": gap,
            "Brier Score": brier,
            "Wilson Lower 95%": lower,
            "Lift vs Top 5": float(hit_rate - overall_hit_rate),
            "Decision Evidence": evidence,
            "Reason": reason,
        })

    report = pd.DataFrame(rows, columns=REPORT_COLUMNS)
    if report.empty:
        return report
    evidence_order = {
        "STRONG EVIDENCE": 0,
        "SUPPORTED": 1,
        "LEARNING": 2,
        "CAUTION": 3,
        "UNDERPERFORMING": 4,
    }
    report["_evidence_order"] = report["Decision Evidence"].map(evidence_order).fillna(9)
    report = report.sort_values(
        ["_evidence_order", "Settled Legs", "Market", "Probability Band", "Quality Band"],
        ascending=[True, False, True, True, True],
    ).drop(columns=["_evidence_order"])
    return report.reset_index(drop=True)


def decision_profile_for_play(play: pd.Series | dict[str, object], report: pd.DataFrame) -> dict[str, object]:
    market = str(play.get("Market", ""))
    prob_band = probability_band(play.get("Model Probability"))
    dq_band = quality_band(play.get("Data Quality"))
    base = {
        "Decision Evidence": "LEARNING",
        "Decision Sample": 0,
        "Tier Hit Rate": None,
        "Tier Avg Probability": None,
        "Tier Calibration Gap": None,
        "Tier Brier": None,
        "Tier Wilson Lower 95%": None,
        "Tier Lift vs Top 5": None,
        "Decision Probability Band": prob_band,
        "Decision Quality Band": dq_band,
        "Decision Reason": "No settled walk-forward legs are available yet for this exact market/probability/quality segment.",
    }
    if report.empty:
        return base

    matched = report.loc[
        report["Market"].astype(str).eq(market)
        & report["Probability Band"].astype(str).eq(prob_band)
        & report["Quality Band"].astype(str).eq(dq_band)
    ]
    if matched.empty:
        return base
    row = matched.iloc[0]
    return {
        "Decision Evidence": str(row.get("Decision Evidence", "LEARNING")),
        "Decision Sample": int(row.get("Settled Legs", 0) or 0),
        "Tier Hit Rate": _number(row.get("Hit Rate")),
        "Tier Avg Probability": _number(row.get("Avg Model Probability")),
        "Tier Calibration Gap": _number(row.get("Calibration Gap")),
        "Tier Brier": _number(row.get("Brier Score")),
        "Tier Wilson Lower 95%": _number(row.get("Wilson Lower 95%")),
        "Tier Lift vs Top 5": _number(row.get("Lift vs Top 5")),
        "Decision Probability Band": prob_band,
        "Decision Quality Band": dq_band,
        "Decision Reason": str(row.get("Reason", "")),
    }


def attach_decision_profiles(plays: pd.DataFrame, report: pd.DataFrame) -> pd.DataFrame:
    """Attach descriptive decision evidence without changing Top-5 order or eligibility."""
    if plays.empty:
        return plays.copy()
    out = plays.copy()
    profiles = [decision_profile_for_play(row, report) for _, row in out.iterrows()]
    profile_frame = pd.DataFrame(profiles, index=out.index)
    for column in profile_frame.columns:
        out[column] = profile_frame[column]
    return out

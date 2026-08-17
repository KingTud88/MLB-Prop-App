from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from engine.decision_learning import MIN_DECISION_OBSERVATIONS, STRONG_DECISION_OBSERVATIONS, wilson_lower_bound

ACCOUNTABILITY_VERSION = "top-plays-accountability-v1"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

MARGIN_PERCENT_EDGES = [0.0, 0.10, 0.15, 0.20, float("inf")]
MARGIN_PERCENT_LABELS = ["<10%", "10–14%", "15–19%", "20%+"]

SUMMARY_COLUMNS = [
    "Dimension",
    "Segment",
    "Settled Legs",
    "Observed Days",
    "Hits",
    "Hit Rate",
    "Avg Model Probability",
    "Calibration Gap",
    "Brier Score",
    "Wilson Lower 95%",
    "Lift vs Overall",
    "Avg Projection Margin",
    "Avg Margin % of Line",
    "Avg Outcome Margin",
    "Evidence",
    "Reason",
    "Report Only",
    "Production Authority",
    "Accountability Version",
]


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def margin_percent(projection: object, line: object) -> float | None:
    proj = _num(projection)
    market_line = _num(line)
    if proj is None or market_line is None or abs(market_line) < 1e-12:
        return None
    return float(abs(proj - market_line) / abs(market_line))


def margin_percent_band(value: object) -> str:
    number = _num(value)
    if number is None or number < 0:
        return "UNKNOWN"
    band = pd.cut(
        pd.Series([number]),
        bins=MARGIN_PERCENT_EDGES,
        labels=MARGIN_PERCENT_LABELS,
        right=False,
        include_lowest=True,
    ).iloc[0]
    return "UNKNOWN" if pd.isna(band) else str(band)


def enrich_detail(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty:
        return pd.DataFrame() if detail is None else detail.copy()
    out = detail.copy()
    if "Projection Margin" not in out.columns:
        out["Projection Margin"] = out.apply(
            lambda row: None
            if _num(row.get("Projection")) is None or _num(row.get("Line")) is None
            else abs(float(_num(row.get("Projection"))) - float(_num(row.get("Line")))),
            axis=1,
        )
    out["Margin % of Line"] = out.apply(lambda row: margin_percent(row.get("Projection"), row.get("Line")), axis=1)
    out["Margin % Band"] = out["Margin % of Line"].map(margin_percent_band)
    return out


def _evidence_label(
    *,
    n: int,
    hit_rate: float,
    avg_probability: float,
    gap: float,
    brier: float,
    lower_bound: float,
) -> tuple[str, str]:
    """Use the same evidence thresholds as the existing decision-learning layer."""
    if n < int(MIN_DECISION_OBSERVATIONS):
        return (
            "LEARNING",
            f"Need {int(MIN_DECISION_OBSERVATIONS)} settled real-line Top Plays in this segment; {n} available. Directional only.",
        )

    underperformance = (
        n >= int(STRONG_DECISION_OBSERVATIONS)
        and (hit_rate < 0.50 or hit_rate < avg_probability - 0.15 or brier > 0.30)
    )
    if underperformance:
        return (
            "UNDERPERFORMING",
            "Enough real-line Top Plays exist and realized results are materially worse than the model probability profile.",
        )

    strong = (
        n >= int(STRONG_DECISION_OBSERVATIONS)
        and hit_rate >= 0.60
        and gap <= 0.08
        and brier <= 0.23
        and lower_bound >= 0.50
    )
    if strong:
        return (
            "STRONG EVIDENCE",
            "Enough real-line Top Plays exist with strong hit-rate, calibration, Brier, and confidence-bound support.",
        )

    supported = hit_rate >= 0.52 and hit_rate >= avg_probability - 0.08 and gap <= 0.10 and brier <= 0.26
    if supported:
        return (
            "SUPPORTED",
            "Enough real-line Top Plays exist and realized results broadly support the model probability profile.",
        )

    return (
        "CAUTION",
        "Enough observations exist to evaluate this segment, but the evidence is not strong enough for a supported label.",
    )


def _summary_row(data: pd.DataFrame, dimension: str, segment: str, overall_rate: float | None) -> dict[str, object]:
    settled = data.loc[data.get("Hit", pd.Series(index=data.index, dtype=object)).notna()].copy()
    probabilities = pd.to_numeric(settled.get("Model Probability"), errors="coerce")
    valid = probabilities.notna()
    settled = settled.loc[valid].copy()
    probabilities = probabilities.loc[valid].clip(0.0, 1.0)
    n = int(len(settled))
    observed_days = int(settled.get("Postmortem Date", pd.Series(dtype=object)).dropna().astype(str).nunique()) if n else 0

    if n:
        y = settled["Hit"].astype(float).to_numpy()
        p = probabilities.to_numpy(float)
        hits = int(y.sum())
        hit_rate = float(y.mean())
        avg_probability = float(p.mean())
        gap = float(abs(hit_rate - avg_probability))
        brier = float(np.mean((p - y) ** 2))
        lower = float(wilson_lower_bound(hits, n) or 0.0)
        projection_margin = float(pd.to_numeric(settled.get("Projection Margin"), errors="coerce").mean())
        margin_pct = float(pd.to_numeric(settled.get("Margin % of Line"), errors="coerce").mean())
        outcome_margin = float(pd.to_numeric(settled.get("Outcome Margin"), errors="coerce").mean())
        evidence, reason = _evidence_label(
            n=n,
            hit_rate=hit_rate,
            avg_probability=avg_probability,
            gap=gap,
            brier=brier,
            lower_bound=lower,
        )
    else:
        hits = 0
        hit_rate = avg_probability = gap = brier = lower = float("nan")
        projection_margin = margin_pct = outcome_margin = float("nan")
        evidence = "LEARNING"
        reason = f"Need {int(MIN_DECISION_OBSERVATIONS)} settled real-line Top Plays in this segment; 0 available."

    lift = float(hit_rate - overall_rate) if overall_rate is not None and pd.notna(hit_rate) else float("nan")
    return {
        "Dimension": dimension,
        "Segment": segment,
        "Settled Legs": n,
        "Observed Days": observed_days,
        "Hits": hits,
        "Hit Rate": hit_rate,
        "Avg Model Probability": avg_probability,
        "Calibration Gap": gap,
        "Brier Score": brier,
        "Wilson Lower 95%": lower,
        "Lift vs Overall": lift,
        "Avg Projection Margin": projection_margin,
        "Avg Margin % of Line": margin_pct,
        "Avg Outcome Margin": outcome_margin,
        "Evidence": evidence,
        "Reason": reason,
        "Report Only": REPORT_ONLY,
        "Production Authority": PRODUCTION_AUTHORITY,
        "Accountability Version": ACCOUNTABILITY_VERSION,
    }


def build_accountability_summary(detail: pd.DataFrame) -> pd.DataFrame:
    data = enrich_detail(detail)
    if data.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    settled = data.loc[data.get("Hit", pd.Series(index=data.index, dtype=object)).notna()].copy()
    overall_rate = float(settled["Hit"].astype(float).mean()) if not settled.empty else None

    rows = [_summary_row(data, "OVERALL", "ALL REAL-LINE TOP PLAYS", overall_rate)]
    specs = (
        ("RANK", "Rank"),
        ("MARKET", "Market"),
        ("SIDE", "Side"),
        ("STATUS", "Status"),
        ("PROBABILITY BAND", "Probability Band"),
        ("QUALITY BAND", "Quality Band"),
        ("MARGIN % BAND", "Margin % Band"),
        ("LINE SOURCE", "Line Source"),
        ("LINEUP STATE", "Lineup State"),
        ("WEATHER RISK", "Weather Risk"),
        ("MARKET HEALTH", "Historical Market Health"),
    )
    for dimension, column in specs:
        if column not in data.columns:
            continue
        values = data[column].fillna("UNKNOWN").astype(str)
        for segment in sorted(values.unique()):
            rows.append(_summary_row(data.loc[values.eq(segment)], dimension, segment, overall_rate))
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def _pct(value: object) -> str:
    number = _num(value)
    return "—" if number is None else f"{number:.1%}"


def build_findings(detail: pd.DataFrame, summary: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    data = enrich_detail(detail)
    findings: list[dict[str, object]] = []

    overall = summary.loc[summary.get("Dimension", pd.Series(dtype=str)).eq("OVERALL")]
    if overall.empty:
        overall_n = 0
        overall_hit = overall_prob = overall_gap = None
        overall_evidence = "LEARNING"
    else:
        row = overall.iloc[0]
        overall_n = int(row.get("Settled Legs", 0) or 0)
        overall_hit = _num(row.get("Hit Rate"))
        overall_prob = _num(row.get("Avg Model Probability"))
        overall_gap = _num(row.get("Calibration Gap"))
        overall_evidence = str(row.get("Evidence", "LEARNING"))

    observed_days = 0
    total_days = 0
    if coverage is not None and not coverage.empty:
        total_days = int(coverage.get("Date", pd.Series(dtype=object)).astype(str).nunique())
        real_rows = pd.to_numeric(coverage.get("Rows With Any Persisted Real Line"), errors="coerce").fillna(0)
        observed_days = int(coverage.loc[real_rows.gt(0), "Date"].astype(str).nunique())

    findings.append({
        "Finding": "OVERALL ACCOUNTABILITY STATE",
        "Status": overall_evidence,
        "Evidence": f"{overall_n} settled real-line Top Plays across {observed_days} observed real-line slate(s)",
        "Conclusion": (
            f"Observed hit rate {_pct(overall_hit)} versus average model probability {_pct(overall_prob)} "
            f"(calibration gap {_pct(overall_gap)}). Current sample is too small to change ranking or trust labels."
        ),
    })
    findings.append({
        "Finding": "REAL-LINE COVERAGE",
        "Status": "LEARNING" if observed_days < 5 else "MONITOR",
        "Evidence": f"{observed_days} of {total_days} frozen slate date(s) currently contain persisted real lines",
        "Conclusion": "Older slates without observed real lines are intentionally excluded rather than reconstructed from model defaults.",
    })

    markets = set(data.get("Market", pd.Series(dtype=str)).dropna().astype(str)) if not data.empty else set()
    for market in ("Strikeouts", "Total Outs", "Hits Allowed"):
        group = data.loc[data.get("Market", pd.Series(index=data.index, dtype=str)).astype(str).eq(market)] if not data.empty else pd.DataFrame()
        settled_n = int(group.get("Hit", pd.Series(dtype=object)).notna().sum()) if not group.empty else 0
        findings.append({
            "Finding": f"{market.upper()} SAMPLE",
            "Status": "LEARNING",
            "Evidence": f"{settled_n} settled Top Play leg(s)",
            "Conclusion": "No market-specific conclusion is allowed yet." if market in markets else "No persisted real-line Top Play evidence exists for this market yet.",
        })

    for dimension, column, name in (
        ("RANK", "Rank", "RANK ORDER"),
        ("LINEUP STATE", "Lineup State", "LINEUP CONTEXT"),
        ("WEATHER RISK", "Weather Risk", "WEATHER CONTEXT"),
        ("LINE SOURCE", "Line Source", "LINE-SOURCE CONTEXT"),
    ):
        unique = data.get(column, pd.Series(dtype=object)).dropna().astype(str).nunique() if not data.empty else 0
        max_n = 0
        if not summary.empty:
            subset = summary.loc[summary["Dimension"].eq(dimension)]
            if not subset.empty:
                max_n = int(pd.to_numeric(subset["Settled Legs"], errors="coerce").fillna(0).max())
        conclusion = (
            "Only one observed state exists, so this context cannot be compared yet."
            if unique <= 1
            else f"Multiple states are present, but the largest segment has only {max_n} settled leg(s); keep learning."
        )
        findings.append({
            "Finding": name,
            "Status": "LEARNING",
            "Evidence": f"{unique} observed state(s); largest segment {max_n} settled leg(s)",
            "Conclusion": conclusion,
        })

    margin_rows = summary.loc[summary.get("Dimension", pd.Series(dtype=str)).eq("MARGIN % BAND")] if not summary.empty else pd.DataFrame()
    max_margin_n = int(pd.to_numeric(margin_rows.get("Settled Legs"), errors="coerce").fillna(0).max()) if not margin_rows.empty else 0
    findings.append({
        "Finding": "MODEL-vs-LINE MARGIN",
        "Status": "LEARNING",
        "Evidence": f"Largest relative-margin band has {max_margin_n} settled leg(s)",
        "Conclusion": "Projection/line separation is now tracked relative to the market line, but no margin band is large enough to trust yet.",
    })

    out = pd.DataFrame(findings)
    out["Report Only"] = REPORT_ONLY
    out["Production Authority"] = PRODUCTION_AUTHORITY
    out["Accountability Version"] = ACCOUNTABILITY_VERSION
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only Top Plays accountability report.")
    parser.add_argument("--detail", type=Path, default=Path("data/top_plays_postmortem_detail.csv"))
    parser.add_argument("--coverage", type=Path, default=Path("data/top_plays_postmortem_coverage.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/top_plays_accountability_summary.csv"))
    parser.add_argument("--findings", type=Path, default=Path("data/top_plays_accountability_findings.csv"))
    args = parser.parse_args()

    detail = pd.read_csv(args.detail) if args.detail.exists() else pd.DataFrame()
    coverage = pd.read_csv(args.coverage) if args.coverage.exists() else pd.DataFrame()
    summary = build_accountability_summary(detail)
    findings = build_findings(detail, summary, coverage)
    for path, frame in ((args.summary, summary), (args.findings, findings)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    overall = summary.loc[summary.get("Dimension", pd.Series(dtype=str)).eq("OVERALL")]
    if not overall.empty:
        row = overall.iloc[0]
        print(
            "settled_legs={} observed_days={} hit_rate={} avg_probability={} evidence={}".format(
                int(row["Settled Legs"]),
                int(row["Observed Days"]),
                _pct(row["Hit Rate"]),
                _pct(row["Avg Model Probability"]),
                row["Evidence"],
            )
        )
    print(f"version={ACCOUNTABILITY_VERSION} production_authority={PRODUCTION_AUTHORITY} report_only={REPORT_ONLY}")


if __name__ == "__main__":
    main()

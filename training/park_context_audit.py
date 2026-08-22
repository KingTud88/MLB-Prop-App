from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests

VERSION = "park-context-audit-v1-preregistered-report-only"
PREREGISTRATION_VERSION = "park-context-preregistration-v1"
SOURCE_VERSION = "baseball-savant-statcast-park-factors-prior-season-3yr-v1"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_PROJECTION_ADJUSTMENT = True
NO_AUTO_PROMOTION = True
AUTOMATIC_DECISION_ALLOWED = False
SUPPORTING_DIAGNOSTIC_ONLY = True
PROMOTION_ROW_REGISTERED = False

PREREGISTERED_GAME_DATE = "2026-08-22"
FIRST_ELIGIBLE_GAME_DATE = "2026-08-23"
ROLLING_YEARS = 3
SOURCE_BAT_SIDE = "BOTH"
SOURCE_CONDITION = "ALL"
SOURCE_PARK_SCOPE = "MLB"
MIN_SOURCE_VENUES = 25
MIN_SOURCE_COVERAGE = 0.95
MIN_RESOLVED_STARTS = 60
MIN_RESOLVED_DAYS = 10
MIN_DISTINCT_VENUES = 12
MIN_HIGH_BUCKET_STARTS = 12
MIN_LOW_BUCKET_STARTS = 12
HIGH_FACTOR_MIN = 104.0
LOW_FACTOR_MAX = 96.0

MARKETS = (
    {
        "Market": "K",
        "Projection_Column": "projection",
        "Actual_Column": "actual_strikeouts",
        "Factor_Column": "SO_Factor",
        "Statcast_Metric": "SO",
        "Expected_Direction": "POSITIVE",
        "Flat_Tolerance": 0.10,
        "Primary_Outcome": "actual_strikeouts - frozen_projection",
        "Selection_Basis": "Official Statcast SO park factor; higher-than-average SO parks are expected to have higher K residuals if venue adds incremental signal.",
    },
    {
        "Market": "H",
        "Projection_Column": "hits_projection",
        "Actual_Column": "actual_hits_allowed",
        "Factor_Column": "H_Factor",
        "Statcast_Metric": "H",
        "Expected_Direction": "POSITIVE",
        "Flat_Tolerance": 0.15,
        "Primary_Outcome": "actual_hits_allowed - frozen_hits_projection",
        "Selection_Basis": "Official Statcast H park factor; higher-than-average hit parks are expected to have higher Hits Allowed residuals if venue adds incremental signal.",
    },
    {
        "Market": "OUTS",
        "Projection_Column": "outs_projection",
        "Actual_Column": "actual_outs",
        "Factor_Column": "OBP_Factor",
        "Statcast_Metric": "OBP_EXPLORATORY_PROXY",
        "Expected_Direction": "NEGATIVE",
        "Flat_Tolerance": 0.25,
        "Primary_Outcome": "actual_outs - frozen_outs_projection",
        "Selection_Basis": "No official outs park factor exists in the selected Statcast table. Prior-season OBP park context is frozen as an exploratory proxy only; any signal requires a separate future challenger preregistration.",
    },
)

VENUE_ALIASES = {
    "uniqlo field at dodger stadium": "dodger stadium",
    "rate field": "guaranteed rate field",
    "daikin park": "minute maid park",
}

PREREGISTRATION_COLUMNS = [
    "Preregistration_Version", "Preregistered_Game_Date", "First_Eligible_Game_Date",
    "Market", "Statcast_Metric", "Source_Policy", "Source_Year_Rule", "Rolling_Years",
    "Source_Bat_Side", "Source_Condition", "Source_Park_Scope", "Primary_Outcome",
    "Primary_Effect", "Expected_Direction", "Low_Factor_Max", "High_Factor_Min",
    "Flat_Tolerance", "Min_Source_Coverage", "Min_Resolved_Starts", "Min_Resolved_Days",
    "Min_Distinct_Venues", "Min_Low_Bucket_Starts", "Min_High_Bucket_Starts",
    "Selection_Basis", "Outs_Model_Authority", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "No_Auto_Promotion", "Automatic_Decision_Allowed",
    "Supporting_Diagnostic_Only", "Promotion_Row_Registered",
]

SOURCE_COLUMNS = [
    "Source_Year", "Source_Window_Start_Year", "Source_Window_End_Year", "Venue",
    "Venue_Normalized", "H_Factor", "SO_Factor", "OBP_Factor", "BACON_Factor", "PA",
    "Source_URL", "Captured_At_UTC", "Source_SHA256", "Source_Version",
]

DETAIL_COLUMNS = [
    "Game_Date", "Game_PK", "Pitcher_ID", "Pitcher", "Team", "Opponent", "Venue",
    "Venue_Normalized", "Market", "Projection", "Actual", "Residual", "Source_Year",
    "Factor_Metric", "Park_Factor", "Factor_Delta", "Factor_Bucket", "Expected_Direction",
    "Source_URL", "Source_SHA256", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "Evaluation_Version",
]

SUMMARY_COLUMNS = [
    "Market", "Status", "Resolved_Starts", "Resolved_Days", "Distinct_Venues",
    "Source_Matched_Starts", "Source_Coverage", "Low_Bucket_Starts", "High_Bucket_Starts",
    "Low_Bucket_Mean_Residual", "High_Bucket_Mean_Residual", "High_Minus_Low_Mean_Residual",
    "Residual_Per_10_Factor_Points", "Residual_Factor_Correlation", "Evidence_Direction",
    "Expected_Direction", "Ready_For_Manual_Review", "Reason", "Recommended_Action",
    "First_Eligible_Game_Date", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "No_Auto_Promotion", "Automatic_Decision_Allowed",
    "Supporting_Diagnostic_Only", "Promotion_Row_Registered", "Evaluation_Version",
]

GATE_COLUMNS = [
    "Status", "Markets_Tracked", "Markets_Source_Ready", "Markets_Mature",
    "Markets_Ready_For_Manual_Review", "Recommended_Action", "Preregistered_Game_Date",
    "First_Eligible_Game_Date", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "No_Auto_Promotion", "Automatic_Decision_Allowed",
    "Supporting_Diagnostic_Only", "Promotion_Row_Registered", "Evaluation_Version",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_venue(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()
    return VENUE_ALIASES.get(text, text)


def source_year_for_game_date(value: object) -> int | None:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return int(ts.year) - 1


def statcast_source_url(source_year: int) -> str:
    return (
        "https://baseballsavant.mlb.com/leaderboard/statcast-park-factors"
        f"?batSide=&condition=All&parks=mlb&rolling={ROLLING_YEARS}"
        f"&stat=index_wOBA&type=year&year={int(source_year)}"
    )


def parse_embedded_statcast_data(html: str) -> list[dict[str, object]]:
    match = re.search(r"\bdata\s*=\s*(\[[\s\S]*?\])\s*;", str(html))
    if not match:
        raise ValueError("Statcast park-factor embedded data payload not found")
    payload = json.loads(match.group(1))
    if not isinstance(payload, list):
        raise ValueError("Statcast park-factor payload is not a list")
    return [row for row in payload if isinstance(row, dict)]


def _row_value(row: dict[str, object], *aliases: str) -> object:
    normalized = {str(key).strip().lower(): value for key, value in row.items()}
    for alias in aliases:
        key = alias.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def _number(value: object) -> float:
    return float(pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0])


def normalize_statcast_source(
    rows: Iterable[dict[str, object]],
    source_year: int,
    *,
    captured_at_utc: str | None = None,
) -> pd.DataFrame:
    captured = captured_at_utc or _utc_now()
    url = statcast_source_url(source_year)
    prepared: list[dict[str, object]] = []
    for row in rows:
        venue = _row_value(row, "venue_name", "venue")
        if not venue:
            continue
        prepared.append({
            "Source_Year": int(source_year),
            "Source_Window_Start_Year": int(source_year) - ROLLING_YEARS + 1,
            "Source_Window_End_Year": int(source_year),
            "Venue": str(venue).strip(),
            "Venue_Normalized": _normalize_venue(venue),
            "H_Factor": _number(_row_value(row, "index_hits", "index_h", "hits")),
            "SO_Factor": _number(_row_value(row, "index_so", "so")),
            "OBP_Factor": _number(_row_value(row, "index_obp", "obp")),
            "BACON_Factor": _number(_row_value(row, "index_bacon", "bacon")),
            "PA": _number(_row_value(row, "pa")),
            "Source_URL": url,
            "Captured_At_UTC": captured,
            "Source_SHA256": "",
            "Source_Version": SOURCE_VERSION,
        })
    source = pd.DataFrame(prepared, columns=SOURCE_COLUMNS)
    if source.empty:
        raise ValueError("Statcast park-factor payload contained no usable venue rows")
    required = ["H_Factor", "SO_Factor", "OBP_Factor"]
    if len(source) < MIN_SOURCE_VENUES or source[required].isna().any().any():
        raise ValueError("Statcast park-factor payload failed minimum venue/metric validation")
    canonical_cols = [
        "Source_Year", "Venue_Normalized", "H_Factor", "SO_Factor", "OBP_Factor",
        "BACON_Factor", "PA",
    ]
    canonical = source[canonical_cols].sort_values(["Source_Year", "Venue_Normalized"]).to_csv(index=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    source["Source_SHA256"] = digest
    return source.sort_values("Venue_Normalized").reset_index(drop=True)


def fetch_statcast_source(source_year: int, *, session: requests.Session | None = None) -> pd.DataFrame:
    client = session or requests.Session()
    response = client.get(
        statcast_source_url(source_year),
        headers={"Accept": "text/html", "User-Agent": "StrikeOutKing9000/park-context-research-v1"},
        timeout=20,
    )
    response.raise_for_status()
    return normalize_statcast_source(parse_embedded_statcast_data(response.text), source_year)


def build_preregistration() -> pd.DataFrame:
    rows = []
    for spec in MARKETS:
        rows.append({
            "Preregistration_Version": PREREGISTRATION_VERSION,
            "Preregistered_Game_Date": PREREGISTERED_GAME_DATE,
            "First_Eligible_Game_Date": FIRST_ELIGIBLE_GAME_DATE,
            "Market": spec["Market"],
            "Statcast_Metric": spec["Statcast_Metric"],
            "Source_Policy": "Baseball Savant Statcast Park Factors; prior completed season only; 3-year rolling; both batter sides; all conditions; MLB parks",
            "Source_Year_Rule": "game_year - 1",
            "Rolling_Years": ROLLING_YEARS,
            "Source_Bat_Side": SOURCE_BAT_SIDE,
            "Source_Condition": SOURCE_CONDITION,
            "Source_Park_Scope": SOURCE_PARK_SCOPE,
            "Primary_Outcome": spec["Primary_Outcome"],
            "Primary_Effect": "HIGH_FACTOR_MEAN_RESIDUAL_MINUS_LOW_FACTOR_MEAN_RESIDUAL",
            "Expected_Direction": spec["Expected_Direction"],
            "Low_Factor_Max": LOW_FACTOR_MAX,
            "High_Factor_Min": HIGH_FACTOR_MIN,
            "Flat_Tolerance": spec["Flat_Tolerance"],
            "Min_Source_Coverage": MIN_SOURCE_COVERAGE,
            "Min_Resolved_Starts": MIN_RESOLVED_STARTS,
            "Min_Resolved_Days": MIN_RESOLVED_DAYS,
            "Min_Distinct_Venues": MIN_DISTINCT_VENUES,
            "Min_Low_Bucket_Starts": MIN_LOW_BUCKET_STARTS,
            "Min_High_Bucket_Starts": MIN_HIGH_BUCKET_STARTS,
            "Selection_Basis": spec["Selection_Basis"],
            "Outs_Model_Authority": (
                "NONE; exploratory proxy cannot define or tune an Outs adjustment"
                if spec["Market"] == "OUTS" else "N/A"
            ),
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
            "No_Auto_Promotion": NO_AUTO_PROMOTION,
            "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
            "Supporting_Diagnostic_Only": SUPPORTING_DIAGNOSTIC_ONLY,
            "Promotion_Row_Registered": PROMOTION_ROW_REGISTERED,
        })
    return pd.DataFrame(rows, columns=PREREGISTRATION_COLUMNS)


def _source_lookup(source: pd.DataFrame) -> dict[tuple[int, str], pd.Series]:
    if source is None or source.empty:
        return {}
    required = {"Source_Year", "Venue_Normalized"}
    if not required.issubset(source.columns):
        return {}
    lookup: dict[tuple[int, str], pd.Series] = {}
    for _, row in source.iterrows():
        year = pd.to_numeric(pd.Series([row.get("Source_Year")]), errors="coerce").iloc[0]
        venue = _normalize_venue(row.get("Venue_Normalized") or row.get("Venue"))
        if pd.isna(year) or not venue:
            continue
        lookup[(int(year), venue)] = row
    return lookup


def _factor_bucket(value: float) -> str:
    if not np.isfinite(value):
        return "SOURCE_MISSING"
    if value <= LOW_FACTOR_MAX:
        return "LOW"
    if value >= HIGH_FACTOR_MIN:
        return "HIGH"
    return "NEUTRAL"


def build_forward_detail(history: pd.DataFrame, source: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    frame = history.copy()
    if "history_semantics" in frame.columns:
        current = frame["history_semantics"].astype(str).str.contains("starter", case=False, na=False)
        if current.any():
            frame = frame.loc[current].copy()
    dates = pd.to_datetime(frame.get("game_date"), errors="coerce")
    frame = frame.loc[dates.notna() & dates.ge(pd.Timestamp(FIRST_ELIGIBLE_GAME_DATE))].copy()
    if frame.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    frame["_game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
    frame["_source_year"] = frame["_game_date"].dt.year.astype(int) - 1
    frame["_venue_norm"] = frame.get("venue", pd.Series("", index=frame.index)).map(_normalize_venue)
    lookup = _source_lookup(source)

    rows: list[dict[str, object]] = []
    for spec in MARKETS:
        projection = pd.to_numeric(frame.get(spec["Projection_Column"]), errors="coerce")
        actual = pd.to_numeric(frame.get(spec["Actual_Column"]), errors="coerce")
        resolved = frame.loc[projection.notna() & actual.notna()].copy()
        if resolved.empty:
            continue
        for idx, row in resolved.iterrows():
            projection_value = float(projection.loc[idx])
            actual_value = float(actual.loc[idx])
            source_year = int(row["_source_year"])
            source_row = lookup.get((source_year, row["_venue_norm"]))
            factor = np.nan
            source_url = ""
            source_sha = ""
            if source_row is not None:
                factor = pd.to_numeric(pd.Series([source_row.get(spec["Factor_Column"])]), errors="coerce").iloc[0]
                source_url = str(source_row.get("Source_URL") or "")
                source_sha = str(source_row.get("Source_SHA256") or "")
            factor_value = float(factor) if pd.notna(factor) else np.nan
            rows.append({
                "Game_Date": row["_game_date"].date().isoformat(),
                "Game_PK": row.get("game_pk", pd.NA),
                "Pitcher_ID": row.get("pitcher_id", pd.NA),
                "Pitcher": str(row.get("player", "Unknown")),
                "Team": str(row.get("team", "")),
                "Opponent": str(row.get("opponent", "")),
                "Venue": str(row.get("venue", "")),
                "Venue_Normalized": row["_venue_norm"],
                "Market": spec["Market"],
                "Projection": projection_value,
                "Actual": actual_value,
                "Residual": actual_value - projection_value,
                "Source_Year": source_year,
                "Factor_Metric": spec["Statcast_Metric"],
                "Park_Factor": factor_value,
                "Factor_Delta": factor_value - 100.0 if np.isfinite(factor_value) else np.nan,
                "Factor_Bucket": _factor_bucket(factor_value),
                "Expected_Direction": spec["Expected_Direction"],
                "Source_URL": source_url,
                "Source_SHA256": source_sha,
                "Report_Only": REPORT_ONLY,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
                "Evaluation_Version": VERSION,
            })
    return pd.DataFrame(rows, columns=DETAIL_COLUMNS)


def _slope_and_corr(group: pd.DataFrame) -> tuple[float, float]:
    x = pd.to_numeric(group["Park_Factor"], errors="coerce")
    y = pd.to_numeric(group["Residual"], errors="coerce")
    valid = x.notna() & y.notna()
    x = x.loc[valid]
    y = y.loc[valid]
    if len(x) < 3 or x.nunique() < 2:
        return np.nan, np.nan
    x10 = (x - 100.0) / 10.0
    slope = float(np.polyfit(x10.to_numpy(float), y.to_numpy(float), 1)[0])
    corr = float(x.corr(y))
    return slope, corr


def _direction(effect: float, expected: str, tolerance: float, mature_buckets: bool) -> str:
    if not mature_buckets or not np.isfinite(effect):
        return "LEARNING"
    if abs(effect) < tolerance:
        return "FLAT"
    if expected == "POSITIVE":
        return "EXPECTED" if effect > 0 else "OPPOSITE"
    return "EXPECTED" if effect < 0 else "OPPOSITE"


def build_summary(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for spec in MARKETS:
        group = detail.loc[detail["Market"].eq(spec["Market"])].copy() if detail is not None and not detail.empty else pd.DataFrame(columns=DETAIL_COLUMNS)
        resolved = int(len(group))
        matched = group["Park_Factor"].notna() if resolved else pd.Series(dtype=bool)
        matched_count = int(matched.sum()) if resolved else 0
        coverage = float(matched_count / resolved) if resolved else 0.0
        matched_group = group.loc[matched].copy() if resolved else group
        dates = pd.to_datetime(matched_group.get("Game_Date"), errors="coerce") if matched_count else pd.Series(dtype="datetime64[ns]")
        days = int(dates.dt.date.nunique()) if matched_count else 0
        venues = int(matched_group.get("Venue_Normalized", pd.Series(dtype=object)).nunique()) if matched_count else 0
        low = matched_group.loc[matched_group["Factor_Bucket"].eq("LOW")]
        high = matched_group.loc[matched_group["Factor_Bucket"].eq("HIGH")]
        low_n, high_n = int(len(low)), int(len(high))
        low_mean = float(pd.to_numeric(low["Residual"], errors="coerce").mean()) if low_n else np.nan
        high_mean = float(pd.to_numeric(high["Residual"], errors="coerce").mean()) if high_n else np.nan
        effect = high_mean - low_mean if np.isfinite(low_mean) and np.isfinite(high_mean) else np.nan
        slope, corr = _slope_and_corr(matched_group)
        source_ready = resolved > 0 and coverage >= MIN_SOURCE_COVERAGE
        mature_counts = (
            resolved >= MIN_RESOLVED_STARTS
            and days >= MIN_RESOLVED_DAYS
            and venues >= MIN_DISTINCT_VENUES
            and low_n >= MIN_LOW_BUCKET_STARTS
            and high_n >= MIN_HIGH_BUCKET_STARTS
        )
        mature = source_ready and mature_counts
        evidence_direction = _direction(effect, spec["Expected_Direction"], float(spec["Flat_Tolerance"]), low_n >= MIN_LOW_BUCKET_STARTS and high_n >= MIN_HIGH_BUCKET_STARTS)
        if resolved == 0:
            status = "LEARNING"
            reason = f"No resolved starts on or after {FIRST_ELIGIBLE_GAME_DATE}."
        elif coverage < MIN_SOURCE_COVERAGE:
            status = "SOURCE_COVERAGE_INCOMPLETE"
            reason = f"Park-factor match coverage {coverage:.1%} is below frozen {MIN_SOURCE_COVERAGE:.0%}."
        elif mature:
            status = "READY_FOR_MANUAL_RESEARCH_REVIEW"
            reason = "Frozen forward maturity gates satisfied; source-owned evidence direction is ready for human review only."
        else:
            status = "LEARNING"
            reason = (
                f"Collect forward evidence: starts {resolved}/{MIN_RESOLVED_STARTS}, days {days}/{MIN_RESOLVED_DAYS}, "
                f"venues {venues}/{MIN_DISTINCT_VENUES}, low {low_n}/{MIN_LOW_BUCKET_STARTS}, high {high_n}/{MIN_HIGH_BUCKET_STARTS}."
            )
        if spec["Market"] == "OUTS":
            action = "COLLECT_EXPLORATORY_OBP_PARK_SIGNAL; SEPARATE_PREREGISTRATION_REQUIRED_BEFORE_ANY_OUTS_CHALLENGER"
        else:
            action = "COLLECT_FORWARD_PARK_RESIDUAL_EVIDENCE; NO_PRODUCTION_ADJUSTMENT"
        rows.append({
            "Market": spec["Market"],
            "Status": status,
            "Resolved_Starts": resolved,
            "Resolved_Days": days,
            "Distinct_Venues": venues,
            "Source_Matched_Starts": matched_count,
            "Source_Coverage": coverage,
            "Low_Bucket_Starts": low_n,
            "High_Bucket_Starts": high_n,
            "Low_Bucket_Mean_Residual": low_mean,
            "High_Bucket_Mean_Residual": high_mean,
            "High_Minus_Low_Mean_Residual": effect,
            "Residual_Per_10_Factor_Points": slope,
            "Residual_Factor_Correlation": corr,
            "Evidence_Direction": evidence_direction,
            "Expected_Direction": spec["Expected_Direction"],
            "Ready_For_Manual_Review": bool(mature),
            "Reason": reason,
            "Recommended_Action": action,
            "First_Eligible_Game_Date": FIRST_ELIGIBLE_GAME_DATE,
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
            "No_Auto_Promotion": NO_AUTO_PROMOTION,
            "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
            "Supporting_Diagnostic_Only": SUPPORTING_DIAGNOSTIC_ONLY,
            "Promotion_Row_Registered": PROMOTION_ROW_REGISTERED,
            "Evaluation_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def build_gate(summary: pd.DataFrame, source: pd.DataFrame) -> pd.DataFrame:
    source_ready = source is not None and not source.empty and source["Venue_Normalized"].nunique() >= MIN_SOURCE_VENUES
    statuses = summary.get("Status", pd.Series(dtype=object)).astype(str) if summary is not None else pd.Series(dtype=object)
    ready_count = int(summary.get("Ready_For_Manual_Review", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()) if summary is not None and not summary.empty else 0
    if not source_ready:
        status = "SOURCE_MISSING"
        action = "CAPTURE_PRIOR_COMPLETED_SEASON_STATCAST_PARK_FACTORS_THEN_COLLECT_FORWARD_EVIDENCE"
    elif ready_count > 0:
        status = "READY_FOR_MANUAL_RESEARCH_REVIEW"
        action = "MANUAL_RESEARCH_REVIEW_ONLY; NO_PRODUCTION_CHANGE"
    elif statuses.eq("SOURCE_COVERAGE_INCOMPLETE").any():
        status = "SOURCE_COVERAGE_INCOMPLETE"
        action = "FIX_VENUE_SOURCE_MAPPING_BEFORE_INTERPRETING_EVIDENCE"
    else:
        status = "LEARNING"
        action = "KEEP_FROZEN_AND_COLLECT_FORWARD_EVIDENCE"
    return pd.DataFrame([{
        "Status": status,
        "Markets_Tracked": len(MARKETS),
        "Markets_Source_Ready": int((summary["Source_Coverage"] >= MIN_SOURCE_COVERAGE).sum()) if summary is not None and not summary.empty else 0,
        "Markets_Mature": ready_count,
        "Markets_Ready_For_Manual_Review": ready_count,
        "Recommended_Action": action,
        "Preregistered_Game_Date": PREREGISTERED_GAME_DATE,
        "First_Eligible_Game_Date": FIRST_ELIGIBLE_GAME_DATE,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
        "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
        "Supporting_Diagnostic_Only": SUPPORTING_DIAGNOSTIC_ONLY,
        "Promotion_Row_Registered": PROMOTION_ROW_REGISTERED,
        "Evaluation_Version": VERSION,
    }], columns=GATE_COLUMNS)


def _read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=columns or [])


def refresh_missing_sources(history: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    dates = pd.to_datetime(history.get("game_date"), errors="coerce") if history is not None and not history.empty else pd.Series(dtype="datetime64[ns]")
    eligible = dates.loc[dates.notna() & dates.ge(pd.Timestamp(FIRST_ELIGIBLE_GAME_DATE))]
    needed_years = {int(pd.Timestamp(FIRST_ELIGIBLE_GAME_DATE).year) - 1}
    needed_years.update(int(year) - 1 for year in eligible.dt.year.unique())
    needed = sorted(needed_years)
    have = set(pd.to_numeric(existing.get("Source_Year"), errors="coerce").dropna().astype(int).tolist()) if existing is not None and not existing.empty else set()
    frames = [existing.copy()] if existing is not None and not existing.empty else []
    for source_year in needed:
        if source_year in have:
            continue
        frames.append(fetch_statcast_source(source_year))
    if not frames:
        return pd.DataFrame(columns=SOURCE_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(["Source_Year", "Venue_Normalized"], keep="last")
    return combined[SOURCE_COLUMNS].sort_values(["Source_Year", "Venue_Normalized"]).reset_index(drop=True)


def write_outputs(root: Path, *, refresh_source: bool = False) -> tuple[Path, Path, Path, Path, Path]:
    root = Path(root)
    data = root / "data"
    archive_path = data / "projection_archive.csv"
    source_path = data / "park_context_statcast_source.csv"
    prereg_path = data / "park_context_preregistration.csv"
    detail_path = data / "park_context_forward_detail.csv"
    summary_path = data / "park_context_forward_summary.csv"
    gate_path = data / "park_context_gate.csv"

    history = _read_csv(archive_path)
    source = _read_csv(source_path, SOURCE_COLUMNS)
    if refresh_source:
        source = refresh_missing_sources(history, source)

    prereg = build_preregistration()
    detail = build_forward_detail(history, source)
    summary = build_summary(detail)
    gate = build_gate(summary, source)

    prereg.to_csv(prereg_path, index=False)
    source.to_csv(source_path, index=False)
    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    gate.to_csv(gate_path, index=False)
    return prereg_path, source_path, detail_path, summary_path, gate_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run preregistered report-only park context research.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--refresh-missing-source", action="store_true")
    args = parser.parse_args()
    write_outputs(args.root, refresh_source=args.refresh_missing_source)


if __name__ == "__main__":
    main()

from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS

SIGNAL_VALIDATION_VERSION = "signals-v1"
MIN_PAIRED_OBSERVATIONS = 20

MARKET_SPECS = {
    "Strikeouts": ("projection", "actual_strikeouts", "k_range_low", "k_range_high"),
    "Hits Allowed": ("hits_projection", "actual_hits_allowed", "hits_range_low", "hits_range_high"),
    "Total Outs": ("outs_projection", "actual_outs", "outs_range_low", "outs_range_high"),
}

PAIRED_SIGNALS = {
    "Workload v1 upgrade": {
        "Strikeouts": "workload_preupgrade_projection",
        "Hits Allowed": "workload_preupgrade_hits_projection",
        "Total Outs": "workload_preupgrade_outs_projection",
    },
    "Confirmed lineup upgrade": {
        "Strikeouts": "lineup_preconfirm_projection",
        "Hits Allowed": "lineup_preconfirm_hits_projection",
    },
}


def _num_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _current_rows(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty or "history_semantics" not in history.columns:
        return history.iloc[0:0].copy()
    frame = history.loc[history["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)].copy()
    if "game_date" in frame.columns:
        frame["_game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
        sort_cols = ["_game_date"]
        if "captured_at_utc" in frame.columns:
            sort_cols.append("captured_at_utc")
        frame = frame.sort_values(sort_cols, na_position="last")
    return frame.reset_index(drop=True)


def _paired_status(n: int, relative_improvement: float | None, improved_share: float | None) -> tuple[str, str]:
    if n < MIN_PAIRED_OBSERVATIONS:
        return "LEARNING", f"Need {MIN_PAIRED_OBSERVATIONS} resolved paired outcomes; {n} available."
    rel = 0.0 if relative_improvement is None else float(relative_improvement)
    share = 0.5 if improved_share is None else float(improved_share)
    if rel >= 0.05 and share >= 0.55:
        return "HELPING", "Post-upgrade MAE is at least 5% better and a majority of paired starts improved."
    if rel <= -0.05 and share <= 0.45:
        return "HURTING", "Post-upgrade MAE is at least 5% worse and fewer than half of paired starts improved."
    return "MIXED", "Enough paired evidence exists, but the accuracy change is not consistently positive or negative."


def paired_signal_report(history: pd.DataFrame) -> pd.DataFrame:
    """Measure feature upgrades with same-game before/after projection pairs.

    This is deliberately stricter than comparing unrelated cohorts. A row is only
    eligible when the frozen snapshot preserves the pre-upgrade prediction, the
    post-upgrade prediction, and the final result for the same pitcher/game.
    Sportsbook data is never read.
    """
    columns = [
        "Signal", "Market", "Resolved Pairs", "Pre MAE", "Post MAE", "MAE Improvement",
        "Relative MAE Improvement", "Improved Starts", "Improved Share", "Pre Bias", "Post Bias",
        "Status", "Reason", "Validation Version",
    ]
    current = _current_rows(history)
    rows: list[dict[str, object]] = []
    for signal, market_pre_columns in PAIRED_SIGNALS.items():
        for market, pre_column in market_pre_columns.items():
            post_column, actual_column, _, _ = MARKET_SPECS[market]
            if current.empty:
                paired = pd.DataFrame()
            else:
                data = pd.DataFrame({
                    "pre": _num_series(current, pre_column),
                    "post": _num_series(current, post_column),
                    "actual": _num_series(current, actual_column),
                })
                paired = data.dropna(subset=["pre", "post", "actual"]).copy()
            n = int(len(paired))
            if n:
                pre_error = paired["actual"] - paired["pre"]
                post_error = paired["actual"] - paired["post"]
                pre_abs = pre_error.abs()
                post_abs = post_error.abs()
                pre_mae = float(pre_abs.mean())
                post_mae = float(post_abs.mean())
                improvement = float(pre_mae - post_mae)
                relative = None if pre_mae <= 1e-12 else float(improvement / pre_mae)
                improved = int((post_abs < pre_abs).sum())
                share = float(improved / n)
                pre_bias = float(pre_error.mean())
                post_bias = float(post_error.mean())
            else:
                pre_mae = post_mae = improvement = relative = share = pre_bias = post_bias = None
                improved = 0
            status, reason = _paired_status(n, relative, share)
            rows.append({
                "Signal": signal,
                "Market": market,
                "Resolved Pairs": n,
                "Pre MAE": pre_mae,
                "Post MAE": post_mae,
                "MAE Improvement": improvement,
                "Relative MAE Improvement": relative,
                "Improved Starts": improved,
                "Improved Share": share,
                "Pre Bias": pre_bias,
                "Post Bias": post_bias,
                "Status": status,
                "Reason": reason,
                "Validation Version": SIGNAL_VALIDATION_VERSION,
            })
    return pd.DataFrame(rows, columns=columns)


def _rest_band(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    out = pd.Series("UNKNOWN", index=values.index, dtype=object)
    out.loc[numeric.le(4)] = "SHORT ≤4d"
    out.loc[numeric.between(5, 7, inclusive="both")] = "STANDARD 5–7d"
    out.loc[numeric.ge(8)] = "EXTENDED 8d+"
    return out


def _matchup_k_band(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric.where(numeric <= 1.0, numeric / 100.0)
    out = pd.Series("UNKNOWN", index=values.index, dtype=object)
    out.loc[numeric.lt(0.20)] = "LOW K <20%"
    out.loc[numeric.between(0.20, 0.25, inclusive="left")] = "NORMAL K 20–24.9%"
    out.loc[numeric.ge(0.25)] = "HIGH K 25%+"
    return out


def _contact_band(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric.where(numeric <= 1.0, numeric / 100.0)
    out = pd.Series("UNKNOWN", index=values.index, dtype=object)
    out.loc[numeric.lt(0.21)] = "LOW H/PA <21%"
    out.loc[numeric.between(0.21, 0.25, inclusive="left")] = "NORMAL H/PA 21–24.9%"
    out.loc[numeric.ge(0.25)] = "HIGH H/PA 25%+"
    return out


def context_performance_report(history: pd.DataFrame) -> pd.DataFrame:
    """Describe model accuracy inside baseball context buckets.

    These are associations, not causal feature-credit claims. Weather is included
    explicitly as CONTEXT ONLY because it does not currently feed the forecast.
    """
    columns = ["Context", "Level", "Role", "Market", "Resolved", "MAE", "Bias", "80% Range Coverage", "Status"]
    current = _current_rows(history)
    if current.empty:
        return pd.DataFrame(columns=columns)

    dimensions: list[tuple[str, pd.Series, str]] = []
    if "lineup_source" in current.columns:
        dimensions.append(("Lineup Source", current["lineup_source"].fillna("UNKNOWN").astype(str), "MODEL INPUT"))
    if "leash_label" in current.columns:
        dimensions.append(("Workload Leash", current["leash_label"].fillna("UNKNOWN").astype(str), "MODEL INPUT"))
    if "days_since_last_start" in current.columns:
        dimensions.append(("Rest", _rest_band(current["days_since_last_start"]), "MODEL INPUT"))
    if "starter_history_source" in current.columns:
        dimensions.append(("History Source", current["starter_history_source"].fillna("UNKNOWN").astype(str), "MODEL INPUT"))
    if "opponent_k_pct" in current.columns:
        dimensions.append(("Opponent K Environment", _matchup_k_band(current["opponent_k_pct"]), "MODEL INPUT"))
    if "opponent_hit_rate" in current.columns:
        dimensions.append(("Opponent Contact Environment", _contact_band(current["opponent_hit_rate"]), "MODEL INPUT"))
    if "weather_delay_risk" in current.columns:
        dimensions.append(("Weather Delay Risk", current["weather_delay_risk"].fillna("UNKNOWN").astype(str), "CONTEXT ONLY"))

    rows: list[dict[str, object]] = []
    for context_name, levels, role in dimensions:
        for level in sorted(levels.dropna().astype(str).unique()):
            if level in {"", "UNKNOWN", "nan", "None"}:
                continue
            mask = levels.astype(str).eq(level)
            group = current.loc[mask]
            for market, (projection_col, actual_col, low_col, high_col) in MARKET_SPECS.items():
                projected = _num_series(group, projection_col)
                actual = _num_series(group, actual_col)
                valid = projected.notna() & actual.notna()
                n = int(valid.sum())
                if n:
                    error = actual[valid] - projected[valid]
                    mae = float(error.abs().mean())
                    bias = float(error.mean())
                else:
                    mae = bias = None
                low = _num_series(group, low_col)
                high = _num_series(group, high_col)
                range_valid = actual.notna() & low.notna() & high.notna()
                coverage = float(((actual[range_valid] >= low[range_valid]) & (actual[range_valid] <= high[range_valid])).mean()) if range_valid.any() else None
                rows.append({
                    "Context": context_name,
                    "Level": level,
                    "Role": role,
                    "Market": market,
                    "Resolved": n,
                    "MAE": mae,
                    "Bias": bias,
                    "80% Range Coverage": coverage,
                    "Status": "TRACKING" if n >= 15 else "LEARNING",
                })
    return pd.DataFrame(rows, columns=columns)


def _lookup_status(report: pd.DataFrame, signal: str, market: str) -> tuple[str, int]:
    if report.empty:
        return "LEARNING", 0
    matched = report.loc[report["Signal"].astype(str).eq(signal) & report["Market"].astype(str).eq(market)]
    if matched.empty:
        return "LEARNING", 0
    row = matched.iloc[0]
    n = pd.to_numeric(pd.Series([row.get("Resolved Pairs")]), errors="coerce").fillna(0).iloc[0]
    return str(row.get("Status", "LEARNING")), int(n)


def snapshot_signal_profile(snapshot: Mapping[str, object], market: str, paired_report: pd.DataFrame) -> dict[str, object]:
    evidence: list[tuple[str, str, int]] = []
    if str(snapshot.get("workload_version", "")) == "workload-v1":
        status, n = _lookup_status(paired_report, "Workload v1 upgrade", market)
        evidence.append(("Workload", status, n))
    if str(snapshot.get("lineup_source", "")) == "CONFIRMED_LINEUP" and market in {"Strikeouts", "Hits Allowed"}:
        status, n = _lookup_status(paired_report, "Confirmed lineup upgrade", market)
        evidence.append(("Lineup", status, n))

    if not evidence:
        return {"Signal Evidence": "LEARNING", "Signal Sample": 0, "Signal Detail": "No mature paired signal evidence yet."}
    statuses = {status for _, status, _ in evidence}
    if "HURTING" in statuses:
        overall = "CAUTION"
    elif "HELPING" in statuses and statuses.issubset({"HELPING", "LEARNING"}):
        overall = "SUPPORTED"
    elif statuses == {"HELPING"}:
        overall = "SUPPORTED"
    elif "MIXED" in statuses:
        overall = "MIXED"
    else:
        overall = "LEARNING"
    detail = " · ".join(f"{name}: {status} (n={n})" for name, status, n in evidence)
    sample = max((n for _, _, n in evidence), default=0)
    return {"Signal Evidence": overall, "Signal Sample": int(sample), "Signal Detail": detail}


def attach_signal_profiles(plays: pd.DataFrame, history: pd.DataFrame, paired_report: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach current signal evidence after ranking; never reorder or filter plays."""
    if plays.empty:
        return plays.copy()
    report = paired_signal_report(history) if paired_report is None else paired_report
    out = plays.copy()
    profiles: list[dict[str, object]] = []
    game_col = pd.to_numeric(history.get("game_pk", pd.Series(index=history.index, dtype=float)), errors="coerce") if not history.empty else pd.Series(dtype=float)
    pitcher_col = pd.to_numeric(history.get("pitcher_id", pd.Series(index=history.index, dtype=float)), errors="coerce") if not history.empty else pd.Series(dtype=float)
    for _, play in out.iterrows():
        game_pk = pd.to_numeric(pd.Series([play.get("Game PK")]), errors="coerce").iloc[0]
        pitcher_id = pd.to_numeric(pd.Series([play.get("Pitcher ID")]), errors="coerce").iloc[0]
        snapshot: Mapping[str, object] = {}
        if not history.empty and pd.notna(game_pk) and pd.notna(pitcher_id):
            matched = history.loc[game_col.eq(float(game_pk)) & pitcher_col.eq(float(pitcher_id))]
            if not matched.empty:
                snapshot = matched.iloc[-1]
        profiles.append(snapshot_signal_profile(snapshot, str(play.get("Market", "")), report))
    profile_frame = pd.DataFrame(profiles, index=out.index)
    for col in ["Signal Evidence", "Signal Sample", "Signal Detail"]:
        out[col] = profile_frame[col]
    return out

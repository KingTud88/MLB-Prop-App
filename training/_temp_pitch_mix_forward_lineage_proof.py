from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from training.pitch_mix_whiff_forward_evaluation import PREREGISTERED_GAME_DATE


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def clean(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def num(value: object) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return np.nan if pd.isna(parsed) else float(parsed)


def utc(value: object) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce", utc=True)


def main() -> None:
    scores = pd.read_csv("data/pitch_mix_whiff_score_log.csv")
    projections = pd.read_csv("data/projection_log.csv")

    eligible = scores.copy()
    if "audit_eligible" in eligible.columns:
        eligible = eligible.loc[eligible["audit_eligible"].map(truthy)].copy()
    if "no_projection_adjustment" in eligible.columns:
        eligible = eligible.loc[eligible["no_projection_adjustment"].map(truthy)].copy()
    dates = pd.to_datetime(eligible.get("game_date"), errors="coerce")
    eligible = eligible.loc[dates.notna() & dates.ge(pd.Timestamp(PREREGISTERED_GAME_DATE))].copy()

    results: list[dict[str, object]] = []
    for _, score in eligible.iterrows():
        game_pk = int(num(score.get("game_pk")))
        pitcher_id = int(num(score.get("pitcher_id")))
        source = clean(score.get("lineup_source")) or "ACTIVE_ROSTER"
        lineup_hash = clean(score.get("lineup_hash"))
        score_capture = utc(score.get("whiff_context_captured_at_utc"))

        game_col = pd.to_numeric(projections.get("game_pk"), errors="coerce")
        pitcher_col = pd.to_numeric(projections.get("pitcher_id"), errors="coerce")
        exact = projections.loc[game_col.eq(game_pk) & pitcher_col.eq(pitcher_id)].copy()
        source_matches = exact.copy()
        if "lineup_source" in source_matches.columns:
            source_text = (
                source_matches["lineup_source"]
                .fillna("ACTIVE_ROSTER")
                .astype(str)
                .str.strip()
                .replace("", "ACTIVE_ROSTER")
            )
            source_matches = source_matches.loc[source_text.eq(source)].copy()

        hash_matches = source_matches.copy()
        if "lineup_hash" in hash_matches.columns:
            hash_text = hash_matches["lineup_hash"].fillna("").astype(str).str.strip().replace("nan", "")
            hash_matches = hash_matches.loc[hash_text.eq(lineup_hash)].copy()

        captured = (
            pd.to_datetime(hash_matches["captured_at_utc"], errors="coerce", utc=True)
            if "captured_at_utc" in hash_matches.columns
            else pd.Series(index=hash_matches.index, dtype="datetime64[ns, UTC]")
        )
        first_matching_capture = captured.dropna().min() if captured.notna().any() else pd.NaT
        last_matching_capture = captured.dropna().max() if captured.notna().any() else pd.NaT

        if exact.empty:
            reason = "NO_EXACT_GAME_PITCHER_PROJECTION"
            pre_score = hash_matches.iloc[0:0]
        elif source_matches.empty:
            reason = "LINEUP_SOURCE_MISMATCH"
            pre_score = hash_matches.iloc[0:0]
        elif hash_matches.empty:
            reason = "LINEUP_HASH_MISMATCH"
            pre_score = hash_matches.iloc[0:0]
        elif pd.isna(score_capture):
            reason = "MISSING_SCORE_CAPTURE_TIME"
            pre_score = hash_matches.iloc[0:0]
        else:
            eligible_time = captured.notna() & captured.le(score_capture)
            pre_score = hash_matches.loc[eligible_time].copy()
            if pre_score.empty:
                reason = "NO_PROJECTION_AT_OR_BEFORE_SCORE_CAPTURE"
            else:
                pre_score = pre_score.assign(_captured=captured.loc[pre_score.index]).sort_values("_captured")
                chosen = pre_score.iloc[-1]
                if not np.isfinite(num(chosen.get("projection"))):
                    reason = "MISSING_PROJECTION_VALUE"
                elif not np.isfinite(num(chosen.get("actual_strikeouts"))):
                    reason = "PRE_SCORE_PROJECTION_UNRESOLVED"
                else:
                    reason = "ELIGIBLE"

        first_delay_minutes = np.nan
        if not pd.isna(first_matching_capture) and not pd.isna(score_capture):
            first_delay_minutes = (first_matching_capture - score_capture).total_seconds() / 60.0

        results.append(
            {
                "game_pk": game_pk,
                "pitcher_id": pitcher_id,
                "player": clean(score.get("player")),
                "lineup_source": source,
                "lineup_hash": lineup_hash,
                "score_capture": score_capture.isoformat() if not pd.isna(score_capture) else "",
                "exact_projection_rows": len(exact),
                "source_match_rows": len(source_matches),
                "hash_match_rows": len(hash_matches),
                "pre_score_rows": len(pre_score),
                "first_matching_projection_capture": first_matching_capture.isoformat() if not pd.isna(first_matching_capture) else "",
                "last_matching_projection_capture": last_matching_capture.isoformat() if not pd.isna(last_matching_capture) else "",
                "first_projection_minus_score_minutes": first_delay_minutes,
                "reason": reason,
            }
        )

    detail = pd.DataFrame(results)
    print("PITCH_MIX_FORWARD_LINEAGE_PROOF")
    print(f"preregistered_game_date={PREREGISTERED_GAME_DATE}")
    print(f"eligible_score_rows={len(detail)}")
    print("reason_counts=" + repr(dict(Counter(detail["reason"]))))
    if not detail.empty:
        display_cols = [
            "game_pk",
            "pitcher_id",
            "player",
            "lineup_source",
            "score_capture",
            "exact_projection_rows",
            "source_match_rows",
            "hash_match_rows",
            "pre_score_rows",
            "first_matching_projection_capture",
            "first_projection_minus_score_minutes",
            "reason",
        ]
        print(detail[display_cols].sort_values(["reason", "player"]).to_string(index=False))


if __name__ == "__main__":
    main()

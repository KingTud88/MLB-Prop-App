from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from engine.ui_theme import apply_page_theme

from automation.daily_projection_runner import (
    LOG_PATH,
    PROBABILITY_SEMANTICS,
    load_observation_log,
    resolve_observation_log,
    fill_missing_pregame_paths,
    attach_pregame_weather,
    attach_pregame_team_leash,
    refresh_pregame_lineups,
    project,
    resolve_row,
    resolve_workload_actuals,
    schedule,
)
from engine.calibration import calibrate_blend
from engine.hits_calibration import calibrate_hits_blend
from engine.outs_calibration import calibrate_outs_blend
from engine.odds_snapshot import refresh_strikeout_snapshot, resolve_api_key
from navigation import render_sidebar
from training.projection_storage import load_projection_archive, overlay_manual_market_lines, save_projection_archive

st.set_page_config(page_title="Daily Projection Run", page_icon="📊", layout="wide")
apply_page_theme()
render_sidebar("daily")
st.markdown(
    """
    <style>
    .block-container { padding-top: 3.25rem !important; }
    /* daily-control-deck-v2: presentation only. */
    .daily-hero { margin:.25rem 0 1.15rem; padding:.9rem 1rem; border:1px solid rgba(73,111,151,.48); border-left:3px solid #ff3655; border-radius:16px; background:linear-gradient(120deg,rgba(227,25,55,.08),rgba(10,29,54,.76) 42%,rgba(6,18,35,.78)); box-shadow:0 14px 34px rgba(0,0,0,.16); }
    .daily-hero strong { color:#f8fbff; font-size:1rem; }
    .daily-hero span { display:block; color:#9db0c5; font-size:.84rem; margin-top:.2rem; }
    .daily-kicker { margin:1.35rem 0 .42rem; color:#aebfd2; font-size:.72rem; font-weight:900; letter-spacing:.13em; text-transform:uppercase; }
    .daily-kicker::before { content:''; display:inline-block; width:22px; height:2px; margin-right:.5rem; vertical-align:middle; background:#ff3655; box-shadow:0 0 11px rgba(227,25,55,.42); }
    .daily-paid-note { margin:.35rem 0 .8rem; padding:.72rem .85rem; border-radius:13px; border:1px solid rgba(250,204,21,.32); background:rgba(120,79,8,.08); color:#c9d7e5; font-size:.86rem; }
    /* DAILY_COMMAND_UI_V3 */
    .block-container{max-width:1540px!important;padding-top:2.05rem!important;padding-bottom:4rem!important}
    .daily-command-hero{position:relative;overflow:hidden;margin:.1rem 0 .75rem;padding:1.05rem 1.2rem 1.1rem;border:1px solid rgba(80,108,136,.78);border-radius:18px;background:linear-gradient(112deg,rgba(8,28,50,.99),rgba(5,19,35,.99));box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 18px 42px rgba(0,0,0,.30)}
    .daily-command-hero:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(#ff3655,#a60c29)}
    .daily-command-kicker{font:900 .70rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.13em;color:#ff6a7d;text-transform:uppercase}
    .daily-command-title{margin:.22rem 0 .28rem;font-family:Impact,"Arial Black","Arial Narrow",sans-serif;font-size:clamp(2.6rem,5vw,4.8rem);line-height:.86;letter-spacing:.012em;color:#f5f1e9;text-transform:uppercase;text-shadow:3px 4px 0 #07182b}
    .daily-command-title span{color:#ec1638;-webkit-text-stroke:1px #f1eee7;paint-order:stroke fill}
    .daily-command-sub{max-width:1180px;color:#c0ceda;font:650 .90rem/1.48 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .daily-command-rule{margin-top:.58rem;width:max-content;max-width:100%;padding:.25rem .58rem;border-top:1px solid rgba(236,22,56,.65);border-bottom:1px solid rgba(236,22,56,.65);color:#edf3f7;font:900 .67rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.09em;text-transform:uppercase}
    .daily-section-head{width:max-content;min-width:240px;max-width:92%;margin:1.15rem auto .65rem;padding:.44rem 1.65rem;border:1px solid #ff3151;border-bottom-color:#790b1d;border-radius:8px;background:linear-gradient(180deg,#f21b3d,#b70d29);box-shadow:0 7px 16px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.22);color:#fff;font:900 .90rem/1.15 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;letter-spacing:.04em;text-align:center;text-transform:uppercase}
    .daily-note{margin:.45rem 0 .78rem;padding:.78rem .88rem;border:1px solid rgba(73,111,151,.56);border-radius:13px;background:linear-gradient(110deg,rgba(10,34,59,.90),rgba(5,22,40,.92));color:#d2dde6;font:700 .84rem/1.45 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .daily-note.paid{border-color:rgba(250,204,21,.42);background:linear-gradient(110deg,rgba(88,65,8,.24),rgba(29,29,16,.52));color:#e9dfb4}
    .daily-action-label{margin:.15rem 0 .32rem;color:#f4f7fa;font:900 1.12rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .daily-action-copy{margin:0 0 .62rem;color:#aebfd0;font:650 .83rem/1.42 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    [data-testid="stMetric"]{min-height:108px;padding:.70rem .76rem!important;border:1px solid rgba(77,108,137,.72)!important;border-radius:14px!important;background:linear-gradient(145deg,rgba(9,31,55,.98),rgba(4,18,33,.98))!important}
    [data-testid="stMetricLabel"]{color:#eef4f8!important;font-size:.78rem!important;font-weight:900!important;text-transform:uppercase!important}
    [data-testid="stMetricValue"]{font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif!important;color:#fff!important;font-size:1.65rem!important;font-weight:900!important}
    div[data-testid="stDataFrame"]{border:1px solid rgba(77,108,137,.62);border-radius:14px;overflow:hidden;box-shadow:0 12px 28px rgba(0,0,0,.20)}
    div[data-testid="stButton"] button[kind="primary"]{min-height:48px!important;border:1px solid #ff4560!important;background:linear-gradient(180deg,#f31b3d,#bc0d2b)!important;font-weight:900!important;letter-spacing:.035em!important;text-transform:uppercase!important}
    .daily-run-status{display:flex;align-items:center;justify-content:space-between;gap:1rem;margin:.1rem 0 .75rem;padding:.72rem .85rem;border-radius:12px;background:rgba(7,28,49,.86);border:1px solid rgba(69,102,132,.68)}
    .daily-run-status.ok{border-color:rgba(50,229,141,.55)}
    .daily-run-status.error{border-color:rgba(255,71,98,.60)}
    .daily-run-status .main{color:#f5f8fb;font:900 .92rem/1.2 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
    .daily-run-status .meta{color:#aebfd0;font:700 .76rem/1.25 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;text-align:right}
    @media (max-width:900px) { .daily-hero { padding:.78rem .85rem; } .daily-kicker { margin-top:1rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="daily-command-hero"><div class="daily-command-kicker">StrikeOut King 9000 · Daily Command Board</div>'
    '<div class="daily-command-title">DAILY <span>RUN</span></div>'
    '<div class="daily-command-sub">Capture every announced MLB starter as a frozen pregame strikeout, total-outs, and hits-allowed snapshot. Market data stays isolated and never ranks or drives the baseball projection.</div>'
    '<div class="daily-command-rule">MODEL FIRST · FROZEN PREGAME · MARKET DATA ISOLATED</div></div>'
    '<div class="daily-section-head">Slate Control</div>',
    unsafe_allow_html=True,
)

EASTERN = ZoneInfo("America/New_York")
today = datetime.now(EASTERN).date()
ARCHIVE_PATH = LOG_PATH.parent / "projection_archive.csv"
slate_date = st.date_input("Slate date", value=today)


def load_log() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(LOG_PATH)
    except Exception:
        return pd.DataFrame()
    # Legacy projection logs may predate hits/outs resolution columns. Always
    # materialize them as Series so summary counts never call .notna() on a scalar.
    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches"):
        if col not in frame.columns:
            frame[col] = np.nan
    if "resolved_at_utc" not in frame.columns:
        frame["resolved_at_utc"] = ""
    return frame


def history_only_for_day(day: str) -> pd.DataFrame:
    """Return persistent history-only starter observations for one slate date."""
    frame = load_observation_log()
    if frame.empty or "game_date" not in frame.columns:
        return pd.DataFrame()
    rows = frame.loc[frame["game_date"].astype(str).eq(str(day))].copy()
    if rows.empty:
        return rows
    actual_cols = [
        "actual_strikeouts", "actual_hits_allowed", "actual_outs",
        "actual_batters_faced", "actual_pitches",
    ]
    for col in actual_cols + ["history_games_available_at_capture"]:
        if col in rows.columns:
            rows[col] = pd.to_numeric(rows[col], errors="coerce")
    available = [col for col in actual_cols if col in rows.columns]
    resolved = rows[available].notna().all(axis=1) if available else pd.Series(False, index=rows.index)
    rows["observation_status"] = np.where(resolved, "RESOLVED", "PENDING")
    return rows.sort_values(["observation_status", "game_time", "player"], ascending=[True, True, True]).reset_index(drop=True)


def save_log(frame: pd.DataFrame) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    for line in range(3, 11):
        for prefix in ("sim", "math"):
            col = f"{prefix}_{line}p"
            if col not in frame.columns:
                frame[col] = np.nan
    if "probability_semantics" not in frame.columns:
        frame["probability_semantics"] = ""
    if "history_semantics" not in frame.columns:
        frame["history_semantics"] = ""
    if "starter_history_games" not in frame.columns:
        frame["starter_history_games"] = np.nan
    if "starter_history_source" not in frame.columns:
        frame["starter_history_source"] = ""
    if "starter_history_mlb_games" not in frame.columns:
        frame["starter_history_mlb_games"] = np.nan
    if "starter_history_observation_games" not in frame.columns:
        frame["starter_history_observation_games"] = np.nan
    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs", "actual_batters_faced", "actual_pitches"):
        if col not in frame.columns:
            frame[col] = np.nan
    if "resolved_at_utc" not in frame.columns:
        frame["resolved_at_utc"] = ""
    frame.to_csv(LOG_PATH, index=False)


def _archive_row_key(row: pd.Series) -> str:
    game_pk = str(row.get("game_pk", "")).split(".")[0]
    pitcher_id = str(row.get("pitcher_id", "")).split(".")[0]
    return f"{game_pk}:{pitcher_id}"


def _parse_market_line(value: object) -> float:
    text = str(value or "").strip()
    if not text:
        return np.nan
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Invalid market line: {text}") from exc


def _manual_input_default(row: pd.Series, line_col: str, source_col: str) -> str:
    source = row.get(source_col, "")
    if pd.isna(source) or str(source).strip().upper() != "MANUAL":
        return ""
    value = pd.to_numeric(pd.Series([row.get(line_col)]), errors="coerce").iloc[0]
    return "" if pd.isna(value) else f"{float(value):g}"


def commit_projection_archive(slate: pd.DataFrame, manual_lines: dict[str, dict[str, float]], slate_day: str) -> int:
    if slate.empty:
        return 0
    snapshot = slate.copy().reset_index(drop=True)
    snapshot["manual_strikeout_line"] = [manual_lines.get(_archive_row_key(row), {}).get("k", np.nan) for _, row in snapshot.iterrows()]
    snapshot["manual_outs_line"] = [manual_lines.get(_archive_row_key(row), {}).get("outs", np.nan) for _, row in snapshot.iterrows()]
    snapshot["manual_hits_allowed_line"] = [manual_lines.get(_archive_row_key(row), {}).get("hits", np.nan) for _, row in snapshot.iterrows()]
    snapshot["archive_source"] = "DAILY_RUN_MANUAL"
    snapshot["archive_committed_at_utc"] = datetime.now(ZoneInfo("UTC")).isoformat()

    existing = load_projection_archive(ARCHIVE_PATH, st.secrets)
    if existing.empty:
        existing = load_log()
        if not existing.empty and "game_date" in existing.columns:
            cutoff = pd.Timestamp(slate_day).date()
            legacy_dates = pd.to_datetime(existing["game_date"], errors="coerce").dt.date
            existing = existing.loc[legacy_dates < cutoff].copy()
            if not existing.empty:
                existing["manual_strikeout_line"] = np.nan
                existing["manual_outs_line"] = np.nan
                existing["manual_hits_allowed_line"] = np.nan
                existing["archive_source"] = "LEGACY_PRE_MANUAL_ARCHIVE"
                existing["archive_committed_at_utc"] = existing.get("captured_at_utc", "")
        else:
            existing = pd.DataFrame()

    if not existing.empty and {"game_pk", "pitcher_id"}.issubset(existing.columns) and {"game_pk", "pitcher_id"}.issubset(snapshot.columns):
        new_keys = set(zip(snapshot["game_pk"].astype(str), snapshot["pitcher_id"].astype(str)))
        keep_mask = [key not in new_keys for key in zip(existing["game_pk"].astype(str), existing["pitcher_id"].astype(str))]
        existing = existing.loc[keep_mask].copy()

    archive = pd.concat([existing, snapshot], ignore_index=True, sort=False)
    save_projection_archive(ARCHIVE_PATH, archive, st.secrets)
    return len(snapshot)


def apply_active_market_lines(slate_day: str, manual_lines: dict[str, dict[str, float]]) -> int:
    """Apply user-entered sportsbook lines to frozen rows used by current Top Plays."""
    frame = load_log()
    if frame.empty or "game_date" not in frame.columns:
        return 0
    for col in (
        "active_strikeout_line", "active_outs_line", "active_hits_allowed_line",
        "active_strikeout_line_source", "active_outs_line_source", "active_hits_allowed_line_source",
    ):
        if col not in frame.columns:
            frame[col] = np.nan if col.endswith("_line") else ""

    applied = 0
    day_mask = frame["game_date"].astype(str).eq(str(slate_day))
    for idx in frame.index[day_mask]:
        row = frame.loc[idx]
        values = manual_lines.get(_archive_row_key(row), {})
        for key, line_col, source_col in (
            ("k", "active_strikeout_line", "active_strikeout_line_source"),
            ("outs", "active_outs_line", "active_outs_line_source"),
            ("hits", "active_hits_allowed_line", "active_hits_allowed_line_source"),
        ):
            value = values.get(key, np.nan)
            if pd.notna(value):
                frame.at[idx, line_col] = float(value)
                frame.at[idx, source_col] = "MANUAL"
                applied += 1
    save_log(frame)
    return applied


def apply_paid_strikeout_lines(odds_snapshot: pd.DataFrame, slate_day: str) -> int:
    """Apply saved paid K lines without overwriting a deliberate manual line."""
    if odds_snapshot.empty:
        return 0
    frame = load_log()
    if frame.empty or "game_date" not in frame.columns:
        return 0
    for col, default in (("active_strikeout_line", np.nan), ("active_strikeout_line_source", "")):
        if col not in frame.columns:
            frame[col] = default

    snap = odds_snapshot.copy()
    snap["point"] = pd.to_numeric(snap.get("point"), errors="coerce")
    snap = snap.dropna(subset=["point"])
    snap["_name"] = snap.get("pitcher", pd.Series(index=snap.index, dtype=str)).fillna("").astype(str).map(lambda x: " ".join(x.lower().split()))
    snap["_book"] = snap.get("book", pd.Series(index=snap.index, dtype=str)).fillna("").astype(str).str.lower()

    applied = 0
    day_mask = frame["game_date"].astype(str).eq(str(slate_day))
    for idx in frame.index[day_mask]:
        if str(frame.at[idx, "active_strikeout_line_source"] or "").upper() == "MANUAL":
            continue
        name = " ".join(str(frame.at[idx, "player"]).lower().split())
        offers = snap.loc[snap["_name"].eq(name)]
        if offers.empty:
            continue
        fanduel = offers.loc[offers["_book"].str.contains("fanduel", na=False)]
        chosen = fanduel if not fanduel.empty else offers
        mode = chosen["point"].mode()
        if mode.empty:
            continue
        frame.at[idx, "active_strikeout_line"] = float(mode.iloc[0])
        frame.at[idx, "active_strikeout_line_source"] = "PAID API · FANDUEL" if not fanduel.empty else "PAID API · CONSENSUS"
        applied += 1
    save_log(frame)
    return applied


def run_full_slate(day: str) -> tuple[pd.DataFrame, int, int, list[str], list[str]]:
    frame = load_log()
    announced = schedule(day)
    existing = set()
    if not frame.empty and {"game_pk", "pitcher_id"}.issubset(frame.columns):
        existing = set(
            zip(
                pd.to_numeric(frame["game_pk"], errors="coerce"),
                pd.to_numeric(frame["pitcher_id"], errors="coerce"),
            )
        )

    new_rows: list[dict] = []
    skipped = 0
    history_only: list[str] = []
    errors: list[str] = []
    for row in announced:
        key = (row["game_pk"], row["pitcher_id"])
        if key in existing:
            skipped += 1
            continue
        try:
            result = project(row)
        except Exception as exc:
            errors.append(f"{row.get('player', 'Unknown')}: {type(exc).__name__}: {exc}")
            continue
        if result is None:
            history_only.append(
                f"{row.get('player', 'Unknown')}: no usable starter history — final K / hits / outs / BF / pitches will be tracked"
            )
            continue
        new_rows.append(result)

    if new_rows:
        frame = pd.concat([frame, pd.DataFrame(new_rows)], ignore_index=True)

    refreshed = fill_missing_pregame_paths(frame)
    weather_refreshed = attach_pregame_weather(frame, announced)
    team_leash_refreshed = attach_pregame_team_leash(frame)
    lineup_refreshed = refresh_pregame_lineups(frame, announced)
    save_log(frame)

    slate = frame.loc[frame.get("game_date", pd.Series(dtype=str)).astype(str).eq(day)].copy() if not frame.empty else pd.DataFrame()
    return slate, len(new_rows), skipped + refreshed + weather_refreshed + team_leash_refreshed + lineup_refreshed, history_only, errors


def _num(row: pd.Series, key: str) -> float | None:
    value = pd.to_numeric(pd.Series([row.get(key)]), errors="coerce").iloc[0]
    return None if pd.isna(value) else float(value)


def _range_text(low: object, high: object) -> str:
    """Render a central outcome interval as one compact human-readable value."""
    lo = pd.to_numeric(pd.Series([low]), errors="coerce").iloc[0]
    hi = pd.to_numeric(pd.Series([high]), errors="coerce").iloc[0]
    if pd.isna(lo) or pd.isna(hi):
        return "—"

    def _endpoint(value: float) -> str:
        value = float(value)
        rounded = round(value)
        return str(int(rounded)) if abs(value - rounded) < 1e-9 else f"{value:.1f}"

    return f"{_endpoint(float(lo))}–{_endpoint(float(hi))}"


def render_projection_rationale(row: pd.Series, history: pd.DataFrame) -> None:
    pitcher = str(row.get("player", "Unknown"))
    st.markdown(f"### 🔎 Why we projected {pitcher} this way")
    st.caption(
        "This explanation uses the frozen pregame snapshot. Later game results do not change the inputs or probabilities shown here."
    )

    k_mean = _num(row, "projection")
    hits_mean = _num(row, "hits_projection")
    quality = _num(row, "data_quality")
    opp_k = _num(row, "opponent_k_pct")
    outs_mean = _num(row, "outs_projection")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Projected Ks", "—" if k_mean is None else f"{k_mean:.2f}")
    c2.metric("Projected outs", "—" if outs_mean is None else f"{outs_mean:.2f}")
    c3.metric("Projected hits allowed", "—" if hits_mean is None else f"{hits_mean:.2f}")
    c4.metric("Data quality", "—" if quality is None else f"{quality:.0f}/100")
    c5.metric("Opponent K%", "—" if opp_k is None else f"{opp_k:.1f}%")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Strikeout path · 5+")
        sim = _num(row, "sim_5p")
        math_p = _num(row, "math_5p")
        cal = calibrate_blend(history, 5)
        blended = None if sim is None or math_p is None else cal.weight_simulation * sim + cal.weight_math * math_p
        detail = pd.DataFrame([
            {"Component": "Simulation", "Probability": sim, "Weight": cal.weight_simulation},
            {"Component": "Mathematical", "Probability": math_p, "Weight": cal.weight_math},
        ])
        for col in ("Probability", "Weight"):
            detail[col] = detail[col].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
        st.dataframe(detail, hide_index=True, use_container_width=True)
        st.write("**Blended 5+ probability:**", "—" if blended is None else f"{blended:.1%}")
        st.caption(
            f"Calibration: {'learned' if cal.calibrated else '50/50 baseline'} · {cal.observations} compatible resolved observations."
        )

    with right:
        st.markdown("#### Hits allowed path · Over 5.5")
        hit_sim = _num(row, "hits_sim_over_5_5")
        hit_math = _num(row, "hits_math_over_5_5")
        hit_cal = calibrate_hits_blend(history, 5.5)
        hit_blended = None if hit_sim is None or hit_math is None else hit_cal.weight_simulation * hit_sim + hit_cal.weight_math * hit_math
        detail = pd.DataFrame([
            {"Component": "Simulation", "Probability": hit_sim, "Weight": hit_cal.weight_simulation},
            {"Component": "Mathematical", "Probability": hit_math, "Weight": hit_cal.weight_math},
        ])
        for col in ("Probability", "Weight"):
            detail[col] = detail[col].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
        st.dataframe(detail, hide_index=True, use_container_width=True)
        st.write("**Blended O5.5 probability:**", "—" if hit_blended is None else f"{hit_blended:.1%}")
        st.caption(
            f"Calibration: {'learned' if hit_cal.calibrated else '50/50 baseline'} · {hit_cal.observations} resolved hit observations."
        )

    st.markdown("#### Total outs path · Over 15.5")
    outs_sim = _num(row, "outs_sim_over_15_5")
    outs_math = _num(row, "outs_math_over_15_5")
    outs_cal = calibrate_outs_blend(history, 15.5)
    outs_blended = None if outs_sim is None or outs_math is None else outs_cal.weight_simulation * outs_sim + outs_cal.weight_math * outs_math
    detail = pd.DataFrame([
        {"Component": "Simulation", "Probability": outs_sim, "Weight": outs_cal.weight_simulation},
        {"Component": "Mathematical", "Probability": outs_math, "Weight": outs_cal.weight_math},
    ])
    for col in ("Probability", "Weight"):
        detail[col] = detail[col].map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
    st.dataframe(detail, hide_index=True, use_container_width=True)
    st.write("**Blended O15.5 probability:**", "—" if outs_blended is None else f"{outs_blended:.1%}")
    st.caption(f"Calibration: {'learned' if outs_cal.calibrated else '50/50 baseline'} · {outs_cal.observations} resolved outs observations.")

    facts = {
        "Matchup": f"{row.get('team', '—')} vs {row.get('opponent', '—')}",
        "Confidence": row.get("confidence", "—"),
        "Matchup PA sample": int(_num(row, "matchup_pa") or 0),
        "Matchup batters": int(_num(row, "matchup_batters") or 0),
        "Lineup source": row.get("lineup_source", "ACTIVE_ROSTER"),
        "Confirmed lineup hitters": int(_num(row, "lineup_batters") or 0),
        "Lineup projection delta": _num(row, "lineup_projection_delta"),
        "K 80% range": f"{row.get('k_range_low', '—')}–{row.get('k_range_high', '—')}",
        "Hits 80% range": f"{row.get('hits_range_low', '—')}–{row.get('hits_range_high', '—')}",
        "Outs 80% range": f"{row.get('outs_range_low', '—')}–{row.get('outs_range_high', '—')}",
        "Probability semantics": row.get("probability_semantics", "—"),
        "History semantics": row.get("history_semantics", "—"),
        "Starter appearances used": int(_num(row, "starter_history_games") or 0),
        "History source": row.get("starter_history_source", "—"),
        "MLB starts used": int(_num(row, "starter_history_mlb_games") or 0),
        "Observed starts used": int(_num(row, "starter_history_observation_games") or 0),
        "Workload version": row.get("workload_version", "—"),
        "Expected pitches": _num(row, "expected_pitches"),
        "Expected BF": _num(row, "expected_bf"),
        "Expected outs workload": _num(row, "expected_outs"),
        "Pitches / BF": _num(row, "pitches_per_bf"),
        "Days since last start": _num(row, "days_since_last_start"),
        "Recent leash": row.get("leash_label", "—"),
        "Pitch trend": _num(row, "pitch_trend"),
        "Team leash role": row.get("team_leash_role", "—"),
        "Team leash status": row.get("team_leash_status", "—"),
        "Team leash label": row.get("team_leash_label", "—"),
        "Team starts tracked": int(_num(row, "team_leash_starts") or 0),
        "Team avg pitches": _num(row, "team_leash_avg_pitches"),
        "Team TTO reach rate": _num(row, "team_leash_tto_reach_rate"),
        "Team 90+ pitch rate": _num(row, "team_leash_90_pitch_rate"),
        "Candidate pitch multiplier": _num(row, "team_leash_pitch_multiplier_candidate"),
    }
    st.dataframe(pd.DataFrame([facts]), hide_index=True, use_container_width=True)
    st.caption(
        "Strikeouts, total outs, and hits allowed each use independent simulation + mathematical paths with protected calibration baselines until enough resolved observations exist."
    )


st.markdown('<div class="daily-note">Batch capture only · the Projection page remains the single-pitcher deep dive. Existing snapshots stay frozen after first pitch; while still pregame, a roster-fallback row may upgrade once MLB posts a confirmed batting order.</div>', unsafe_allow_html=True)

st.markdown('<div class="daily-section-head">Projection Capture</div>', unsafe_allow_html=True)
st.markdown('<div class="daily-action-label">⚾ Run the full starter slate</div><div class="daily-action-copy">Primary daily action · capture new eligible starters, preserve frozen snapshots, and refresh only allowed pregame context.</div>', unsafe_allow_html=True)
if st.button("⚾ RUN ALL TODAY'S PITCHERS", type="primary", use_container_width=True):
    with st.spinner("Simulating every announced starter and writing pregame snapshots..."):
        try:
            slate, added, skipped, history_only, errors = run_full_slate(slate_date.isoformat())
        except Exception as exc:
            slate = pd.DataFrame()
            added = skipped = 0
            history_only = []
            errors = [f"Slate run failed: {type(exc).__name__}: {exc}"]
    durable_archive = load_projection_archive(ARCHIVE_PATH, st.secrets)
    slate = overlay_manual_market_lines(slate, durable_archive)
    st.session_state["daily_slate"] = slate
    st.session_state["daily_slate_date"] = slate_date.isoformat()
    st.session_state["daily_added"] = added
    st.session_state["daily_skipped"] = skipped
    st.session_state["daily_history_only"] = history_only
    st.session_state["daily_errors"] = errors
    st.session_state["daily_run_at"] = datetime.now(EASTERN).strftime("%b %d, %Y · %I:%M:%S %p ET")

st.markdown('<div class="daily-section-head">Slate Output</div>', unsafe_allow_html=True)
# PROJECTION_RESTART_PERSISTENCE_V1
if st.session_state.get("daily_slate_date") != slate_date.isoformat():
    persisted_log = load_log()
    recovered = persisted_log.loc[
        persisted_log.get("game_date", pd.Series(index=persisted_log.index, dtype=str)).astype(str).eq(slate_date.isoformat())
    ].copy() if not persisted_log.empty else pd.DataFrame()
    if not recovered.empty:
        durable_archive = load_projection_archive(ARCHIVE_PATH, st.secrets)
        recovered = overlay_manual_market_lines(recovered, durable_archive)
        st.session_state["daily_slate"] = recovered
        st.session_state["daily_added"] = 0
        st.session_state["daily_skipped"] = len(recovered)
        st.session_state["daily_history_only"] = []
        st.session_state["daily_errors"] = []
        st.session_state["daily_run_at"] = "Recovered from frozen projection log"
    else:
        for key in ("daily_slate", "daily_added", "daily_skipped", "daily_history_only", "daily_errors", "daily_run_at"):
            st.session_state.pop(key, None)
    st.session_state["daily_slate_date"] = slate_date.isoformat()

slate = st.session_state.get("daily_slate")
if isinstance(slate, pd.DataFrame):
    added = int(st.session_state.get("daily_added", 0))
    skipped = int(st.session_state.get("daily_skipped", 0))
    history_only = list(st.session_state.get("daily_history_only", []))
    errors = list(st.session_state.get("daily_errors", []))
    # DAILY_RUN_STATUS_V1
    run_at = str(st.session_state.get("daily_run_at", "Run timestamp unavailable"))
    status_class = "error" if errors else "ok"
    status_text = "Completed with capture errors" if errors else "Slate capture complete"
    st.markdown(
        f'<div class="daily-run-status {status_class}"><div class="main">{status_text}</div><div class="meta">{slate_date:%b %d, %Y} · {run_at}</div></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Projected starters", len(slate))
    c2.metric("New snapshots", added)
    c3.metric("Already captured/refreshed", skipped)
    c4.metric("History-only tracked", len(history_only))
    c5.metric("Errors", len(errors))
    confirmed_lineups = int(slate.get("lineup_source", pd.Series(index=slate.index, dtype=str)).astype(str).eq("CONFIRMED_LINEUP").sum()) if not slate.empty else 0
    c6.metric("Confirmed lineups", confirmed_lineups)

    if not slate.empty:
        st.markdown('<div class="daily-action-label">🎚️ Manual sportsbook lines</div>', unsafe_allow_html=True)
        st.caption("Open each pitcher bar and enter the real sportsbook lines you want Top Plays to evaluate. Manual values override paid API lines. Half-lines such as 4.5, 15.5, and 5.5 are supported; a blank market is excluded from Top Plays unless a paid active line already exists. Saved manual lines reload automatically after an app restart.")
        durable_archive = load_projection_archive(ARCHIVE_PATH, st.secrets)
        slate = overlay_manual_market_lines(slate, durable_archive)
        st.session_state["daily_slate"] = slate
        manual_line_values: dict[str, dict[str, str]] = {}
        for _, manual_row in slate.reset_index(drop=True).iterrows():
            row_key = _archive_row_key(manual_row)
            player = str(manual_row.get("player", "Unknown"))
            team = str(manual_row.get("team", "—"))
            opponent = str(manual_row.get("opponent", "—"))
            with st.expander(f"⚾ {player} · {team} vs {opponent}", expanded=False):
                l1, l2, l3 = st.columns(3)
                k_raw = l1.text_input("Strikeout line", value=_manual_input_default(manual_row, "active_strikeout_line", "active_strikeout_line_source"), placeholder="e.g. 4.5", key=f"daily_manual_k_{row_key}")
                outs_raw = l2.text_input("Total outs line", value=_manual_input_default(manual_row, "active_outs_line", "active_outs_line_source"), placeholder="e.g. 15.5", key=f"daily_manual_outs_{row_key}")
                hits_raw = l3.text_input("Hits allowed line", value=_manual_input_default(manual_row, "active_hits_allowed_line", "active_hits_allowed_line_source"), placeholder="e.g. 5.5", key=f"daily_manual_hits_{row_key}")
                st.caption(f"Model: {float(manual_row.get('projection', float('nan'))):.2f} K · {float(manual_row.get('outs_projection', float('nan'))):.2f} outs · {float(manual_row.get('hits_projection', float('nan'))):.2f} hits allowed")
            manual_line_values[row_key] = {"k": k_raw, "outs": outs_raw, "hits": hits_raw}

        if st.button("✅ APPLY LINES + ADD TO PROJECTION ARCHIVE", type="primary", use_container_width=True, key="daily_apply_archive"):
            try:
                parsed_lines = {
                    key: {
                        "k": _parse_market_line(values.get("k")),
                        "outs": _parse_market_line(values.get("outs")),
                        "hits": _parse_market_line(values.get("hits")),
                    }
                    for key, values in manual_line_values.items()
                }
                filled_lines = sum(pd.notna(value) for values in parsed_lines.values() for value in values.values())
                if filled_lines == 0:
                    raise ValueError("Enter at least one sportsbook line before adding the slate to the Projection Archive.")
                archived = commit_projection_archive(slate, parsed_lines, slate_date.isoformat())
                applied = filled_lines
                refreshed_log = load_log()
                refreshed_slate = refreshed_log.loc[refreshed_log.get("game_date", pd.Series(dtype=str)).astype(str).eq(slate_date.isoformat())].copy()
                durable_archive = load_projection_archive(ARCHIVE_PATH, st.secrets)
                st.session_state["daily_slate"] = overlay_manual_market_lines(refreshed_slate, durable_archive)
                st.session_state["daily_slate_date"] = slate_date.isoformat()
                st.session_state["daily_archive_saved_at"] = datetime.now(EASTERN).strftime("%b %d, %Y · %I:%M:%S %p ET")
                st.success(f"Persisted {applied} manual sportsbook line(s) for Top Plays and saved {archived} pitcher projection row(s) to restart-safe storage.")
            except ValueError as exc:
                st.error(str(exc))

    if not slate.empty:
        # Keep the primary projection scan tight: pitcher/matchup first, then Ks.
        # Audit/context fields (weather, starter sample, workload) stay available
        # but live farther right so they do not separate the pitcher from Projection K.
        display_cols = [
            "player", "team", "opponent",
            "active_strikeout_line", "active_strikeout_line_source", "projection", "k_range_low", "k_range_high", "sim_5p", "math_5p",
            "active_outs_line", "active_outs_line_source", "outs_projection", "outs_range_low", "outs_range_high", "outs_sim_over_15_5", "outs_math_over_15_5",
            "active_hits_allowed_line", "active_hits_allowed_line_source", "hits_projection", "hits_range_low", "hits_range_high", "hits_sim_over_5_5", "hits_math_over_5_5",
            "confidence", "data_quality", "opponent_k_pct",
            "lineup_source", "lineup_batters", "lineup_projection_delta",
            "weather_icon", "weather_delay_risk", "weather_precip_probability",
            "starter_history_games", "starter_history_source", "starter_history_mlb_games", "starter_history_observation_games",
            "workload_version", "expected_pitches", "expected_bf", "expected_outs", "pitches_per_bf", "days_since_last_start", "leash_label", "pitch_trend",
            "team_leash_label", "team_leash_status", "team_leash_starts", "team_leash_avg_pitches", "team_leash_tto_reach_rate", "team_leash_90_pitch_rate", "team_leash_pitch_multiplier_candidate", "team_leash_role",
            "probability_semantics", "actual_strikeouts", "actual_hits_allowed", "actual_outs",
        ]
        display_cols = [c for c in display_cols if c in slate.columns]
        display = slate[display_cols].copy()
        if "weather_icon" in display.columns:
            display["player"] = display.apply(lambda r: f"{r.get('player', 'Unknown')} {str(r.get('weather_icon', '') or '')}".strip(), axis=1)
            display = display.drop(columns=["weather_icon"])

        # Low/high columns are endpoints of ONE central 80% interval. Collapse
        # them into a single value so nobody reads either endpoint as an 80%
        # milestone probability. Keep the new range exactly where the old pair
        # lived so each market scans projection -> range -> SIM -> MATH.
        for low_col, high_col, label in (
            ("k_range_low", "k_range_high", "80% K Range"),
            ("hits_range_low", "hits_range_high", "80% Hits Range"),
            ("outs_range_low", "outs_range_high", "80% Outs Range"),
        ):
            if low_col in display.columns and high_col in display.columns:
                insert_at = display.columns.get_loc(low_col)
                values = [
                    _range_text(low, high)
                    for low, high in zip(display[low_col], display[high_col])
                ]
                display.insert(insert_at, label, values)
                display = display.drop(columns=[low_col, high_col])

        display = display.rename(
            columns={
                "player": "Pitcher",
                "starter_history_games": "Starts",
                "starter_history_source": "History",
                "starter_history_mlb_games": "MLB Starts",
                "starter_history_observation_games": "Observed Starts",
                "workload_version": "Workload",
                "expected_pitches": "Exp Pitches",
                "expected_bf": "Exp BF",
                "expected_outs": "Exp Outs",
                "pitches_per_bf": "Pitches/BF",
                "days_since_last_start": "Rest Days",
                "leash_label": "Leash",
                "pitch_trend": "Pitch Trend",
                "team_leash_label": "Team Leash",
                "team_leash_status": "Team Leash Status",
                "team_leash_starts": "Team Starts",
                "team_leash_avg_pitches": "Team Avg Pitches",
                "team_leash_tto_reach_rate": "TTO %",
                "team_leash_90_pitch_rate": "90+ %",
                "team_leash_pitch_multiplier_candidate": "Pitch Adj",
                "team_leash_role": "Team Leash Role",
                "weather_delay_risk": "Weather",
                "weather_precip_probability": "Rain %",
                "lineup_source": "Lineup",
                "lineup_batters": "Hitters",
                "lineup_projection_delta": "Lineup K Δ",
                "team": "Team",
                "opponent": "Opp",
                "active_strikeout_line": "K Line",
                "active_strikeout_line_source": "K Source",
                "projection": "Projection K",
                "active_outs_line": "Outs Line",
                "active_outs_line_source": "Outs Source",
                "outs_projection": "Projection Outs",
                "active_hits_allowed_line": "Hits Line",
                "active_hits_allowed_line_source": "Hits Source",
                "hits_projection": "Projection Hits",
                "confidence": "Confidence",
                "data_quality": "Quality",
                "opponent_k_pct": "Opp K%",
                "sim_5p": "SIM 5+ K",
                "math_5p": "MATH 5+ K",
                "hits_sim_over_5_5": "SIM O5.5 Hits",
                "hits_math_over_5_5": "MATH O5.5 Hits",
                "outs_sim_over_15_5": "SIM O15.5 Outs",
                "outs_math_over_15_5": "MATH O15.5 Outs",
                "probability_semantics": "Semantics",
                "actual_strikeouts": "Actual K",
                "actual_hits_allowed": "Actual Hits Allowed",
                "actual_outs": "Actual Outs",
            }
        )
        projection_highlight_cols = [
            col for col in ("Projection K", "Projection Hits", "Projection Outs")
            if col in display.columns
        ]
        probability_cols = [
            col for col in (
                "SIM 5+ K", "MATH 5+ K", "SIM O5.5 Hits", "MATH O5.5 Hits",
                "SIM O15.5 Outs", "MATH O15.5 Outs",
            )
            if col in display.columns
        ]
        formatters: dict[str, str] = {}
        for col in projection_highlight_cols:
            formatters[col] = "{:.2f}"
        for col in ("K Line", "Outs Line", "Hits Line"):
            if col in display.columns:
                formatters[col] = "{:.1f}"
        for col in probability_cols:
            formatters[col] = "{:.1%}"
        for col in ("Exp Pitches", "Exp BF", "Exp Outs", "Team Avg Pitches"):
            if col in display.columns:
                formatters[col] = "{:.1f}"
        for col in ("Pitches/BF",):
            if col in display.columns:
                formatters[col] = "{:.2f}"
        for col in ("Quality", "Starts", "MLB Starts", "Observed Starts", "Rest Days", "Team Starts"):
            if col in display.columns:
                formatters[col] = "{:.0f}"
        if "Opp K%" in display.columns:
            formatters["Opp K%"] = "{:.1f}%"
        if "Rain %" in display.columns:
            formatters["Rain %"] = "{:.0f}%"
        if "Lineup K Δ" in display.columns:
            formatters["Lineup K Δ"] = "{:+.2f}"
        for col in ("Pitch Trend", "TTO %", "90+ %"):
            if col in display.columns:
                formatters[col] = "{:.1%}"
        if "Pitch Adj" in display.columns:
            formatters["Pitch Adj"] = "{:.3f}"
        for col in ("Actual K", "Actual Hits Allowed", "Actual Outs"):
            if col in display.columns:
                formatters[col] = "{:.0f}"

        styled_display = display.style.format(formatters, na_rep="—")
        if projection_highlight_cols:
            styled_display = styled_display.map(
                lambda value: "color: #22c55e; font-weight: 700;" if pd.notna(value) else "",
                subset=projection_highlight_cols,
            )

        # Make user-entered execution lines immediately visible without
        # changing the frozen projection layer. Paid/API lines keep the
        # standard table styling; MANUAL lines get the orange treatment.
        manual_line_styles = pd.DataFrame("", index=display.index, columns=display.columns)
        for line_col, source_col in (
            ("K Line", "K Source"),
            ("Outs Line", "Outs Source"),
            ("Hits Line", "Hits Source"),
        ):
            if line_col not in display.columns or source_col not in display.columns:
                continue
            manual_mask = (
                display[source_col].fillna("").astype(str).str.upper().eq("MANUAL")
                & display[line_col].notna()
            )
            manual_line_styles.loc[manual_mask, line_col] = (
                "color: #ff9f1c; font-weight: 800; background-color: rgba(255,159,28,.12);"
            )
            manual_line_styles.loc[manual_mask, source_col] = "color: #ff9f1c; font-weight: 800;"
        styled_display = styled_display.apply(lambda _: manual_line_styles, axis=None)

        st.subheader(f"{slate_date:%B %d, %Y} starter slate")
        st.caption(
            "How to read: Line = active sportsbook execution line attached after projection capture · Projection = frozen expected average outcome · 80% Range = one central simulated interval (10th–90th percentile), not an 80% chance at each endpoint · "
            "SIM/MATH = the probability from each independent model path. MANUAL/PAID API source labels show exactly where each line came from. Adding or changing a line never changes the frozen projection. Click a pitcher row for the full breakdown. Headline projections are green."
        )
        event = st.dataframe(
            styled_display,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="daily_projection_selection",
        )
        selected_rows = list(event.selection.rows) if event is not None else []
        if selected_rows:
            selected_pos = int(selected_rows[0])
            selected_row = slate.iloc[selected_pos]
            render_projection_rationale(selected_row, load_log())

        compatible = int(slate.get("probability_semantics", pd.Series(dtype=str)).astype(str).eq(PROBABILITY_SEMANTICS).sum())
        st.caption(f"{compatible}/{len(slate)} rows use the current calibration probability semantics: {PROBABILITY_SEMANTICS}.")

    if history_only:
        st.info("📚 History-only starters being tracked")
        st.caption(
            "These starters were not projected because there was not enough legitimate starter history. "
            "Their final strikeouts, hits allowed, outs, batters faced, and pitches will still be saved so future starts can use the new data."
        )
        for pitcher in history_only:
            st.write(f"- {pitcher}")

    if errors:
        st.warning("Some announced starters hit real capture errors:")
        for error in errors:
            st.write(f"- {error}")

st.markdown('<div class="daily-section-head">Manual Paid Data</div>', unsafe_allow_html=True)
st.markdown('<div class="daily-note paid">Optional market-data pull · manual only · strikeout lines only · saved snapshot is reused elsewhere without another paid request.</div>', unsafe_allow_html=True)
st.markdown('<div class="daily-action-label">💳 Paid strikeout lines</div>', unsafe_allow_html=True)
st.caption("Manual only. This button is the ONLY paid Odds API path and requests pitcher_strikeouts only. The saved snapshot is reused by Main Projections without another API call.")
if st.button("💳 LOAD STRIKEOUT LINES · PAID API", use_container_width=True, key="daily_paid_k_odds"):
    api_key=resolve_api_key(st.secrets)
    with st.spinner("Loading today's main pitcher strikeout lines once and saving the snapshot..."):
        odds_snapshot,quota,odds_error=refresh_strikeout_snapshot(api_key,slate_date.isoformat())
    if odds_error:
        st.error(odds_error)
    else:
        pitchers=int(odds_snapshot.get("pitcher",pd.Series(dtype=str)).nunique()) if not odds_snapshot.empty else 0
        active_lines = apply_paid_strikeout_lines(odds_snapshot, slate_date.isoformat())
        st.success(f"Saved {len(odds_snapshot)} strikeout offers for {pitchers} pitchers and applied {active_lines} active K line(s) for Top Plays. Manual K lines override these paid lines.")
        if quota:
            st.caption(f"Last paid request: {quota.get('last','—')} credit(s) · {quota.get('remaining','—')} remaining · {quota.get('used','—')} used.")


st.markdown('<div class="daily-section-head">Persistent History-Only Tracker</div>', unsafe_allow_html=True)
st.caption(
    "These rows live in starter_observation_log.csv, separate from projection_log.csv. "
    "They are real starter observations collected specifically for pitchers who could not yet receive a legitimate projection."
)
history_rows = history_only_for_day(slate_date.isoformat())
if history_rows.empty:
    st.info("No history-only starter observations are recorded for this slate date.")
else:
    resolved_count = int(history_rows["observation_status"].eq("RESOLVED").sum())
    pending_count = int(history_rows["observation_status"].eq("PENDING").sum())
    h1, h2, h3 = st.columns(3)
    h1.metric("History-only starts", len(history_rows))
    h2.metric("Pending results", pending_count)
    h3.metric("Resolved into history", resolved_count)

    history_display_cols = [
        "player", "team", "opponent", "reason", "history_games_available_at_capture",
        "observation_status", "actual_strikeouts", "actual_hits_allowed", "actual_outs",
        "actual_batters_faced", "actual_pitches", "resolved_at_utc",
    ]
    history_display_cols = [col for col in history_display_cols if col in history_rows.columns]
    history_display = history_rows[history_display_cols].copy().rename(columns={
        "player": "Pitcher",
        "team": "Team",
        "opponent": "Opp",
        "reason": "Tracking Reason",
        "history_games_available_at_capture": "Starts Available",
        "observation_status": "Status",
        "actual_strikeouts": "Actual K",
        "actual_hits_allowed": "Actual Hits Allowed",
        "actual_outs": "Actual Outs",
        "actual_batters_faced": "Actual BF",
        "actual_pitches": "Actual Pitches",
        "resolved_at_utc": "Resolved At",
    })
    st.dataframe(history_display, hide_index=True, use_container_width=True)
    st.caption(
        "When a row resolves, its full starter line becomes eligible fallback history for that pitcher on a future start. "
        "It never becomes a fake historical projection or calibration row."
    )

st.markdown('<div class="daily-section-head">Resolve Completed Games</div>', unsafe_allow_html=True)
if st.button("Resolve completed projection outcomes"):
    frame = load_log()
    updated = 0
    observation_updates = 0
    with st.spinner("Checking MLB results for projected and history-only starters..."):
        if not frame.empty:
            for idx in frame.index:
                actual_k, actual_hits, actual_outs, resolved = resolve_row(frame.loc[idx])
                actual_bf, actual_pitches = resolve_workload_actuals(frame.loc[idx])
                changed = False
                if pd.notna(actual_k) and pd.isna(frame.loc[idx].get("actual_strikeouts")):
                    frame.at[idx, "actual_strikeouts"] = actual_k
                    changed = True
                if pd.notna(actual_hits) and pd.isna(frame.loc[idx].get("actual_hits_allowed")):
                    frame.at[idx, "actual_hits_allowed"] = actual_hits
                    changed = True
                if pd.notna(actual_outs) and pd.isna(frame.loc[idx].get("actual_outs")):
                    frame.at[idx, "actual_outs"] = actual_outs
                    changed = True
                if pd.notna(actual_bf) and pd.isna(frame.loc[idx].get("actual_batters_faced")):
                    frame.at[idx, "actual_batters_faced"] = actual_bf
                    changed = True
                if pd.notna(actual_pitches) and pd.isna(frame.loc[idx].get("actual_pitches")):
                    frame.at[idx, "actual_pitches"] = actual_pitches
                    changed = True
                if changed:
                    frame.at[idx, "resolved_at_utc"] = resolved
                    updated += 1
            save_log(frame)
        observation_updates = resolve_observation_log()
    if updated or observation_updates:
        st.success(
            f"Resolved {updated} new projection outcome(s) and {observation_updates} history-only starter observation(s)."
        )
    else:
        st.info("No new completed projected or history-only starter outcomes were available.")

archive = load_log()
if not archive.empty and "game_date" in archive.columns:
    day_rows = archive.loc[archive["game_date"].astype(str).eq(slate_date.isoformat())].copy()
    if not day_rows.empty:
        actual_k = pd.to_numeric(day_rows.get("actual_strikeouts"), errors="coerce")
        actual_hits = pd.to_numeric(day_rows.get("actual_hits_allowed"), errors="coerce")
        actual_outs = pd.to_numeric(day_rows.get("actual_outs"), errors="coerce")
        st.caption(
            f"Projection log currently contains {len(day_rows)} snapshot(s) for this slate; "
            f"{int(actual_k.notna().sum())} have resolved strikeouts and "
            f"{int(actual_hits.notna().sum())} have resolved hits allowed and "
            f"{int(actual_outs.notna().sum())} have resolved outs."
        )

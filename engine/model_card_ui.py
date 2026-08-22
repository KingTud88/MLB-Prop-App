from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from engine.calibration import calibration_summary
from engine.hits_calibration import calibrate_hits_blend, hits_calibration_report
from engine.outs_calibration import calibrate_outs_blend, outs_calibration_report


ExplainCallback = Callable[[str, str], None]


def build_path_table(
    *,
    simulation_mean: float,
    simulation_sd: float,
    mathematical_mean: float,
    mathematical_sd: float,
    ensemble_mean: float,
    ensemble_sd: float,
    mean_label: str,
) -> pd.DataFrame:
    """Return presentation-only SIM / MATH / ensemble path values."""
    return pd.DataFrame(
        [
            {"Path": "Simulation", mean_label: float(simulation_mean), "SD": float(simulation_sd)},
            {"Path": "Mathematical", mean_label: float(mathematical_mean), "SD": float(mathematical_sd)},
            {"Path": "Ensemble", mean_label: float(ensemble_mean), "SD": float(ensemble_sd)},
        ]
    )


def build_probability_table(
    *,
    simulation_probabilities: dict[float, float],
    mathematical_probabilities: dict[float, float],
    history: pd.DataFrame,
    calibrator: Callable[[pd.DataFrame, float], object],
) -> pd.DataFrame:
    """Blend already-produced milestone probabilities with the existing calibrator."""
    lines = sorted(set(simulation_probabilities) & set(mathematical_probabilities))
    rows: list[dict[str, object]] = []
    for line in lines:
        line = float(line)
        simulation = float(simulation_probabilities[line])
        mathematical = float(mathematical_probabilities[line])
        calibration = calibrator(history, line)
        simulation_weight = float(calibration.weight_simulation)
        probability = simulation_weight * simulation + (1.0 - simulation_weight) * mathematical
        rows.append(
            {
                "Line": line,
                "Probability": probability,
                "Simulation": simulation,
                "Math": mathematical,
                "Sim Weight": simulation_weight,
            }
        )
    return pd.DataFrame(rows, columns=["Line", "Probability", "Simulation", "Math", "Sim Weight"])


def _format_path_table(frame: pd.DataFrame, mean_label: str) -> pd.DataFrame:
    display = frame.copy()
    display[mean_label] = pd.to_numeric(display[mean_label], errors="coerce").map(
        lambda value: "—" if pd.isna(value) else f"{float(value):.2f}"
    )
    display["SD"] = pd.to_numeric(display["SD"], errors="coerce").map(
        lambda value: "—" if pd.isna(value) else f"{float(value):.2f}"
    )
    return display


def _format_probability_table(frame: pd.DataFrame, *, half_run_line: bool) -> pd.DataFrame:
    display = frame.copy()
    if half_run_line:
        display["Line"] = pd.to_numeric(display["Line"], errors="coerce").map(
            lambda value: "—" if pd.isna(value) else f"Over {float(value):g}"
        )
    for column in ("Probability", "Simulation", "Math", "Sim Weight"):
        display[column] = pd.to_numeric(display[column], errors="coerce").map(
            lambda value: "—" if pd.isna(value) else f"{float(value):.1%}"
        )
    return display


def _format_calibration_report(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    for column in ("Simulation Weight", "Math Weight"):
        if column in display.columns:
            display[column] = pd.to_numeric(display[column], errors="coerce").map(
                lambda value: "—" if pd.isna(value) else f"{float(value):.1%}"
            )
    if "Calibrated Brier" in display.columns:
        display["Calibrated Brier"] = pd.to_numeric(display["Calibrated Brier"], errors="coerce").map(
            lambda value: "—" if pd.isna(value) else f"{float(value):.4f}"
        )
    return display


def _explain(explain: ExplainCallback | None, key: str, label: str) -> None:
    if explain is not None:
        explain(key, label)


def render_model_card_markets(
    *,
    proj: object,
    kdf: pd.DataFrame,
    hits_proj: object,
    history: pd.DataFrame,
    render_k_calibration_dashboard: Callable[[], None],
    explain: ExplainCallback | None = None,
) -> None:
    """Render three-market Model Card parity from existing projection outputs only."""
    st.markdown('<div class="section-head">MODEL CARD</div>', unsafe_allow_html=True)
    st.write(
        "Each market keeps independent simulation and mathematical paths, then displays the existing ensemble and "
        "starter-only calibration context. Sportsbook prices are execution-only and are not inputs to these tables."
    )

    strikeouts_tab, hits_tab, outs_tab = st.tabs(["Strikeouts", "Hits Allowed", "Outs"])

    with strikeouts_tab:
        st.markdown("### Path comparison")
        strikeout_paths = build_path_table(
            simulation_mean=proj.engine.simulation_mean,
            simulation_sd=proj.engine.simulation_sd,
            mathematical_mean=proj.engine.mathematical_mean,
            mathematical_sd=proj.engine.mathematical_sd,
            ensemble_mean=proj.mean_k,
            ensemble_sd=proj.k_sd,
            mean_label="Mean K",
        )
        st.dataframe(_format_path_table(strikeout_paths, "Mean K"), use_container_width=True, hide_index=True)
        _explain(explain, "model_paths", "ⓘ EXPLAIN MODEL PATHS")

        st.markdown("### Milestone probabilities")
        model_view = kdf[["Line", "Probability", "Simulation", "Math", "Sim Weight"]].copy()
        for column in ("Probability", "Simulation", "Math", "Sim Weight"):
            model_view[column] = pd.to_numeric(model_view[column], errors="coerce").map(
                lambda value: "—" if pd.isna(value) else f"{float(value):.1%}"
            )
        st.dataframe(model_view, use_container_width=True, hide_index=True)
        _explain(explain, "model_ladder", "ⓘ EXPLAIN MILESTONE TABLE")

        st.markdown("### Calibration diagnostics")
        render_k_calibration_dashboard()
        st.dataframe(calibration_summary(history), use_container_width=True, hide_index=True)
        _explain(explain, "calibration", "ⓘ EXPLAIN CALIBRATION")

    with hits_tab:
        st.markdown("### Path comparison")
        hits_paths = build_path_table(
            simulation_mean=hits_proj.simulation_mean,
            simulation_sd=hits_proj.simulation_sd,
            mathematical_mean=hits_proj.mathematical_mean,
            mathematical_sd=hits_proj.mathematical_sd,
            ensemble_mean=hits_proj.ensemble_mean,
            ensemble_sd=hits_proj.ensemble_sd,
            mean_label="Mean Hits",
        )
        st.dataframe(_format_path_table(hits_paths, "Mean Hits"), use_container_width=True, hide_index=True)

        st.markdown("### Milestone probabilities")
        hits_probabilities = build_probability_table(
            simulation_probabilities=hits_proj.simulation_probabilities,
            mathematical_probabilities=hits_proj.mathematical_probabilities,
            history=history,
            calibrator=calibrate_hits_blend,
        )
        st.dataframe(
            _format_probability_table(hits_probabilities, half_run_line=True),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Calibration diagnostics")
        st.caption("Starter-only frozen resolved Hits Allowed projections; sportsbook prices are excluded.")
        st.dataframe(
            _format_calibration_report(hits_calibration_report(history)),
            use_container_width=True,
            hide_index=True,
        )

    with outs_tab:
        outs_proj = proj.outs_engine
        st.markdown("### Path comparison")
        outs_paths = build_path_table(
            simulation_mean=outs_proj.simulation_mean,
            simulation_sd=outs_proj.simulation_sd,
            mathematical_mean=outs_proj.mathematical_mean,
            mathematical_sd=outs_proj.mathematical_sd,
            ensemble_mean=outs_proj.ensemble_mean,
            ensemble_sd=outs_proj.ensemble_sd,
            mean_label="Mean Outs",
        )
        st.dataframe(_format_path_table(outs_paths, "Mean Outs"), use_container_width=True, hide_index=True)

        st.markdown("### Milestone probabilities")
        outs_probabilities = build_probability_table(
            simulation_probabilities=outs_proj.simulation_probabilities,
            mathematical_probabilities=outs_proj.mathematical_probabilities,
            history=history,
            calibrator=calibrate_outs_blend,
        )
        st.dataframe(
            _format_probability_table(outs_probabilities, half_run_line=True),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Calibration diagnostics")
        st.caption("Starter-only frozen resolved Outs projections; sportsbook prices are excluded.")
        st.dataframe(
            _format_calibration_report(outs_calibration_report(history)),
            use_container_width=True,
            hide_index=True,
        )

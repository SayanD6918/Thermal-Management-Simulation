"""Streamlit dashboard for the validated thermal-management models.

Run locally with:
    streamlit run dashboard.py
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import dashboard_logic as dl
from stage3_parameter_studies import BASE as TWO_NODE_BASE
from stage3_parameter_studies import STUDIES

st.set_page_config(
    page_title="Thermal Management Simulation",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SINGLE_DEFAULT = dl.SINGLE_NODE_DEFAULT
TWO_DEFAULT = TWO_NODE_BASE


def _init_state() -> None:
    if "mode" not in st.session_state:
        st.session_state.mode = "Two-node"
    if "single_values" not in st.session_state:
        st.session_state.single_values = {
            "heat_generation_W": SINGLE_DEFAULT.heat_generation_W,
            "mass_kg": SINGLE_DEFAULT.mass_kg,
            "specific_heat_J_per_kgK": SINGLE_DEFAULT.specific_heat_J_per_kgK,
            "area_m2": SINGLE_DEFAULT.area_m2,
            "h_W_per_m2K": SINGLE_DEFAULT.h_W_per_m2K,
            "ambient_C": SINGLE_DEFAULT.ambient_C,
            "initial_C": SINGLE_DEFAULT.initial_C,
            "duration_s": SINGLE_DEFAULT.duration_s,
            "dt_s": SINGLE_DEFAULT.dt_s,
        }
    if "two_values" not in st.session_state:
        st.session_state.two_values = {
            "heat_generation_W": TWO_DEFAULT.heat_generation_W,
            "component_mass_kg": TWO_DEFAULT.component_mass_kg,
            "component_specific_heat_J_per_kgK": TWO_DEFAULT.component_specific_heat_J_per_kgK,
            "wall_mass_kg": TWO_DEFAULT.wall_mass_kg,
            "wall_specific_heat_J_per_kgK": TWO_DEFAULT.wall_specific_heat_J_per_kgK,
            "conduction_thickness_m": TWO_DEFAULT.conduction_thickness_m,
            "conduction_conductivity_W_per_mK": TWO_DEFAULT.conduction_conductivity_W_per_mK,
            "conduction_area_m2": TWO_DEFAULT.conduction_area_m2,
            "convection_h_W_per_m2K": TWO_DEFAULT.convection_h_W_per_m2K,
            "convection_area_m2": TWO_DEFAULT.convection_area_m2,
            "ambient_C": TWO_DEFAULT.ambient_C,
            "initial_component_C": TWO_DEFAULT.initial_component_C,
            "initial_wall_C": TWO_DEFAULT.initial_wall_C,
            "duration_s": TWO_DEFAULT.duration_s,
            "dt_s": TWO_DEFAULT.dt_s,
        }
    if "threshold_C" not in st.session_state:
        st.session_state.threshold_C = dl.TWO_NODE_THRESHOLD_DEFAULT
    if "current_result" not in st.session_state:
        st.session_state.current_result = None
    if "scenario_results" not in st.session_state:
        st.session_state.scenario_results = []


def _reset_defaults() -> None:
    st.session_state.single_values = {
        "heat_generation_W": SINGLE_DEFAULT.heat_generation_W,
        "mass_kg": SINGLE_DEFAULT.mass_kg,
        "specific_heat_J_per_kgK": SINGLE_DEFAULT.specific_heat_J_per_kgK,
        "area_m2": SINGLE_DEFAULT.area_m2,
        "h_W_per_m2K": SINGLE_DEFAULT.h_W_per_m2K,
        "ambient_C": SINGLE_DEFAULT.ambient_C,
        "initial_C": SINGLE_DEFAULT.initial_C,
        "duration_s": SINGLE_DEFAULT.duration_s,
        "dt_s": SINGLE_DEFAULT.dt_s,
    }
    st.session_state.two_values = {
        "heat_generation_W": TWO_DEFAULT.heat_generation_W,
        "component_mass_kg": TWO_DEFAULT.component_mass_kg,
        "component_specific_heat_J_per_kgK": TWO_DEFAULT.component_specific_heat_J_per_kgK,
        "wall_mass_kg": TWO_DEFAULT.wall_mass_kg,
        "wall_specific_heat_J_per_kgK": TWO_DEFAULT.wall_specific_heat_J_per_kgK,
        "conduction_thickness_m": TWO_DEFAULT.conduction_thickness_m,
        "conduction_conductivity_W_per_mK": TWO_DEFAULT.conduction_conductivity_W_per_mK,
        "conduction_area_m2": TWO_DEFAULT.conduction_area_m2,
        "convection_h_W_per_m2K": TWO_DEFAULT.convection_h_W_per_m2K,
        "convection_area_m2": TWO_DEFAULT.convection_area_m2,
        "ambient_C": TWO_DEFAULT.ambient_C,
        "initial_component_C": TWO_DEFAULT.initial_component_C,
        "initial_wall_C": TWO_DEFAULT.initial_wall_C,
        "duration_s": TWO_DEFAULT.duration_s,
        "dt_s": TWO_DEFAULT.dt_s,
    }
    st.session_state.threshold_C = (
        dl.SINGLE_THRESHOLD_DEFAULT if st.session_state.mode == "Single-node" else dl.TWO_NODE_THRESHOLD_DEFAULT
    )
    st.session_state.current_result = None


def _load_example(name: str) -> None:
    if st.session_state.mode == "Single-node":
        st.session_state.single_values = dl.apply_example(
            "Single-node", name, st.session_state.single_values
        )
    else:
        st.session_state.two_values = dl.apply_example(
            "Two-node", name, st.session_state.two_values
        )
    st.session_state.current_result = None


def _number_input(label: str, key: str, value: float, unit: str, *, min_value: float | None = None, help_text: str | None = None) -> float:
    return st.number_input(
        f"{label} [{unit}]",
        min_value=min_value,
        value=float(value),
        format="%.6g",
        key=key,
        help=help_text,
    )


def _collect_single_inputs() -> tuple[dict[str, float], float]:
    v = st.session_state.single_values
    c1, c2 = st.columns(2)
    with c1:
        v["heat_generation_W"] = _number_input("Heat generation", "s_q", v["heat_generation_W"], "W", min_value=0.0, help_text="Net heat generated by the component.")
        v["mass_kg"] = _number_input("Component mass", "s_m", v["mass_kg"], "kg", min_value=1e-12)
        v["specific_heat_J_per_kgK"] = _number_input("Specific heat", "s_cp", v["specific_heat_J_per_kgK"], "J/(kg K)", min_value=1e-12)
        v["area_m2"] = _number_input("Effective exposed area", "s_area", v["area_m2"], "m²", min_value=1e-12)
        v["h_W_per_m2K"] = _number_input("Convection coefficient", "s_h", v["h_W_per_m2K"], "W/(m² K)", min_value=1e-12)
    with c2:
        v["ambient_C"] = _number_input("Ambient temperature", "s_amb", v["ambient_C"], "°C")
        v["initial_C"] = _number_input("Initial component temperature", "s_init", v["initial_C"], "°C")
        v["duration_s"] = _number_input("Simulation duration", "s_duration", v["duration_s"], "s", min_value=1e-12)
        v["dt_s"] = _number_input("Time step", "s_dt", v["dt_s"], "s", min_value=1e-12)
        st.session_state.threshold_C = _number_input("Temperature threshold", "s_threshold", st.session_state.threshold_C, "°C")
    return dict(v), float(st.session_state.threshold_C)


def _collect_two_inputs() -> tuple[dict[str, float], float]:
    v = st.session_state.two_values
    c1, c2 = st.columns(2)
    with c1:
        v["heat_generation_W"] = _number_input("Heat generation", "t_q", v["heat_generation_W"], "W", min_value=0.0)
        v["component_mass_kg"] = _number_input("Component mass", "t_cm", v["component_mass_kg"], "kg", min_value=1e-12)
        v["component_specific_heat_J_per_kgK"] = _number_input("Component specific heat", "t_ccp", v["component_specific_heat_J_per_kgK"], "J/(kg K)", min_value=1e-12)
        v["wall_mass_kg"] = _number_input("Wall mass", "t_wm", v["wall_mass_kg"], "kg", min_value=1e-12)
        v["wall_specific_heat_J_per_kgK"] = _number_input("Wall specific heat", "t_wcp", v["wall_specific_heat_J_per_kgK"], "J/(kg K)", min_value=1e-12)
        v["conduction_thickness_m"] = _number_input("Conduction thickness", "t_L", v["conduction_thickness_m"], "m", min_value=1e-12)
        v["conduction_conductivity_W_per_mK"] = _number_input("Conduction conductivity", "t_k", v["conduction_conductivity_W_per_mK"], "W/(m K)", min_value=1e-12)
        v["conduction_area_m2"] = _number_input("Conduction area", "t_Ac", v["conduction_area_m2"], "m²", min_value=1e-12)
    with c2:
        v["convection_h_W_per_m2K"] = _number_input("Convection coefficient", "t_h", v["convection_h_W_per_m2K"], "W/(m² K)", min_value=1e-12)
        v["convection_area_m2"] = _number_input("Convection area", "t_Av", v["convection_area_m2"], "m²", min_value=1e-12)
        v["ambient_C"] = _number_input("Ambient temperature", "t_amb", v["ambient_C"], "°C")
        v["initial_component_C"] = _number_input("Initial component temperature", "t_ic", v["initial_component_C"], "°C")
        v["initial_wall_C"] = _number_input("Initial wall temperature", "t_iw", v["initial_wall_C"], "°C")
        v["duration_s"] = _number_input("Simulation duration", "t_duration", v["duration_s"], "s", min_value=1e-12)
        v["dt_s"] = _number_input("Time step", "t_dt", v["dt_s"], "s", min_value=1e-12)
        st.session_state.threshold_C = _number_input("Temperature threshold", "t_threshold", st.session_state.threshold_C, "°C")
    st.caption("Conduction resistance is derived as R_cond = L/(kA). Convection resistance is derived as R_conv = 1/(hA).")
    return dict(v), float(st.session_state.threshold_C)


def _plot_result(result: dict, *, compare_results: list[dict] | None = None) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    t = result["time_s"]
    ax.plot(t, result["component_C"], label="Component", linewidth=2)
    ax.plot(t, result["analytical_component_C"], linestyle="--", label="Component analytical")
    if result["wall_C"] is not None:
        ax.plot(t, result["wall_C"], label="Wall", linewidth=2)
        ax.plot(t, result["analytical_wall_C"], linestyle="--", label="Wall analytical")
    ax.axhline(result["ambient_C"], linestyle=":", label=f"Ambient ({result['ambient_C']:.1f} °C)")
    ax.axhline(result["threshold_C"], linestyle="-.", label=f"Threshold ({result['threshold_C']:.1f} °C)")
    ax.axhline(result["component_ss_C"], linestyle=":", label=f"Component steady state ({result['component_ss_C']:.2f} °C)")
    if result["wall_ss_C"] is not None:
        ax.axhline(result["wall_ss_C"], linestyle=":", label=f"Wall steady state ({result['wall_ss_C']:.2f} °C)")
    if compare_results:
        for r in compare_results:
            ax.plot(r["time_s"], r["component_C"], alpha=0.75, label=f"{r.get('scenario', 'Scenario')} component")
            if r["wall_C"] is not None:
                ax.plot(r["time_s"], r["wall_C"], linestyle="--", alpha=0.75, label=f"{r.get('scenario', 'Scenario')} wall")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Temperature [°C]")
    ax.set_title(f"{result['mode']} thermal response")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8, ncol=2)
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True, use_container_width=True)


def _render_results(result: dict) -> None:
    st.subheader("Results summary")
    cols = st.columns(4)
    cols[0].metric("Final component", f"{result['component_C'][-1]:.2f} °C")
    cols[1].metric("Maximum component", f"{np.max(result['component_C']):.2f} °C")
    cols[2].metric("Component steady state", f"{result['component_ss_C']:.2f} °C")
    cols[3].metric("Threshold crossing", "Not reached" if result["threshold_num_s"] is None else f"{result['threshold_num_s']:.1f} s")
    if result["wall_C"] is not None:
        cols = st.columns(4)
        cols[0].metric("Final wall", f"{result['wall_C'][-1]:.2f} °C")
        cols[1].metric("Wall steady state", f"{result['wall_ss_C']:.2f} °C")
        cols[2].metric("Slow time constant", f"{result['time_constant_s']:.1f} s")
        cols[3].metric("Fast time constant", f"{result['fast_time_constant_s']:.2f} s")
    else:
        st.metric("Thermal time constant", f"{result['time_constant_s']:.1f} s")

    if result["reached_steady_state"]:
        st.success(f"Simulation endpoint is within ±{dl.STEADY_STATE_TOLERANCE_K:g} K of the analytical steady state.")
    else:
        st.info(f"Simulation endpoint has not demonstrated steady-state convergence within ±{dl.STEADY_STATE_TOLERANCE_K:g} K; the final temperature is not labelled as steady state.")

    _plot_result(result)

    with st.expander("Numerical verification and energy balance"):
        st.write(f"Maximum component numerical-vs-analytical error: {result['max_error_component_K']:.3e} K")
        if result["wall_C"] is not None:
            st.write(f"Maximum wall numerical-vs-analytical error: {result['max_error_wall_K']:.3e} K")
        st.json(result["energy"])


def _scenario_editor(mode: str, slot: int) -> tuple[str, dict[str, float], float]:
    base = dict(st.session_state.single_values if mode == "Single-node" else st.session_state.two_values)
    key_prefix = f"sc{slot}_"
    name = st.text_input("Scenario name", value=f"Scenario {slot}", key=key_prefix + "name")
    compatible = {
        "Single-node": {
            "Heat generation": "heat_generation_W",
            "Ambient temperature": "ambient_C",
            "Convection coefficient": "h_W_per_m2K",
            "Component mass": "mass_kg",
        },
        "Two-node": {
            "Heat generation": "heat_generation_W",
            "Ambient temperature": "ambient_C",
            "Conduction thickness": "conduction_thickness_m",
            "Convection coefficient": "convection_h_W_per_m2K",
            "Convection area": "convection_area_m2",
            "Component mass": "component_mass_kg",
            "Wall mass": "wall_mass_kg",
        },
    }[mode]
    label = st.selectbox("Parameter to vary", list(compatible), key=key_prefix + "param")
    field = compatible[label]
    default = float(base[field])
    value = st.number_input("Scenario value", value=default, format="%.6g", key=key_prefix + "value")
    scenario_values = dict(base)
    scenario_values[field] = value
    if mode == "Two-node" and field == "ambient_C":
        scenario_values["initial_component_C"] = value
        scenario_values["initial_wall_C"] = value
    if mode == "Single-node" and field == "ambient_C":
        scenario_values["initial_C"] = value
    threshold = float(st.session_state.threshold_C)
    return name or f"Scenario {slot}", scenario_values, threshold


def _render_scenarios(mode: str) -> None:
    st.subheader("User-selected scenario comparison")
    st.caption("These are dashboard scenarios, distinct from the predefined Stage 3 sensitivity grids. Each scenario reuses the selected model implementation.")
    count = st.slider("Number of comparison scenarios", 1, 3, 2)
    editors = st.columns(count)
    scenario_specs = []
    for i, col in enumerate(editors, start=1):
        with col:
            scenario_specs.append(_scenario_editor(mode, i))
    if st.button("Run scenario comparison", type="primary"):
        results = []
        try:
            base_values = dict(st.session_state.single_values if mode == "Single-node" else st.session_state.two_values)
            base_result = dl.run_model(mode, base_values, float(st.session_state.threshold_C))
            base_result["scenario"] = "Current configuration"
            results.append(base_result)
            for name, values, threshold in scenario_specs:
                r = dl.run_model(mode, values, threshold)
                r["scenario"] = name
                results.append(r)
            st.session_state.scenario_results = results
        except ValueError as exc:
            st.error(f"Scenario input error: {exc}")
    results = st.session_state.scenario_results
    if results:
        st.dataframe(dl.scenario_comparison_dataframe(results), use_container_width=True, hide_index=True)
        _plot_result(results[0], compare_results=results[1:])
        st.download_button(
            "Download scenario comparison CSV",
            data=dl.make_download_bytes(dl.scenario_comparison_dataframe(results)),
            file_name="thermal_scenario_comparison.csv",
            mime="text/csv",
        )


@st.cache_data(show_spinner=False)
def _cached_stage3_study(study_name: str) -> pd.DataFrame:
    field, values = STUDIES[study_name]
    rows = []
    for value in values:
        changes = {field: value}
        if field == "ambient_C":
            changes["initial_component_C"] = value
            changes["initial_wall_C"] = value
        p = TWO_NODE_BASE.with_changes(**changes)
        r = dl.run_two_node(p, dl.TWO_NODE_THRESHOLD_DEFAULT)
        rows.append({
            "study": study_name,
            "parameter": field,
            "value": value,
            "unit": dl._PARAMETER_UNITS.get(field, ""),
            "component_steady_state_C": r["component_ss_C"],
            "wall_steady_state_C": r["wall_ss_C"],
            "threshold_time_s": r["threshold_num_s"],
        })
    return pd.DataFrame(rows)


def _render_stage3_reference() -> None:
    st.subheader("Predefined Stage 3 sensitivity studies")
    study_name = st.selectbox("Study", list(STUDIES), key="stage3_study")
    field, _ = STUDIES[study_name]
    df = _cached_stage3_study(study_name)
    st.dataframe(df, use_container_width=True, hide_index=True)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(df["value"], df["component_steady_state_C"], marker="o", label="Component")
    ax.plot(df["value"], df["wall_steady_state_C"], marker="s", label="Wall")
    ax.set_xlabel(f"{field} [{dl._PARAMETER_UNITS.get(field, '')}]")
    ax.set_ylabel("Steady-state temperature [°C]")
    ax.set_title(f"Stage 3 — {study_name.replace('_', ' ').title()}")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True, use_container_width=True)
    st.download_button("Download Stage 3 study CSV", data=dl.make_download_bytes(df), file_name=f"stage3_{study_name}.csv", mime="text/csv")


def main() -> None:
    _init_state()
    st.title("Thermal Management of Electronic Components Under Varying Environmental Conditions")
    st.caption("Engineering dashboard for the validated Stage 1–3 lumped thermal models")

    with st.sidebar:
        st.header("Simulation setup")
        mode = st.radio("Model selection", ["Single-node", "Two-node"], index=0 if st.session_state.mode == "Single-node" else 1)
        if mode != st.session_state.mode:
            st.session_state.mode = mode
            st.session_state.current_result = None
            st.session_state.threshold_C = dl.SINGLE_THRESHOLD_DEFAULT if mode == "Single-node" else dl.TWO_NODE_THRESHOLD_DEFAULT
        example = st.selectbox("Documented example scenario", list(dl.EXAMPLE_SCENARIOS), help="Loads documented illustrative settings; values are not experimental limits.")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Load example"):
                _load_example(example)
                st.rerun()
        with b2:
            if st.button("Reset defaults"):
                _reset_defaults()
                st.rerun()
        st.divider()
        st.info("Default parameters are illustrative unless a documented Stage 3 reference is explicitly identified. No CFD/FEM/3-D field solution is performed.")

    st.markdown("### Overview")
    c1, c2, c3 = st.columns(3)
    c1.info(f"**Current simulation mode:** {mode}")
    c2.info("**Heat path:** component heat generation → conduction to enclosure wall → convection to ambient air")
    c3.info("**Scope:** lumped thermal model; not a 3-D CFD or finite-element simulation")

    st.markdown("### Simulation inputs")
    if mode == "Single-node":
        values, threshold = _collect_single_inputs()
        st.caption("The single-node model represents one spatially uniform lumped thermal mass with an effective convective boundary.")
    else:
        values, threshold = _collect_two_inputs()
        st.caption("The two-node model resolves a spatially uniform component node and enclosure-wall node; the wall then rejects heat by convection.")

    if st.button("Run simulation", type="primary", use_container_width=True):
        try:
            result = dl.run_model(mode, values, threshold)
            st.session_state.current_result = result
            st.session_state.scenario_results = []
        except ValueError as exc:
            st.session_state.current_result = None
            st.error(f"Simulation input error: {exc}")

    result = st.session_state.current_result
    if result is not None:
        _render_results(result)
        st.markdown("### Data export")
        e1, e2, e3 = st.columns(3)
        with e1:
            ts = dl.current_timeseries_dataframe(result)
            st.download_button("Download current time series CSV", data=dl.make_download_bytes(ts), file_name="thermal_current_timeseries.csv", mime="text/csv")
        with e2:
            ps = dl.parameter_summary_dataframe(result)
            st.download_button("Download parameter summary CSV", data=dl.make_download_bytes(ps), file_name="thermal_parameter_summary.csv", mime="text/csv")
        with e3:
            st.download_button("Download text summary", data=dl.make_summary_text(result).encode("utf-8"), file_name="thermal_simulation_summary.txt", mime="text/plain")

    tab1, tab2, tab3 = st.tabs(["Scenario comparison", "Stage 3 studies", "Assumptions & limitations"])
    with tab1:
        _render_scenarios(mode)
    with tab2:
        if mode == "Two-node":
            _render_stage3_reference()
        else:
            st.info("The predefined Stage 3 sensitivity studies are based on the validated two-node implementation. Use the single-node mode above for the Stage 1 model itself.")
    with tab3:
        st.subheader("Model assumptions and limitations")
        with st.expander("Governing equations", expanded=True):
            st.markdown(
                "**Single-node:** `m cp dT/dt = Q_gen − hA(T − T_inf)`\n\n"
                "**Two-node:** `Cc dTc/dt = Q_gen − (Tc − Tw)/R_cond` and `Cw dTw/dt = (Tc − Tw)/R_cond − (Tw − T_inf)/R_conv`."
            )
        with st.expander("Engineering assumptions"):
            st.markdown(
                "- Temperatures are spatially uniform within each lumped node.\n"
                "- Properties, heat generation, ambient temperature, resistance and convection inputs are constant during a run.\n"
                "- Radiation, internal enclosure air, contact resistance and additional heat paths are excluded.\n"
                "- Ambient temperature is an imposed boundary condition.\n"
                "- `h` is an input/scenario assumption in the two-node model; it is not solved from CFD.\n"
                "- Default values are illustrative unless explicitly identified as reference data."
            )
        with st.expander("Validation and applicability"):
            st.markdown(
                f"- The dashboard reuses the existing validated Stage 1/2 model functions.\n"
                f"- Analytical-vs-numerical transient checks are shown after successful runs.\n"
                f"- The endpoint is considered converged only within ±{dl.STEADY_STATE_TOLERANCE_K:g} K of the analytical steady state.\n"
                "- Stage 3's wall Biot check supports only the stated illustrative material/geometry case; low Biot number does not validate the complete enclosure model.\n"
                "- No experimental validation is claimed.\n"
                "- High-altitude scenarios use idealized standard-atmosphere conditions and the explicitly documented simplified convection scaling; altitude alone does not determine `h`."
            )
        with st.expander("Scope boundary"):
            st.markdown("This application does **not** implement 3-D CFD, finite-element analysis, radiation, hardware integration, cloud services, databases, user accounts, or external APIs.")


if __name__ == "__main__":
    main()
